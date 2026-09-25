import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { FixtureWorld } from "#fixture-world";
import { readStatus, shelterPlan, statusPath } from "#node-runtime";
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
        // What matters is that the shelter stands. Since information seeking,
        // looking before acting costs time, and the fixture's scheduled zombie
        // now arrives while the last blocks are going in: the kernel preempts
        // with flee, so the call is correctly attributed to flee even though
        // the shelter was finished. Assert the request and the world, not
        // which skill happened to be running when the threat arrived.
        const requested = report.decisions.map(
          (decision) => decision.requestedSkill,
        );
        assert.ok(requested.includes("build_basic_shelter"));
        assert.ok(
          shelterPlan({ x: 0, y: 64, z: 0 }).every(
            (position) => world.blockAt(position)?.solid === true,
          ),
          "the shelter is actually standing",
        );

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
          // Room for bounded searches as well as routine work. A restarted
          // Person recalls where it looked and searches there more briefly,
          // but the fixture's zombie makes it flee somewhere it has not
          // searched, and "not found" was only ever about the other place.
          maxDecisions: 28,
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

test(
  "an operator-marked run is recorded as contaminated",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-marked-evidence-");
    const outputDirectory = temporaryDirectory("person-marked-runs-");
    const world = FixtureWorld.fromFile(
      path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
    );
    const { report } = await runEpisode({
      worldObject: world,
      cognitionCommand: ["uv", "run", "person-cognition"],
      evidenceDirectory,
      outputDirectory,
      maxDecisions: 2,
      episodeId: "ep_marked",
      operatorIntervention: { reason: "operator teleported to Person" },
    });
    assert.ok(report.decisions.length > 0);

    // The marker travels with the evidence, so a debug session can never be
    // mistaken for a counted acceptance run when the journal is read later.
    const events = readJournal(evidenceDirectory).filter(
      (event) =>
        event.type === "episode_started" || event.type === "episode_ended",
    );
    assert.ok(events.length > 0);
    for (const event of events)
      assert.ok(
        ((event.payload["reason_codes"] ?? []) as string[]).includes(
          "operator_intervention",
        ),
        `${event.type} must carry the contamination marker`,
      );

    const status = readStatus(
      statusPath(outputDirectory, report.worldId, report.personId),
    );
    assert.ok(status);
    assert.equal(status.operatorIntervention.flagged, true);
    assert.equal(
      status.operatorIntervention.reason,
      "operator teleported to Person",
    );
    assert.equal(status.command, "run");
    assert.ok(status.decisions > 0);
    assert.equal(
      status.connection,
      "disconnected",
      "the runtime shut the body down",
    );
  },
);

test(
  "an ordinary run carries no contamination marker",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-clean-evidence-");
    const outputDirectory = temporaryDirectory("person-clean-runs-");
    const world = FixtureWorld.fromFile(
      path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
    );
    await runEpisode({
      worldObject: world,
      cognitionCommand: ["uv", "run", "person-cognition"],
      evidenceDirectory,
      outputDirectory,
      maxDecisions: 2,
      episodeId: "ep_clean",
    });
    for (const event of readJournal(evidenceDirectory))
      assert.ok(
        !((event.payload["reason_codes"] ?? []) as string[]).includes(
          "operator_intervention",
        ),
        "a clean run must not be marked",
      );
  },
);
