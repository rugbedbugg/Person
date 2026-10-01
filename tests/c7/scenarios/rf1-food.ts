/**
 * RF-1 (C7B, repeated_failure): hungry, far from a home Person remembers.
 *
 * Person's history: it learned home from its own return there, saw berry
 * bushes at home, and walked about seventy blocks ahead. Now it is hungry
 * with no food in hand. Its planner reaches for its owned chest, which is at
 * home; from here the withdrawal is refused, three times, and the food goal
 * blocks. Grounded remedy: go home, where the remembered food and the chest
 * are. System 1 alone never retries the blocked food goal.
 */
import { FixtureWorld } from "#fixture-world";
import { of, PERSON, type Scenario } from "../scenario.ts";

const HOME = { x: 0, y: 64, z: 72 };
const CHEST = { x: 2, y: 64, z: 69 };
const BUSHES = [
  [3, 70],
  [4, 72],
  [3, 74],
  [-3, 71],
  [-4, 73],
];
const WIDE = {
  min: { x: -96, y: 56, z: -96 },
  max: { x: 96, y: 80, z: 160 },
};

export const rf1Food: Scenario = {
  id: "c7b-rf1-food-home",
  family: "C7B",
  provider: {
    prelude: { name: "home-and-away", args: ["72", "plant_food"] },
    world: () => {
      const world = new FixtureWorld({
        name: "c7b-rf1",
        seed: 3,
        startTick: 0,
        timeOfDay: 1000,
        biome: "plains",
        groundLevel: 63,
        spawn: { x: 0, y: 64, z: 0 },
        spawnYaw: 0,
        vitals: { health: 20, food: 10, saturation: 0, air: 300, armor: 0 },
        inventory: [
          { name: "stone_pickaxe", count: 1 },
          { name: "stone_axe", count: 1 },
        ],
        blocks: BUSHES.map(([x, z]) => ({
          name: "sweet_berry_bush",
          position: { x: x!, y: 64, z: z! },
        })),
        clusters: [],
        entities: [],
        containers: [
          {
            position: CHEST,
            kind: "chest",
            contents: [{ name: "bread", count: 24 }],
          },
        ],
        events: [],
      });
      world.registerOwnedStorage(CHEST, "storage_1");
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
    maxTicks: 6000,
    maxDecisions: 300,
    habits: "off",
    affectArbitration: "off",
  },
  evaluator: {
    trigger: "repeated_failure",
    intendedRemedy: { goal_type: "RECOVER_HOME", desired: ["at_home"] },
    premises: [
      "home_relation is far",
      "a recalled perception of plant food at the place labelled home",
      "three refused withdrawals from owned storage here",
    ],
    oracle: {
      assessment: {
        summary: "Food keeps failing here, and food was seen at home.",
        premises: ["$situation", "$goal:SECURE_FOOD", "$mem:perceived"],
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
          premises: [
            "$situation",
            "$goal:SECURE_FOOD",
            "$mem:perceived",
            "$recent:withdraw_owned_storage",
          ],
        },
      ],
      preferred: "s1",
      evidence_needed: [],
      confidence: 0.6,
    },
    // Fed again, and no food failure for the stabilization window after.
    resolved: ({ events, world }) => {
      const fed = of(events, "skill_completed").find(
        (event) =>
          event.payload["executed_skill"] === "eat_to_target" &&
          event.payload["status"] === "SUCCESS",
      );
      if (!fed || world.snapshot().food < 16) return false;
      return !of(events, "skill_failed").some(
        (event) =>
          event.payload["goal_id"] === "goal_secure_food" &&
          event.tick > fed.tick &&
          event.tick <= fed.tick + 1200,
      );
    },
  },
};
