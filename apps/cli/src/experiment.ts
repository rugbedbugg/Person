import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { loadConfig, type PersonConfig } from "#config";
import { FixtureWorld, type FixtureWorldDefinition } from "#fixture-world";
import { PersonRuntime, type EpisodeReport } from "#node-runtime";

/**
 * The experiment harness (ADR 0013).
 *
 * Research tooling that runs outside Person. It runs one fixture world under
 * several conditions and several world seeds, every run independent, and
 * measures each run from the runtime's episode report and Person's evidence
 * journal after the run is over. Nothing it reads or computes is ever sent to
 * Person: cognition receives exactly what it receives in any fixture run, and
 * the seed only lays out the world.
 *
 * There is no aggregate score. Metrics are reported one by one.
 */

export type AffectMode = "off" | "record_only" | "active";

export interface ExperimentCondition {
  id: string;
  affectMode: AffectMode;
}

export interface ExperimentPlan {
  name: string;
  description?: string;
  /** The fixture world, relative to the plan file. */
  world: string;
  /** The Person configuration every run starts from, relative to the plan. */
  config: string;
  seeds: number[];
  conditions: ExperimentCondition[];
  maxDecisions: number;
  learningMode?: "off" | "shadow" | "supervised";
}

export interface RunMetadata {
  plan: string;
  planSha256: string;
  condition: string;
  affectMode: AffectMode;
  seed: number;
  episodeId: string;
  commit: string;
  treeClean: boolean;
  configSha256: string;
  worldSha256: string;
  skillLibraryRevision: string;
  protocolVersion: string;
  learningMode: string;
  maxDecisions: number;
  cognitionCommand: string[];
  node: string;
}

/** One decision, as the runtime recorded it, without per-run identifiers. */
export interface TraceEntry {
  tick: number;
  goalId: string;
  goalType: string;
  routineId: string;
  requestedSkill: string;
  requestedParameters: Record<string, number | string | boolean>;
  validation: string;
  executedSkill: string | null;
  status: string;
}

export type Metrics = Record<string, number>;

export interface RunResult {
  metadata: RunMetadata;
  metrics: Metrics;
  distributions: Record<string, Record<string, number>>;
  trace: TraceEntry[];
}

export interface Divergence {
  seed: number;
  /** Index of the first decision that differs, or -1 if the traces agree. */
  firstDifference: number;
  lengths: [number, number];
}

export interface Comparison {
  between: [string, string];
  purpose: string;
  divergences: Divergence[];
  divergentSeeds: number;
}

export interface ExperimentResults {
  plan: ExperimentPlan;
  planSha256: string;
  commit: string;
  treeClean: boolean;
  runs: RunResult[];
  /** Per condition, per metric: the value from each seed, in seed order. */
  byCondition: Record<string, Record<string, number[]>>;
  comparisons: Comparison[];
}

const sha256 = (text: string): string =>
  createHash("sha256").update(text).digest("hex");

function git(cwd: string, args: string[]): string {
  try {
    return execFileSync("git", args, { cwd, encoding: "utf8" }).trim();
  } catch {
    return "unknown";
  }
}

export function loadPlan(file: string): ExperimentPlan {
  const plan = JSON.parse(readFileSync(file, "utf8")) as ExperimentPlan;
  const problems: string[] = [];
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(plan.name ?? ""))
    problems.push("name must be a short lowercase identifier");
  if (!Array.isArray(plan.seeds) || plan.seeds.length === 0)
    problems.push("seeds must list at least one world seed");
  else if (
    !plan.seeds.every((seed) => Number.isInteger(seed) && seed >= 0) ||
    new Set(plan.seeds).size !== plan.seeds.length
  )
    problems.push("seeds must be distinct non-negative integers");
  if (!Array.isArray(plan.conditions) || plan.conditions.length === 0)
    problems.push("conditions must list at least one condition");
  else {
    const ids = plan.conditions.map((condition) => condition.id);
    if (new Set(ids).size !== ids.length)
      problems.push("condition ids must be distinct");
    for (const condition of plan.conditions)
      if (!["off", "record_only", "active"].includes(condition.affectMode))
        problems.push(
          `condition ${condition.id} has an unknown affectMode ${condition.affectMode}`,
        );
  }
  if (
    !Number.isInteger(plan.maxDecisions) ||
    plan.maxDecisions < 1 ||
    plan.maxDecisions > 100000
  )
    problems.push("maxDecisions must be between 1 and 100000");
  if (typeof plan.world !== "string" || typeof plan.config !== "string")
    problems.push("world and config must be paths");
  if (problems.length)
    throw new Error(
      `Invalid experiment plan ${file}:\n  - ${problems.join("\n  - ")}`,
    );
  return plan;
}

