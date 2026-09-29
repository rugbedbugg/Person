import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import {
  compareTraces,
  loadPlan,
  runExperiment,
  runOne,
  type ExperimentPlan,
} from "../../apps/cli/src/experiment.ts";
import { REPOSITORY, temporaryDirectory } from "../support/harness.ts";

/**
 * The experiment harness (ADR 0013): research tooling outside Person.
 *
 * These runs use the real runtime, the real cognition process and a fixture
 * body. TESTED IN FIXTURE. Nothing here is Minecraft evidence.
 */

function planFile(overrides: Partial<ExperimentPlan> = {}): string {
  const directory = temporaryDirectory("person-plan-");
  const file = path.join(directory, "plan.json");
  const plan: ExperimentPlan = {
    name: "probe",
    world: path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
    config: path.join(REPOSITORY, "examples/fixture.toml"),
    seeds: [1, 2],
    conditions: [
      { id: "P0", affectMode: "off" },
      { id: "P1", affectMode: "record_only" },
      { id: "P2", affectMode: "active" },
    ],
    maxDecisions: 8,
    learningMode: "off",
    ...overrides,
  };
  writeFileSync(file, JSON.stringify(plan));
  return file;
}

test(
  "affect that reaches no decision changes no decision",
  { timeout: 300000 },
  async () => {
    const results = await runExperiment({
      planFile: planFile(),
      outputDirectory: temporaryDirectory("person-experiment-"),
      repository: REPOSITORY,
    });
    const control = results.comparisons.find(
      (comparison) => comparison.between.join() === "P0,P1",
    );
    assert.ok(control, "the negative control is always reported");
    assert.equal(control.divergentSeeds, 0, JSON.stringify(control));

    for (const seed of [1, 2]) {
      const run = (id: string) =>
        results.runs.find(
          (r) => r.metadata.condition === id && r.metadata.seed === seed,
        )!;
      assert.equal(run("P0").metrics["affect_appraisals"], 0, "off is off");
      assert.ok(run("P1").metrics["affect_appraisals"]! > 0);
      assert.equal(run("P1").metrics["biased_goal_selections"], 0);
      assert.ok(
        run("P2").metrics["biased_goal_selections"]! > 0,
        "active affect adjusts priorities",
      );
    }
    assert.equal(results.runs.length, 6, "every condition on every seed");
  },
);

test(
  "every run records what is needed to repeat it exactly",
  { timeout: 300000 },
  async () => {
    const out = temporaryDirectory("person-experiment-");
    const results = await runExperiment({
      planFile: planFile({ seeds: [3] }),
      outputDirectory: out,
      repository: REPOSITORY,
    });
    for (const run of results.runs) {
      const metadata = run.metadata;
      assert.match(metadata.commit, /^[0-9a-f]{40}$/);
      assert.equal(typeof metadata.treeClean, "boolean");
      assert.match(metadata.configSha256, /^[0-9a-f]{64}$/);
      assert.match(metadata.worldSha256, /^[0-9a-f]{64}$/);
      assert.match(metadata.planSha256, /^[0-9a-f]{64}$/);
      assert.equal(metadata.seed, 3);
      assert.ok(metadata.skillLibraryRevision.length > 0);
      assert.ok(metadata.cognitionCommand.includes("--config"));
    }
    const directory = path.join(out, "probe");
    assert.ok(readdirSync(directory).includes("results.json"));
    assert.ok(readdirSync(directory).includes("metrics.csv"));

    // The configurations of the three conditions differ in the affect mode and
    // in where each run writes, and nowhere else.
    const config = (id: string) => {
      const body = JSON.parse(
        readFileSync(path.join(directory, id, "seed-3", "config.json"), "utf8"),
      );
      const normalised = JSON.stringify(body).replaceAll(`/${id}/`, "/<c>/");
      return JSON.parse(normalised) as Record<string, unknown> & {
        affect: { mode: string };
      };
    };
    const [off, recorded, active] = ["P0", "P1", "P2"].map(config);
    assert.deepEqual(
      [off!.affect.mode, recorded!.affect.mode, active!.affect.mode],
      ["off", "record_only", "active"],
    );
    const withoutMode = (body: Record<string, unknown>) => ({
      ...body,
      affect: null,
    });
    assert.deepEqual(withoutMode(off!), withoutMode(recorded!));
    assert.deepEqual(withoutMode(off!), withoutMode(active!));
  },
);

test(
  "the same plan at the same commit measures the same run",
  { timeout: 300000 },
  async () => {
    const file = planFile({
      seeds: [4],
      conditions: [{ id: "P2", affectMode: "active" }],
    });
    const plan = loadPlan(file);
    const once = await runOne({
      plan,
      planFile: file,
      condition: plan.conditions[0]!,
      seed: 4,
      outputDirectory: temporaryDirectory("person-experiment-"),
      repository: REPOSITORY,
    });
    const again = await runOne({
      plan,
      planFile: file,
      condition: plan.conditions[0]!,
      seed: 4,
      outputDirectory: temporaryDirectory("person-experiment-"),
      repository: REPOSITORY,
    });
    assert.deepEqual(again.metrics, once.metrics);
    assert.deepEqual(again.trace, once.trace);
    assert.equal(again.metadata.worldSha256, once.metadata.worldSha256);
  },
);

