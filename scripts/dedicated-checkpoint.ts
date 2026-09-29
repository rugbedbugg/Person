/**
 * Dedicated-server checkpoint probe (operator tooling, not Person).
 *
 * Drives the real Mineflayer adapter against a local 1.16.1 research server
 * and checks, with the operator's server console as the independent witness:
 *
 *   gaze      the adapter's `look` turns the body the server sees;
 *   threat    a hostile in view reaches cognition's observation, one behind
 *             Person or inside a closed box does not, and the safety kernel,
 *             reading the privileged snapshot, sees all three;
 *   leakage   no observation carries a coordinate, a facing or a handle.
 *
 * Observations are built exactly as `person observe` builds them. Console
 * commands (summon, fill, data get) are operator actions on the world and are
 * recorded as such; nothing they return is given to cognition. The summoned
 * zombie has no AI, so it never moves or attacks.
 *
 *   node scripts/dedicated-checkpoint.ts <config.toml> <server-dir> <out.json>
 */
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { loadConfig } from "#config";
import {
  PermissionGate,
  PlacementLedger,
  ProtectedAreas,
  SafetyKernel,
  buildObservation,
  type PhysicalGuard,
  type WorldSnapshot,
} from "#node-runtime";
import { protocolValidator, type Observation } from "#protocol";
import { createEmbodiment } from "../apps/cli/src/embodiment.ts";

const [configPath, serverDirectory, outFile] = process.argv.slice(2);
if (!configPath || !serverDirectory || !outFile) {
  process.stderr.write(
    "usage: node scripts/dedicated-checkpoint.ts <config> <server-dir> <out.json>\n",
  );
  process.exit(2);
}
const TAG = "person_probe";
const FORBIDDEN = new Set([
  "position",
  "x",
  "y",
  "z",
  "yaw",
  "pitch",
  "heading",
  "entityId",
  "uuid",
  "username",
  "homeDistance",
  "lastSafePosition",
]);

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const logFile = path.join(serverDirectory, "logs", "latest.log");
const operatorActions: string[] = [];

async function console_(command: string): Promise<string[]> {
  const before = readFileSync(logFile, "utf8").length;
  operatorActions.push(command);
  appendFileSync(path.join(serverDirectory, "console.fifo"), `${command}\n`);
  await sleep(700);
  return readFileSync(logFile, "utf8")
    .slice(before)
    .split("\n")
    .filter(Boolean);
}

async function serverRotation(username: string): Promise<[number, number]> {
  const lines = await console_(`data get entity ${username} Rotation`);
  const match = lines
    .map((line) => /entity data: \[(-?[\d.]+)f, (-?[\d.]+)f\]/.exec(line))
    .find(Boolean);
  if (!match) throw new Error(`no rotation reported: ${lines.join(" | ")}`);
  return [Number(match[1]), Number(match[2])];
}

function leaks(value: unknown, at = "observation"): string[] {
  if (Array.isArray(value))
    return value.flatMap((item, index) => leaks(item, `${at}[${index}]`));
  if (value && typeof value === "object")
    return Object.entries(value).flatMap(([key, item]) => [
      ...(FORBIDDEN.has(key) ? [`${at}.${key}`] : []),
      ...leaks(item, `${at}.${key}`),
    ]);
  return [];
}

const config = loadConfig(configPath);
const username = config.bot?.username ?? "PersonAda";
const embodiment = await createEmbodiment(config, path.dirname(configPath));
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

