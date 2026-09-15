import { mkdirSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { ItemDelta, SkillOutcome, TerminalStatus } from "#protocol";

export interface DecisionRecord {
  decisionId: string;
  tick: number;
  contextId: string;
  goalId: string;
  goalType: string;
  goalReasonCodes: string[];
  routineId: string;
  routineName: string;
  routineSteps: string[];
  learnedOrFallback: "learned" | "fallback";
  policyConfidence: number;
  policyReasonCodes: string[];
  evidenceRefs: string[];
  requestedSkill: string;
  requestedParameters: Record<string, number | string | boolean>;
  preconditions: { fact: string; op: string; value: number }[];
  expectedEffects: { fact: string; op: string; value: number }[];
  validation: string;
  validationLevel: string;
  validationReasonCodes: string[];
  executedSkill: string | null;
  status: TerminalStatus;
  requestedSkillStatus: TerminalStatus;
  emergency: boolean;
  healthDelta: number;
  foodDelta: number;
  elapsedTicks: number;
  budgetTicks: number;
  budgetPressure: number;
  navigationTicks: number;
  interactionTicks: number;
  waitingTicks: number;
  inventoryDelta: ItemDelta[];
  outcomeMessageId: string;
}

export interface EpisodeReport {
  schemaVersion: 1;
  episodeId: string;
  personId: string;
  worldId: string;
  sessionId: string;
  trainingContext: string;
  learningMode: string;
  rngSeed: number | null;
  policyRevision: number;
  skillLibraryRevision: string;
  protocolVersion: string;
  startedAt: string;
  finishedAt: string;
  outcome: "completed" | "failed" | "interrupted";
  reason: string | null;
  startTick: number;
  endTick: number;
  elapsedTicks: number;
  decisions: DecisionRecord[];
  safetyOverrides: {
    tick: number;
    level: string;
    trigger: string;
    action: string;
    preemptedSkill: string | null;
  }[];
  storageProvenance: unknown[];
  totals: {
    decisions: number;
    accepted: number;
    replaced: number;
    rejected: number;
    learnedDecisions: number;
    fallbackDecisions: number;
    successes: number;
    failures: number;
    emergencies: number;
    healthLost: number;
    resourceDelta: ItemDelta[];
  };
  /**
   * Per-skill timing, so a cost limit can be revised from measurements.
   *
   * `worstPressure` is the closest any single run came to its budget. A value
   * near one means the budget is about to start causing timeouts; a value far
   * below it means the budget is not the reason anything failed.
   */
  tickBudgets: {
    skill: string;
    runs: number;
    budgetTicks: number;
    meanElapsedTicks: number;
    maxElapsedTicks: number;
    worstPressure: number;
    meanNavigationTicks: number;
    meanInteractionTicks: number;
    timeouts: number;
  }[];
}

const mergeDeltas = (deltas: ItemDelta[][]): ItemDelta[] => {
  const totals = new Map<string, number>();
  for (const group of deltas)
    for (const item of group)
      totals.set(item.name, (totals.get(item.name) ?? 0) + item.delta);
  return [...totals]
    .filter(([, delta]) => delta !== 0)
    .map(([name, delta]) => ({ name, delta }))
    .sort((a, b) => a.name.localeCompare(b.name));
};

function summariseTickBudgets(
  decisions: DecisionRecord[],
): EpisodeReport["tickBudgets"] {
  const grouped = new Map<string, DecisionRecord[]>();
  for (const decision of decisions) {
    if (!decision.executedSkill) continue;
    const bucket = grouped.get(decision.executedSkill) ?? [];
    bucket.push(decision);
    grouped.set(decision.executedSkill, bucket);
  }
  const mean = (values: number[]): number =>
    values.length === 0
      ? 0
      : Number((values.reduce((a, b) => a + b, 0) / values.length).toFixed(1));
  return [...grouped]
    .map(([skill, runs]) => ({
      skill,
      runs: runs.length,
      budgetTicks: runs[0]?.budgetTicks ?? 0,
      meanElapsedTicks: mean(runs.map((run) => run.elapsedTicks)),
      maxElapsedTicks: Math.max(...runs.map((run) => run.elapsedTicks)),
      worstPressure: Number(
        Math.max(...runs.map((run) => run.budgetPressure)).toFixed(4),
      ),
      meanNavigationTicks: mean(runs.map((run) => run.navigationTicks)),
      meanInteractionTicks: mean(runs.map((run) => run.interactionTicks)),
      timeouts: runs.filter((run) => run.status === "TIMED_OUT").length,
    }))
    .sort((a, b) => b.worstPressure - a.worstPressure);
}

/**
 * Per-episode report.
 *
 * Every strategic decision is recorded with the context it was made in, the
 * evidence behind it, what was requested, what the runtime allowed, what
 * actually ran, and what changed. The expected effects are kept alongside the
 * observed ones so a later world model can compute prediction error from the
 * same record rather than needing the episode re-run.
 */
export class EpisodeReportBuilder {
  readonly #report: EpisodeReport;

  constructor(
    initial: Omit<
      EpisodeReport,
      | "decisions"
      | "safetyOverrides"
      | "totals"
      | "finishedAt"
      | "outcome"
      | "reason"
      | "endTick"
      | "elapsedTicks"
      | "storageProvenance"
      | "tickBudgets"
    >,
  ) {
    this.#report = {
      ...initial,
      finishedAt: initial.startedAt,
      outcome: "failed",
      reason: null,
      endTick: initial.startTick,
      elapsedTicks: 0,
      decisions: [],
      safetyOverrides: [],
      storageProvenance: [],
      tickBudgets: [],
      totals: {
        decisions: 0,
        accepted: 0,
        replaced: 0,
        rejected: 0,
        learnedDecisions: 0,
        fallbackDecisions: 0,
        successes: 0,
        failures: 0,
        emergencies: 0,
        healthLost: 0,
        resourceDelta: [],
      },
    };
  }

  addDecision(record: DecisionRecord): void {
    this.#report.decisions.push(record);
    const totals = this.#report.totals;
    totals.decisions += 1;
    if (record.validation === "ACCEPT") totals.accepted += 1;
    if (record.validation === "REPLACE") totals.replaced += 1;
    if (record.validation === "REJECT") totals.rejected += 1;
    if (record.learnedOrFallback === "learned") totals.learnedDecisions += 1;
    else totals.fallbackDecisions += 1;
    if (record.status === "SUCCESS") totals.successes += 1;
    else totals.failures += 1;
    if (record.emergency) totals.emergencies += 1;
    if (record.healthDelta < 0) totals.healthLost += -record.healthDelta;
  }

  addSafetyOverride(entry: EpisodeReport["safetyOverrides"][number]): void {
    this.#report.safetyOverrides.push(entry);
  }

  setStorageProvenance(records: unknown[]): void {
    this.#report.storageProvenance = records;
  }

  finish(
    outcome: EpisodeReport["outcome"],
    reason: string | null,
    endTick: number,
  ): EpisodeReport {
    this.#report.outcome = outcome;
    this.#report.reason = reason;
    this.#report.finishedAt = new Date().toISOString();
    this.#report.endTick = endTick;
    this.#report.elapsedTicks = Math.max(0, endTick - this.#report.startTick);
    this.#report.totals.resourceDelta = mergeDeltas(
      this.#report.decisions.map((decision) => decision.inventoryDelta),
    );
    this.#report.tickBudgets = summariseTickBudgets(this.#report.decisions);
    return this.#report;
  }

  get report(): EpisodeReport {
    return this.#report;
  }
}

