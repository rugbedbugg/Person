import test from "node:test";
import assert from "node:assert/strict";
import { MineflayerEmbodiment } from "#minecraft-adapter";
import { PERCEPTION, type Embodiment, type PhysicalGuard } from "#node-runtime";
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
): Promise<{ body: MineflayerEmbodiment & Embodiment; bot: MineflayerDouble }> {
  const base = baseConfig();
  const config = {
    ...base,
    runtime: {
      ...base.runtime,
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

/** A field of stone all around Person, the situation the first live run hit. */
const stoneField = (): Record<string, string> => {
  const blocks: Record<string, string> = {};
  for (let x = -6; x <= 6; x++)
    for (let z = -6; z <= 6; z++)
      for (let y = 60; y <= 62; y++) blocks[`${x},${y},${z}`] = "stone";
  return blocks;
};

test("the biome reaches the observation through the real lookup", async () => {
  const { body } = await connected({ biome: "jungle" });
  assert.equal(body.snapshot().biome, "jungle");
  await body.disconnect();
});

test("a chunk with no biome data reports unknown rather than a guess", async () => {
  const { body, bot } = await connected();
  bot.biome = null;
  assert.equal(
    body.snapshot().biome,
    "unknown",
    "the fallback must stay reachable and observable",
  );
  await body.disconnect();
});

test("abundant stone cannot hide the only tree in range", async () => {
  const blocks = stoneField();
  // One log, deliberately further away than hundreds of stone blocks.
  blocks["20,64,0"] = "oak_log";
  blocks["20,65,0"] = "oak_log";
  blocks["30,64,4"] = "coal_ore";
  blocks["12,64,8"] = "sweet_berry_bush";
  const { body } = await connected({ blocks });

  const resources = body.snapshot().resources;
  const kinds = resources.map((block) => block.kind);
  assert.ok(kinds.includes("wood"), "wood must survive a stone field");
  assert.ok(kinds.includes("coal_ore"), "coal must survive a stone field");
  assert.ok(kinds.includes("plant_food"), "food must survive a stone field");
  assert.equal(
    kinds.filter((kind) => kind === "wood").length,
    2,
    "every log in range is reported, not just the budget remainder",
  );
  await body.disconnect();
});

test("no single resource kind can consume the whole budget", async () => {
  const { body } = await connected({ blocks: stoneField() });
  const resources = body.snapshot().resources;
  const stone = resources.filter((block) => block.kind === "stone").length;
  assert.ok(
    resources.length <= PERCEPTION.resources.total,
    `the resource list stays bounded (${resources.length})`,
  );
  assert.ok(
    stone <= PERCEPTION.resources.perCategory + PERCEPTION.resources.overflow,
    `stone took ${stone} slots, above its quota plus the overflow budget`,
  );
  await body.disconnect();
});

test("the resource list is nearest-first and deterministic", async () => {
  const blocks = stoneField();
  blocks["14,64,0"] = "oak_log";
  blocks["-14,64,0"] = "oak_log";
  const { body } = await connected({ blocks });
  const first = body.snapshot().resources;
  const second = body.snapshot().resources;
  assert.deepEqual(
    first.map((block) => block.position),
    second.map((block) => block.position),
    "the same world snapshot must produce the same list",
  );
  const origin = { x: 0, y: 64, z: 0 };
  const range = (position: { x: number; y: number; z: number }): number =>
    Math.hypot(
      position.x - origin.x,
      position.y - origin.y,
      position.z - origin.z,
    );
  for (let index = 1; index < first.length; index++)
    assert.ok(
      range(first[index - 1]!.position) <= range(first[index]!.position) + 1e-9,
      "resources must be reported nearest first",
    );
  await body.disconnect();
});

test("two players stay distinguishable instead of collapsing into one name", async () => {
  const { body, bot } = await connected();
  bot.spawnPlayer(
    "rugbedbugg",
    { x: 4, y: 64, z: 0 },
    "8a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
  );
  bot.spawnPlayer(
    "PersonWatcher",
    { x: 6, y: 64, z: 0 },
    "1f2e3d4c-5b6a-4978-8765-4321fedcba09",
  );
  const players = body.findEntities().filter((entity) => entity.player);
  assert.equal(players.length, 2);
  assert.deepEqual(
    players.map((player) => player.name),
    ["player", "player"],
    "the species name is still what Minecraft reports",
  );
  assert.deepEqual(
    players.map((player) => player.username),
    ["rugbedbugg", "PersonWatcher"],
  );
  assert.equal(new Set(players.map((player) => player.uuid)).size, 2);
  await body.disconnect();
});

test("identity is carried only in a shape the protocol can express", async () => {
  const { body, bot } = await connected();
  // A name too long for Minecraft and a malformed UUID. Neither is repaired,
  // rewritten or truncated: the field is simply absent.
  bot.spawnPlayer(
    "ThisNameIsFarTooLongForMinecraft",
    { x: 4, y: 64, z: 0 },
    "nope",
  );
  bot.spawnEntity("cow", { x: 5, y: 64, z: 0 });
  const [player, cow] = body.findEntities();
  assert.ok(player && cow);
  assert.equal(player.username, null);
  assert.equal(player.uuid, null);
  assert.equal(cow.username, null, "a mob has no account name");
  await body.disconnect();
});
