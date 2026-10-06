/**
 * The environment boundary, TypeScript side (ADR 0025).
 *
 * Person's core packages (protocol, configuration, skill infrastructure) are
 * environment-neutral: they describe an observation envelope, a configuration
 * core and a skill contract, and every Minecraft word lives in the Minecraft
 * profile under `environments/minecraft`. The Python side of the same rule is
 * `tests/python/test_epistemic_architecture.py`.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { SCHEMA_DIRECTORY, environmentManifest } from "#protocol";
import { REPOSITORY } from "../support/harness.ts";

const CORE_TS = [
  "packages/protocol/ts",
  "packages/config/ts",
  "packages/skills/ts",
];

/** Minecraft ontology no core source may name outside a comment. */
const MINECRAFT_WORDS =
  /\b(minecraft|mineflayer|biome|hostiles?|villagers?|furnace|chest|peaceful|zombie|creeper|nether|overworld)\b/i;

function coreSources(): string[] {
  const files: string[] = [];
  for (const root of CORE_TS) {
    const walk = (directory: string): void => {
      for (const entry of readdirSync(directory)) {
        const full = path.join(directory, entry);
        if (statSync(full).isDirectory()) walk(full);
        else if (full.endsWith(".ts") && !full.endsWith(".test.ts"))
          files.push(full);
      }
    };
    walk(path.join(REPOSITORY, root));
  }
  return files;
}

/** The code of a source file, without its comments. */
const code = (source: string): string =>
  source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

// Discovering installed environments is data (their manifests), not code:
// `#protocol` reads `environments/*/environment.json` and imports nothing.
test("Person's core TypeScript never imports an environment", () => {
  for (const file of coreSources()) {
    const source = readFileSync(file, "utf8");
    assert.ok(
      !/(from|import\() *"(#minecraft|[^"]*environments\/)/.test(code(source)),
      `${path.relative(REPOSITORY, file)} imports an environment profile`,
    );
  }
});

test("Person's core TypeScript names no Minecraft ontology", () => {
  for (const file of coreSources()) {
    const match = MINECRAFT_WORDS.exec(code(readFileSync(file, "utf8")));
    assert.equal(
      match,
      null,
      `${path.relative(REPOSITORY, file)} names ${match?.[0]}; it belongs in environments/minecraft`,
    );
  }
});

test("the core observation is an envelope; its payload belongs to the environment", () => {
  const schema = JSON.parse(
    readFileSync(
      path.join(SCHEMA_DIRECTORY, "observation.schema.json"),
      "utf8",
    ),
  ) as { properties: Record<string, unknown> };
  assert.deepEqual(Object.keys(schema.properties).sort(), [
    "cognition",
    "experience",
    "observationVersion",
    "payload",
    "previousOutcome",
    "selfMotion",
    "type",
  ]);
  const types = code(
    readFileSync(
      path.join(REPOSITORY, "packages/protocol/ts/types.ts"),
      "utf8",
    ),
  );
  for (const field of [
    "vitals",
    "nearby",
    "affordances",
    "permissions",
    "home",
  ])
    assert.ok(
      !new RegExp(`\\b${field}\\??:`).test(types),
      `the core Observation type must not declare ${field}`,
    );
  const manifest = environmentManifest("minecraft");
  assert.ok(
    manifest.payloadSchema,
    "Minecraft declares its own payload schema",
  );
});

test("the generic skill contract enumerates no environment vocabulary", () => {
  const schema = read("packages/skills/schema/skill-spec.schema.json");
  for (const word of ["gather_wood", "SECURE_FOOD", "chest", "furnace"])
    assert.ok(!schema.includes(word), `the generic skill schema names ${word}`);
  const specs = readdirSync(
    path.join(REPOSITORY, "environments/minecraft/skills"),
  );
  assert.ok(
    specs.includes("vocabulary.json"),
    "Minecraft owns its skill vocabulary",
  );
});

function read(relative: string): string {
  return readFileSync(path.join(REPOSITORY, relative), "utf8");
}
