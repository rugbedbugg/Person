/**
 * C7 behavioural scenarios (ADR 0024): what a scenario is, and how one runs.
 *
 * A scenario is two separately hashed objects. The provider-visible part is
 * everything Person and the model can receive: the synthetic prior history
 * (a prelude lived through Person's real cognition), the fixture world, the
 * runtime configuration and the episode length. The evaluator part is never
 * serialized into anything cognition reads: the intended grounded remedy,
 * the scripted oracle answer, the premises that support it, and the frozen
 * success and failure criteria.
 */
import { spawnSync } from "node:child_process";
import { cpSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { FixtureWorld } from "#fixture-world";
import { REPOSITORY, temporaryDirectory } from "../support/harness.ts";
import { journal, type Event } from "../support/quiet-grove.ts";
import { runEpisode } from "../support/runtime.ts";

export const PERSON = "test-person-000";
export const COGNITION = ["uv", "run", "person-cognition"];

export type TriggerKind =
  | "repeated_failure"
  | "no_viable_plan"
  | "repeated_prediction_error"
  | "emergency_recurrence"
  | "habit_breakdown";

export interface ProviderInputSpec {
  /** The synthetic history: a prelude in experiments/c7/prelude.py. */
  prelude: { name: string; args: string[] };
  world: () => FixtureWorld;
  /** The runtime's placement ledger, as Person's history implies it. */
  ledger: Record<string, unknown>;
  config: Record<string, unknown>;
  home: { x: number; y: number; z: number };
  maxTicks: number;
  maxDecisions: number;
  habits: "off" | "active";
  affectArbitration: "off" | "active";
}

export interface Outcome {
  events: Event[];
  world: FixtureWorld;
}

export interface EvaluatorSpec {
  trigger: TriggerKind;
  /** Normalized template: goal type and sorted desired facts. */
  intendedRemedy: { goal_type: string; desired: string[] };
  /** The Person-visible evidence the intended remedy rests on, in words. */
  premises: string[];
  /** A TemplateModel answer stating the intended remedy (oracle control). */
  oracle: unknown;
  /** The frozen behavioural success criterion. */
  resolved: (outcome: Outcome) => boolean;
}

export interface Scenario {
  id: string;
  family: "C7B" | "C7C-1" | "C7C-2";
  provider: ProviderInputSpec;
  evaluator: EvaluatorSpec;
}

/** Live the prelude through Person's real cognition, into a fresh root. */
export function prelude(spec: ProviderInputSpec["prelude"]): string {
  const root = temporaryDirectory("person-c7-prelude-");
  const run = spawnSync(
    "uv",
    [
      "run",
      "python",
      "experiments/c7/prelude.py",
      root,
      PERSON,
      spec.name,
      ...spec.args,
    ],
    { cwd: REPOSITORY, encoding: "utf8" },
  );
  if (run.status !== 0) throw new Error(`prelude failed: ${run.stderr}`);
  return root;
}

/** One run of a scenario with the given scripted answers. */
export async function run(
  scenario: Scenario,
  answers: unknown[],
): Promise<Outcome & { evidenceDirectory: string; outputDirectory: string }> {
  const spec = scenario.provider;
  const evidenceDirectory = temporaryDirectory("person-c7-");
  const outputDirectory = temporaryDirectory("person-c7-run-");
  cpSync(prelude(spec.prelude), evidenceDirectory, { recursive: true });
  writeFileSync(
    path.join(outputDirectory, `world-test-world-${PERSON}.json`),
    JSON.stringify(spec.ledger),
  );
  const world = spec.world();
  await runEpisode({
    worldObject: world,
    cognitionCommand: COGNITION,
    evidenceDirectory,
    outputDirectory,
    personId: PERSON,
    home: spec.home,
    config: spec.config as never,
    maxDecisions: spec.maxDecisions,
    maxTicks: spec.maxTicks,
    deliberation: {
      mode: "active",
      answers,
      habits: spec.habits,
      affectArbitration: spec.affectArbitration,
    },
  });
  return {
    events: journal(evidenceDirectory),
    world,
    evidenceDirectory,
    outputDirectory,
  };
}

export const of = (events: Event[], type: string): Event[] =>
  events.filter((event) => event.type === type);
