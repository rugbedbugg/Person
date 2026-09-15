import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import type { Position } from "#config";

export const STATUS_SCHEMA_VERSION = 1;

export type ConnectionState =
  "starting" | "connecting" | "ready" | "disconnected" | "failed";

/**
 * A snapshot of what Person is doing, for a human watching from outside.
 *
 * This is telemetry, not a channel. The runtime writes it; the `person status`
 * command reads it. Nothing reads it back into a decision, and cognition never
 * sees it at all, so watching Person cannot change what Person does.
 *
 * It is a file rather than a socket or a service on purpose: an operator needs
 * to see the last known state after a run has ended just as often as during
 * one, and a file is the only thing that survives the process.
 */
export interface RuntimeStatus {
  schemaVersion: number;
  updatedAt: string;
  command: string;
  connection: ConnectionState;
  readiness: string;
  failureReason: string | null;
  failureHint: string | null;

  personId: string;
  botUsername: string | null;
  worldId: string;
  sessionId: string;
  episodeId: string | null;
  server: { host: string; port: number; version: string } | null;

  embodiment: string;
  trainingContext: string;
  learningMode: string;
  policyRevision: number;
  operatorIntervention: { flagged: boolean; reason: string | null };

  tick: number | null;
  dimension: string | null;
  position: Position | null;
  health: number | null;
  food: number | null;

  goal: string | null;
  goalType: string | null;
  routine: string | null;
  skill: string | null;

  home: {
    position: Position;
    distance: number | null;
    shelterState: string;
  } | null;
  lastSafePosition: Position | null;

  safety: {
    threat: string;
    emergencies: number;
    lastEmergency: { trigger: string; action: string; level: string } | null;
  };
  lastValidation: {
    decision: string;
    level: string;
    requestedSkill: string;
    executedSkill: string | null;
    reasonCodes: string[];
  } | null;
  decisions: number;
}

export function statusPath(
  outputDirectory: string,
  worldId: string,
  personId: string,
): string {
  return path.join(outputDirectory, "status", `${worldId}-${personId}.json`);
}

const blank = (seed: Partial<RuntimeStatus>): RuntimeStatus => ({
  schemaVersion: STATUS_SCHEMA_VERSION,
  updatedAt: new Date().toISOString(),
  command: "unknown",
  connection: "starting",
  readiness: "not started",
  failureReason: null,
  failureHint: null,
  personId: "unknown",
  botUsername: null,
  worldId: "unknown",
  sessionId: "unknown",
  episodeId: null,
  server: null,
  embodiment: "unknown",
  trainingContext: "unknown",
  learningMode: "off",
  policyRevision: 0,
  operatorIntervention: { flagged: false, reason: null },
  tick: null,
  dimension: null,
  position: null,
  health: null,
  food: null,
  goal: null,
  goalType: null,
  routine: null,
  skill: null,
  home: null,
  lastSafePosition: null,
  safety: { threat: "none", emergencies: 0, lastEmergency: null },
  lastValidation: null,
  decisions: 0,
  ...seed,
});

/**
 * Writes the status file atomically.
 *
 * A reader polling this file must never catch it half-written, and a crash
 * must never leave it unparseable, so every update is a temporary file and a
 * rename. Write failures are swallowed: telemetry must not be able to stop
 * Person from running.
 */
export class StatusWriter {
  readonly file: string;
  #status: RuntimeStatus;
  #enabled = true;

  constructor(file: string, seed: Partial<RuntimeStatus>) {
    this.file = file;
    this.#status = blank(seed);
    this.write();
  }

  get status(): RuntimeStatus {
    return this.#status;
  }

  update(patch: Partial<RuntimeStatus>): void {
    this.#status = {
      ...this.#status,
      ...patch,
      updatedAt: new Date().toISOString(),
    };
    this.write();
  }

  private write(): void {
    if (!this.#enabled) return;
    try {
      mkdirSync(path.dirname(this.file), { recursive: true, mode: 0o700 });
      const temporary = `${this.file}.tmp`;
      writeFileSync(temporary, `${JSON.stringify(this.#status, null, 2)}\n`, {
        mode: 0o600,
      });
      renameSync(temporary, this.file);
    } catch {
      // Telemetry is never allowed to be the reason a run fails.
      this.#enabled = false;
    }
  }
}

