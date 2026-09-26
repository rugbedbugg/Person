import test from "node:test";
import assert from "node:assert/strict";
import { harness } from "../support/harness.ts";

const base = {
  name: "resources",
  seed: 11,
  startTick: 0,
  timeOfDay: 1000,
  biome: "forest",
  groundLevel: 63,
  spawn: { x: 0, y: 64, z: 0 },
  vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
  blocks: [],
  clusters: [],
  entities: [],
  containers: [],
  events: [],
};

const withTrees = {
  ...base,
  inventory: [],
  clusters: [
    { name: "oak_log", center: { x: 6, y: 64, z: 0 }, count: 20, spread: 2 },
  ],
};

test("gather_wood harvests, records evidence and reports its effects", async () => {
  const world = await harness({ world: withTrees });
  const result = await world.run("gather_wood", {
    target_amount: 4,
    max_distance: 32,
  });
  assert.equal(result.status, "SUCCESS", JSON.stringify(result.reasonCodes));
  assert.ok(result.effects.includes("wood_increased"));
  assert.ok(result.evidenceKinds.includes("inventory_delta"));
  assert.ok(result.evidenceKinds.includes("harvested_blocks"));
  const gained = result.inventoryDelta.find((item) => item.name === "oak_log");
  assert.ok(gained && gained.delta >= 4, JSON.stringify(result.inventoryDelta));
  assert.ok(result.elapsedTicks > 0, "elapsed ticks must be recorded");
});

test("gather_wood reports UNREACHABLE when nothing permitted is in range", async () => {
  const world = await harness({ world: { ...base, inventory: [] } });
  const result = await world.run("gather_wood", {
    target_amount: 4,
    max_distance: 16,
  });
  assert.equal(result.status, "UNREACHABLE");
  assert.ok(result.reasonCodes.includes("unreachable_resource"));
});

test("mine_stone refuses to run without a pickaxe and succeeds with one", async () => {
  const bare = await harness({ world: { ...base, inventory: [] } });
  const denied = await bare.run("mine_stone", {
    target_amount: 2,
    max_distance: 16,
  });
  assert.equal(denied.status, "INVALIDATED");
  assert.ok(denied.reasonCodes.includes("missing_tool"));

  const equipped = await harness({
    world: {
      ...base,
      inventory: [{ name: "wooden_pickaxe", count: 1 }],
      // Exposed surface stone. Person has no dig-down skill in this milestone,
      // so stone has to be reachable from the surface.
      clusters: [
        { name: "stone", center: { x: 5, y: 64, z: 0 }, count: 8, spread: 1 },
      ],
    },
  });
  const mined = await equipped.run("mine_stone", {
    target_amount: 2,
    max_distance: 16,
  });
  assert.equal(mined.status, "SUCCESS", JSON.stringify(mined.reasonCodes));
  const gained = mined.inventoryDelta.find(
    (item) => item.name === "cobblestone",
  );
  assert.ok(gained && gained.delta >= 2);
});

test("a tick budget smaller than the work produces TIMED_OUT", async () => {
  const world = await harness({ world: withTrees });
  const result = await world.runner.run({
    skillId: "gather_wood",
    parameters: { target_amount: 20, max_distance: 32 },
    limits: { maxTicks: 1, maxDistance: 32, minHealth: 0 },
    emergency: false,
  });
  assert.equal(result.status, "TIMED_OUT");
  assert.ok(result.reasonCodes.includes("tick_budget_exceeded"));
});

test("losing the connection mid-skill produces DISCONNECTED", async () => {
  const world = await harness({ world: withTrees });
  const running = world.run("gather_wood", {
    target_amount: 20,
    max_distance: 32,
  });
  world.world.dropConnection();
  const result = await running;
  assert.equal(result.status, "DISCONNECTED");
  assert.ok(result.reasonCodes.includes("connection_lost"));
});

test("death during a skill is reported as DEATH", async () => {
  const world = await harness({ world: withTrees });
  const running = world.run("gather_wood", {
    target_amount: 20,
    max_distance: 32,
  });
  world.world.setVitals({ health: 0 });
  const result = await running;
  assert.equal(result.status, "DEATH");
});

// A rule of this fixture world that nothing in Person is told: while it
// rains, berry bushes break but give nothing. Harvesting has to report that
// honestly, as a genuine attempt that yielded nothing, and stop trying.
const barrenInRain = {
  ...base,
  inventory: [],
  hiddenRules: [
    {
      kind: "barren_while_weather" as const,
      weather: "rain" as const,
      blocks: ["sweet_berry_bush"],
    },
  ],
  clusters: [
    {
      name: "sweet_berry_bush",
      center: { x: 5, y: 64, z: 0 },
      count: 12,
      spread: 2,
    },
  ],
};

const bushesLeft = (world: Awaited<ReturnType<typeof harness>>): number =>
  world.world.findBlocks({ kinds: ["plant_food"], maxDistance: 64, limit: 64 })
    .length;

test("a harvest that yields nothing is a genuine failure, not a full inventory", async () => {
  const world = await harness({
    world: {
      ...barrenInRain,
      events: [
        { atTick: 0, type: "weather" as const, weather: "rain" as const },
      ],
    },
  });
  const before = bushesLeft(world);
  const result = await world.run("gather_plant_food", {
    target_amount: 6,
    max_distance: 32,
  });
  assert.equal(result.status, "FAILED", JSON.stringify(result.reasonCodes));
  assert.ok(result.reasonCodes.includes("no_yield"), result.reasonCodes.join());
  assert.ok(!result.reasonCodes.includes("inventory_full"));
  assert.equal(
    before - bushesLeft(world),
    2,
    "it stops after two fruitless tries",
  );
});

test("the same harvest in clear weather yields as usual", async () => {
  const world = await harness({ world: barrenInRain });
  const result = await world.run("gather_plant_food", {
    target_amount: 6,
    max_distance: 32,
  });
  assert.equal(result.status, "SUCCESS", JSON.stringify(result.reasonCodes));
});
