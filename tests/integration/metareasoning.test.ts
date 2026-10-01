/**
 * Metareasoning through the real runtime and cognition (ADR 0021), with
 * scripted answers and a synthetic identity: the canonical air-recurrence
 * cases, an unavailable model, and record-only changing nothing.
 *
 * The pool: deep water beside dry home. The body is put at the bottom; each
 * suffocation is answered by `restore_air`; the body then sinks again, as a
 * Mineflayer body does. Restoring air keeps working, and the strategy of
 * staying in deep water keeps failing.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import type { Position } from "#config";
import { FixtureWorld } from "#fixture-world";
import { temporaryDirectory } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

const COGNITION = ["uv", "run", "person-cognition"];
const HOME = { x: 8, y: 64, z: 0 };

function pool(): FixtureWorld {
  const blocks: { name: string; position: Position }[] = [];
  for (let x = -3; x <= 3; x++)
    for (let z = -3; z <= 3; z++)
      for (let y = 57; y <= 63; y++)
        blocks.push({ name: "water", position: { x, y, z } });
  const world = new FixtureWorld({
    name: "deep-pool",
    seed: 21,
    startTick: 0,
    timeOfDay: 1000,
    biome: "plains",
    groundLevel: 63,
    spawn: HOME,
    spawnYaw: 0,
    vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
    inventory: [],
    blocks,
    clusters: [],
    entities: [],
    containers: [],
    events: [],
  });
  world.teleport({ x: 0, y: 58, z: 0 });
  world.setVitals({ air: 85 });
  return world;
}

const RECOVER = {
  assessment: {
    summary: "Air keeps running out while staying in deep water.",
    premises: ["$mem:endangered", "$situation"],
  },
  uncertainties: [],
  strategies: [
    {
      id: "s1",
      goal_type: "RECOVER_HOME",
      project_kind: null,
      desired: [{ fact: "at_home", direction: "achieve" }],
      expected: [
        { fact: "at_home", direction: "achieve", support: ["$cap:at_home"] },
      ],
      capability_refs: ["$cap:at_home"],
      premises: ["$mem:endangered", "$situation"],
    },
  ],
  preferred: "s1",
  evidence_needed: [],
  confidence: 0.6,
};

/** A recovery Person has no way to bring about: nothing produces it. */
const UNPLANNABLE = {
  ...RECOVER,
  strategies: [
    {
      ...RECOVER.strategies[0],
      goal_type: "SECURE_FOOD",
      desired: [{ fact: "reachable_animal", direction: "achieve" }],
      expected: [],
      capability_refs: [],
    },
  ],
};

function journal(evidence: string) {
  const directory = path.join(evidence, "journal");
  return readdirSync(directory)
    .filter((name) => name.endsWith(".jsonl"))
    .sort()
    .flatMap((name) =>
      readFileSync(path.join(directory, name), "utf8").split("\n"),
    )
    .filter((line) => line.trim())
    .map(
      (line) =>
        JSON.parse(line) as { type: string; payload: Record<string, unknown> },
    );
}

async function live(
  mode: "off" | "record_only" | "active",
  answers: unknown[],
  maxDecisions = 500,
  habits: "off" | "record_only" = "off",
) {
  const evidenceDirectory = temporaryDirectory("person-meta-");
  const world = pool();
  const { report } = await runEpisode({
    worldObject: world,
    cognitionCommand: COGNITION,
    evidenceDirectory,
    personId: "test-person-000",
    maxDecisions,
    home: HOME,
    deliberation: { mode, answers, habits },
  });
  return { report, world, events: journal(evidenceDirectory) };
}

type Event = { type: string; payload: Record<string, unknown> };
const of = (events: Event[], type: string): Event[] =>
  events.filter((event) => event.type === type);

test(
  "A: recurring suffocation leads to one deliberation, an adopted recovery at 700, and the body out of the water",
  { timeout: 300000 },
  async () => {
    const { world, events } = await live("active", [RECOVER]);
    const overrides = of(events, "emergency_override");
    assert.ok(overrides.length >= 3, "suffocation recurred");
    for (const override of overrides)
      if (override.payload["trigger"] === "suffocation")
        assert.equal(override.payload["action"], "restore_air");
    const requested = of(events, "deliberation_requested").filter(
      (e) =>
        e.payload["trigger_key_full"] === "emergency_recurrence:suffocation",
    );
    assert.equal(
      requested.length,
      1,
      "one deliberation, not one per emergency",
    );
    assert.equal(
      of(events, "deliberation_goal_ended")[0]?.payload["why"],
      "satisfied",
      "the recovery was reached",
    );
    const [adopted] = of(events, "deliberation_adopted");
    assert.ok(adopted, "the recovery was adopted");
    assert.equal(adopted.payload["goal_type"], "RECOVER_HOME");
    assert.equal(adopted.payload["priority"], 700);
    assert.equal(adopted.payload["priority_source"], "recovery_band");
    assert.ok(
      events.some(
        (e) =>
          e.type === "skill_started" &&
          e.payload["executed_skill"] === "return_home",
      ),
      "Person's own planner and skill did the how",
    );
    const at = world.snapshot().position;
    assert.ok(
      Math.abs(at.x) > 3 || Math.abs(at.z) > 3 || at.y >= 64,
      `out of the water at ${JSON.stringify(at)}`,
    );
  },
);

