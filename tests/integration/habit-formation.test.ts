/**
 * C4.1 (ADR 0022 with the ADR 0021/0022 amendment): three independent
 * episodes of one recurring problem, each deliberated, remedied and resolved
 * through the real runtime and cognition, form one shadow habit, and nothing
 * habitual ever acts. Scripted answers, a synthetic identity, a fixture world.
 *
 * The problem is fixture machinery (`barren_until_rested`): after each
 * `unrest` the trees around Person drop nothing until its body has rested
 * long enough. One idle rest is not enough; the rest a deliberation adopts
 * completes it. The world creates the problem and never supplies the remedy.
 * Habit learning stays correlational: Person learns "pursuing rest has
 * resolved this here", never that rest makes trees bear wood.
 *
 * The world is quiet so the context signature can repeat exactly: a shelter
 * and a stocked chest already recorded at a home away from the trees, the
 * trees in reach so Person never walks (its place estimate never drifts),
 * stone in hand, food kept full, and each episode one day after the last.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { Position } from "#config";
import { FixtureWorld } from "#fixture-world";
import { shelterPlan } from "../../apps/node-runtime/src/skills/shelter-plan.ts";
import { temporaryDirectory } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

const COGNITION = ["uv", "run", "person-cognition"];
const PERSON = "test-person-000";
const HOME = { x: -12, y: 64, z: 0 };
const CHEST = { x: -10, y: 64, z: 2 };
const DAY = 24000;
const EPISODES = [0, DAY, 2 * DAY];
const RESET = [
  "oak_log",
  "oak_planks",
  "stick",
  "crafting_table",
  "wooden_pickaxe",
  "wooden_axe",
  "stone_pickaxe",
  "stone_axe",
];

/** Trunks all round, within reach of where Person stands. */
const trunks = [-2, -1, 0, 1, 2]
  .flatMap((x) => [-2, -1, 0, 1, 2].map((z) => [x, z] as const))
  .filter(([x, z]) => Math.max(Math.abs(x), Math.abs(z)) === 2)
  .flatMap(([x, z]) =>
    [64, 65, 66, 67, 68].map((y) => ({
      name: "oak_log",
      position: { x, y, z } as Position,
    })),
  );

function quietWorld(): FixtureWorld {
  const world = new FixtureWorld({
    name: "quiet-grove",
    seed: 7,
    startTick: 0,
    timeOfDay: 1000,
    biome: "forest",
    groundLevel: 63,
    spawn: { x: 0, y: 64, z: 0 },
    spawnYaw: 0,
    vitals: { health: 20, food: 20, saturation: 20, air: 300, armor: 0 },
    inventory: [
      { name: "bread", count: 200 },
      { name: "cobblestone", count: 64 },
    ],
    blocks: [
      ...shelterPlan(HOME).map((position) => ({ name: "dirt", position })),
      ...trunks,
    ],
    clusters: [],
    entities: [],
    containers: [
      {
        position: CHEST,
        kind: "chest",
        contents: [{ name: "bread", count: 40 }],
      },
    ],
    events: EPISODES.flatMap((at) => [
      { atTick: at, type: "unrest" as const },
      ...(at === 0
        ? []
        : [
            { atTick: at, type: "remove_items" as const, items: RESET },
            {
              atTick: at,
              type: "set_vitals" as const,
              vitals: { health: 20, food: 20, saturation: 20 },
            },
          ]),
    ]),
    hiddenRules: [
      { kind: "barren_until_rested", restTicks: 700, blocks: ["oak_log"] },
    ],
  });
  world.registerOwnedStorage(CHEST, "storage_1");
  return world;
}

/** The runtime's own record of the shelter and chest, as if it had built them. */
function seedLedger(outputDirectory: string): void {
  writeFileSync(
    path.join(outputDirectory, `world-test-world-${PERSON}.json`),
    JSON.stringify({
      version: 1,
      worldId: "test-world",
      personId: PERSON,
      home: {
        homeId: "home_primary",
        position: HOME,
        shelterState: "complete",
        bedKnown: false,
      },
      storage: [
        {
          storageId: "storage_1",
          worldId: "test-world",
          dimension: "overworld",
          position: CHEST,
          createdByPerson: PERSON,
          creationEvent: "seeded",
          homeId: "home_primary",
          lastVerified: "2026-10-01T00:00:00.000Z",
        },
      ],
      placedBlocks: shelterPlan(HOME).map((p) => `${p.x},${p.y},${p.z}`),
      furnacePosition: null,
      craftingTablePosition: null,
    }),
  );
}

/** "Gathering keeps failing; rest first." Cites the failing goal and gathers. */
const REST = {
  assessment: {
    summary: "Gathering keeps yielding nothing.",
    premises: ["$situation", "$goal:ESTABLISH_TOOLS", "$recent:gather_wood"],
  },
  uncertainties: [],
  strategies: [
    {
      id: "s1",
      goal_type: "MAINTAIN_RESERVES",
      project_kind: null,
      desired: [{ fact: "rested", direction: "achieve" }],
      // wait_safely is the planner's, not a capability the model is offered.
      expected: [],
      capability_refs: [],
      premises: ["$situation", "$goal:ESTABLISH_TOOLS", "$recent:gather_wood"],
    },
  ],
  preferred: "s1",
  evidence_needed: [],
  confidence: 0.5,
};

type Event = {
  type: string;
  tick: number;
  payload: Record<string, unknown>;
};

