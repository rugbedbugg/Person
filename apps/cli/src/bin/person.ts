#!/usr/bin/env node
import path from "node:path";
import { fileURLToPath } from "node:url";
import { inspectCommand, runCommand, validateCommand } from "../commands.ts";

const USAGE = `Person: a persistent artificial inhabitant for Minecraft.

Usage:
  person run      --config <file> [--json] [--episode-id <id>]
  person learn    --mode off|shadow|supervised --config <file> [--json]
  person validate <file> [--migrate]
  person inspect  evidence|skills|config [--config <file>] [--json]

Notes:
  Learning is off unless you ask for it. "person run" uses the mode in the
  configuration file, which examples ship as "off"; "person learn" is the only
  way to put a learner in control, and even then the Node safety kernel keeps
  the final say over every physical action.

Compatibility aliases:
  shroud <args>            same as person <args>
  shroud-train <args>      same as person learn <args>
`;

export interface ParsedCommand {
  command: "run" | "learn" | "validate" | "inspect" | "help";
  configPath?: string;
  target?: string;
  learningMode?: "off" | "shadow" | "supervised";
  json: boolean;
  migrate: boolean;
  episodeId?: string;
}

export class UsageError extends Error {}

export function parseArguments(argv: string[]): ParsedCommand {
  const parsed: ParsedCommand = {
    command: "help",
    json: false,
    migrate: false,
  };
  if (argv.length === 0 || argv[0] === "--help" || argv[0] === "-h")
    return parsed;
  const [command, ...rest] = argv;
  if (
    command === "run" ||
    command === "learn" ||
    command === "validate" ||
    command === "inspect"
  )
    parsed.command = command;
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
        "person inspect needs a target (evidence, skills, config)",
      );
  }
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
