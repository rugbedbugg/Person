import { distance, positionKey, type Position } from "#config";
import {
  envelope,
  type Observation,
  type PreviousOutcome,
  type SessionIdentity,
  type TrainingContext,
} from "#protocol";
import type { WorldSnapshot } from "../embodiment/types.ts";
import type { PermissionGate } from "../safety/permissions.ts";
import type { SafetyKernel } from "../safety/safety-kernel.ts";
import { categories } from "../skills/materials.ts";
import { PERCEPTION, resourceCategory, shapeEntities } from "./perception.ts";
import { eyePose, visible, VISION } from "./vision.ts";
import { relativeTo } from "./relative.ts";
import { shelterPlan } from "../skills/shelter-plan.ts";
import { poseOf, selfMotion, type SelfMotion } from "./self-motion.ts";
import type { PlacementLedger } from "../runtime/placement-ledger.ts";

/**
 * Raised whenever what an observation means changes, so evidence recorded
 * under one contract is never read as the other. 2: relative percepts replaced
 * coordinates. 3: a peripheral entity no longer says whose it is. 4: ledger
 * workstations say they come from the placement ledger, not from memory.
 * 5: `selfMotion`, a coarse relative sense of Person's own movement.
 * 6: `home.homeDistance` removed. A drift-free distance to home at any range
 * is not a sense; Person's relation to home is its own belief (C8).
 */
export const OBSERVATION_VERSION = 6;

export interface CognitionState {
  activeGoal: string | null;
  activeRoutine: string | null;
  activeSkill: string | null;
  suspendedGoals: string[];
}

export interface ObservationInputs {
  identity: SessionIdentity;
  snapshot: WorldSnapshot;
  permissions: PermissionGate;
  kernel: SafetyKernel;
  ledger: PlacementLedger;
  trainingContext: TrainingContext;
  cognition: CognitionState;
  previousOutcome: PreviousOutcome | null;
  blockAt: (
    position: Position,
  ) => { solid: boolean; hazard: boolean; kind: string } | null;
  /**
   * What Person felt of its own motion since the previous observation
   * (ADR 0008). A caller with no sense, such as a one-off `person observe`,
   * leaves it out and the observation says the sense has only just started.
   */
  selfMotion?: SelfMotion;
}

const dayPhase = (
  timeOfDay: number,
): Observation["environment"]["dayPhase"] => {
  if (timeOfDay >= 23000 || timeOfDay < 1000) return "dawn";
  if (timeOfDay < 11000) return "day";
  if (timeOfDay < 13000) return "dusk";
  return "night";
};

function shelterState(
  inputs: ObservationInputs,
): Observation["home"]["shelterState"] {
  const home = inputs.ledger.home.position;
  const plan = shelterPlan(home);
  const present = plan.filter(
    (position) => inputs.blockAt(position)?.solid === true,
  ).length;
  if (present === plan.length) return "complete";
  if (inputs.ledger.home.shelterState === "complete") return "breached";
  if (present > 0 && inputs.ledger.placedBlocks.size > 0) return "partial";
  return "none";
}

function affordances(inputs: ObservationInputs): Observation["affordances"] {
  const { snapshot, permissions, ledger } = inputs;
  const here = snapshot.position;
  // The body already worked this out for the safety kernel; asking it again
  // here would be a second answer to the same question.
  const diggable =
    snapshot.diggableGround &&
    [
      { x: here.x + 1, y: here.y, z: here.z },
      { x: here.x - 1, y: here.y, z: here.z },
      { x: here.x, y: here.y, z: here.z + 1 },
      { x: here.x, y: here.y, z: here.z - 1 },
    ].some((position) => permissions.mayEmergencyDig(position).allowed);

  const home = ledger.home.position;
  const floor = inputs.blockAt({ ...home, y: home.y - 1 });
  const shelterSite =
    floor?.solid === true &&
    permissions.mayBuild(home).allowed &&
    shelterPlan(home).every(
      (position) => permissions.mayBuild(position).allowed,
    );

  const storageSite = [
    { x: home.x + 2, y: home.y, z: home.z },
    { x: home.x - 2, y: home.y, z: home.z },
    { x: home.x, y: home.y, z: home.z + 2 },
    { x: home.x, y: home.y, z: home.z - 2 },
  ].some((position) => {
    const block = inputs.blockAt(position);
    const below = inputs.blockAt({ ...position, y: position.y - 1 });
    return (
      block !== null &&
      !block.solid &&
      below?.solid === true &&
      permissions.mayBuild(position).allowed
    );
  });

  return { diggableGround: diggable, shelterSite, storageSite };
}

