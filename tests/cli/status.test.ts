import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { UsageError, parseArguments } from "../../apps/cli/src/bin/person.ts";
import { followStatus, statusCommand } from "../../apps/cli/src/commands.ts";
import {
  StatusWriter,
  readStatus,
  renderStatus,
  stalenessSeconds,
  statusPath,
} from "#node-runtime";
import { loadConfig } from "#config";
import { REPOSITORY } from "../support/harness.ts";

const CONFIG = path.join(REPOSITORY, "examples/fixture.toml");

function seeded(): { file: string; writer: StatusWriter } {
  const directory = mkdtempSync(path.join(tmpdir(), "person-status-"));
  const file = statusPath(directory, "world", "ada");
  return {
    file,
    writer: new StatusWriter(file, {
      command: "run",
      personId: "ada",
      botUsername: "PersonAda",
      worldId: "world",
      sessionId: "8f6c1c0e-3d0a-4a1e-9f3a-2b6f1d9c4e11",
    }),
  };
}

test("status flags are parsed, and follow belongs to status alone", () => {
  const plain = parseArguments(["status", "--config", "c.toml"]);
  assert.equal(plain.command, "status");
  assert.equal(plain.follow, false);
  const following = parseArguments([
    "status",
    "--config",
    "c.toml",
    "--follow",
    "--interval",
    "250",
  ]);
  assert.equal(following.follow, true);
  assert.equal(following.intervalMs, 250);
  assert.throws(() => parseArguments(["status"]), /needs --config/);
  assert.throws(
    () => parseArguments(["run", "--config", "c.toml", "--follow"]),
    /--follow only applies/,
  );
  assert.throws(
    () =>
      parseArguments([
        "status",
        "--config",
        "c",
        "--follow",
        "--interval",
        "5",
      ]),
    /--interval must be between/,
  );
});

test("the LAN port and host are parsed and validated", () => {
  const parsed = parseArguments([
    "observe",
    "--config",
    "c.toml",
    "--port",
    "51234",
    "--host",
    "localhost",
  ]);
  assert.equal(parsed.connection.port, 51234);
  assert.equal(parsed.connection.host, "127.0.0.1", "localhost is normalised");
  assert.throws(
    () => parseArguments(["observe", "--config", "c", "--port", "0"]),
    /--port must be/,
  );
  assert.throws(
    () => parseArguments(["observe", "--config", "c", "--port", "70000"]),
    /--port must be/,
  );
  assert.throws(
    () => parseArguments(["observe", "--config", "c", "--port", "abc"]),
    /--port must be/,
  );
  assert.throws(
    () => parseArguments(["observe", "--config", "c", "--port"]),
    /--port needs/,
  );
  assert.throws(
    () => parseArguments(["run", "--config", "c", "--host", "example.com"]),
    /--host must be one of/,
  );
});

test("operator intervention can be declared, with or without a reason", () => {
  const bare = parseArguments([
    "run",
    "--config",
    "c.toml",
    "--operator-intervention",
  ]);
  assert.deepEqual(bare.operatorIntervention, {});
  const explained = parseArguments([
    "run",
    "--config",
    "c.toml",
    "--operator-intervention=gave Person a pickaxe",
  ]);
  assert.deepEqual(explained.operatorIntervention, {
    reason: "gave Person a pickaxe",
  });
  const clean = parseArguments(["run", "--config", "c.toml"]);
  assert.equal(
    clean.operatorIntervention,
    undefined,
    "a run is clean unless declared otherwise",
  );
  assert.throws(
    () => parseArguments(["run", "--config", "c", "--operator-intervention="]),
    /needs a reason/,
  );
});

