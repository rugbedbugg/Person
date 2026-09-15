import test from "node:test";
import assert from "node:assert/strict";
import { baseConfig, harness } from "../support/harness.ts";
import { PermissionGate, ProtectedAreas } from "#node-runtime";

const PROTECTED = {
  min: { x: 20, y: 56, z: 20 },
  max: { x: 28, y: 80, z: 28 },
};

const world = {
  name: "safety",
  seed: 9,
  startTick: 0,
  timeOfDay: 1000,
  biome: "plains",
  groundLevel: 63,
  spawn: { x: 0, y: 64, z: 0 },
  vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
  inventory: [{ name: "oak_log", count: 40 }],
  blocks: [
    { position: { x: 24, y: 64, z: 24 }, name: "oak_log" },
    { position: { x: 25, y: 64, z: 24 }, name: "oak_log" },
  ],
  clusters: [],
  entities: [
    { name: "cow", position: { x: 2, y: 64, z: 2 } },
    { name: "cow", position: { x: 3, y: 64, z: 3 }, named: true },
    { name: "sheep", position: { x: -3, y: 64, z: 2 }, tamed: true },
    { name: "villager", position: { x: -2, y: 64, z: -3 }, villager: true },
    { name: "player", position: { x: 0, y: 64, z: -4 }, player: true },
  ],
  containers: [],
  events: [],
};

test("harvesting inside a protected area is denied", async () => {
  const bench = await harness({ world });
  assert.equal(
    bench.permissions.mayHarvest({ x: 24, y: 64, z: 24 }).allowed,
    false,
  );
  assert.equal(
    bench.permissions.mayHarvest({ x: 24, y: 64, z: 24 }).reason,
    "protected_area",
  );
  const result = await bench.run("gather_wood", {
    target_amount: 2,
    max_distance: 48,
  });
  assert.equal(
    result.status,
    "UNREACHABLE",
    "the only trees are inside the protected area",
  );
});

test("configuration refuses a home Person could not legally build on", () => {
  assert.throws(
    () =>
      baseConfig({
        home: { x: 24, y: 64, z: 24 },
        protectedAreas: [PROTECTED],
      }),
    /protectedAreas\/0 overlaps the home footprint/,
  );
});

test("building inside a protected area is denied at the interaction itself", async () => {
  const bench = await harness({ world });
  const inside = { x: 24, y: 65, z: 24 };
  assert.equal(bench.permissions.mayBuild(inside).allowed, false);
  assert.equal(bench.permissions.mayBuild(inside).reason, "protected_area");
  assert.equal(bench.guard.canModify(inside), false);
  await assert.rejects(
    () => bench.world.place(inside, "oak_log"),
    (error: unknown) =>
      (error as { reason?: string }).reason === "protected_area",
  );
  await assert.rejects(
    () => bench.world.dig({ x: 24, y: 64, z: 24 }),
    (error: unknown) =>
      (error as { reason?: string }).reason === "protected_area",
  );
});

test("a path may not clip a protected area, not even in the middle", () => {
  const config = baseConfig({ protectedAreas: [PROTECTED] });
  const areas = new ProtectedAreas(config);
  assert.equal(areas.permitted({ x: 24, y: 64, z: 24 }), false);
  assert.equal(areas.permitted({ x: 10, y: 64, z: 10 }), true);
  // Both endpoints are legal; the straight route between them is not.
  assert.equal(
    areas.routePermitted({ x: 10, y: 64, z: 10 }, { x: 40, y: 64, z: 40 }),
    false,
  );
  const violation = areas.firstViolation(
    { x: 10, y: 64, z: 10 },
    { x: 40, y: 64, z: 40 },
  );
  assert.ok(violation && violation.x >= 20 && violation.x <= 28);
});

test("navigation cannot route through a protected area", async () => {
  const guarded = await harness({ world, protectedAreas: [PROTECTED] });
  await assert.rejects(
    () =>
      guarded.world.moveTo(
        { x: 23, y: 64, z: 23 },
        { range: 0, maxTicks: 2400 },
      ),
    /no walkable route/i,
  );
  // The same journey is fine when nothing is protected, which is what shows
  // the refusal above came from the guard rather than from the terrain.
  const open = await harness({ world, protectedAreas: [] });
  await open.world.moveTo(
    { x: 23, y: 64, z: 23 },
    { range: 0, maxTicks: 4800 },
  );
  assert.deepEqual(open.world.snapshot().position, { x: 23, y: 64, z: 23 });
});

