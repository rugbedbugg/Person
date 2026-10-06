/**
 * The air-deprivation emergency through the real runtime and cognition (ADR
 * 0019), with a synthetic identity: what the kernel substitutes, that one air
 * emergency is one emergency however often it is seen, and that a death and
 * respawn leave nothing of it behind.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { FixtureWorld } from "#fixture-world";
import { temporaryDirectory } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";
import { type Position } from "#minecraft";

const COGNITION = ["uv", "run", "person-cognition"];

function pool(options: {
  lid: boolean;
  entities?: { name: string; position: Position }[];
}) {
  const blocks: { name: string; position: Position }[] = [];
  for (let x = -3; x <= 3; x++)
    for (let z = -3; z <= 3; z++)
      for (let y = 57; y <= 63; y++)
        blocks.push({
          name: y >= 60 && options.lid ? "stone" : "water",
          position: { x, y, z },
        });
  if (options.lid)
    for (let x = -6; x <= 6; x++)
      for (let z = -6; z <= 6; z++)
        if (Math.abs(x) > 3 || Math.abs(z) > 3)
          for (let y = 60; y <= 63; y++)
            blocks.push({ name: "stone", position: { x, y, z } });
  return new FixtureWorld({
    name: "pool",
    seed: 5,
    startTick: 0,
    timeOfDay: 1000,
    biome: "plains",
    groundLevel: 63,
    // Spawn, and respawn, on dry land beside the pool.
    spawn: { x: 12, y: 64, z: 12 },
    spawnYaw: 0,
    vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
    inventory: [],
    blocks,
    clusters: [],
    entities: options.entities ?? [],
    containers: [],
    events: [],
  });
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

async function submerged(
  world: FixtureWorld,
  air: number,
): Promise<FixtureWorld> {
  world.teleport({ x: 0, y: 58, z: 0 });
  world.setVitals({ air });
  return world;
}

test(
  "with a hostile nearby and air critical, the runtime restores air instead of fleeing",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-air-");
    const world = await submerged(
      pool({
        lid: false,
        entities: [{ name: "zombie", position: { x: 6, y: 64, z: 0 } }],
      }),
      60,
    );
    await runEpisode({
      worldObject: world,
      cognitionCommand: COGNITION,
      evidenceDirectory,
      personId: "test-person-000",
      maxDecisions: 2,
    });
    const events = journal(evidenceDirectory);
    const first = events.find((e) => e.type === "emergency_override");
    assert.equal(first?.payload["trigger"], "suffocation");
    assert.equal(first?.payload["action"], "restore_air");
    const escape = events.find(
      (e) =>
        e.type === "skill_started" &&
        e.payload["executed_skill"] === "restore_air",
    );
    assert.ok(escape, "restore_air ran");
    assert.ok(
      !events.some(
        (e) =>
          e.type === "emergency_override" &&
          e.payload["trigger"] === "suffocation" &&
          e.payload["action"] !== "restore_air",
      ),
      "an air emergency is never routed to flee",
    );
  },
);

test(
  "an air emergency with no way out is one emergency per decision, and a respawn leaves none of it",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-air-");
    const world = await submerged(pool({ lid: true }), 82);
    const { report } = await runEpisode({
      worldObject: world,
      cognitionCommand: COGNITION,
      evidenceDirectory,
      personId: "test-person-000",
      maxDecisions: 24,
      death: "respawn",
    });
    const events = journal(evidenceDirectory);
    const overrides = events.filter((e) => e.type === "emergency_override");
    assert.ok(
      overrides.length <= report.decisions.length,
      "never more than one per decision",
    );
    const died = events.findIndex((e) => e.type === "person_died");
    const respawned = events.findIndex((e) => e.type === "person_respawned");
    assert.ok(
      died >= 0 && respawned > died,
      "the body drowned and was respawned",
    );
    // An emergency outcome is journalled against the skill it preempted.
    const failed = events.filter(
      (e) =>
        (e.type === "skill_failed" || e.type === "skill_interrupted") &&
        e.payload["executed_skill"] === "restore_air" &&
        e.payload["status"] === "FAILED",
    );
    assert.ok(
      failed.length >= 1,
      "the escape failed, bounded, rather than looping",
    );
    assert.ok(
      !events
        .slice(respawned)
        .some(
          (e) =>
            e.type === "emergency_override" &&
            e.payload["trigger"] === "suffocation",
        ),
      "no air emergency lingers after the respawn",
    );
    const critical = events.filter(
      (e) =>
        e.type === "affect_appraised" &&
        e.payload["trigger"] === "breath_critical",
    );
    assert.ok(
      critical.length <= 1,
      `breath_critical felt ${critical.length} times in one submersion`,
    );
  },
);
