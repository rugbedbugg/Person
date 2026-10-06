/**
 * The quiet grove (ADR 0022 C5, ADR 0023 C6): a fixture world built so one
 * familiar problem can recur in exactly the same Person-visible context.
 * A shelter recorded at a home away from the trees, a chest already
 * Person's and within reach, trunks within reach so Person never walks (its
 * place estimate never drifts), stone in hand, food kept full. The problem
 * is `barren_until_withdrawn`: after each `unrest` the trees drop nothing
 * until Person takes something from its chest.
 */
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { FixtureWorld } from "#fixture-world";
import { shelterPlan } from "../../apps/node-runtime/src/skills/shelter-plan.ts";
import { type Position } from "#minecraft";

export const COGNITION = ["uv", "run", "person-cognition"];
export const PERSON = "test-person-000";
export const HOME = { x: -12, y: 64, z: 0 };
export const CHEST = { x: 1, y: 64, z: 1 };
export const DAY = 24000;
export const EPISODES = [0, DAY, 2 * DAY, 3 * DAY, 4 * DAY];
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

export function quietWorld(
  episodes: number[] = EPISODES,
  regimeChange = 4,
  hurtAt: number | null = null,
): FixtureWorld {
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
    events: [
      // A sudden hurt, far from any emergency: unease rises (ADR 0010).
      ...(hurtAt === null
        ? []
        : [
            {
              atTick: hurtAt,
              type: "set_vitals" as const,
              vitals: { health: 12 },
            },
          ]),
      ...episodes.flatMap((at, n) => [
        { atTick: at, type: "unrest" as const },
        ...(n === regimeChange
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
    ],
    hiddenRules: [{ kind: "barren_until_withdrawn", blocks: ["oak_log"] }],
  });
  world.registerOwnedStorage(CHEST, "storage_1");
  return world;
}

export function seedLedger(outputDirectory: string): void {
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
export const WITHDRAW = {
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

export type Event = {
  type: string;
  tick: number;
  payload: Record<string, unknown>;
};

export function journal(evidence: string): Event[] {
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

export const of = (events: Event[], type: string): Event[] =>
  events.filter((event) => event.type === type);
