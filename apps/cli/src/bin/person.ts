#!/usr/bin/env node
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  compareCommand,
  followStatus,
  inspectCommand,
  observeCommand,
  runCommand,
  skillTestCommand,
  statusCommand,
  validateCommand,
} from "../commands.ts";
import { runExperiment, summariseExperiment } from "../experiment.ts";
import {
  preflight,
  renderPreflight,
  writeWorldManifest,
} from "../preflight.ts";
import {
  loadMinecraftConfig,
  parseHost,
  parsePort,
  type ConnectionOverride,
} from "#minecraft";

const USAGE = `Person: a persistent artificial inhabitant for Minecraft.

Usage:
  person run      --config <file> [--port <n>] [--host <h>] [--json] [--episode-id <id>]
  person learn    --mode off|shadow|supervised --config <file> [--port <n>] [--json]
  person observe  --config <file> [--port <n>] [--host <h>] [--json] [--out <file>]
  person skill-test --config <file> --skill <id> [--port <n>] [--host <h>] [--json]
                    [--operator-setup]
  person status   --config <file> [--json] [--follow [--interval <ms>]]
  person validate <file> [--migrate]
  person inspect  evidence|skills|config|predictions [--config <file>] [--json]
  person compare  <reference-observation.json> <actual-observation.json> [--json]
  person experiment --plan <plan.json> [--out <directory>] [--jobs <n>]
                    [--heldout] [--json]
  person preflight --config <file> --server-dir <dir> --backup <dir>
                   [--found] [--json]
  person world-manifest --server-dir <dir> --purpose <text>

Every command that connects also accepts:
  --operator-intervention[=reason]   mark this run as contaminated by a human

Notes:
  Minecraft assigns a new port every time a world is opened to LAN, so --port
  is runtime information rather than configuration. It overrides whatever the
  file says, for this invocation only, and is never written back.

  "observe" connects, takes one observation and stops. It is the smallest thing
  that can be done against a live Minecraft world, and the right first one.

  "skill-test" validates one skill that is already in the library against the
  same safety kernel and executor an autonomous run uses. It selects no goal,
  runs no planner and changes nothing the learner knows. --skill accepts a
  registered skill name and nothing else. --operator-setup pauses after
  connecting so you can position Person yourself before the measured run.

  "status" reads what the runtime last wrote. It never connects, so watching
  Person cannot change what Person does.
  "compare" diffs a captured observation against a reference and flags fields
  that look like defaults nothing ever filled in.

  "experiment" runs a research plan in the fixture world: every condition on
  every world seed, each run independent, measured afterwards from its report
  and journal (ADR 0013). It never connects to Minecraft. Results go under
  --out (default runs/experiments). --jobs runs that many at once, which
  changes nothing measured. A held-out plan runs only with --heldout: it
  evaluates a finished model once and is not for designing one.

  "preflight" checks, before founding (--found) or embodying a canonical or
  validation Person, that the revision, configuration, continuity root,
  evidence path, backup destination, server and world are exactly what they
  must be (ADR 0018). It is read-only, connects to nothing, and fails closed.
  "world-manifest" records a newly created world's identity, once.

  Learning is off unless you ask for it. "person run" uses the mode in the
  configuration file, which examples ship as "off"; "person learn" is the only
  way to put a learner in control, and even then the Node safety kernel keeps
  the final say over every physical action.

Compatibility aliases:
  shroud <args>            same as person <args>
  shroud-train <args>      same as person learn <args>
`;

export interface ParsedCommand {
  command:
    | "run"
    | "learn"
    | "validate"
    | "inspect"
    | "observe"
    | "status"
    | "compare"
    | "skill-test"
    | "experiment"
    | "preflight"
    | "world-manifest"
    | "help";
  configPath?: string;
  target?: string;
  learningMode?: "off" | "shadow" | "supervised";
  skillId?: string;
  planPath?: string;
  jobs: number;
  heldout: boolean;
  operatorSetup: boolean;
  json: boolean;
  migrate: boolean;
  episodeId?: string;
  outputFile?: string;
  connection: ConnectionOverride;
  operatorIntervention?: { reason?: string };
  follow: boolean;
  intervalMs: number;
  positional: string[];
  serverDirectory?: string;
  backupDirectory?: string;
  purpose?: string;
  found: boolean;
}

