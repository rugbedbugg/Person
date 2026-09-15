import test from "node:test";
import assert from "node:assert/strict";
import { MineflayerEmbodiment } from "#minecraft-adapter";
import type { Embodiment, PhysicalGuard } from "#node-runtime";
import { baseConfig } from "../support/harness.ts";
import {
  MineflayerDouble,
  doubleFactory,
  type DoubleOptions,
} from "../support/mineflayer-double.ts";

const permissiveGuard: PhysicalGuard = {
  canEnter: () => true,
  canModify: () => true,
  canTargetEntity: () => true,
};

async function connected(
  options: DoubleOptions = {},
  overrides: Partial<Parameters<typeof baseConfig>[0]> = {},
): Promise<{ body: MineflayerEmbodiment & Embodiment; bot: MineflayerDouble }> {
  const config = {
    ...baseConfig(overrides),
    runtime: {
      ...baseConfig(overrides).runtime,
      embodiment: "minecraft" as const,
      trainingContext: "minecraft_peaceful" as const,
    },
    server: { host: "127.0.0.1", port: 25565, version: "1.16.1" as const },
    bot: { username: "PersonAda", auth: "offline" as const },
  };
  const { bot, createBot } = doubleFactory(options);
  const body = new MineflayerEmbodiment(config, {
    createBot: createBot as never,
    connectTimeoutMs: 5000,
  });
  body.setGuard(permissiveGuard);
  await body.connect();
  return { body, bot };
}

test("a named animal is recognised from sparse metadata, not crashed on", async () => {
  // Mineflayer parses metadata into an object keyed by index. Treating it as an
  // array threw before this was fixed, which took the whole observation with it.
  const { body, bot } = await connected();
  bot.spawnEntity("cow", { x: 3, y: 64, z: 0 });
  bot.spawnEntity(
    "cow",
    { x: 4, y: 64, z: 0 },
    { metadata: { "2": "Bessie" } },
  );
  bot.spawnEntity(
    "cow",
    { x: 5, y: 64, z: 0 },
    { metadata: { "2": { text: "Daisy" } } },
  );

  const entities = body.findEntities();
  assert.equal(entities.length, 3);
  const [plain, stringNamed, componentNamed] = entities;
  assert.ok(plain && stringNamed && componentNamed);
  assert.equal(plain.named, false);
  assert.equal(
    plain.passive,
    true,
    "an unnamed cow is a legitimate food animal",
  );
  assert.equal(stringNamed.named, true);
  assert.equal(componentNamed.named, true);
  await body.disconnect();
});

test("an unrecognised custom-name shape is treated as named", async () => {
  const { body, bot } = await connected();
  bot.spawnEntity(
    "pig",
    { x: 3, y: 64, z: 0 },
    { metadata: { "2": { extra: [{ text: "x" }] } } },
  );
  const [pig] = body.findEntities();
  assert.ok(pig);
  assert.equal(
    pig.named,
    true,
    "erring towards named costs a meal, not somebody's pet",
  );
  await body.disconnect();
});

test("hostility follows the registry, including mobs it files as unknown", async () => {
  const { body, bot } = await connected();
  bot.spawnEntity("zombie", { x: 3, y: 64, z: 0 });
  bot.spawnEntity("hoglin", { x: 4, y: 64, z: 0 });
  bot.spawnEntity("cow", { x: 5, y: 64, z: 0 });
  const byName = new Map(
    body.findEntities().map((entity) => [entity.name, entity]),
  );
  assert.equal(byName.get("zombie")?.hostile, true, "registry category");
  assert.equal(
    byName.get("hoglin")?.hostile,
    true,
    "registry says UNKNOWN; it still attacks",
  );
  assert.equal(byName.get("cow")?.hostile, false);
  await body.disconnect();
});

test("neutral mobs are not hostile, and are not huntable either", async () => {
  const { body, bot } = await connected();
  bot.spawnEntity("wolf", { x: 3, y: 64, z: 0 });
  const [wolf] = body.findEntities();
  assert.ok(wolf);
  assert.equal(wolf.hostile, false, "a wolf is not a standing emergency");
  assert.equal(wolf.neutral, true);
  assert.equal(wolf.passive, false, "never a food target");
  assert.equal(wolf.tamed, true, "tameable species are treated as owned");
  await body.disconnect();
});

