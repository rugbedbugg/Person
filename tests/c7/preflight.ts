/**
 * The C7 solvability preflight (ADR 0024), with zero frontier calls.
 *
 *   node tests/c7/preflight.ts [scenario-id ...]
 *
 * For each behavioural scenario: a negative control (System 2 unavailable)
 * must reach the scenario's trigger without resolving the problem; an oracle
 * control (a scripted provider stating the intended grounded remedy) must be
 * admitted, adopted and resolve it by the frozen criterion. A scenario that
 * fails either is engineering-invalid. The report also counts the intended
 * remedy templates, for the catalogue diversity rule. As in the evaluation,
 * a scenario gets one provider answer; later requests are unavailable.
 */
import { writeFileSync } from "node:fs";
import { of, run, type Scenario } from "./scenario.ts";
import { SCENARIOS } from "./scenarios/index.ts";

interface Control {
  passed: boolean;
  details: Record<string, unknown>;
}

const triggered = (
  scenario: Scenario,
  events: { payload: Record<string, unknown> }[],
) =>
  events.some(
    (event) => event.payload["trigger_kind"] === scenario.evaluator.trigger,
  );

async function negative(scenario: Scenario): Promise<Control> {
  const outcome = await run(scenario, [null, null, null, null]);
  const requested = of(outcome.events, "deliberation_requested");
  const reached = triggered(scenario, requested);
  const resolved = scenario.evaluator.resolved(outcome);
  return {
    passed: reached && !resolved,
    details: { reached_trigger: reached, resolved_by_system_1: resolved },
  };
}

async function oracle(scenario: Scenario): Promise<Control> {
  const answer = scenario.evaluator.oracle;
  // One provider call per C7B scenario, as the frozen budget allows: any
  // later request finds System 2 unavailable.
  const outcome = await run(scenario, [answer, null, null, null]);
  const adopted = of(outcome.events, "deliberation_adopted").find(
    (event) =>
      event.payload["goal_type"] ===
      scenario.evaluator.intendedRemedy.goal_type,
  );
  const premise = of(outcome.events, "deliberation_requested").some(
    (event) =>
      ((event.payload["memory_retrieval"] as { result_count?: number } | null)
        ?.result_count ?? 0) > 0,
  );
  const resolved = scenario.evaluator.resolved(outcome);
  return {
    passed: Boolean(adopted) && resolved,
    details: {
      adopted: Boolean(adopted),
      retrieved_memory: premise,
      resolved,
    },
  };
}

const wanted = new Set(process.argv.slice(2));
const report: Record<string, unknown> = {};
const templates: Record<string, number> = {};
let failed = 0;
for (const scenario of SCENARIOS) {
  if (wanted.size && !wanted.has(scenario.id)) continue;
  const no = await negative(scenario);
  const yes = await oracle(scenario);
  const template = `${scenario.evaluator.intendedRemedy.goal_type}/${[
    ...scenario.evaluator.intendedRemedy.desired,
  ]
    .sort()
    .join("+")}`;
  if (scenario.family === "C7B")
    templates[template] = (templates[template] ?? 0) + 1;
  report[scenario.id] = {
    family: scenario.family,
    trigger: scenario.evaluator.trigger,
    intended: template,
    negative: no,
    oracle: yes,
    valid: no.passed && yes.passed,
  };
  if (!(no.passed && yes.passed)) failed += 1;
  console.log(scenario.id, JSON.stringify(report[scenario.id]));
}
const summary = { scenarios: report, intended_remedy_counts: templates };
if (process.env.C7_PREFLIGHT_OUT)
  writeFileSync(
    process.env.C7_PREFLIGHT_OUT,
    JSON.stringify(summary, null, 2) + "\n",
  );
console.log("intended remedy counts", JSON.stringify(templates));
process.exit(failed ? 1 : 0);