test(
  "B: a recovery Person cannot plan is discarded, and Person carries on without it",
  { timeout: 300000 },
  async () => {
    const { events } = await live("active", [UNPLANNABLE]);
    assert.equal(
      of(events, "deliberation_requested").filter(
        (e) =>
          e.payload["trigger_key_full"] === "emergency_recurrence:suffocation",
      ).length,
      1,
    );
    assert.equal(of(events, "deliberation_adopted").length, 0);
    const [discarded] = of(events, "deliberation_discarded");
    assert.equal(discarded?.payload["reason"], "infeasible");
    for (const override of of(events, "emergency_override"))
      if (override.payload["trigger"] === "suffocation")
        assert.equal(override.payload["action"], "restore_air");
  },
);

test(
  "C: an unavailable model changes nothing and is not asked again in a loop",
  { timeout: 300000 },
  async () => {
    const { events } = await live("active", [null, null, null, null]);
    assert.equal(
      of(events, "deliberation_requested").filter(
        (e) =>
          e.payload["trigger_key_full"] === "emergency_recurrence:suffocation",
      ).length,
      1,
      "no loop: the same problem is not asked about again within its cooldown",
    );
    const [discarded] = of(events, "deliberation_discarded");
    assert.equal(discarded?.payload["reason"], "unavailable");
    assert.ok(
      of(events, "deliberation_suppressed").every(
        (e) => e.payload["reason"] !== undefined,
      ),
    );
  },
);

test(
  "record-only runs the whole path and changes nothing but its own evidence",
  { timeout: 300000 },
  async () => {
    const off = await live("off", [RECOVER]);
    const shadow = await live("record_only", [RECOVER]);
    const skills = (report: typeof off.report) =>
      report.decisions.map((d) => [
        d.requestedSkill ?? null,
        d.executedSkill ?? null,
        d.status ?? null,
      ]);
    assert.deepEqual(skills(shadow.report), skills(off.report));
    assert.deepEqual(
      shadow.world.snapshot().position,
      off.world.snapshot().position,
    );
    assert.equal(of(shadow.events, "deliberation_adopted").length, 0);
    const [disposition] = of(shadow.events, "deliberation_shadow_disposition");
    assert.equal(disposition?.payload["disposition"], "would_adopt");
    assert.equal(
      (disposition?.payload["hypothetical_goal"] as { goal_type: string })
        .goal_type,
      "RECOVER_HOME",
    );
    assert.equal(of(off.events, "deliberation_requested").length, 0);
  },
);

test(
  "shadow habit learning changes nothing Person does, and records its evidence apart",
  { timeout: 300000 },
  async () => {
    // Plumbing, not the canonical habit case (ADR 0022): the same adopted
    // recovery, with habit learning off and in record-only.
    const off = await live("active", [RECOVER], 500, "off");
    const shadow = await live("active", [RECOVER], 500, "record_only");
    const skills = (report: typeof off.report) =>
      report.decisions.map((d) => [
        d.requestedSkill ?? null,
        d.executedSkill ?? null,
        d.status ?? null,
      ]);
    assert.deepEqual(skills(shadow.report), skills(off.report));
    assert.deepEqual(
      shadow.world.snapshot().position,
      off.world.snapshot().position,
    );
    const evidence = of(shadow.events, "habit_evidence_shadow");
    assert.equal(evidence.length, 1);
    assert.equal(
      evidence[0]!.payload["verdict"],
      "success",
      "satisfied, and quiet for the window",
    );
    assert.ok(
      !shadow.events.some(
        (e) => e.type.startsWith("habit_") && !e.type.endsWith("_shadow"),
      ),
      "nothing in the active stream",
    );
    assert.ok(!off.events.some((e) => e.type.startsWith("habit_")));
  },
);
