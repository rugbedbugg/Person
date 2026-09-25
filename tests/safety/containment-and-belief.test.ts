import test from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { SelfMotionSense, buildObservation } from "#node-runtime";
import { harness, type Harness } from "../support/harness.ts";

/**
 * Cognitive belief is not capability authority (C8).
 *
 * The runtime keeps exact physical position and enforces containment on it.
 * Person keeps a fallible belief about where it is. Neither may leak into
 * the other: what Person believes cannot relax or tighten enforcement, and a
 * physical change that enforcement reacts to reaches Person only as what its
 * body felt.
 *
 * Deterministic and offline. The Python suite proves the belief half.
 */

function observe(
  bench: Harness,
  sense: SelfMotionSense,
  activeGoal: string | null,
) {
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
      activeGoal,
      activeRoutine: null,
      activeSkill: null,
      suspendedGoals: [],
    },
    previousOutcome: null,
    blockAt: (position) => bench.world.blockAt(position),
    selfMotion: sense.sense(bench.world.snapshot()),
  });
}

test("no home distance reaches cognition", async () => {
  const bench = await harness();
  await bench.world.connect();
  bench.world.teleport({ x: 10, y: 64, z: 7 });
  const observation = observe(bench, new SelfMotionSense(), null);
  assert.ok(!("homeDistance" in observation.home));
  assert.ok(!JSON.stringify(observation).includes("homeDistance"));
});

test("a push across a containment boundary is enforced, and only felt by Person", async () => {
  // The default harness protects x 20..28, z 20..28.
  const bench = await harness();
  await bench.world.connect();
  const sense = new SelfMotionSense();
  bench.world.teleport({ x: 18, y: 64, z: 24 });
  observe(bench, sense, null);
  assert.equal(bench.kernel.assess(bench.world.snapshot()), null);

  bench.world.pass(20);
  bench.world.teleport({ x: 22, y: 64, z: 24 });
  const verdict = bench.kernel.assess(bench.world.snapshot());
  assert.equal(verdict?.trigger, "protected_area_entry", "enforcement reacts");

  const felt = observe(bench, sense, null);
  assert.equal(felt.selfMotion.continuity, "continuous");
  assert.equal(felt.selfMotion.translation.band, "short", "Person felt a push");
  const serialized = JSON.stringify(felt);
  for (const leaked of ['"x"', '"z"', "protected_area", "boundary"])
    assert.ok(!serialized.includes(leaked), `${leaked} reached cognition`);
  // Nor the body's coordinates as bare numbers (identifiers are strings).
  assert.ok(!/[:,\[]\s*(22|24)(\.0+)?\s*[,}\]]/.test(serialized));
});

test("what cognition is doing or believes changes no enforcement", async () => {
  const bench = await harness();
  await bench.world.connect();
  bench.world.teleport({ x: 22, y: 64, z: 24 });
  const before = bench.kernel.assess(bench.world.snapshot());
  // The only way cognition's state enters the runtime is as a report inside
  // the observation. Build observations with different cognitive states and
  // confirm the verdict is unmoved: the kernel reads the body, not the mind.
  observe(bench, new SelfMotionSense(), "goal_recover_home");
  observe(bench, new SelfMotionSense(), "goal_secure_shelter");
  assert.deepEqual(bench.kernel.assess(bench.world.snapshot()), before);
  assert.equal(
    bench.kernel.assess.length,
    1,
    "the kernel takes the snapshot only",
  );
});
