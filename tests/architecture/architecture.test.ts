import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { loadConfig } from "#config";
import { SCHEMA_DIRECTORY, protocolValidator } from "#protocol";
import { skillRegistry } from "#skills";
import { implementedSkillIds } from "#node-runtime";
import { REPOSITORY } from "../support/harness.ts";

const read = (relative: string): string =>
  readFileSync(path.join(REPOSITORY, relative), "utf8");

function sourceFiles(root: string, extension: string): string[] {
  const absolute = path.join(REPOSITORY, root);
  const files: string[] = [];
  const walk = (directory: string): void => {
    for (const entry of readdirSync(directory)) {
      if (
        entry === "node_modules" ||
        entry === "__pycache__" ||
        entry.startsWith(".")
      )
        continue;
      const full = path.join(directory, entry);
      if (statSync(full).isDirectory()) walk(full);
      else if (full.endsWith(extension)) files.push(full);
    }
  };
  walk(absolute);
  return files;
}

test("SkillInvocation has no general-purpose command channel", () => {
  const schema = JSON.parse(
    readFileSync(
      path.join(SCHEMA_DIRECTORY, "skill-invocation.schema.json"),
      "utf8",
    ),
  ) as Record<string, unknown>;
  assert.equal(
    schema["unevaluatedProperties"],
    false,
    "unknown fields must be refused",
  );
  const properties = Object.keys(
    schema["properties"] as Record<string, unknown>,
  );
  for (const forbidden of [
    "command",
    "chat",
    "script",
    "code",
    "eval",
    "raw",
    "packet",
  ])
    assert.ok(
      !properties.includes(forbidden),
      `SkillInvocation must not expose ${forbidden}`,
    );

  const common = JSON.parse(
    readFileSync(path.join(SCHEMA_DIRECTORY, "common.schema.json"), "utf8"),
  ) as {
    $defs: Record<string, { additionalProperties?: { type?: string[] } }>;
  };
  const parameters = common.$defs["skillParameters"];
  assert.deepEqual(parameters?.additionalProperties?.type, [
    "integer",
    "number",
    "string",
    "boolean",
  ]);
});

test("every SkillOutcome names the skill that actually executed", () => {
  const schema = JSON.parse(
    readFileSync(
      path.join(SCHEMA_DIRECTORY, "skill-outcome.schema.json"),
      "utf8",
    ),
  ) as { required: string[] };
  for (const field of [
    "requestedSkill",
    "executedSkill",
    "requestedSkillStatus",
    "status",
  ])
    assert.ok(
      schema.required.includes(field),
      `SkillOutcome must require ${field}`,
    );
});

test("cognition may only send decisions; the runtime owns every verdict", () => {
  const validator = protocolValidator();
  const cognitionTypes = [
    "CognitionReady",
    "GoalDecision",
    "PolicyDecision",
    "SkillInvocation",
  ];
  const runtimeTypes = [
    "SessionHello",
    "Observation",
    "ValidationDecision",
    "SkillStarted",
    "SkillOutcome",
    "EmergencyEvent",
    "EpisodeEvent",
  ];
  assert.deepEqual(
    [...validator.messageTypes].sort(),
    [...runtimeTypes, ...cognitionTypes].sort(),
  );
  const channel = read("apps/node-runtime/src/ipc/cognition-channel.ts");
  assert.match(
    channel,
    /COGNITION_MESSAGE_TYPES as readonly string\[\]\)\.includes\(message\.type\)/,
    "the channel must drop anything cognition is not allowed to say",
  );
});

test("no proposal reaches an executor without passing the validator", () => {
  const runtime = read("apps/node-runtime/src/runtime/person-runtime.ts");
  assert.ok(
    runtime.includes("this.validator.validate("),
    "the runtime must validate proposals",
  );
  const executions = runtime.match(/this\.runner\.run\(/g) ?? [];
  assert.equal(
    executions.length,
    2,
    "exactly two execution sites: the validated proposal and the emergency replacement",
  );
  const validationIndex = runtime.indexOf("this.validator.validate(");
  assert.ok(
    validationIndex < runtime.indexOf("this.runner.run("),
    "validation must happen before execution",
  );
});

test("the skill library and its implementations agree exactly", () => {
  assert.deepEqual(implementedSkillIds(), skillRegistry().ids);
});

test("no skill implementation is a placeholder", () => {
  for (const file of sourceFiles("apps/node-runtime/src/skills/impl", ".ts")) {
    const source = readFileSync(file, "utf8");
    assert.ok(
      !/not implemented/i.test(source),
      `${path.basename(file)} must not contain a not-implemented marker`,
    );
    assert.ok(
      !/TODO[: ]/.test(source),
      `${path.basename(file)} must not contain a required-scope TODO`,
    );
  }
});

test("the cognition process is spawned with pipes and nothing else", () => {
  const channel = read("apps/node-runtime/src/ipc/cognition-channel.ts");
  assert.match(channel, /stdio: \["pipe", "pipe", "pipe"\]/);
  assert.ok(
    !/net\.|createServer|listen\(/.test(channel),
    "the cognition transport must stay local stdio",
  );
});

test("learning is off in every shipped configuration", () => {
  for (const file of readdirSync(path.join(REPOSITORY, "examples"))) {
    if (!file.endsWith(".toml")) continue;
    const config = loadConfig(path.join(REPOSITORY, "examples", file));
    assert.equal(
      config.learning.mode,
      "off",
      `${file} must ship with learning off`,
    );
  }
});

test("the runtime never generates or evaluates code", () => {
  const roots = [
    "apps/node-runtime/src",
    "apps/cli/src",
    "adapters/minecraft/src",
    "fixtures/src",
  ];
  for (const root of roots)
    for (const file of sourceFiles(root, ".ts")) {
      const source = readFileSync(file, "utf8");
      assert.ok(!/\beval\(/.test(source), `${file} must not call eval`);
      assert.ok(
        !/new Function\(/.test(source),
        `${file} must not build functions at runtime`,
      );
      assert.ok(
        !/child_process.*exec\b/.test(source),
        `${file} must not run shell commands`,
      );
    }
});

test("the Minecraft client is only reachable from the adapter", () => {
  const roots = [
    "apps/node-runtime/src",
    "apps/cli/src",
    "fixtures/src",
    "packages",
  ];
  for (const root of roots)
    for (const file of sourceFiles(root, ".ts")) {
      const source = readFileSync(file, "utf8");
      const importsMineflayer = /from "mineflayer/.test(source);
      assert.ok(
        !importsMineflayer,
        `${path.relative(REPOSITORY, file)} must not import Mineflayer; only the adapter may`,
      );
    }
  assert.match(
    read("adapters/minecraft/src/embodiment.ts"),
    /from "mineflayer"/,
  );
});
