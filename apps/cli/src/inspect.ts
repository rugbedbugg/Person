import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";

export interface EvidenceSummary {
  directory: string;
  exists: boolean;
  segments: number;
  events: number;
  truncatedTailRecords: number;
  duplicateRecords: number;
  eventTypes: Record<string, number>;
  routines: {
    trainingContext: string;
    contextId: string;
    routineId: string;
    attempts: number;
    successes: number;
    failures: number;
    posteriorMean: number;
  }[];
  skillAttribution: {
    trainingContext: string;
    contextId: string;
    skillId: string;
    attempts: number;
    successes: number;
    preemptions: number;
  }[];
  snapshots: number;
  latestSnapshotTick: number | null;
}

interface Counts {
  attempts: number;
  successes: number;
  failures: number;
  preemptions: number;
}

const blank = (): Counts => ({
  attempts: 0,
  successes: 0,
  failures: 0,
  preemptions: 0,
});

const FAILURE = new Set([
  "FAILED",
  "TIMED_OUT",
  "UNREACHABLE",
  "INVALIDATED",
  "DEATH",
  "DISCONNECTED",
]);

/**
 * Reads the evidence store the way cognition does, without importing it.
 *
 * Two independent readers of the same journal is a cheap and useful check:
 * if this disagrees with the learner, one of them is wrong about the format.
 */
export class EvidenceInspector {
  readonly directory: string;

  constructor(directory: string) {
    this.directory = directory;
  }

  summarise(): EvidenceSummary {
    const journal = path.join(this.directory, "journal");
    const snapshots = path.join(this.directory, "snapshots");
    const summary: EvidenceSummary = {
      directory: this.directory,
      exists: existsSync(journal),
      segments: 0,
      events: 0,
      truncatedTailRecords: 0,
      duplicateRecords: 0,
      eventTypes: {},
      routines: [],
      skillAttribution: [],
      snapshots: 0,
      latestSnapshotTick: null,
    };
    if (!summary.exists) return summary;

    const files = readdirSync(journal)
      .filter((name) => name.endsWith(".jsonl"))
      .sort();
    summary.segments = files.length;
    const routines = new Map<string, Counts>();
    const skills = new Map<string, Counts>();
    const seen = new Set<string>();

    for (const [fileIndex, file] of files.entries()) {
      const raw = readFileSync(path.join(journal, file), "utf8");
      if (!raw) continue;
      const complete = raw.endsWith("\n");
      const lines = raw.split("\n");
      if (lines.at(-1) === "") lines.pop();
      for (const [index, line] of lines.entries()) {
        const lastLine =
          fileIndex === files.length - 1 && index === lines.length - 1;
        let event: Record<string, unknown>;
        try {
          event = JSON.parse(line) as Record<string, unknown>;
        } catch {
          if (lastLine && !complete) summary.truncatedTailRecords += 1;
          else
            throw new Error(
              `${file} line ${index + 1} is not readable evidence`,
            );
          continue;
        }
        const id = String(event["event_id"]);
        if (seen.has(id)) {
          summary.duplicateRecords += 1;
          continue;
        }
        seen.add(id);
        summary.events += 1;
        const type = String(event["type"]);
        summary.eventTypes[type] = (summary.eventTypes[type] ?? 0) + 1;
        const payload = (event["payload"] ?? {}) as Record<string, unknown>;
        const trainingContext = String(event["training_context"] ?? "");
        const contextId = String(payload["context_id"] ?? "");

        if (type === "routine_outcome") {
          const key = `${trainingContext}|${contextId}|${String(payload["routine_id"] ?? "")}`;
          const counts = routines.get(key) ?? blank();
          counts.attempts += 1;
          const status = String(payload["status"] ?? "");
          if (status === "SUCCESS") counts.successes += 1;
          else if (FAILURE.has(status)) counts.failures += 1;
          routines.set(key, counts);
        }
        if (
          type === "skill_completed" ||
          type === "skill_failed" ||
          type === "skill_interrupted"
        ) {
          const executed = payload["executed_skill"];
          const requested = payload["requested_skill"];
          if (typeof executed === "string") {
            const key = `${trainingContext}|${contextId}|${executed}`;
            const counts = skills.get(key) ?? blank();
            counts.attempts += 1;
            const status = String(payload["status"] ?? "");
            if (status === "SUCCESS") counts.successes += 1;
            else if (FAILURE.has(status)) counts.failures += 1;
            skills.set(key, counts);
          }
          if (typeof requested === "string" && requested !== executed) {
            const key = `${trainingContext}|${contextId}|${requested}`;
            const counts = skills.get(key) ?? blank();
            counts.preemptions += 1;
            skills.set(key, counts);
          }
        }
      }
    }

    summary.routines = [...routines]
      .map(([key, counts]) => {
        const [trainingContext = "", contextId = "", routineId = ""] =
          key.split("|");
        return {
          trainingContext,
          contextId,
          routineId,
          attempts: counts.attempts,
          successes: counts.successes,
          failures: counts.failures,
          posteriorMean:
            (1 + counts.successes) / (2 + counts.successes + counts.failures),
        };
      })
      .sort((a, b) => a.routineId.localeCompare(b.routineId));

    summary.skillAttribution = [...skills]
      .map(([key, counts]) => {
        const [trainingContext = "", contextId = "", skillId = ""] =
          key.split("|");
        return {
          trainingContext,
          contextId,
          skillId,
          attempts: counts.attempts,
          successes: counts.successes,
          preemptions: counts.preemptions,
        };
      })
      .sort((a, b) => a.skillId.localeCompare(b.skillId));

    if (existsSync(snapshots)) {
      const files = readdirSync(snapshots).filter((name) =>
        name.endsWith(".json"),
      );
      summary.snapshots = files.length;
      const latest = files.sort().at(-1);
      if (latest) {
        try {
          const document = JSON.parse(
            readFileSync(path.join(snapshots, latest), "utf8"),
          ) as {
            tick?: number;
          };
          summary.latestSnapshotTick = document.tick ?? null;
        } catch {
          summary.latestSnapshotTick = null;
        }
      }
    }
    return summary;
  }

  render(summary: EvidenceSummary): string {
    if (!summary.exists) return `No evidence store at ${summary.directory}`;
    const lines = [
      `Evidence store ${summary.directory}`,
      `  segments=${summary.segments} events=${summary.events} snapshots=${summary.snapshots} snapshotTick=${summary.latestSnapshotTick ?? "none"}`,
      `  truncatedTail=${summary.truncatedTailRecords} duplicates=${summary.duplicateRecords}`,
      `  event types: ${Object.entries(summary.eventTypes)
        .map(([type, count]) => `${type}=${count}`)
        .join(" ")}`,
      "  routines:",
    ];
    for (const routine of summary.routines)
      lines.push(
        `    ${routine.routineId} [${routine.trainingContext}] ${routine.contextId} attempts=${routine.attempts} successes=${routine.successes} mean=${routine.posteriorMean.toFixed(3)}`,
      );
    lines.push("  executed-skill attribution:");
    for (const skill of summary.skillAttribution)
      lines.push(
        `    ${skill.skillId} attempts=${skill.attempts} successes=${skill.successes} preemptions=${skill.preemptions}`,
      );
    return lines.join("\n");
  }
}
