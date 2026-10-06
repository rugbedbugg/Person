import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import type { EpisodeReport } from "#node-runtime";
import { baseConfig } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

/**
 * Projects, end to end: the real runtime, the real cognition process, a
 * fixture body.
 *
 * Person is fed, equipped and carrying building materials. It builds its
 * shelter, which makes that place home in its own map; calm and at home, it
 * takes up improving the home. The same life placed a thousand blocks along
 * X must produce the same projects and the same decisions, because nothing
 * about projects may depend on where the world is on Minecraft's grid.
 *
 * TESTED IN FIXTURE. None of this is live Minecraft evidence.
 */

const COGNITION = ["uv", "run", "person-cognition"];
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g;

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

const COGNITIVE = new Set([
  "goal_selected",
  "routine_selected",
  "place_formed",
  "place_visited",
  "project_started",
  "project_changed",
  "memory_recalled",
]);

const mind = (events: JournalEvent[]): string[] =>
  events
    .filter((event) => COGNITIVE.has(event.type))
    .map((event) =>
      `${event.type} ${JSON.stringify(event.payload)}`.replace(UUID, "<id>"),
    );

const requests = (report: EpisodeReport): string[] =>
  report.decisions.map(
    (decision) =>
      `${decision.goalType}:${decision.requestedSkill}->${decision.executedSkill}`,
  );

async function lifeAt(dx: number) {
  const at = (x: number, y: number, z: number) => ({ x: x + dx, y, z });
  const config = baseConfig();
  type Box = (typeof config.world.resourceAreas)[number];
  const shifted = (box: Box): Box => ({
    min: at(box.min.x, box.min.y, box.min.z),
    max: at(box.max.x, box.max.y, box.max.z),
  });
  return runEpisode({
    home: at(0, 64, 0),
    world: {
      name: "projects",
      spawn: at(0, 64, 0),
      spawnYaw: 0,
      vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
      inventory: [
        { name: "dirt", count: 64 },
        { name: "stone_pickaxe", count: 1 },
        { name: "cooked_beef", count: 8 },
      ],
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
    maxDecisions: 10,
  });
}

test(
  "a calm Person with a home it built takes up a project, wherever the world is",
  { timeout: 300000 },
  async () => {
    const here = await lifeAt(0);
    const there = await lifeAt(1000);

    const events = readJournal(here.evidenceDirectory);
    const started = events.filter((event) => event.type === "project_started");
    assert.ok(started.length >= 1, requests(here.report).join(", "));
    const project = started[0]!.payload["project"] as Record<string, unknown>;
    assert.equal(project["kind"], "improve_home");
    assert.match(String(project["anchor"]), /^place_\d+$/);

    assert.deepEqual(requests(there.report), requests(here.report));
    assert.deepEqual(mind(readJournal(there.evidenceDirectory)), mind(events));

    const serialized = JSON.stringify(
      events
        .filter((event) => event.type.startsWith("project_"))
        .map((event) => event.payload),
    );
    for (const forbidden of ['"x"', '"z"', "yaw", "homeDistance", "1000"])
      assert.ok(
        !serialized.includes(forbidden),
        `project state holds ${forbidden}`,
      );
  },
);