interface JournalEvent {
  type: string;
  payload: Record<string, unknown>;
}

function readJournal(evidenceDirectory: string): JournalEvent[] {
  const directory = path.join(evidenceDirectory, "journal");
  let names: string[];
  try {
    names = readdirSync(directory);
  } catch {
    return [];
  }
  return names
    .filter((name) => name.endsWith(".jsonl"))
    .sort()
    .flatMap((name) =>
      readFileSync(path.join(directory, name), "utf8").split("\n"),
    )
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as JournalEvent);
}

export function traceOf(report: EpisodeReport): TraceEntry[] {
  return report.decisions.map((decision) => ({
    tick: decision.tick,
    goalId: decision.goalId,
    goalType: decision.goalType,
    routineId: decision.routineId,
    requestedSkill: decision.requestedSkill,
    requestedParameters: decision.requestedParameters,
    validation: decision.validation,
    executedSkill: decision.executedSkill,
    status: decision.status,
  }));
}

const count = <T>(items: T[], keep: (item: T) => boolean): number =>
  items.filter(keep).length;

const tally = (values: string[]): Record<string, number> => {
  const totals: Record<string, number> = {};
  for (const value of values) totals[value] = (totals[value] ?? 0) + 1;
  return Object.fromEntries(
    Object.entries(totals).sort(([a], [b]) => a.localeCompare(b)),
  );
};

/**
 * What a run did, measured from its records. Every metric is a plain count or
 * quantity with one meaning; none is a composite.
 */
