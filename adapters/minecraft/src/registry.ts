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

/**
 * Armour points per piece in 1.16.1.
 *
 * Mineflayer does not expose a total, so it is computed from the equipped
 * slots. Leaving it at zero would tell the safety kernel that Person is
 * unarmoured no matter what it is wearing.
 */
export const ARMOR_POINTS: Readonly<Record<string, number>> = Object.freeze({
  leather_helmet: 1,
  leather_chestplate: 3,
  leather_leggings: 2,
  leather_boots: 1,
  golden_helmet: 2,
  golden_chestplate: 5,
  golden_leggings: 3,
  golden_boots: 1,
  chainmail_helmet: 2,
  chainmail_chestplate: 5,
  chainmail_leggings: 4,
  chainmail_boots: 1,
  iron_helmet: 2,
  iron_chestplate: 6,
  iron_leggings: 5,
  iron_boots: 2,
  diamond_helmet: 3,
  diamond_chestplate: 8,
  diamond_leggings: 6,
  diamond_boots: 3,
  netherite_helmet: 3,
  netherite_chestplate: 8,
  netherite_leggings: 6,
  netherite_boots: 3,
  turtle_helmet: 2,
});

/** Player inventory window slots that hold armour, head to feet. */
export const ARMOR_SLOTS = [5, 6, 7, 8] as const;

/** Fuel burn value in smelting operations for the fuels Person uses. */
export const FUEL_BURN: Readonly<Record<string, number>> = Object.freeze({
  coal: 8,
  charcoal: 8,
  stick: 0.5,
});
