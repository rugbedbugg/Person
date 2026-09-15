import test from "node:test";
import assert from "node:assert/strict";
import { distance, type Box, type Position } from "#config";
import { MineflayerEmbodiment } from "#minecraft-adapter";
import type { PhysicalGuard } from "#node-runtime";
import { baseConfig, harness } from "../support/harness.ts";
import { doubleFactory } from "../support/mineflayer-double.ts";

const PROTECTED: Box = {
  min: { x: -4, y: 56, z: -40 },
  max: { x: 4, y: 80, z: 40 },
};

/**
 * A wall of protected territory between Person and its destination. Both ends
 * are legal; the straight line between them is not.
 */
const world = {
  name: "routes",
  seed: 51,
  startTick: 0,
  timeOfDay: 1000,
  biome: "plains",
  groundLevel: 63,
  spawn: { x: -12, y: 64, z: 0 },
  vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
  inventory: [],
  blocks: [],
  clusters: [],
  entities: [],
  containers: [],
  events: [],
};

test("a route around a protected area is found, and every step of it is legal", async () => {
  const bench = await harness({
    world,
    protectedAreas: [PROTECTED],
    home: { x: -12, y: 64, z: 0 },
  });
  const destination: Position = { x: 12, y: 64, z: 0 };
  assert.equal(
    bench.permissions.mayEnter({ x: -12, y: 64, z: 0 }).allowed,
    true,
  );
  assert.equal(bench.permissions.mayEnter(destination).allowed, true);
  assert.equal(
    bench.permissions.areas.routePermitted(
      { x: -12, y: 64, z: 0 },
      destination,
    ),
    false,
    "the straight line crosses the protected strip",
  );

  await bench.world.moveTo(destination, { range: 0, maxTicks: 8000 });
  assert.deepEqual(bench.world.snapshot().position, destination);
});

test("a destination reachable only through a protected area is refused", async () => {
  // The strip runs the whole way across, so there is no legal detour at all.
  const walled: Box = {
    min: { x: -4, y: 56, z: -200 },
    max: { x: 4, y: 80, z: 200 },
  };
  const bench = await harness({
    world,
    protectedAreas: [walled],
    home: { x: -12, y: 64, z: 0 },
  });
  await assert.rejects(
    () =>
      bench.world.moveTo({ x: 12, y: 64, z: 0 }, { range: 0, maxTicks: 8000 }),
    /no walkable route/i,
  );
  assert.ok(
    distance(bench.world.snapshot().position, { x: -12, y: 64, z: 0 }) < 1,
    "a refused route must not have moved Person part of the way",
  );
});

test("the guard is consulted for every step the path search considers", async () => {
  // This is what makes replanning safe. Pathfinder re-runs its search whenever
  // a path resets, and it asks the same exclusion function every time, so a
  // detour computed later cannot cross ground the first plan avoided.
  const config = {
    ...baseConfig({
      protectedAreas: [PROTECTED],
      home: { x: -12, y: 64, z: 0 },
    }),
    runtime: {
      ...baseConfig({
        protectedAreas: [PROTECTED],
        home: { x: -12, y: 64, z: 0 },
      }).runtime,
      embodiment: "minecraft" as const,
      trainingContext: "minecraft_peaceful" as const,
    },
    server: { host: "127.0.0.1", port: 25565, version: "1.16.1" as const },
    bot: { username: "PersonAda", auth: "offline" as const },
  };
  const { bot, createBot } = doubleFactory({
    position: { x: -12, y: 64, z: 0 },
  });

  interface InstalledMovements {
    exclusionAreasStep: ((block: unknown) => number)[];
    exclusionAreasBreak: (() => number)[];
    exclusionAreasPlace: (() => number)[];
  }
  let installed: InstalledMovements | null = null;
  bot.pathfinder.setMovements = (movements: unknown) => {
    installed = movements as InstalledMovements;
  };

  const denied: Position[] = [];
  const guard: PhysicalGuard = {
    canEnter: (position) => {
      const inside =
        position.x >= PROTECTED.min.x &&
        position.x <= PROTECTED.max.x &&
        position.z >= PROTECTED.min.z &&
        position.z <= PROTECTED.max.z;
      if (inside) denied.push(position);
      return !inside;
    },
    canModify: () => true,
    canTargetEntity: () => true,
  };
  const body = new MineflayerEmbodiment(config, {
    createBot: createBot as never,
    connectTimeoutMs: 5000,
  });
  body.setGuard(guard);
  await body.connect();

  assert.ok(installed, "the adapter must install its movements");
  const movements = installed as InstalledMovements;
  assert.equal(movements.exclusionAreasStep.length, 1);

  // Pathfinder calls these with a block. A protected step must cost enough to
  // be unusable, and an ordinary one must cost nothing.
  const insideCost = movements.exclusionAreasStep[0]?.({
    position: { x: 0, y: 64, z: 0 },
  });
  const outsideCost = movements.exclusionAreasStep[0]?.({
    position: { x: 30, y: 64, z: 0 },
  });
  assert.equal(
    insideCost,
    100,
    "a step into protected ground must be excluded",
  );
  assert.equal(outsideCost, 0);
  assert.ok(denied.length > 0, "the guard was actually asked");

  // Breaking and placing along a route are refused outright, whatever the
  // search would prefer.
  assert.equal(movements.exclusionAreasBreak[0]?.(), 100);
  assert.equal(movements.exclusionAreasPlace[0]?.(), 100);
  await body.disconnect();
});

test("a protected destination is refused before any movement is attempted", async () => {
  const config = {
    ...baseConfig({
      protectedAreas: [PROTECTED],
      home: { x: -12, y: 64, z: 0 },
    }),
    runtime: {
      ...baseConfig({
        protectedAreas: [PROTECTED],
        home: { x: -12, y: 64, z: 0 },
      }).runtime,
      embodiment: "minecraft" as const,
      trainingContext: "minecraft_peaceful" as const,
    },
    server: { host: "127.0.0.1", port: 25565, version: "1.16.1" as const },
    bot: { username: "PersonAda", auth: "offline" as const },
  };
  const { bot, createBot } = doubleFactory({
    position: { x: -12, y: 64, z: 0 },
  });
  let routed = false;
  bot.pathfinder.goto = async () => {
    routed = true;
  };
  const body = new MineflayerEmbodiment(config, {
    createBot: createBot as never,
    connectTimeoutMs: 5000,
  });
  body.setGuard({
    canEnter: (position) => !(position.x >= -4 && position.x <= 4),
    canModify: () => true,
    canTargetEntity: () => true,
  });
  await body.connect();
  await assert.rejects(
    () => body.moveTo({ x: 0, y: 64, z: 0 }, { range: 0, maxTicks: 600 }),
    (error: unknown) =>
      (error as { reason?: string }).reason === "protected_area",
  );
  assert.equal(
    routed,
    false,
    "the pathfinder was never asked to plan an illegal route",
  );
  await body.disconnect();
});
