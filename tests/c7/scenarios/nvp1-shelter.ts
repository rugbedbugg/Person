/**
 * NVP-1 (C7B, no_viable_plan): no shelter materials here; wood at home.
 *
 * Person's history: it learned home from its own return there, saw trees at
 * home, and walked about seventy blocks ahead. It has no shelter and nothing
 * to build one with, and searching here finds nothing: the shelter goal has
 * no viable plan. Grounded remedy: go home, where it remembers wood. System
 * 1 alone does not go home by day.
 */
import { FixtureWorld } from "#fixture-world";
import { of, PERSON, type Scenario } from "../scenario.ts";

const HOME = { x: 0, y: 64, z: 72 };
const TREES = [
  [4, 70],
  [5, 72],
  [4, 74],
  [-4, 70],
  [-5, 72],
  [-4, 74],
  [2, 77],
  [-2, 77],
  [2, 67],
  [-2, 67],
];
const WIDE = {
  min: { x: -96, y: 56, z: -96 },
  max: { x: 96, y: 80, z: 160 },
};

export const nvp1Shelter: Scenario = {
  id: "c7b-nvp1-shelter-home",
  family: "C7B",
  provider: {
    prelude: { name: "home-and-away", args: ["72", "wood"] },
    world: () => {
      const world = new FixtureWorld({
        name: "c7b-nvp1",
        seed: 3,
        startTick: 0,
        timeOfDay: 1000,
        biome: "plains",
        groundLevel: 63,
        spawn: { x: 0, y: 64, z: 0 },
        spawnYaw: 0,
        vitals: { health: 20, food: 20, saturation: 20, air: 300, armor: 0 },
        inventory: [
          { name: "bread", count: 64 },
          { name: "stone_pickaxe", count: 1 },
          { name: "stone_axe", count: 1 },
        ],
        blocks: TREES.flatMap(([x, z]) =>
          [64, 65, 66, 67].map((y) => ({
            name: "oak_log",
            position: { x: x!, y, z: z! },
          })),
        ),
        clusters: [],
        entities: [],
        containers: [],
        events: [],
      });
      return world;
    },
    ledger: {
      version: 1,
      worldId: "test-world",
      personId: PERSON,
      home: {
        homeId: "home_primary",
        position: HOME,
        shelterState: "none",
        bedKnown: false,
      },
      storage: [],
      placedBlocks: [],
      furnacePosition: null,
      craftingTablePosition: null,
    },
    config: {
      world: {
        home: HOME,
        exploration: WIDE,
        resourceAreas: [WIDE],
        protectedAreas: [],
      },
    },
    home: HOME,
    maxTicks: 7000,
    maxDecisions: 300,
    habits: "off",
    affectArbitration: "off",
  },
  evaluator: {
    trigger: "no_viable_plan",
    intendedRemedy: { goal_type: "RECOVER_HOME", desired: ["at_home"] },
    premises: [
      "home_relation is far",
      "a recalled perception of wood at the place labelled home",
      "the shelter goal has no viable plan here",
    ],
    oracle: {
      assessment: {
        summary: "Nothing to build a shelter with here; wood was seen at home.",
        premises: ["$situation", "$goal:SECURE_SHELTER", "$mem:perceived"],
      },
      uncertainties: [],
      strategies: [
        {
          id: "s1",
          goal_type: "RECOVER_HOME",
          project_kind: null,
          desired: [{ fact: "at_home", direction: "achieve" }],
          expected: [],
          capability_refs: [],
          premises: ["$situation", "$goal:SECURE_SHELTER", "$mem:perceived"],
        },
      ],
      preferred: "s1",
      evidence_needed: [],
      confidence: 0.6,
    },
    // A shelter built, and no shelter failure in the window after.
    resolved: ({ events }) => {
      const built = of(events, "skill_completed").find(
        (event) =>
          event.payload["executed_skill"] === "build_basic_shelter" &&
          event.payload["status"] === "SUCCESS",
      );
      if (!built) return false;
      return !of(events, "skill_failed").some(
        (event) =>
          event.payload["goal_id"] === "goal_secure_shelter" &&
          event.tick > built.tick &&
          event.tick <= built.tick + 1200,
      );
    },
  },
};
