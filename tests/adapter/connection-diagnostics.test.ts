import test from "node:test";
import assert from "node:assert/strict";
import { MineflayerEmbodiment } from "#minecraft-adapter";
import { classifyConnectError, classifyKick } from "#minecraft-adapter";
import { baseConfig } from "../support/harness.ts";
import { MineflayerDouble } from "../support/mineflayer-double.ts";

const CONTEXT = {
  host: "127.0.0.1",
  port: 51234,
  version: "1.16.1",
  username: "PersonAda",
};

const socketError = (code: string, message = code): Error & { code: string } =>
  Object.assign(new Error(message), { code });

function minecraftConfig() {
  const base = baseConfig();
  return {
    ...base,
    runtime: {
      ...base.runtime,
      embodiment: "minecraft" as const,
      trainingContext: "minecraft_peaceful" as const,
    },
    server: { host: "127.0.0.1", port: 51234, version: "1.16.1" as const },
    bot: { username: "PersonAda", auth: "offline" as const },
  };
}

/**
 * Connects against a double that fails the way a real client would, and checks
 * the failure is classified rather than left to time out anonymously.
 */
async function failingConnect(
  fail: (bot: MineflayerDouble) => void,
): Promise<unknown> {
  const bot = new MineflayerDouble();
  const body = new MineflayerEmbodiment(minecraftConfig(), {
    createBot: (() => {
      queueMicrotask(() => fail(bot));
      return bot;
    }) as never,
    connectTimeoutMs: 4000,
  });
  body.setGuard({
    canEnter: () => true,
    canModify: () => true,
    canTargetEntity: () => true,
  });
  try {
    await body.connect();
    return null;
  } catch (error) {
    return error;
  } finally {
    await body.disconnect();
  }
}

test("a refused connection says so, and says what to do about it", async () => {
  const error = (await failingConnect((bot) =>
    bot.emit(
      "error",
      socketError("ECONNREFUSED", "connect ECONNREFUSED 127.0.0.1:51234"),
    ),
  )) as { reason?: string; hint?: string; message?: string };
  assert.equal(error.reason, "connection_refused");
  assert.match(error.message ?? "", /127\.0\.0\.1:51234/);
  assert.match(error.hint ?? "", /--port/);
  assert.match(error.hint ?? "", /changes every time/);
});

test("network failures are distinguished from each other", () => {
  const cases: [string, string][] = [
    ["ECONNREFUSED", "connection_refused"],
    ["ENOTFOUND", "host_unresolved"],
    ["EHOSTUNREACH", "host_unreachable"],
    ["ENETUNREACH", "host_unreachable"],
    ["ETIMEDOUT", "connection_timed_out"],
    ["ECONNRESET", "connection_reset"],
  ];
  for (const [code, reason] of cases) {
    const classified = classifyConnectError(socketError(code), CONTEXT);
    assert.equal(classified.reason, reason, code);
    assert.ok(classified.hint, `${code} must carry a hint`);
  }
});

test("a version mismatch is not reported as a network problem", () => {
  const classified = classifyConnectError(
    new Error("unsupported protocol version: 47"),
    CONTEXT,
  );
  assert.equal(classified.reason, "protocol_mismatch");
  assert.match(classified.hint ?? "", /1\.16\.1/);
});

test("kicks are classified by what the server said", () => {
  const cases: [string, string][] = [
    ["You are already logged in with that name", "identity_conflict"],
    ["You are not white-listed on this server!", "login_refused"],
    ["Outdated client! Please use 1.16.1", "protocol_mismatch"],
    [
      "Failed to verify username! Authentication servers are down",
      "authentication_refused",
    ],
    ["The server is restarting", "server_kicked"],
  ];
  for (const [reason, expected] of cases) {
    const classified = classifyKick(reason, CONTEXT);
    assert.equal(classified.reason, expected, reason);
    assert.ok(classified.hint);
    assert.match(
      classified.message,
      /restarting|logged in|white|Outdated|verify/i,
    );
  }
});

test("a kick arriving as a chat component is still readable", () => {
  const classified = classifyKick(
    { message: "You are already logged in with that name" },
    CONTEXT,
  );
  assert.equal(classified.reason, "identity_conflict");
});

test("a login kick fails the connection immediately rather than timing out", async () => {
  const started = Date.now();
  const error = (await failingConnect((bot) =>
    bot.emit("kicked", "You are already logged in with that name"),
  )) as { reason?: string };
  assert.equal(error.reason, "identity_conflict");
  assert.ok(
    Date.now() - started < 3000,
    "a refused login must not wait out the spawn timeout",
  );
});

test("a connection that closes before spawn is distinguished from a timeout", async () => {
  const error = (await failingConnect((bot) =>
    bot.emit("end", "socket closed"),
  )) as {
    reason?: string;
    hint?: string;
  };
  assert.equal(error.reason, "connection_closed");
  assert.ok(error.hint);
});

test("a server that accepts but never spawns is a spawn timeout", async () => {
  const error = (await failingConnect(() => {})) as {
    reason?: string;
    hint?: string;
  };
  assert.equal(error.reason, "spawn_timeout");
  assert.match(error.hint ?? "", /reachable/);
});
