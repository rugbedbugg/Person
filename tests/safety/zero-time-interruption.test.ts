/**
 * The zero-time livelock found in the R2 held-out D run, and what replaced it.
 *
 * An unseen skeleton sat between the kernel's contact range (7) and a second,
 * skill-local threshold (8). `wait_safely` refused to wait, the kernel did not
 * take over, the fixture clock did not move, and Person re-proposed the same
 * wait forever. Safety now has one definition, the kernel's; the fixture
 * moves on one tick after a zero-time interruption or zero-time failure under
 * runtime control; and a repeated zero-time failure ends the episode.
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
  runtimeTookControl,
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

type Reply = Pick<ExecutionResult, "status" | "elapsedTicks"> & {
  preempted?: boolean;
};

/** A runner that reports what it is told to, and never moves the world. */
function scripted(bench: Harness, replies: Reply[]): SkillRunner {
  const queue = [...replies];
  return {
    run: async (request: { skillId: string }): Promise<ExecutionResult> => {
      const reply = queue.shift() ?? { status: "SUCCESS", elapsedTicks: 0 };
      const now = bench.world.snapshot();
      return {
        skillId: request.skillId,
        status: reply.status,
        reasonCodes: reply.status === "SUCCESS" ? [] : ["stub"],
        effects: [],
        evidenceKinds: ["elapsed_ticks"],
        evidenceDetails: {},
        elapsedTicks: reply.elapsedTicks,
        healthBefore: now.health,
        healthAfter: now.health,
        foodBefore: now.food,
        foodAfter: now.food,
        inventoryBefore: now.inventory,
        inventoryAfter: now.inventory,
        inventoryDelta: [],
        preemption: reply.preempted
          ? (bench.kernel.assess(now) ?? {
              level: "L1",
              trigger: "immediate_threat",
              action: "flee",
              reasonCodes: ["stub"],
            })
          : null,
        timings: {
          navigationTicks: 0,
          interactionTicks: 0,
          waitingTicks: 0,
        },
        budgetPressure: 0,
      } as unknown as ExecutionResult;
    },
  } as unknown as SkillRunner;
}

/** Ticks the world moved during one dispatch, and the validator's verdict. */
async function dispatchWith(
  bench: Harness,
  skillId: string,
  replies: Reply[],
): Promise<{ moved: number; decision: string; runtime: boolean }> {
  const before = bench.world.snapshot().tick;
  const dispatched = await dispatchSkill(
    invocation(skillId),
    { goalId: "goal_idle", routineId: "r_test", contextId: "c_test" },
    {
      registry: skillRegistry(),
      validator: bench.validator,
      runner: scripted(bench, replies),
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
  return {
    moved: bench.world.snapshot().tick - before,
    decision: dispatched.verdict.decision,
    runtime: runtimeTookControl(dispatched.verdict, dispatched.result),
  };
}

test("the fixture world moves on after an attempt interrupted before any time passed", async () => {
  const bench = await harness({ world });
  const { moved } = await dispatchWith(bench, "wait_safely", [
    { status: "INTERRUPTED", elapsedTicks: 0 },
  ]);
  assert.equal(moved, 1);
});

test("Person's own zero-tick failures, successes and timed attempts do not move the world", async () => {
  for (const reply of [
    { status: "FAILED", elapsedTicks: 0 },
    { status: "UNREACHABLE", elapsedTicks: 0 },
    { status: "SUCCESS", elapsedTicks: 0 },
    { status: "INTERRUPTED", elapsedTicks: 5 },
  ] as const) {
    const bench = await harness({ world });
    const result = await dispatchWith(bench, "wait_safely", [reply]);
    assert.equal(result.runtime, false);
    assert.equal(
      result.moved,
      0,
      `${reply.status} after ${reply.elapsedTicks}`,
    );
  }
});

test("a kernel replacement that fails at 0 ticks moves the world one tick", async () => {
  // Held-out D, after the first fix: the kernel replaces an idle wait with
  // flee, and flee finds no route that increases clearance.
  const bench = await harness({ world });
  bench.world.spawn("skeleton", behind(5));
  const result = await dispatchWith(bench, "wait_safely", [
    { status: "FAILED", elapsedTicks: 0 },
  ]);
  assert.equal(result.decision, "REPLACE");
  assert.equal(result.runtime, true);
  assert.equal(result.moved, 1);
});

test("a preemption whose emergency skill does not succeed at 0 ticks moves the world one tick", async () => {
  const bench = await harness({ world });
  const result = await dispatchWith(bench, "gather_wood", [
    { status: "PREEMPTED", elapsedTicks: 0, preempted: true },
    { status: "UNREACHABLE", elapsedTicks: 0 },
  ]);
  assert.equal(result.decision, "ACCEPT");
  assert.equal(result.runtime, true);
  assert.equal(result.moved, 1);
});

test("runtime control means replacement or preemption, not an emergency-type skill", async () => {
  // wait_safely is an emergency skill; Person proposing it in a calm world is
  // still Person's decision.
  const bench = await harness({ world });
  const result = await dispatchWith(bench, "wait_safely", [
    { status: "FAILED", elapsedTicks: 0 },
  ]);
  assert.equal(result.decision, "ACCEPT");
  assert.equal(result.runtime, false);
  // And Person proposing exactly what the emergency calls for is Person's too.
  const threatened = await harness({ world });
  threatened.world.spawn("zombie", behind(5));
  const matched = await dispatchWith(threatened, "flee", [
    { status: "FAILED", elapsedTicks: 0 },
  ]);
  assert.equal(matched.decision, "ACCEPT");
  assert.equal(matched.runtime, false);
  assert.equal(matched.moved, 0);
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
    maxDecisions: 40,
  });
  assert.notEqual(report.reason, "runtime_livelock");
  const ticks = report.decisions.map((d) => d.tick);
  const most = Math.max(
    ...[...new Set(ticks)].map((t) => ticks.filter((u) => u === t).length),
  );
  assert.ok(most <= 2, `${most} decisions at one tick`);
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