test("damage is remembered, which is what makes a neutral mob a threat", async () => {
  const { body, bot } = await connected();
  assert.equal(body.snapshot().recentlyDamaged, false);
  bot.damage(4);
  const after = body.snapshot();
  assert.equal(after.recentlyDamaged, true);
  assert.equal(after.lastDamageTick, 1000);
  await body.disconnect();
});

test("players and villagers are never food, whatever else they are", async () => {
  const { body, bot } = await connected();
  bot.spawnPlayer("Someone", { x: 2, y: 64, z: 0 });
  bot.spawnEntity("villager", { x: 3, y: 64, z: 0 });
  bot.spawnEntity("iron_golem", { x: 4, y: 64, z: 0 });
  const entities = body.findEntities();
  for (const entity of entities)
    assert.equal(entity.passive, false, entity.name);
  assert.equal(entities.find((e) => e.player)?.name, "player");
  assert.equal(entities.find((e) => e.name === "villager")?.villager, true);
  assert.equal(entities.find((e) => e.name === "iron_golem")?.villager, true);
  await body.disconnect();
});

test("free slots come from the window, not from counting stacks", async () => {
  const { body } = await connected({
    inventory: [{ name: "oak_log", count: 64 }],
    emptySlots: 7,
  });
  assert.equal(body.snapshot().freeSlots, 7);
  await body.disconnect();
});

test("the dimension is read from the server", async () => {
  const { body } = await connected();
  assert.equal(body.snapshot().dimension, "overworld");
  await body.disconnect();

  await assert.rejects(
    () => connected({ dimension: "the_nether" }),
    (error: unknown) =>
      (error as { reason?: string }).reason === "unsupported_dimension",
  );
});

test("a world whose rules make survival meaningless is refused", async () => {
  await assert.rejects(
    () => connected({ gameMode: "creative" }),
    (error: unknown) =>
      (error as { reason?: string }).reason === "unsupported_game_mode",
  );
  await assert.rejects(
    () => connected({ doDaylightCycle: false }),
    (error: unknown) =>
      (error as { reason?: string }).reason === "daylight_cycle_disabled",
  );
  await assert.rejects(
    () => connected({ difficulty: "normal" }),
    (error: unknown) =>
      (error as { reason?: string }).reason === "difficulty_mismatch",
  );
});

test("connection waits for the world, and gives up rather than hanging", async () => {
  // Chunks arrive after the spawn packet; acting before they do produces
  // observations nothing downstream can tell are wrong.
  const late = await connected({ chunkDelayTicks: 8 });
  assert.ok(
    late.body.blockAt({ x: 0, y: 63, z: 0 }),
    "the world is usable once connect returns",
  );
  await late.body.disconnect();

  await assert.rejects(
    () => connected({ chunkDelayTicks: 20000 }),
    (error: unknown) =>
      (error as { reason?: string }).reason === "world_not_ready",
  );
});

test("crafting asks the server which recipes are possible", async () => {
  const { body, bot } = await connected({
    inventory: [{ name: "oak_log", count: 4 }],
  });
  const planks = await body.craft("oak_planks", 1, null);
  assert.equal(planks.produced[0]?.name, "oak_planks");
  assert.equal(planks.produced[0]?.count, 4);

  // A pickaxe needs a table in 1.16.1, and the server is the authority on that.
  bot.give("stick", 4);
  await assert.rejects(
    () => body.craft("wooden_pickaxe", 1, null),
    (error: unknown) =>
      (error as { reason?: string }).reason === "no_crafting_table",
  );
  await body.disconnect();
});

test("a craft that produces nothing is a failure, not a quiet success", async () => {
  const { body, bot } = await connected({
    inventory: [{ name: "oak_log", count: 1 }],
  });
  bot.craft = async () => {
    bot.calls.push("craft");
  };
  await assert.rejects(
    () => body.craft("oak_planks", 1, null),
    (error: unknown) =>
      (error as { reason?: string }).reason === "craft_unconfirmed",
  );
  await body.disconnect();
});

