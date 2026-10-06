import type { BlockKind } from "#node-runtime";

export interface BlockDefinition {
  kind: BlockKind;
  solid: boolean;
  hazard: boolean;
  drops: { name: string; count: number }[];
  /** Minimum pickaxe tier needed to get a drop. */
  tool: number;
}

const block = (
  kind: BlockKind,
  options: Partial<BlockDefinition> = {},
): BlockDefinition => ({
  kind,
  solid: options.solid ?? true,
  hazard: options.hazard ?? false,
  drops: options.drops ?? [],
  tool: options.tool ?? 0,
});

/**
 * A small, explicit block table.
 *
 * The fixture deliberately does not depend on minecraft-data: the point is a
 * world whose every rule is visible in one file, so a test failure means the
 * skill is wrong rather than the simulation being subtly different today.
 */
export const BLOCKS: Readonly<Record<string, BlockDefinition>> = Object.freeze({
  air: block("air", { solid: false }),
  dirt: block("dirt", { drops: [{ name: "dirt", count: 1 }] }),
  grass_block: block("grass", { drops: [{ name: "dirt", count: 1 }] }),
  stone: block("stone", {
    drops: [{ name: "cobblestone", count: 1 }],
    tool: 1,
  }),
  cobblestone: block("cobblestone", {
    drops: [{ name: "cobblestone", count: 1 }],
    tool: 1,
  }),
  coal_ore: block("coal_ore", { drops: [{ name: "coal", count: 1 }], tool: 1 }),
  oak_log: block("wood", { drops: [{ name: "oak_log", count: 1 }] }),
  birch_log: block("wood", { drops: [{ name: "birch_log", count: 1 }] }),
  oak_leaves: block("leaves", { drops: [{ name: "apple", count: 1 }] }),
  sweet_berry_bush: block("plant_food", {
    solid: false,
    drops: [{ name: "sweet_berries", count: 2 }],
  }),
  oak_planks: block("planks", { drops: [{ name: "oak_planks", count: 1 }] }),
  birch_planks: block("planks", {
    drops: [{ name: "birch_planks", count: 1 }],
  }),
  crafting_table: block("crafting_table", {
    drops: [{ name: "crafting_table", count: 1 }],
  }),
  furnace: block("furnace", { drops: [{ name: "furnace", count: 1 }] }),
  chest: block("chest", { drops: [{ name: "chest", count: 1 }] }),
  water: block("water", { solid: false, hazard: true }),
  lava: block("lava", { solid: false, hazard: true }),
  fire: block("fire", { solid: false, hazard: true }),
  cactus: block("cactus", { hazard: true }),
});

export const definitionOf = (name: string): BlockDefinition =>
  BLOCKS[name] ?? BLOCKS["air"]!;

export const HOSTILES = new Set([
  "zombie",
  "skeleton",
  "creeper",
  "spider",
  "husk",
  "stray",
]);
export const RANGED_HOSTILES = new Set(["skeleton", "stray"]);
/** Mobs that only become dangerous once Person has taken damage. */
export const NEUTRALS = new Set([
  "wolf",
  "polar_bear",
  "llama",
  "panda",
  "bee",
  "iron_golem",
]);

export const PASSIVE_ANIMALS: Readonly<
  Record<string, { drop: string; health: number }>
> = Object.freeze({
  cow: { drop: "beef", health: 10 },
  pig: { drop: "porkchop", health: 10 },
  chicken: { drop: "chicken", health: 4 },
  sheep: { drop: "mutton", health: 8 },
});
