import type { BlockKind } from "#node-runtime";

/** Maps Minecraft 1.16.1 block names onto the semantic kinds skills reason over. */
export function blockKind(name: string): BlockKind {
  if (name === "air" || name === "cave_air" || name === "void_air")
    return "air";
  if (name.endsWith("_log") || name.endsWith("_wood")) return "wood";
  if (name.endsWith("_leaves")) return "leaves";
  if (name === "sweet_berry_bush") return "plant_food";
  if (name === "coal_ore") return "coal_ore";
  if (
    name === "stone" ||
    name === "andesite" ||
    name === "diorite" ||
    name === "granite"
  )
    return "stone";
  if (name === "cobblestone") return "cobblestone";
  if (name.endsWith("_planks")) return "planks";
  if (name === "dirt" || name === "coarse_dirt") return "dirt";
  if (name === "grass_block") return "grass";
  if (name === "water") return "water";
  if (name === "lava") return "lava";
  if (name === "fire" || name === "soul_fire") return "fire";
  if (name === "cactus") return "cactus";
  if (name === "chest" || name === "trapped_chest" || name === "barrel")
    return "chest";
  if (name === "furnace" || name === "blast_furnace" || name === "smoker")
    return "furnace";
  if (name === "crafting_table") return "crafting_table";
  if (name.endsWith("_bed")) return "bed";
  return "other";
}

export const HAZARD_BLOCKS = new Set([
  "lava",
  "fire",
  "soul_fire",
  "cactus",
  "magma_block",
  "campfire",
  "soul_campfire",
  "water",
]);

export const HOSTILE_MOBS = new Set([
  "zombie",
  "husk",
  "drowned",
  "zombie_villager",
  "skeleton",
  "stray",
  "creeper",
  "spider",
  "cave_spider",
  "witch",
  "pillager",
  "vindicator",
  "evoker",
  "ravager",
  "phantom",
  "slime",
  "enderman",
  "silverfish",
  "zombified_piglin",
]);

export const RANGED_MOBS = new Set(["skeleton", "stray", "pillager", "witch"]);

export const PASSIVE_MOBS = new Set([
  "cow",
  "pig",
  "sheep",
  "chicken",
  "rabbit",
  "mooshroom",
  "turtle",
  "cod",
  "salmon",
]);

export const TAMEABLE_MOBS = new Set([
  "wolf",
  "cat",
  "ocelot",
  "parrot",
  "horse",
  "llama",
]);

/** Fuel burn value in smelting operations for the fuels Person uses. */
export const FUEL_BURN: Readonly<Record<string, number>> = Object.freeze({
  coal: 8,
  charcoal: 8,
  stick: 0.5,
});