test("container contents are read from the container, not from an empty cache", async () => {
  // The cached view starts empty. Deciding what to withdraw from it would
  // always conclude "nothing", which is how the first withdrawal used to fail.
  const chest = { x: 2, y: 64, z: 0 };
  const { body } = await connected({
    containers: { "2,64,0": [{ name: "apple", count: 6 }] },
  });
  assert.deepEqual(
    body.containerAt(chest)?.contents,
    [],
    "nothing is known yet",
  );
  const live = await body.inspectContainer(chest);
  assert.deepEqual(live?.contents, [{ name: "apple", count: 6 }]);
  assert.deepEqual(body.containerAt(chest)?.contents, [
    { name: "apple", count: 6 },
  ]);

  const moved = await body.withdraw(chest, [{ name: "apple", count: 2 }]);
  assert.deepEqual(moved, [{ name: "apple", count: 2 }]);
  await body.disconnect();
});

test("a full inventory is reported as such rather than as an unknown error", async () => {
  const chest = { x: 2, y: 64, z: 0 };
  const { body, bot } = await connected({
    containers: { "2,64,0": [{ name: "apple", count: 6 }] },
  });
  await body.inspectContainer(chest);
  bot.failNextTransfer = "Unable to withdraw, Bot inventory is full.";
  await assert.rejects(
    () => body.withdraw(chest, [{ name: "apple", count: 2 }]),
    (error: unknown) =>
      (error as { reason?: string }).reason === "inventory_full",
  );
  await body.disconnect();
});

test("depositing into a container Person did not place is impossible", async () => {
  const chest = { x: 2, y: 64, z: 0 };
  const { body } = await connected({
    inventory: [{ name: "oak_log", count: 4 }],
    containers: { "2,64,0": [] },
  });
  await assert.rejects(
    () => body.deposit(chest, [{ name: "oak_log", count: 1 }]),
    (error: unknown) =>
      (error as { reason?: string }).reason ===
      "existing_container_deposit_forbidden",
  );
  await body.disconnect();
});

test("smelting collects the output that is ready instead of losing it", async () => {
  const furnace = { x: 2, y: 64, z: 0 };
  const { body, bot } = await connected({
    inventory: [
      { name: "beef", count: 4 },
      { name: "coal", count: 2 },
    ],
    blocks: { "2,64,0": "furnace" },
  });
  body.registerOwnedStorage(furnace, "storage_test");
  const result = await body.smelt("beef", 4, furnace);
  assert.ok(result.produced.some((item) => item.name === "cooked_beef"));
  assert.ok(bot.held("cooked_beef") > 0);
  await body.disconnect();
});

test("armour points are computed from what Person is wearing", async () => {
  const { body, bot } = await connected();
  assert.equal(body.snapshot().armor, 0, "nothing worn");
  bot.wear(["iron_helmet", "iron_chestplate"]);
  assert.equal(
    body.snapshot().armor,
    8,
    "mineflayer exposes no total, so it is summed",
  );
  await body.disconnect();
});

test("the observation reports real light rather than guessing from the clock", async () => {
  const { body } = await connected({ timeOfDay: 18000 });
  const snapshot = body.snapshot();
  assert.ok(snapshot.lightLevel >= 0 && snapshot.lightLevel <= 15);
  assert.equal(
    snapshot.biome,
    "forest",
    "biome comes from the block, not a default",
  );
  await body.disconnect();
});

test("digging equips the right tool and reports only what was collected", async () => {
  const { body, bot } = await connected({
    inventory: [
      { name: "wooden_axe", count: 1 },
      { name: "wooden_pickaxe", count: 1 },
    ],
    blocks: { "2,64,0": "oak_log", "3,64,0": "stone" },
  });
  const logs = await body.dig({ x: 2, y: 64, z: 0 });
  assert.deepEqual(logs, [{ name: "oak_log", count: 1 }]);
  assert.ok(bot.calls.includes("equip:wooden_axe"), "an axe for wood");

  const stone = await body.dig({ x: 3, y: 64, z: 0 });
  assert.deepEqual(
    stone,
    [{ name: "cobblestone", count: 1 }],
    "stone drops cobblestone",
  );
  assert.ok(bot.calls.includes("equip:wooden_pickaxe"), "a pickaxe for stone");
  await body.disconnect();
});

