import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import {
  loadPlan,
  runOne,
  type ExperimentPlan,
} from "../../apps/cli/src/experiment.ts";
import { REPOSITORY, temporaryDirectory } from "../support/harness.ts";

/**
 * With interoception off, R2 reproduces R1.5 appraisal exactly (ADR 0014).
 *
 * Three generations of reference, each immutable once recorded:
 *
 * - `r15-affect/`, historical, at `5548bbd`, with phantom SECURE_FOOD
 *   completions;
 * - `r15-affect-corrected/`, after goals already satisfied stopped being
 *   queued (ADR 0015), under the old hostile physics;
 * - `r15-affect-fixture-realism/`, after hostiles stopped walking and attacking
 *   through walls (ADR 0016): the current baseline, which the same scenarios
 *   run now must reproduce exactly.
 *
 * Each step is pinned. Corrected to fixture-realism: B and C identical; D
 * identical up to its first divergence, with a hostile-physics event (from the
 * fixture's operator-side diagnostics) between the last identical decision and
 * the first different one. Historical to corrected: the same decisions and
 * goal choices, and only the phantom completions removed. TESTED IN FIXTURE.
 */

interface Reference {
  scenario: {
    world: string;
    seed: number;
    learningMode: "off" | "supervised";
    maxExperiencedTicks: number;
    maxDecisions: number;
  };
  recordedAt?: string;
  note?: string;
  trace: unknown[];
  affect: unknown[];
  priorities: unknown[];
}

const directory = path.join(
  REPOSITORY,
  "fixtures/regression/r15-affect-fixture-realism",
);
const corrected = path.join(
  REPOSITORY,
  "fixtures/regression/r15-affect-corrected",
);
const historical = path.join(REPOSITORY, "fixtures/regression/r15-affect");
const PHANTOM = "goal_complete_secure_food";
/** Measured when the corrected references were recorded (ADR 0015). */
const PHANTOMS_REMOVED: Record<string, number> = {
  "b-near-tie.json": 10,
  "c-exploration.json": 13,
  "d-setback.json": 13,
};

/** Measured when the fixture-realism references were recorded (ADR 0016). */
const PHYSICS_SPLIT: Record<string, unknown> = {
  "d-setback.json": { decision: 40, tick: 4014, physics: 4009 },
};

const triggers = (records: unknown[]): string[] =>
  records.map((record) => (record as { trigger: string }).trigger);

