/**
 * The Mineflayer body's lifetime (ADR 0017): a respawn that is real before it
 * is reported, a death found on joining, and reconnection in which a retired
 * client can never change the state of its replacement.
 *
 * Every behaviour of the double used here follows mineflayer 4.39.0's health
 * plugin: `death` when health reaches zero, `spawn` only for a living body,
 * and `bot.respawn()` ignored while alive.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { MineflayerEmbodiment } from "#minecraft-adapter";
import { baseConfig } from "../support/harness.ts";
import {
  MineflayerDouble,
  reconnectingFactory,
  type DoubleOptions,
} from "../support/mineflayer-double.ts";

function minecraftConfig() {
  const base = baseConfig();
  return {
    ...base,
    runtime: {
      ...base.runtime,
      embodiment: "minecraft" as const,
      trainingContext: "minecraft_peaceful" as const,
    },
    server: { host: "127.0.0.1", port: 25565, version: "1.16.1" as const },
    bot: { username: "PersonAda", auth: "offline" as const },
  };
}

function body(createBot: () => MineflayerDouble): MineflayerEmbodiment {
  const embodiment = new MineflayerEmbodiment(minecraftConfig(), {
    createBot: createBot as never,
    connectTimeoutMs: 1500,
  });
  embodiment.setGuard({
    canEnter: () => true,
    canModify: () => true,
    canTargetEntity: () => true,
  });
  return embodiment;
}

function connections(...options: DoubleOptions[]) {
  const factory = reconnectingFactory(...options);
  const embodiment = body(factory.createBot);
  const fatal: string[] = [];
  embodiment.on("fatal", (reason: string) => fatal.push(reason));
  return { embodiment, bots: factory.bots, fatal };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

// ------------------------------------------------------------------ respawn

test("a respawn is reported only once the server has put the body back and the world is ready", async () => {
  const { embodiment, bots } = connections({
    respawnAt: { x: 4, y: 64, z: 4 },
    respawnChunkDelayTicks: 6,
  });
  await embodiment.connect();
  const [bot] = bots;
  bot!.damage(20);
  assert.equal(embodiment.snapshot().alive, false, "the death is seen");
  await embodiment.respawn();
  assert.ok(
    bot!.blockAt(bot!.entity.position),
    "the world around the new body had arrived",
  );
  const now = embodiment.snapshot();
  assert.equal(now.alive, true);
  assert.equal(now.connected, true);
  assert.deepEqual(now.position, { x: 4, y: 64, z: 4 });
  assert.deepEqual(now.lastSafePosition, { x: 4, y: 64, z: 4 });
  assert.equal(now.recentlyDamaged, false, "a new body remembers no harm");
  assert.equal(bot!.calls.filter((c) => c === "respawn").length, 1);
  await embodiment.disconnect();
});

test("a living body is not respawned", async () => {
  const { embodiment, bots } = connections({});
  await embodiment.connect();
  await embodiment.respawn();
  assert.ok(!bots[0]!.calls.includes("respawn"));
  assert.equal(embodiment.snapshot().alive, true);
  await embodiment.disconnect();
});

test("a server that never respawns the body is a refusal, not a respawn", async () => {
  const { embodiment, bots } = connections({ respawnNever: true });
  await embodiment.connect();
  bots[0]!.damage(20);
  await assert.rejects(embodiment.respawn(), { reason: "spawn_timeout" });
  assert.equal(embodiment.snapshot().alive, false);
  await embodiment.disconnect();
});

test("losing the connection during a respawn is a refusal", async () => {
  const { embodiment, bots } = connections({ respawnNever: true });
  await embodiment.connect();
  bots[0]!.damage(20);
  const respawn = embodiment.respawn();
  await tick();
  bots[0]!.emit("end", "socketClosed");
  await assert.rejects(respawn, { name: "DisconnectedError" });
  assert.equal(embodiment.snapshot().connected, false);
  await embodiment.disconnect();
});

test("a respawn outside the exploration area is refused", async () => {
  const { embodiment, bots } = connections({
    respawnAt: { x: 100000, y: 64, z: 0 },
  });
  await embodiment.connect();
  bots[0]!.damage(20);
  await assert.rejects(embodiment.respawn(), {
    reason: "spawn_outside_bounds",
  });
  await embodiment.disconnect();
});

test("a respawn while disconnected is refused", async () => {
  const { embodiment, bots } = connections({});
  await embodiment.connect();
  bots[0]!.damage(20);
  await embodiment.disconnect();
  await assert.rejects(embodiment.respawn(), { name: "DisconnectedError" });
});

// ------------------------------------------------------ joining a dead body

test("joining as a player who left dead connects to a dead body instead of timing out", async () => {
  const { embodiment, bots } = connections({ joinDead: true });
  const started = Date.now();
  await embodiment.connect();
  assert.ok(
    Date.now() - started < 1000,
    "no wait for a spawn that never comes",
  );
  const now = embodiment.snapshot();
  assert.equal(now.connected, true);
  assert.equal(now.alive, false);
  await embodiment.respawn();
  assert.equal(embodiment.snapshot().alive, true);
  assert.equal(bots.length, 1);
  await embodiment.disconnect();
});

// -------------------------------------------------------------- reconnection

test("a retired client's late end cannot disconnect its replacement", async () => {
  const { embodiment, bots, fatal } = connections({});
  await embodiment.connect();
  bots[0]!.emit("end", "socketClosed");
  assert.equal(embodiment.snapshot().connected, false);
  await embodiment.connect();
  const before = fatal.length;
  bots[0]!.emit("end", "socketClosed");
  bots[0]!.emit("kicked", "late");
  assert.equal(embodiment.snapshot().connected, true);
  assert.equal(fatal.length, before, "nothing about the new client was said");
  await embodiment.disconnect();
});

test("a retired client's late error cannot disconnect its replacement", async () => {
  const { embodiment, bots, fatal } = connections({});
  await embodiment.connect();
  bots[0]!.emit("error", new Error("ECONNRESET"));
  await embodiment.connect();
  const before = fatal.length;
  bots[0]!.emit("error", new Error("late ECONNRESET"));
  bots[0]!.damage(5);
  assert.equal(embodiment.snapshot().connected, true);
  assert.equal(embodiment.snapshot().recentlyDamaged, false);
  assert.equal(fatal.length, before);
  await embodiment.disconnect();
});

test("a duplicated end and error leave one lost connection that can be reached again", async () => {
  const { embodiment, bots } = connections({});
  await embodiment.connect();
  bots[0]!.emit("end", "socketClosed");
  bots[0]!.emit("error", new Error("EPIPE"));
  bots[0]!.emit("end", "socketClosed");
  assert.equal(embodiment.snapshot().connected, false);
  await embodiment.connect();
  assert.equal(embodiment.snapshot().connected, true);
  assert.equal(bots.length, 2);
  await embodiment.disconnect();
});

test("a failed reconnection leaves the body disconnected, and a later one succeeds", async () => {
  let attempt = 0;
  const made: MineflayerDouble[] = [];
  const embodiment = body(() => {
    const bot = new MineflayerDouble();
    made.push(bot);
    attempt += 1;
    if (attempt === 2)
      queueMicrotask(() => bot.emit("kicked", "Server restarting"));
    else bot.spawn();
    return bot;
  });
  await embodiment.connect();
  made[0]!.emit("end", "socketClosed");
  await assert.rejects(embodiment.connect());
  assert.equal(embodiment.snapshot().connected, false);
  await embodiment.connect();
  made[1]!.emit("end", "late");
  assert.equal(
    embodiment.snapshot().connected,
    true,
    "the failed client is retired too",
  );
  assert.equal(made.length, 3);
  assert.ok(
    made[0]!.calls.includes("quit") && made[1]!.calls.includes("quit"),
    "each retired client was closed, not left behind",
  );
  await embodiment.disconnect();
});

test("a death around a reconnection is found on the new connection", async () => {
  const { embodiment, bots } = connections({}, { joinDead: true });
  await embodiment.connect();
  bots[0]!.damage(20);
  bots[0]!.emit("end", "socketClosed");
  await embodiment.connect();
  assert.equal(embodiment.snapshot().connected, true);
  assert.equal(
    embodiment.snapshot().alive,
    false,
    "still dead after rejoining",
  );
  await embodiment.respawn();
  assert.equal(embodiment.snapshot().alive, true);
  await embodiment.disconnect();
});

test("an explicit disconnect retires the client, so its own end says nothing", async () => {
  const { embodiment, bots, fatal } = connections({});
  await embodiment.connect();
  await embodiment.disconnect();
  bots[0]!.emit("end", "socketClosed");
  bots[0]!.emit("error", new Error("closing"));
  assert.deepEqual(fatal, []);
  assert.equal(bots.length, 1, "nothing reconnected");
});
