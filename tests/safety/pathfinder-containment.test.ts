import test from "node:test";
import assert from "node:assert/strict";
import type { Box, Position } from "#config";
import {
  BLOCKS,
  FEET,
  GROUND,
  bench,
  boxGuard,
  trespasses,
} from "../support/pathfinder-bench.ts";

/**
 * Protected-region containment, proved against the real pathfinder.
 *
 * These run the actual mineflayer-pathfinder search over a synthetic world,
 * with the movement policy the live adapter installs. They are the tests that
 * deviation C7 existed for: the previous protected-route tests asserted
 * routing against the fixture world, and asserted only that an exclusion
 * function had been installed against the Minecraft one.
 *
 * Nothing here is live Minecraft evidence.
 */

const open = { minX: -8, maxX: 8, minZ: -8, maxZ: 8 };

/** A wall across the middle of the room, with a gap in the north end. */
const WALL: Box = {
  min: { x: -1, y: GROUND, z: -8 },
  max: { x: 1, y: GROUND + 5, z: 4 },
};

/** The same wall, sealing the room completely. */
const SEALED: Box = {
  min: { x: -1, y: GROUND, z: -8 },
  max: { x: 1, y: GROUND + 5, z: 8 },
};

const from: Position = { x: -6, y: FEET, z: 0 };
const to: Position = { x: 6, y: FEET, z: 0 };

test("a route around a protected region is found, and no step enters it", () => {
  const guard = boxGuard([WALL]);
  const world = bench({ bounds: open });
  const result = world.path(from, to, guard);

  assert.equal(result.status, "success", "a legal way round exists");
  assert.deepEqual(
    trespasses(result.path, guard),
    [],
    "no position on the path may be inside the region",
  );
  const arrived = result.path.at(-1);
  assert.deepEqual({ x: arrived?.x, y: arrived?.y, z: arrived?.z }, to);
});

test("the detour is taken even when cutting through would be cheaper", () => {
  // The exclusion is a rejection, not a price. A long wall makes the legal
  // detour cost far more than the penalty for one forbidden step, and the
  // search must still refuse to cross.
  const long: Box = {
    min: { x: -1, y: GROUND, z: -60 },
    max: { x: 1, y: GROUND + 5, z: 60 },
  };
  const guard = boxGuard([long]);
  const world = bench({ bounds: { minX: -8, maxX: 8, minZ: -64, maxZ: 64 } });
  const result = world.path(from, to, guard);

  assert.equal(result.status, "success");
  assert.deepEqual(trespasses(result.path, guard), []);
  assert.ok(
    result.path.length > 100,
    `expected the long way round, walked ${result.path.length} steps`,
  );
});

test("a destination reachable only through a protected region is refused", () => {
  const guard = boxGuard([SEALED]);
  const world = bench({ bounds: open });
  const result = world.path(from, to, guard);

  assert.notEqual(result.status, "success", "there is no legal route");
  assert.deepEqual(
    trespasses(result.path, guard),
    [],
    "a refused route must not have planned a step inside the region",
  );
});

test("an unrestricted route is still found", () => {
  const world = bench({ bounds: open });
  const result = world.path(from, to, null);
  assert.equal(result.status, "success");
  assert.deepEqual(result.path.at(-1), to);
});

test("a diagonal cannot cut the corner of a protected region", () => {
  // A single forbidden block on the diagonal between two open squares. The
  // search must route around it rather than clip through.
  const corner: Box = {
    min: { x: 0, y: GROUND, z: 0 },
    max: { x: 0, y: GROUND + 3, z: 0 },
  };
  const guard = boxGuard([corner]);
  const world = bench({ bounds: open });
  const result = world.path(
    { x: -2, y: FEET, z: -2 },
    { x: 2, y: FEET, z: 2 },
    guard,
  );

  assert.equal(result.status, "success");
  assert.deepEqual(trespasses(result.path, guard), []);
});

test("a jump up into a protected region is not planned", () => {
  const world = bench({ bounds: open });
  // A step up onto a ledge at x=1.
  for (let z = -8; z <= 8; z++)
    for (let x = 1; x <= 8; x++)
      world.setBlock({ x, y: GROUND + 1, z }, BLOCKS.STONE);
  const ledge: Box = {
    min: { x: 1, y: GROUND + 2, z: -8 },
    max: { x: 8, y: GROUND + 5, z: 8 },
  };
  const guard = boxGuard([ledge]);
  const result = world.path(
    { x: -2, y: FEET, z: 0 },
    { x: 4, y: GROUND + 2, z: 0 },
    guard,
  );

  assert.notEqual(result.status, "success");
  assert.deepEqual(trespasses(result.path, guard), []);
});

test("a drop down into a protected region is not planned", () => {
  const world = bench({
    bounds: { minX: -8, maxX: 8, minZ: -2, maxZ: 2 },
    ceiling: GROUND + 10,
  });
  // Raise the western half by two, so moving east is a drop.
  for (let x = -8; x <= 0; x++)
    for (let z = -2; z <= 2; z++) {
      world.setBlock({ x, y: GROUND + 1, z }, BLOCKS.STONE);
      world.setBlock({ x, y: GROUND + 2, z }, BLOCKS.STONE);
    }
  const below: Box = {
    min: { x: 1, y: GROUND, z: -2 },
    max: { x: 8, y: GROUND + 2, z: 2 },
  };
  const guard = boxGuard([below]);
  const result = world.path(
    { x: -2, y: GROUND + 3, z: 0 },
    { x: 4, y: FEET, z: 0 },
    guard,
  );

  assert.notEqual(result.status, "success");
  assert.deepEqual(trespasses(result.path, guard), []);
});

