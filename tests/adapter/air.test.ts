/**
 * The Mineflayer body's upward swim (ADR 0019), over the conformance double:
 * holding jump rises through water, and the stroke ends when the head is in
 * air, the body dies, the connection is lost, or the budget is spent.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { MineflayerEmbodiment, blockKind } from "#minecraft-adapter";
import { baseConfig } from "../support/harness.ts";
import { reconnectingFactory } from "../support/mineflayer-double.ts";

/** Water from y 57 to 63 in the column at the origin. */
const COLUMN: Record<string, string> = Object.fromEntries(
  [57, 58, 59, 60, 61, 62, 63].map((y) => [`0,${y},0`, "water"]),
);

async function swimmer(blocks: Record<string, string> = COLUMN) {
  const base = baseConfig();
  const factory = reconnectingFactory({
    position: { x: 0, y: 58, z: 0 },
    blocks,
  });
  const body = new MineflayerEmbodiment(
    {
      ...base,
      runtime: {
        ...base.runtime,
        embodiment: "minecraft",
        trainingContext: "minecraft_peaceful",
      },
      server: { host: "127.0.0.1", port: 25565, version: "1.16.1" },
      bot: { username: "PersonAda", auth: "offline" },
    },
    { createBot: factory.createBot as never, connectTimeoutMs: 1500 },
  );
  body.setGuard({
    canEnter: () => true,
    canModify: () => true,
    canTargetEntity: () => true,
  });
  await body.connect();
  return { body, bot: factory.bots[0]! };
}

const headKind = (body: MineflayerEmbodiment): string | undefined => {
  const feet = body.snapshot().position!;
  return body.blockAt({ ...feet, y: feet.y + 1 })?.kind;
};

test("holding jump in open water rises until the head is in air, then lets go", async () => {
  const { body, bot } = await swimmer();
  assert.equal(headKind(body), "water");
  await body.ascend({ maxTicks: 100 });
  assert.equal(headKind(body), "air");
  assert.equal(bot.controls["jump"], false, "jump released");
  await body.disconnect();
});

test("a stroke under a solid ceiling spends its budget and stops", async () => {
  const { body, bot } = await swimmer({ ...COLUMN, "0,60,0": "stone" });
  const started = Date.now();
  await body.ascend({ maxTicks: 10 });
  assert.equal(headKind(body), "water");
  assert.ok(Date.now() - started < 2000, "bounded");
  assert.equal(bot.controls["jump"], false);
  await body.disconnect();
});

test("a stroke ends when the body dies", async () => {
  const { body, bot } = await swimmer({ ...COLUMN, "0,60,0": "stone" });
  const swimming = body.ascend({ maxTicks: 200 });
  bot.damage(20);
  await assert.rejects(swimming, { reason: "died" });
  await body.disconnect();
});

test("a stroke ends when the connection is lost", async () => {
  const { body, bot } = await swimmer({ ...COLUMN, "0,60,0": "stone" });
  const swimming = body.ascend({ maxTicks: 200 });
  bot.emit("end", "socketClosed");
  await assert.rejects(swimming, { name: "DisconnectedError" });
  await body.disconnect();
});

test("plants that grow only under water read as water, so they are never mistaken for air", () => {
  for (const name of [
    "water",
    "kelp",
    "kelp_plant",
    "seagrass",
    "tall_seagrass",
    "bubble_column",
  ])
    assert.equal(blockKind(name), "water", name);
  assert.equal(blockKind("air"), "air");
});
