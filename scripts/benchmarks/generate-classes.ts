/**
 * Generates held-out A2, B2 or C2 exactly as
 * `experiments/benchmarks/heldout-v2/PROCEDURE.md` declares.
 *
 *   node scripts/benchmarks/generate-classes.ts <A|B|C> <seed> <world.json> <plan.json>
 *
 * Valid by construction: the class-defining bundle (inventory, vitals, food
 * sources, chest contents, learner) is copied whole from one known instance
 * of the class, chosen by the first draw; only layout is drawn fresh, in a way
 * that never needs a rejection loop. Deterministic: the same class and seed
 * always write the same bytes. It never runs anything, and never retries.
 */
import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

type Point = { x: number; y: number; z: number };
type Item = { name: string; count: number };

interface Bundle {
  source: string;
  vitals: Record<string, number>;
  inventory: Item[];
  berries: number;
  chest: Item[] | null;
  /** Herd kind and member offsets from the first member, as in the source. */
  herd: { kind: string; offsets: [number, number][] } | null;
  /** Radius of the herd's first member from spawn, in blocks. */
  herdRadius: [number, number] | null;
  /** Whether food sources must lie inside the initial field of view. */
  inView: boolean;
  learningMode: "off" | "supervised";
}

const BUNDLES: Record<string, Bundle[]> = {
  A: [
    {
      source: "fixtures/worlds/benchmarks/development/a-wide-margin.json",
      vitals: { health: 20, food: 12, saturation: 0, air: 300, armor: 0 },
      inventory: [
        { name: "stone_pickaxe", count: 1 },
        { name: "oak_planks", count: 64 },
      ],
      berries: 12,
      chest: [
        { name: "bread", count: 64 },
        { name: "cooked_meat", count: 32 },
      ],
      herd: {
        kind: "cow",
        offsets: [
          [0, 0],
          [1, 1],
        ],
      },
      herdRadius: [16, 20],
      inView: false,
      learningMode: "off",
    },
    {
      source: "fixtures/worlds/benchmarks/heldout/a-wide-margin.json",
      vitals: { health: 20, food: 10, saturation: 0, air: 300, armor: 0 },
      inventory: [
        { name: "stone_pickaxe", count: 1 },
        { name: "oak_log", count: 40 },
      ],
      berries: 12,
      chest: [
        { name: "bread", count: 48 },
        { name: "cooked_meat", count: 24 },
      ],
      herd: { kind: "pig", offsets: [[0, 0]] },
      herdRadius: [16, 20],
      inView: false,
      learningMode: "off",
    },
  ],
  B: [
    {
      source: "fixtures/worlds/benchmarks/development/b-near-tie.json",
      vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
      inventory: [
        { name: "wooden_pickaxe", count: 1 },
        { name: "oak_planks", count: 64 },
        { name: "oak_log", count: 8 },
      ],
      berries: 12,
      chest: null,
      herd: null,
      herdRadius: null,
      inView: false,
      learningMode: "off",
    },
    {
      source: "fixtures/worlds/benchmarks/heldout/b-near-tie.json",
      vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
      inventory: [{ name: "oak_log", count: 40 }],
      berries: 12,
      chest: null,
      herd: null,
      herdRadius: null,
      inView: false,
      learningMode: "off",
    },
  ],
  C: [
    {
      source: "fixtures/worlds/benchmarks/development/c-exploration.json",
      vitals: { health: 20, food: 8, saturation: 0, air: 300, armor: 0 },
      inventory: [
        { name: "stone_pickaxe", count: 1 },
        { name: "oak_planks", count: 32 },
        { name: "furnace", count: 1 },
        { name: "coal", count: 16 },
      ],
      berries: 16,
      chest: [{ name: "bread", count: 12 }],
      herd: {
        kind: "cow",
        offsets: [
          [0, 0],
          [1, -1],
          [-1, -2],
          [2, 0],
          [0, -3],
          [1, 1],
        ],
      },
      herdRadius: [5, 8],
      inView: true,
      learningMode: "supervised",
    },
    {
      source: "fixtures/worlds/benchmarks/heldout/c-exploration.json",
      vitals: { health: 20, food: 6, saturation: 0, air: 300, armor: 0 },
      inventory: [
        { name: "stone_pickaxe", count: 1 },
        { name: "oak_log", count: 24 },
        { name: "furnace", count: 1 },
        { name: "coal", count: 16 },
      ],
      berries: 12,
      chest: [{ name: "apple", count: 16 }],
      herd: {
        kind: "pig",
        offsets: [
          [0, 0],
          [-1, -1],
          [-2, 1],
          [1, -2],
          [-1, 3],
        ],
      },
      herdRadius: [5, 8],
      inView: true,
      learningMode: "supervised",
    },
  ],
};

const NAMES: Record<string, string> = {
  A: "a-wide-margin",
  B: "b-near-tie",
  C: "c-exploration",
};
const MEATS = [
  "cooked_beef",
  "cooked_porkchop",
  "cooked_mutton",
  "cooked_chicken",
];
const YAWS = [0, Math.PI / 2, Math.PI, (3 * Math.PI) / 2];
const COMPASS = [0, 45, 90, 135, 180, 225, 270, 315];
const IN_VIEW = [-45, -20, 0, 20, 45];
const BOUND = 48;

