import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import type { EpisodeReport } from "#node-runtime";
import type { FixtureWorldDefinition } from "#fixture-world";
import { baseConfig } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

/**
 * The spatial firewall, end to end (ADR 0008).
 *
 * Person's sense of place is built from what it felt of its own motion and
 * what it saw, both relative to itself. So two worlds that differ only in
 * where everything is on Minecraft's grid must be indistinguishable to it:
 * every decision, every place it forms, every estimate, every memory. If
 * shifting the whole world a thousand blocks changes anything in Person's
 * mind, an absolute frame has leaked through.
 *
 * TESTED IN FIXTURE. None of this is live Minecraft evidence.
 */

const COGNITION = ["uv", "run", "person-cognition"];

interface JournalEvent {
  type: string;
  payload: Record<string, unknown>;
}

function readJournal(evidenceDirectory: string): JournalEvent[] {
  const journal = path.join(evidenceDirectory, "journal");
  return readdirSync(journal)
    .filter((name) => name.endsWith(".jsonl"))
    .sort()
    .flatMap((name) =>
      readFileSync(path.join(journal, name), "utf8").split("\n"),
    )
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as JournalEvent);
}

/** Cognition's own records, with software identifiers blanked. */
const COGNITIVE = new Set([
  "goal_selected",
  "routine_selected",
  "information_search",
  "memory_encoded",
  "memory_recalled",
  "place_formed",
  "place_visited",
]);
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g;

const mind = (events: JournalEvent[]): string[] =>
  events
    .filter((event) => COGNITIVE.has(event.type))
    .map((event) =>
      `${event.type} ${JSON.stringify(event.payload)}`.replace(UUID, "<id>"),
    );

const requests = (report: EpisodeReport): string[] =>
  report.decisions.map(
    (decision) =>
      `${decision.requestedSkill}(${JSON.stringify(decision.requestedParameters)})->${decision.executedSkill}:${decision.validation}`,
  );

/** One scenario, placed `dx` blocks along X on Minecraft's grid. */
async function lifeAt(dx: number) {
  const at = (x: number, y: number, z: number) => ({ x: x + dx, y, z });
  const blocks: FixtureWorldDefinition["blocks"] = [
    // A tree behind Person, and another off to its right: it must look, walk
    // and turn, so self-motion is exercised and not just stillness.
    ...[64, 65, 66].map((y) => ({ position: at(0, y, 8), name: "oak_log" })),
    ...[64, 65, 66].map((y) => ({ position: at(10, y, -3), name: "oak_log" })),
  ];
  const config = baseConfig();
  const shifted = (box: {
    min: { x: number; y: number; z: number };
    max: { x: number; y: number; z: number };
  }) => ({
    min: at(box.min.x, box.min.y, box.min.z),
    max: at(box.max.x, box.max.y, box.max.z),
  });
  return runEpisode({
    home: at(0, 64, 0),
    world: {
      name: "spatial",
      spawn: at(0, 64, 0),
      spawnYaw: 0,
      vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
      blocks,
    },
    config: {
      world: {
        home: at(0, 64, 0),
        exploration: shifted(config.world.exploration),
        resourceAreas: config.world.resourceAreas.map(shifted),
        protectedAreas: config.world.protectedAreas.map(shifted),
      },
    },
    cognitionCommand: COGNITION,
    maxDecisions: 14,
  });
}

test(
  "moving the whole world a thousand blocks changes nothing in Person's mind",
  { timeout: 300000 },
  async () => {
    const here = await lifeAt(0);
    const there = await lifeAt(1000);

    // The bodies really were in different places.
    assert.notEqual(
      here.world.snapshot().position.x,
      there.world.snapshot().position.x,
    );

    assert.deepEqual(requests(there.report), requests(here.report));
    const mindHere = mind(readJournal(here.evidenceDirectory));
    const mindThere = mind(readJournal(there.evidenceDirectory));
    assert.deepEqual(mindThere, mindHere);

    // And the scenario was not vacuous: Person moved, and formed places at
    // estimates away from where it began.
    const places = readJournal(here.evidenceDirectory).filter((event) =>
      event.type.startsWith("place_"),
    );
    assert.ok(places.length >= 2, `${places.length} place records`);
    assert.ok(
      places.some((event) => {
        const estimate = event.payload["estimate"] as Record<string, number>;
        return Math.hypot(estimate["forward"]!, estimate["left"]!) > 1;
      }),
      "some place was formed or revisited after travelling",
    );
    assert.ok(
      requests(here.report).some((request) =>
        request.startsWith("gather_wood"),
      ),
    );
  },
);

test(
  "no coordinate, heading or ledger value reaches the spatial records",
  { timeout: 300000 },
  async () => {
    const life = await lifeAt(1000);
    const spatial = readJournal(life.evidenceDirectory).filter(
      (event) =>
        event.type.startsWith("place_") ||
        (event.type === "episode_ended" && "self_estimate" in event.payload),
    );
    assert.ok(spatial.length > 0);
    const serialized = JSON.stringify(spatial.map((event) => event.payload));
    for (const forbidden of [
      '"x"',
      '"y"',
      '"z"',
      "yaw",
      "pitch",
      "homeDistance",
      "1000",
    ])
      assert.ok(
        !serialized.includes(forbidden),
        `spatial records hold ${forbidden}`,
      );
  },
);
