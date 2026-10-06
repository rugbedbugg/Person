import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse as parseToml } from "smol-toml";
import { Ajv2020 } from "ajv/dist/2020.js";
import type { ValidateFunction } from "ajv";
import { discoveredEnvironments, environmentManifest } from "#protocol";
import type { CoreConfig } from "./types.ts";

export const CONFIG_SCHEMA_FILE = fileURLToPath(
  new URL("../schema/person-config.schema.json", import.meta.url),
);

/** The configuration version this loader writes and validates. */
export const CONFIG_VERSION = 3;

export class ConfigError extends Error {
  readonly diagnostics: string[];
  constructor(message: string, diagnostics: string[] = []) {
    super(
      diagnostics.length
        ? `${message}:\n  - ${diagnostics.join("\n  - ")}`
        : message,
    );
    this.name = "ConfigError";
    this.diagnostics = diagnostics;
  }
}

const compiled = new Map<string, ValidateFunction>();

/**
 * The schema a document of one environment is checked against: the core
 * schema and the environment's own, together, with nothing left over that
 * neither of them owns (ADR 0025).
 */
function schemaValidator(kind: string): ValidateFunction {
  let validate = compiled.get(kind);
  if (!validate) {
    const ajv = new Ajv2020({
      strict: true,
      allErrors: true,
      allowUnionTypes: true,
    });
    const core = JSON.parse(readFileSync(CONFIG_SCHEMA_FILE, "utf8")) as {
      $id: string;
    };
    const environment = environmentManifest(kind).configSchema as {
      $id: string;
    };
    ajv.addSchema(core);
    ajv.addSchema(environment);
    validate = ajv.compile({
      type: "object",
      allOf: [{ $ref: core.$id }, { $ref: environment.$id }],
      unevaluatedProperties: false,
    });
    compiled.set(kind, validate);
  }
  return validate;
}

const DEFAULTS = {
  runtime: {
    rngSeed: null,
    maxDecisions: 400,
    maxTicks: 72000,
    decisionIntervalMs: 0,
    reconnectAttempts: 0,
    reconnectIntervalMs: 1000,
  },
  learning: {
    evidenceDirectory: "",
    snapshotEveryEvents: 50,
    explorationBonus: 0.15,
    minimumSupport: 3,
  },
  cognition: { startTimeoutMs: 20000, decisionTimeoutMs: 5000 },
} as const;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/**
 * Validates the core of a configuration together with the sections its
 * environment owns, and applies the core defaults.
 *
 * Only what is environment-neutral is decided here. The environment's own
 * semantic checks (Minecraft's world geometry, for one) belong to its profile:
 * `validateMinecraftConfig` in `#minecraft` runs this and then its own.
 */
export function validateConfig(
  input: unknown,
  baseDirectory: string = process.cwd(),
): CoreConfig & Record<string, unknown> {
  if (!isRecord(input)) throw new ConfigError("Configuration must be a table");
  if (input["configVersion"] !== CONFIG_VERSION)
    throw new ConfigError("Configuration does not match the schema", [
      `/configVersion must be ${CONFIG_VERSION}; an older document is upgraded by its environment's loader`,
    ]);
  const environment = input["environment"];
  const kind =
    isRecord(environment) && typeof environment["kind"] === "string"
      ? environment["kind"]
      : null;
  if (kind === null)
    throw new ConfigError("Configuration does not match the schema", [
      "/environment/kind is required",
    ]);
  if (!discoveredEnvironments().has(kind))
    throw new ConfigError("Configuration names an unknown environment", [
      `/environment/kind ${JSON.stringify(kind)} is not an installed environment profile`,
    ]);
  const validate = schemaValidator(kind);
  if (!validate(input))
    throw new ConfigError(
      "Configuration does not match the schema",
      (validate.errors ?? []).map(
        (e) => `${e.instancePath || "/"} ${e.message ?? "is invalid"}`,
      ),
    );
  const raw = input as unknown as CoreConfig & Record<string, unknown>;
  const config = {
    ...raw,
    runtime: {
      ...DEFAULTS.runtime,
      ...raw.runtime,
      outputDirectory: path.resolve(baseDirectory, raw.runtime.outputDirectory),
    },
    learning: { ...DEFAULTS.learning, ...raw.learning },
    cognition: { ...DEFAULTS.cognition, ...raw.cognition },
  };
  config.learning.evidenceDirectory = path.resolve(
    baseDirectory,
    raw.learning.evidenceDirectory ??
      path.join(raw.runtime.outputDirectory, "evidence"),
  );
  return config;
}

/** Parse a TOML or JSON configuration document without validating it. */
export function parseConfigDocument(text: string, filename: string): unknown {
  try {
    return filename.endsWith(".json") ? JSON.parse(text) : parseToml(text);
  } catch (error) {
    throw new ConfigError(
      `${filename} could not be parsed: ${(error as Error).message}`,
    );
  }
}

export function readConfigDocument(filename: string): {
  document: unknown;
  absolute: string;
} {
  const absolute = path.resolve(filename);
  let text: string;
  try {
    text = readFileSync(absolute, "utf8");
  } catch (error) {
    throw new ConfigError(
      `Cannot read configuration ${absolute}: ${(error as Error).message}`,
    );
  }
  return { document: parseConfigDocument(text, absolute), absolute };
}
