import test from "node:test";
import assert from "node:assert/strict";
import type { PersonConfig } from "#config";
import { FixtureWorld } from "#fixture-world";
import { runSkillValidation } from "#node-runtime";
import { REPOSITORY, baseConfig } from "../support/harness.ts";

/**
 * The effect comparison, end to end, against the real implementation.
 *
 * The comparison is not written twice. It lives in the cognition package, on
 * the same symbolic state the planner reasons over, and the harness runs it
 * once over the two observations it captured. These tests are what proves the
 * connection actually works rather than silently degrading to "inconclusive"
 * every time.
 */
const COGNITION = ["uv", "run", "person-cognition"];

const withComparison = (config: PersonConfig): PersonConfig => ({
  ...config,
  cognition: { ...config.cognition, command: COGNITION },
});

test("return_home's declared effect is checked against the world, and matches", async () => {
  const config = withComparison(baseConfig({ home: { x: 0, y: 64, z: 0 } }));
  const world = new FixtureWorld({ spawn: { x: 10, y: 64, z: 0 } });

  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "return_home",
    cwd: REPOSITORY,
  });

  assert.equal(run.report.terminalStatus, "SUCCESS");
  const comparison = run.report.effectComparison;
  assert.ok(comparison, "a comparison must be attempted");
  assert.equal(
    comparison.available,
    true,
    `the comparison did not run: ${comparison.reason}`,
  );
  assert.equal(comparison.matched, 1);
  assert.equal(comparison.mismatched, 0);
  const atHome = comparison.facts.find((fact) => fact.fact === "at_home");
  assert.ok(atHome);
  assert.equal(atHome.verdict, "match");
  assert.equal(atHome.before, 0);
  assert.equal(atHome.observed, 1);
});

test("an effect an observation cannot carry is not counted as a failure", async () => {
  // wait_safely promises `rested`, which is a record that something transient
  // happened rather than anything about the world. The right answer is "not
  // observable", and calling it a mismatch would make every successful wait
  // look like a broken contract.
  const config = withComparison(baseConfig({ home: { x: 0, y: 64, z: 0 } }));
  const world = new FixtureWorld({ spawn: { x: 0, y: 64, z: 0 } });

  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "wait_safely",
    parameters: { ticks: 40 },
    cwd: REPOSITORY,
  });

  assert.equal(run.report.terminalStatus, "SUCCESS");
  const comparison = run.report.effectComparison;
  assert.ok(comparison);
  assert.equal(comparison.available, true, comparison.reason ?? "");
  assert.equal(comparison.notObservable, 1);
  assert.equal(comparison.mismatched, 0);
  assert.equal(comparison.facts[0]?.fact, "rested");
  assert.equal(comparison.facts[0]?.verdict, "not_observable");
});

test("a comparison that cannot run leaves the report honest rather than empty", async () => {
  const base = baseConfig({ home: { x: 0, y: 64, z: 0 } });
  const config: PersonConfig = {
    ...base,
    cognition: {
      ...base.cognition,
      command: ["definitely-not-a-real-program-person-test"],
    },
  };
  const world = new FixtureWorld({ spawn: { x: 10, y: 64, z: 0 } });

  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "return_home",
    cwd: REPOSITORY,
  });

  assert.equal(run.report.terminalStatus, "SUCCESS", "the skill still ran");
  const comparison = run.report.effectComparison;
  assert.ok(comparison);
  assert.equal(comparison.available, false);
  assert.match(comparison.reason ?? "", /comparison_failed/);
  assert.equal(comparison.inconclusive, 1);
  assert.equal(comparison.mismatched, 0);
  assert.ok(run.reportPath, "and the report is still written");
});