for (const name of readdirSync(directory)
  .filter((file) => file.endsWith(".json"))
  .sort())
  test(
    `interoception off reproduces R1.5 exactly: ${name}`,
    { timeout: 300000 },
    async () => {
      const reference = JSON.parse(
        readFileSync(path.join(directory, name), "utf8"),
      ) as Reference;
      const planDirectory = temporaryDirectory("person-r15-");
      const planFile = path.join(planDirectory, "plan.json");
      const plan: ExperimentPlan = {
        name: "r15-reference",
        world: path.join(REPOSITORY, reference.scenario.world),
        config: path.join(REPOSITORY, "examples/fixture.toml"),
        seeds: [reference.scenario.seed],
        conditions: [{ id: "R15", affectMode: "active", interoception: "off" }],
        maxDecisions: reference.scenario.maxDecisions,
        learningMode: reference.scenario.learningMode,
        horizons: [
          {
            id: "short",
            maxDecisions: reference.scenario.maxDecisions,
            maxExperiencedTicks: reference.scenario.maxExperiencedTicks,
          },
        ],
      };
      writeFileSync(planFile, JSON.stringify(plan));
      const out = temporaryDirectory("person-r15-run-");
      const physicsLog = path.join(out, "physics.jsonl");
      process.env["PERSON_FIXTURE_PHYSICS_LOG"] = physicsLog;
      const loaded = loadPlan(planFile);
      const run = await runOne({
        plan: loaded,
        planFile,
        condition: loaded.conditions[0]!,
        seed: reference.scenario.seed,
        horizon: loaded.horizons![0]!,
        outputDirectory: out,
        repository: REPOSITORY,
      }).finally(() => delete process.env["PERSON_FIXTURE_PHYSICS_LOG"]);
      const journal = path.join(
        out,
        "R15",
        "short",
        `seed-${reference.scenario.seed}`,
        "evidence",
        "journal",
      );
      const events = readdirSync(journal)
        .filter((file) => file.endsWith(".jsonl"))
        .sort()
        .flatMap((file) =>
          readFileSync(path.join(journal, file), "utf8").split("\n"),
        )
        .filter((line) => line.trim())
        .map(
          (line) =>
            JSON.parse(line) as {
              type: string;
              payload: Record<string, unknown>;
            },
        );
      assert.deepEqual(run.trace, reference.trace, "the same decisions");
      assert.deepEqual(
        events
          .filter((e) => e.type === "affect_appraised")
          .map((e) => e.payload),
        reference.affect,
        "the same appraisals, to the last digit",
      );
      assert.deepEqual(
        events
          .filter((e) => e.type === "goal_selected")
          .map((e) => ({
            goal_id: e.payload["goal_id"],
            base_priority: e.payload["base_priority"],
            affect_bias: e.payload["affect_bias"],
            priority: e.payload["priority"],
          })),
        reference.priorities,
        "the same priority adjustments",
      );
      assert.equal(events.filter((e) => e.type === "affect_tonic").length, 0);

      // Corrected to fixture-realism: the hostile-physics change (ADR 0016).
      const before = JSON.parse(
        readFileSync(path.join(corrected, name), "utf8"),
      ) as Reference;
      const physics = existsSync(physicsLog)
        ? readFileSync(physicsLog, "utf8")
            .split("\n")
            .filter((line) => line.trim())
            .map((line) => JSON.parse(line) as { tick: number })
        : [];
      const split = before.trace.findIndex(
        (entry, index) =>
          JSON.stringify(entry) !== JSON.stringify(reference.trace[index]),
      );
      if (split < 0) {
        assert.deepEqual(reference, {
          ...before,
          recordedAt: reference.recordedAt,
          note: reference.note,
        });
      } else {
        const tickOf = (entry: unknown) => (entry as { tick: number }).tick;
        const lastSame = split > 0 ? tickOf(before.trace[split - 1]) : -1;
        const firstDifferent = tickOf(reference.trace[split]);
        assert.ok(
          physics.length > 0,
          "a changed trajectory needs a physics event",
        );
        const first = physics[0]!.tick;
        assert.ok(
          first > lastSame && first <= firstDifferent,
          `first physics event at ${first}, decisions identical to ${lastSame}, different from ${firstDifferent}`,
        );
        assert.deepEqual(
          PHYSICS_SPLIT[name],
          { decision: split, tick: firstDifferent, physics: first },
          "the split is where it was measured",
        );
      }

      // Historical to corrected: the phantom-goal fix (ADR 0015).
      const old = JSON.parse(
        readFileSync(path.join(historical, name), "utf8"),
      ) as Reference;
      assert.deepEqual(
        before.trace,
        old.trace,
        "historical decisions unchanged",
      );
      // Real completions of SECURE_FOOD share the trigger, so the old
      // sequence is walked in order: every record the fix dropped must be a
      // phantom completion, and exactly as many as measured.
      const kept = triggers(before.affect);
      const dropped: string[] = [];
      let k = 0;
      for (const trigger of triggers(old.affect)) {
        if (k < kept.length && kept[k] === trigger) k += 1;
        else dropped.push(trigger);
      }
      assert.equal(
        k,
        kept.length,
        "the corrected sequence is ordered within the old",
      );
      assert.ok(
        dropped.every((trigger) => trigger === PHANTOM),
        `${dropped}`,
      );
      assert.equal(dropped.length, PHANTOMS_REMOVED[name]);
      const choice = (records: unknown[]) =>
        records.map((record) => {
          const r = record as { goal_id: unknown; base_priority: unknown };
          return [r.goal_id, r.base_priority];
        });
      assert.deepEqual(
        choice(before.priorities),
        choice(old.priorities),
        "the same goals chosen from the same base priorities",
      );
    },
  );
