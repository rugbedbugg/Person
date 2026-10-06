import { ConfigError } from "#config";
import { validateMinecraftConfig, type MinecraftConfig } from "./config.ts";

/**
 * Compatibility only. Earlier configuration formats were Minecraft-only by
 * construction, so reading them is the Minecraft profile's business: a
 * Shroud V1 document, and a Person configVersion 2 document whose
 * `runtime.trainingContext` folded environment, embodiment and difficulty
 * into one value (ADR 0025). Nothing here is ever written back to a file.
 */

export interface MigrationResult {
  config: MinecraftConfig;
  fromVersion: "shroud-v1" | "person-v2" | "person-v3";
  notes: string[];
}

/** The difficulty a v2 `trainingContext` stood for. */
const LEGACY_DIFFICULTY: Record<string, "peaceful" | "normal" | undefined> = {
  minecraft_peaceful: "peaceful",
  minecraft_normal: "normal",
};

/**
 * Upgrades a configVersion 2 document to version 3, in memory. A version 3
 * document, or anything that is not a version 2 document, is returned as it
 * came, for the schema to judge.
 */
export function upgradeConfigDocument(document: unknown): {
  document: unknown;
  notes: string[];
} {
  if (!isRecord(document) || document["configVersion"] !== 2)
    return { document, notes: [] };
  const runtime = isRecord(document["runtime"]) ? document["runtime"] : {};
  const { trainingContext, embodiment, ...rest } = runtime as Record<
    string,
    unknown
  >;
  const body = embodiment === "minecraft" ? "mineflayer" : embodiment;
  const difficulty = LEGACY_DIFFICULTY[String(trainingContext)];
  const notes = [
    `configVersion 2 read as 3: runtime.trainingContext ${JSON.stringify(trainingContext)} became environment.kind "minecraft"` +
      (body === "mineflayer" && difficulty
        ? `, runtime.embodiment "mineflayer" and environment.difficulty "${difficulty}"`
        : `, runtime.embodiment ${JSON.stringify(body)}`),
  ];
  if (trainingContext === "replay")
    notes.push(
      'trainingContext "replay" is not a configured context any more; replay is an experience context of records, never of a running body',
    );
  return {
    document: {
      ...document,
      configVersion: 3,
      environment: {
        kind: "minecraft",
        ...(body === "mineflayer" && difficulty ? { difficulty } : {}),
      },
      runtime: { ...rest, embodiment: body },
    },
    notes,
  };
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

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

/** True for a Shroud V1 config document. */
export function isLegacyConfig(document: unknown): boolean {
  if (!isRecord(document)) return false;
  if (document["configVersion"] === 2 || document["configVersion"] === 3)
    return false;
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
    const upgraded = upgradeConfigDocument(document);
    return {
      config: validateMinecraftConfig(upgraded.document, baseDirectory),
      fromVersion: document["configVersion"] === 2 ? "person-v2" : "person-v3",
      notes: upgraded.notes,
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
  const difficulty =
    difficultyMode === "peaceful-training" ? "peaceful" : "normal";

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
    configVersion: 3,
    personId,
    worldId: (legacy["worldId"] as string | undefined) ?? "migrated-world",
    environment: { kind: "minecraft", difficulty },
    runtime: {
      embodiment: "mineflayer",
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
    config: validateMinecraftConfig(migrated, baseDirectory),
    fromVersion: "shroud-v1",
    notes,
  };
}

/**
 * The experience stream a pre-v20 journal record's `training_context` always
 * meant: the same table as `person_persistence.legacy` (ADR 0025). Old
 * records are read with it and never rewritten.
 */
export const LEGACY_EXPERIENCE_KEYS: Readonly<Record<string, string>> = {
  fixture: "lived:minecraft/fixture",
  minecraft_peaceful: "lived:minecraft/mineflayer/peaceful",
  minecraft_normal: "lived:minecraft/mineflayer/normal",
  replay: "replay:minecraft/unknown",
};
