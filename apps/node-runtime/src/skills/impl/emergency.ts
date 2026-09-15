import { distance, type Position } from "#config";
import {
  SkillFailure,
  itemCount,
  type SkillContext,
  type SkillImplementation,
} from "../execution.ts";
import { isBuildingMaterial } from "../materials.ts";
import { travelTo } from "../navigate.ts";
import {
  openShelterEntrance,
  sealShelterEntrance,
  shelterIsSealed,
} from "../shelter-access.ts";

const DIRECTIONS: [number, number][] = [
  [1, 0],
  [-1, 0],
  [0, 1],
  [0, -1],
  [1, 1],
  [1, -1],
  [-1, 1],
  [-1, -1],
];

const hostileClearance = (
  context: SkillContext,
  position: Position,
): number => {
  const hostiles = context
    .snapshot()
    .entities.filter((entity) => entity.hostile);
  if (hostiles.length === 0) return Number.POSITIVE_INFINITY;
  return Math.min(
    ...hostiles.map((entity) => distance(position, entity.position)),
  );
};

const standingHazard = (context: SkillContext): boolean => {
  const snapshot = context.snapshot();
  return snapshot.hazards.some(
    (hazard) => distance(snapshot.position, hazard.position) <= 1.5,
  );
};

const buildingItem = (context: SkillContext): string | null =>
  context.snapshot().inventory.find((item) => isBuildingMaterial(item.name))
    ?.name ?? null;

/**
 * Move away from hostiles and hazards until a clearance target is met.
 *
 * Short hops are preferred over one long route: mob positions go stale quickly
 * and a long path is a long time without re-checking. Bounded self-defence is
 * allowed against a hostile that is already in contact, and only against a
 * hostile.
 */
export const flee: SkillImplementation = async (context) => {
  const clearance = context.number("min_clearance");
  let hopped = 0;
  for (let attempt = 0; attempt < 8; attempt++) {
    context.checkpoint();
    const snapshot = context.snapshot();
    const hostiles = snapshot.entities.filter((entity) => entity.hostile);
    if (
      hostileClearance(context, snapshot.position) >= clearance &&
      !standingHazard(context)
    ) {
      context.effect("threat_cleared");
      context.note("threat_clearance", {
        clearance: Math.min(
          9999,
          Math.round(hostileClearance(context, snapshot.position)),
        ),
        hops: hopped,
      });
      return;
    }

    const contact = hostiles.find((entity) => entity.distance <= 2.5);
    if (contact && context.permissions.mayDefend(contact).allowed) {
      await context.embodiment.attack(contact.entityId);
      context.effect("defensive_strike");
      context.note("vitals_delta", { defended_against: contact.name });
    }

    const away = { x: 0, z: 0 };
    for (const hostile of hostiles) {
      away.x += snapshot.position.x - hostile.position.x;
      away.z += snapshot.position.z - hostile.position.z;
    }
    const magnitude = Math.hypot(away.x, away.z) || 1;
    const preferred: [number, number] = [
      away.x / magnitude,
      away.z / magnitude,
    ];
    const options = [
      preferred,
      ...DIRECTIONS.map(([x, z]) => [x, z] as [number, number]),
    ];

    let moved = false;
    for (const [dx, dz] of options) {
      for (const radius of [8, 5, 3]) {
        const target: Position = {
          x: Math.round(snapshot.position.x + dx * radius),
          y: snapshot.position.y,
          z: Math.round(snapshot.position.z + dz * radius),
        };
        if (!context.permissions.mayEnter(target).allowed) continue;
        if (
          hostileClearance(context, target) <=
          hostileClearance(context, snapshot.position)
        )
          continue;
        try {
          await context.embodiment.moveTo(target, { range: 1, maxTicks: 200 });
          moved = true;
          hopped += 1;
          break;
        } catch {
          // Try the next direction; a blocked hop is normal while fleeing.
        }
      }
      if (moved) break;
    }
    if (!moved) break;
  }

  const final = context.snapshot();
  if (
    hostileClearance(context, final.position) >= clearance &&
    !standingHazard(context)
  ) {
    context.effect("threat_cleared");
    context.note("threat_clearance", { clearance: clearance, hops: hopped });
    return;
  }
  throw new SkillFailure(
    "no_safe_route",
    "FAILED",
    "No route increased clearance from the threat",
  );
};

/**
 * Dig a short refuge away from the threat and seal the entrance behind.
 * Used when there is no outward route left.
 */