test("digging is refused where the neighbours make it unsafe", async () => {
  const { body } = await connected({
    blocks: { "2,64,0": "oak_log", "3,64,0": "lava" },
  });
  await assert.rejects(
    () => body.dig({ x: 2, y: 64, z: 0 }),
    (error: unknown) => (error as { reason?: string }).reason === "unsafe_dig",
  );
  await body.disconnect();
});

test("digging the block underfoot is refused", async () => {
  const { body } = await connected();
  await assert.rejects(
    () => body.dig({ x: 0, y: 63, z: 0 }),
    (error: unknown) => (error as { reason?: string }).reason === "unsafe_dig",
  );
  await body.disconnect();
});

test("placement finds an inert reference and confirms the block arrived", async () => {
  const { body, bot } = await connected({
    inventory: [{ name: "oak_planks", count: 4 }],
  });
  await body.place({ x: 1, y: 64, z: 0 }, "oak_planks");
  assert.ok(bot.calls.includes("place:oak_planks"));
  assert.equal(body.blockAt({ x: 1, y: 64, z: 0 })?.name, "oak_planks");
  await body.disconnect();
});

test("placement against a container is refused, and so is placing into a block", async () => {
  const { body } = await connected({
    inventory: [{ name: "oak_planks", count: 4 }],
    blocks: { "1,64,0": "chest", "2,64,0": "stone" },
  });
  // Every neighbour of this target is either air or the chest, and Person never
  // right-clicks a container.
  await assert.rejects(
    () => body.place({ x: 1, y: 65, z: 0 }, "oak_planks"),
    (error: unknown) =>
      (error as { reason?: string }).reason === "no_placement_reference",
  );
  await assert.rejects(
    () => body.place({ x: 2, y: 64, z: 0 }, "oak_planks"),
    (error: unknown) => (error as { reason?: string }).reason === "occupied",
  );
  await body.disconnect();
});

test("placement without the item is refused before anything is sent", async () => {
  const { body } = await connected();
  await assert.rejects(
    () => body.place({ x: 1, y: 64, z: 0 }, "oak_planks"),
    (error: unknown) =>
      (error as { reason?: string }).reason === "missing_item",
  );
  await body.disconnect();
});

test("the guard is asked before any attack, and out-of-reach targets are refused", async () => {
  const { body, bot } = await connected();
  const cow = bot.spawnEntity("cow", { x: 2, y: 64, z: 0 });
  const distant = bot.spawnEntity("cow", { x: 30, y: 64, z: 0 });
  await body.attack(cow.id);
  assert.ok(bot.calls.some((call) => call.startsWith("attack:")));
  await assert.rejects(
    () => body.attack(distant.id),
    (error: unknown) =>
      (error as { reason?: string }).reason === "out_of_reach",
  );
  await assert.rejects(
    () => body.attack(9999),
    (error: unknown) => (error as { reason?: string }).reason === "no_target",
  );

  body.setGuard({
    canEnter: () => true,
    canModify: () => true,
    canTargetEntity: () => false,
  });
  await assert.rejects(
    () => body.attack(cow.id),
    (error: unknown) =>
      (error as { reason?: string }).reason === "forbidden_target",
  );
  await body.disconnect();
});

test("eating equips the food first, as the server requires", async () => {
  const { body, bot } = await connected({
    inventory: [{ name: "cooked_beef", count: 2 }],
    food: 10,
  });
  await body.consume("cooked_beef");
  assert.ok(bot.calls.includes("equip:cooked_beef"));
  assert.ok(bot.calls.includes("consume:cooked_beef"));
  await assert.rejects(
    () => body.consume("bread"),
    (error: unknown) =>
      (error as { reason?: string }).reason === "missing_item",
  );
  await body.disconnect();
});

test("the block search survives being handed palette entries with no position", async () => {
  // Real mineflayer calls the matcher on palette entries before it has a
  // position for them, which is why a matcher may only look at the name.
  const { body } = await connected({
    blocks: { "4,64,0": "oak_log", "5,64,0": "coal_ore" },
  });
  const wood = body.findBlocks({ kinds: ["wood"], maxDistance: 16, limit: 8 });
  assert.equal(wood.length, 1);
  assert.equal(wood[0]?.name, "oak_log");
  const ore = body.findBlocks({
    kinds: ["coal_ore"],
    maxDistance: 16,
    limit: 8,
  });
  assert.equal(ore[0]?.kind, "coal_ore");
  await body.disconnect();
});
