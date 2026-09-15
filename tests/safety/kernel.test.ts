import test from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { PROTOCOL_VERSION, type SkillInvocation } from "#protocol";
import { skillRegistry } from "#skills";
import { harness } from "../support/harness.ts";

const world = {
  name: "kernel",
  seed: 13,
  startTick: 0,
  timeOfDay: 1000,
  biome: "plains",
  groundLevel: 63,
  spawn: { x: 0, y: 64, z: 0 },
  vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
  inventory: [{ name: "oak_log", count: 24 }],
  blocks: [],
  clusters: [
    { name: "oak_log", center: { x: 8, y: 64, z: 0 }, count: 12, spread: 2 },
  ],
  entities: [],
  containers: [],
  events: [],
};

function invocation(
  skillId: string,
  parameters: Record<string, number | string | boolean> = {},
): SkillInvocation {
  const spec = skillRegistry().get(skillId);
  return {
    protocolVersion: PROTOCOL_VERSION,
    messageId: randomUUID(),
    personId: "ada",
    sessionId: randomUUID(),
    worldId: "test-world",
    tick: 1,
    timestamp: new Date().toISOString(),
    type: "SkillInvocation",
    decisionId: randomUUID(),
    goalId: "goal_secure_shelter",
    routineId: "r_test",
    routineStepIndex: 0,
    skillId,
    skillVersion: spec.version,
    parameters: skillRegistry().resolveParameters(skillId, parameters),
    limits: { ...spec.costLimits },
  };
}

test("a calm world accepts an ordinary proposal at L2", async () => {
  const bench = await harness({ world });
  const verdict = bench.validator.validate(
    invocation("gather_wood"),
    bench.world.snapshot(),
  );
  assert.equal(verdict.decision, "ACCEPT");
  assert.equal(verdict.level, "L2");
  assert.equal(verdict.executedSkill, "gather_wood");
});

test("an immediate threat replaces the proposal with flee at L1", async () => {
  const bench = await harness({ world });
  bench.world.spawn("zombie", { x: 3, y: 64, z: 0 });
  const verdict = bench.validator.validate(
    invocation("gather_wood"),
    bench.world.snapshot(),
  );
  assert.equal(verdict.decision, "REPLACE");
  assert.equal(verdict.level, "L1");
  assert.equal(verdict.executedSkill, "flee");
  assert.ok(verdict.reasonCodes.includes("immediate_threat"));
});

test("a hostile swarm digs in rather than running", async () => {
  const bench = await harness({ world });
  for (const offset of [2, 3, 4])
    bench.world.spawn("zombie", { x: offset, y: 64, z: 1 });
  const verdict = bench.validator.validate(
    invocation("gather_wood"),
    bench.world.snapshot(),
  );
  assert.equal(verdict.decision, "REPLACE");
  assert.equal(verdict.executedSkill, "dig_in");
  assert.ok(verdict.reasonCodes.includes("hostile_swarm"));
});

test("critical hunger with food available replaces with eat_to_target", async () => {
  const bench = await harness({
    world: { ...world, inventory: [{ name: "cooked_beef", count: 2 }] },
  });
  bench.world.setVitals({ food: 4 });
  const verdict = bench.validator.validate(
    invocation("gather_wood"),
    bench.world.snapshot(),
  );
  assert.equal(verdict.decision, "REPLACE");
  assert.equal(verdict.executedSkill, "eat_to_target");
  assert.ok(verdict.reasonCodes.includes("critical_hunger"));
});

test("a proposal that already matches the emergency is accepted, not replaced", async () => {
  const bench = await harness({ world });
  bench.world.spawn("zombie", { x: 3, y: 64, z: 0 });
  const verdict = bench.validator.validate(
    invocation("flee"),
    bench.world.snapshot(),
  );
  assert.equal(verdict.decision, "ACCEPT");
  assert.equal(verdict.level, "L1");
  assert.ok(verdict.reasonCodes.includes("proposal_matched_emergency"));
});

test("unknown skills, wrong versions and bad parameters are rejected", async () => {
  const bench = await harness({ world });
  const snapshot = bench.world.snapshot();
  const unknown = { ...invocation("gather_wood"), skillId: "teleport_home" };
  assert.equal(bench.validator.validate(unknown, snapshot).decision, "REJECT");
  assert.ok(
    bench.validator
      .validate(unknown, snapshot)
      .reasonCodes.includes("unknown_skill"),
  );

  const wrongVersion = { ...invocation("gather_wood"), skillVersion: 99 };
  assert.ok(
    bench.validator
      .validate(wrongVersion, snapshot)
      .reasonCodes.includes("skill_version_mismatch"),
  );

  const badParameters = {
    ...invocation("gather_wood"),
    parameters: { target_amount: 9999, max_distance: 48 },
  };
  const verdict = bench.validator.validate(badParameters, snapshot);
  assert.equal(verdict.decision, "REJECT");
  assert.ok(verdict.reasonCodes.includes("invalid_parameters"));
});

test("limits are clamped down to the skill contract, never up", async () => {
  const bench = await harness({ world });
  const greedy = {
    ...invocation("gather_wood"),
    limits: { maxTicks: 70000, maxDistance: 250, minHealth: 0 },
  };
  const verdict = bench.validator.validate(greedy, bench.world.snapshot());
  assert.equal(verdict.decision, "ACCEPT");
  assert.ok(verdict.reasonCodes.includes("limits_clamped_to_spec"));
  const spec = skillRegistry().get("gather_wood");
  assert.equal(verdict.executedLimits?.maxTicks, spec.costLimits.maxTicks);
  assert.equal(
    verdict.executedLimits?.maxDistance,
    spec.costLimits.maxDistance,
  );
  assert.ok(
    (verdict.executedLimits?.minHealth ?? 0) >= spec.costLimits.minHealth,
  );
});

test("the emergency assessment is deterministic for the same world", async () => {
  const bench = await harness({ world });
  bench.world.spawn("zombie", { x: 3, y: 64, z: 0 });
  const snapshot = bench.world.snapshot();
  const first = bench.kernel.assess(snapshot);
  for (let repeat = 0; repeat < 20; repeat++)
    assert.deepEqual(bench.kernel.assess(snapshot), first);
});

test("the safe exploration envelope closes when anything is wrong", async () => {
  const bench = await harness({ world });
  assert.equal(bench.kernel.safeEnvelope(bench.world.snapshot()), true);
  bench.world.setVitals({ health: 10 });
  assert.equal(bench.kernel.safeEnvelope(bench.world.snapshot()), false);
  bench.world.setVitals({ health: 20, food: 8 });
  assert.equal(bench.kernel.safeEnvelope(bench.world.snapshot()), false);
  bench.world.setVitals({ food: 20 });
  bench.world.spawn("zombie", { x: 4, y: 64, z: 0 });
  assert.equal(bench.kernel.safeEnvelope(bench.world.snapshot()), false);
});
