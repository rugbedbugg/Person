import { execFile } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import type { Observation } from "#protocol";

/**
 * Asks the existing prediction-error code whether a skill did what it said.
 *
 * The comparison is not reimplemented here. It lives in the cognition package,
 * on top of the same symbolic state the planner reasons over, and this runs it
 * once over two observations instead of over a live decision. A second
 * implementation in Node would drift from the first one, and then a validation
 * report and a prediction-error record would quietly stop meaning the same
 * thing.
 *
 * What crosses the boundary is a question and an answer, both JSON, neither of
 * them a request for anything physical. The comparison cannot propose, cannot
 * execute, and is never consulted about what to run.
 */

export type EffectVerdict =
  "match" | "mismatch" | "not_observable" | "inconclusive";

export interface EffectFactComparison {
  fact: string;
  op: string;
  predictedValue: number;
  before: number;
  predicted: number | null;
  observed: number | null;
  severity: string;
  verdict: EffectVerdict;
}

export interface EffectComparison {
  available: boolean;
  reason: string | null;
  facts: EffectFactComparison[];
  unexplained: { fact: string; before: number; observed: number }[];
  worstSeverity: string;
  matched: number;
  mismatched: number;
  notObservable: number;
  inconclusive: number;
}

export interface EffectComparisonRequest {
  expectedEffects: { fact: string; op: string; value: number }[];
  before: Observation;
  after: Observation | null;
}

/** Everything inconclusive, because the comparison itself could not be made. */
export function unavailableComparison(
  request: EffectComparisonRequest,
  reason: string,
): EffectComparison {
  return {
    available: false,
    reason,
    facts: request.expectedEffects.map((effect) => ({
      fact: effect.fact,
      op: effect.op,
      predictedValue: effect.value,
      before: 0,
      predicted: null,
      observed: null,
      severity: "unobserved",
      verdict: "inconclusive" as const,
    })),
    unexplained: [],
    worstSeverity: "unobserved",
    matched: 0,
    mismatched: 0,
    notObservable: 0,
    inconclusive: request.expectedEffects.length,
  };
}

export interface EffectComparisonOptions {
  /** The cognition command from configuration, used as a one-shot analyser. */
  command: string[];
  cwd: string;
  timeoutMs?: number;
}

export async function compareEffects(
  request: EffectComparisonRequest,
  options: EffectComparisonOptions,
): Promise<EffectComparison> {
  const [program, ...rest] = options.command;
  if (!program)
    return unavailableComparison(request, "no_comparison_command_configured");

  const directory = mkdtempSync(path.join(tmpdir(), "person-effects-"));
  const file = path.join(directory, "request.json");
  try {
    writeFileSync(file, JSON.stringify(request), { mode: 0o600 });
    const stdout = await new Promise<string>((resolve, reject) => {
      execFile(
        program,
        [...rest, "--compare-effects", file],
        {
          cwd: options.cwd,
          timeout: options.timeoutMs ?? 30000,
          maxBuffer: 8 * 1024 * 1024,
        },
        (error, out) => (error ? reject(error) : resolve(out)),
      );
    });
    const parsed: unknown = JSON.parse(stdout);
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      !Array.isArray((parsed as EffectComparison).facts)
    )
      return unavailableComparison(request, "comparison_output_unreadable");
    return parsed as EffectComparison;
  } catch (error) {
    // A missing interpreter must not cost the run its report: the observations
    // are already captured, and they are the part that cannot be retaken.
    const reason = (error as { code?: string }).code;
    return unavailableComparison(
      request,
      typeof reason === "string" && reason.length <= 32
        ? `comparison_failed_${reason.toLowerCase()}`
        : "comparison_failed",
    );
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}