test(
  "the seed changes the world and never reaches Person",
  { timeout: 300000 },
  async () => {
    const out = temporaryDirectory("person-experiment-");
    const results = await runExperiment({
      planFile: planFile({
        seeds: [5, 6],
        conditions: [{ id: "P2", affectMode: "active" }],
      }),
      outputDirectory: out,
      repository: REPOSITORY,
    });
    const [first, second] = results.runs;
    assert.notEqual(first!.metadata.worldSha256, second!.metadata.worldSha256);
    for (const seed of [5, 6]) {
      const config = JSON.parse(
        readFileSync(
          path.join(out, "probe", "P2", `seed-${seed}`, "config.json"),
          "utf8",
        ),
      ) as { runtime: { rngSeed: number | null } };
      assert.notEqual(config.runtime.rngSeed, seed);
      const journal = path.join(out, "probe", "P2", `seed-${seed}`, "evidence");
      const text = readdirSync(path.join(journal, "journal"))
        .map((name) =>
          readFileSync(path.join(journal, "journal", name), "utf8"),
        )
        .join("");
      assert.ok(!text.includes(`"rng_seed": ${seed},`));
    }
  },
);

test("a divergence is located at the first decision that differs", () => {
  const entry = (skill: string) => ({
    tick: 1,
    goalId: "g",
    goalType: "SECURE_FOOD",
    routineId: "r",
    requestedSkill: skill,
    requestedParameters: {},
    validation: "ACCEPT",
    executedSkill: skill,
    status: "SUCCESS",
  });
  const a = [entry("look"), entry("eat_to_target")];
  assert.equal(compareTraces(1, a, a).firstDifference, -1);
  assert.equal(
    compareTraces(1, a, [entry("look"), entry("flee")]).firstDifference,
    1,
  );
  assert.equal(compareTraces(1, a, [entry("look")]).firstDifference, 1);
});

test("a malformed plan is refused before anything runs", () => {
  for (const overrides of [
    { seeds: [] },
    { seeds: [1, 1] },
    { conditions: [{ id: "X", affectMode: "loud" as never }] },
    {
      conditions: [
        { id: "P", affectMode: "off" as const },
        { id: "P", affectMode: "active" as const },
      ],
    },
    { maxDecisions: 0 },
    { name: "Has Spaces" },
  ])
    assert.throws(
      () => loadPlan(planFile(overrides)),
      /Invalid experiment plan/,
    );
});

test(
  "a run ends at whichever bound comes first, in Person's experienced time",
  { timeout: 300000 },
  async () => {
    const results = await runExperiment({
      planFile: planFile({
        seeds: [1],
        conditions: [{ id: "P2", affectMode: "active" }],
        horizons: [
          { id: "ticks", maxDecisions: 500, maxExperiencedTicks: 1500 },
          { id: "decisions", maxDecisions: 5, maxExperiencedTicks: 100000 },
        ],
      }),
      outputDirectory: temporaryDirectory("person-experiment-"),
      repository: REPOSITORY,
      jobs: 2,
    });
    const run = (id: string) =>
      results.runs.find((r) => r.metadata.horizon === id)!;
    const ticks = run("ticks").metrics;
    assert.ok(ticks["elapsed_ticks"]! >= 1500, "the bound was what ended it");
    assert.ok(ticks["decisions"]! < 500);
    // Person did not observe the end of its last action, so its own clock
    // stops short of the runtime's by at most that one action.
    assert.ok(ticks["experienced_ticks"]! <= ticks["elapsed_ticks"]!);
    assert.ok(
      ticks["experienced_ticks"]! >= ticks["elapsed_ticks"]! - 12000,
      "no skill's budget is longer than 12000 ticks",
    );
    const decisions = run("decisions").metrics;
    assert.equal(decisions["decisions"], 5);
    assert.ok(decisions["experienced_ticks"]! < 100000);
    assert.equal(run("ticks").metadata.maxExperiencedTicks, 1500);
    assert.deepEqual(
      results.comparisons.map((c) => c.horizon),
      [],
      "one condition: nothing to compare",
    );
  },
);

test("a held-out plan does not run unless it is asked for by name", async () => {
  await assert.rejects(
    runExperiment({
      planFile: planFile({ split: "heldout" }),
      outputDirectory: temporaryDirectory("person-experiment-"),
      repository: REPOSITORY,
    }),
    /held-out plan/,
  );
});

test(
  "running cells at once measures exactly what running them in turn does",
  { timeout: 300000 },
  async () => {
    const file = planFile({ seeds: [7, 8] });
    const serial = await runExperiment({
      planFile: file,
      outputDirectory: temporaryDirectory("person-experiment-"),
      repository: REPOSITORY,
      jobs: 1,
    });
    const parallel = await runExperiment({
      planFile: file,
      outputDirectory: temporaryDirectory("person-experiment-"),
      repository: REPOSITORY,
      jobs: 4,
    });
    assert.deepEqual(
      parallel.runs.map((run) => [run.metrics, run.trace]),
      serial.runs.map((run) => [run.metrics, run.trace]),
    );
    for (const run of serial.runs) {
      // Affect can only change a choice where it had the opportunity to.
      assert.equal(run.metrics["priority_changed_without_opportunity"], 0);
      assert.equal(run.metrics["exploration_changed_without_opportunity"], 0);
      if (run.metadata.affectMode !== "active") {
        assert.equal(run.metrics["priority_changed"], 0);
        assert.equal(run.metrics["exploration_changed"], 0);
      }
      assert.equal(run.metrics["affect_exact_duplicate_appraisals"], 0);
    }
    assert.ok(serial.affectBounds.swings["protective"]!["outgoing"]! > 0);
  },
);
