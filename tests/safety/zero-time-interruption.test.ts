/**
 * The zero-time livelock found in the R2 held-out D run, and what replaced it.
 *
 * An unseen skeleton sat between the kernel's contact range (7) and a second,
 * skill-local threshold (8). `wait_safely` refused to wait, the kernel did not
 * take over, the fixture clock did not move, and Person re-proposed the same
 * wait forever. Safety now has one definition, the kernel's, and the fixture
 * world always moves on after an attempt that took no time and did not work.
 */
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { randomUUID } from "node:crypto";
import {
  PROTOCOL_VERSION,
  type Envelope,
  type MessageType,
  type Observation,
  type SkillInvocation,
} from "#protocol";
import { skillRegistry } from "#skills";
import {
  STALL_LIMIT,
  StallDetector,
  buildObservation,
  dispatchSkill,
  type DecisionRecord,
  type ExecutionResult,
  type SkillRunner,
} from "#node-runtime";
import { REPOSITORY, harness, type Harness } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

const NODE = process.execPath;
const SCRIPTED = path.join(REPOSITORY, "tests/support/scripted-cognition.ts");

// Yaw 0 faces negative Z: +Z is behind Person, -Z in front of it.
const world = {
  name: "zero-time",
  seed: 31,
  startTick: 0,
  timeOfDay: 1000,
  biome: "plains",
  groundLevel: 63,
  spawn: { x: 0, y: 64, z: 0 },
  spawnYaw: 0,
  vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
  inventory: [{ name: "bread", count: 4 }],
  blocks: [],
  clusters: [],
  entities: [],
  containers: [],
  events: [],
};

const behind = (d: number) => ({ x: 0, y: 64, z: d });
const inFront = (d: number) => ({ x: 0, y: 64, z: -d });

function observe(bench: Harness): Observation {
  return buildObservation({
    identity: {
      personId: bench.config.personId,
      sessionId: randomUUID(),
      worldId: bench.config.worldId,
    },
    snapshot: bench.world.snapshot(),
    permissions: bench.permissions,
    kernel: bench.kernel,
    ledger: bench.ledger,
    trainingContext: "fixture",
    cognition: {
      activeGoal: null,
      activeRoutine: null,
      activeSkill: null,
      suspendedGoals: [],
    },
    previousOutcome: null,
    blockAt: (position) => bench.world.blockAt(position),
  });
}

const SKILLS = [
  ["wait_safely", { ticks: 20 }],
  ["look_around", {}],
] as const;

test("look_around: an unseen hostile at 7 blocks is preempted by the kernel", async () => {
  const bench = await harness({ world });
  bench.world.spawn("zombie", behind(7));
  const result = await bench.run("look_around");
  assert.equal(result.status, "PREEMPTED");
  assert.ok(result.reasonCodes.includes("immediate_threat"));
});

test("wait_safely: an unseen hostile at 7 blocks ends the wait, and the kernel takes the next act", async () => {
  // wait_safely is an emergency skill, which the kernel does not preempt
  // mid-flight; it stops on the kernel's own definition of contact range, and
  // the kernel replaces whatever Person proposes next.
  const bench = await harness({ world });
  bench.world.spawn("zombie", behind(7));
  const result = await bench.run("wait_safely", { ticks: 20 });
  assert.equal(result.status, "INTERRUPTED");
  assert.ok(result.reasonCodes.includes("threat_appeared"));
  const verdict = bench.validator.validate(
    invocation("wait_safely"),
    bench.world.snapshot(),
  );
  assert.equal(verdict.decision, "REPLACE");
  assert.equal(verdict.level, "L1");
  assert.equal(verdict.executedSkill, "flee");
});

