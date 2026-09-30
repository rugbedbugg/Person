/**
 * Death through the real runtime and real cognition (ADR 0017, I3), with
 * synthetic identities. The runtime, never cognition, observes a death and
 * decides whether it is terminal; a respawn continues the same Person; a
 * permadeath ends it for good, whatever the configuration later says.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { FixtureWorld } from "#fixture-world";
import { temporaryDirectory } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

const COGNITION = ["uv", "run", "person-cognition"];

// Barely alive, with a zombie a step away in the open.
const doomed = {
  name: "doomed",
  seed: 51,
  startTick: 0,
  timeOfDay: 1000,
  biome: "plains",
  groundLevel: 63,
  spawn: { x: 0, y: 64, z: 0 },
  spawnYaw: 0,
  vitals: { health: 1, food: 20, saturation: 5, air: 300, armor: 0 },
  inventory: [],
  blocks: [],
  clusters: [],
  entities: [{ name: "zombie", position: { x: 0, y: 64, z: -2 } }],
  containers: [],
  events: [],
};

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
        JSON.parse(line) as {
          type: string;
          person_id: string;
          payload: Record<string, unknown>;
        },
    );
}

test(
  "a respawn continues the same Person in the same session",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-life-");
    const { report } = await runEpisode({
      worldObject: new FixtureWorld(doomed),
      cognitionCommand: COGNITION,
      evidenceDirectory,
      personId: "test-person-000",
      maxDecisions: 6,
      death: "respawn",
    });
    const events = journal(evidenceDirectory);
    const count = (type: string) =>
      events.filter((e) => e.type === type).length;
    assert.ok(count("person_died") >= 1, "the body died");
    assert.ok(count("person_respawned") >= 1, "and came back");
    assert.equal(count("person_terminated"), 0);
    assert.equal(count("person_founded"), 1, "no new Person");
    assert.equal(count("session_started"), 1, "no new session");
    assert.ok(events.every((e) => e.person_id === "test-person-000"));
    assert.ok(
      events.some(
        (e) => e.type === "memory_encoded" && e.payload["kind"] === "died",
      ),
      "the death is remembered",
    );
    assert.notEqual(report.reason, "death", "the episode ran on");
  },
);

test(
  "a permadeath ends the Person, and no later configuration resumes it",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-life-");
    const { report } = await runEpisode({
      worldObject: new FixtureWorld(doomed),
      cognitionCommand: COGNITION,
      evidenceDirectory,
      personId: "test-person-000",
      maxDecisions: 6,
      death: "permadeath",
    });
    assert.equal(report.reason, "death");
    const events = journal(evidenceDirectory);
    const died = events.filter((e) => e.type === "person_died");
    assert.equal(died.length, 1);
    assert.equal(died[0]!.payload["terminal"], true);
    assert.ok(events.some((e) => e.type === "person_terminated"));
    const before = events.length;

    // The operator changes the configuration to respawn: nothing resumes.
    const again = await runEpisode({
      worldObject: new FixtureWorld({
        ...doomed,
        vitals: { ...doomed.vitals, health: 20 },
        entities: [],
      }),
      cognitionCommand: COGNITION,
      evidenceDirectory,
      personId: "test-person-000",
      maxDecisions: 6,
      death: "respawn",
    });
    assert.equal(again.report.outcome, "failed");
    assert.equal(again.report.decisions.length, 0, "no decision was made");
    assert.equal(
      journal(evidenceDirectory).length,
      before,
      "a terminated Person's evidence is read, never extended",
    );
  },
);

/** A body that cannot be brought back, like a Minecraft adapter without it. */
class Unrevivable extends FixtureWorld {
  override respawn = undefined as unknown as FixtureWorld["respawn"];
}

test(
  "a Person left awaiting a respawn is respawned by the next run before it perceives anything",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-life-");
    const first = await runEpisode({
      worldObject: new Unrevivable(doomed),
      cognitionCommand: COGNITION,
      evidenceDirectory,
      personId: "test-person-000",
      maxDecisions: 6,
      death: "respawn",
    });
    assert.equal(first.report.reason, "death", "no respawn was possible");
    const awaiting = journal(evidenceDirectory);
    assert.equal(
      awaiting.filter((e) => e.type === "person_respawned").length,
      0,
    );

    await runEpisode({
      worldObject: new FixtureWorld({ ...doomed, entities: [] }),
      cognitionCommand: COGNITION,
      evidenceDirectory,
      personId: "test-person-000",
      maxDecisions: 3,
      death: "respawn",
    });
    const fresh = journal(evidenceDirectory).slice(awaiting.length);
    const respawned = fresh.findIndex((e) => e.type === "person_respawned");
    const perceived = fresh.findIndex(
      (e) => e.type === "goal_selected" || e.type === "memory_encoded",
    );
    assert.ok(respawned >= 0, "the new run brought the body back");
    assert.ok(
      perceived < 0 || respawned < perceived,
      "before anything was perceived",
    );
    assert.equal(
      journal(evidenceDirectory).filter((e) => e.type === "person_founded")
        .length,
      1,
      "the same Person",
    );
  },
);
