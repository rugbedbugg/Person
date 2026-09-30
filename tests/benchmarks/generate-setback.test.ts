import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { FixtureWorld } from "#fixture-world";
import { REPOSITORY, temporaryDirectory } from "../support/harness.ts";

const GENERATOR = path.join(
  REPOSITORY,
  "scripts/benchmarks/generate-setback.ts",
);

// Never the declared D2 seed: generating D2 is its own, committed step.
function generate(seed: string): { world: string; plan: string } {
  const out = temporaryDirectory("person-d2-");
  const world = path.join(out, "world.json");
  const plan = path.join(out, "plan.json");
  execFileSync(process.execPath, [GENERATOR, seed, world, plan], {
    cwd: REPOSITORY,
  });
  return {
    world: readFileSync(world, "utf8"),
    plan: readFileSync(plan, "utf8"),
  };
}

test("the setback generator is deterministic", () => {
  assert.deepEqual(generate("test-seed-a"), generate("test-seed-a"));
  assert.notEqual(generate("test-seed-a").world, generate("test-seed-b").world);
});

test("a generated setback world stays in its declared ranges and loads", () => {
  for (const seed of [
    "test-seed-a",
    "test-seed-b",
    "test-seed-c",
    "test-seed-d",
  ]) {
    const world = JSON.parse(generate(seed).world);
    assert.ok([14, 15, 16].includes(world.vitals.food));
    const [berries, logs] = world.clusters.map(
      (c: { center: object }) => c.center,
    );
    const chest = world.containers[0].position;
    const gap = (a: { x: number; z: number }, b: { x: number; z: number }) =>
      Math.hypot(a.x - b.x, a.z - b.z);
    assert.ok(
      gap(berries, logs) > 6 && gap(chest, berries) > 3 && gap(chest, logs) > 3,
    );
    const [spawn, despawn] = world.events;
    assert.ok(
      spawn.atTick >= 3000 && spawn.atTick <= 7000 && spawn.atTick % 200 === 0,
    );
    assert.ok([600, 800, 1000].includes(despawn.atTick - spawn.atTick));
    assert.ok(["zombie", "skeleton"].includes(spawn.name));
    const reach = Math.hypot(spawn.offset.x, spawn.offset.z);
    assert.ok(reach >= 3.5 && reach <= 9.5, `${reach}`);
    new FixtureWorld(world).snapshot();
  }
});

test("a generated plan is held out, with fresh seeds and all four conditions", () => {
  const plan = JSON.parse(generate("test-seed-a").plan);
  assert.equal(plan.split, "heldout");
  assert.deepEqual(plan.seeds, [201, 202, 203, 204, 205]);
  assert.deepEqual(
    plan.conditions.map((c: { id: string }) => c.id),
    ["P0", "A15", "R2rec", "R2act"],
  );
});