test("status reports the last thing the runtime wrote", () => {
  const { file, writer } = seeded();
  writer.update({
    connection: "ready",
    readiness: "world ready",
    dimension: "overworld",
    position: { x: 12, y: 64, z: -3 },
    health: 18,
    food: 11,
    goalType: "SECURE_FOOD",
    routine: "r_abc",
    skill: "gather_plant_food",
    home: {
      position: { x: 0, y: 64, z: 0 },
      distance: 12.4,
      shelterState: "none",
    },
    lastSafePosition: { x: 1, y: 64, z: 0 },
    safety: {
      threat: "nearby",
      emergencies: 2,
      lastEmergency: {
        trigger: "immediate_threat",
        action: "flee",
        level: "L1",
      },
    },
    lastValidation: {
      decision: "REPLACE",
      level: "L1",
      requestedSkill: "gather_wood",
      executedSkill: "flee",
      reasonCodes: ["immediate_threat"],
    },
    decisions: 7,
  });

  const status = readStatus(file);
  assert.ok(status);
  const rendered = renderStatus(status);
  for (const fragment of [
    "PersonAda",
    "ready",
    "12,64,-3",
    "health=18",
    "food=11",
    "SECURE_FOOD",
    "gather_plant_food",
    "distance=12.4",
    "threat=nearby",
    "REPLACE",
    "replaced by flee",
    "mode=off",
  ])
    assert.match(
      rendered,
      new RegExp(fragment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
      fragment,
    );
});

test("a stale status says so rather than looking live", () => {
  const { file, writer } = seeded();
  writer.update({ connection: "ready" });
  const status = readStatus(file);
  assert.ok(status);
  assert.ok(stalenessSeconds(status) < 5);
  const later = Date.parse(status.updatedAt) + 120_000;
  assert.match(renderStatus(status, later), /STALE/);
});

test("status is honest when nothing has run yet", () => {
  const config = loadConfig(CONFIG);
  const missing = {
    ...config,
    runtime: {
      ...config.runtime,
      outputDirectory: mkdtempSync(path.join(tmpdir(), "person-empty-")),
    },
  };
  assert.equal(
    readStatus(statusPath(missing.runtime.outputDirectory, "w", "p")),
    null,
  );
});

test("an unreadable status is ignored rather than crashing the reader", () => {
  const { file, writer } = seeded();
  writer.update({ connection: "ready" });
  const raw = JSON.parse(readFileSync(file, "utf8")) as {
    schemaVersion: number;
  };
  assert.equal(raw.schemaVersion, 1);
  const { file: other } = seeded();
  assert.notEqual(file, other);
});

test("status never connects to anything", () => {
  // The command reads a file. There is no embodiment, no cognition process and
  // no socket, which is what makes watching Person free of side effects.
  const source = readFileSync(
    path.join(REPOSITORY, "apps/cli/src/commands.ts"),
    "utf8",
  );
  const statusSection = source.slice(
    source.indexOf("export function statusCommand("),
    source.indexOf("/** Reprints the status whenever"),
  );
  for (const forbidden of ["createEmbodiment", "PersonRuntime", "connect("])
    assert.ok(
      !statusSection.includes(forbidden),
      `status must not use ${forbidden}`,
    );
});

test("follow reprints only when the status changes", async () => {
  const config = loadConfig(CONFIG);
  const directory = mkdtempSync(path.join(tmpdir(), "person-follow-"));
  const file = statusPath(directory, config.worldId, config.personId);
  const writer = new StatusWriter(file, {
    command: "run",
    personId: config.personId,
    worldId: config.worldId,
    sessionId: "8f6c1c0e-3d0a-4a1e-9f3a-2b6f1d9c4e11",
  });

  const written: string[] = [];
  let ticks = 0;
  const followed = followStatus(
    { ...config, runtime: { ...config.runtime, outputDirectory: directory } },
    false,
    20,
    (text) => written.push(text),
    () => ticks++ < 12,
  );
  setTimeout(() => writer.update({ connection: "ready", health: 20 }), 80);
  await followed;

  assert.ok(written.length >= 2, "the change must be reprinted");
  assert.ok(
    written.length <= 6,
    "an unchanged status must not be reprinted every tick",
  );
  assert.match(written.at(-1) ?? "", /ready/);
});

test("statusCommand reports a missing store without throwing", () => {
  const result = statusCommand(loadConfig(CONFIG), true);
  assert.ok(result.code === 0 || result.code === 1);
  const body = JSON.parse(result.output) as { found?: boolean };
  if (result.code === 1) assert.equal(body.found, false);
});
