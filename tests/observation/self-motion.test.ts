import test from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import {
  SelfMotionSense,
  buildObservation,
  selfMotion,
  type BodyPose,
} from "#node-runtime";
import { harness, type Harness } from "../support/harness.ts";

/**
 * Person's sense of its own motion (ADR 0008).
 *
 * The runtime knows exactly where Person is and which way it faces. What it
 * reports is what a body would feel: moved a little ahead and to the left,
 * turned right. These tests pin the categories, the frame they are relative
 * to, and that nothing absolute survives the translation.
 *
 * Deterministic and offline. This proves the geometry, not Minecraft.
 */

const DEG = Math.PI / 180;

/** Facing negative Z at yaw 0; turning left increases yaw. */
const pose = (x: number, z: number, yawDegrees = 0, tick = 0): BodyPose => ({
  position: { x, y: 64, z },
  yaw: yawDegrees * DEG,
  tick,
  dimension: "overworld",
  alive: true,
});

test("standing still is felt as no motion at all", () => {
  const felt = selfMotion(pose(0, 0, 0, 0), pose(0.2, -0.1, 0, 40));
  assert.equal(felt.continuity, "continuous");
  assert.deepEqual(felt.translation, {
    direction: "none",
    band: "none",
    distance: 0,
  });
  assert.equal(felt.rotation, "none");
  assert.equal(felt.vertical, "level");
});

test("walking the way Person faces is felt as ahead", () => {
  const felt = selfMotion(pose(0, 0, 0, 0), pose(0, -6, 0, 40));
  assert.equal(felt.translation.direction, "ahead");
  assert.equal(felt.translation.band, "short");
  assert.equal(felt.translation.distance, 6);
});

test("sideways and diagonal motion land in the right sectors", () => {
  // Facing negative Z, negative X is Person's left.
  const cases: [number, number, string][] = [
    [-5, 0, "left"],
    [5, 0, "right"],
    [-4, -4, "ahead_left"],
    [4, -4, "ahead_right"],
    [0, 5, "behind"],
    [-4, 4, "behind_left"],
    [4, 4, "behind_right"],
  ];
  for (const [x, z, expected] of cases)
    assert.equal(
      selfMotion(pose(0, 0, 0, 0), pose(x, z, 0, 40)).translation.direction,
      expected,
      `${x},${z}`,
    );
});

test("the frame is the facing at the previous observation, not the world", () => {
  // The same step in the world is "ahead" for one facing and "right" for
  // another, because translation is felt relative to where Person faced.
  const step = pose(0, -6, 0, 40);
  assert.equal(selfMotion(pose(0, 0, 0), step).translation.direction, "ahead");
  assert.equal(
    selfMotion(pose(0, 0, 90), step).translation.direction,
    "right",
    "facing negative X, negative Z is to the right",
  );
});

test("turning on the spot changes facing and nothing else", () => {
  const felt = selfMotion(pose(0, 0, 0, 0), pose(0, 0, 90, 10));
  assert.equal(felt.translation.band, "none");
  assert.equal(felt.rotation, "left");
  assert.equal(
    selfMotion(pose(0, 0, 0), pose(0, 0, -45)).rotation,
    "slight_right",
  );
  assert.equal(
    selfMotion(pose(0, 0, 0), pose(0, 0, 180)).rotation,
    "about_face",
  );
  assert.equal(selfMotion(pose(0, 0, 170), pose(0, 0, -170)).rotation, "none");
});

test("rotation is rounded to an eighth of a turn, never reported in degrees", () => {
  // 30 and 60 degrees both feel like a slight turn; 20 is nothing.
  assert.equal(
    selfMotion(pose(0, 0, 0), pose(0, 0, 30)).rotation,
    "slight_left",
  );
  assert.equal(
    selfMotion(pose(0, 0, 0), pose(0, 0, 60)).rotation,
    "slight_left",
  );
  assert.equal(selfMotion(pose(0, 0, 0), pose(0, 0, 20)).rotation, "none");
  const felt = JSON.stringify(selfMotion(pose(0, 0, 0), pose(3, -7, 37, 40)));
  assert.ok(!/\d+\.\d{2,}/.test(felt), `no fine-grained number: ${felt}`);
});

test("a jump no walking explains is felt as a discontinuity, not a distance", () => {
  const felt = selfMotion(pose(0, 0, 0, 0), pose(300, 0, 0, 20));
  assert.equal(felt.continuity, "discontinuous");
  assert.equal(felt.translation.distance, null);
  assert.equal(felt.translation.direction, "unknown");
  const revived = selfMotion(
    { ...pose(0, 0), alive: false },
    { ...pose(0, 0), alive: true },
  );
  assert.equal(revived.continuity, "discontinuous");
});

test("falling is felt", () => {
  const fall = selfMotion(pose(0, 0), {
    ...pose(0, 0, 0, 20),
    position: { x: 0, y: 58, z: 0 },
  });
  assert.equal(fall.vertical, "down");
});

function observe(bench: Harness, sense: SelfMotionSense) {
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
    selfMotion: sense.sense(bench.world.snapshot()),
  });
}

test("through the real observation path: start, a glance, a walk", async () => {
  const bench = await harness();
  await bench.world.connect();
  const sense = new SelfMotionSense();

  assert.equal(observe(bench, sense).selfMotion.continuity, "start");

  await bench.world.look("left");
  const glance = observe(bench, sense).selfMotion;
  assert.equal(glance.rotation, "slight_left", "one gaze step is one eighth");
  assert.equal(glance.translation.band, "none");

  const before = bench.world.snapshot().position;
  await bench.world.moveTo({ x: before.x, y: before.y, z: before.z - 6 });
  const walk = observe(bench, sense).selfMotion;
  assert.equal(walk.translation.band, "short");
  assert.notEqual(walk.translation.direction, "none");
});

test("being pushed is felt as motion, like any other", async () => {
  const bench = await harness();
  await bench.world.connect();
  const sense = new SelfMotionSense();
  observe(bench, sense);
  const here = bench.world.snapshot().position;
  bench.world.pass(20);
  bench.world.teleport({ x: here.x + 3, y: here.y, z: here.z });
  const felt = observe(bench, sense).selfMotion;
  assert.equal(felt.continuity, "continuous");
  assert.equal(felt.translation.band, "short");
});

test("the sense carries nothing absolute", async () => {
  const bench = await harness();
  await bench.world.connect();
  const sense = new SelfMotionSense();
  observe(bench, sense);
  bench.world.pass(40);
  bench.world.teleport({ x: 7, y: 64, z: -9 });
  bench.world.turn(1.234);
  const felt = observe(bench, sense).selfMotion;
  const serialized = JSON.stringify(felt);
  for (const forbidden of [
    '"x"',
    '"y"',
    '"z"',
    "yaw",
    "pitch",
    "1.234",
    "north",
  ])
    assert.ok(!serialized.includes(forbidden), `${forbidden} in ${serialized}`);
});
