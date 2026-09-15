import { ConfigError, validateConfig } from "./load.ts";
import type { PersonConfig } from "./types.ts";

export interface MigrationResult {
  config: PersonConfig;
  fromVersion: "shroud-v1" | "person-v2";
  notes: string[];
}

export const LEGACY_CHECKPOINT_DIAGNOSTIC = [
  "Legacy Shroud V1 learning checkpoint detected.",
  "",
  "V1 Q-learning checkpoints are incompatible with the",
  "Person hierarchical skill policy.",
  "",
  "The checkpoint has not been modified.",
  "",
  "Start a new Person evidence store or import reviewed",
  "historical traces through the demonstration mechanism.",
].join("\n");

/**
 * Recognises a Shroud V1 tabular Q-learning checkpoint.
 *
 * There is no conversion path. The V1 policy is a table over seven integer
 * action ids; Person selects routines built from typed skills in a coarse
 * semantic context. Any mapping between them would be invented, not learned.
 */
export function isLegacyLearningCheckpoint(document: unknown): boolean {
  if (typeof document !== "object" || document === null) return false;
  const record = document as Record<string, unknown>;
  const schema = record["schema"];
  const hasTable =
    Array.isArray(record["entries"]) && Array.isArray(record["actions"]);
  return (
    (typeof schema === "string" && schema.startsWith("shroud-rl-v")) || hasTable
  );
}

export class LegacyCheckpointError extends Error {
  constructor() {
    super(LEGACY_CHECKPOINT_DIAGNOSTIC);
    this.name = "LegacyCheckpointError";
  }
}

export function assertNotLegacyCheckpoint(document: unknown): void {
  if (isLegacyLearningCheckpoint(document)) throw new LegacyCheckpointError();
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/** True for a Shroud V1 config document. */
export function isLegacyConfig(document: unknown): boolean {
  if (!isRecord(document)) return false;
  if (document["configVersion"] === 2) return false;
  return (
    "exploration" in document &&
    "resourceAreas" in document &&
    "outputDirectory" in document
  );
}

/**
 * Migrates a Shroud V1 configuration to the Person contract.
 *
 * Learning is deliberately not carried across: V1 `learningMode` refers to a
 * learner that no longer exists, and enabling learning is always an explicit
 * operator decision.
 */
export function migrateConfig(
  document: unknown,
  baseDirectory: string,
): MigrationResult {
  if (!isLegacyConfig(document)) {
    if (!isRecord(document))
      throw new ConfigError("Configuration must be an object");
    return {
      config: validateConfig(document, baseDirectory),
      fromVersion: "person-v2",
      notes: [],
    };
  }
  const legacy = document as Record<string, never>;
  const notes: string[] = [];
  const username =
    (legacy["bot"]?.["username"] as string | undefined) ?? "PersonBot";
  const personId =
    username
      .toLowerCase()
      .replace(/[^a-z0-9_-]/g, "")
      .slice(0, 32) || "person";
  const difficultyMode =
    (legacy["difficultyMode"] as string | undefined) ?? "normal";
  const trainingContext =
    difficultyMode === "peaceful-training"
      ? "minecraft_peaceful"
      : "minecraft_normal";

  if (legacy["learningMode"] && legacy["learningMode"] !== "off")
    notes.push(
      `learningMode "${String(
        legacy["learningMode"],
      )}" was not carried over; Person starts with learning.mode = "off" and never enables learning implicitly`,
    );
  if (legacy["spawn"])
    notes.push(
      "spawn bounds were dropped; Person validates its spawn against the exploration area",
    );
  if (legacy["maxChunks"])
    notes.push(
      "maxChunks was dropped; chunk retention is an adapter concern in Person",
    );

  const migrated = {
    configVersion: 2,
    personId,
    worldId: (legacy["worldId"] as string | undefined) ?? "migrated-world",
    runtime: {
      embodiment: "minecraft",
      trainingContext,
      outputDirectory: legacy["outputDirectory"] as unknown as string,
    },
    learning: { mode: "off" },
    cognition: { command: ["uv", "run", "person-cognition"] },
    server: legacy["server"],
    bot: legacy["bot"],
    authorization: {
      worldOwnerApproved: true,
      dedicatedIdentity: true,
      resourceAreasAreUnowned: true,
      naturalDaylightCycle: true,
      normalDifficulty: difficultyMode !== "peaceful-training",
    },
    world: {
      home: legacy["home"],
      exploration: legacy["exploration"],
      resourceAreas: legacy["resourceAreas"],
      protectedAreas: legacy["protectedAreas"] ?? [],
    },
    permissions: {
      containers: {
        existing: { withdraw: true, deposit: false },
        owned: { withdraw: true, deposit: true },
      },
      hunting: {
        passiveUnnamedAnimals: true,
        namedAnimals: false,
        tamedAnimals: false,
      },
      players: { combat: false },
      villagers: { harm: false },
      building: { enabled: true },
      protectedAreas: { enforcement: "strict" },
    },
  };
  notes.push(
    "permissions were defaulted: existing containers are withdraw-only and never deposited into",
  );
  return {
    config: validateConfig(migrated, baseDirectory),
    fromVersion: "shroud-v1",
    notes,
  };
}
