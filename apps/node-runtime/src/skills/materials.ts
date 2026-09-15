import type { ItemStack } from "#protocol";

export const LOGS = [
  "oak_log",
  "birch_log",
  "spruce_log",
  "jungle_log",
  "acacia_log",
  "dark_oak_log",
] as const;

export const PLANT_FOOD = ["apple", "sweet_berries", "carrot"] as const;
export const RAW_FOOD = [
  "beef",
  "porkchop",
  "chicken",
  "mutton",
  "rabbit",
  "cod",
  "salmon",
  "potato",
] as const;
export const COOKED_FOOD = [
  "cooked_beef",
  "cooked_porkchop",
  "cooked_chicken",
  "cooked_mutton",
  "cooked_rabbit",
  "cooked_cod",
  "cooked_salmon",
  "baked_potato",
  "bread",
] as const;

export const SMELTING: Readonly<Record<string, string>> = Object.freeze({
  beef: "cooked_beef",
  porkchop: "cooked_porkchop",
  chicken: "cooked_chicken",
  mutton: "cooked_mutton",
  rabbit: "cooked_rabbit",
  cod: "cooked_cod",
  salmon: "cooked_salmon",
  potato: "baked_potato",
});

/** Food value in hunger points, used to decide how much to eat. */
export const FOOD_VALUE: Readonly<Record<string, number>> = Object.freeze({
  apple: 4,
  sweet_berries: 2,
  carrot: 3,
  bread: 5,
  cooked_beef: 8,
  cooked_porkchop: 8,
  cooked_chicken: 6,
  cooked_mutton: 6,
  cooked_rabbit: 5,
  cooked_cod: 5,
  cooked_salmon: 6,
  baked_potato: 5,
});

/** Fuel units one item provides when smelting. */
export const FUEL_VALUE: Readonly<Record<string, number>> = Object.freeze({
  coal: 8,
  charcoal: 8,
  stick: 1,
});

const suffix = (name: string, ending: string): boolean => name.endsWith(ending);

export const isLog = (name: string): boolean =>
  (LOGS as readonly string[]).includes(name);
export const isPlanks = (name: string): boolean => suffix(name, "_planks");
export const isStone = (name: string): boolean =>
  name === "stone" || name === "cobblestone";
export const isCoal = (name: string): boolean =>
  name === "coal" || name === "charcoal";
export const isPlantFood = (name: string): boolean =>
  (PLANT_FOOD as readonly string[]).includes(name);
export const isRawFood = (name: string): boolean =>
  (RAW_FOOD as readonly string[]).includes(name);
export const isCookedFood = (name: string): boolean =>
  (COOKED_FOOD as readonly string[]).includes(name);
export const isEdible = (name: string): boolean =>
  isPlantFood(name) || isCookedFood(name);
export const isFuel = (name: string): boolean =>
  name in FUEL_VALUE || isLog(name) || isPlanks(name);
export const isTool = (name: string): boolean =>
  suffix(name, "_pickaxe") ||
  suffix(name, "_axe") ||
  suffix(name, "_shovel") ||
  suffix(name, "_hoe");
export const isWeapon = (name: string): boolean => suffix(name, "_sword");
export const isArmor = (name: string): boolean =>
  suffix(name, "_helmet") ||
  suffix(name, "_chestplate") ||
  suffix(name, "_leggings") ||
  suffix(name, "_boots");
export const isBuildingMaterial = (name: string): boolean =>
  isPlanks(name) ||
  isLog(name) ||
  name === "cobblestone" ||
  name === "dirt" ||
  name === "stone";

export const TOOL_TIERS: Readonly<Record<string, number>> = Object.freeze({
  wooden: 1,
  stone: 2,
  iron: 3,
  diamond: 4,
});

export function toolTier(inventory: readonly ItemStack[]): number {
  let tier = 0;
  for (const item of inventory) {
    if (!item.name.endsWith("_pickaxe")) continue;
    const prefix = item.name.replace("_pickaxe", "");
    tier = Math.max(tier, TOOL_TIERS[prefix] ?? 0);
  }
  return tier;
}

export function tally(inventory: readonly ItemStack[]): Map<string, number> {
  const totals = new Map<string, number>();
  for (const item of inventory)
    totals.set(item.name, (totals.get(item.name) ?? 0) + item.count);
  return totals;
}

export function categories(
  inventory: readonly ItemStack[],
): Record<string, number> {
  const sum = (predicate: (name: string) => boolean): number =>
    inventory
      .filter((i) => predicate(i.name))
      .reduce((total, i) => total + i.count, 0);
  return {
    food: sum(isEdible),
    raw_food: sum(isRawFood),
    cooked_food: sum(isCookedFood),
    fuel: sum(isFuel),
    wood: sum(isLog),
    stone: sum(isStone),
    coal: sum(isCoal),
    tools: sum(isTool),
    weapons: sum(isWeapon),
    armor: sum(isArmor),
    building_materials: sum(isBuildingMaterial),
  };
}

export function inventoryDelta(
  before: readonly ItemStack[],
  after: readonly ItemStack[],
): { name: string; delta: number }[] {
  const start = tally(before);
  const end = tally(after);
  const names = new Set([...start.keys(), ...end.keys()]);
  return [...names]
    .map((name) => ({
      name,
      delta: (end.get(name) ?? 0) - (start.get(name) ?? 0),
    }))
    .filter((entry) => entry.delta !== 0)
    .sort((a, b) => a.name.localeCompare(b.name));
}
