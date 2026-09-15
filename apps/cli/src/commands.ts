import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import {
  ConfigError,
  LegacyCheckpointError,
  assertNotLegacyCheckpoint,
  describeConnection,
  isLegacyConfig,
  loadConfig,
  migrateConfig,
  withConnectionOverride,
  type ConnectionOverride,
  type PersonConfig,
} from "#config";
import {
  PersonRuntime,
  readStatus,
  renderStatus,
  statusPath,
  summariseEpisode,
} from "#node-runtime";
import { skillRegistry } from "#skills";
import { PROTOCOL_VERSION } from "#protocol";
import { EvidenceInspector } from "./inspect.ts";
import { createEmbodiment } from "./embodiment.ts";
import {
  captureObservation,
  compareObservations,
  renderFindings,
  renderObservation,
  resolveBase,
} from "./observe.ts";

export interface CommandResult {
  code: number;
  output: string;
}

export interface RunOptions {
  configPath: string;
  learningMode?: "off" | "shadow" | "supervised";
  json: boolean;
  episodeId?: string;
  connection?: ConnectionOverride;
  operatorIntervention?: { reason?: string };
}

function withLearningMode(
  config: PersonConfig,
  mode?: RunOptions["learningMode"],
): PersonConfig {
  if (!mode || mode === config.learning.mode) return config;
  return { ...config, learning: { ...config.learning, mode } };
}

export async function runCommand(options: RunOptions): Promise<CommandResult> {
  const base = loadConfig(options.configPath);
  // The LAN port is runtime information, not configuration: Minecraft picks a
  // new one every time a world is opened. The override applies to this
  // invocation and is never written back.
  const config = withConnectionOverride(
    withLearningMode(base, options.learningMode),
    options.connection ?? {},
  );
  const embodiment = await createEmbodiment(
    config,
    path.dirname(path.resolve(options.configPath)),
  );
  if (!options.json && config.runtime.embodiment === "minecraft")
    process.stderr.write(
      `person: connecting to ${describeConnection(config, options.connection ?? {})}\n`,
    );
  const runtime = new PersonRuntime({
    config,
    embodiment,
    cwd: process.cwd(),
    ...(options.episodeId ? { episodeId: options.episodeId } : {}),
    ...(options.operatorIntervention
      ? { operatorIntervention: options.operatorIntervention }
      : {}),
    onDiagnostic: (kind, detail) => {
      if (!options.json)
        process.stderr.write(`person: ${kind} ${JSON.stringify(detail)}\n`);
    },
  });
  const report = await runtime.run();
  return {
    code: report.outcome === "completed" ? 0 : 1,
    output: options.json
      ? `${JSON.stringify(report, null, 2)}\n`
      : `${summariseEpisode(report)}\n`,
  };
}

/**
 * Connects, takes one observation, and stops.
 *
 * The smallest thing that can be done against a live server, and therefore the
 * right first thing to do against one.
 */
export interface ObserveOptions {
  configPath: string;
  json: boolean;
  outputFile?: string;
  connection?: ConnectionOverride;
  operatorIntervention?: { reason?: string };
}

/**
 * Connects, takes one observation, and stops.
 *
 * The smallest thing that can be done against a live server, and therefore the
 * right first thing to do against one. It runs no skill, writes no learning
 * update, and disconnects before returning.
 */
