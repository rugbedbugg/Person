/**
 * Air deprivation restores air (ADR 0019). Found in the E3 live rehearsal: a
 * submerged body whose suffocation emergency answered with a sideways flee
 * drowned. These run the real kernel and the real skill in the fixture's pool.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { DisconnectedError } from "#node-runtime";
import { FixtureWorld } from "#fixture-world";
import { harness } from "../support/harness.ts";
import { type Position } from "#minecraft";

/** A pool from y 57 to 63 across x, z in [-3, 3], open to the sky above. */
function pool(extra: { name: string; position: Position }[] = []) {
  const water: { name: string; position: Position }[] = [];
  for (let x = -3; x <= 3; x++)
    for (let z = -3; z <= 3; z++)
      for (let y = 57; y <= 63; y++)
        water.push({ name: "water", position: { x, y, z } });
  return {
    name: "pool",
    seed: 3,
    startTick: 0,
    timeOfDay: 1000,
    biome: "plains",
    groundLevel: 63,
    spawn: { x: 0, y: 58, z: 0 },
    vitals: { health: 20, food: 20, saturation: 5, air: 60, armor: 0 },
    inventory: [],
    blocks: [...water, ...extra],
    clusters: [],
    entities: [],
    containers: [],
    events: [],
  };
}

/** Stone over the whole pool and its rim at y 60: no air within reach. */
const lid = (): { name: string; position: Position }[] => {
  const blocks: { name: string; position: Position }[] = [];
  for (let x = -6; x <= 6; x++)
    for (let z = -6; z <= 6; z++)
      for (let y = 60; y <= 63; y++)
        blocks.push({ name: "stone", position: { x, y, z } });
  return blocks;
};

const headIsClear = (world: FixtureWorld): boolean => {
  const feet = world.snapshot().position;
  const head = world.blockAt({ ...feet, y: feet.y + 1 });
  return head !== null && !head.solid && head.kind !== "water";
};

// ------------------------------------------------------------------ kernel

test("an air emergency is answered by restoring air, not by fleeing", async () => {
  const h = await harness({ world: pool() });
  const assessment = h.kernel.assess(h.world.snapshot());
  assert.equal(assessment?.trigger, "suffocation");
  assert.equal(assessment?.action, "restore_air");
  assert.equal(
    h.validator.emergencyInvocation(assessment!)?.skillId,
    "restore_air",
  );
});

test("air still comes first with a hostile nearby, and ordinary flee keeps its meaning", async () => {
  const h = await harness({
    world: {
      ...pool(),
      entities: [{ name: "zombie", position: { x: 5, y: 64, z: 0 } }],
    },
  });
  assert.equal(h.kernel.assess(h.world.snapshot())?.action, "restore_air");
  h.world.setVitals({ air: 300 });
  h.world.teleport({ x: 6, y: 64, z: 3 });
  const onLand = h.kernel.assess(h.world.snapshot());
  assert.equal(onLand?.trigger, "immediate_threat");
  assert.equal(onLand?.action, "flee", "hostile avoidance is unchanged");
});

// ------------------------------------------------------------------- skill

test("in open water the body swims up to air", async () => {
  const h = await harness({ world: pool() });
  const result = await h.run("restore_air");
  assert.equal(result.status, "SUCCESS", JSON.stringify(result.reasonCodes));
  assert.ok(result.effects.includes("air_restored"));
  assert.ok(headIsClear(h.world));
  assert.ok(
    h.kernel.assess(h.world.snapshot()) === null || h.world.snapshot().air > 60,
  );
});

test("with the way straight up blocked, the body reaches air by the next open column", async () => {
  const h = await harness({
    world: pool(
      [60, 61, 62, 63].map((y) => ({
        name: "stone",
        position: { x: 0, y, z: 0 },
      })),
    ),
  });
  const result = await h.run("restore_air");
  assert.equal(result.status, "SUCCESS", JSON.stringify(result.reasonCodes));
  assert.ok(headIsClear(h.world));
});

test("with no reachable air the skill fails cleanly, bounded, and digs nothing", async () => {
  const h = await harness({ world: pool(lid()) });
  const before = h.world.blockAt({ x: 0, y: 60, z: 0 })?.name;
  const result = await h.run("restore_air");
  assert.equal(result.status, "FAILED");
  assert.ok(
    result.reasonCodes.includes("no_reachable_air"),
    JSON.stringify(result.reasonCodes),
  );
  assert.equal(
    h.world.blockAt({ x: 0, y: 60, z: 0 })?.name,
    before,
    "no excavation",
  );
  assert.ok(
    result.elapsedTicks <= 300,
    `bounded: ${result.elapsedTicks} ticks`,
  );
});

test("a body that drowns during the escape ends it as DEATH", async () => {
  const h = await harness({ world: pool() });
  h.world.setVitals({ air: 0, health: 2 });
  // A stroke that gets nowhere while the air is already gone.
  h.world.ascend = async () => {
    h.world.pass(40);
  };
  const result = await h.run("restore_air");
  assert.equal(result.status, "DEATH");
});

test("a world lost during the escape ends it as DISCONNECTED", async () => {
  const h = await harness({ world: pool() });
  h.world.ascend = async () => {
    h.world.dropConnection();
    throw new DisconnectedError();
  };
  const result = await h.run("restore_air");
  assert.equal(result.status, "DISCONNECTED");
});

test("the fixture loses air under water, and breathes again at the surface", async () => {
  const world = new FixtureWorld(pool());
  await world.connect();
  world.setVitals({ air: 300 });
  world.pass(100);
  assert.equal(world.snapshot().air, 200);
  world.teleport({ x: 0, y: 63, z: 0 });
  world.pass(10);
  assert.ok(world.snapshot().air > 200);
});
