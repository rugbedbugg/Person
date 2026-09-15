/**
 * Entity and block classification against authoritative Minecraft data.
 *
 * Two rules govern everything here, and they point in opposite directions on
 * purpose:
 *
 * - What Person may *attack* comes from a short explicit allowlist. Widening it
 *   by accident must be impossible, so no data source can add to it.
 * - What Person must *flee from* is deliberately over-inclusive. A mob the
 *   runtime fails to recognise as dangerous is a safety failure, so anything
 *   the registry calls hostile counts, plus a list of mobs the 1.16.1 registry
 *   files under "UNKNOWN" that are perfectly capable of killing you.
 */

/** Mobs Person may take food from: unnamed, untamed, and food-bearing. */
export const HUNTABLE_FOOD_ANIMALS: ReadonlySet<string> = new Set([
  "cow",
  "pig",
  "sheep",
  "chicken",
  "rabbit",
  "mooshroom",
  "cod",
  "salmon",
]);

/** Species that can be tamed. Treated as owned whether or not they are. */
export const TAMEABLE_MOBS: ReadonlySet<string> = new Set([
  "wolf",
  "cat",
  "ocelot",
  "parrot",
  "horse",
  "donkey",
  "mule",
  "llama",
  "trader_llama",
  "skeleton_horse",
  "zombie_horse",
]);

export const VILLAGER_MOBS: ReadonlySet<string> = new Set([
  "villager",
  "wandering_trader",
  "zombie_villager",
  "iron_golem",
  "snow_golem",
]);

/**
 * Hostile on sight, but not categorised as hostile by the 1.16.1 registry.
 *
 * Checked against `minecraft-data`: hoglin and zoglin land in the "UNKNOWN"
 * category and attack without provocation.
 */
export const EXTRA_HOSTILE_MOBS: ReadonlySet<string> = new Set([
  "hoglin",
  "zoglin",
  "piglin_brute",
]);

/**
 * Mobs that are harmless until provoked, and lethal afterwards.
 *
 * Treating these as hostile on sight would leave Person fleeing from a llama
 * for the rest of its life; ignoring them entirely would leave it standing
 * still while a wolf pack kills it. They count as a threat only once Person
 * has actually taken damage, which is the signal the world gives for free.
 */
export const NEUTRAL_MOBS: ReadonlySet<string> = new Set([
  "wolf",
  "polar_bear",
  "llama",
  "trader_llama",
  "panda",
  "dolphin",
  "bee",
  "piglin",
  "zombified_piglin",
  "iron_golem",
]);

/** Mobs whose projectiles reach much further than their bodies. */
export const RANGED_MOBS: ReadonlySet<string> = new Set([
  "skeleton",
  "stray",
  "pillager",
  "witch",
  "blaze",
  "ghast",
  "shulker",
  "drowned",
  "wither_skeleton",
]);

export const HOSTILE_CATEGORY = "Hostile mobs";
export const PASSIVE_CATEGORY = "Passive mobs";

export interface EntityFacts {
  name: string;
  player: boolean;
  villager: boolean;
  hostile: boolean;
  /** Harmless until provoked. A threat only once Person has taken damage. */
  neutral: boolean;
  /** True only for species on the food allowlist. Not "not hostile". */
  huntableSpecies: boolean;
  tameable: boolean;
  ranged: boolean;
}

/**
 * Classifies one entity.
 *
 * `category` is the `minecraft-data` entity category the client reports as
 * `entity.kind`. It widens hostility detection and nothing else.
 */
export function classifyEntity(
  name: string,
  type: string | undefined,
  category: string | undefined,
): EntityFacts {
  const player = type === "player";
  const villager = !player && VILLAGER_MOBS.has(name);
  const tameable = TAMEABLE_MOBS.has(name);
  const hostile =
    !player &&
    !villager &&
    (category === HOSTILE_CATEGORY || EXTRA_HOSTILE_MOBS.has(name));
  return {
    name: player ? "player" : name,
    player,
    villager,
    hostile,
    neutral: !player && !hostile && NEUTRAL_MOBS.has(name),
    huntableSpecies:
      !player && !villager && !tameable && HUNTABLE_FOOD_ANIMALS.has(name),
    tameable,
    ranged: RANGED_MOBS.has(name),
  };
}

/**
 * Extracts a custom name from entity metadata.
 *
 * Mineflayer parses metadata into a sparse object keyed by index, not an
 * array. In 1.16.1 index 2 carries the optional custom name, which arrives as
 * a string, a chat component, or nothing at all. An unrecognised shape is
 * treated as named, because the cost of being wrong in that direction is a
 * missed meal and the cost of being wrong in the other is killing something
 * that belonged to somebody.
 */
export function customName(metadata: unknown): string | null {
  if (metadata === null || metadata === undefined) return null;
  if (typeof metadata !== "object") return null;
  const value = (metadata as Record<string, unknown>)["2"];
  if (value === null || value === undefined) return null;
  if (typeof value === "string") return value.trim() === "" ? null : value;
  if (typeof value === "object") {
    const component = value as {
      text?: unknown;
      extra?: unknown;
      toString?: () => string;
    };
    if (typeof component.text === "string" && component.text.trim() !== "")
      return component.text;
    if (Array.isArray(component.extra) && component.extra.length > 0)
      return "custom";
    // A chat component of an unexpected shape still means somebody named it.
    return "custom";
  }
  return "custom";
}

export const isNamed = (metadata: unknown): boolean =>
  customName(metadata) !== null;
