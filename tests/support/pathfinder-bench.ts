import type mineflayer from "mineflayer";
import pathfinderPackage from "mineflayer-pathfinder";
// The package root exports only pathfinder/Movements/goals. The search itself
// is what has to be exercised here, so these two come from the package's lib
// directory. Test-only: production never reaches past the package root.
import AStarSearch from "mineflayer-pathfinder/lib/astar.js";
import MoveNode from "mineflayer-pathfinder/lib/move.js";
import registryLoader from "prismarine-registry";
import blockLoader from "prismarine-block";
import vec3Package from "vec3";
import { contains, type Box, type Position } from "#config";
import type { PhysicalGuard } from "#node-runtime";
import { createGuardedMovements } from "#minecraft-adapter";

const { Vec3 } = vec3Package;
const { goals } = pathfinderPackage;

/**
 * Runs the real mineflayer-pathfinder search over a synthetic 1.16.1 world.
 *
 * Person's containment claim is a claim about what the path search will and
 * will not generate, and a stubbed `goto` says nothing about that. This builds
 * a world the real `Movements` implementation can read, hands it the same
 * configuration the live adapter installs, and runs the same A* the live body
 * runs. It is deterministic and offline: it proves search behaviour, not
 * Minecraft behaviour, and must never be described as live validation.
 */

const registry = registryLoader("1.16.1");
const Block = blockLoader(registry as never);

export const BLOCKS = {
  AIR: registry.blocksByName.air?.defaultState ?? 0,
  STONE: registry.blocksByName.stone?.defaultState ?? 1,
  LADDER: registry.blocksByName.ladder?.defaultState ?? 0,
  WATER: registry.blocksByName.water?.defaultState ?? 0,
};

/** Ground surface; Person's feet stand at GROUND + 1. */
export const GROUND = 63;
export const FEET = GROUND + 1;

type Bot = ReturnType<typeof mineflayer.createBot>;
type MovementPolicy = ReturnType<typeof createGuardedMovements>;

const key = (x: number, y: number, z: number): string => `${x},${y},${z}`;

export interface BenchOptions {
  /** Open area. Outside it, and above the ceiling, the world is solid. */
  bounds: { minX: number; maxX: number; minZ: number; maxZ: number };
  ceiling?: number;
  overrides?: [Position, number][];
}

export interface SearchOutcome {
  status: string;
  /** Feet position of each step the search chose. */
  path: Position[];
}

/**
 * The slice of a Mineflayer bot the path search reads. Everything here is
 * consulted by `Movements`; the search touches nothing else on the bot.
 */
function benchBot(read: (position: Position) => number, at: Position): Bot {
  const cache = new Map<string, unknown>();
  return {
    registry,
    version: "1.16.1",
    game: { minY: 0 },
    entity: { position: new Vec3(at.x, at.y, at.z) },
    entities: {},
    inventory: { items: () => [], slots: [] },
    pathfinder: { bestHarvestTool: () => null },
    blockAt(position: { x: number; y: number; z: number }) {
      const k = key(position.x, position.y, position.z);
      const hit = cache.get(k);
      if (hit) return hit;
      const block = Block.fromStateId(
        read({ x: position.x, y: position.y, z: position.z }),
        0,
      );
      (block as { position: unknown }).position = new Vec3(
        position.x,
        position.y,
        position.z,
      );
      cache.set(k, block);
      return block;
    },
  } as unknown as Bot;
}

export interface Bench {
  setBlock: (position: Position, stateId: number) => void;
  path: (
    from: Position,
    to: Position,
    guard: PhysicalGuard | null,
    tune?: (movements: MovementPolicy) => void,
  ) => SearchOutcome;
}

export function bench(options: BenchOptions): Bench {
  const { bounds } = options;
  const ceiling = options.ceiling ?? GROUND + 6;
  const overrides = new Map<string, number>();
  for (const [position, state] of options.overrides ?? [])
    overrides.set(key(position.x, position.y, position.z), state);

  const read = (p: Position): number => {
    const override = overrides.get(key(p.x, p.y, p.z));
    if (override !== undefined) return override;
    if (p.y <= GROUND || p.y > ceiling) return BLOCKS.STONE;
    if (p.x < bounds.minX || p.x > bounds.maxX) return BLOCKS.STONE;
    if (p.z < bounds.minZ || p.z > bounds.maxZ) return BLOCKS.STONE;
    return BLOCKS.AIR;
  };

  return {
    setBlock(position, stateId) {
      overrides.set(key(position.x, position.y, position.z), stateId);
    },
    path(from, to, guard, tune) {
      const bot = benchBot(read, from);
      const movements = createGuardedMovements(bot, () => guard);
      tune?.(movements);
      const start = new MoveNode(from.x, from.y, from.z, 0, 0);
      const search = new AStarSearch(
        start,
        movements,
        new goals.GoalBlock(to.x, to.y, to.z),
        8000,
        8000,
        -1,
      );
      const result = search.compute() as {
        status: string;
        path: { x: number; y: number; z: number }[];
      };
      return {
        status: result.status,
        path: result.path.map((move) => ({
          x: Math.floor(move.x),
          y: Math.floor(move.y),
          z: Math.floor(move.z),
        })),
      };
    },
  };
}

/** A guard that refuses every position inside any of the given boxes. */
export function boxGuard(boxes: Box[]): PhysicalGuard {
  const forbidden = (position: Position): boolean =>
    boxes.some((box) => contains(box, position));
  return {
    canEnter: (position) => !forbidden(position),
    canModify: (position) => !forbidden(position),
    canTargetEntity: () => true,
  };
}

/**
 * Every position a path makes Person occupy: the feet block of each step and
 * the head block above it.
 */
export function occupied(path: Position[]): Position[] {
  return path.flatMap((step) => [step, { ...step, y: step.y + 1 }]);
}

/** Positions on the path that the guard refuses. */
export function trespasses(path: Position[], guard: PhysicalGuard): Position[] {
  return occupied(path).filter((position) => !guard.canEnter(position));
}

/**
 * Corner columns a diagonal step would thread between, where the guard refuses
 * one of them.
 *
 * A diagonal from A to B changes x and z together, so the floored position
 * passes through `(B.x, A.z)` or `(A.x, B.z)` on the way, whichever axis
 * crosses its block boundary first. That is a block Person occupies, so a
 * forbidden one is a containment question rather than a geometric aside.
 */
export function cornerTrespasses(
  from: Position,
  path: Position[],
  guard: PhysicalGuard,
): Position[] {
  const steps = [from, ...path];
  const bad: Position[] = [];
  for (let i = 1; i < steps.length; i++) {
    const a = steps[i - 1];
    const b = steps[i];
    if (!a || !b) continue;
    if (Math.abs(b.x - a.x) !== 1 || Math.abs(b.z - a.z) !== 1) continue;
    const low = Math.min(a.y, b.y);
    const high = Math.max(a.y, b.y) + 1;
    for (const corner of [
      { x: b.x, z: a.z },
      { x: a.x, z: b.z },
    ])
      for (let y = low; y <= high; y++) {
        const position = { x: corner.x, y, z: corner.z };
        if (!guard.canEnter(position)) bad.push(position);
      }
  }
  return bad;
}
