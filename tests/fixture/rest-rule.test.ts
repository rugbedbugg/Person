/**
 * The synthetic recurring problem behind the habit-formation tests (ADR 0022,
 * C4.1): `barren_until_rested`. After an `unrest` event the listed blocks
 * break but drop nothing until the body has waited; a `rest_stops_helping`
 * regime change makes waiting useless. `remove_items` and `set_vitals` reset a
 * problem between episodes. The world creates the problem and never supplies
 * its solution. Privileged fixture physics; nothing here reaches Person.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { FixtureWorld } from "#fixture-world";

const log = (x: number) => ({ name: "oak_log", position: { x, y: 64, z: 2 } });

function world(events: unknown[], restTicks?: number): FixtureWorld {
  return new FixtureWorld({
    name: "rest-rule",
    seed: 3,
    startTick: 0,
    timeOfDay: 1000,
    biome: "forest",
    groundLevel: 63,
    spawn: { x: 0, y: 64, z: 0 },
    vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
    inventory: [{ name: "bread", count: 4 }],
    blocks: [-2, -1, 0, 1, 2].map(log),
    clusters: [],
    entities: [],
    containers: [
      {
        position: { x: 0, y: 64, z: -2 },
        kind: "chest",
        contents: [{ name: "oak_log", count: 5 }],
      },
    ],
    events,
    hiddenRules: [
      {
        kind: "barren_until_rested",
        blocks: ["oak_log"],
        ...(restTicks ? { restTicks } : {}),
      },
    ],
  } as ConstructorParameters<typeof FixtureWorld>[0]);
}

const logs = (w: FixtureWorld): number =>
  w.snapshot().inventory.find((item) => item.name === "oak_log")?.count ?? 0;

test("until the body has waited, an unrested world's logs drop nothing; then they do", async () => {
  const w = world([{ atTick: 0, type: "unrest" }]);
  await w.connect();
  w.pass(1);
  assert.deepEqual(await w.dig(log(-2).position), [], "barren");
  await w.waitTicks(60);
  assert.deepEqual(await w.dig(log(-1).position), [], "not rested enough yet");
  await w.waitTicks(40);
  await w.dig(log(0).position);
  assert.equal(logs(w), 1, "rested: the rule switches off");
});

test("time passing is not rest: only the body's own waiting counts", async () => {
  const w = world([{ atTick: 0, type: "unrest" }]);
  await w.connect();
  w.pass(500);
  assert.deepEqual(await w.dig(log(-2).position), []);
});

test("a rest requirement is a rule parameter", async () => {
  const w = world([{ atTick: 0, type: "unrest" }], 300);
  await w.connect();
  w.pass(1);
  await w.waitTicks(200);
  assert.deepEqual(await w.dig(log(-2).position), []);
  await w.waitTicks(100);
  await w.dig(log(-1).position);
  assert.equal(logs(w), 1);
});

test("after the regime change, resting no longer helps", async () => {
  const w = world([
    { atTick: 0, type: "unrest" },
    { atTick: 0, type: "rest_stops_helping" },
  ]);
  await w.connect();
  w.pass(1);
  await w.waitTicks(1000);
  assert.deepEqual(await w.dig(log(-2).position), []);
});

test("an episode reset takes items from the body and the world's chests, and sets vitals", async () => {
  const w = world([
    { atTick: 200, type: "remove_items", items: ["oak_log", "bread"] },
    {
      atTick: 200,
      type: "set_vitals",
      vitals: { health: 12, food: 15, saturation: 3 },
    },
  ]);
  await w.connect();
  await w.dig(log(-2).position);
  assert.equal(logs(w), 1, "a world never unrested is not barren");
  w.pass(300);
  const snapshot = w.snapshot();
  assert.deepEqual(snapshot.inventory, []);
  assert.deepEqual(w.containerAt({ x: 0, y: 64, z: -2 })?.contents, []);
  assert.equal(snapshot.health, 12);
  assert.equal(snapshot.food, 15);
  assert.equal(snapshot.saturation, 3);
});

test("only the part of a wait after the problem began is rest", async () => {
  const w = world([{ atTick: 50, type: "unrest" }]);
  await w.connect();
  await w.waitTicks(100); // fifty of these ticks come after the unrest
  assert.deepEqual(await w.dig(log(-2).position), []);
  await w.waitTicks(50);
  await w.dig(log(-1).position);
  assert.equal(logs(w), 1);
});

// `barren_until_withdrawn` (C5): the cure is taking something from a
// container Person owns; what is taken never matters.

function chestWorld(events: unknown[], owned: boolean): FixtureWorld {
  const w = new FixtureWorld({
    name: "withdraw-rule",
    seed: 3,
    startTick: 0,
    timeOfDay: 1000,
    biome: "forest",
    groundLevel: 63,
    spawn: { x: 0, y: 64, z: 0 },
    vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
    inventory: [],
    blocks: [-2, -1, 0, 1, 2].map(log),
    clusters: [],
    entities: [],
    containers: [
      {
        position: { x: 1, y: 64, z: -1 },
        kind: "chest",
        contents: [{ name: "bread", count: 8 }],
      },
    ],
    events,
    hiddenRules: [{ kind: "barren_until_withdrawn", blocks: ["oak_log"] }],
  } as ConstructorParameters<typeof FixtureWorld>[0]);
  if (owned) w.registerOwnedStorage({ x: 1, y: 64, z: -1 }, "storage_1");
  return w;
}

const bread = [{ name: "bread", count: 1 }];

test("logs stay barren until Person withdraws from a chest it owns", async () => {
  const w = chestWorld([{ atTick: 0, type: "unrest" }], true);
  await w.connect();
  w.pass(1);
  await w.waitTicks(1000);
  assert.deepEqual(await w.dig(log(-2).position), [], "rest is not this cure");
  await w.withdraw({ x: 1, y: 64, z: -1 }, bread);
  await w.dig(log(-1).position);
  assert.equal(logs(w), 1);
});

test("taking from a chest Person does not own cures nothing", async () => {
  const w = chestWorld([{ atTick: 0, type: "unrest" }], false);
  await w.connect();
  w.pass(1);
  await w.withdraw({ x: 1, y: 64, z: -1 }, bread);
  assert.deepEqual(await w.dig(log(-2).position), []);
});

test("a new unrest needs a new withdrawal, and the regime change makes it useless", async () => {
  const w = chestWorld(
    [
      { atTick: 0, type: "unrest" },
      { atTick: 100, type: "unrest" },
      { atTick: 100, type: "withdrawal_stops_helping" },
    ],
    true,
  );
  await w.connect();
  w.pass(1);
  await w.withdraw({ x: 1, y: 64, z: -1 }, bread);
  w.pass(120);
  assert.deepEqual(
    await w.dig(log(-2).position),
    [],
    "the earlier withdrawal is spent",
  );
  await w.withdraw({ x: 1, y: 64, z: -1 }, bread);
  assert.deepEqual(
    await w.dig(log(-1).position),
    [],
    "withdrawing no longer helps",
  );
});