export class UsageError extends Error {}

export function parseArguments(argv: string[]): ParsedCommand {
  const parsed: ParsedCommand = {
    command: "help",
    json: false,
    migrate: false,
    operatorSetup: false,
    jobs: 1,
    heldout: false,
    connection: {},
    follow: false,
    intervalMs: 1000,
    positional: [],
    found: false,
  };
  if (argv.length === 0 || argv[0] === "--help" || argv[0] === "-h")
    return parsed;
  const [command, ...rest] = argv;
  const COMMANDS = [
    "run",
    "learn",
    "validate",
    "inspect",
    "observe",
    "status",
    "compare",
    "skill-test",
    "experiment",
    "preflight",
    "world-manifest",
  ] as const;
  if ((COMMANDS as readonly string[]).includes(command as string))
    parsed.command = command as (typeof COMMANDS)[number];
  else throw new UsageError(`Unknown command ${command}`);

  const positional: string[] = [];
  for (let index = 0; index < rest.length; index++) {
    const argument = rest[index];
    if (argument === "--config") {
      const value = rest[++index];
      if (!value || value.startsWith("--"))
        throw new UsageError("--config needs a file path");
      if (parsed.configPath) throw new UsageError("--config was given twice");
      parsed.configPath = value;
    } else if (argument === "--mode") {
      const value = rest[++index];
      if (value !== "off" && value !== "shadow" && value !== "supervised")
        throw new UsageError("--mode must be off, shadow, or supervised");
      parsed.learningMode = value;
    } else if (argument === "--episode-id") {
      const value = rest[++index];
      if (!value || value.startsWith("--"))
        throw new UsageError("--episode-id needs a value");
      parsed.episodeId = value;
    } else if (argument === "--skill") {
      const value = rest[++index];
      if (!value || value.startsWith("--"))
        throw new UsageError("--skill needs the name of a registered skill");
      if (parsed.skillId) throw new UsageError("--skill was given twice");
      parsed.skillId = value;
    } else if (argument === "--plan") {
      const value = rest[++index];
      if (!value || value.startsWith("--"))
        throw new UsageError("--plan needs an experiment plan file");
      parsed.planPath = value;
    } else if (argument === "--jobs") {
      const value = Number(rest[++index]);
      if (!Number.isInteger(value) || value < 1 || value > 64)
        throw new UsageError("--jobs must be a whole number from 1 to 64");
      parsed.jobs = value;
    } else if (
      argument === "--server-dir" ||
      argument === "--backup" ||
      argument === "--purpose"
    ) {
      const value = rest[++index];
      if (!value || value.startsWith("--"))
        throw new UsageError(`${argument} needs a value`);
      if (argument === "--server-dir") parsed.serverDirectory = value;
      else if (argument === "--backup") parsed.backupDirectory = value;
      else parsed.purpose = value;
    } else if (argument === "--found") parsed.found = true;
    else if (argument === "--heldout") parsed.heldout = true;
    else if (argument === "--operator-setup") parsed.operatorSetup = true;
    else if (argument === "--out") {
      const value = rest[++index];
      if (!value || value.startsWith("--"))
        throw new UsageError("--out needs a file path");
      parsed.outputFile = value;
    } else if (argument === "--port") {
      const value = rest[++index];
      if (!value || value.startsWith("--"))
        throw new UsageError("--port needs the number Minecraft displayed");
      parsed.connection.port = parsePort(value);
    } else if (argument === "--host") {
      const value = rest[++index];
      if (!value || value.startsWith("--"))
        throw new UsageError("--host needs a host");
      parsed.connection.host = parseHost(value);
    } else if (argument === "--interval") {
      const value = Number(rest[++index]);
      if (!Number.isInteger(value) || value < 100 || value > 60000)
        throw new UsageError(
          "--interval must be between 100 and 60000 milliseconds",
        );
      parsed.intervalMs = value;
    } else if (argument === "--follow") parsed.follow = true;
    else if (argument === "--operator-intervention")
      parsed.operatorIntervention = {};
    else if (argument?.startsWith("--operator-intervention=")) {
      const reason = argument.slice("--operator-intervention=".length);
      if (!reason)
        throw new UsageError(
          "--operator-intervention= needs a reason after the =",
        );
      parsed.operatorIntervention = { reason };
    } else if (argument === "--json") parsed.json = true;
    else if (argument === "--migrate") parsed.migrate = true;
    else if (argument === "--help" || argument === "-h")
      return { ...parsed, command: "help" };
    else if (argument?.startsWith("--"))
      throw new UsageError(`Unknown option ${argument}`);
    else if (argument) positional.push(argument);
  }

  if (parsed.command === "validate") {
    parsed.configPath = positional[0] ?? parsed.configPath;
    if (!parsed.configPath)
      throw new UsageError("person validate needs a configuration file");
  }
  if (parsed.command === "inspect") {
    parsed.target = positional[0];
    if (!parsed.target)
      throw new UsageError(
        "person inspect needs a target (evidence, skills, config, predictions)",
      );
  }
  if (parsed.command === "skill-test") {
    if (!parsed.configPath)
      throw new UsageError("person skill-test needs --config <file>");
    if (!parsed.skillId)
      throw new UsageError(
        "person skill-test needs --skill <registered skill>",
      );
  }
  if (parsed.operatorSetup && parsed.command !== "skill-test")
    throw new UsageError("--operator-setup only applies to person skill-test");
  if (parsed.command === "experiment" && !parsed.planPath)
    throw new UsageError("person experiment needs --plan <file>");
  if (
    (parsed.planPath || parsed.heldout || parsed.jobs !== 1) &&
    parsed.command !== "experiment"
  )
    throw new UsageError(
      "--plan, --jobs and --heldout only apply to person experiment",
    );
  if (parsed.command === "observe" && !parsed.configPath)
    throw new UsageError("person observe needs --config <file>");
  if (parsed.command === "status" && !parsed.configPath)
    throw new UsageError("person status needs --config <file>");
  if (parsed.follow && parsed.command !== "status")
    throw new UsageError("--follow only applies to person status");
  if (parsed.command === "compare" && positional.length !== 2)
    throw new UsageError(
      "person compare needs a reference observation and an actual observation",
    );
  if (
    parsed.command === "preflight" &&
    (!parsed.configPath || !parsed.serverDirectory || !parsed.backupDirectory)
  )
    throw new UsageError(
      "person preflight needs --config <file>, --server-dir <dir> and --backup <dir>",
    );
  if (
    parsed.command === "world-manifest" &&
    (!parsed.serverDirectory || !parsed.purpose)
  )
    throw new UsageError(
      "person world-manifest needs --server-dir <dir> and --purpose <text>",
    );
  if (parsed.found && parsed.command !== "preflight")
    throw new UsageError("--found only applies to person preflight");
  parsed.positional = positional;
  if (
    (parsed.command === "run" || parsed.command === "learn") &&
    !parsed.configPath
  )
    throw new UsageError(`person ${parsed.command} needs --config <file>`);
  if (parsed.command === "learn" && !parsed.learningMode)
    throw new UsageError("person learn needs --mode off|shadow|supervised");
  return parsed;
}