export function measure(
  report: EpisodeReport,
  events: JournalEvent[],
): { metrics: Metrics; distributions: Record<string, Record<string, number>> } {
  const decisions = report.decisions;
  const of = (type: string) => events.filter((event) => event.type === type);
  const projectChanges = of("project_changed").map((event) =>
    String(event.payload["change"]),
  );
  const investigationChanges = of("investigation_changed").map((event) =>
    String(event.payload["change"]),
  );
  const searches = of("information_search");
  const selected = of("goal_selected");
  const appraised = of("affect_appraised");
  const lastAffect = (appraised.at(-1)?.payload["after"] ?? {}) as Record<
    string,
    number
  >;

  let hungerCrises = 0;
  let switches = 0;
  let repeatedFailures = 0;
  for (const [index, decision] of decisions.entries()) {
    const previous = decisions[index - 1];
    if (
      decision.goalType === "SECURE_FOOD" &&
      previous?.goalType !== "SECURE_FOOD"
    )
      hungerCrises += 1;
    if (previous && previous.goalId !== decision.goalId) switches += 1;
    if (
      previous &&
      previous.status !== "SUCCESS" &&
      decision.status !== "SUCCESS" &&
      previous.requestedSkill === decision.requestedSkill
    )
      repeatedFailures += 1;
  }

  // Recovery: after a setback (a failed decision, or one that cost health),
  // how many decisions until the next success. Setbacks never recovered from
  // within the run are counted apart rather than guessed at.
  const recoveries: number[] = [];
  let unrecovered = 0;
  for (const [index, decision] of decisions.entries()) {
    const setback = decision.status !== "SUCCESS" || decision.healthDelta < 0;
    if (!setback) continue;
    const next = decisions
      .slice(index + 1)
      .findIndex((later) => later.status === "SUCCESS");
    if (next === -1) unrecovered += 1;
    else recoveries.push(next + 1);
  }
  const mean = (values: number[]): number =>
    values.length === 0
      ? 0
      : Number((values.reduce((a, b) => a + b, 0) / values.length).toFixed(4));

  const metrics: Metrics = {
    completed: report.outcome === "completed" ? 1 : 0,
    died: decisions.some((decision) => decision.status === "DEATH") ? 1 : 0,
    decisions: report.totals.decisions,
    elapsed_ticks: report.elapsedTicks,
    successes: report.totals.successes,
    failures: report.totals.failures,
    emergencies: report.totals.emergencies,
    kernel_replacements: report.totals.replaced,
    kernel_rejections: report.totals.rejected,
    safety_overrides: report.safetyOverrides.length,
    health_lost: report.totals.healthLost,
    food_lost: decisions.reduce(
      (sum, decision) => sum + Math.max(0, -decision.foodDelta),
      0,
    ),
    hunger_crises: hungerCrises,
    goal_switches: switches,
    distinct_goals: new Set(decisions.map((decision) => decision.goalId)).size,
    distinct_routines: new Set(decisions.map((decision) => decision.routineId))
      .size,
    distinct_skills: new Set(
      decisions.map((decision) => decision.executedSkill ?? "none"),
    ).size,
    repeated_failures: repeatedFailures,
    setbacks: recoveries.length + unrecovered,
    mean_decisions_to_recover: mean(recoveries),
    unrecovered_setbacks: unrecovered,
    exploring_decisions: count(decisions, (decision) =>
      decision.policyReasonCodes.includes("exploring"),
    ),
    exploration_bonus_decisions: count(decisions, (decision) =>
      decision.policyReasonCodes.includes("exploration_bonus"),
    ),
    searches_started: count(
      searches,
      (event) => event.payload["phase"] === "started",
    ),
    searches_exhausted: count(
      searches,
      (event) => event.payload["phase"] === "exhausted",
    ),
    glances: count(decisions, (decision) => decision.requestedSkill === "look"),
    projects_started: of("project_started").length,
    projects_interrupted: count(projectChanges, (c) => c === "interrupted"),
    projects_resumed: count(projectChanges, (c) => c === "resumed"),
    projects_completed: count(projectChanges, (c) => c === "completed"),
    projects_abandoned: count(projectChanges, (c) => c === "abandoned"),
    effect_evidence: of("effect_evidence").length,
    effect_evidence_admitted: count(
      of("effect_evidence"),
      (event) => event.payload["admitted_to"] !== "none",
    ),
    hypotheses_proposed: of("hypothesis_proposed").length,
    hypotheses_rejected: of("hypothesis_rejected").length,
    investigations_started: count(investigationChanges, (c) => c === "started"),
    investigation_trials: count(investigationChanges, (c) => c === "trial"),
    investigations_interrupted: count(
      investigationChanges,
      (c) => c === "interrupted",
    ),
    investigations_concluded: count(
      investigationChanges,
      (c) => c === "concluded",
    ),
    affect_appraisals: appraised.length,
    affect_valence_final: lastAffect["valence"] ?? 0,
    affect_unease_final: lastAffect["unease"] ?? 0,
    affect_control_final: lastAffect["control"] ?? 0,
    biased_goal_selections: count(
      selected,
      (event) => Number(event.payload["affect_bias"] ?? 0) !== 0,
    ),
    max_abs_affect_bias: selected.reduce(
      (most, event) =>
        Math.max(most, Math.abs(Number(event.payload["affect_bias"] ?? 0))),
      0,
    ),
  };
  return {
    metrics,
    distributions: {
      goal_types: tally(decisions.map((decision) => decision.goalType)),
      executed_skills: tally(
        decisions.map((decision) => decision.executedSkill ?? "none"),
      ),
      terminal_statuses: tally(decisions.map((decision) => decision.status)),
    },
  };
}

export function compareTraces(
  seed: number,
  first: TraceEntry[],
  second: TraceEntry[],
): Divergence {
  const length = Math.max(first.length, second.length);
  let firstDifference = -1;
  for (let index = 0; index < length; index++) {
    if (JSON.stringify(first[index]) !== JSON.stringify(second[index])) {
      firstDifference = index;
      break;
    }
  }
  return { seed, firstDifference, lengths: [first.length, second.length] };
}

