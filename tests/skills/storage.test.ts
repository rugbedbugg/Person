import test from "node:test";
import assert from "node:assert/strict";
import { harness } from "../support/harness.ts";

const STORAGE_WORLD = {
  name: "storage",
  seed: 5,
  startTick: 0,
  timeOfDay: 1000,
  biome: "plains",
  groundLevel: 63,
  spawn: { x: 0, y: 64, z: 0 },
  vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
  inventory: [
    { name: "chest", count: 1 },
    { name: "oak_log", count: 24 },
    { name: "cooked_beef", count: 12 },
  ],
  blocks: [],
  clusters: [],
  entities: [],
  containers: [
    {
      position: { x: -5, y: 64, z: 0 },
      kind: "chest" as const,
      contents: [{ name: "apple", count: 6 }],
    },
  ],
  events: [],
};

test("placing an owned chest records provenance and enables deposit", async () => {
  const world = await harness({ world: STORAGE_WORLD });
  const placed = await world.run("place_owned_chest");
  assert.equal(placed.status, "SUCCESS", JSON.stringify(placed.reasonCodes));
  assert.equal(world.ledger.ownedStorage.length, 1);
  const record = world.ledger.ownedStorage[0];
  assert.ok(record);
  assert.equal(record.createdByPerson, "ada");
  assert.equal(record.worldId, "test-world");
  assert.match(record.creationEvent, /^place_owned_chest@tick:/);

  const deposited = await world.run("deposit_owned_storage", {
    category: "food",
    keep: 4,
  });
  assert.equal(
    deposited.status,
    "SUCCESS",
    JSON.stringify(deposited.reasonCodes),
  );
  const stored = world.world.containerAt(record.position);
  assert.ok(stored);
  assert.equal(stored.storageId, record.storageId);
  assert.equal(
    stored.contents.find((item) => item.name === "cooked_beef")?.count,
    8,
  );

  const withdrawn = await world.run("withdraw_owned_storage", {
    category: "food",
    amount: 2,
  });
  assert.equal(
    withdrawn.status,
    "SUCCESS",
    JSON.stringify(withdrawn.reasonCodes),
  );
});

test("a pre-existing container can be looted but never deposited into", async () => {
  const world = await harness({ world: STORAGE_WORLD });
  const looted = await world.run("loot_permitted_container", { amount: 3 });
  assert.equal(looted.status, "SUCCESS", JSON.stringify(looted.reasonCodes));
  assert.ok(
    world.world.snapshot().inventory.some((item) => item.name === "apple"),
    "looting should have moved apples into the inventory",
  );

  // There is no owned storage, so deposit has nothing legal to target.
  const deposit = await world.run("deposit_owned_storage", {
    category: "any",
    keep: 0,
  });
  assert.equal(deposit.status, "INVALIDATED");
  assert.ok(deposit.reasonCodes.includes("no_owned_storage"));

  // And the embodiment itself refuses a deposit into a container it did not place.
  await assert.rejects(
    () =>
      world.world.deposit({ x: -5, y: 64, z: 0 }, [
        { name: "oak_log", count: 1 },
      ]),
    (error: unknown) =>
      (error as { reason?: string }).reason ===
      "existing_container_deposit_forbidden",
  );
});
