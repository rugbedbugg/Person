import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { FixtureWorld } from "#fixture-world";
import { REPOSITORY } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

const NODE = process.execPath;
const SCRIPTED = path.join(REPOSITORY, "tests/support/scripted-cognition.ts");

const threatenedWorld = {
  name: "attribution",
  seed: 21,
  startTick: 0,
  timeOfDay: 1000,
  biome: "plains",
  groundLevel: 63,
  spawn: { x: 0, y: 64, z: 0 },
  vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
  inventory: [{ name: "oak_log", count: 8 }],
  blocks: [],
  clusters: [
    { name: "oak_log", center: { x: 10, y: 64, z: 0 }, count: 12, spread: 2 },
  ],
  entities: [{ name: "zombie", position: { x: 3, y: 64, z: 0 } }],
  containers: [],
  events: [],
};

test("a proposal made under threat is replaced, and the outcome credits what ran", async () => {
  const { report } = await runEpisode({
    world: threatenedWorld,
    cognitionCommand: [NODE, SCRIPTED, "gather_wood"],
    maxDecisions: 1,
  });

  assert.equal(report.decisions.length, 1);
  const decision = report.decisions[0];
  assert.ok(decision);
  assert.equal(decision.requestedSkill, "gather_wood");
  assert.equal(decision.executedSkill, "flee");
  assert.equal(decision.validation, "REPLACE");
  assert.equal(decision.validationLevel, "L1");
  assert.equal(decision.requestedSkillStatus, "PREEMPTED");
  assert.equal(decision.emergency, true);
  assert.equal(report.totals.replaced, 1);
  assert.equal(report.safetyOverrides.length >= 1, true);
  assert.equal(report.safetyOverrides[0]?.preemptedSkill, "gather_wood");

  // The expected effects recorded belong to what actually executed, so a later
  // world model compares the right prediction with the right outcome.
  assert.ok(decision.expectedEffects.some((effect) => effect.fact === "safe"));
});

test("without a threat the same proposal runs as requested", async () => {
  const { report } = await runEpisode({
    world: { ...threatenedWorld, entities: [] },
    cognitionCommand: [NODE, SCRIPTED, "gather_wood", "--target_amount=2"],
    maxDecisions: 1,
  });
  const decision = report.decisions[0];
  assert.ok(decision);
  assert.equal(decision.requestedSkill, "gather_wood");
  assert.equal(decision.executedSkill, "gather_wood");
  assert.equal(decision.validation, "ACCEPT");
  assert.equal(decision.status, "SUCCESS");
});

test("a rejected proposal executes nothing at all", async () => {
  const world = new FixtureWorld({ ...threatenedWorld, entities: [] });
  const before = world.snapshot();
  const { report } = await runEpisode({
    worldObject: world,
    cognitionCommand: [NODE, SCRIPTED, "gather_wood", "--target_amount=9999"],
    maxDecisions: 1,
  });
  const decision = report.decisions[0];
  assert.ok(decision);
  assert.equal(decision.validation, "REJECT");
  assert.equal(decision.executedSkill, null);
  assert.equal(decision.status, "INVALIDATED");
  assert.deepEqual(world.snapshot().inventory, before.inventory);
  assert.deepEqual(world.snapshot().position, before.position);
});
