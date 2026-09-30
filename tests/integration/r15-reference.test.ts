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
 * The reference runs were recorded at `5548bbd`, before any R2 change, in
 * `fixtures/regression/r15-affect/`. The same scenarios run now, with the
 * switch off, must make the same decisions, record the same appraisals and
 * apply the same priority adjustments. TESTED IN FIXTURE.
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

const directory = path.join(REPOSITORY, "fixtures/regression/r15-affect");

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
    },
  );