export function readStatus(file: string): RuntimeStatus | null {
  if (!existsSync(file)) return null;
  try {
    const document: unknown = JSON.parse(readFileSync(file, "utf8"));
    if (
      typeof document !== "object" ||
      document === null ||
      (document as RuntimeStatus).schemaVersion !== STATUS_SCHEMA_VERSION
    )
      return null;
    return document as RuntimeStatus;
  } catch {
    return null;
  }
}

/** How long ago the status was written, in seconds. */
export function stalenessSeconds(
  status: RuntimeStatus,
  now = Date.now(),
): number {
  const written = Date.parse(status.updatedAt);
  return Number.isNaN(written)
    ? Number.POSITIVE_INFINITY
    : (now - written) / 1000;
}

const place = (position: Position | null): string =>
  position ? `${position.x},${position.y},${position.z}` : "unknown";

export function renderStatus(status: RuntimeStatus, now = Date.now()): string {
  const age = stalenessSeconds(status, now);
  const lines: string[] = [];
  lines.push(
    `Person ${status.personId}${status.botUsername ? ` (in Minecraft as ${status.botUsername})` : ""}`,
  );
  lines.push(
    `  state     ${status.connection}, ${status.readiness}${
      status.failureReason ? ` [${status.failureReason}]` : ""
    }`,
  );
  if (status.failureHint) lines.push(`  hint      ${status.failureHint}`);
  lines.push(
    `  updated   ${status.updatedAt} (${age < 0 ? 0 : Math.round(age)}s ago)${
      age > 30 ? "  STALE: nothing is writing this" : ""
    }`,
  );
  lines.push(
    `  session   world=${status.worldId} session=${status.sessionId.slice(0, 8)} episode=${status.episodeId ?? "none"} command=${status.command}`,
  );
  lines.push(
    `  server    ${status.server ? `${status.server.host}:${status.server.port} (${status.server.version})` : `none (${status.embodiment})`}`,
  );
  lines.push(
    `  where     ${status.dimension ?? "unknown"} at ${place(status.position)} health=${status.health ?? "?"} food=${status.food ?? "?"} tick=${status.tick ?? "?"}`,
  );
  lines.push(
    `  doing     goal=${status.goalType ?? status.goal ?? "none"} routine=${status.routine ?? "none"} skill=${status.skill ?? "none"}`,
  );
  lines.push(
    `  home      ${
      status.home
        ? `${place(status.home.position)} distance=${
            status.home.distance === null
              ? "unknown"
              : status.home.distance.toFixed(1)
          } shelter=${status.home.shelterState}`
        : "unknown"
    }`,
  );
  lines.push(`  lastSafe  ${place(status.lastSafePosition)}`);
  lines.push(
    `  safety    threat=${status.safety.threat} emergencies=${status.safety.emergencies}${
      status.safety.lastEmergency
        ? ` last=${status.safety.lastEmergency.level}/${status.safety.lastEmergency.trigger} -> ${status.safety.lastEmergency.action}`
        : ""
    }`,
  );
  lines.push(
    `  validated ${
      status.lastValidation
        ? `${status.lastValidation.decision} (${status.lastValidation.level}) ${status.lastValidation.requestedSkill}${
            status.lastValidation.executedSkill &&
            status.lastValidation.executedSkill !==
              status.lastValidation.requestedSkill
              ? ` replaced by ${status.lastValidation.executedSkill}`
              : ""
          }${
            status.lastValidation.reasonCodes.length
              ? ` [${status.lastValidation.reasonCodes.slice(0, 4).join(", ")}]`
              : ""
          }`
        : "nothing yet"
    }`,
  );
  lines.push(
    `  learning  mode=${status.learningMode} policyRevision=${status.policyRevision} trainingContext=${status.trainingContext} decisions=${status.decisions}`,
  );
  if (status.operatorIntervention.flagged)
    lines.push(
      `  OPERATOR INTERVENTION: this run is marked contaminated${
        status.operatorIntervention.reason
          ? ` (${status.operatorIntervention.reason})`
          : ""
      }`,
    );
  return lines.join("\n");
}
