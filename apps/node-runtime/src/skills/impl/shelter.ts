import { distance, type Position } from "#config";
import {
  SkillFailure,
  type SkillContext,
  type SkillImplementation,
} from "../execution.ts";
import { isBuildingMaterial } from "../materials.ts";
import { travelTo } from "../navigate.ts";
import { shelterEntrance, shelterPlan } from "../shelter-plan.ts";

const buildingItem = (context: SkillContext): string | null =>
  context.snapshot().inventory.find((item) => isBuildingMaterial(item.name))
    ?.name ?? null;

/** Blocks of the shelter plan that are not yet solid. */
function missingBlocks(context: SkillContext, home: Position): Position[] {
  return shelterPlan(home).filter((position) => {
    const block = context.embodiment.blockAt(position);
    return !block || !block.solid;
  });
}

export function shelterSealed(context: SkillContext, home: Position): boolean {
  if (missingBlocks(context, home).length > 0) return false;
  const floor = context.embodiment.blockAt({ ...home, y: home.y - 1 });
  if (!floor?.solid) return false;
  return [0, 1].every((dy) => {
    const inside = context.embodiment.blockAt({ ...home, y: home.y + dy });
    return inside !== null && !inside.solid;
  });
}

async function placeShelterBlocks(
  context: SkillContext,
  home: Position,
): Promise<number> {
  let placed = 0;
  for (const position of shelterPlan(home)) {
    context.checkpoint();
    const block = context.embodiment.blockAt(position);
    if (block?.solid) continue;
    const verdict = context.permissions.mayBuild(position);
    if (!verdict.allowed)
      throw new SkillFailure(
        verdict.reason === "protected_area"
          ? "protected_area"
          : "obstructed_site",
        "INVALIDATED",
        `Building denied at ${position.x},${position.y},${position.z}: ${verdict.reason}`,
      );
    const material = buildingItem(context);
    if (!material)
      throw new SkillFailure(
        "missing_materials",
        "FAILED",
        "Ran out of shelter material",
      );
    await context.embodiment.place(position, material);
    context.memory.recordPlacement(position);
    placed += 1;
  }
  return placed;
}

/** Build and seal a small shelter at the active home position. */
export const buildBasicShelter: SkillImplementation = async (context) => {
  const home = context.home();
  const needed = missingBlocks(context, home).length;
  const available = context
    .snapshot()
    .inventory.filter((item) => isBuildingMaterial(item.name))
    .reduce((total, item) => total + item.count, 0);
  if (available < needed)
    throw new SkillFailure(
      "missing_materials",
      "INVALIDATED",
      `Shelter needs ${needed} blocks and ${available} are held`,
    );
  const floor = context.embodiment.blockAt({ ...home, y: home.y - 1 });
  if (!floor?.solid)
    throw new SkillFailure(
      "obstructed_site",
      "FAILED",
      "Home has no solid floor to build on",
    );

  if (distance(context.snapshot().position, home) > 3)
    await travelTo(context, home, 1);
  const placed = await placeShelterBlocks(context, home);
  if (!shelterSealed(context, home))
    throw new SkillFailure(
      "obstructed_site",
      "FAILED",
      "Shelter enclosure verification failed",
    );
  context.memory.home = { ...context.memory.home, shelterState: "complete" };
  context.effect("shelter_complete");
  context.note("placed_blocks", { placed });
  context.note("shelter_verified", {
    sealed: true,
    entrance: shelterEntrance(home).length,
  });
};

/** Replace missing blocks in an existing owned shelter until it is sealed. */
export const repairShelter: SkillImplementation = async (context) => {
  const home = context.home();
  const missing = missingBlocks(context, home);
  if (missing.length === 0) {
    context.memory.home = { ...context.memory.home, shelterState: "complete" };
    context.effect("shelter_intact");
    context.note("shelter_verified", { sealed: true, repaired: 0 });
    return;
  }
  const available = context
    .snapshot()
    .inventory.filter((item) => isBuildingMaterial(item.name))
    .reduce((total, item) => total + item.count, 0);
  if (available < missing.length)
    throw new SkillFailure(
      "missing_materials",
      "INVALIDATED",
      `Repair needs ${missing.length} blocks and ${available} are held`,
    );
  if (distance(context.snapshot().position, home) > 3)
    await travelTo(context, home, 1);
  const placed = await placeShelterBlocks(context, home);
  if (!shelterSealed(context, home))
    throw new SkillFailure(
      "obstructed_site",
      "FAILED",
      "Shelter is still not sealed after repair",
    );
  context.memory.home = { ...context.memory.home, shelterState: "complete" };
  context.effect("shelter_complete");
  context.note("placed_blocks", { placed });
  context.note("shelter_verified", { sealed: true, repaired: placed });
};

export const shelterSkills: Record<string, SkillImplementation> = {
  build_basic_shelter: buildBasicShelter,
  repair_shelter: repairShelter,
};