export const digIn: SkillImplementation = async (context) => {
  const snapshot = context.snapshot();
  const depth = context.number("depth");
  const threat = snapshot.entities
    .filter((entity) => entity.hostile)
    .sort((a, b) => a.distance - b.distance)[0];
  const feet = snapshot.position;
  const dx = threat
    ? Math.abs(threat.position.x - feet.x) >=
      Math.abs(threat.position.z - feet.z)
      ? -Math.sign(threat.position.x - feet.x)
      : 0
    : 1;
  const dz =
    dx === 0 ? -Math.sign((threat?.position.z ?? feet.z + 1) - feet.z) : 0;
  if (dx === 0 && dz === 0)
    throw new SkillFailure(
      "no_diggable_ground",
      "FAILED",
      "Cannot choose a refuge direction",
    );

  const targets: Position[] = [];
  for (let step = 1; step <= depth; step++)
    for (const dy of [0, 1])
      targets.push({
        x: feet.x + dx * step,
        y: feet.y + dy,
        z: feet.z + dz * step,
      });

  for (const target of targets) {
    const verdict = context.permissions.mayEmergencyDig(target);
    if (!verdict.allowed)
      throw new SkillFailure(
        verdict.reason === "protected_area"
          ? "protected_area"
          : "no_diggable_ground",
        "INVALIDATED",
        `Emergency dig denied at ${target.x},${target.y},${target.z}: ${verdict.reason}`,
      );
    const block = context.embodiment.blockAt(target);
    if (!block)
      throw new SkillFailure(
        "no_diggable_ground",
        "FAILED",
        "Refuge blocks unknown",
      );
    if (!block.solid) continue;
    if (!["dirt", "grass", "stone"].includes(block.kind))
      throw new SkillFailure(
        "no_diggable_ground",
        "FAILED",
        `Cannot dig ${block.name}`,
      );
    await context.embodiment.dig(target);
    context.note("harvested_blocks", { block: block.name });
  }

  const entrance: Position = { x: feet.x + dx, y: feet.y, z: feet.z + dz };
  await context.embodiment.moveTo(entrance, { range: 0, maxTicks: 120 });
  const cover = { x: feet.x, y: feet.y, z: feet.z };
  const material = buildingItem(context);
  if (material && context.permissions.mayBuild(cover).allowed) {
    try {
      await context.embodiment.place(cover, material);
      context.memory.recordPlacement(cover);
      context.note("placed_blocks", { sealed_with: material });
    } catch {
      // An unsealed refuge is still better than standing in the open.
    }
  }
  context.effect("refuge_dug");
  context.note("position_reached", {
    x: entrance.x,
    y: entrance.y,
    z: entrance.z,
  });
};

/** Hold position in a verified safe place for the requested budget. */
export const waitSafely: SkillImplementation = async (context) => {
  const total = context.number("ticks");
  const step = 20;
  let waited = 0;
  while (waited < total) {
    context.checkpoint();
    const snapshot = context.snapshot();
    if (
      snapshot.entities.some((entity) => entity.hostile && entity.distance <= 8)
    )
      throw new SkillFailure(
        "threat_appeared",
        "INTERRUPTED",
        "A hostile approached during the wait",
      );
    if (standingHazard(context))
      throw new SkillFailure(
        "hazard_appeared",
        "INTERRUPTED",
        "A hazard reached the wait position",
      );
    await context.embodiment.waitTicks(Math.min(step, total - waited));
    waited += step;
  }
  context.effect("waited_safely");
  context.note("elapsed_ticks", { waited: Math.min(waited, total) });
};

/** Travel back to the active home position by a permitted route. */
export const returnHome: SkillImplementation = async (context) => {
  const home = context.home();
  const sealed = shelterIsSealed(context, home);
  try {
    await travelTo(context, home, sealed ? 2 : 1);
  } catch (error) {
    // A sealed shelter is a closed door, not an unreachable destination.
    if (!sealed) throw error;
    const opened = await openShelterEntrance(context, home);
    if (!opened) throw error;
    await travelTo(context, home, 0);
    await sealShelterEntrance(context, home);
    context.effect("entered_shelter");
  }
  const arrived = context.snapshot().position;
  if (distance(arrived, home) > 2.5)
    throw new SkillFailure(
      "unreachable_home",
      "UNREACHABLE",
      "Route ended away from home",
    );
  context.effect("arrived_home");
  context.note("position_reached", {
    x: arrived.x,
    y: arrived.y,
    z: arrived.z,
  });
};

export const emergencySkills: Record<string, SkillImplementation> = {
  flee,
  dig_in: digIn,
  wait_safely: waitSafely,
  return_home: returnHome,
};

export { buildingItem, itemCount };