/**
 * Builds the semantic observation cognition sees.
 *
 * Everything here is derived: no Mineflayer object, no block array, no raw
 * entity handle crosses the boundary. What cognition may do is reported as
 * permissions, so the answer always comes from the side that enforces it.
 */
export function buildObservation(inputs: ObservationInputs): Observation {
  const { snapshot, permissions, ledger } = inputs;
  const home = ledger.home.position;
  // Where Person is looking, and what that lets it see. Privileged: the pose
  // is used here and never reported.
  const pose = eyePose(snapshot);
  const sighted = <T>(
    candidates: readonly T[],
    at: (item: T) => Position,
    limit: number,
  ): T[] => visible(candidates, at, pose, inputs.blockAt, { limit });
  const located = (position: Position, span: number) =>
    relativeTo(pose, position, span);
  const ownedKeys = new Set(
    ledger.ownedStorage.map((record) => positionKey(record.position)),
  );

  // Containers are found by looking, so they are filtered by what Person can
  // see. The ones Person placed itself are reported under `home.ownedStorage`,
  // which comes from the placement ledger rather than from sight.
  const containers = sighted(
    snapshot.containers,
    (container) => container.position,
    PERCEPTION.containers.total,
  ).map((container) => {
    const owned =
      container.storageId !== null ||
      ownedKeys.has(positionKey(container.position));
    return {
      kind: container.kind,
      ...located(
        container.position,
        distance(snapshot.position, container.position),
      ),
      provenance: (owned ? "owned" : "existing") as "owned" | "existing",
      storageId:
        container.storageId ??
        ledger.storageAt(container.position)?.storageId ??
        null,
    };
  });

  // Workstations come from Person's own placement ledger, so they are known
  // rather than seen and are not filtered by line of sight. This is the one
  // channel in `nearby` that reports a thing Person is not currently looking
  // at, it reports only Person's own work, and it is runtime bookkeeping, not
  // Person's memory: recollection reaches cognition by its own bounded path.
  const workstations: Observation["nearby"]["workstations"] = [];
  if (ledger.craftingTablePosition)
    workstations.push({
      kind: "crafting_table",
      ...located(
        ledger.craftingTablePosition,
        distance(snapshot.position, ledger.craftingTablePosition),
      ),
      provenance: "owned",
      source: "placement_ledger",
    });
  if (ledger.furnacePosition)
    workstations.push({
      kind: "furnace",
      ...located(
        ledger.furnacePosition,
        distance(snapshot.position, ledger.furnacePosition),
      ),
      provenance: "owned",
      source: "placement_ledger",
    });

  // Identity is reported as strongly as the body can establish it. The entity
  // id is a session-local handle and the display name of every player in
  // Minecraft is literally "player", so neither survives a reconnect or tells
  // two people apart; the username and the UUID do, and they are carried
  // through whenever the client actually has them.
  // What Person can tell about something it is looking at: what kind of thing
  // it is, where it is relative to Person, and whether it is someone's. The
  // entity id and the account UUID are protocol handles rather than anything
  // Person could perceive, so neither is reported. A player's name is on a
  // nameplate above their head, so that one is.
  const entityRecord = (entity: WorldSnapshot["entities"][number]) => {
    const where = located(entity.position, entity.distance);
    const recognised = where.detail === "central";
    return {
      // Which species it is, and whose it is, are things Person reads off a
      // thing it is looking at. In the corner of the eye there is movement at
      // a bearing, and the list it arrived in already says whether it is a
      // threat. Whether the runtime would let Person hunt it is withheld with
      // them, because the verdict is computed from exactly those facts and
      // would give them away.
      ...where,
      ...(recognised
        ? {
            name: entity.name,
            named: entity.named,
            tamed: entity.tamed,
            protectedTarget: !permissions.mayHunt(entity).allowed,
          }
        : {}),
      ...(recognised && entity.username !== null
        ? { username: entity.username }
        : {}),
    };
  };

  const inventoryCategories = categories(snapshot.inventory);
  const storedFood = ledger.ownedStorage.reduce((total, record) => {
    const container = snapshot.containers.find(
      (candidate) =>
        positionKey(candidate.position) === positionKey(record.position),
    );
    return (
      total +
      (container?.contents ?? [])
        .filter((item) =>
          /(^cooked_|^sweet_berries$|^apple$|^bread$|^carrot$)/.test(item.name),
        )
        .reduce((sum, item) => sum + item.count, 0)
    );
  }, 0);

  const threat = inputs.kernel.threatState(snapshot);

  return {
    ...envelope(inputs.identity, "Observation", snapshot.tick),
    type: "Observation",
    observationVersion: OBSERVATION_VERSION,
    trainingContext: inputs.trainingContext,
    selfMotion: inputs.selfMotion ?? selfMotion(null, poseOf(snapshot)),
    vitals: {
      health: snapshot.health,
      food: snapshot.food,
      saturation: snapshot.saturation,
      air: snapshot.air,
      armor: snapshot.armor,
      statusEffects: snapshot.statusEffects,
      alive: snapshot.alive,
    },
    environment: {
      dimension: snapshot.dimension,
      dayPhase: dayPhase(snapshot.timeOfDay),
      timeOfDay: snapshot.timeOfDay,
      weather: snapshot.weather,
      lightLevel: snapshot.lightLevel,
      biome: snapshot.biome,
    },
    inventory: {
      items: snapshot.inventory,
      categories: inventoryCategories,
      freeSlots: snapshot.freeSlots,
    },
    permissions: permissions.summary() as Observation["permissions"],
    affordances: affordances(inputs),
    nearby: {
      resources: sighted(
        snapshot.resources,
        (block) => block.position,
        PERCEPTION.resources.total,
      ).map((block) => {
        const where = located(
          block.position,
          distance(snapshot.position, block.position),
        );
        return {
          kind: resourceCategory(block.kind),
          // The coarse category survives the periphery; the exact block does
          // not. Person can see that there is vegetation over there without
          // being able to say it is a sweet berry bush.
          ...(where.detail === "central" ? { name: block.name } : {}),
          ...where,
          harvestPermitted: permissions.mayHarvest(block.position).allowed,
        };
      }),
      hostiles: sighted(
        shapeEntities(
          snapshot.entities.filter((entity) => entity.hostile),
          { limit: PERCEPTION.entities.hostileTotal },
        ),
        (entity) => entity.position,
        PERCEPTION.entities.hostileTotal,
      ).map(entityRecord),
      // Passive animals are shaped to the region Person may actually walk
      // into. The unshaped list stays in the snapshot the safety kernel and
      // the permission gate read, so this changes what cognition is told and
      // nothing about what it is allowed to do.
      passiveAnimals: sighted(
        shapeEntities(
          snapshot.entities.filter((entity) => entity.passive),
          {
            limit: PERCEPTION.entities.passiveTotal,
            radius: PERCEPTION.entities.passiveRadius,
            keep: (entity) => permissions.areas.permitted(entity.position),
          },
        ),
        (entity) => entity.position,
        PERCEPTION.entities.passiveTotal,
      ).map(entityRecord),
      players: sighted(
        shapeEntities(
          snapshot.entities.filter((entity) => entity.player),
          { limit: PERCEPTION.entities.playerTotal },
        ),
        (entity) => entity.position,
        PERCEPTION.entities.playerTotal,
      ).map(entityRecord),
      containers,
      workstations,
      hazards: sighted(
        snapshot.hazards,
        (hazard) => hazard.position,
        PERCEPTION.hazards.total,
      ).map((hazard) => ({
        kind: (["lava", "fire", "water", "cactus"].includes(hazard.kind)
          ? hazard.kind
          : "other") as Observation["nearby"]["hazards"][number]["kind"],
        ...located(
          hazard.position,
          distance(snapshot.position, hazard.position),
        ),
      })),
    },
    home: {
      activeHome: { homeId: ledger.home.homeId },
      shelterState: shelterState(inputs),
      ownedStorage: ledger.ownedStorage.map((record) => ({
        storageId: record.storageId,
        contents:
          snapshot.containers.find(
            (candidate) =>
              positionKey(candidate.position) === positionKey(record.position),
          )?.contents ?? [],
      })),
      bedKnown: ledger.home.bedKnown,
      foodReserve: storedFood,
      fuelReserve: inventoryCategories["fuel"] ?? 0,
    },
    navigation: {
      routeStatus: snapshot.stuck ? "blocked" : "idle",
      pathRisk:
        threat === "immediate"
          ? "high"
          : threat === "nearby"
            ? "moderate"
            : "low",
      stuckState: snapshot.stuck ? "stuck" : "free",
      returnPathKnown: permissions.areas.routePermitted(
        snapshot.position,
        home,
      ),
    },
    cognition: inputs.cognition,
    previousOutcome: inputs.previousOutcome,
  };
}
