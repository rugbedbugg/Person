import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
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
 * Two sets of references. `r15-affect-corrected/` is the canonical baseline,
 * recorded after goals already satisfied stopped being queued (ADR 0015
 * branch): the same scenarios run now, with the switch off, must make the same
 * decisions, record the same appraisals and apply the same priority
 * adjustments. `r15-affect/` is the historical record at `5548bbd`, immutable;
 * the bridge to it is pinned exactly: the same decisions and goal choices,
 * and the historical appraisals minus only the phantom SECURE_FOOD
 * completions. TESTED IN FIXTURE.
 */

interface Reference {
  scenario: {
    world: string;
    seed: number;
    learningMode: "off" | "supervised";
    maxExperiencedTicks: number;
    maxDecisions: number;
  };
  trace: unknown[];
  affect: unknown[];
  priorities: unknown[];
}

const directory = path.join(
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
      const loaded = loadPlan(planFile);
      const run = await runOne({
        plan: loaded,
        planFile,
        condition: loaded.conditions[0]!,
        seed: reference.scenario.seed,
        horizon: loaded.horizons![0]!,
        outputDirectory: out,
        repository: REPOSITORY,
      });
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

      // The bridge to the historical reference, recorded before the fix.
      const old = JSON.parse(
        readFileSync(path.join(historical, name), "utf8"),
      ) as Reference;
      assert.deepEqual(run.trace, old.trace, "historical decisions unchanged");
      // Real completions of SECURE_FOOD share the trigger, so the old
      // sequence is walked in order: every record the fix dropped must be a
      // phantom completion, and exactly as many as measured.
      const kept = triggers(reference.affect);
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
        choice(reference.priorities),
        choice(old.priorities),
        "the same goals chosen from the same base priorities",
      );
    },
  );