export interface RunOneOptions {
  plan: ExperimentPlan;
  planFile: string;
  condition: ExperimentCondition;
  seed: number;
  outputDirectory: string;
  repository: string;
}

/** One independent run: fresh evidence, one world seed, one condition. */
export async function runOne(options: RunOneOptions): Promise<RunResult> {
  const { plan, condition, seed, repository } = options;
  const planDirectory = path.dirname(path.resolve(options.planFile));
  const runDirectory = path.join(
    options.outputDirectory,
    condition.id,
    `seed-${seed}`,
  );
  // Independence: nothing from an earlier run of the same cell survives.
  // The seed goes to the world only. `runtime.rngSeed`, which cognition is
  // told in SessionHello, stays whatever the base configuration says.
  rmSync(runDirectory, { recursive: true, force: true });
  const evidenceDirectory = path.join(runDirectory, "evidence");
  const reportDirectory = path.join(runDirectory, "output");
  mkdirSync(evidenceDirectory, { recursive: true });
  mkdirSync(reportDirectory, { recursive: true });

  const configFile = path.join(runDirectory, "config.json");
  const base = loadConfig(path.resolve(planDirectory, plan.config));
  const cognitionCommand = [
    "uv",
    "run",
    "person-cognition",
    "--config",
    configFile,
  ];
  const config: PersonConfig = {
    ...base,
    runtime: {
      ...base.runtime,
      embodiment: "fixture",
      trainingContext: "fixture",
      outputDirectory: reportDirectory,
      maxDecisions: plan.maxDecisions,
      decisionIntervalMs: 0,
    },
    learning: {
      ...base.learning,
      mode: plan.learningMode ?? base.learning.mode,
      evidenceDirectory,
    },
    affect: { mode: condition.affectMode },
    cognition: { ...base.cognition, command: cognitionCommand },
  };
  delete config.runtime.fixtureWorld;
  const configText = `${JSON.stringify(config, null, 2)}\n`;
  writeFileSync(configFile, configText);

  const worldFile = path.resolve(planDirectory, plan.world);
  const definition: FixtureWorldDefinition = {
    ...(JSON.parse(readFileSync(worldFile, "utf8")) as FixtureWorldDefinition),
    seed,
  };
  const worldText = `${JSON.stringify(definition, null, 2)}\n`;
  writeFileSync(path.join(runDirectory, "world.json"), worldText);

  const episodeId = `${plan.name}-${condition.id}-s${seed}`.toLowerCase();
  const runtime = new PersonRuntime({
    config,
    embodiment: new FixtureWorld(definition),
    cwd: repository,
    episodeId,
  });
  const report = await runtime.run();
  const { metrics, distributions } = measure(
    report,
    readJournal(evidenceDirectory),
  );
  const result: RunResult = {
    metadata: {
      plan: plan.name,
      planSha256: sha256(readFileSync(options.planFile, "utf8")),
      condition: condition.id,
      affectMode: condition.affectMode,
      seed,
      episodeId,
      commit: git(repository, ["rev-parse", "HEAD"]),
      treeClean: git(repository, ["status", "--porcelain"]) === "",
      configSha256: sha256(configText),
      worldSha256: sha256(worldText),
      skillLibraryRevision: report.skillLibraryRevision,
      protocolVersion: report.protocolVersion,
      learningMode: report.learningMode,
      maxDecisions: plan.maxDecisions,
      cognitionCommand,
      node: process.version,
    },
    metrics,
    distributions,
    trace: traceOf(report),
  };
  writeFileSync(
    path.join(runDirectory, "run.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
  return result;
}

const COMPARISONS: {
  modes: [AffectMode, AffectMode];
  purpose: string;
}[] = [
  {
    modes: ["off", "record_only"],
    purpose:
      "negative control: affect that reaches no decision must change no decision",
  },
  {
    modes: ["record_only", "active"],
    purpose: "the causal effect of letting the same affect reach decisions",
  },
  {
    modes: ["off", "active"],
    purpose: "the whole affect system",
  },
];

export interface ExperimentOptions {
  planFile: string;
  outputDirectory: string;
  repository: string;
  onRun?: (result: RunResult) => void;
}

/** Runs every (condition, seed) cell of a plan, then compares conditions. */
export async function runExperiment(
  options: ExperimentOptions,
): Promise<ExperimentResults> {
  const plan = loadPlan(options.planFile);
  const outputDirectory = path.join(options.outputDirectory, plan.name);
  const runs: RunResult[] = [];
  for (const condition of plan.conditions)
    for (const seed of plan.seeds) {
      const result = await runOne({
        plan,
        planFile: options.planFile,
        condition,
        seed,
        outputDirectory,
        repository: options.repository,
      });
      runs.push(result);
      options.onRun?.(result);
    }

  const byCondition: ExperimentResults["byCondition"] = {};
  for (const run of runs) {
    const metrics = (byCondition[run.metadata.condition] ??= {});
    for (const [name, value] of Object.entries(run.metrics))
      (metrics[name] ??= []).push(value);
  }

  const comparisons: Comparison[] = [];
  for (const { modes, purpose } of COMPARISONS) {
    const first = plan.conditions.find((c) => c.affectMode === modes[0]);
    const second = plan.conditions.find((c) => c.affectMode === modes[1]);
    if (!first || !second) continue;
    const divergences = plan.seeds.map((seed) => {
      const trace = (id: string) =>
        runs.find(
          (run) => run.metadata.condition === id && run.metadata.seed === seed,
        )?.trace ?? [];
      return compareTraces(seed, trace(first.id), trace(second.id));
    });
    comparisons.push({
      between: [first.id, second.id],
      purpose,
      divergences,
      divergentSeeds: count(divergences, (d) => d.firstDifference !== -1),
    });
  }

  const results: ExperimentResults = {
    plan,
    planSha256: sha256(readFileSync(options.planFile, "utf8")),
    commit: git(options.repository, ["rev-parse", "HEAD"]),
    treeClean: git(options.repository, ["status", "--porcelain"]) === "",
    runs,
    byCondition,
    comparisons,
  };
  writeFileSync(
    path.join(outputDirectory, "results.json"),
    `${JSON.stringify(results, null, 2)}\n`,
  );
  writeFileSync(path.join(outputDirectory, "metrics.csv"), metricsCsv(runs));
  return results;
}

/** One row per run, one column per metric: for analysis elsewhere. */
export function metricsCsv(runs: RunResult[]): string {
  const names = [
    ...new Set(runs.flatMap((run) => Object.keys(run.metrics))),
  ].sort();
  const header = ["condition", "affect_mode", "seed", ...names].join(",");
  const rows = runs.map((run) =>
    [
      run.metadata.condition,
      run.metadata.affectMode,
      run.metadata.seed,
      ...names.map((name) => run.metrics[name] ?? ""),
    ].join(","),
  );
  return `${[header, ...rows].join("\n")}\n`;
}

/** A plain summary: per condition, each metric's mean, min and max over seeds. */
export function summariseExperiment(results: ExperimentResults): string {
  const lines: string[] = [
    `Experiment ${results.plan.name} at ${results.commit.slice(0, 12)}${results.treeClean ? "" : " (uncommitted changes)"}`,
    `  seeds: ${results.plan.seeds.join(", ")}; decisions per run: ${results.plan.maxDecisions}`,
  ];
  for (const comparison of results.comparisons)
    lines.push(
      `  ${comparison.between.join(" vs ")}: ${comparison.divergentSeeds}/${comparison.divergences.length} seeds diverge (${comparison.purpose})`,
    );
  const conditions = Object.keys(results.byCondition);
  const names = Object.keys(results.byCondition[conditions[0] ?? ""] ?? {});
  lines.push(
    `  metric: ${conditions.map((c) => `${c} mean [min-max]`).join(" | ")}`,
  );
  for (const name of names)
    lines.push(
      `  ${name}: ${conditions
        .map((condition) => {
          const values = results.byCondition[condition]?.[name] ?? [];
          const mean =
            values.reduce((a, b) => a + b, 0) / Math.max(1, values.length);
          return `${Number(mean.toFixed(3))} [${Math.min(...values)}-${Math.max(...values)}]`;
        })
        .join(" | ")}`,
    );
  return `${lines.join("\n")}\n`;
}