export async function observeCommand(
  options: ObserveOptions,
): Promise<CommandResult> {
  const config = withConnectionOverride(
    loadConfig(options.configPath),
    options.connection ?? {},
  );
  const identity = describeConnection(config, options.connection ?? {});
  if (!options.json && config.runtime.embodiment === "minecraft")
    process.stderr.write(`person: connecting to ${identity}\n`);

  let captured;
  try {
    captured = await captureObservation(
      config,
      resolveBase(options.configPath),
      {
        operatorIntervention: options.operatorIntervention,
      },
    );
  } catch (error) {
    // The first live connection is the least diagnosable moment in the system.
    // Whatever the adapter worked out about the failure is reported verbatim
    // rather than collapsed into "failed to connect".
    const failure = error as {
      reason?: string;
      hint?: string | null;
      message?: string;
    };
    const reason = failure.reason ?? "unknown_error";
    if (options.json)
      return {
        code: 1,
        output: `${JSON.stringify(
          {
            connected: false,
            reason,
            message: failure.message ?? String(error),
            hint: failure.hint ?? null,
            target: identity,
          },
          null,
          2,
        )}\n`,
      };
    return {
      code: 1,
      output:
        `Could not observe ${identity}\n` +
        `  reason: ${reason}\n` +
        `  detail: ${failure.message ?? String(error)}\n` +
        (failure.hint ? `  try:    ${failure.hint}\n` : ""),
    };
  }

  if (options.outputFile)
    writeFileSync(
      path.resolve(options.outputFile),
      `${JSON.stringify(captured.observation, null, 2)}\n`,
      { mode: 0o600 },
    );
  if (options.json)
    return {
      code: captured.valid ? 0 : 1,
      output: `${JSON.stringify(
        {
          connected: true,
          valid: captured.valid,
          diagnostics: captured.diagnostics,
          observation: captured.observation,
        },
        null,
        2,
      )}\n`,
    };
  const header = captured.valid
    ? `Connected to ${identity}\nObservation is valid against the protocol schema.`
    : `Connected to ${identity}\nObservation FAILS the protocol schema:\n  ${captured.diagnostics.join("\n  ")}`;
  const written = options.outputFile
    ? `\nFull normalised observation written to ${path.resolve(options.outputFile)}`
    : "\nRe-run with --json or --out <file> for the full normalised observation.";
  return {
    code: captured.valid ? 0 : 1,
    output: `${header}\n${renderObservation(captured.observation)}${written}\n`,
  };
}

/**
 * Reports what Person is doing, from the outside.
 *
 * Read-only by construction: the runtime writes a status file and this reads
 * it. Nothing here connects to Minecraft, so watching Person can never change
 * what Person does, and the last known state survives the run that produced it.
 */
export function statusCommand(
  config: PersonConfig,
  json: boolean,
): CommandResult {
  const file = statusPath(
    config.runtime.outputDirectory,
    config.worldId,
    config.personId,
  );
  const status = readStatus(file);
  if (!status)
    return {
      code: 1,
      output: json
        ? `${JSON.stringify({ found: false, file }, null, 2)}\n`
        : `No status recorded yet at ${file}\nRun person observe or person run first.\n`,
    };
  return {
    code: 0,
    output: json
      ? `${JSON.stringify(status, null, 2)}\n`
      : `${renderStatus(status)}\n`,
  };
}

