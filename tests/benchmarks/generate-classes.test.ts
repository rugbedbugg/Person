import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { FixtureWorld } from "#fixture-world";
import { REPOSITORY, temporaryDirectory } from "../support/harness.ts";

const GENERATOR = path.join(
  REPOSITORY,
  "scripts/benchmarks/generate-classes.ts",
);
const NAMES: Record<string, string> = {
  A: "a-wide-margin",
  B: "b-near-tie",
  C: "c-exploration",
};

// Never the declared seeds: generating A2, B2 and C2 is its own committed step.
function generate(cls: string, seed: string) {
  const out = temporaryDirectory("person-v2-");
  const world = path.join(out, "world.json");
  const plan = path.join(out, "plan.json");
  execFileSync(process.execPath, [GENERATOR, cls, seed, world, plan], {
    cwd: REPOSITORY,
  });
  return {
    world: readFileSync(world, "utf8"),
    plan: JSON.parse(readFileSync(plan, "utf8")),
  };
}

const source = (split: string, cls: string) =>
  JSON.parse(
    readFileSync(
      path.join(
        REPOSITORY,
        `fixtures/worlds/benchmarks/${split}/${NAMES[cls]}.json`,
      ),
      "utf8",
    ),
  );

/** What defines the class: everything but layout and interchangeable meat. */
function defining(world: {
  vitals: object;
  inventory: object;
  clusters: { name: string; count: number }[];
  entities: { name: string; position: { x: number; z: number } }[];
  containers: { contents: { name: string; count: number }[] }[];
}) {
  const first = world.entities[0]?.position;
  return {
    vitals: world.vitals,
    inventory: world.inventory,
    berries: world.clusters.find((c) => c.name === "sweet_berry_bush")?.count,
    herd: world.entities.map((e) => [
      e.name,
      e.position.x - first!.x,
      e.position.z - first!.z,
    ]),
    chest: world.containers.map((c) =>
      c.contents.map((item) => [
        item.name.startsWith("cooked_") ? "cooked_meat" : item.name,
        item.count,
      ]),
    ),
  };
}

test("the class generator is deterministic and separates its classes", () => {
  for (const cls of ["A", "B", "C"])
    assert.deepEqual(generate(cls, "test-seed"), generate(cls, "test-seed"));
  assert.notEqual(
    generate("A", "test-seed").world,
    generate("C", "test-seed").world,
  );
});

test("every generated world carries one known class instance's bundle exactly", () => {
  for (const cls of ["A", "B", "C"])
    for (let i = 0; i < 8; i++) {
      const world = JSON.parse(generate(cls, `test-seed-${i}`).world);
      const candidates = ["development", "heldout"].map((split) =>
        defining(source(split, cls)),
      );
      assert.ok(
        candidates.some((candidate) => {
          try {
            assert.deepEqual(defining(world), candidate);
            return true;
          } catch {
            return false;
          }
        }),
        `${cls} seed ${i} mixes or alters a bundle`,
      );
      new FixtureWorld(world).snapshot();
    }
});

test("class C places its food sources inside the initial field of view", () => {
  for (let i = 0; i < 16; i++) {
    const world = JSON.parse(generate("C", `test-seed-${i}`).world);
    const ahead = {
      x: -Math.sin(world.spawnYaw),
      z: -Math.cos(world.spawnYaw),
    };
    const angle = (p: { x: number; z: number }) =>
      (Math.acos((p.x * ahead.x + p.z * ahead.z) / Math.hypot(p.x, p.z)) *
        180) /
      Math.PI;
    const berries = world.clusters.find(
      (c: { name: string }) => c.name === "sweet_berry_bush",
    ).center;
    // The berries and the herd's first member are placed at most 45° off
    // facing; the rest of the herd spreads from there. Vision reaches 100°.
    assert.ok(
      angle(berries) <= 50,
      `berries ${angle(berries).toFixed(1)}° off`,
    );
    assert.ok(
      angle(world.entities[0].position) <= 50,
      "herd anchor off facing",
    );
    for (const entity of world.entities)
      assert.ok(angle(entity.position) <= 90, "a herd member near the edge");
  }
});

test("a generated plan is held out, with the V2 seeds and all four conditions", () => {
  for (const cls of ["A", "B", "C"]) {
    const { plan } = generate(cls, "test-seed");
    assert.equal(plan.split, "heldout");
    assert.equal(plan.benchmarkClass, cls);
    assert.deepEqual(plan.seeds, [201, 202, 203, 204, 205]);
    assert.deepEqual(
      plan.conditions.map((c: { id: string }) => c.id),
      ["P0", "A15", "R2rec", "R2act"],
    );
    assert.equal(plan.learningMode, cls === "C" ? "supervised" : "off");
  }
});
