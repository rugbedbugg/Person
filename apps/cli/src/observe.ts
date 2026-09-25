import { randomUUID } from "node:crypto";
import path from "node:path";
import type { PersonConfig } from "#config";
import type { Observation } from "#protocol";
import { protocolValidator } from "#protocol";
import { distance } from "#config";
import {
  PermissionGate,
  ProtectedAreas,
  SafetyKernel,
  StatusWriter,
  PlacementLedger,
  buildObservation,
  statusPath,
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
export interface CaptureOptions {
  operatorIntervention?: { reason?: string };
  /** How long to allow for a clean disconnect before giving up on it. */
  disconnectTimeoutMs?: number;
  /**
   * A body to use instead of building one from configuration.
   *
   * Exists so a test can watch every call this function makes and prove it
   * only ever looks. Production always leaves it unset.
   */
  embodiment?: Embodiment;
}

export async function captureObservation(
  config: PersonConfig,
  baseDirectory: string,
  options: CaptureOptions = {},
): Promise<{
  observation: Observation;
  valid: boolean;
  diagnostics: string[];
}> {
  const sessionId = randomUUID();
  const status = new StatusWriter(
    statusPath(config.runtime.outputDirectory, config.worldId, config.personId),
    {
      command: "observe",
      connection: "connecting",
      readiness: "connecting",
      personId: config.personId,
      botUsername: config.bot?.username ?? null,
      worldId: config.worldId,
      sessionId,
      server: config.server ?? null,
      embodiment: config.runtime.embodiment,
      trainingContext: config.runtime.trainingContext,
      learningMode: config.learning.mode,
      operatorIntervention: {
        flagged: options.operatorIntervention !== undefined,
        reason: options.operatorIntervention?.reason ?? null,
      },
    },
  );
  const embodiment: Embodiment =
    options.embodiment ?? (await createEmbodiment(config, baseDirectory));
  const areas = new ProtectedAreas(config);
  const permissions = new PermissionGate(config, areas);
  const kernel = new SafetyKernel(permissions);
  const ledger = PlacementLedger.load(
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
  try {
    // Inside the try: installing the guard is the first thing that touches the
    // body, and a failure there should be reported like any other.
    embodiment.setGuard(guard);
    await embodiment.connect();
    status.update({ connection: "ready", readiness: "world ready" });
    const observation = buildObservation({
      identity: {
        personId: config.personId,
        sessionId,
        worldId: config.worldId,
      },
      snapshot: embodiment.snapshot(),
      permissions,
      kernel,
      ledger,
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
    const snapshot = embodiment.snapshot();
    status.update({
      tick: snapshot.tick,
      dimension: snapshot.dimension,
      position: snapshot.position,
      health: snapshot.health,
      food: snapshot.food,
      lastSafePosition: snapshot.lastSafePosition,
      home: {
        position: ledger.home.position,
        distance: distance(snapshot.position, ledger.home.position),
        shelterState: ledger.home.shelterState,
      },
      safety: {
        threat: kernel.threatState(snapshot),
        emergencies: 0,
        lastEmergency: null,
      },
      readiness: result.valid
        ? "observation captured"
        : "observation rejected by schema",
    });
    return {
      observation,
      valid: result.valid,
      diagnostics: result.diagnostics,
    };
  } catch (error) {
    const failure = error as { reason?: string; hint?: string | null };
    status.update({
      connection: "failed",
      readiness: "stopped",
      failureReason: failure.reason ?? "unknown_error",
      failureHint: failure.hint ?? null,
    });
    throw error;
  } finally {
    // A hung quit must not hold the command open. The process has to end even
    // when the server has stopped answering.
    const timeout = options.disconnectTimeoutMs ?? 10000;
    let timer: NodeJS.Timeout | undefined;
    await Promise.race([
      embodiment.disconnect(),
      new Promise<void>((resolve) => {
        timer = setTimeout(resolve, timeout);
      }),
    ]).finally(() => {
      if (timer) clearTimeout(timer);
    });
    status.update({
      connection:
        status.status.connection === "failed" ? "failed" : "disconnected",
      readiness: "stopped",
    });
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
  const nearest = <T extends { distance: number }>(
    items: T[],
    limit = 3,
  ): T[] => [...items].sort((a, b) => a.distance - b.distance).slice(0, limit);
  const away = (distance: number): string => `${distance.toFixed(1)}m`;

  lines.push(
    `Observation v${observation.observationVersion} (${observation.trainingContext})`,
  );
  lines.push(
    `  vitals    health=${vitals.health} food=${vitals.food} saturation=${vitals.saturation} air=${vitals.air} armor=${vitals.armor} alive=${vitals.alive}`,
  );
  if (vitals.statusEffects.length)
    lines.push(
      `  effects   ${vitals.statusEffects.map((effect) => `${effect.name}+${effect.amplifier}`).join(" ")}`,
    );
  lines.push(
    `  world     ${environment.dimension} ${environment.dayPhase} time=${environment.timeOfDay} weather=${environment.weather} light=${environment.lightLevel} biome=${environment.biome}`,
  );

  const categories = Object.entries(observation.inventory.categories)
    .filter(([, count]) => count > 0)
    .map(([name, count]) => `${name}=${count}`)
    .join(" ");
  lines.push(
    `  inventory ${observation.inventory.items.length} stacks, ${observation.inventory.freeSlots} free slots${categories ? ` (${categories})` : ""}`,
  );
  if (observation.inventory.items.length)
    lines.push(
      `            ${observation.inventory.items
        .map((item) => `${item.name}x${item.count}`)
        .slice(0, 10)
        .join(" ")}`,
    );

  const nearby = observation.nearby;
  lines.push("  nearby");
  // The category breakdown is the point of a balanced search: a run that finds
  // sixty-four of one thing is reporting a perception failure, not a forest.
  const perKind = new Map<string, number>();
  for (const resource of nearby.resources)
    perKind.set(resource.kind, (perKind.get(resource.kind) ?? 0) + 1);
  const breakdown = [...perKind]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([kind, count]) => `${kind} ${count}`)
    .join(", ");
  lines.push(
    `    resources    ${nearby.resources.length}${breakdown ? ` (${breakdown})` : ""}${
      nearby.resources.length
        ? `: ${nearest(nearby.resources)
            .map(
              (resource) =>
                `${resource.name} ${away(resource.distance)}${resource.harvestPermitted ? "" : " (not permitted)"}`,
            )
            .join(", ")}`
        : ""
    }`,
  );
  lines.push(
    `    animals      ${nearby.passiveAnimals.length}${
      nearby.passiveAnimals.length
        ? `: ${nearest(nearby.passiveAnimals)
            .map(
              (animal) =>
                `${animal.name} ${away(animal.distance)}${animal.protectedTarget ? " (protected)" : ""}`,
            )
            .join(", ")}`
        : ""
    }`,
  );
  lines.push(
    `    threats      ${nearby.hostiles.length}${
      nearby.hostiles.length
        ? `: ${nearest(nearby.hostiles)
            .map((hostile) => `${hostile.name} ${away(hostile.distance)}`)
            .join(", ")}`
        : ""
    }`,
  );
  lines.push(
    `    players      ${nearby.players.length}${
      nearby.players.length
        ? `: ${nearest(nearby.players)
            .map(
              (player) =>
                `${player.username ?? player.name} ${away(player.distance)}`,
            )
            .join(", ")}`
        : ""
    }`,
  );
  lines.push(
    `    containers   ${nearby.containers.length}${
      nearby.containers.length
        ? `: ${nearest(nearby.containers)
            .map(
              (container) =>
                `${container.kind} ${away(container.distance)} (${container.provenance})`,
            )
            .join(", ")}`
        : ""
    }`,
  );
  lines.push(
    `    workstations ${nearby.workstations.length}${
      nearby.workstations.length
        ? `: ${nearest(nearby.workstations)
            .map(
              (station) =>
                `${station.kind} ${away(station.distance)} (${station.provenance})`,
            )
            .join(", ")}`
        : ""
    }`,
  );
  lines.push(
    `    hazards      ${nearby.hazards.length}${
      nearby.hazards.length
        ? `: ${nearest(nearby.hazards)
            .map((hazard) => `${hazard.kind} ${away(hazard.distance)}`)
            .join(", ")}`
        : ""
    }`,
  );

  const home = observation.home;
  lines.push(
    `  home      ${
      home.activeHome ? home.activeHome.homeId : "none"
    } shelter=${home.shelterState} storage=${home.ownedStorage.length} foodReserve=${home.foodReserve} fuelReserve=${home.fuelReserve} bed=${home.bedKnown}`,
  );
  const navigation = observation.navigation;
  lines.push(
    `  route     ${navigation.routeStatus} risk=${navigation.pathRisk} stuck=${navigation.stuckState} returnKnown=${navigation.returnPathKnown}`,
  );
  const permitted = Object.entries(observation.permissions)
    .filter(([, allowed]) => allowed)
    .map(([name]) => name)
    .join(",");
  const refused = Object.entries(observation.permissions)
    .filter(([, allowed]) => !allowed)
    .map(([name]) => name)
    .join(",");
  lines.push(`  allowed   ${permitted || "nothing"}`);
  if (refused) lines.push(`  refused   ${refused}`);
  lines.push(
    `  can       diggableGround=${observation.affordances.diggableGround} shelterSite=${observation.affordances.shelterSite} storageSite=${observation.affordances.storageSite}`,
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
