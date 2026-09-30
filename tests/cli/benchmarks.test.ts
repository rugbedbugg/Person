import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { FixtureWorld, type FixtureWorldDefinition } from "#fixture-world";
import { loadPlan } from "../../apps/cli/src/experiment.ts";
import { REPOSITORY } from "../support/harness.ts";

/**
 * The R1.5 benchmark suite and its split (ADR 0013). Nothing here runs a
 * plan: held-out plans are evaluated once, on a finished model, and never
 * while one is designed.
 */

const plans = (split: string) => {
  const directory = path.join(REPOSITORY, "experiments/benchmarks", split);
  return readdirSync(directory)
    .filter((name) => name.endsWith(".json") && name !== "MANIFEST.json")
    .sort()
    .map((name) => {
      const file = path.join(directory, name);
      return { file, name, plan: loadPlan(file) };
    });
};

test("every benchmark class exists in both splits, with the three affect modes", () => {
  for (const split of ["development", "heldout"]) {
    const found = plans(split);
    assert.deepEqual(
      found.map((entry) => entry.plan.benchmarkClass),
      ["A", "B", "C", "D"],
    );
    for (const { plan } of found) {
      assert.equal(plan.split, split);
      assert.deepEqual(
        plan.conditions.map((condition) => condition.affectMode),
        ["off", "record_only", "active"],
      );
      assert.deepEqual(
        (plan.horizons ?? []).map((horizon) => horizon.id),
        ["short", "medium", "long"],
      );
    }
  }
});

test("development and held-out share no world and no seed", () => {
  const development = plans("development");
  const heldout = plans("heldout");
  const worlds = (entries: typeof development) =>
    entries.map((entry) =>
      path.resolve(path.dirname(entry.file), entry.plan.world),
    );
  for (const world of worlds(development))
    assert.ok(world.includes("/benchmarks/development/"), world);
  for (const world of worlds(heldout))
    assert.ok(world.includes("/benchmarks/heldout/"), world);
  const seeds = (entries: typeof development) =>
    new Set(entries.flatMap((entry) => entry.plan.seeds));
  for (const seed of seeds(heldout))
    assert.ok(!seeds(development).has(seed), `seed ${seed} is in both splits`);
  const digest = (file: string) =>
    createHash("sha256").update(readFileSync(file)).digest("hex");
  const developmentWorlds = new Set(worlds(development).map(digest));
  for (const world of worlds(heldout))
    assert.ok(
      !developmentWorlds.has(digest(world)),
      "a held-out world is a copy",
    );
});

test("the held-out set is frozen exactly as its manifest records", () => {
  const manifest = JSON.parse(
    readFileSync(
      path.join(REPOSITORY, "experiments/benchmarks/heldout/MANIFEST.json"),
      "utf8",
    ),
  ) as { files: Record<string, string> };
  const listed = Object.keys(manifest.files).sort();
  const present = [
    ...plans("heldout").map((entry) => path.relative(REPOSITORY, entry.file)),
    ...readdirSync(path.join(REPOSITORY, "fixtures/worlds/benchmarks/heldout"))
      .filter((name) => name.endsWith(".json"))
      .map((name) => `fixtures/worlds/benchmarks/heldout/${name}`),
  ].sort();
  assert.deepEqual(
    listed,
    present,
    "every held-out file is listed, and only those",
  );
  for (const [file, hash] of Object.entries(manifest.files))
    assert.equal(
      createHash("sha256")
        .update(readFileSync(path.join(REPOSITORY, file)))
        .digest("hex"),
      hash,
      `${file} changed after the held-out set was frozen`,
    );
});

test("every benchmark world is a valid fixture world", () => {
  for (const split of ["development", "heldout"])
    for (const { file, plan } of plans(split)) {
      const definition = JSON.parse(
        readFileSync(path.resolve(path.dirname(file), plan.world), "utf8"),
      ) as FixtureWorldDefinition;
      const world = new FixtureWorld(definition);
      assert.equal(world.definition.name, definition.name);
    }
});

test("held-out D2 is frozen as its manifest records, and regenerates from its seed", async () => {
  const { execFileSync } = await import("node:child_process");
  const { temporaryDirectory } = await import("../support/harness.ts");
  const manifest = JSON.parse(
    readFileSync(
      path.join(REPOSITORY, "experiments/benchmarks/heldout-d2/MANIFEST.json"),
      "utf8",
    ),
  ) as { seedUsed: string; files: Record<string, string> };
  for (const [file, hash] of Object.entries(manifest.files))
    assert.equal(
      createHash("sha256")
        .update(readFileSync(path.join(REPOSITORY, file)))
        .digest("hex"),
      hash,
      `${file} changed after D2 was frozen`,
    );
  const out = temporaryDirectory("person-d2-check-");
  execFileSync(
    process.execPath,
    [
      "scripts/benchmarks/generate-setback.ts",
      manifest.seedUsed,
      path.join(out, "world.json"),
      path.join(out, "plan.json"),
    ],
    { cwd: REPOSITORY },
  );
  assert.equal(
    readFileSync(path.join(out, "world.json"), "utf8"),
    readFileSync(
      path.join(
        REPOSITORY,
        "fixtures/worlds/benchmarks/heldout-d2/d2-setback.json",
      ),
      "utf8",
    ),
    "the committed world is exactly what the declared seed generates",
  );
});
