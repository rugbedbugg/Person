#!/usr/bin/env node
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  loadConfig,
  parseHost,
  parsePort,
  type ConnectionOverride,
} from "#config";
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
    | "help";
  configPath?: string;
  target?: string;
  learningMode?: "off" | "shadow" | "supervised";
  skillId?: string;
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
}

export class UsageError extends Error {}

export function parseArguments(argv: string[]): ParsedCommand {
  const parsed: ParsedCommand = {
    command: "help",
    json: false,
    migrate: false,
    operatorSetup: false,
    connection: {},
    follow: false,
    intervalMs: 1000,
    positional: [],
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
    } else if (argument === "--operator-setup") parsed.operatorSetup = true;
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
      const config = loadConfig(parsed.configPath as string);
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