function journal(evidence: string): Event[] {
  const directory = path.join(evidence, "journal");
  return readdirSync(directory)
    .filter((name) => name.endsWith(".jsonl"))
    .sort()
    .flatMap((name) =>
      readFileSync(path.join(directory, name), "utf8").split("\n"),
    )
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as Event);
}

const of = (events: Event[], type: string): Event[] =>
  events.filter((event) => event.type === type);
const at = (event: Event): number => Number(event.payload["experienced_tick"]);

test(
  "C4.1: three deliberated, remedied and resolved episodes form one shadow habit, and nothing habitual acts",
  { timeout: 1_200_000 },
  async () => {
    const outputDirectory = temporaryDirectory("person-habit-run-");
    const evidenceDirectory = temporaryDirectory("person-habit-");
    seedLedger(outputDirectory);
    await runEpisode({
      worldObject: quietWorld(),
      cognitionCommand: COGNITION,
      evidenceDirectory,
      outputDirectory,
      personId: PERSON,
      home: HOME,
      maxDecisions: 2000,
      maxTicks: 3 * DAY + 4000,
      deliberation: {
        mode: "active",
        answers: [REST, REST, REST],
        habits: "record_only",
      },
    });
    const events = journal(evidenceDirectory);
    const KEY = "repeated_failure:ESTABLISH_TOOLS";

    const requested = of(events, "deliberation_requested");
    assert.equal(requested.length, 3, "one deliberation per episode, no more");
    const adopted = of(events, "deliberation_adopted");
    assert.deepEqual(
      adopted.map((event) => event.payload["trigger_key_full"]),
      [KEY, KEY, KEY],
    );
    const ids = adopted.map((event) =>
      String(event.payload["deliberation_id"]),
    );
    assert.equal(new Set(ids).size, 3, "three independent lifecycles");

    const evidence = of(events, "habit_evidence_shadow");
    for (const [n, id] of ids.entries()) {
      const start = EPISODES[n]!;
      const end = EPISODES[n + 1] ?? Infinity;
      const inEpisode = (event: Event) =>
        event.tick >= start && event.tick < end;
      const goalId = `goal_deliberation_${id}`;
      const adoptedAt = at(adopted[n]!);

      // The trees stayed barren until the adopted remedy: no gather succeeded
      // in this episode before it was adopted.
      const gathers = events.filter(
        (event) =>
          inEpisode(event) &&
          event.type === "skill_completed" &&
          event.payload["executed_skill"] === "gather_wood",
      );
      assert.ok(
        gathers.every((event) => event.tick > adoptedAt),
        `episode ${n + 1}: wood only after the remedy was adopted`,
      );

      // The adopted goal's own routine produced the rest and satisfied it.
      const own = events.find(
        (event) =>
          event.type === "routine_outcome" &&
          event.payload["goal_id"] === goalId,
      );
      assert.equal(own?.payload["status"], "SUCCESS");
      assert.equal(
        own?.payload["routine_name"],
        "maintain_reserves__wait_safely",
      );
      const ended = of(events, "deliberation_goal_ended").filter(
        (event) => event.payload["deliberation_id"] === id,
      );
      assert.deepEqual(
        ended.map((event) => event.payload["why"]),
        ["satisfied"],
      );

      // Exactly one retry of the goal Person had given up on, which retried
      // and made real progress.
      const retries = of(events, "deliberation_source_retry").filter(
        (event) => event.payload["deliberation_id"] === id,
      );
      assert.equal(
        retries.length,
        1,
        `episode ${n + 1}: one retry, granted once`,
      );
      assert.equal(
        retries[0]!.payload["source_goal_id"],
        "goal_establish_tools",
      );
      assert.equal(
        retries[0]!.payload["prior_block_reason"],
        "repeated_routine_failure",
      );
      const retryAt = at(retries[0]!);
      const progress = events.find(
        (event) =>
          inEpisode(event) &&
          event.type === "routine_outcome" &&
          event.payload["goal_id"] === "goal_establish_tools" &&
          event.payload["status"] === "SUCCESS",
      );
      assert.ok(progress, `episode ${n + 1}: the retried goal succeeded`);
      assert.ok(gathers.length > 0 && gathers[0]!.tick >= retryAt);

      // Stable: success only once the whole window has passed quietly.
      const verdicts = evidence.filter(
        (event) => event.payload["deliberation_id"] === id,
      );
      assert.deepEqual(
        verdicts.map((event) => [
          event.payload["verdict"],
          event.payload["reason"],
        ]),
        [["success", "stable"]],
      );
      assert.ok(at(verdicts[0]!) - at(ended[0]!) >= 1200);
    }

    // One template, one exact context signature, three successes, one promotion.
    const candidates = of(events, "habit_candidate_shadow");
    assert.equal(candidates.length, 1, "the same response template each time");
    const template = candidates[0]!.payload["template"] as Record<
      string,
      unknown
    >;
    assert.equal(template["trigger_kind"], "repeated_failure");
    assert.equal(template["goal_type"], "MAINTAIN_RESERVES");
    assert.ok(
      evidence.every(
        (event) => event.payload["template_id"] === template["template_id"],
      ),
    );
    const promotions = of(events, "habit_promotion_shadow");
    assert.equal(promotions.length, 1);
    assert.deepEqual(promotions[0]!.payload["founding"], ids);

    // Record-only never acts: nothing in the active stream exists.
    for (const active of [
      "habit_candidate_formed",
      "habit_evidence",
      "habit_promoted",
      "habit_conflict",
      "habit_invoked",
      "habit_not_applicable",
      "habit_demoted",
    ])
      assert.equal(of(events, active).length, 0, `${active} must not exist`);
  },
);
