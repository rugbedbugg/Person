import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import type { EpisodeReport } from "#node-runtime";
import type { FixtureWorldDefinition } from "#fixture-world";
import { baseConfig } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

/**
 * Causal hypotheses and controlled experiments, end to end (ADR 0012): the
 * real runtime, the real cognition process, a fixture body in a world with a
 * rule nothing in Person is told. While it rains, berry bushes break and give
 * nothing.
 *
 * Person, hungry, gathers berries in the rain and gets none, then in clear
 * weather and gets some. From that variation it proposes a typed hypothesis,
 * tests it with trials in both weathers through the ordinary goal path, and
 * comes to hold it. The same life a thousand blocks along X, or with a hidden
 * hazard it never perceives, thinks exactly the same; a world without the
 * rule decides exactly the same until an outcome first differs.
 *
 * TESTED IN FIXTURE. None of this is live Minecraft evidence.
 */

const COGNITION = ["uv", "run", "person-cognition"];
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g;
const CAUSAL = new Set([
  "causal_trial",
  "hypothesis_proposed",
  "hypothesis_rejected",
  "hypothesis_evidence",
  "investigation_changed",
]);

interface JournalEvent {
  type: string;
  tick: number;
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

const causal = (events: JournalEvent[]): string[] =>
  events
    .filter((event) => CAUSAL.has(event.type))
    .map((event) =>
      `${event.type} ${JSON.stringify(event.payload)}`.replace(UUID, "<id>"),
    );

const decisions = (report: EpisodeReport): string[] =>
  report.decisions.map(
    (decision) =>
      `${decision.goalType}:${decision.requestedSkill}->${decision.executedSkill}`,
  );

interface Life {
  dx?: number;
  rule?: boolean;
  hiddenLava?: boolean;
  learningMode?: "off" | "shadow" | "supervised";
}

async function life({
  dx = 0,
  rule = true,
  hiddenLava = false,
  learningMode = "supervised",
}: Life = {}) {
  const at = (x: number, y: number, z: number) => ({ x: x + dx, y, z });
  // A short shower at the start, then spells of rain and clear weather.
  const events: FixtureWorldDefinition["events"] = [
    { atTick: 0, type: "weather", weather: "rain" },
    { atTick: 40, type: "weather", weather: "clear" },
  ];
  for (let tick = 1000, index = 0; tick < 24000; tick += 600, index++)
    events.push({
      atTick: tick,
      type: "weather",
      weather: index % 2 === 0 ? "rain" : "clear",
    });
  const blocks: FixtureWorldDefinition["blocks"] = [];
  if (hiddenLava) {
    // Behind Person and behind a wall: physically there, never perceived.
    for (let x = -3; x <= 3; x++)
      for (let y = 64; y <= 67; y++)
        blocks.push({ position: at(x, y, 3), name: "dirt" });
    blocks.push({ position: at(0, 64, 6), name: "lava" });
  }
  const config = baseConfig();
  type Box = (typeof config.world.resourceAreas)[number];
  const shifted = (box: Box): Box => ({
    min: at(box.min.x, box.min.y, box.min.z),
    max: at(box.max.x, box.max.y, box.max.z),
  });
  const run = await runEpisode({
    home: at(0, 64, 0),
    world: {
      name: "causal-learning",
      spawn: at(0, 64, 0),
      spawnYaw: 0,
      vitals: { health: 20, food: 15, saturation: 0, air: 300, armor: 0 },
      // Equipped, but with nothing to build a shelter from: Person stays
      // out among the bushes rather than sealing itself in.
      inventory: [{ name: "stone_pickaxe", count: 1 }],
      blocks,
      clusters: [
        {
          name: "sweet_berry_bush",
          center: at(0, 64, -8),
          count: 40,
          spread: 4,
        },
      ],
      events,
      hiddenRules: rule
        ? [
            {
              kind: "barren_while_weather",
              weather: "rain",
              blocks: ["sweet_berry_bush"],
            },
          ]
        : [],
    },
    config: {
      world: {
        home: at(0, 64, 0),
        exploration: shifted(config.world.exploration),
        resourceAreas: config.world.resourceAreas.map(shifted),
        protectedAreas: config.world.protectedAreas.map(shifted),
      },
    },
    learningMode,
    cognitionCommand: COGNITION,
    maxDecisions: 60,
  });
  return { ...run, events: readJournal(run.evidenceDirectory) };
}

test(
  "a hidden rule is noticed, tested by experiment and believed",
  { timeout: 600000 },
  async () => {
    const { report, events } = await life();
    const proposed = events.filter((e) => e.type === "hypothesis_proposed");
    const rain = proposed
      .map((e) => e.payload["hypothesis"] as Record<string, unknown>)
      .find(
        (h) =>
          JSON.stringify(h["condition"]) ===
          JSON.stringify({ variable: "weather", value: "rain" }),
      );
    assert.ok(rain, decisions(report).join(", "));
    assert.equal(rain["intervention"], "gather_plant_food");
    assert.deepEqual(rain["outcome"], {
      fact: "plant_food",
      direction: "less_likely",
    });

    // Trials went through the ordinary path: planned, validated, executed as
    // requested, using only the intervention (or a glance to find a bush).
    const trials = report.decisions.filter((d) => d.goalType === "INVESTIGATE");
    assert.ok(trials.length >= 8, decisions(report).join(", "));
    for (const trial of trials) {
      assert.ok(["gather_plant_food", "look"].includes(trial.requestedSkill));
      assert.equal(trial.executedSkill, trial.requestedSkill);
    }

    const interventional = events.filter(
      (e) =>
        e.type === "hypothesis_evidence" &&
        e.payload["hypothesis_id"] === rain["hypothesis_id"] &&
        e.payload["kind"] === "interventional" &&
        e.payload["verdict"] !== "inconclusive",
    );
    const arms = new Set(interventional.map((e) => e.payload["arm"]));
    assert.deepEqual([...arms].sort(), ["absent", "held"], "both sides tested");

    const concluded = events.find(
      (e) =>
        e.type === "investigation_changed" &&
        e.payload["change"] === "concluded",
    );
    assert.ok(concluded, "the experiment finished");
    const standing = concluded.payload["standing"] as Record<string, unknown>;
    assert.equal(standing["standing"], "supported");
    assert.equal(standing["controlled"], true);

    const serialized = JSON.stringify(
      events.filter((e) => CAUSAL.has(e.type)).map((e) => e.payload),
    );
    for (const forbidden of ['"x"', '"z"', "yaw", "homeDistance", "position"])
      assert.ok(
        !serialized.includes(forbidden),
        `causal state holds ${forbidden}`,
      );
  },
);

test(
  "where the world is on the grid, and hazards Person never perceives, change nothing it concludes",
  { timeout: 600000 },
  async () => {
    const here = await life();
    const there = await life({ dx: 1000 });
    const hidden = await life({ hiddenLava: true });
    assert.ok(causal(here.events).length > 0);
    assert.deepEqual(causal(there.events), causal(here.events), "+1000 X");
    assert.deepEqual(decisions(there.report), decisions(here.report));
    assert.deepEqual(causal(hidden.events), causal(here.events), "hidden lava");
  },
);

test(
  "a different hidden mechanic changes nothing until a consequence is observed",
  { timeout: 600000 },
  async () => {
    const barren = await life();
    const fruitful = await life({ rule: false });
    const statuses = (report: EpisodeReport): string[] =>
      report.decisions.map((d) => d.status);
    const first = statuses(barren.report).findIndex(
      (status, index) => status !== statuses(fruitful.report)[index],
    );
    assert.ok(first >= 0, "the rule does make a difference, eventually");
    // Up to and including the first outcome that differed, Person decided
    // exactly the same in both worlds: the rule itself was never seen.
    assert.deepEqual(
      decisions(barren.report).slice(0, first + 1),
      decisions(fruitful.report).slice(0, first + 1),
    );
  },
);

test(
  "with learning off, nothing is hypothesised and nothing is investigated",
  { timeout: 600000 },
  async () => {
    const { report, events } = await life({ learningMode: "off" });
    assert.deepEqual(causal(events), []);
    assert.ok(report.decisions.every((d) => d.goalType !== "INVESTIGATE"));
  },
);
