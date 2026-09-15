import { distance, type Position } from "#config";
import { type SkillContext } from "./execution.ts";
import { isBuildingMaterial } from "./materials.ts";
import { shelterEntrance, shelterPlan } from "./shelter-plan.ts";

/** A sealed shelter Person built is a room, and a room needs a door. */
export function shelterIsSealed(
  context: SkillContext,
  home: Position,
): boolean {
  return shelterPlan(home).every(
    (position) => context.embodiment.blockAt(position)?.solid === true,
  );
}

export function insideShelter(context: SkillContext, home: Position): boolean {
  return (
    distance(context.snapshot().position, home) <= 1.5 &&
    shelterIsSealed(context, home)
  );
}

const buildingItem = (context: SkillContext): string | null =>
  context.snapshot().inventory.find((item) => isBuildingMaterial(item.name))
    ?.name ?? null;

/**
 * Opens the doorway of an owned shelter.
 *
 * Only blocks Person placed itself may be removed, so this can never be used
 * to break into something else that happens to be in the way.
 */
export async function openShelterEntrance(
  context: SkillContext,
  home: Position,
): Promise<boolean> {
  let opened = false;
  for (const position of shelterEntrance(home)) {
    const block = context.embodiment.blockAt(position);
    if (!block || !block.solid) continue;
    if (!block.ownedByPerson && !context.memory.isOwnedBlock(position))
      return false;
    await context.embodiment.dig(position);
    context.memory.placedBlocks.delete(
      `${position.x},${position.y},${position.z}`,
    );
    opened = true;
  }
  return opened;
}

/** Replaces the doorway blocks, lowest first so each has something to rest on. */
export async function sealShelterEntrance(
  context: SkillContext,
  home: Position,
): Promise<boolean> {
  for (const position of [...shelterEntrance(home)].reverse()) {
    const block = context.embodiment.blockAt(position);
    if (block?.solid) continue;
    if (!context.permissions.mayBuild(position).allowed) return false;
    const material = buildingItem(context);
    if (!material) return false;
    await context.embodiment.place(position, material);
    context.memory.recordPlacement(position);
  }
  return true;
}
