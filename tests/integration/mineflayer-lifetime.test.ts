/**
 * Death, respawn and reconnection through the real runtime, real cognition
 * and the real Mineflayer adapter, over the conformance double (ADR 0017).
 * Synthetic identities only. This is the offline stand-in for the live
 * rehearsal, not a substitute for it.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { MineflayerEmbodiment } from "#minecraft-adapter";
import { baseConfig, temporaryDirectory } from "../support/harness.ts";
import {
  reconnectingFactory,
  type DoubleOptions,
} from "../support/mineflayer-double.ts";
import { runEpisode } from "../support/runtime.ts";

const COGNITION = ["uv", "run", "person-cognition"];

function minecraftBody(...options: DoubleOptions[]) {
  const base = baseConfig();
  const factory = reconnectingFactory(...options);
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
  return { body, bots: factory.bots };
}

function journal(evidence: string) {
  const directory = path.join(evidence, "journal");
  return readdirSync(directory)
    .filter((name) => name.endsWith(".jsonl"))
    .sort()
    .flatMap((name) =>
      readFileSync(path.join(directory, name), "utf8").split("\n"),
    )
    .filter((line) => line.trim())
    .map(
      (line) =>
        JSON.parse(line) as { type: string; payload: Record<string, unknown> },
    );
}

test(
  "a body found dead is reported dead, respawned by the adapter, and the same Person carries on",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-mf-life-");
    const { body, bots } = minecraftBody({ joinDead: true });
    const { report } = await runEpisode({
      worldObject: body,
      cognitionCommand: COGNITION,
      evidenceDirectory,
      personId: "test-person-000",
      maxDecisions: 3,
      death: "respawn",
    });
    const types = journal(evidenceDirectory).map((e) => e.type);
    assert.equal(types.filter((t) => t === "person_died").length, 1);
    assert.equal(types.filter((t) => t === "person_respawned").length, 1);
    assert.ok(types.indexOf("person_died") < types.indexOf("person_respawned"));
    assert.equal(bots.length, 1);
    assert.equal(bots[0]!.calls.filter((c) => c === "respawn").length, 1);
    assert.notEqual(report.reason, "death");
    assert.ok(report.decisions.length > 0, "Person went on deciding");
  },
);

test(
  "a connection lost while dead is reconnected, found still dead, and respawned once",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-mf-life-");
    const { body, bots } = minecraftBody(
      { joinDead: true, dropOnRespawn: true },
      { joinDead: true },
    );
    const { report } = await runEpisode({
      worldObject: body,
      cognitionCommand: COGNITION,
      evidenceDirectory,
      personId: "test-person-000",
      maxDecisions: 3,
      death: "respawn",
      reconnectAttempts: 1,
    });
    const events = journal(evidenceDirectory);
    const count = (type: string) =>
      events.filter((e) => e.type === type).length;
    assert.equal(count("person_died"), 1, "one death, however often seen");
    assert.equal(count("person_respawned"), 1);
    assert.deepEqual(
      events
        .filter((e) => e.type === "world_availability_changed")
        .map((e) => e.payload["state"]),
      ["available", "unavailable", "available"],
    );
    assert.equal(count("session_started"), 1, "the same session");
    assert.equal(bots.length, 2);
    assert.notEqual(report.reason, "death");
  },
);

test(
  "a death with a server that never respawns ends the episode awaiting a respawn, without crashing",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-mf-life-");
    const { body } = minecraftBody({ joinDead: true, respawnNever: true });
    const { report } = await runEpisode({
      worldObject: body,
      cognitionCommand: COGNITION,
      evidenceDirectory,
      personId: "test-person-000",
      maxDecisions: 3,
      death: "respawn",
    });
    assert.equal(report.outcome, "failed");
    assert.equal(report.reason, "death");
    const types = journal(evidenceDirectory).map((e) => e.type);
    assert.equal(types.filter((t) => t === "person_died").length, 1);
    assert.ok(!types.includes("person_respawned"), "no respawn was invented");
    assert.ok(types.includes("session_ended"), "a clean end, not a crash");
  },
);

test(
  "an ordinary run with a reconnection budget connects exactly once, and its shutdown reconnects nothing",
  { timeout: 300000 },
  async () => {
    const { body, bots } = minecraftBody({});
    await runEpisode({
      worldObject: body,
      cognitionCommand: COGNITION,
      personId: "test-person-000",
      maxDecisions: 2,
      reconnectAttempts: 3,
    });
    assert.equal(bots.length, 1);
    assert.ok(bots[0]!.calls.includes("quit"), "shut down cleanly");
  },
);
