import test from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import {
  PROTOCOL_VERSION,
  type Observation,
  type SkillInvocation,
} from "#protocol";
import { skillRegistry } from "#skills";
import { GAZE_DIRECTIONS, buildObservation } from "#node-runtime";
import { harness, type Harness } from "../support/harness.ts";

/**
 * `look`: one deliberate glance, and Person stays looking that way.
 *
 * `look_around` sweeps and comes back, so nothing it passes reaches cognition.
 * Looking for something needs the opposite: turn, and let the next ordinary
 * observation be taken from there. These tests pin the motor half of that loop
 * and its boundary. The planner half is in the cognition tests.
 *
 * Deterministic and offline. Nothing here is live Minecraft evidence.
 */

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
    memory: bench.memory,
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

function invocation(parameters: Record<string, unknown>): SkillInvocation {
  const spec = skillRegistry().get("look");
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
    routineId: "r_seek_evidence",
    routineStepIndex: 0,
    skillId: "look",
    skillVersion: spec.version,
    parameters: parameters as SkillInvocation["parameters"],
    limits: { ...spec.costLimits },
  };
}

test("look takes one closed word and nothing that could be a place", () => {
  const spec = skillRegistry().get("look");
  assert.deepEqual(Object.keys(spec.parameters), ["direction"]);
  assert.deepEqual(
    [...(spec.parameters["direction"]?.enum ?? [])].sort(),
    [...GAZE_DIRECTIONS].sort(),
    "the skill's vocabulary is exactly the gaze vocabulary",
  );
  assert.deepEqual(spec.requiredPermissions, []);
  assert.equal(spec.costLimits.maxDistance, 0, "looking is not travelling");
});

test("the validator refuses anything outside the vocabulary", async () => {
  const bench = await harness();
  const snapshot = bench.world.snapshot();

  for (const direction of GAZE_DIRECTIONS)
    assert.equal(
      bench.validator.validate(invocation({ direction }), snapshot).decision,
      "ACCEPT",
      direction,
    );
  for (const parameters of [
    { direction: "north" },
    { direction: 90 },
    { direction: "left", yaw: 1.5 },
    { direction: "left", x: 12 },
  ])
    assert.equal(
      bench.validator.validate(invocation(parameters), snapshot).decision,
      "REJECT",
      JSON.stringify(parameters),
    );
});

test("a glance leaves Person facing the new way, unlike a sweep", async () => {
  const bench = await harness();
  bench.world.turn(0);
  // Behind Person to begin with.
  bench.world.spawn("cow", { x: 0, y: 64, z: 8 });
  assert.equal(observe(bench).nearby.passiveAnimals.length, 0);

  // Four glances, each an ordinary skill, and each a separate observation.
  const seen: string[] = [];
  for (let glance = 0; glance < 4; glance++) {
    const result = await bench.run("look", { direction: "left" });
    assert.equal(result.status, "SUCCESS");
    const animals = observe(bench).nearby.passiveAnimals;
    seen.push(animals.map((animal) => animal.detail).join(",") || "nothing");
  }

  assert.deepEqual(seen, ["nothing", "peripheral", "peripheral", "central"]);
  const [cow] = observe(bench).nearby.passiveAnimals;
  assert.equal(cow?.name, "cow", "recognised only once it is looked at");
});

test("a bearing and a glance agree about which side is which", async () => {
  // The planner turns towards a glimpse using the glimpse's bearing. If the
  // observation's "left" were the body's "right", every such turn would be
  // away from the thing. Found while building information seeking: Phase 3
  // reported every left/right bearing mirrored, and nothing read them yet.
  for (const [side, x] of [
    ["right", 12],
    ["left", -12],
  ] as const) {
    const bench = await harness();
    bench.world.turn(0);
    bench.world.spawn("cow", { x, y: 64, z: -2 });

    const [glimpse] = observe(bench).nearby.passiveAnimals;
    assert.equal(glimpse?.detail, "peripheral");
    assert.equal(
      glimpse?.bearing,
      side,
      `a cow on the ${side} is on the ${side}`,
    );

    await bench.run("look", { direction: side });
    await bench.run("look", { direction: side });
    assert.equal(observe(bench).nearby.passiveAnimals[0]?.bearing, "ahead");
  }
});

test("a glance reports that it happened and nothing about what it saw", async () => {
  const bench = await harness();
  bench.world.spawn("cow", { x: 0, y: 64, z: 8 });
  const result = await bench.run("look", { direction: "right" });
  const serialized = JSON.stringify(result);

  assert.ok(result.effects.includes("looked"));
  for (const field of ["yaw", "pitch", "heading", "cow", "position"])
    assert.ok(!serialized.includes(`"${field}`), `${field} must not appear`);
});
