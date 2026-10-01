/**
 * C6 (ADR 0023): affective arbitration in record-only changes nothing (C6a);
 * active, it brings deliberation one signal earlier and says so (C6b).
 *
 * The same quiet-grove episode, through the real runtime and cognition with
 * scripted answers, once with affective arbitration off and once
 * record-only: identical deliberation requests, goals, skills and final
 * state. Only the affect-arbitration evidence differs, and deliberation
 * itself is never an appraisal input.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { temporaryDirectory } from "../support/harness.ts";
import {
  COGNITION,
  HOME,
  PERSON,
  WITHDRAW,
  journal,
  of,
  quietWorld,
  seedLedger,
  type Event,
} from "../support/quiet-grove.ts";
import { runEpisode } from "../support/runtime.ts";

async function live(affectArbitration: "off" | "record_only" | "active") {
  const outputDirectory = temporaryDirectory("person-affect-run-");
  const evidenceDirectory = temporaryDirectory("person-affect-");
  seedLedger(outputDirectory);
  // Hurt early, far from any emergency: unease is high when the first
  // failures arrive, so record-only has moments where affect would have
  // deliberated sooner.
  const world = quietWorld([0], 4, 5);
  await runEpisode({
    worldObject: world,
    cognitionCommand: COGNITION,
    evidenceDirectory,
    outputDirectory,
    personId: PERSON,
    home: HOME,
    maxDecisions: 400,
    maxTicks: 4000,
    deliberation: {
      mode: "active",
      answers: [WITHDRAW],
      habits: "active",
      affectArbitration,
    },
  });
  return { events: journal(evidenceDirectory), world };
}

/** What Person did, without ids that differ between any two runs. */
function behaviour(events: Event[]) {
  return events
    .filter((event) =>
      [
        "deliberation_requested",
        "deliberation_adopted",
        "deliberation_discarded",
        "deliberation_suppressed",
        "goal_selected",
        "skill_started",
        "skill_completed",
        "habit_evidence",
      ].includes(event.type),
    )
    .map((event) => {
      const p = event.payload;
      return [
        event.tick,
        event.type,
        p["trigger_key_full"] ?? p["goal_type"] ?? p["executed_skill"] ?? "",
        p["reason"] ?? p["status"] ?? p["verdict"] ?? "",
      ];
    });
}

test(
  "C6a: record-only affective arbitration records what affect would do and changes nothing Person does",
  { timeout: 600_000 },
  async () => {
    const off = await live("off");
    const shadow = await live("record_only");

    assert.deepEqual(behaviour(shadow.events), behaviour(off.events));
    assert.deepEqual(
      shadow.world.snapshot().inventory,
      off.world.snapshot().inventory,
    );
    assert.ok(behaviour(off.events).length > 20, "a run that did something");

    assert.equal(of(off.events, "affective_arbitration_shadow").length, 0);
    const recorded = of(shadow.events, "affective_arbitration_shadow");
    if (process.env.AFFECT_DUMP)
      for (const event of recorded) console.log(JSON.stringify(event.payload));
    assert.ok(
      recorded.some(
        (event) =>
          event.payload["affect_advanced_threshold"] === true &&
          event.payload["unease_band"] === "high",
      ),
      "record-only saw affect want earlier deliberation, and behaviour still did not change",
    );
    for (const event of recorded) {
      assert.equal(event.payload["mode"], "record_only");
      assert.ok(!("unease" in event.payload), "bands, never values");
    }
    for (const event of of(shadow.events, "deliberation_requested"))
      assert.ok(
        !("affect_changed_outcome" in event.payload),
        "record-only adds no counterfactual to a request",
      );

    // Deliberation is never an appraisal input.
    for (const run of [off, shadow])
      for (const event of of(run.events, "affect_appraised"))
        assert.ok(
          !/deliberation|habit|arbitration/.test(
            String(event.payload["trigger"]),
          ),
          `appraised ${String(event.payload["trigger"])}`,
        );
  },
);

test(
  "C6b: high unease brings deliberation one failure earlier, and the journal says it would not otherwise have happened yet",
  { timeout: 600_000 },
  async () => {
    const off = await live("off");
    const active = await live("active");

    const [baseline] = of(off.events, "deliberation_requested");
    const [advanced] = of(active.events, "deliberation_requested");
    assert.ok(baseline && advanced);
    assert.equal(
      (baseline.payload["signal"] as Record<string, unknown>)["count"],
      3,
    );
    assert.equal(
      (advanced.payload["signal"] as Record<string, unknown>)["count"],
      2,
      "one signal earlier",
    );
    assert.ok(advanced.tick < baseline.tick);
    assert.equal(advanced.payload["baseline_would_fire"], false);
    assert.equal(advanced.payload["affect_changed_outcome"], true);
    assert.equal(
      advanced.payload["trigger_key_full"],
      "repeated_failure:ESTABLISH_TOOLS",
    );

    // The earlier remedy still has to earn its success the ordinary way.
    const resolved = of(active.events, "habit_evidence").map((event) => [
      event.payload["verdict"],
      event.payload["reason"],
    ]);
    assert.deepEqual(resolved, [["success", "stable"]]);

    // What the model saw carried no affect.
    for (const event of of(active.events, "deliberation_requested"))
      assert.ok(!JSON.stringify(event.payload).includes("unease"));
  },
);