function observe(): {
  observation: Observation;
  snapshot: WorldSnapshot;
  valid: boolean;
} {
  const snapshot = embodiment.snapshot();
  const observation = buildObservation({
    identity: {
      personId: config.personId,
      sessionId: "00000000-0000-4000-8000-00000000c0de",
      worldId: config.worldId,
    },
    snapshot,
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
  return {
    observation,
    snapshot,
    valid: protocolValidator().validate(observation).valid,
  };
}

const results: Record<string, unknown> = {};
const failures: string[] = [];
const expect = (ok: boolean, what: string) => {
  if (!ok) failures.push(what);
};

embodiment.setGuard(guard);
await embodiment.connect();
try {
  await sleep(1500);
  await console_(`kill @e[tag=${TAG}]`);

  // ---- gaze: the adapter turns the head, and the server agrees ----------
  await embodiment.look("forward");
  await sleep(500);
  const start = await serverRotation(username);
  await embodiment.look("left");
  await embodiment.look("left");
  await sleep(500);
  const turned = await serverRotation(username);
  await embodiment.look("right");
  await embodiment.look("right");
  await sleep(500);
  const back = await serverRotation(username);
  const wrap = (degrees: number) =>
    ((((degrees + 180) % 360) + 360) % 360) - 180;
  const swing = Math.abs(wrap(turned[0] - start[0]));
  results["gaze"] = { start, turned, back, swingDegrees: swing };
  expect(Math.abs(swing - 90) < 1, "two left glances turn the body 90 degrees");
  expect(
    Math.abs(wrap(back[0] - start[0])) < 1,
    "two right glances turn it back",
  );

  // ---- threat in view, behind, and boxed in -------------------------------
  const here = embodiment.snapshot();
  const ahead = { x: -Math.sin(here.yaw), z: -Math.cos(here.yaw) };
  const at = (distance: number) => ({
    x: Math.floor(here.position.x + ahead.x * distance) + 0.5,
    y: Math.floor(here.position.y),
    z: Math.floor(here.position.z + ahead.z * distance) + 0.5,
  });
  const summon = async (spot: { x: number; y: number; z: number }) => {
    await console_(
      `summon zombie ${spot.x} ${spot.y} ${spot.z} {NoAI:1b,Silent:1b,PersistenceRequired:1b,Tags:["${TAG}"]}`,
    );
    for (let tries = 0; tries < 20; tries++) {
      const snapshot = embodiment.snapshot();
      if (snapshot.entities.some((entity) => entity.hostile)) return;
      await sleep(250);
    }
    throw new Error("the summoned zombie never reached the body's snapshot");
  };
  const probe = (name: string) => {
    const { observation, snapshot, valid } = observe();
    const record = {
      valid,
      observationVersion: observation.observationVersion,
      perceivedHostiles: observation.nearby.hostiles,
      kernelThreat: kernel.threatState(snapshot),
      hostilesInSnapshot: snapshot.entities.filter((entity) => entity.hostile)
        .length,
      leaks: leaks(observation),
    };
    results[name] = record;
    expect(valid, `${name}: observation is schema-valid`);
    expect(record.leaks.length === 0, `${name}: nothing privileged leaks`);
    return record;
  };

  const inView = at(5);
  await summon(inView);
  const seen = probe("threatInView");
  expect(seen.perceivedHostiles.length === 1, "a zombie in view is perceived");
  expect(seen.kernelThreat !== "none", "the kernel sees the zombie in view");
  await console_(`kill @e[tag=${TAG}]`);
  await sleep(800);

  const behind = { ...at(-5) };
  await summon(behind);
  const unseen = probe("threatBehind");
  expect(
    unseen.perceivedHostiles.length === 0,
    "a zombie behind is not perceived",
  );
  expect(
    unseen.kernelThreat !== "none",
    "the kernel still sees the zombie behind",
  );
  await console_(`kill @e[tag=${TAG}]`);
  await sleep(800);

  const boxed = at(6);
  const box = `${Math.floor(boxed.x) - 1} ${boxed.y} ${Math.floor(boxed.z) - 1} ${Math.floor(boxed.x) + 1} ${boxed.y + 3} ${Math.floor(boxed.z) + 1}`;
  await console_(`fill ${box} stone hollow`);
  await summon({ ...boxed, y: boxed.y + 1 });
  const hidden = probe("threatOccluded");
  expect(
    hidden.perceivedHostiles.length === 0,
    "a boxed-in zombie is not perceived",
  );
  expect(
    hidden.kernelThreat !== "none",
    "the kernel still sees the boxed-in zombie",
  );
  await console_(`kill @e[tag=${TAG}]`);
  await console_(`fill ${box} air`);
  await sleep(800);

  const clear = probe("afterCleanup");
  expect(clear.kernelThreat === "none", "no threat remains after cleanup");
} finally {
  await console_(`kill @e[tag=${TAG}]`).catch(() => []);
  await embodiment.disconnect();
}

const evidence = {
  probe: "dedicated-checkpoint",
  recordedAt: new Date().toISOString(),
  server: config.server ?? null,
  worldId: config.worldId,
  trainingContext: config.runtime.trainingContext,
  operatorActions,
  results,
  failures,
  passed: failures.length === 0,
};
writeFileSync(outFile, `${JSON.stringify(evidence, null, 2)}\n`);
process.stdout.write(
  `${evidence.passed ? "PASS" : "FAIL"}: ${failures.length ? failures.join("; ") : "all probe checks held"}\n`,
);
process.exit(evidence.passed ? 0 : 1);
