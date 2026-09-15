import test from "node:test";
import assert from "node:assert/strict";
import { harness } from "../support/harness.ts";

const base = {
  name: "food",
  seed: 3,
  startTick: 0,
  timeOfDay: 1000,
  biome: "plains",
  groundLevel: 63,
  spawn: { x: 0, y: 64, z: 0 },
  vitals: { health: 20, food: 10, saturation: 0, air: 300, armor: 0 },
  inventory: [],
  blocks: [],
  clusters: [],
  entities: [],
  containers: [],
  events: [],
};

test("hunting takes only unnamed, untamed passive animals", async () => {
  const world = await harness({
    world: {
      ...base,
      entities: [
        { name: "cow", position: { x: 3, y: 64, z: 0 } },
        { name: "cow", position: { x: 2, y: 64, z: 2 }, named: true },
        { name: "sheep", position: { x: -2, y: 64, z: 1 }, tamed: true },
      ],
    },
  });
  const result = await world.run("hunt_safe_passive_animals", {
    target_amount: 1,
    max_distance: 16,
  });
  assert.equal(result.status, "SUCCESS", JSON.stringify(result.reasonCodes));
  assert.ok(
    result.inventoryDelta.some(
      (item) => item.name === "beef" && item.delta > 0,
    ),
  );

  const survivors = world.world.findEntities();
  assert.ok(
    survivors.some((entity) => entity.named),
    "the named animal must still be alive",
  );
  assert.ok(
    survivors.some((entity) => entity.tamed),
    "the tamed animal must still be alive",
  );
});

test("eat_to_target raises hunger and stops at the target", async () => {
  const world = await harness({
    world: { ...base, inventory: [{ name: "cooked_beef", count: 4 }] },
  });
  const result = await world.run("eat_to_target", { target_food: 18 });
  assert.equal(result.status, "SUCCESS", JSON.stringify(result.reasonCodes));
  assert.ok(world.world.snapshot().food >= 18);
  assert.ok(result.evidenceKinds.includes("vitals_delta"));
});

test("eat_to_target is INVALIDATED with nothing edible", async () => {
  const world = await harness({
    world: { ...base, inventory: [{ name: "oak_log", count: 4 }] },
  });
  const result = await world.run("eat_to_target", { target_food: 18 });
  assert.equal(result.status, "INVALIDATED");
  assert.ok(result.reasonCodes.includes("no_food"));
});

test("cooking requires an owned furnace and fuel, then produces cooked food", async () => {
  const world = await harness({
    world: {
      ...base,
      inventory: [
        { name: "beef", count: 3 },
        { name: "coal", count: 2 },
        { name: "cobblestone", count: 16 },
        { name: "oak_log", count: 6 },
      ],
    },
  });
  const noFurnace = await world.run("cook_food", { target_amount: 2 });
  assert.equal(noFurnace.status, "INVALIDATED");
  assert.ok(noFurnace.reasonCodes.includes("no_furnace"));

  const built = await world.run("craft_furnace");
  assert.equal(built.status, "SUCCESS", JSON.stringify(built.reasonCodes));
  assert.ok(
    world.memory.furnacePosition,
    "the furnace position must be remembered",
  );

  const cooked = await world.run("cook_food", { target_amount: 2 });
  assert.equal(cooked.status, "SUCCESS", JSON.stringify(cooked.reasonCodes));
  assert.ok(
    cooked.inventoryDelta.some(
      (item) => item.name === "cooked_beef" && item.delta === 2,
    ),
  );
  assert.ok(cooked.evidenceKinds.includes("smelted_items"));
});

test("shelter is built, verified, reopened and repaired", async () => {
  const world = await harness({
    world: { ...base, inventory: [{ name: "oak_log", count: 40 }] },
  });
  const built = await world.run("build_basic_shelter");
  assert.equal(built.status, "SUCCESS", JSON.stringify(built.reasonCodes));
  assert.ok(built.evidenceKinds.includes("shelter_verified"));
  assert.equal(world.memory.home.shelterState, "complete");

  // Knock a block out and repair it.
  world.world.setBlock({ x: 1, y: 64, z: 1 }, "air");
  const repaired = await world.run("repair_shelter");
  assert.equal(
    repaired.status,
    "SUCCESS",
    JSON.stringify(repaired.reasonCodes),
  );
  assert.ok(world.world.blockAt({ x: 1, y: 64, z: 1 })?.solid);
});

test("building without materials is INVALIDATED rather than half-built", async () => {
  const world = await harness({
    world: { ...base, inventory: [{ name: "oak_log", count: 3 }] },
  });
  const result = await world.run("build_basic_shelter");
  assert.equal(result.status, "INVALIDATED");
  assert.ok(result.reasonCodes.includes("missing_materials"));
});