export async function main(argv: string[]): Promise<number> {
  const invoked = path.basename(argv[1] ?? "person");
  const args =
    invoked === "shroud-train" ? ["learn", ...argv.slice(2)] : argv.slice(2);
  let parsed: ParsedCommand;
  try {
    parsed = parseArguments(args);
  } catch (error) {
    process.stderr.write(`person: ${(error as Error).message}\n\n${USAGE}`);
    return 2;
  }
  if (parsed.command === "help") {
    process.stdout.write(USAGE);
    return 0;
  }
  try {
    if (parsed.command === "validate") {
      const result = validateCommand(
        parsed.configPath as string,
        parsed.migrate,
      );
      process.stdout.write(result.output);
      return result.code;
    }
    if (parsed.command === "observe") {
      const result = await observeCommand({
        configPath: parsed.configPath as string,
        json: parsed.json,
        ...(parsed.outputFile ? { outputFile: parsed.outputFile } : {}),
        connection: parsed.connection,
        ...(parsed.operatorIntervention
          ? { operatorIntervention: parsed.operatorIntervention }
          : {}),
      });
      process.stdout.write(result.output);
      return result.code;
    }
    if (parsed.command === "experiment") {
      const results = await runExperiment({
        planFile: path.resolve(parsed.planPath as string),
        outputDirectory: path.resolve(
          parsed.outputFile ?? path.join("runs", "experiments"),
        ),
        repository: process.cwd(),
        jobs: parsed.jobs,
        allowHeldout: parsed.heldout,
        onRun: (run) => {
          if (!parsed.json)
            process.stderr.write(
              `person: ${run.metadata.condition} ${run.metadata.horizon} seed ${run.metadata.seed}: ${run.metrics["decisions"]} decisions, ${run.metrics["experienced_ticks"]} ticks\n`,
            );
        },
      });
      process.stdout.write(
        parsed.json
          ? `${JSON.stringify(results, null, 2)}\n`
          : summariseExperiment(results),
      );
      const leaked = results.comparisons.some(
        (comparison) =>
          comparison.purpose.startsWith("negative control") &&
          comparison.divergentSeeds > 0,
      );
      return leaked ? 1 : 0;
    }
    if (parsed.command === "preflight") {
      const result = await preflight({
        configPath: parsed.configPath as string,
        operation: parsed.found ? "found" : "embody",
        serverDirectory: parsed.serverDirectory as string,
        backupDirectory: parsed.backupDirectory as string,
        repository: process.cwd(),
      });
      process.stdout.write(
        parsed.json
          ? `${JSON.stringify(result, null, 2)}\n`
          : renderPreflight(result),
      );
      return result.ok ? 0 : 1;
    }
    if (parsed.command === "world-manifest") {
      const manifest = writeWorldManifest(
        parsed.serverDirectory as string,
        parsed.purpose as string,
      );
      process.stdout.write(`${JSON.stringify(manifest, null, 2)}\n`);
      return 0;
    }
    if (parsed.command === "skill-test") {
      const result = await skillTestCommand({
        configPath: parsed.configPath as string,
        skillId: parsed.skillId as string,
        json: parsed.json,
        operatorSetup: parsed.operatorSetup,
        connection: parsed.connection,
        ...(parsed.operatorIntervention
          ? { operatorIntervention: parsed.operatorIntervention }
          : {}),
      });
      process.stdout.write(result.output);
      return result.code;
    }
    if (parsed.command === "status") {
      const config = loadMinecraftConfig(parsed.configPath as string);
      if (!parsed.follow) {
        const result = statusCommand(config, parsed.json);
        process.stdout.write(result.output);
        return result.code;
      }
      let running = true;
      const stop = (): void => {
        running = false;
      };
      process.once("SIGINT", stop);
      process.once("SIGTERM", stop);
      return followStatus(
        config,
        parsed.json,
        parsed.intervalMs,
        (text) => process.stdout.write(text),
        () => running,
      );
    }
    if (parsed.command === "compare") {
      const result = compareCommand(
        parsed.positional[0] as string,
        parsed.positional[1] as string,
        parsed.json,
      );
      process.stdout.write(result.output);
      return result.code;
    }
    if (parsed.command === "inspect") {
      const result = inspectCommand(
        parsed.target as string,
        parsed.configPath,
        parsed.json,
      );
      process.stdout.write(result.output);
      return result.code;
    }
    const result = await runCommand({
      configPath: parsed.configPath as string,
      ...(parsed.learningMode ? { learningMode: parsed.learningMode } : {}),
      json: parsed.json,
      ...(parsed.episodeId ? { episodeId: parsed.episodeId } : {}),
      connection: parsed.connection,
      ...(parsed.operatorIntervention
        ? { operatorIntervention: parsed.operatorIntervention }
        : {}),
    });
    process.stdout.write(result.output);
    return result.code;
  } catch (error) {
    process.stderr.write(`person: ${(error as Error).message}\n`);
    return 1;
  }
}

const entry = process.argv[1];
if (entry && fileURLToPath(import.meta.url) === path.resolve(entry)) {
  main(process.argv).then((code) => {
    process.exitCode = code;
  });
}
