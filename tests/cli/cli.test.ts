import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { UsageError, parseArguments } from "../../apps/cli/src/bin/person.ts";
import {
  compareCommand,
  inspectCommand,
  observeCommand,
  skillTestCommand,
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

test("observe and compare are parsed like the other commands", () => {
  const observe = parseArguments([
    "observe",
    "--config",
    "c.toml",
    "--out",
    "o.json",
  ]);
  assert.equal(observe.command, "observe");
  assert.equal(observe.outputFile, "o.json");
  const compare = parseArguments(["compare", "a.json", "b.json"]);
  assert.equal(compare.command, "compare");
  assert.deepEqual(compare.positional, ["a.json", "b.json"]);
  assert.throws(() => parseArguments(["observe"]), /needs --config/);
  assert.throws(
    () => parseArguments(["compare", "a.json"]),
    /reference observation/,
  );
  assert.throws(
    () => parseArguments(["observe", "--config", "c", "--out"]),
    /--out needs/,
  );
});

test("observe takes one observation and validates it", async () => {
  const result = await observeCommand({
    configPath: path.join(REPOSITORY, "examples/fixture.toml"),
    json: true,
  });
  assert.equal(result.code, 0);
  const body = JSON.parse(result.output) as {
    valid: boolean;
    diagnostics: string[];
    observation: {
      type: string;
      vitals: { alive: boolean };
      environment: { biome: string };
    };
  };
  assert.equal(body.valid, true, body.diagnostics.join("; "));
  assert.equal(body.observation.type, "Observation");
  assert.equal(body.observation.vitals.alive, true);
  assert.notEqual(
    body.observation.environment.biome,
    "unknown",
    "biome must come from the world, not a default",
  );
});

test("observe writes the capture where it is asked to", async () => {
  const target = path.join(
    mkdtempSync(path.join(tmpdir(), "person-observe-")),
    "capture.json",
  );
  const result = await observeCommand({
    configPath: path.join(REPOSITORY, "examples/fixture.toml"),
    json: false,
    outputFile: target,
  });
  assert.equal(result.code, 0);
  assert.match(result.output, /valid against the protocol schema/);
  const written = JSON.parse(readFileSync(target, "utf8")) as { type: string };
  assert.equal(written.type, "Observation");
});

test("compare reports structural gaps and suspicious defaults", () => {
  const directory = mkdtempSync(path.join(tmpdir(), "person-compare-"));
  const reference = JSON.parse(
    readFileSync(
      path.join(REPOSITORY, "fixtures/protocol-corpus/valid/observation.json"),
      "utf8",
    ),
  ) as Record<string, unknown>;
  const actual = JSON.parse(JSON.stringify(reference)) as Record<
    string,
    unknown
  >;
  // A real capture that is missing a block cognition depends on, and full of
  // fields nothing ever wrote.
  delete actual["affordances"];
  (actual["environment"] as Record<string, unknown>)["biome"] = "unknown";
  (actual["nearby"] as Record<string, unknown>)["resources"] = [];

  const referencePath = path.join(directory, "reference.json");
  const actualPath = path.join(directory, "actual.json");
  writeFileSync(referencePath, JSON.stringify(reference));
  writeFileSync(actualPath, JSON.stringify(actual));

  const result = compareCommand(referencePath, actualPath, true);
  assert.equal(result.code, 1, "a structural gap is a failure");
  const body = JSON.parse(result.output) as {
    structural: number;
    suspicious: number;
    findings: { path: string; kind: string; note: string }[];
  };
  assert.equal(body.structural, 1);
  assert.ok(body.suspicious >= 2);
  assert.ok(body.findings.some((finding) => finding.path === "/affordances"));
  assert.ok(
    body.findings.some(
      (finding) =>
        finding.kind === "suspicious" && finding.path === "/environment/biome",
    ),
  );
});

test("comparing an observation with itself finds nothing structural", () => {
  const capture = path.join(
    REPOSITORY,
    "fixtures/protocol-corpus/valid/observation.json",
  );
  const result = compareCommand(capture, capture, true);
  const body = JSON.parse(result.output) as { structural: number };
  assert.equal(body.structural, 0);
  assert.equal(result.code, 0);
});

test("skill-test is parsed like the other commands, and demands a skill", () => {
  const parsed = parseArguments([
    "skill-test",
    "--config",
    "examples/fixture.toml",
    "--skill",
    "wait_safely",
    "--port",
    "51234",
  ]);
  assert.equal(parsed.command, "skill-test");
  assert.equal(parsed.skillId, "wait_safely");
  assert.equal(parsed.operatorSetup, false);
  assert.equal(parsed.connection.port, 51234);

  const setup = parseArguments([
    "skill-test",
    "--config",
    "c.toml",
    "--skill",
    "return_home",
    "--operator-setup",
  ]);
  assert.equal(setup.operatorSetup, true);

  assert.throws(
    () => parseArguments(["skill-test", "--config", "c.toml"]),
    /needs --skill/,
  );
  assert.throws(
    () => parseArguments(["skill-test", "--skill", "wait_safely"]),
    /needs --config/,
  );
  assert.throws(
    () => parseArguments(["skill-test", "--config", "c", "--skill"]),
    /--skill needs/,
  );
  assert.throws(
    () => parseArguments(["observe", "--config", "c.toml", "--operator-setup"]),
    /--operator-setup only applies/,
  );
  // There is no way to describe an action the library does not already have.
  for (const forbidden of [
    "--command",
    "--chat",
    "--script",
    "--position",
    "--teleport",
    "--parameters",
  ])
    assert.throws(
      () =>
        parseArguments([
          "skill-test",
          "--config",
          "c.toml",
          "--skill",
          "wait_safely",
          forbidden,
          "anything",
        ]),
      /Unknown option/,
      `${forbidden} must not be accepted`,
    );
});

test("skill-test refuses a skill the library does not contain", async () => {
  const result = await skillTestCommand({
    configPath: path.join(REPOSITORY, "examples/fixture.toml"),
    skillId: "teleport_home",
    json: false,
  });
  assert.equal(result.code, 2);
  assert.match(result.output, /not a registered skill/);
  assert.match(result.output, /wait_safely/, "it lists what is available");
});
