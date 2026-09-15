import { distance, type Position } from "#config";
import type { BlockView } from "../embodiment/types.ts";
import { SkillFailure, type SkillContext } from "./execution.ts";
import { insideShelter, openShelterEntrance } from "./shelter-access.ts";

const OFFSETS: [number, number, number][] = [];
for (let dx = -3; dx <= 3; dx++)
  for (let dz = -3; dz <= 3; dz++)
    for (let dy = -2; dy <= 2; dy++) OFFSETS.push([dx, dy, dz]);

const standable = (context: SkillContext, position: Position): boolean => {
  const feet = context.embodiment.blockAt(position);
  const head = context.embodiment.blockAt({ ...position, y: position.y + 1 });
  const floor = context.embodiment.blockAt({ ...position, y: position.y - 1 });
  if (!feet || !head || !floor) return false;
  if (feet.solid || head.solid || feet.hazard || head.hazard || floor.hazard)
    return false;
  return floor.solid;
};

/** Standing positions from which a block can be reached, safest first. */
export function approachPositions(
  context: SkillContext,
  target: Position,
): Position[] {
  const origin = context.snapshot().position;
  return OFFSETS.map(([dx, dy, dz]) => ({
    x: target.x + dx,
    y: target.y + dy,
    z: target.z + dz,
  }))
    .filter((candidate) => distance(candidate, target) <= 3.5)
    .filter((candidate) => context.permissions.mayEnter(candidate).allowed)
    .filter((candidate) => standable(context, candidate))
    .sort((a, b) => distance(origin, a) - distance(origin, b));
}

/**
 * Opens the shelter doorway when Person is sealed inside it.
 *
 * A route that fails because Person walled itself in is a closed door, not an
 * unreachable destination. Every outward move gets one attempt at the door.
 */
async function ensureEgress(context: SkillContext): Promise<boolean> {
  const home = context.home();
  if (!insideShelter(context, home)) return false;
  try {
    return await openShelterEntrance(context, home);
  } catch {
    return false;
  }
}

/** Walks to a position from which `target` can be worked on. */
export async function approach(
  context: SkillContext,
  target: Position,
): Promise<void> {
  if (distance(context.snapshot().position, target) <= 3.5) return;
  context.checkpoint();
  let lastReason = "no_route";
  for (let attempt = 0; attempt < 2; attempt++) {
    const candidates = approachPositions(context, target).slice(0, 6);
    if (candidates.length === 0) lastReason = "No permitted approach position";
    for (const candidate of candidates) {
      context.checkpoint();
      try {
        await context.embodiment.moveTo(candidate, {
          range: 0,
          maxTicks: context.limits.maxTicks,
        });
        return;
      } catch (error) {
        lastReason = (error as Error).message;
      }
    }
    if (attempt === 1 || !(await ensureEgress(context))) break;
  }
  throw new SkillFailure("unreachable_target", "UNREACHABLE", lastReason);
}

export async function travelTo(
  context: SkillContext,
  target: Position,
  range = 1,
): Promise<void> {
  if (!context.permissions.mayEnter(target).allowed)
    throw new SkillFailure(
      "protected_area",
      "INVALIDATED",
      "Destination is not permitted",
    );
  context.checkpoint();
  let lastError = "no_route";
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      await context.embodiment.moveTo(target, {
        range,
        maxTicks: context.limits.maxTicks,
      });
      return;
    } catch (error) {
      lastError = (error as Error).message;
    }
    if (attempt === 1 || !(await ensureEgress(context))) break;
  }
  throw new SkillFailure("no_route", "UNREACHABLE", lastError);
}

/** Resources the permission gate currently allows harvesting, nearest first. */
export function permittedResources(
  context: SkillContext,
  kinds: BlockView["kind"][],
  maxDistance: number,
  limit = 32,
): BlockView[] {
  const origin = context.snapshot().position;
  return context.embodiment
    .findBlocks({ kinds, maxDistance, limit })
    .filter((block) => context.permissions.mayHarvest(block.position).allowed)
    .sort(
      (a, b) => distance(origin, a.position) - distance(origin, b.position),
    );
}
