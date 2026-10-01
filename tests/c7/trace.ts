/**
 * Scenario development aid: one control of one scenario, as a condensed
 * behaviour timeline. Scripted models only.
 *
 *   node tests/c7/trace.ts <scenario-id> negative|oracle [from-tick]
 */
import { run } from "./scenario.ts";
import { SCENARIOS } from "./scenarios/index.ts";

const [id, control = "oracle", from = "0"] = process.argv.slice(2);
const scenario = SCENARIOS.find((candidate) => candidate.id === id);
if (!scenario) throw new Error(`no scenario ${id}`);
const answer = control === "oracle" ? scenario.evaluator.oracle : null;
const outcome = await run(scenario, [answer, null, null, null]);
let last = "";
for (const event of outcome.events) {
  if (event.tick < Number(from)) continue;
  const p = event.payload;
  let line = "";
  if (event.type === "skill_completed" || event.type === "skill_failed")
    line = `${event.type} ${String(p["executed_skill"])} ${String(p["status"])}`;
  else if (event.type === "goal_selected")
    line = `goal ${String(p["goal_type"])}`;
  else if (
    event.type.startsWith("deliberation_") ||
    event.type.startsWith("habit_")
  )
    line = `${event.type} ${String(p["trigger_key_full"] ?? p["goal_type"] ?? p["why"] ?? p["reason"] ?? "")}`;
  else if (event.type === "information_search")
    line = `search ${String(p["phase"])} ${JSON.stringify(p["purpose"])}`;
  else continue;
  if (line !== last) console.log(event.tick, line);
  last = line;
}
const snapshot = outcome.world.snapshot();
console.log(
  "end",
  JSON.stringify(snapshot.position),
  "food",
  snapshot.food,
  JSON.stringify(snapshot.inventory),
);
console.log("resolved", scenario.evaluator.resolved(outcome));
