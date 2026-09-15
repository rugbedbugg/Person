import { randomUUID } from "node:crypto";
import path from "node:path";
import type { PersonConfig } from "#config";
import type { Observation } from "#protocol";
import { protocolValidator } from "#protocol";
import {
  PermissionGate,
  ProtectedAreas,
  SafetyKernel,
  WorldMemory,
  buildObservation,
  type Embodiment,
  type PhysicalGuard,
} from "#node-runtime";
import { createEmbodiment } from "./embodiment.ts";

/**
 * Captures exactly one observation and stops.
 *
 * This is the Stage B instrument: it connects a body, normalises what it can
 * see, checks the result against the protocol schema, and disconnects without
 * running a skill. Against Minecraft it is the smallest possible thing that
 * can still be wrong, which makes it the right first contact with a server.
 */
export async function captureObservation(
  config: PersonConfig,
  baseDirectory: string,
): Promise<{
  observation: Observation;
  valid: boolean;
  diagnostics: string[];
}> {
  const embodiment: Embodiment = await createEmbodiment(config, baseDirectory);
  const areas = new ProtectedAreas(config);
  const permissions = new PermissionGate(config, areas);
  const kernel = new SafetyKernel(permissions);
  const memory = WorldMemory.load(
    config.runtime.outputDirectory,
    config.worldId,
    config.personId,
    config.world.home,
  );
  const guard: PhysicalGuard = {
    canEnter: (position) => permissions.mayEnter(position).allowed,
    canModify: (position) =>
      areas.permitted(position) &&
      (areas.harvestable(position) || permissions.mayBuild(position).allowed),
    canTargetEntity: (entity) =>
      permissions.mayHunt(entity).allowed ||
      permissions.mayDefend(entity).allowed,
  };
  embodiment.setGuard(guard);
  try {
    await embodiment.connect();
    const observation = buildObservation({
      identity: {
        personId: config.personId,
        sessionId: randomUUID(),
        worldId: config.worldId,
      },
      snapshot: embodiment.snapshot(),
      permissions,
      kernel,
      memory,
      trainingContext: config.runtime.trainingContext,
      cognition: {
        activeGoal: null,
        activeRoutine: null,
        activeSkill: null,
        suspendedGoals: [],
      },
      previousOutcome: null,
      blockAt: (position) => embodiment.blockAt(position),
    });
    const result = protocolValidator().validate(observation);
    return {
      observation,
      valid: result.valid,
      diagnostics: result.diagnostics,
    };
  } finally {
    await embodiment.disconnect();
  }
}

export interface Finding {
  path: string;
  kind: "missing" | "differs" | "suspicious";
  expected?: unknown;
  actual?: unknown;
  note: string;
}

type Json = Record<string, unknown>;

const isObject = (value: unknown): value is Json =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/**
 * Fields whose value can be technically valid and still mean "this runtime
 * never filled it in". A fixture that never populates a field and a real body
 * that cannot populate it look identical in a plain diff, which is exactly the
 * confusion this milestone exists to remove.
 */
const SUSPICIOUS: {
  path: string;
  when: (value: unknown) => boolean;
  note: string;
}[] = [
  {
    path: "/environment/biome",
    when: (value) => value === "unknown",
    note: "biome was not read from the world; block biome data may be unavailable",
  },
  {
    path: "/vitals/armor",
    when: (value) => value === 0,
    note: "armor is always zero: worn armour is not being read",
  },
  {
    path: "/vitals/saturation",
    when: (value) => value === 0,
    note: "saturation is zero, which is plausible when hungry and suspicious when full",
  },
  {
    path: "/navigation/lastSafePosition",
    when: (value) => value === null,
    note: "no safe position has been recorded yet",
  },
  {
    path: "/home/homeDistance",
    when: (value) => value === null,
    note: "home distance is unknown, so every home-relative decision is blind",
  },
  {
    path: "/nearby/resources",
    when: (value) => Array.isArray(value) && value.length === 0,
    note: "no resources in range at all: check the search radius and block classification",
  },
  {
    path: "/inventory/freeSlots",
    when: (value) => value === 36,
    note: "the inventory reports completely empty, which may mean it was not read",
  },
];

function walk(
  expected: unknown,
  actual: unknown,
  at: string,
  findings: Finding[],
): void {
  if (isObject(expected) && isObject(actual)) {
    for (const key of Object.keys(expected)) {
      const next = `${at}/${key}`;
      if (!(key in actual)) {
        findings.push({
          path: next,
          kind: "missing",
          expected: expected[key],
          note: "present in the reference observation, absent here",
        });
        continue;
      }
      walk(expected[key], actual[key], next, findings);
    }
    for (const key of Object.keys(actual))
      if (!(key in expected))
        findings.push({
          path: `${at}/${key}`,
          kind: "differs",
          actual: actual[key],
          note: "present here, absent from the reference observation",
        });
    return;
  }
  if (Array.isArray(expected) && Array.isArray(actual)) {
    if (expected.length !== actual.length)
      findings.push({
        path: at,
        kind: "differs",
        expected: expected.length,
        actual: actual.length,
        note: "different number of entries",
      });
    return;
  }
  if (JSON.stringify(expected) !== JSON.stringify(actual))
    findings.push({
      path: at,
      kind: "differs",
      expected,
      actual,
      note: "values differ",
    });
}

