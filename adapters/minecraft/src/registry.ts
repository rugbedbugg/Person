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

/**
 * The shape of a `prismarine-biome` biome as it arrives on a block.
 *
 * The id is always right. The name is not: see `resolveBiome`.
 */
export interface BiomeHandle {
  id?: unknown;
  name?: unknown;
}

/** Enough of `bot.registry` to resolve a biome id. */
export interface BiomeRegistry {
  biomes?: Record<number, { name?: unknown } | undefined> | undefined;
}

const IDENTIFIER = /^[a-z][a-z0-9_]{0,63}$/;

const biomeIdentifier = (value: unknown): string | null => {
  if (typeof value !== "string") return null;
  const name = value.replace(/^minecraft:/, "");
  return IDENTIFIER.test(name) ? name : null;
};

/**
 * Resolves the biome at a block against the client's own biome registry.
 *
 * `block.biome.name` cannot be used, and the first live observation is how we
 * found out: it reported `biome: "unknown"` in an ordinary loaded Overworld
 * chunk. The cause is upstream and unconditional. `prismarine-block` builds
 * its Biome class with `require('prismarine-biome')(registry.version)`, where
 * `registry.version` is a Version object rather than a version string;
 * `prismarine-biome` only treats a *string* as a version, so it takes the
 * Version object for a registry, finds no `biomes` table on it, and returns
 * its empty placeholder for every id. Every block therefore carries a biome
 * whose name is the empty string and whose id is correct.
 *
 * So the id is what gets resolved, against the registry the client is actually
 * running: `minecraft-data`'s table on 1.16.1, and whatever the server's
 * dimension codec supplied on the versions that send one. No name is guessed,
 * no biome is inferred from terrain, and a block whose chunk has not arrived
 * still resolves to "unknown" because that is the honest answer.
 */
export function resolveBiome(
  registry: BiomeRegistry | null | undefined,
  block: { biome?: BiomeHandle | null } | null | undefined,
): string {
  if (!block) return "unknown";
  const direct = biomeIdentifier(block.biome?.name);
  if (direct) return direct;
  const id = block.biome?.id;
  if (typeof id !== "number" || !Number.isInteger(id)) return "unknown";
  return biomeIdentifier(registry?.biomes?.[id]?.name) ?? "unknown";
}
