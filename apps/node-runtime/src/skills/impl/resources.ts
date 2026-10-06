import {
  SkillFailure,
  type SkillContext,
  type SkillImplementation,
} from "../execution.ts";
import {
  isCoal,
  isLog,
  isPlantFood,
  isStone,
  tally,
  toolTier,
} from "../materials.ts";
import { approach, permittedResources } from "../navigate.ts";
import type { BlockKind } from "../../embodiment/types.ts";

/** Consecutive digs that gained nothing before a harvest gives up. */
const FRUITLESS_LIMIT = 2;

interface HarvestOptions {
  kinds: BlockKind[];
  matches: (name: string) => boolean;
  target: number;
  maxDistance: number;
  effect: string;
}

/**
 * Shared harvesting loop.
 *
 * Every candidate block is checked against the permission gate again at the
 * moment it is dug, not only when it was found: the world can change and a
 * detour can put Person somewhere the original search never considered.
 */
async function harvest(
  context: SkillContext,
  options: HarvestOptions,
): Promise<void> {
  const held = (): number =>
    [...tally(context.snapshot().inventory)].reduce(
      (total, [name, count]) => total + (options.matches(name) ? count : 0),
      0,
    );
  const before = held();
  const failed = new Set<string>();
  let harvested = 0;
  // Digging that produces nothing, twice running, is not going to start
  // producing: stop rather than strip everything in range for no gain.
  let fruitless = 0;

  while (held() - before < options.target && fruitless < FRUITLESS_LIMIT) {
    context.checkpoint();
    const candidates = permittedResources(
      context,
      options.kinds,
      options.maxDistance,
    ).filter(
      (block) =>
        !failed.has(
          `${block.position.x},${block.position.y},${block.position.z}`,
        ),
    );
    if (candidates.length === 0) break;
    const block = candidates[0];
    if (!block) break;
    const key = `${block.position.x},${block.position.y},${block.position.z}`;
    try {
      await approach(context, block.position);
      context.checkpoint();
      const verdict = context.permissions.mayHarvest(block.position);
      if (!verdict.allowed)
        throw new SkillFailure(
          "protected_area",
          "INVALIDATED",
          `Harvest denied: ${verdict.reason}`,
        );
      const holding = held();
      const drops = await context.embodiment.dig(block.position);
      harvested += 1;
      fruitless = held() > holding ? 0 : fruitless + 1;
      context.note("harvested_blocks", {
        block: block.name,
        drops: drops.length,
      });
    } catch (error) {
      if (error instanceof SkillFailure && error.status === "INVALIDATED")
        throw error;
      failed.add(key);
    }
  }

  const gained = held() - before;
  if (gained <= 0) {
    if (harvested > 0)
      throw context.snapshot().freeSlots === 0
        ? new SkillFailure(
            "inventory_full",
            "FAILED",
            "Harvested blocks produced no items",
          )
        : new SkillFailure(
            "no_yield",
            "FAILED",
            "Harvested blocks yielded nothing",
          );
    throw new SkillFailure(
      "unreachable_resource",
      "UNREACHABLE",
      "No permitted resource of this kind could be reached",
    );
  }
  context.effect(options.effect);
  context.note("inventory_delta", { gained, blocks: harvested });
}

export const gatherWood: SkillImplementation = (context) =>
  harvest(context, {
    kinds: ["wood"],
    matches: isLog,
    target: context.number("target_amount"),
    maxDistance: context.number("max_distance"),
    effect: "wood_increased",
  });

export const gatherPlantFood: SkillImplementation = (context) =>
  harvest(context, {
    kinds: ["plant_food", "leaves"],
    matches: isPlantFood,
    target: context.number("target_amount"),
    maxDistance: context.number("max_distance"),
    effect: "plant_food_increased",
  });

export const mineStone: SkillImplementation = (context) => {
  if (toolTier(context.snapshot().inventory) < 1)
    throw new SkillFailure(
      "missing_tool",
      "INVALIDATED",
      "Mining stone requires a pickaxe",
    );
  return harvest(context, {
    kinds: ["stone"],
    matches: isStone,
    target: context.number("target_amount"),
    maxDistance: context.number("max_distance"),
    effect: "stone_increased",
  });
};

export const mineCoal: SkillImplementation = (context) => {
  if (toolTier(context.snapshot().inventory) < 1)
    throw new SkillFailure(
      "missing_tool",
      "INVALIDATED",
      "Mining coal requires a pickaxe",
    );
  return harvest(context, {
    kinds: ["coal_ore"],
    matches: isCoal,
    target: context.number("target_amount"),
    maxDistance: context.number("max_distance"),
    effect: "coal_increased",
  });
};

export const resourceSkills: Record<string, SkillImplementation> = {
  gather_wood: gatherWood,
  gather_plant_food: gatherPlantFood,
  mine_stone: mineStone,
  mine_coal: mineCoal,
};