export function writeEpisodeReport(
  directory: string,
  report: EpisodeReport,
): string {
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const file = path.join(directory, `episode-${report.episodeId}.json`);
  const temporary = `${file}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(report, null, 2)}\n`, {
    mode: 0o600,
  });
  renameSync(temporary, file);
  return file;
}

/** A short human-readable form of the same facts, for terminal output. */
export function summariseEpisode(report: EpisodeReport): string {
  const lines: string[] = [];
  lines.push(
    `Episode ${report.episodeId} (${report.outcome}${report.reason ? `: ${report.reason}` : ""})`,
  );
  lines.push(
    `  person=${report.personId} world=${report.worldId} context=${report.trainingContext} learning=${report.learningMode}`,
  );
  lines.push(
    `  decisions=${report.totals.decisions} accepted=${report.totals.accepted} replaced=${report.totals.replaced} rejected=${report.totals.rejected}`,
  );
  lines.push(
    `  learned=${report.totals.learnedDecisions} fallback=${report.totals.fallbackDecisions} successes=${report.totals.successes} failures=${report.totals.failures}`,
  );
  lines.push(
    `  emergencies=${report.totals.emergencies} healthLost=${report.totals.healthLost} ticks=${report.elapsedTicks}`,
  );
  for (const decision of report.decisions) {
    const executed = decision.executedSkill ?? "none";
    const attribution =
      decision.requestedSkill === executed
        ? executed
        : `${decision.requestedSkill} -> ${executed}`;
    lines.push(
      `  [${decision.tick}] ${decision.goalType} via ${decision.routineName} (${decision.learnedOrFallback}) ${attribution} ${decision.status}`,
    );
  }
  const pressured = report.tickBudgets.filter(
    (entry) => entry.worstPressure >= 0.5,
  );
  if (pressured.length)
    lines.push(
      `  tick budgets under pressure: ${pressured
        .map(
          (entry) =>
            `${entry.skill} ${Math.round(entry.worstPressure * 100)}% of ${entry.budgetTicks}`,
        )
        .join(", ")}`,
    );
  if (report.totals.resourceDelta.length)
    lines.push(
      `  resources: ${report.totals.resourceDelta
        .map((item) => `${item.name}${item.delta > 0 ? "+" : ""}${item.delta}`)
        .join(" ")}`,
    );
  return lines.join("\n");
}

export type { SkillOutcome };
