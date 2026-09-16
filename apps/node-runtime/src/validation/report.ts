import { mkdirSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { Position } from "#config";
import type {
  CostLimits,
  Observation,
  SkillInvocation,
  SkillOutcome,
  SkillParameters,
  TerminalStatus,
} from "#protocol";
import type { EffectComparison } from "./effects.ts";
import type { LearningFingerprint } from "./learning-state.ts";

export const SKILL_VALIDATION_REPORT_VERSION = 1;

/**
 * The record of one operator-run single-skill validation.
 *
 * An episode report is about a run of Person deciding things. This is about a
 * human deciding one thing and watching what the body did with it, so it keeps
 * both observations in full: the point of the exercise is that the world before
 * and the world after can be read by somebody who was not there.
 *
 * It is written to a separate directory from episode reports and from the
 * evidence store, because a validation run is explicitly not an experience.
 */
export interface SkillValidationReport {
  schemaVersion: typeof SKILL_VALIDATION_REPORT_VERSION;
  testId: string;
  startedAt: string;
  finishedAt: string;

  personId: string;
  worldId: string;
  sessionId: string;
  embodiment: string;
  minecraftVersion: string | null;
  trainingContext: string;
  protocolVersion: string;
  skillLibraryRevision: string;

  /** What the operator asked for. */
  requestedSkill: string;
  requestedParameters: SkillParameters;
  requestedLimits: CostLimits | null;
  /** The exact proposal that entered the runtime, or null if it never did. */
  invocation: SkillInvocation | null;

  /** What the safety kernel said about it. */
  safety: {
    decision: string | null;
    level: string | null;
    reasonCodes: string[];
    executedSkill: string | null;
    executedParameters: SkillParameters | null;
    executedLimits: CostLimits | null;
    emergency: { level: string; trigger: string; action: string } | null;
  };
  /** What actually ran. Never assumed to be what was requested. */
  actualSkill: string | null;

  operatorSetup: boolean;
  operatorIntervention: { flagged: boolean; reason: string | null };
  timeline: {
    connectedAt: string | null;
    setupStartedAt: string | null;
    setupCompletedAt: string | null;
    skillStartedAt: string | null;
    skillFinishedAt: string | null;
    disconnectedAt: string | null;
    elapsedMs: number;
  };

  preObservation: Observation | null;
  preObservationValid: boolean;
  postObservation: Observation | null;
  postObservationValid: boolean;
  postObservationReason: string | null;

  outcome: SkillOutcome | null;
  terminalStatus: TerminalStatus | null;
  requestedSkillStatus: TerminalStatus | null;
  elapsedTicks: number;
  completionEvidence: {
    kinds: string[];
    details: Record<string, number | string | boolean | null>;
  } | null;

  expectedEffects: { fact: string; op: string; value: number }[];
  observedEffects: string[];
  effectComparison: EffectComparison | null;

  /** Enough to diagnose navigation without replaying the run. */
  navigation: {
    homePosition: Position | null;
    startPosition: Position | null;
    endPosition: Position | null;
    homeDistanceBefore: number | null;
    homeDistanceAfter: number | null;
    routeStatusBefore: string | null;
    routeStatusAfter: string | null;
    stuckStateBefore: string | null;
    stuckStateAfter: string | null;
  };

  learning: {
    mode: string;
    policyRevisionBefore: number;
    policyRevisionAfter: number;
    evidenceBefore: LearningFingerprint | null;
    evidenceAfter: LearningFingerprint | null;
    changed: boolean;
  };

  disconnect: {
    status: "clean" | "timed_out" | "failed";
    detail: string | null;
  };
  result: "completed" | "refused" | "failed";
  failure: { reason: string; detail: string | null } | null;
}

export function skillValidationDirectory(outputDirectory: string): string {
  return path.join(outputDirectory, "validation", "skill-tests");
}

export function writeSkillValidationReport(
  directory: string,
  report: SkillValidationReport,
): string {
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const file = path.join(
    directory,
    `${report.worldId}-${report.personId}-${report.requestedSkill}-${report.testId}.json`,
  );
  const temporary = `${file}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(report, null, 2)}\n`, {
    mode: 0o600,
  });
  renameSync(temporary, file);
  return file;
}

const distanceText = (value: number | null): string =>
  value === null ? "unknown" : value.toFixed(1);

/** The short form an operator reads in the terminal. Details live in the file. */
export function summariseSkillValidation(
  report: SkillValidationReport,
  reportPath: string | null,
): string {
  const lines: string[] = [];
  const pad = (label: string): string => label.padEnd(14, " ");
  lines.push(`Skill validation: ${report.requestedSkill}`);
  lines.push(
    `  ${pad("connected")}${report.timeline.connectedAt ? "yes" : "no"}`,
  );
  if (report.operatorSetup)
    lines.push(
      `  ${pad("setup")}operator, ${
        report.timeline.setupCompletedAt ? "confirmed" : "not confirmed"
      }`,
    );
  lines.push(`  ${pad("safety")}${report.safety.decision ?? "not reached"}`);
  if (report.safety.reasonCodes.length)
    lines.push(`  ${pad("reasons")}${report.safety.reasonCodes.join(", ")}`);
  lines.push(`  ${pad("requested")}${report.requestedSkill}`);
  lines.push(
    `  ${pad("executed")}${report.actualSkill ?? "nothing"}${
      report.actualSkill && report.actualSkill !== report.requestedSkill
        ? "  (the kernel substituted this)"
        : ""
    }`,
  );
  lines.push(`  ${pad("outcome")}${report.terminalStatus ?? "none"}`);
  if (report.requestedSkillStatus && report.actualSkill !== null)
    lines.push(`  ${pad("requested as")}${report.requestedSkillStatus}`);
  lines.push(
    `  ${pad("duration")}${report.elapsedTicks} ticks, ${Math.round(
      report.timeline.elapsedMs,
    )}ms`,
  );
  const comparison = report.effectComparison;
  lines.push(
    `  ${pad("effects")}${
      comparison
        ? `${comparison.matched} matched, ${comparison.mismatched} mismatched, ${comparison.notObservable} not observable, ${comparison.inconclusive} inconclusive${
            comparison.available ? "" : ` (${comparison.reason})`
          }`
        : "not compared"
    }`,
  );
  lines.push(
    `  ${pad("home")}${distanceText(
      report.navigation.homeDistanceBefore,
    )} before, ${distanceText(report.navigation.homeDistanceAfter)} after`,
  );
  lines.push(
    `  ${pad("learning")}${report.learning.changed ? "CHANGED" : "unchanged"} (mode=${report.learning.mode}, policyRevision ${report.learning.policyRevisionBefore} to ${report.learning.policyRevisionAfter})`,
  );
  lines.push(
    `  ${pad("disconnect")}${report.disconnect.status}${
      report.disconnect.detail ? ` (${report.disconnect.detail})` : ""
    }`,
  );
  if (report.failure)
    lines.push(
      `  ${pad("failure")}${report.failure.reason}${
        report.failure.detail ? `: ${report.failure.detail}` : ""
      }`,
    );
  lines.push(`  ${pad("report")}${reportPath ?? "not written"}`);
  return lines.join("\n");
}
