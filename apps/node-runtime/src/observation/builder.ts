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
import { shelterPlan } from "../skills/shelter-plan.ts";
import type { WorldMemory } from "../runtime/world-memory.ts";

export const OBSERVATION_VERSION = 1;

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
  memory: WorldMemory;
  trainingContext: TrainingContext;
  cognition: CognitionState;
  previousOutcome: PreviousOutcome | null;
  blockAt: (
    position: Position,
  ) => { solid: boolean; hazard: boolean; kind: string } | null;
}

const dayPhase = (
  timeOfDay: number,
): Observation["environment"]["dayPhase"] => {
  if (timeOfDay >= 23000 || timeOfDay < 1000) return "dawn";
  if (timeOfDay < 11000) return "day";
  if (timeOfDay < 13000) return "dusk";
  return "night";
};

const resourceKind = (
  kind: string,
): "wood" | "stone" | "coal" | "plant_food" | "dirt" | "other" => {
  switch (kind) {
    case "wood":
      return "wood";
    case "stone":
    case "cobblestone":
      return "stone";
    case "coal_ore":
      return "coal";
    case "plant_food":
    case "leaves":
      return "plant_food";
    case "dirt":
    case "grass":
      return "dirt";
    default:
      return "other";
  }
};

function shelterState(
  inputs: ObservationInputs,
): Observation["home"]["shelterState"] {
  const home = inputs.memory.home.position;
  const plan = shelterPlan(home);
  const present = plan.filter(
    (position) => inputs.blockAt(position)?.solid === true,
  ).length;
  if (present === plan.length) return "complete";
  if (inputs.memory.home.shelterState === "complete") return "breached";
  if (present > 0 && inputs.memory.placedBlocks.size > 0) return "partial";
  return "none";
}

function affordances(inputs: ObservationInputs): Observation["affordances"] {
  const { snapshot, permissions, memory } = inputs;
  const here = snapshot.position;
  const diggable = [
    { x: here.x + 1, y: here.y, z: here.z },
    { x: here.x - 1, y: here.y, z: here.z },
    { x: here.x, y: here.y, z: here.z + 1 },
    { x: here.x, y: here.y, z: here.z - 1 },
  ].some((position) => {
    const block = inputs.blockAt(position);
    return (
      block !== null &&
      block.solid &&
      ["dirt", "grass", "stone"].includes(block.kind) &&
      permissions.mayEmergencyDig(position).allowed
    );
  });

  const home = memory.home.position;
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
  const { snapshot, permissions, memory } = inputs;
  const home = memory.home.position;
  const homeDistance = distance(snapshot.position, home);
  const ownedKeys = new Set(
    memory.ownedStorage.map((record) => positionKey(record.position)),
  );

  const containers = snapshot.containers.map((container) => {
    const owned =
      container.storageId !== null ||
      ownedKeys.has(positionKey(container.position));
    return {
      kind: container.kind,
      position: container.position,
      distance: distance(snapshot.position, container.position),
      provenance: (owned ? "owned" : "existing") as "owned" | "existing",
      storageId:
        container.storageId ??
        memory.storageAt(container.position)?.storageId ??
        null,
    };
  });

  const workstations: Observation["nearby"]["workstations"] = [];
  if (memory.craftingTablePosition)
    workstations.push({
      kind: "crafting_table",
      position: memory.craftingTablePosition,
      distance: distance(snapshot.position, memory.craftingTablePosition),
      provenance: "owned",
    });
  if (memory.furnacePosition)
    workstations.push({
      kind: "furnace",
      position: memory.furnacePosition,
      distance: distance(snapshot.position, memory.furnacePosition),
      provenance: "owned",
    });

  const entityRecord = (entity: WorldSnapshot["entities"][number]) => ({
    entityId: entity.entityId,
    name: entity.name,
    position: entity.position,
    distance: entity.distance,
    named: entity.named,
    tamed: entity.tamed,
    protectedTarget: !permissions.mayHunt(entity).allowed,
  });

  const inventoryCategories = categories(snapshot.inventory);
  const storedFood = memory.ownedStorage.reduce((total, record) => {
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
      position: snapshot.position,
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
      resources: snapshot.resources.map((block) => ({
        kind: resourceKind(block.kind),
        name: block.name,
        position: block.position,
        distance: distance(snapshot.position, block.position),
        harvestPermitted: permissions.mayHarvest(block.position).allowed,
      })),
      hostiles: snapshot.entities
        .filter((entity) => entity.hostile)
        .map(entityRecord),
      passiveAnimals: snapshot.entities
        .filter((entity) => entity.passive)
        .map(entityRecord),
      players: snapshot.entities
        .filter((entity) => entity.player)
        .map(entityRecord),
      containers,
      workstations,
      hazards: snapshot.hazards.map((hazard) => ({
        kind: (["lava", "fire", "water", "cactus"].includes(hazard.kind)
          ? hazard.kind
          : "other") as Observation["nearby"]["hazards"][number]["kind"],
        position: hazard.position,
        distance: distance(snapshot.position, hazard.position),
      })),
    },
    home: {
      activeHome: { homeId: memory.home.homeId, position: home },
      homeDistance,
      shelterState: shelterState(inputs),
      ownedStorage: memory.ownedStorage.map((record) => ({
        storageId: record.storageId,
        position: record.position,
        contents:
          snapshot.containers.find(
            (candidate) =>
              positionKey(candidate.position) === positionKey(record.position),
          )?.contents ?? [],
      })),
      bedKnown: memory.home.bedKnown,
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
      lastSafePosition: snapshot.lastSafePosition,
    },
    cognition: inputs.cognition,
    previousOutcome: inputs.previousOutcome,
  };
}