function read(document: unknown, pointer: string): unknown {
  let cursor: unknown = document;
  for (const segment of pointer.split("/").filter(Boolean)) {
    if (!isObject(cursor)) return undefined;
    cursor = cursor[segment];
  }
  return cursor;
}

/**
 * A semantic comparison of two observations.
 *
 * Structural differences are expected: two worlds are two worlds. What matters
 * is whether the *shape* of the real observation matches what the fixture
 * taught the cognition process to expect, and whether any field looks like a
 * default that nothing ever wrote.
 */
export function compareObservations(
  reference: unknown,
  actual: unknown,
): { findings: Finding[]; structural: number; suspicious: number } {
  const findings: Finding[] = [];
  walk(reference, actual, "", findings);
  const structural = findings.filter(
    (finding) => finding.kind === "missing",
  ).length;

  for (const rule of SUSPICIOUS) {
    const value = read(actual, rule.path);
    if (value === undefined) continue;
    if (rule.when(value))
      findings.push({
        path: rule.path,
        kind: "suspicious",
        actual: value,
        note: rule.note,
      });
  }
  return {
    findings,
    structural,
    suspicious: findings.filter((finding) => finding.kind === "suspicious")
      .length,
  };
}

export function renderObservation(observation: Observation): string {
  const lines: string[] = [];
  const vitals = observation.vitals;
  const environment = observation.environment;
  lines.push(
    `Observation v${observation.observationVersion} (${observation.trainingContext})`,
  );
  lines.push(
    `  vitals   health=${vitals.health} food=${vitals.food} saturation=${vitals.saturation} air=${vitals.air} armor=${vitals.armor} alive=${vitals.alive}`,
  );
  lines.push(
    `  world    ${environment.dimension} ${environment.dayPhase} time=${environment.timeOfDay} weather=${environment.weather} light=${environment.lightLevel} biome=${environment.biome}`,
  );
  lines.push(
    `  position ${environment.position.x},${environment.position.y},${environment.position.z}`,
  );
  const categories = Object.entries(observation.inventory.categories)
    .filter(([, count]) => count > 0)
    .map(([name, count]) => `${name}=${count}`)
    .join(" ");
  lines.push(
    `  items    ${observation.inventory.items.length} stacks, ${observation.inventory.freeSlots} free slots${categories ? ` (${categories})` : ""}`,
  );
  const nearby = observation.nearby;
  lines.push(
    `  nearby   resources=${nearby.resources.length} hostiles=${nearby.hostiles.length} animals=${nearby.passiveAnimals.length} players=${nearby.players.length} containers=${nearby.containers.length} workstations=${nearby.workstations.length} hazards=${nearby.hazards.length}`,
  );
  const home = observation.home;
  lines.push(
    `  home     ${home.activeHome ? `${home.activeHome.homeId} at ${home.activeHome.position.x},${home.activeHome.position.y},${home.activeHome.position.z}` : "none"} distance=${home.homeDistance ?? "unknown"} shelter=${home.shelterState} storage=${home.ownedStorage.length} foodReserve=${home.foodReserve}`,
  );
  const navigation = observation.navigation;
  lines.push(
    `  route    ${navigation.routeStatus} risk=${navigation.pathRisk} stuck=${navigation.stuckState} returnKnown=${navigation.returnPathKnown}`,
  );
  const permitted = Object.entries(observation.permissions)
    .filter(([, allowed]) => allowed)
    .map(([name]) => name)
    .join(",");
  lines.push(`  allowed  ${permitted || "nothing"}`);
  lines.push(
    `  can      diggableGround=${observation.affordances.diggableGround} shelterSite=${observation.affordances.shelterSite} storageSite=${observation.affordances.storageSite}`,
  );
  return lines.join("\n");
}

export function renderFindings(
  result: ReturnType<typeof compareObservations>,
): string {
  if (result.findings.length === 0)
    return "No differences and nothing suspicious.";
  const lines = [
    `${result.findings.length} finding(s): ${result.structural} structural, ${result.suspicious} suspicious`,
  ];
  for (const finding of result.findings.slice(0, 80)) {
    const detail =
      finding.kind === "differs" && finding.expected !== undefined
        ? ` expected=${JSON.stringify(finding.expected)} actual=${JSON.stringify(finding.actual)}`
        : finding.actual !== undefined
          ? ` actual=${JSON.stringify(finding.actual)}`
          : "";
    lines.push(`  [${finding.kind}] ${finding.path || "/"}${detail}`);
    lines.push(`      ${finding.note}`);
  }
  if (result.findings.length > 80)
    lines.push(`  ... ${result.findings.length - 80} more`);
  return lines.join("\n");
}

export const resolveBase = (configPath: string): string =>
  path.dirname(path.resolve(configPath));
