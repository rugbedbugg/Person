import type { ItemStack } from "#protocol";
import { LOGS, isPlanks, tally } from "./materials.ts";

export interface Recipe {
  item: string;
  output: number;
  inputs: Record<string, number>;
  requiresTable: boolean;
}

export interface CraftStep {
  item: string;
  times: number;
  output: number;
  requiresTable: boolean;
}

/**
 * A small auditable dependency graph for the recipes Person needs.
 *
 * Against Minecraft the adapter still resolves the real recipe from the server
 * registry; this table exists so the planner and the deterministic fixture
 * agree on what a craft consumes and produces.
 */
export function recipesFor(woodPrefix: string): Record<string, Recipe> {
  const planks = `${woodPrefix}_planks`;
  const table = (
    item: string,
    output: number,
    inputs: Record<string, number>,
    requiresTable: boolean,
  ): Recipe => ({
    item,
    output,
    inputs,
    requiresTable,
  });
  return {
    [planks]: table(planks, 4, { [`${woodPrefix}_log`]: 1 }, false),
    stick: table("stick", 4, { [planks]: 2 }, false),
    crafting_table: table("crafting_table", 1, { [planks]: 4 }, false),
    wooden_pickaxe: table("wooden_pickaxe", 1, { [planks]: 3, stick: 2 }, true),
    wooden_axe: table("wooden_axe", 1, { [planks]: 3, stick: 2 }, true),
    stone_pickaxe: table(
      "stone_pickaxe",
      1,
      { cobblestone: 3, stick: 2 },
      true,
    ),
    stone_axe: table("stone_axe", 1, { cobblestone: 3, stick: 2 }, true),
    furnace: table("furnace", 1, { cobblestone: 8 }, true),
    chest: table("chest", 1, { [planks]: 8 }, true),
  };
}

export class RecipeError extends Error {
  readonly missing: string;
  constructor(missing: string) {
    super(`Missing self-gathered resource: ${missing}`);
    this.name = "RecipeError";
    this.missing = missing;
  }
}

/** The wood type Person has most of, so plank recipes stay consistent. */
export function preferredWood(inventory: readonly ItemStack[]): string {
  const totals = tally(inventory);
  const ranked = LOGS.map((log) => ({
    prefix: log.replace("_log", ""),
    available:
      (totals.get(log) ?? 0) * 4 +
      (totals.get(log.replace("_log", "_planks")) ?? 0),
  })).sort((a, b) => b.available - a.available);
  return ranked[0]?.prefix ?? "oak";
}

/**
 * Expands a craft request into ordered steps, materialising intermediate
 * ingredients from what is actually held. Throws naming the first material
 * Person has not gathered yet, which is what the planner needs to hear.
 */
export function planCraft(
  item: string,
  quantity: number,
  inventory: readonly ItemStack[],
): CraftStep[] {
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > 64)
    throw new RecipeError("valid quantity");
  const prefix = preferredWood(inventory);
  const recipes = recipesFor(prefix);
  const stock = tally(inventory);
  // Any plank variety is interchangeable for crafting purposes; normalise to
  // the preferred one so a mixed inventory still satisfies a recipe.
  const planks = `${prefix}_planks`;
  for (const [name, count] of [...stock])
    if (isPlanks(name) && name !== planks) {
      stock.set(planks, (stock.get(planks) ?? 0) + count);
      stock.delete(name);
    }
  const steps: CraftStep[] = [];
  const target = item === "planks" ? planks : item;

  const ensure = (name: string, amount: number, depth: number): void => {
    if (depth > 8) throw new RecipeError(name);
    const missing = amount - (stock.get(name) ?? 0);
    if (missing <= 0) return;
    const recipe = recipes[name];
    if (!recipe) throw new RecipeError(name);
    if (recipe.requiresTable) ensure("crafting_table", 1, depth + 1);
    const times = Math.ceil(missing / recipe.output);
    for (const [ingredient, per] of Object.entries(recipe.inputs)) {
      ensure(ingredient, per * times, depth + 1);
      stock.set(ingredient, (stock.get(ingredient) ?? 0) - per * times);
    }
    stock.set(name, (stock.get(name) ?? 0) + recipe.output * times);
    steps.push({
      item: name,
      times,
      output: times * recipe.output,
      requiresTable: recipe.requiresTable,
    });
  };

  ensure(target, quantity, 0);
  return steps;
}