/** Reprints the status whenever the runtime writes a new one. */
export async function followStatus(
  config: PersonConfig,
  json: boolean,
  intervalMs: number,
  write: (text: string) => void,
  shouldContinue: () => boolean,
): Promise<number> {
  const file = statusPath(
    config.runtime.outputDirectory,
    config.worldId,
    config.personId,
  );
  let last = "";
  while (shouldContinue()) {
    const status = readStatus(file);
    const rendered = status
      ? json
        ? `${JSON.stringify(status)}\n`
        : `${renderStatus(status)}\n`
      : `waiting for ${file}\n`;
    if (rendered !== last) {
      write(rendered);
      last = rendered;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return 0;
}

/**
 * Compares a reference observation with one taken somewhere else.
 *
 * Two different worlds differ in their contents; that is not news. What this
 * looks for is a field the real body cannot populate, or a value that is
 * really a default nothing ever wrote.
 */
export function compareCommand(
  referencePath: string,
  actualPath: string,
  json: boolean,
): CommandResult {
  const reference: unknown = JSON.parse(
    readFileSync(path.resolve(referencePath), "utf8"),
  );
  const actual: unknown = JSON.parse(
    readFileSync(path.resolve(actualPath), "utf8"),
  );
  const result = compareObservations(reference, actual);
  return {
    code: result.structural > 0 ? 1 : 0,
    output: json
      ? `${JSON.stringify(result, null, 2)}\n`
      : `${renderFindings(result)}\n`,
  };
}

export function validateCommand(
  configPath: string,
  migrate: boolean,
): CommandResult {
  const absolute = path.resolve(configPath);
  let document: unknown;
  const text = readFileSync(absolute, "utf8");
  if (absolute.endsWith(".json")) {
    document = JSON.parse(text);
    try {
      assertNotLegacyCheckpoint(document);
    } catch (error) {
      if (error instanceof LegacyCheckpointError)
        return { code: 2, output: `${error.message}\n` };
      throw error;
    }
  }

  if (document !== undefined && isLegacyConfig(document)) {
    if (!migrate)
      return {
        code: 2,
        output:
          "Legacy Shroud V1 configuration detected.\n\n" +
          "Re-run with --migrate to see the Person configuration it maps to.\n" +
          "Learning is never carried across a migration.\n",
      };
    const result = migrateConfig(document, path.dirname(absolute));
    const notes = result.notes.map((note) => `  - ${note}`).join("\n");
    return {
      code: 0,
      output:
        `Migrated from ${result.fromVersion} to configVersion 2.\n${notes}\n\n` +
        `${JSON.stringify(result.config, null, 2)}\n`,
    };
  }

  try {
    const config = loadConfig(absolute);
    const registry = skillRegistry();
    return {
      code: 0,
      output:
        `Configuration valid: ${absolute}\n` +
        `  person=${config.personId} world=${config.worldId}\n` +
        `  embodiment=${config.runtime.embodiment} trainingContext=${config.runtime.trainingContext}\n` +
        `  learning=${config.learning.mode} (learning never enables itself)\n` +
        `  protocol=${PROTOCOL_VERSION} skills=${registry.ids.length} libraryRevision=${registry.revision}\n` +
        `  existing containers: withdraw=${config.permissions.containers.existing.withdraw} deposit=${config.permissions.containers.existing.deposit}\n` +
        `  protected areas: ${config.world.protectedAreas.length} (enforcement ${config.permissions.protectedAreas.enforcement})\n`,
    };
  } catch (error) {
    if (error instanceof ConfigError)
      return { code: 2, output: `${error.message}\n` };
    throw error;
  }
}

export function inspectCommand(
  what: string,
  configPath: string | undefined,
  json: boolean,
): CommandResult {
  if (
    what !== "evidence" &&
    what !== "skills" &&
    what !== "config" &&
    what !== "predictions"
  )
    return {
      code: 2,
      output: `Unknown inspect target ${what}. Try: evidence, skills, config, predictions.\n`,
    };

  if (what === "skills") {
    const registry = skillRegistry();
    if (json)
      return {
        code: 0,
        output: `${JSON.stringify(
          {
            revision: registry.revision,
            skills: registry.ids.map((id) => registry.get(id)),
          },
          null,
          2,
        )}\n`,
      };
    const lines = registry.ids.map((id) => {
      const spec = registry.get(id);
      return `  ${spec.id} v${spec.version} [${spec.category}] risk=${spec.risk} ${spec.summary}`;
    });
    return {
      code: 0,
      output: `Skill library ${registry.revision}\n${lines.join("\n")}\n`,
    };
  }

  if (!configPath)
    return { code: 2, output: "--config is required for this inspection.\n" };
  const config = loadConfig(configPath);
  if (what === "config")
    return { code: 0, output: `${JSON.stringify(config, null, 2)}\n` };

  const inspector = new EvidenceInspector(config.learning.evidenceDirectory);
  const summary = inspector.summarise();
  if (what === "predictions")
    return {
      code: 0,
      output: json
        ? `${JSON.stringify(summary.predictionError, null, 2)}\n`
        : `Prediction error in ${summary.directory}\n  recorded=${summary.predictionError.recorded} ${Object.entries(
            summary.predictionError.severities,
          )
            .map(([severity, count]) => `${severity}=${count}`)
            .join(" ")}\n${summary.predictionError.worst
            .map(
              (entry) =>
                `  ${entry.severity} ${entry.skill}: ${entry.facts
                  .map(
                    (fact) =>
                      `${fact.fact} predicted ${fact.predicted} observed ${fact.observed}`,
                  )
                  .join("; ")}`,
            )
            .join("\n")}\n`,
    };
  return {
    code: 0,
    output: json
      ? `${JSON.stringify(summary, null, 2)}\n`
      : `${inspector.render(summary)}\n`,
  };
}
