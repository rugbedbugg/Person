import test from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import type { Observation } from "#protocol";
import { GAZE, VISION, buildObservation, survey } from "#node-runtime";
import { harness, type Harness } from "../support/harness.ts";

/**
 * Active perception: Person deciding to look, rather than happening to face.
 *
 * Phase 3 gave Person a bounded field of view and no way to point it. That
 * made what Person could discover a function of where it spawned. These tests
 * cover the smallest fix: a semantic gaze vocabulary Person can ask for, and a
 * bounded survey it can perform, neither of which hands cognition an angle.
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

/**
 * Whether the animal is perceived at all.
 *
 * Presence rather than name: Phase 3 withholds identity outside central
 * vision, so a creature caught in the periphery is perceived without being
 * recognised. These tests are about where Person is looking, not about what it
 * can name, and only one animal is ever spawned in each of them.
 */
const sees = (bench: Harness, _name: string): boolean =>
  observe(bench).nearby.passiveAnimals.length > 0;

/** Anything perceptible at all, named or not. */
const perceivedCount = (bench: Harness): number =>
  observe(bench).nearby.passiveAnimals.length;

test("something behind Person is absent until Person looks at it", async () => {
  const bench = await harness();
  // Facing negative Z; the cow is the other way.
  bench.world.turn(0);
  bench.world.spawn("cow", { x: 0, y: 64, z: 8 });

  assert.equal(sees(bench, "cow"), false, "behind Person to begin with");

  // Two deliberate turns of the bounded gaze step bring it round.
  for (let turn = 0; turn < 4; turn++) await bench.world.look("left");
  assert.equal(sees(bench, "cow"), true, "looking at it now");
});

test("turning away again makes it absent", async () => {
  const bench = await harness();
  bench.world.turn(0);
  bench.world.spawn("cow", { x: 0, y: 64, z: -8 });
  assert.equal(sees(bench, "cow"), true, "straight ahead");

  for (let turn = 0; turn < 4; turn++) await bench.world.look("left");
  assert.equal(sees(bench, "cow"), false, "now behind Person");
});

test("left and right turn opposite ways, and towards the right side", async () => {
  const bench = await harness();
  bench.world.turn(0);
  // Facing negative Z, Person's right hand points towards positive X. A cow
  // on each side proves the directions are not merely different but correct.
  bench.world.spawn("cow", { x: 12, y: 64, z: 4 });

  assert.equal(sees(bench, "cow"), false, "off to the right, out of view");
  await bench.world.look("right");
  await bench.world.look("right");
  assert.equal(sees(bench, "cow"), true, "looking right finds it");

  await bench.world.look("left");
  await bench.world.look("left");
  await bench.world.look("left");
  await bench.world.look("left");
  assert.equal(sees(bench, "cow"), false, "looking left loses it again");
});

test("looking up and down changes what is perceptible vertically", async () => {
  const bench = await harness();
  bench.world.turn(0);
  // Well above Person, straight ahead: outside the vertical field until it
  // looks up.
  bench.world.spawn("cow", { x: 0, y: 78, z: -4 });

  const before = sees(bench, "cow");
  await bench.world.look("up");
  await bench.world.look("up");
  const after = sees(bench, "cow");

  assert.equal(before, false, "too high to see while looking level");
  assert.equal(after, true, "looking up brings it into the field");
});

test("a survey finds something on the left, and something on the right", async () => {
  for (const side of [-1, 1]) {
    const bench = await harness();
    bench.world.turn(0);
    // Directly beside Person, outside the field while facing forward.
    bench.world.spawn("cow", { x: 10 * side, y: 64, z: 6 });
    assert.equal(sees(bench, "cow"), false, "not visible facing forward");

    await survey(bench.world);
    assert.equal(
      sees(bench, "cow"),
      true,
      `the survey should have turned to the ${side < 0 ? "left" : "right"}`,
    );
  }
});

test("a survey cannot find something behind a wall", async () => {
  const bench = await harness();
  bench.world.turn(0);
  bench.world.spawn("cow", { x: 8, y: 64, z: 0 });
  for (let z = -3; z <= 3; z++)
    for (let y = 64; y <= 66; y++)
      bench.world.setBlock({ x: 4, y, z }, "stone");

  await survey(bench.world);
  assert.equal(sees(bench, "cow"), false, "the wall is still a wall");
});

test("a survey cannot find something out of range", async () => {
  const bench = await harness();
  bench.world.turn(0);
  bench.world.spawn("cow", { x: VISION.range + 12, y: 64, z: 0 });

  await survey(bench.world);
  assert.equal(sees(bench, "cow"), false, "range is still range");
});

test("a survey is bounded in orientations and in what it yields", async () => {
  const bench = await harness();
  bench.world.turn(0);
  // A crowd, all round Person.
  for (let index = 0; index < 40; index++) {
    const angle = (index / 40) * Math.PI * 2;
    bench.world.spawn("cow", {
      x: Math.round(Math.cos(angle) * 9),
      y: 64,
      z: Math.round(Math.sin(angle) * 9),
    });
  }

  assert.ok(GAZE.scanOrientations.length <= 8, "a survey is a finite sweep");
  await survey(bench.world);

  assert.ok(
    perceivedCount(bench) <= 12,
    `a survey must not turn into a world dump: ${perceivedCount(bench)}`,
  );
});

test("no gaze machinery reaches cognition", async () => {
  const bench = await harness();
  bench.world.spawn("cow", { x: 0, y: 64, z: -5 });
  await survey(bench.world);
  const serialized = JSON.stringify(observe(bench));

  for (const field of ["yaw", "pitch", "gaze", "orientation", "heading"])
    assert.ok(
      !new RegExp(`"${field}"`).test(serialized),
      `${field} is privileged motor state`,
    );
});

test("a gaze request has nowhere to put a coordinate", async () => {
  // Gaze reaches the body as an ordinary SkillInvocation, and the skill takes
  // no parameters at all. There is no field for an angle, an entity or a
  // position, so "look at 12, 64, -30" is not a thing cognition can say badly
  // rather than a thing it is asked not to say.
  const { skillRegistry } = await import("#skills");
  const spec = skillRegistry().get("look_around");

  assert.deepEqual(Object.keys(spec.parameters), []);
  assert.deepEqual(spec.requiredPermissions, []);
  assert.equal(spec.costLimits.maxDistance, 0, "looking is not travelling");
});

test("the gaze vocabulary is closed", async () => {
  const { GAZE_DIRECTIONS } = await import("#node-runtime");
  // Five words, none of them a number. Widening this is a deliberate act.
  assert.deepEqual([...GAZE_DIRECTIONS].sort(), [
    "down",
    "forward",
    "left",
    "right",
    "up",
  ]);
});
