import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse as parseToml } from "smol-toml";
import { Ajv2020 } from "ajv/dist/2020.js";
import type { ValidateFunction } from "ajv";
import { contains, intersects } from "./geometry.ts";
import type { Box, PersonConfig } from "./types.ts";

export const CONFIG_SCHEMA_FILE = fileURLToPath(
  new URL("../schema/person-config.schema.json", import.meta.url),
);

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

let compiled: ValidateFunction | undefined;
function schemaValidator(): ValidateFunction {
  if (!compiled) {
    const ajv = new Ajv2020({
      strict: true,
      allErrors: true,
      allowUnionTypes: true,
    });
    compiled = ajv.compile(
      JSON.parse(readFileSync(CONFIG_SCHEMA_FILE, "utf8")) as object,
    );
  }
  return compiled;
}

const DEFAULTS = {
  runtime: {
    rngSeed: null,
    maxDecisions: 400,
    maxTicks: 72000,
    decisionIntervalMs: 0,
  },
  learning: {
    evidenceDirectory: "",
    snapshotEveryEvents: 50,
    explorationBonus: 0.15,
    minimumSupport: 3,
  },
  cognition: { startTimeoutMs: 20000, decisionTimeoutMs: 5000 },
} as const;

const wellFormed = (box: Box): boolean =>
  box.min.x <= box.max.x && box.min.y <= box.max.y && box.min.z <= box.max.z;

/**
 * Validates configuration and applies defaults.
 *
 * Schema validation alone is not enough: the safety-relevant invariants are
 * geometric (home inside the exploration bounds, protected areas not
 * overlapping what Person is told to use). Those are checked here, in the
 * runtime that owns physical permission.
 */
export function validateConfig(
  input: unknown,
  baseDirectory: string = process.cwd(),
): PersonConfig {
  const validate = schemaValidator();
  if (!validate(input))
    throw new ConfigError(
      "Configuration does not match the schema",
      (validate.errors ?? []).map(
        (e) => `${e.instancePath || "/"} ${e.message ?? "is invalid"}`,
      ),
    );
  const raw = input as PersonConfig;
  const problems: string[] = [];

  const config: PersonConfig = {
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

  const { world } = config;
  if (!wellFormed(world.exploration))
    problems.push("/world/exploration has reversed bounds");
  for (const [index, area] of world.resourceAreas.entries()) {
    if (!wellFormed(area))
      problems.push(`/world/resourceAreas/${index} has reversed bounds`);
    if (
      !contains(world.exploration, area.min) ||
      !contains(world.exploration, area.max)
    )
      problems.push(
        `/world/resourceAreas/${index} must fit inside the exploration bounds`,
      );
  }
  for (const [index, area] of world.protectedAreas.entries())
    if (!wellFormed(area))
      problems.push(`/world/protectedAreas/${index} has reversed bounds`);
  if (!contains(world.exploration, world.home))
    problems.push("/world/home must lie inside the exploration bounds");

  const homeFootprint: Box = {
    min: { x: world.home.x - 2, y: world.home.y - 1, z: world.home.z - 2 },
    max: { x: world.home.x + 2, y: world.home.y + 3, z: world.home.z + 2 },
  };
  for (const [index, area] of world.protectedAreas.entries())
    if (intersects(area, homeFootprint))
      problems.push(
        `/world/protectedAreas/${index} overlaps the home footprint; Person would be unable to build where it is told to live`,
      );

  if (config.runtime.embodiment === "minecraft") {
    if (!config.server)
      problems.push("/server is required when runtime.embodiment is minecraft");
    if (!config.bot)
      problems.push("/bot is required when runtime.embodiment is minecraft");
    if (!config.authorization)
      problems.push(
        "/authorization is required when runtime.embodiment is minecraft",
      );
    if (config.runtime.trainingContext === "fixture")
      problems.push(
        "/runtime/trainingContext must be a minecraft context when runtime.embodiment is minecraft",
      );
  } else if (config.runtime.trainingContext.startsWith("minecraft"))
    problems.push(
      "/runtime/trainingContext must be fixture or replay when runtime.embodiment is fixture",
    );

  if (config.permissions.containers.existing.deposit !== false)
    problems.push("/permissions/containers/existing/deposit must be false");

  if (problems.length)
    throw new ConfigError("Configuration is not usable", problems);
  return config;
}

export function parseConfigText(
  text: string,
  filename: string,
  baseDirectory: string,
): PersonConfig {
  let parsed: unknown;
  try {
    parsed = filename.endsWith(".json") ? JSON.parse(text) : parseToml(text);
  } catch (error) {
    throw new ConfigError(
      `${filename} could not be parsed: ${(error as Error).message}`,
    );
  }
  return validateConfig(parsed, baseDirectory);
}

export function loadConfig(filename: string): PersonConfig {
  const absolute = path.resolve(filename);
  let text: string;
  try {
    text = readFileSync(absolute, "utf8");
  } catch (error) {
    throw new ConfigError(
      `Cannot read configuration ${absolute}: ${(error as Error).message}`,
    );
  }
  return parseConfigText(text, absolute, path.dirname(absolute));
}
