/**
 * C5, the canonical active habit lifecycle (ADR 0022): controlled, then
 * automatic, then controlled again, through the real runtime and cognition,
 * with scripted answers, a synthetic identity and a fixture world.
 *
 * The problem is fixture machinery (`barren_until_withdrawn`): after each
 * `unrest` the trees around Person drop nothing until it takes something out
 * of a chest it owns. What it takes never helps by itself; Person's idle
 * routine never withdraws, so the remedy is the only cure there is.
 *
 * Episodes one day apart, each the same problem in the same context:
 *   1-3: System 2 proposes MAINTAIN_RESERVES/withdrawn; adopted, remedied,
 *        the blocked goal retried once, resolved: three successes, promoted;
 *   4:   the habit answers with no model call, and resolves it the same way;
 *   5:   the world changes (withdrawing no longer helps): the habit is
 *        invoked, its retry fails, it is demoted, and System 2 is asked again.
 *
 * The world is quiet so the context signature can repeat exactly: a shelter
 * recorded at a home away from the trees, the chest in reach and already
 * Person's, the trees in reach so Person never walks, stone in hand, food
 * kept full.
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
const CHEST = { x: 1, y: 64, z: 1 };
const DAY = 24000;
const EPISODES = [0, DAY, 2 * DAY, 3 * DAY, 4 * DAY];
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
    name: "quiet-grove-chest",
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
        contents: [{ name: "bread", count: 64 }],
      },
    ],
    events: EPISODES.flatMap((at, n) => [
      { atTick: at, type: "unrest" as const },
      ...(n === 4
        ? [{ atTick: at, type: "withdrawal_stops_helping" as const }]
        : []),
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
    hiddenRules: [{ kind: "barren_until_withdrawn", blocks: ["oak_log"] }],
  });
  world.registerOwnedStorage(CHEST, "storage_1");
  return world;
}

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
      placedBlocks: [
        ...shelterPlan(HOME).map((p) => `${p.x},${p.y},${p.z}`),
        `${CHEST.x},${CHEST.y},${CHEST.z}`,
      ],
      furnacePosition: null,
      craftingTablePosition: null,
    }),
  );
}

/** "Gathering keeps failing; fetch from storage first." */
const WITHDRAW = {
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
      desired: [{ fact: "withdrawn", direction: "achieve" }],
      expected: [
        {
          fact: "withdrawn",
          direction: "achieve",
          support: ["$cap:withdrawn"],
        },
      ],
      capability_refs: ["$cap:withdrawn"],
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
const inDay = (n: number) => (event: Event) =>
  event.tick >= EPISODES[n]! && event.tick < (EPISODES[n + 1] ?? Infinity);

test(
  "C5: three deliberated resolutions form a habit, the fourth problem is answered without a model, and a changed world sends it back to System 2",
  { timeout: 1_800_000 },
  async () => {
    const outputDirectory = temporaryDirectory("person-lifecycle-run-");
    const evidenceDirectory = temporaryDirectory("person-lifecycle-");
    seedLedger(outputDirectory);
    await runEpisode({
      worldObject: quietWorld(),
      cognitionCommand: COGNITION,
      evidenceDirectory,
      outputDirectory,
      personId: PERSON,
      home: HOME,
      maxDecisions: 4000,
      maxTicks: 5 * DAY + 4000,
      deliberation: {
        mode: "active",
        answers: [WITHDRAW, WITHDRAW, WITHDRAW, WITHDRAW],
        habits: "active",
      },
    });
    const events = journal(evidenceDirectory);
    if (process.env.LIFECYCLE_DUMP)
      for (const event of events)
        if (/^(deliberation_|habit_)/.test(event.type))
          console.log(
            event.tick,
            event.type,
            JSON.stringify(event.payload).slice(0, 220),
          );

    const KEY = "repeated_failure:ESTABLISH_TOOLS";
    const requested = of(events, "deliberation_requested");

    // 1-3: controlled. One deliberation each, adopted, remedied, resolved.
    for (const n of [0, 1, 2]) {
      const day = events.filter(inDay(n));
      const asked = of(day, "deliberation_requested");
      assert.deepEqual(
        asked.map((event) => event.payload["trigger_key_full"]),
        [KEY],
        `episode ${n + 1}: one deliberation`,
      );
      const id = asked[0]!.payload["deliberation_id"];
      const adopted = of(day, "deliberation_adopted");
      assert.equal(adopted.length, 1);
      const adoptedAt = adopted[0]!.tick;
      assert.ok(
        of(day, "skill_completed")
          .filter((event) => event.payload["executed_skill"] === "gather_wood")
          .every((event) => event.tick > adoptedAt),
        `episode ${n + 1}: no wood before the remedy`,
      );
      const own = day.find(
        (event) =>
          event.type === "routine_outcome" &&
          event.payload["goal_id"] === `goal_deliberation_${id}`,
      );
      assert.equal(own?.payload["status"], "SUCCESS");
      assert.equal(
        of(day, "deliberation_source_retry").length,
        1,
        `episode ${n + 1}: one retry`,
      );
      assert.deepEqual(
        of(day, "habit_evidence").map((event) => [
          event.payload["verdict"],
          event.payload["reason"],
        ]),
        [["success", "stable"]],
      );
    }
    const promoted = of(events, "habit_promoted");
    assert.equal(promoted.length, 1, "promoted once, after the third");
    const habit = String(promoted[0]!.payload["template_id"]);
    assert.ok(promoted[0]!.tick < EPISODES[3]!);
    assert.equal(
      of(events, "habit_candidate_formed").length,
      1,
      "one template, one exact signature",
    );

    // 4: automatic. No model, the same remedy, the same resolution.
    const four = events.filter(inDay(3));
    assert.equal(
      of(four, "deliberation_requested").length,
      0,
      "episode 4: zero deliberation requests",
    );
    const invoked = of(four, "habit_invoked");
    assert.equal(invoked.length, 1);
    assert.equal(invoked[0]!.payload["template_id"], habit);
    const invocation = invoked[0]!.payload["habit_invocation_id"];
    assert.deepEqual(
      of(four, "habit_goal_ended").map((event) => event.payload["why"]),
      ["satisfied"],
    );
    const retries = of(four, "habit_source_retry");
    assert.equal(retries.length, 1, "episode 4: one retry, granted once");
    assert.equal(retries[0]!.payload["habit_invocation_id"], invocation);
    assert.equal(retries[0]!.payload["source_goal_id"], "goal_establish_tools");
    assert.deepEqual(
      of(four, "habit_evidence").map((event) => [
        event.payload["via"],
        event.payload["verdict"],
        event.payload["reason"],
      ]),
      [["habit", "success", "stable"]],
    );

    // 5: the world changed. Invoked, satisfied, retried, failed: demoted,
    // and the problem goes back to System 2 at once.
    const five = events.filter(inDay(4));
    assert.equal(of(five, "habit_invoked").length, 1);
    assert.equal(of(five, "habit_source_retry").length, 1);
    const fiveEvidence = of(five, "habit_evidence");
    assert.deepEqual(
      fiveEvidence
        .filter((event) => event.payload["via"] === "habit")
        .map((event) => [event.payload["verdict"], event.payload["reason"]]),
      [["failure", "recurred"]],
      "episode 5: the habit's own remedy no longer resolves it",
    );
    // System 2's answer to the breakdown is evidence for the same problem's
    // template, counted as deliberation, never as the habit's.
    assert.ok(
      fiveEvidence
        .filter((event) => event.payload["via"] !== "habit")
        .every((event) => event.payload["template_id"] === habit),
    );
    const demoted = of(five, "habit_demoted");
    assert.equal(demoted.length, 1);
    assert.equal(demoted[0]!.payload["template_id"], habit);
    const breakdown = of(five, "deliberation_requested");
    assert.ok(breakdown.length >= 1, "System 2 requested again");
    assert.equal(
      breakdown[0]!.payload["trigger_key_full"],
      `habit_breakdown:${habit}`,
    );
    assert.ok(breakdown[0]!.tick >= demoted[0]!.tick);

    // Nothing habitual ever came from the shadow stream.
    assert.equal(of(events, "habit_candidate_shadow").length, 0);
    assert.equal(requested.length, 3 + breakdown.length);
  },
);
