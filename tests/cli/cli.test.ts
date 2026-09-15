import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { UsageError, parseArguments } from "../../apps/cli/src/bin/person.ts";
import {
  inspectCommand,
  validateCommand,
} from "../../apps/cli/src/commands.ts";
import { REPOSITORY } from "../support/harness.ts";

test("the command line is parsed strictly", () => {
  assert.equal(parseArguments([]).command, "help");
  assert.equal(parseArguments(["--help"]).command, "help");
  const run = parseArguments(["run", "--config", "examples/fixture.toml"]);
  assert.equal(run.command, "run");
  assert.equal(run.configPath, "examples/fixture.toml");
  const learn = parseArguments([
    "learn",
    "--mode",
    "shadow",
    "--config",
    "c.toml",
  ]);
  assert.equal(learn.learningMode, "shadow");
  assert.throws(() => parseArguments(["fly"]), UsageError);
  assert.throws(() => parseArguments(["run"]), /needs --config/);
  assert.throws(
    () => parseArguments(["learn", "--config", "c.toml"]),
    /needs --mode/,
  );
  assert.throws(
    () => parseArguments(["learn", "--mode", "always", "--config", "c"]),
    /--mode must be/,
  );
  assert.throws(
    () => parseArguments(["run", "--config", "a", "--config", "b"]),
    /twice/,
  );
  assert.throws(() => parseArguments(["inspect"]), /needs a target/);
});

test("validate reports a usable configuration", () => {
  const result = validateCommand(
    path.join(REPOSITORY, "examples/fixture.toml"),
    false,
  );
  assert.equal(result.code, 0);
  assert.match(result.output, /Configuration valid/);
  assert.match(result.output, /learning=off/);
  assert.match(
    result.output,
    /existing containers: withdraw=true deposit=false/,
  );
});

test("validate explains what is wrong with a broken configuration", () => {
  const result = validateCommand(
    path.join(REPOSITORY, "examples/legacy-q-checkpoint.json"),
    false,
  );
  assert.equal(result.code, 2);
  assert.match(result.output, /Legacy Shroud V1 learning checkpoint detected/);
  assert.match(result.output, /has not been modified/);
  assert.match(result.output, /demonstration mechanism/);
});

test("a legacy configuration must be migrated deliberately", () => {
  const legacy = path.join(REPOSITORY, "examples/legacy-shroud-config.json");
  const refused = validateCommand(legacy, false);
  assert.equal(refused.code, 2);
  assert.match(refused.output, /Legacy Shroud V1 configuration detected/);
  assert.match(refused.output, /--migrate/);

  const migrated = validateCommand(legacy, true);
  assert.equal(migrated.code, 0);
  assert.match(migrated.output, /Migrated from shroud-v1/);
  assert.match(
    migrated.output,
    /Learning is never carried across|learningMode .* was not carried over/,
  );
  const config = JSON.parse(
    migrated.output.slice(migrated.output.indexOf("{")),
  ) as {
    configVersion: number;
    learning: { mode: string };
    permissions: { containers: { existing: { deposit: boolean } } };
    runtime: { trainingContext: string };
  };
  assert.equal(config.configVersion, 2);
  assert.equal(config.learning.mode, "off");
  assert.equal(config.permissions.containers.existing.deposit, false);
  assert.equal(config.runtime.trainingContext, "minecraft_peaceful");
});

test("inspect skills lists the whole library with its revision", () => {
  const result = inspectCommand("skills", undefined, false);
  assert.equal(result.code, 0);
  assert.match(result.output, /Skill library [0-9a-f]{16}/);
  for (const skill of [
    "flee",
    "gather_wood",
    "cook_food",
    "deposit_owned_storage",
  ])
    assert.match(result.output, new RegExp(`\\b${skill}\\b`));
});

test("inspect evidence is honest about an empty store", () => {
  const result = inspectCommand(
    "evidence",
    path.join(REPOSITORY, "examples/fixture.toml"),
    true,
  );
  assert.equal(result.code, 0);
  const summary = JSON.parse(result.output) as {
    exists: boolean;
    events: number;
  };
  assert.equal(typeof summary.exists, "boolean");
  if (!summary.exists) assert.equal(summary.events, 0);
});

test("unknown inspection targets are refused", () => {
  const result = inspectCommand("thoughts", undefined, false);
  assert.equal(result.code, 2);
  assert.match(result.output, /Unknown inspect target/);
});
