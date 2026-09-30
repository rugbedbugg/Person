/**
 * Fixture hostiles obey walls: they cannot step into solid blocks, and cannot
 * hurt Person through them, ranged or melee (ADR 0016).
 *
 * The old fixture let a skeleton shoot, and any hostile walk, through a
 * sealed shelter. This is privileged fixture physics, below cognition and the
 * safety kernel; nothing here reaches Person's observation.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { FixtureWorld } from "#fixture-world";
import { buildObservation, lineBlocked } from "#node-runtime";
import { harness } from "../support/harness.ts";

type Point = { x: number; y: number; z: number };

const base = {
  name: "hostile-physics",
  seed: 41,
  startTick: 0,
  timeOfDay: 1000,
  biome: "plains",
  groundLevel: 63,
  spawn: { x: 0, y: 64, z: 0 },
  spawnYaw: 0,
  vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
  inventory: [],
  blocks: [] as { position: Point; name: string }[],
  clusters: [],
  entities: [] as { name: string; position: Point }[],
  containers: [],
  events: [],
};

const column = (x: number, z: number, name = "stone") => [
  { position: { x, y: 64, z }, name },
  { position: { x, y: 65, z }, name },
];

/** A closed two-high ring of stone around the origin, radius 2. */
const enclosure = () => {
  const blocks = [];
  for (let x = -2; x <= 2; x++)
    for (let z = -2; z <= 2; z++)
      if (Math.max(Math.abs(x), Math.abs(z)) === 2)
        blocks.push(...column(x, z));
  return [...blocks, { position: { x: 0, y: 66, z: 0 }, name: "stone" }];
};

const world = (overrides: Partial<typeof base>) =>
  new FixtureWorld({ ...base, ...overrides });

const hostile = (w: FixtureWorld) =>
  w.snapshot().entities.find((e) => e.hostile)!;

async function wait(w: FixtureWorld, ticks: number) {
  await w.connect();
  await w.waitTicks(ticks);
}

// ------------------------------------------------------------------ attack

test("a skeleton in the open still shoots, and a wall between stops it", async () => {
  const open = world({
    entities: [{ name: "skeleton", position: { x: 0, y: 64, z: -8 } }],
  });
  // Keep it at range: a wall behind the skeleton is irrelevant, it is not moving toward a wall.
  await wait(open, 21);
  assert.ok(open.snapshot().health < 20, "hit in the open");

  const walled = world({
    entities: [{ name: "skeleton", position: { x: 0, y: 64, z: -8 } }],
    blocks: [-1, 0, 1].flatMap((x) => column(x, -3)),
  });
  await wait(walled, 21);
  assert.equal(walled.snapshot().health, 20, "the wall stops the arrow");
});

test("opening the blocking block lets the same attack through", async () => {
  const blocks = column(0, -4, "stone");
  const closed = world({
    entities: [{ name: "skeleton", position: { x: 0, y: 64, z: -10 } }],
    blocks,
  });
  const opened = world({
    entities: [{ name: "skeleton", position: { x: 0, y: 64, z: -10 } }],
    blocks: blocks.map((b) => ({ ...b, name: "air" })),
  });
  await wait(closed, 5);
  await wait(opened, 5);
  // Only the one block differs; the skeleton has not moved yet (every 6 ticks).
  assert.equal(closed.snapshot().health, 20);
  assert.ok(opened.snapshot().health < 20);
});

test("a zombie against the outside of a wall cannot hit Person inside", async () => {
  const w = world({
    blocks: enclosure(),
    entities: [{ name: "zombie", position: { x: 0, y: 64, z: -3 } }],
  });
  await wait(w, 200);
  assert.equal(w.snapshot().health, 20);
});

test("a zombie within reach cannot hit through a one-block wall", async () => {
  // Two blocks apart, inside melee reach, with a wall between them.
  const w = world({
    blocks: [-1, 0, 1].flatMap((x) => column(x, -1)),
    entities: [{ name: "zombie", position: { x: 0, y: 64, z: -2 } }],
  });
  await wait(w, 100);
  assert.equal(w.snapshot().health, 20);
});

test("a zombie in the open still hits", async () => {
  const w = world({
    entities: [{ name: "zombie", position: { x: 0, y: 64, z: -2 } }],
  });
  await wait(w, 21);
  assert.ok(w.snapshot().health < 20);
});

// ---------------------------------------------------------------- movement

