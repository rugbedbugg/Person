/**
 * Generates a class D (setback and recovery) benchmark world from a declared
 * seed, exactly as `experiments/benchmarks/heldout-d2/PROCEDURE.md` says.
 *
 *   node scripts/benchmarks/generate-setback.ts <seed> <world.json> <plan.json>
 *
 * Deterministic: the same seed always writes the same bytes. It never runs
 * anything; freezing and running are separate, deliberate steps.
 */
import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

type Point = { x: number; y: number; z: number };

const DIRECTIONS: [number, number][] = [
  [1, 0],
  [1, 1],
  [0, 1],
  [-1, 1],
  [-1, 0],
  [-1, -1],
  [0, -1],
  [1, -1],
];
const BOUND = 48;
const ATTEMPTS = 100;

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
  at(radius: () => number): Point {
    const [dx, dz] = this.choice(DIRECTIONS);
    const r = radius();
    const length = Math.hypot(dx, dz);
    return {
      x: Math.round((dx * r) / length) + 0,
      y: 64,
      z: Math.round((dz * r) / length) + 0,
    };
  }
}

class Invalid extends Error {}

const gap = (a: Point, b: Point): number => Math.hypot(a.x - b.x, a.z - b.z);
const inside = (p: Point): boolean =>
  Math.abs(p.x) <= BOUND && Math.abs(p.z) <= BOUND;

function redraw(make: () => Point, ok: (p: Point) => boolean): Point {
  for (let attempt = 0; attempt < ATTEMPTS; attempt++) {
    const point = make();
    if (ok(point)) return point;
  }
  throw new Invalid("redraw limit reached");
}

function generate(seed: string) {
  const d = new Draws(seed);
  const spawnYaw = d.choice([0, Math.PI / 2, Math.PI, (3 * Math.PI) / 2]);
  const food = d.int(14, 16);
  const berries = d.at(() => d.int(6, 10));
  const logs = redraw(
    () => d.at(() => d.int(9, 14)),
    (p) => gap(p, berries) > 6,
  );
  const chest = redraw(
    () => d.at(() => d.int(3, 5)),
    (p) => gap(p, berries) > 3 && gap(p, logs) > 3,
  );
  const bread = 8 * d.int(4, 8);
  const meat = d.choice([
    "cooked_beef",
    "cooked_porkchop",
    "cooked_mutton",
    "cooked_chicken",
  ]);
  const meatCount = 8 * d.int(2, 4);
  const material = d.choice([
    { name: "oak_planks", count: 64 },
    { name: "oak_log", count: 40 },
  ]);
  const hostile = d.choice(["zombie", "skeleton"]);
  const spawnTick = 200 * d.int(15, 35);
  const offset = d.at(() => d.int(4, 9));
  const lasts = 200 * d.int(3, 5);

  for (const point of [berries, logs, chest, offset])
    if (!inside(point)) throw new Invalid("outside the exploration box");

  return {
    name: "bench-d2-setback-heldout",
    seed: 1,
    startTick: 0,
    timeOfDay: 1000,
    biome: "forest",
    groundLevel: 63,
    spawn: { x: 0, y: 64, z: 0 },
    spawnYaw,
    vitals: { health: 20, food, saturation: 2, air: 300, armor: 0 },
    inventory: [{ name: "stone_pickaxe", count: 1 }, material],
    blocks: [],
    clusters: [
      { name: "sweet_berry_bush", center: berries, count: 12, spread: 2 },
      { name: "oak_log", center: logs, count: 30, spread: 3 },
    ],
    entities: [],
    containers: [
      {
        position: chest,
        kind: "chest",
        contents: [
          { name: "bread", count: bread },
          { name: meat, count: meatCount },
        ],
        ownedByPerson: true,
      },
    ],
    events: [
      {
        atTick: spawnTick,
        type: "spawn_hostile",
        name: hostile,
        offset: { x: offset.x, y: 0, z: offset.z },
      },
      { atTick: spawnTick + lasts, type: "despawn_hostile" },
    ],
  };
}

const [seed, worldFile, planFile] = process.argv.slice(2);
if (!seed || !worldFile || !planFile) {
  process.stderr.write(
    "usage: generate-setback.ts <seed> <world.json> <plan.json>\n",
  );
  process.exit(2);
}

let used = seed;
let world: ReturnType<typeof generate> | null = null;
for (let retry = 0; world === null; retry++) {
  used = retry === 0 ? seed : `${seed}-r${retry}`;
  try {
    world = generate(used);
  } catch (error) {
    if (!(error instanceof Invalid)) throw error;
  }
}

const plan = {
  name: "r2-heldout-d2-setback",
  description: `Class D, setback and recovery, generated from seed "${used}" by scripts/benchmarks/generate-setback.ts as experiments/benchmarks/heldout-d2/PROCEDURE.md declares. Replaces the INVALID held-out D. HELD OUT: frozen before any run; run once, as an operator-authorized evaluation; nothing is tuned from it.`,
  split: "heldout",
  benchmarkClass: "D",
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
  learningMode: "off",
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
process.stdout.write(`seed used: ${used}\n`);