for (const [skill, parameters] of SKILLS) {
  test(`${skill}: an unseen hostile at 8 blocks does not refuse the act at 0 ticks`, async () => {
    const bench = await harness({ world });
    bench.world.spawn("zombie", behind(8));
    const result = await bench.run(skill, parameters);
    assert.ok(!result.reasonCodes.includes("threat_appeared"));
    assert.ok(result.elapsedTicks > 0, "time passed inside the act");
    // It may still end with the kernel taking over, once the zombie closes in.
    if (result.status !== "SUCCESS") {
      assert.equal(result.status, "PREEMPTED");
      assert.ok(result.reasonCodes.includes("immediate_threat"));
    }
  });

  test(`${skill}: an unseen hostile at 16 blocks lets the act complete`, async () => {
    const bench = await harness({ world });
    bench.world.spawn("zombie", behind(16));
    const result = await bench.run(skill, parameters);
    assert.equal(result.status, "SUCCESS");
  });

  test(`${skill}: seeing the hostile changes what Person knows, not what the body allows`, async () => {
    const seen = await harness({ world });
    seen.world.spawn("zombie", inFront(8));
    const unseen = await harness({ world });
    unseen.world.spawn("zombie", behind(8));
    assert.equal(observe(seen).nearby.hostiles.length, 1);
    assert.equal(observe(unseen).nearby.hostiles.length, 0);
    const a = await seen.run(skill, parameters);
    const b = await unseen.run(skill, parameters);
    assert.equal(a.status, b.status);
    assert.deepEqual(a.reasonCodes, b.reasonCodes);
    assert.equal(a.elapsedTicks, b.elapsedTicks);
  });
}

test("a wait that completes beside an unseen hostile says nothing about it", async () => {
  const bench = await harness({ world });
  bench.world.spawn("zombie", behind(16));
  const result = await bench.run("wait_safely", { ticks: 20 });
  assert.equal(result.status, "SUCCESS");
  const said = JSON.stringify({
    reasonCodes: result.reasonCodes,
    effects: result.effects,
    evidence: result.evidenceDetails,
  });
  assert.ok(!/zombie|hostile|threat/.test(said), said);
  assert.equal(observe(bench).nearby.hostiles.length, 0);
});

// ------------------------------------------------------------ fixture time

function invocation(skillId: string): SkillInvocation {
  const spec = skillRegistry().get(skillId);
  return {
    protocolVersion: PROTOCOL_VERSION,
    messageId: randomUUID(),
    personId: "ada",
    sessionId: randomUUID(),
    worldId: "test-world",
    tick: 0,
    timestamp: new Date().toISOString(),
    type: "SkillInvocation",
    decisionId: randomUUID(),
    goalId: "goal_idle",
    routineId: "r_test",
    routineStepIndex: 0,
    skillId,
    skillVersion: spec.version,
    parameters: skillRegistry().resolveParameters(skillId, {}),
    limits: { ...spec.costLimits },
  };
}

async function dispatchWith(
  bench: Harness,
  skillId: string,
  status: ExecutionResult["status"],
  elapsedTicks: number,
): Promise<number> {
  const before = bench.world.snapshot().tick;
  // The stub runs a real 20-tick wait to borrow a well-formed result, then
  // reports the status and duration under test.
  const runner = {
    run: async (): Promise<ExecutionResult> => {
      const now = bench.world.snapshot();
      return {
        ...(await bench.run("wait_safely", { ticks: 20 })),
        status,
        reasonCodes: status === "SUCCESS" ? [] : ["stub"],
        elapsedTicks,
        healthBefore: now.health,
        healthAfter: now.health,
      };
    },
  } as unknown as SkillRunner;
  await dispatchSkill(
    invocation(skillId),
    { goalId: "goal_idle", routineId: "r_test", contextId: "c_test" },
    {
      registry: skillRegistry(),
      validator: bench.validator,
      runner,
      embodiment: bench.world,
      envelope: (type: MessageType, tick: number) =>
        ({
          protocolVersion: PROTOCOL_VERSION,
          messageId: randomUUID(),
          personId: "ada",
          sessionId: randomUUID(),
          worldId: "test-world",
          tick,
          timestamp: new Date().toISOString(),
          type,
        }) as Envelope,
    },
  );
  return bench.world.snapshot().tick - before;
}

test("the fixture world moves on after an attempt interrupted before any time passed", async () => {
  const bench = await harness({ world });
  // 20 ticks for the borrowed wait, 1 for the progress floor.
  assert.equal(await dispatchWith(bench, "wait_safely", "INTERRUPTED", 0), 21);
});

