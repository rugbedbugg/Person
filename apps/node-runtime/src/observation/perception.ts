import { distance, positionKey, type Position } from "#config";
import type { BlockKind, BlockView } from "../embodiment/types.ts";

/**
 * Perception shaping.
 *
 * The first real observation exposed the problem this file exists to solve: a
 * single "nearest N blocks" search standing on stone returned fifty-five stone
 * blocks and nine coal, and every tree in the valley was invisible to
 * cognition. A budget spent on the most abundant thing in range is a budget
 * spent on the least informative thing in range.
 *
 * So perception is shaped rather than truncated. Each resource category gets a
 * guaranteed share of the observation, a small overflow budget is handed to
 * whatever is nearest after that, and the total stays bounded. Passive animals
 * are reported only where Person could actually use them.
 *
 * Two rules constrain everything here:
 *
 * - shaping is not a safety boundary. The runtime keeps the unshaped snapshot;
 *   the safety kernel, the permission gate and the physical guard all read
 *   that. Dropping an animal from the observation cannot make it huntable, and
 *   keeping one cannot make it a legal target.
 * - shaping is deterministic. The same snapshot must produce the same list, so
 *   every ordering has an explicit tie-break rather than relying on the order a
 *   chunk happened to be scanned in.
 */

export type ResourceCategory =
  "wood" | "stone" | "coal" | "plant_food" | "dirt" | "other";

/**
 * Every tunable number perception uses, in one place.
 *
 * These are the limits, not a policy: nothing here decides what Person does,
 * only how much of the world it is told about.
 */
export const PERCEPTION = {
  resources: {
    /** How far the body looks for usable blocks. */
    searchRadius: 48,
    /** Nearest samples guaranteed to each category that has any at all. */
    perCategory: 12,
    /** Extra nearest-first slots shared out after every quota is honoured. */
    overflow: 16,
    /** Hard ceiling on the resource list. */
    total: 64,
  },
  hazards: { searchRadius: 12, total: 32 },
  containers: { searchRadius: 32, total: 16 },
  entities: {
    /**
     * Passive animals are reported only inside the region Person may enter,
     * and only within reach of it. Seventy cows across a continent are not
     * information; the four in the field next door are.
     */
    passiveRadius: 48,
    passiveTotal: 12,
    /** Hostiles are never region-filtered: a threat outside the fence still bites. */
    hostileTotal: 24,
    playerTotal: 8,
  },
} as const;

/** The protocol category a block kind is reported under. */
export function resourceCategory(kind: BlockKind): ResourceCategory {
  switch (kind) {
    case "wood":
      return "wood";
    case "stone":
    case "cobblestone":
      return "stone";
    case "coal_ore":
      return "coal";
    case "plant_food":
    case "leaves":
      return "plant_food";
    case "dirt":
    case "grass":
      return "dirt";
    default:
      return "other";
  }
}

/**
 * What the body searches for, grouped by the category cognition sees.
 *
 * The order is fixed because it is part of the deterministic output: two
 * blocks at exactly the same distance are separated by their position, and
 * two categories competing for the same overflow slot are separated by this
 * list.
 */
export const RESOURCE_SEARCH: readonly {
  category: ResourceCategory;
  kinds: BlockKind[];
}[] = [
  { category: "wood", kinds: ["wood"] },
  { category: "plant_food", kinds: ["plant_food", "leaves"] },
  { category: "coal", kinds: ["coal_ore"] },
  { category: "stone", kinds: ["stone"] },
];

export type ResourceLimits = {
  searchRadius: number;
  perCategory: number;
  overflow: number;
  total: number;
};

const byDistanceThenPosition = (
  origin: Position,
  a: BlockView,
  b: BlockView,
): number => {
  const gap = distance(origin, a.position) - distance(origin, b.position);
  if (gap !== 0) return gap;
  return positionKey(a.position).localeCompare(positionKey(b.position));
};

/** Nearest-first, with a total order so equal distances never shuffle. */
export const nearestBlocks = (
  blocks: readonly BlockView[],
  origin: Position,
): BlockView[] =>
  [...blocks].sort((a, b) => byDistanceThenPosition(origin, a, b));

/**
 * Category-balanced selection.
 *
 * Each group keeps its quota of nearest samples; everything left over competes
 * for the overflow budget on distance alone. The abundant categories therefore
 * still appear, and still appear nearest-first, but they can no longer crowd
 * out a category that has only three members in the whole search volume.
 */
export function balanceResources(
  groups: readonly (readonly BlockView[])[],
  origin: Position,
  limits: ResourceLimits = PERCEPTION.resources,
): BlockView[] {
  const kept: BlockView[] = [];
  const leftover: BlockView[] = [];
  for (const group of groups) {
    const ordered = nearestBlocks(group, origin);
    kept.push(...ordered.slice(0, limits.perCategory));
    leftover.push(...ordered.slice(limits.perCategory));
  }
  const room = Math.max(
    0,
    Math.min(limits.total - kept.length, limits.overflow),
  );
  kept.push(...nearestBlocks(leftover, origin).slice(0, room));
  return nearestBlocks(kept, origin).slice(0, limits.total);
}

/**
 * Runs the balanced search against whichever body is present.
 *
 * Both embodiments call this, so the fixture world and Minecraft shape
 * perception identically and a skill cannot be tuned against a view of the
 * world that only one of them produces.
 */
export function gatherResources(
  find: (kinds: BlockKind[], maxDistance: number, limit: number) => BlockView[],
  origin: Position,
  limits: ResourceLimits = PERCEPTION.resources,
): BlockView[] {
  const perGroup = limits.perCategory + limits.overflow;
  const groups = RESOURCE_SEARCH.map((group) =>
    find(group.kinds, limits.searchRadius, perGroup),
  );
  return balanceResources(groups, origin, limits);
}

/**
 * Bounds an entity list without changing what any of its members mean.
 *
 * `keep` decides relevance and nothing else: an entity that survives it is
 * reported exactly as the runtime classified it, protections included.
 */
export function shapeEntities<
  T extends { entityId: number; distance: number; position: Position },
>(
  entities: readonly T[],
  options: { limit: number; radius?: number; keep?: (entity: T) => boolean },
): T[] {
  return entities
    .filter(
      (entity) =>
        (options.radius === undefined || entity.distance <= options.radius) &&
        (options.keep === undefined || options.keep(entity)),
    )
    .sort((a, b) => a.distance - b.distance || a.entityId - b.entityId)
    .slice(0, options.limit);
}
