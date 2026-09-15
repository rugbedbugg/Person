import { distance, type Position } from "#config";
import {
  SkillFailure,
  itemCount,
  type SkillContext,
  type SkillImplementation,
} from "../execution.ts";
import { isStone } from "../materials.ts";
import { RecipeError, planCraft, preferredWood } from "../recipes.ts";
import { approach } from "../navigate.ts";

/** A permitted, clear, solid-floored block to put a workstation on. */
function placementSite(
  context: SkillContext,
  near: Position,
  radius = 3,
): Position | null {
  const home = context.home();
  const candidates: Position[] = [];
  for (let dx = -radius; dx <= radius; dx++)
    for (let dz = -radius; dz <= radius; dz++) {
      if (dx === 0 && dz === 0) continue;
      const site: Position = { x: near.x + dx, y: near.y, z: near.z + dz };
      // Never build inside the shelter footprint or across its doorway.
      if (Math.abs(site.x - home.x) <= 1 && Math.abs(site.z - home.z) <= 1)
        continue;
      if (site.x === home.x && site.z === home.z - 2) continue;
      if (!context.permissions.mayBuild(site).allowed) continue;
      const block = context.embodiment.blockAt(site);
      const floor = context.embodiment.blockAt({ ...site, y: site.y - 1 });
      const above = context.embodiment.blockAt({ ...site, y: site.y + 1 });
      if (!block || !floor || !above) continue;
      if (
        block.solid ||
        block.hazard ||
        above.solid ||
        !floor.solid ||
        floor.hazard
      )
        continue;
      candidates.push(site);
    }
  candidates.sort((a, b) => distance(near, a) - distance(near, b));
  return candidates[0] ?? null;
}

/** Ensures an owned crafting table exists and returns its position. */
async function ensureCraftingTable(context: SkillContext): Promise<Position> {
  const remembered = context.memory.craftingTablePosition;
  if (remembered) {
    const block = context.embodiment.blockAt(remembered);
    if (block?.kind === "crafting_table" && block.ownedByPerson) {
      await approach(context, remembered);
      return remembered;
    }
    context.memory.craftingTablePosition = null;
  }
  if (itemCount(context.snapshot().inventory, "crafting_table") === 0) {
    const steps = planCraft("crafting_table", 1, context.snapshot().inventory);
    for (const step of steps) {
      context.checkpoint();
      await context.embodiment.craft(step.item, step.times, null);
    }
  }
  if (itemCount(context.snapshot().inventory, "crafting_table") === 0)
    throw new SkillFailure(
      "missing_materials",
      "FAILED",
      "Could not craft a crafting table",
    );
  const site = placementSite(context, context.snapshot().position);
  if (!site)
    throw new SkillFailure(
      "no_placement_site",
      "FAILED",
      "No permitted crafting table site",
    );
  await context.embodiment.place(site, "crafting_table");
  context.memory.recordPlacement(site);
  context.memory.craftingTablePosition = site;
  context.note("placed_blocks", {
    crafting_table: `${site.x},${site.y},${site.z}`,
  });
  await approach(context, site);
  return site;
}

async function craftAll(
  context: SkillContext,
  requests: [string, number][],
): Promise<number> {
  let crafted = 0;
  for (const [item, quantity] of requests) {
    context.checkpoint();
    let steps;
    try {
      steps = planCraft(item, quantity, context.snapshot().inventory);
    } catch (error) {
      if (error instanceof RecipeError)
        throw new SkillFailure(
          "missing_materials",
          "INVALIDATED",
          error.message,
        );
      throw error;
    }
    const needsTable = steps.some((step) => step.requiresTable);
    const table = needsTable ? await ensureCraftingTable(context) : null;
    for (const step of steps) {
      context.checkpoint();
      const result = await context.embodiment.craft(
        step.item,
        step.times,
        step.requiresTable ? table : null,
      );
      crafted += result.produced.reduce(
        (total, produced) => total + produced.count,
        0,
      );
      context.note("crafted_items", { item: step.item, times: step.times });
    }
  }
  return crafted;
}

export const craftBasicTools: SkillImplementation = async (context) => {
  const crafted = await craftAll(context, [
    ["wooden_pickaxe", 1],
    ["wooden_axe", 1],
  ]);
  context.effect("tool_tier_raised");
  context.note("inventory_delta", { crafted });
};

export const craftStoneTools: SkillImplementation = async (context) => {
  const inventory = context.snapshot().inventory;
  const stone = inventory
    .filter((item) => isStone(item.name))
    .reduce((n, i) => n + i.count, 0);
  if (stone < 6)
    throw new SkillFailure(
      "missing_materials",
      "INVALIDATED",
      "Stone tools need six cobblestone",
    );
  const crafted = await craftAll(context, [
    ["stone_pickaxe", 1],
    ["stone_axe", 1],
  ]);
  context.effect("tool_tier_raised");
  context.note("inventory_delta", { crafted });
};

export const craftFurnace: SkillImplementation = async (context) => {
  await craftAll(context, [["furnace", 1]]);
  const home = context.home();
  const site = placementSite(context, home, 3);
  if (!site)
    throw new SkillFailure(
      "no_placement_site",
      "FAILED",
      "No permitted furnace site",
    );
  await approach(context, site);
  context.checkpoint();
  const verdict = context.permissions.mayBuild(site);
  if (!verdict.allowed)
    throw new SkillFailure(
      "protected_area",
      "INVALIDATED",
      `Furnace placement denied: ${verdict.reason}`,
    );
  await context.embodiment.place(site, "furnace");
  context.memory.recordPlacement(site);
  context.memory.furnacePosition = site;
  context.effect("furnace_placed");
  context.note("placed_blocks", { furnace: `${site.x},${site.y},${site.z}` });
};

export const craftChest: SkillImplementation = async (context) => {
  const crafted = await craftAll(context, [["chest", 1]]);
  context.effect("chest_crafted");
  context.note("crafted_items", { item: "chest", times: 1 });
  context.note("inventory_delta", { crafted });
};

export const craftingSkills: Record<string, SkillImplementation> = {
  craft_basic_tools: craftBasicTools,
  craft_stone_tools: craftStoneTools,
  craft_furnace: craftFurnace,
  craft_chest: craftChest,
};

export { ensureCraftingTable, placementSite, preferredWood };