test("the progress floor leaves zero-tick failures, successes and timed attempts alone", async () => {
  for (const [status, elapsed] of [
    ["FAILED", 0],
    ["UNREACHABLE", 0],
    ["SUCCESS", 0],
    ["INTERRUPTED", 5],
  ] as const) {
    const bench = await harness({ world });
    assert.equal(
      await dispatchWith(bench, "wait_safely", status, elapsed),
      20,
      `${status} after ${elapsed} ticks`,
    );
  }
});

// ------------------------------------------------------------ stall detector

function decision(overrides: Partial<DecisionRecord> = {}): DecisionRecord {
  return {
    tick: 100,
    goalId: "goal_maintain_reserves",
    requestedSkill: "deposit_owned_storage",
    executedSkill: "deposit_owned_storage",
    validation: "ACCEPT",
    status: "FAILED",
    requestedSkillStatus: "FAILED",
    elapsedTicks: 0,
    ...overrides,
  } as DecisionRecord;
}

test("the stall detector fires on the limit-th identical zero-time failure, not before", () => {
  const stall = new StallDetector();
  for (let n = 1; n < STALL_LIMIT; n++)
    assert.equal(stall.observe(decision()), false, `repeat ${n}`);
  assert.equal(stall.observe(decision()), true);
});

test("the stall detector resets on progress, success, or any difference", () => {
  for (const breaker of [
    decision({ elapsedTicks: 4 }),
    decision({ status: "SUCCESS" }),
    decision({ tick: 101 }),
    decision({ requestedSkill: "gather_wood" }),
  ]) {
    const stall = new StallDetector();
    for (let n = 1; n < STALL_LIMIT; n++) stall.observe(decision());
    assert.equal(stall.observe(breaker), false);
    assert.equal(stall.observe(decision()), false, "the count started over");
  }
});

// ---------------------------------------------------------------- episodes

test("an idle wait beside an unseen hostile never repeats at one tick, and the kernel still takes over", async () => {
  const { report } = await runEpisode({
    world: { ...world, entities: [{ name: "zombie", position: behind(8) }] },
    cognitionCommand: [NODE, SCRIPTED, "wait_safely", "--ticks=20"],
    maxDecisions: 8,
  });
  const ticks = report.decisions.map((d) => d.tick);
  assert.equal(new Set(ticks).size, ticks.length, `ticks ${ticks}`);
  assert.ok(
    report.decisions.every((d) => d.elapsedTicks > 0 || d.status === "SUCCESS"),
    "no zero-time failure",
  );
  assert.ok(report.safetyOverrides.length >= 1, "the kernel took over");
  assert.ok(
    report.decisions.some((d) => d.executedSkill === "flee" && d.emergency),
  );
});

test("the original held-out D world no longer freezes at its skeleton", async () => {
  // Regression only. Held-out D stays INVALID for R2; this run is not evidence.
  const { report } = await runEpisode({
    worldFile: "fixtures/worlds/benchmarks/heldout/d-setback.json",
    cognitionCommand: [NODE, SCRIPTED, "wait_safely", "--ticks=600"],
    maxDecisions: 24,
  });
  const atSpawn = report.decisions.filter((d) => d.tick === 6000).length;
  assert.ok(atSpawn <= 2, `${atSpawn} decisions at tick 6000`);
  const last = report.decisions.at(-1);
  assert.ok(last && last.tick > 6000, `ended at ${last?.tick}`);
});

test("an episode that repeats one zero-time failure ends as a runtime livelock", async () => {
  // Nothing to deposit and nowhere to deposit it: the failure takes no time
  // and, proposed again, finds the world exactly as it was.
  const { report } = await runEpisode({
    world,
    cognitionCommand: [NODE, SCRIPTED, "deposit_owned_storage"],
    maxDecisions: 40,
  });
  assert.equal(report.reason, "runtime_livelock");
  assert.equal(report.decisions.length, STALL_LIMIT);
  assert.ok(report.decisions.every((d) => d.status !== "SUCCESS"));
});