class Draws {
  #index = 0;
  readonly seed: string;
  constructor(seed: string) {
    this.seed = seed;
  }
  u(): number {
    const digest = createHash("sha256")
      .update(`${this.seed}:${this.#index++}`)
      .digest();
    return Number(digest.readBigUInt64BE(0)) / 2 ** 64;
  }
  choice<T>(list: readonly T[]): T {
    return list[Math.floor(this.u() * list.length)]!;
  }
  int(lo: number, hi: number): number {
    return lo + Math.floor(this.u() * (hi - lo + 1));
  }
}

/** The world direction, in degrees, that a yaw faces. Yaw 0 faces -Z. */
const facing = (yaw: number): number =>
  ((Math.atan2(-Math.cos(yaw), -Math.sin(yaw)) * 180) / Math.PI + 360) % 360;

const at = (degrees: number, radius: number): Point => {
  const radians = (degrees * Math.PI) / 180;
  return {
    x: Math.round(Math.cos(radians) * radius) + 0,
    y: 64,
    z: Math.round(Math.sin(radians) * radius) + 0,
  };
};

function generate(cls: string, seed: string) {
  const d = new Draws(seed);
  const bundle = d.choice(BUNDLES[cls]!);
  const spawnYaw = d.choice(YAWS);
  const ahead = facing(spawnYaw);

  const berryDirection = bundle.inView
    ? ahead + d.choice(IN_VIEW)
    : d.choice(COMPASS);
  const berries = at(
    berryDirection,
    bundle.inView ? d.int(4, 8) : d.int(6, 10),
  );
  // Logs lie on the far side of spawn from the berries, and the chest to one
  // side, so no two sources can crowd each other and nothing is redrawn.
  const logs = at(berryDirection + 180 + d.choice([-45, 0, 45]), d.int(9, 14));
  const chestPosition = bundle.chest
    ? at(berryDirection + d.choice([-90, 90]), d.int(3, 5))
    : null;
  const meat = bundle.chest ? d.choice(MEATS) : null;
  let herd: Point | null = null;
  if (bundle.herd && bundle.herdRadius) {
    const direction = bundle.inView
      ? ahead + d.choice(IN_VIEW)
      : d.choice(COMPASS);
    herd = at(direction, d.int(...bundle.herdRadius));
  }

  const entities =
    bundle.herd && herd
      ? bundle.herd.offsets.map(([dx, dz]) => ({
          name: bundle.herd!.kind,
          position: { x: herd!.x + dx, y: 64, z: herd!.z + dz },
        }))
      : [];
  const points = [
    berries,
    logs,
    ...(chestPosition ? [chestPosition] : []),
    ...entities.map((entity) => entity.position),
  ];
  for (const point of points)
    if (Math.abs(point.x) > BOUND || Math.abs(point.z) > BOUND)
      throw new Error("outside the exploration box: the procedure is wrong");

  const world = {
    name: `bench-${cls.toLowerCase()}2-${NAMES[cls]}-heldout`,
    seed: 1,
    startTick: 0,
    timeOfDay: 1000,
    biome: "forest",
    groundLevel: 63,
    spawn: { x: 0, y: 64, z: 0 },
    spawnYaw,
    vitals: bundle.vitals,
    inventory: bundle.inventory,
    blocks: [],
    clusters: [
      {
        name: "sweet_berry_bush",
        center: berries,
        count: bundle.berries,
        spread: 2,
      },
      { name: "oak_log", center: logs, count: 30, spread: 3 },
    ],
    entities,
    containers:
      bundle.chest && chestPosition
        ? [
            {
              position: chestPosition,
              kind: "chest",
              contents: bundle.chest.map((item) =>
                item.name === "cooked_meat" ? { ...item, name: meat! } : item,
              ),
              ownedByPerson: true,
            },
          ]
        : [],
    events: [],
  };
  return { world, bundle };
}

const [cls, seed, worldFile, planFile] = process.argv.slice(2);
if (!cls || !(cls in BUNDLES) || !seed || !worldFile || !planFile) {
  process.stderr.write(
    "usage: generate-classes.ts <A|B|C> <seed> <world.json> <plan.json>\n",
  );
  process.exit(2);
}
const { world, bundle } = generate(cls, seed);
const plan = {
  name: `r2-heldout-${cls.toLowerCase()}2-${NAMES[cls]}`,
  description: `Class ${cls}, generated from seed "${seed}" by scripts/benchmarks/generate-classes.ts as experiments/benchmarks/heldout-v2/PROCEDURE.md declares; class-defining bundle from ${bundle.source}. HELD OUT: frozen before any run; run once, as part of the operator-authorized V2 suite; nothing is tuned from it.`,
  split: "heldout",
  benchmarkClass: cls,
  world: path.relative(path.dirname(planFile), worldFile),
  config: path.relative(path.dirname(planFile), "examples/fixture.toml"),
  seeds: [201, 202, 203, 204, 205],
  conditions: [
    { id: "P0", affectMode: "off" },
    { id: "A15", affectMode: "active", interoception: "off" },
    { id: "R2rec", affectMode: "record_only", interoception: "on" },
    { id: "R2act", affectMode: "active", interoception: "on" },
  ],
  maxDecisions: 5000,
  learningMode: bundle.learningMode,
  horizons: [
    { id: "short", maxDecisions: 5000, maxExperiencedTicks: 6000 },
    { id: "medium", maxDecisions: 5000, maxExperiencedTicks: 24000 },
    { id: "long", maxDecisions: 5000, maxExperiencedTicks: 72000 },
  ],
};
for (const [file, document] of [
  [worldFile, world],
  [planFile, plan],
] as const) {
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, `${JSON.stringify(document, null, 2)}\n`);
}
process.stdout.write(
  `${JSON.stringify({ class: cls, seed, bundle: bundle.source })}\n`,
);