test("a ladder cannot be climbed into a protected region", () => {
  // getMoveUp never reads the block it climbs into, so the exclusion cost
  // cannot see this move. C7's live hole.
  const world = bench({
    bounds: { minX: -4, maxX: 4, minZ: -4, maxZ: 4 },
    ceiling: GROUND + 8,
  });
  for (let y = FEET; y <= FEET + 4; y++)
    world.setBlock({ x: 0, y, z: 0 }, BLOCKS.LADDER);
  // Exactly one forbidden block, at the rung Person would step onto. The
  // exclusion cost is charged against the block above the destination, which
  // here is outside the region, so the cost mechanism cannot see this move.
  const rung: Box = {
    min: { x: 0, y: FEET + 1, z: 0 },
    max: { x: 0, y: FEET + 1, z: 0 },
  };
  const guard = boxGuard([rung]);
  const result = world.path(
    { x: 0, y: FEET, z: 0 },
    { x: 0, y: FEET + 2, z: 0 },
    guard,
  );

  assert.notEqual(result.status, "success", "the climb must be refused");
  assert.deepEqual(
    trespasses(result.path, guard),
    [],
    "no step may climb into the region",
  );
});

test("parkour cannot jump into a protected region even if it is enabled", () => {
  // Parkour is off in Person's configuration. It is exercised here because
  // getMoveParkourForward adds the exclusion cost but never rejects on it, and
  // checks the block above its landing square rather than the square itself,
  // so it must be the neighbour filter that holds if it is ever switched on.
  const world = bench({ bounds: { minX: -6, maxX: 6, minZ: -1, maxZ: 1 } });
  for (const z of [-1, 0, 1])
    for (const x of [0, 1]) world.setBlock({ x, y: GROUND, z }, BLOCKS.AIR);
  const landing: Box = {
    min: { x: 2, y: FEET, z: -1 },
    max: { x: 2, y: FEET, z: 1 },
  };
  const guard = boxGuard([landing]);
  const result = world.path(
    { x: -4, y: FEET, z: 0 },
    { x: 5, y: FEET, z: 0 },
    guard,
    (movements) => {
      movements.allowParkour = true;
    },
  );

  assert.deepEqual(
    trespasses(result.path, guard),
    [],
    "a parkour jump must not land inside the region",
  );
});

test("a route may not be dug through a protected region", () => {
  // Person runs with digging off, so no move carries a toBreak list in
  // production. Digging is enabled here to exercise break containment on its
  // own terms. This one holds through the exclusion callback rather than the
  // neighbour filter: `safeToBreak` requires `exclusionBreak(block) < 100` and
  // the callback returns exactly 100, so the move is refused before the filter
  // ever sees it. The filter checks `toBreak` and `toPlace` as well, so the
  // two agree rather than one covering for the other.
  const world = bench({ bounds: { minX: -8, maxX: 8, minZ: -1, maxZ: 1 } });
  for (let y = FEET; y <= FEET + 1; y++)
    for (let z = -1; z <= 1; z++)
      for (const x of [-1, 0, 1]) world.setBlock({ x, y, z }, BLOCKS.STONE);
  const guard = boxGuard([
    { min: { x: -1, y: GROUND, z: -1 }, max: { x: 1, y: GROUND + 4, z: 1 } },
  ]);
  const result = world.path(
    { x: -4, y: FEET, z: 0 },
    { x: 4, y: FEET, z: 0 },
    guard,
    (movements) => {
      movements.canDig = true;
    },
  );

  assert.notEqual(result.status, "success", "the only route is through rock");
  assert.deepEqual(trespasses(result.path, guard), []);
});

test("a stricter policy is honoured by the next search", () => {
  // Containment is read through the guard on every search, so tightening the
  // policy changes what the next path may contain. The path already being
  // walked is stopped by the runtime, not by the planner.
  const world = bench({ bounds: open });
  const before = world.path(from, to, null);
  assert.equal(before.status, "success");

  const guard = boxGuard([SEALED]);
  const after = world.path(from, to, guard);
  assert.notEqual(after.status, "success");
  assert.deepEqual(trespasses(after.path, guard), []);
});

test("path shortcutting stays disabled while an exclusion is registered", () => {
  // postProcessPath returns early when exclusionAreasStep is non-empty. That
  // is what stops a straight line being spliced across ground the search
  // avoided, so the exclusion callbacks must never be removed in favour of the
  // neighbour filter alone.
  const world = bench({ bounds: open });
  let installed: { exclusionAreasStep: unknown[] } | null = null;
  world.path(from, to, boxGuard([WALL]), (movements) => {
    installed = movements as unknown as { exclusionAreasStep: unknown[] };
  });
  assert.ok(installed, "the bench must build a movement policy");
  assert.ok(
    (installed as unknown as { exclusionAreasStep: unknown[] })
      .exclusionAreasStep.length > 0,
    "an exclusion callback must stay registered",
  );
});