test("a hostile never occupies a solid feet or head block", async () => {
  // Feet blocked on the direct line, head blocked on the next, open beyond.
  const w = world({
    entities: [{ name: "zombie", position: { x: 0, y: 64, z: -6 } }],
    blocks: [
      { position: { x: 0, y: 64, z: -5 }, name: "stone" },
      { position: { x: 1, y: 65, z: -5 }, name: "stone" },
      { position: { x: -1, y: 65, z: -5 }, name: "stone" },
    ],
  });
  await w.connect();
  for (let tick = 0; tick < 60; tick++) {
    await w.waitTicks(1);
    const p = hostile(w).position;
    const feet = w.blockAt({ x: Math.floor(p.x), y: 64, z: Math.floor(p.z) });
    const head = w.blockAt({ x: Math.floor(p.x), y: 65, z: Math.floor(p.z) });
    assert.ok(
      !feet?.solid && !head?.solid,
      `inside a block at ${JSON.stringify(p)}`,
    );
  }
});

test("a blocked diagonal falls back to the x step, then to the z step", async () => {
  // Diagonal (+1, +1) blocked; x alone open.
  const xOnly = world({
    entities: [{ name: "zombie", position: { x: -5, y: 64, z: -5 } }],
    blocks: column(-4, -4),
  });
  await wait(xOnly, 6);
  assert.deepEqual(
    [hostile(xOnly).position.x, hostile(xOnly).position.z],
    [-4, -5],
  );

  // Diagonal and x both blocked; z alone open.
  const zOnly = world({
    entities: [{ name: "zombie", position: { x: -5, y: 64, z: -5 } }],
    blocks: [...column(-4, -4), ...column(-4, -5)],
  });
  await wait(zOnly, 6);
  assert.deepEqual(
    [hostile(zOnly).position.x, hostile(zOnly).position.z],
    [-5, -4],
  );
});

test("a sealed enclosure keeps a hostile outside indefinitely", async () => {
  const w = world({
    blocks: enclosure(),
    entities: [{ name: "skeleton", position: { x: 0, y: 64, z: -8 } }],
  });
  await w.connect();
  for (let step = 0; step < 20; step++) {
    await w.waitTicks(60);
    const p = hostile(w).position;
    assert.ok(
      Math.max(Math.abs(p.x), Math.abs(p.z)) >= 3,
      `got inside at ${JSON.stringify(p)}`,
    );
  }
  assert.equal(
    w.snapshot().health,
    20,
    "and never hurt Person through the walls",
  );
});

test("the axis fallback gets a hostile around a single block on its diagonal", async () => {
  const w = world({
    entities: [{ name: "zombie", position: { x: -4, y: 64, z: -4 } }],
    blocks: column(-3, -3),
  });
  await wait(w, 60);
  const p = hostile(w).position;
  assert.ok(
    Math.max(Math.abs(p.x), Math.abs(p.z)) <= 2,
    `still at ${JSON.stringify(p)}`,
  );
});

test("with no pathfinding, a block straight ahead on the axis stops a hostile", async () => {
  // Recorded, not a goal: only the diagonal and the two axis steps are tried.
  const w = world({
    entities: [{ name: "zombie", position: { x: 0, y: 64, z: -6 } }],
    blocks: column(0, -5),
  });
  await wait(w, 60);
  assert.deepEqual([hostile(w).position.x, hostile(w).position.z], [0, -6]);
});

// ------------------------------------------------------------ the firewall

test("hostile physics puts nothing new into Person's observation", async () => {
  const bench = await harness({
    world: {
      ...base,
      blocks: enclosure(),
      entities: [{ name: "skeleton", position: { x: 0, y: 64, z: -8 } }],
    },
  });
  await bench.world.waitTicks(120);
  const observation = buildObservation({
    identity: { personId: "ada", sessionId: randomUUID(), worldId: "w" },
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
  const said = JSON.stringify(observation);
  assert.equal(observation.nearby.hostiles.length, 0, "walled off, not seen");
  assert.ok(
    !/skeleton|lineBlocked|lineOfAttack/.test(said),
    said.slice(0, 300),
  );
});

// ------------------------------------------------------------ the primitive

test("the line primitive is pure geometry, shared with vision", () => {
  const solid = new Set(["0,65,-3"]);
  const blockAt = (p: Point) => ({ solid: solid.has(`${p.x},${p.y},${p.z}`) });
  const eye = { x: 0.5, y: 65.6, z: -7.5 };
  assert.equal(lineBlocked(eye, { x: 0, y: 65, z: 0 }, blockAt), true);
  assert.equal(lineBlocked(eye, { x: 0, y: 65, z: -4 }, blockAt), false);
  assert.equal(lineBlocked(eye, { x: 4, y: 65, z: 0 }, blockAt), false);
});