test("hunting permissions reject players, villagers, named and tamed animals", async () => {
  const bench = await harness({ world });
  const entities = bench.world.findEntities();
  const verdictFor = (
    predicate: (entity: (typeof entities)[number]) => boolean,
  ): string => {
    const entity = entities.find(predicate);
    assert.ok(entity, "fixture must contain the entity under test");
    return bench.permissions.mayHunt(entity).reason;
  };
  assert.equal(
    verdictFor((entity) => entity.player),
    "player_target_forbidden",
  );
  assert.equal(
    verdictFor((entity) => entity.villager),
    "villager_target_forbidden",
  );
  assert.equal(
    verdictFor((entity) => entity.named),
    "named_animal_forbidden",
  );
  assert.equal(
    verdictFor((entity) => entity.tamed),
    "tamed_animal_forbidden",
  );
  const plain = entities.find(
    (entity) =>
      entity.passive && !entity.named && !entity.tamed && !entity.player,
  );
  assert.ok(plain);
  assert.equal(bench.permissions.mayHunt(plain).allowed, true);
});

test("the guard refuses an attack on a forbidden target", async () => {
  const bench = await harness({ world });
  const villager = bench.world.findEntities().find((entity) => entity.villager);
  assert.ok(villager);
  await assert.rejects(
    () => bench.world.attack(villager.entityId),
    (error: unknown) =>
      (error as { reason?: string }).reason === "forbidden_target",
  );
  const player = bench.world.findEntities().find((entity) => entity.player);
  assert.ok(player);
  await assert.rejects(
    () => bench.world.attack(player.entityId),
    (error: unknown) =>
      (error as { reason?: string }).reason === "forbidden_target",
  );
});

test("container permissions are asymmetric by provenance", () => {
  const config = baseConfig();
  const gate = new PermissionGate(config);
  const existing = {
    position: { x: 2, y: 64, z: 2 },
    kind: "chest" as const,
    contents: [],
    storageId: null,
  };
  const owned = {
    ...existing,
    position: { x: 3, y: 64, z: 3 },
    storageId: "storage_3_64_3",
  };
  assert.equal(gate.mayWithdraw(existing).allowed, true);
  assert.equal(gate.mayDeposit(existing).allowed, false);
  assert.equal(
    gate.mayDeposit(existing).reason,
    "existing_container_deposit_forbidden",
  );
  assert.equal(gate.mayWithdraw(owned).allowed, true);
  assert.equal(gate.mayDeposit(owned).allowed, true);
});

test("configuration cannot enable deposits into pre-existing containers", () => {
  assert.throws(
    () =>
      baseConfig({
        config: {
          permissions: {
            containers: {
              existing: { withdraw: true, deposit: true as unknown as false },
              owned: { withdraw: true, deposit: true },
            },
            hunting: {
              passiveUnnamedAnimals: true,
              namedAnimals: false,
              tamedAnimals: false,
            },
            players: { combat: false },
            villagers: { harm: false },
            building: { enabled: true },
            protectedAreas: { enforcement: "strict" },
          },
        },
      }),
    /deposit/,
  );
});

test("configuration cannot enable player combat or hunting protected animals", () => {
  const forbidden = [
    { players: { combat: true } },
    {
      hunting: {
        passiveUnnamedAnimals: true,
        namedAnimals: true,
        tamedAnimals: false,
      },
    },
    {
      hunting: {
        passiveUnnamedAnimals: true,
        namedAnimals: false,
        tamedAnimals: true,
      },
    },
    { villagers: { harm: true } },
    { protectedAreas: { enforcement: "advisory" } },
  ];
  for (const override of forbidden) {
    assert.throws(() => {
      const config = baseConfig();
      baseConfig({
        config: {
          permissions: { ...config.permissions, ...override } as never,
        },
      });
    }, /Configuration/);
  }
});
