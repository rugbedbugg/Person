import test from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import type { Observation } from "#protocol";
import { VISION, buildObservation, canSee, eyePose } from "#node-runtime";
import { harness, type Harness } from "../support/harness.ts";

/**
 * What Person can and cannot see.
 *
 * The cases here are the ones that decide whether perception is a sense or a
 * database query: something behind Person, something through a wall, and
 * something too far off must all be absent from what cognition is told, while
 * the runtime goes on knowing about every one of them.
 *
 * Deterministic and offline. This proves the geometry, not Minecraft.
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

const animals = (observation: Observation): string[] =>
  observation.nearby.passiveAnimals.map((animal) => animal.name);

test("an animal in front and unobstructed is perceived", async () => {
  const bench = await harness();
  const spot = { x: 0, y: 64, z: -6 };
  bench.world.spawn("cow", spot);
  bench.world.face(spot);

  assert.ok(animals(observe(bench)).includes("cow"));
});

test("an animal behind Person is not perceived, but the runtime knows", async () => {
  const bench = await harness();
  const spot = { x: 0, y: 64, z: -6 };
  bench.world.spawn("cow", spot);
  bench.world.face({ x: 0, y: 64, z: 6 });

  assert.ok(!animals(observe(bench)).includes("cow"), "it is behind Person");
  assert.ok(
    bench.world.snapshot().entities.some((entity) => entity.name === "cow"),
    "the privileged snapshot still has it",
  );
});

test("turning towards an animal is what makes it perceptible", async () => {
  const bench = await harness();
  const spot = { x: 0, y: 64, z: -6 };
  bench.world.spawn("cow", spot);

  bench.world.face({ x: 0, y: 64, z: 6 });
  assert.ok(!animals(observe(bench)).includes("cow"));

  bench.world.face(spot);
  assert.ok(animals(observe(bench)).includes("cow"), "turning reveals it");
});

test("an animal beyond visual range is not perceived", async () => {
  const bench = await harness();
  const far = { x: 0, y: 64, z: -(VISION.range + 8) };
  bench.world.spawn("cow", far);
  bench.world.face(far);

  assert.ok(!animals(observe(bench)).includes("cow"));
  assert.ok(
    bench.world.snapshot().entities.some((entity) => entity.name === "cow"),
    "the runtime still knows about it",
  );
});

test("an animal behind an opaque wall is not perceived", async () => {
  const bench = await harness();
  const spot = { x: 0, y: 64, z: -6 };
  bench.world.spawn("cow", spot);
  bench.world.face(spot);
  assert.ok(animals(observe(bench)).includes("cow"), "visible to begin with");

  // A wall across the line of sight, tall enough to cover the eye line.
  for (let x = -2; x <= 2; x++)
    for (let y = 64; y <= 66; y++)
      bench.world.setBlock({ x, y, z: -3 }, "stone");

  assert.ok(!animals(observe(bench)).includes("cow"), "the wall hides it");
  assert.ok(
    bench.world.snapshot().entities.some((entity) => entity.name === "cow"),
    "the runtime still knows about it",
  );
});

test("a nearer obstruction hides the farther of two targets", async () => {
  const bench = await harness();
  const near = { x: 0, y: 64, z: -4 };
  const far = { x: 0, y: 64, z: -10 };
  bench.world.face(far);
  // A solid pillar between the two, on the same line.
  for (let y = 64; y <= 66; y++)
    bench.world.setBlock({ x: 0, y, z: -7 }, "stone");

  const pose = eyePose(bench.world.snapshot());
  const sees = (at: { x: number; y: number; z: number }): boolean =>
    canSee(pose, at, (position) => bench.world.blockAt(position));

  assert.ok(sees(near), "the near square is in plain view");
  assert.ok(!sees(far), "the far one is behind the pillar");
});

test("the field of view has an edge, and it excludes the rear", async () => {
  const bench = await harness();
  const pose = eyePose({ position: { x: 0, y: 64, z: 0 }, yaw: 0, pitch: 0 });
  const clear = (): null => null;
  // yaw 0 faces negative Z.
  assert.ok(canSee(pose, { x: 0, y: 64, z: -8 }, clear), "straight ahead");
  assert.ok(canSee(pose, { x: 8, y: 64, z: -1 }, clear), "off to one side");
  assert.ok(!canSee(pose, { x: 0, y: 64, z: 8 }, clear), "directly behind");
  assert.ok(
    !canSee(pose, { x: 2, y: 64, z: 8 }, clear),
    "behind and to a side",
  );
});

test("the physical world holds things the perceptual one does not", async () => {
  const bench = await harness();
  bench.world.spawn("cow", { x: 0, y: 64, z: -6 });
  bench.world.spawn("pig", { x: 0, y: 64, z: 6 });
  bench.world.face({ x: 0, y: 64, z: -6 });

  const perceived = animals(observe(bench));
  const actual = bench.world
    .snapshot()
    .entities.map((entity) => entity.name)
    .filter((name) => name === "cow" || name === "pig");

  assert.deepEqual(
    perceived.filter((name) => name === "pig"),
    [],
  );
  assert.ok(actual.includes("pig"), "the pig is physically there");
  assert.ok(
    perceived.length < actual.length,
    "perception is a strict subset of what exists",
  );
});
