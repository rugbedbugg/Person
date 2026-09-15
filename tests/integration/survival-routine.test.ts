import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import type { FixtureWorldDefinition } from "#fixture-world";
import { REPOSITORY, harness } from "../support/harness.ts";

/**
 * The acceptance world without its scripted hostile. The emergency path has
 * its own tests; this one is about whether the survival chain itself closes.
 */
const peacefulSlice = (): FixtureWorldDefinition => ({
  ...(JSON.parse(
    readFileSync(
      path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
      "utf8",
    ),
  ) as FixtureWorldDefinition),
  events: [],
});

/**
 * The full survival routine, driven skill by skill through the same runner the
 * runtime uses. This is the sequence the acceptance criteria describe: gather,
 * come home, cook, eat, store the surplus and take it back out again.
 */
test("a complete survival routine runs end to end against the fixture", async () => {
  const bench = await harness({ world: peacefulSlice() });
  const step = async (
    skill: string,
    parameters: Record<string, number | string | boolean> = {},
  ) => {
    const result = await bench.run(skill, parameters);
    assert.equal(
      result.status,
      "SUCCESS",
      `${skill} failed: ${result.reasonCodes.join(", ")} ${JSON.stringify(result.evidenceDetails)}`,
    );
    return result;
  };

  // Person starts hungry, so the first thing any sensible order does is eat.
  await step("gather_plant_food", { target_amount: 6, max_distance: 48 });
  await step("eat_to_target", { target_food: 18 });
  await step("gather_wood", { target_amount: 32, max_distance: 48 });
  await step("craft_basic_tools");
  await step("mine_stone", { target_amount: 12, max_distance: 48 });
  await step("hunt_safe_passive_animals", {
    target_amount: 2,
    max_distance: 32,
  });
  await step("return_home", { max_distance: 128 });
  await step("craft_furnace");
  await step("cook_food", { target_amount: 2 });
  await step("eat_to_target", { target_food: 18 });
  await step("build_basic_shelter");
  await step("craft_chest");
  await step("place_owned_chest");
  const deposited = await step("deposit_owned_storage", {
    category: "any",
    keep: 2,
  });
  const withdrawn = await step("withdraw_owned_storage", {
    category: "any",
    amount: 1,
  });
  assert.ok(
    Number(deposited.evidenceDetails["container_transfer_deposited"] ?? 0) > 0,
    "the deposit must move items into owned storage",
  );
  assert.ok(
    Number(withdrawn.evidenceDetails["container_transfer_withdrawn"] ?? 0) > 0,
    "the withdrawal must take items back out again",
  );

  const snapshot = bench.world.snapshot();
  assert.ok(snapshot.food >= 16, "Person should be fed");
  assert.ok(snapshot.alive);
  assert.equal(bench.memory.home.shelterState, "complete");
  assert.equal(bench.memory.ownedStorage.length, 1);
  const storage = bench.memory.ownedStorage[0];
  assert.ok(storage);
  assert.equal(storage.createdByPerson, "ada");
  assert.ok(
    bench.world.containerAt(storage.position),
    "the owned container still exists",
  );
  assert.ok(
    bench.memory.furnacePosition,
    "the furnace is remembered as an owned workstation",
  );
});

test("emergency skills work when the situation calls for them", async () => {
  const bench = await harness({
    world: {
      name: "emergency",
      seed: 31,
      startTick: 0,
      timeOfDay: 1000,
      biome: "plains",
      groundLevel: 63,
      spawn: { x: 0, y: 64, z: 0 },
      vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
      inventory: [{ name: "oak_log", count: 8 }],
      blocks: [],
      clusters: [],
      entities: [{ name: "zombie", position: { x: 3, y: 64, z: 0 } }],
      containers: [],
      events: [],
    },
  });

  const fled = await bench.run("flee", { min_clearance: 12 });
  assert.equal(fled.status, "SUCCESS", JSON.stringify(fled.reasonCodes));
  assert.ok(fled.effects.includes("threat_cleared"));
  const after = bench.world.snapshot();
  const nearest = Math.min(
    ...after.entities
      .filter((entity) => entity.hostile)
      .map((entity) => entity.distance),
  );
  assert.ok(nearest >= 12, `expected clearance, got ${nearest}`);

  const refuge = await bench.run("dig_in", { depth: 2 });
  assert.equal(refuge.status, "SUCCESS", JSON.stringify(refuge.reasonCodes));
  assert.ok(refuge.effects.includes("refuge_dug"));

  bench.world.despawnHostiles();
  const waited = await bench.run("wait_safely", { ticks: 60 });
  assert.equal(waited.status, "SUCCESS", JSON.stringify(waited.reasonCodes));
  assert.ok(waited.evidenceKinds.includes("elapsed_ticks"));
});

test("waiting is interrupted when a hostile turns up", async () => {
  const bench = await harness({
    world: {
      name: "wait",
      seed: 33,
      startTick: 0,
      timeOfDay: 1000,
      biome: "plains",
      groundLevel: 63,
      spawn: { x: 0, y: 64, z: 0 },
      vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
      inventory: [],
      blocks: [],
      clusters: [],
      entities: [],
      containers: [],
      events: [
        {
          atTick: 30,
          type: "spawn_hostile" as const,
          name: "zombie",
          offset: { x: 3, y: 0, z: 0 },
        },
      ],
    },
  });
  const waited = await bench.run("wait_safely", { ticks: 600 });
  assert.equal(waited.status, "INTERRUPTED");
  assert.ok(waited.reasonCodes.includes("threat_appeared"));
});
