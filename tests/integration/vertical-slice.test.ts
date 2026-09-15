import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { FixtureWorld } from "#fixture-world";
import { REPOSITORY, temporaryDirectory } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

const COGNITION = ["uv", "run", "person-cognition"];

interface JournalEvent {
  event_id: string;
  previous_event_id: string | null;
  episode_id: string;
  type: string;
  training_context: string;
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

test(
  "Person survives, learns, restarts and keeps what it learned",
  { timeout: 600000 },
  async (t) => {
    const evidenceDirectory = temporaryDirectory("person-slice-evidence-");
    const outputDirectory = temporaryDirectory("person-slice-runs-");
    const world = FixtureWorld.fromFile(
      path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
    );

    await t.test(
      "first episode: establish food, shelter, tools and storage",
      async () => {
        const { report } = await runEpisode({
          worldObject: world,
          cognitionCommand: COGNITION,
          evidenceDirectory,
          outputDirectory,
          maxDecisions: 16,
          episodeId: "ep_first",
        });

        assert.ok(
          report.decisions.length > 4,
          "the episode should make several decisions",
        );
        const executed = report.decisions.map(
          (decision) => decision.executedSkill,
        );
        const goals = new Set(
          report.decisions.map((decision) => decision.goalType),
        );

        assert.ok(
          goals.has("SECURE_FOOD"),
          "Person should recognise it is hungry",
        );
        assert.ok(
          executed.includes("gather_plant_food") ||
            executed.includes("hunt_safe_passive_animals"),
          `food was never gathered: ${executed.join(", ")}`,
        );
        assert.ok(
          executed.includes("eat_to_target"),
          "Person should eat what it gathered",
        );
        assert.ok(
          world.snapshot().food >= 16,
          "hunger should have been dealt with",
        );

        assert.ok(goals.has("SECURE_SHELTER"));
        assert.ok(executed.includes("gather_wood"));
        assert.ok(executed.includes("build_basic_shelter"));

        // Every decision is explainable end to end.
        for (const decision of report.decisions) {
          assert.ok(
            decision.contextId.startsWith("h_"),
            "a semantic context must be recorded",
          );
          assert.ok(decision.routineId.startsWith("r_"));
          assert.ok(
            ["learned", "fallback"].includes(decision.learnedOrFallback),
          );
          assert.ok(
            ["ACCEPT", "REJECT", "REPLACE", "PREEMPT"].includes(
              decision.validation,
            ),
          );
          assert.equal(typeof decision.outcomeMessageId, "string");
        }
        assert.equal(
          report.rngSeed,
          1,
          "the fixture seed is recorded for replay",
        );
        assert.equal(report.trainingContext, "fixture");
        assert.equal(report.learningMode, "off");

        const written = readdirSync(path.join(outputDirectory, "reports"));
        assert.ok(
          written.some((name) => name.includes("ep_first")),
          "a report file is written",
        );
      },
    );

    await t.test(
      "a threat preempts the plan and the emergency is attributed",
      async () => {
        const events = readJournal(evidenceDirectory);
        const overrides = events.filter(
          (event) => event.type === "emergency_override",
        );
        assert.ok(
          overrides.length > 0,
          "the injected hostile should have triggered the kernel",
        );
        const interrupted = events.filter(
          (event) =>
            event.type === "skill_interrupted" &&
            event.payload["executed_skill"] !==
              event.payload["requested_skill"],
        );
        assert.ok(
          interrupted.length > 0,
          "a plan should have been replaced mid-episode",
        );
        for (const event of interrupted)
          assert.equal(
            event.payload["executed_skill"],
            "flee",
            "an immediate threat is answered by fleeing",
          );
      },
    );

    await t.test("evidence is an unbroken, replayable chain", () => {
      const events = readJournal(evidenceDirectory);
      assert.ok(events.length > 10);
      const ids = new Set(events.map((event) => event.event_id));
      assert.equal(ids.size, events.length, "event ids must be unique");
      assert.equal(events[0]?.previous_event_id, null);
      for (let index = 1; index < events.length; index++)
        assert.equal(
          events[index]?.previous_event_id,
          events[index - 1]?.event_id,
        );
      for (const event of events)
        assert.equal(event.training_context, "fixture");
      assert.ok(events.some((event) => event.type === "episode_started"));
      assert.ok(events.some((event) => event.type === "routine_outcome"));
    });

    await t.test(
      "a restarted process reuses the evidence it left behind",
      async () => {
        const before = readJournal(evidenceDirectory);
        const lastBefore = before.at(-1);
        assert.ok(lastBefore);

        const { report } = await runEpisode({
          worldObject: world,
          cognitionCommand: COGNITION,
          evidenceDirectory,
          outputDirectory,
          maxDecisions: 8,
          learningMode: "supervised",
          episodeId: "ep_second",
        });
        assert.ok(report.decisions.length > 0);

        const after = readJournal(evidenceDirectory);
        assert.ok(
          after.length > before.length,
          "the second episode appends to the same journal",
        );
        const fresh = after.slice(before.length);
        assert.equal(
          fresh[0]?.previous_event_id,
          lastBefore.event_id,
          "the chain continues across the restart",
        );
        assert.ok(fresh.every((event) => event.episode_id === "ep_second"));

        const selections = fresh.filter(
          (event) => event.type === "routine_selected",
        );
        assert.ok(
          selections.length > 0,
          "the restarted process should select routines",
        );
        const informed = selections.filter((event) =>
          ((event.payload["candidates"] ?? []) as { attempts: number }[]).some(
            (candidate) => candidate.attempts > 0,
          ),
        );
        assert.ok(
          informed.length > 0,
          "at least one decision after the restart must be informed by earlier evidence",
        );

        const snapshots = readdirSync(
          path.join(evidenceDirectory, "snapshots"),
        );
        assert.ok(
          snapshots.length > 0,
          "a snapshot should exist to speed the next restart",
        );
      },
    );
  },
);
