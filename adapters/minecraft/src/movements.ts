import type mineflayer from "mineflayer";
import pathfinderPackage from "mineflayer-pathfinder";
import type { Position } from "#config";
import type { PhysicalGuard } from "#node-runtime";
import { HAZARD_BLOCKS } from "./registry.ts";
import { EXTRA_HOSTILE_MOBS, HOSTILE_CATEGORY } from "./classify.ts";

const { Movements } = pathfinderPackage;

type Bot = ReturnType<typeof mineflayer.createBot>;
type MovementPolicy = InstanceType<typeof pathfinderPackage.Movements>;

/** The shape mineflayer-pathfinder hands to an exclusion callback. */
interface ExclusionBlock {
  position?: { x: number; y: number; z: number };
  x?: number;
  y?: number;
  z?: number;
}

/**
 * One generated movement. `mineflayer-pathfinder` calls these Moves; the
 * fields below are the ones containment cares about. A Move's x/y/z is where
 * Person's feet end up, so the head occupies y+1.
 */
interface GeneratedMove {
  x: number;
  y: number;
  z: number;
  toBreak: { x: number; y: number; z: number }[];
  toPlace: { x: number; y: number; z: number }[];
}

/** `getNeighbors` is real but absent from the package's type declarations. */
interface NeighborSource {
  getNeighbors(node: PathNode): GeneratedMove[];
}

/** The node a move starts from. Only its block coordinates are read. */
interface PathNode {
  x: number;
  y: number;
  z: number;
}

const EXCLUSION_COST = 100;

const floor = (p: { x: number; y: number; z: number }): Position => ({
  x: Math.floor(p.x),
  y: Math.floor(p.y),
  z: Math.floor(p.z),
});

const positionOf = (block: ExclusionBlock): Position =>
  floor(
    block.position ?? {
      x: block.x ?? 0,
      y: block.y ?? 0,
      z: block.z ?? 0,
    },
  );

/**
 * Person's movement policy for mineflayer-pathfinder.
 *
 * Two mechanisms work together here and both are load-bearing.
 *
 * The exclusion callbacks make a forbidden step cost more than
 * `mineflayer-pathfinder`'s internal rejection threshold. Every movement
 * generator that consults them ends with `if (cost > 100) return`, so the move
 * is never generated rather than merely made expensive. Those callbacks are
 * also what keeps path shortcutting switched off: `postProcessPath` returns
 * early whenever `exclusionAreasStep` is non-empty, so a straight-line
 * optimisation can never be spliced across ground the search avoided. Removing
 * them would silently re-enable that.
 *
 * The neighbour filter is the authoritative part. Not every generator consults
 * the exclusion cost: `getMoveUp` never reads the block it climbs into, and
 * `getMoveParkourForward` adds the cost but has no rejection check and tests
 * the block above its landing square rather than the landing square itself. So
 * the guard is applied once more to every generated move, at the single point
 * the search takes its neighbours from. A move is dropped unless every position
 * it would make Person occupy, and every block it would break or place, is
 * permitted. This is the same rule the fixture world enforces, and it holds for
 * movement families that do not exist yet.
 */
export function createGuardedMovements(
  bot: Bot,
  readGuard: () => PhysicalGuard | null,
): MovementPolicy {
  const movements = new Movements(bot);
  movements.canDig = false;
  movements.allow1by1towers = false;
  movements.allowParkour = false;
  movements.allowSprinting = true;
  movements.canOpenDoors = false;
  movements.scafoldingBlocks = [];
  movements.maxDropDown = 2;
  movements.allowFreeMotion = false;
  for (const name of HAZARD_BLOCKS) {
    const id = bot.registry.blocksByName[name]?.id;
    if (id !== undefined) movements.blocksToAvoid.add(id);
  }

  const permitted = (position: Position): boolean =>
    readGuard()?.canEnter(position) !== false;
  const modifiable = (position: Position): boolean =>
    readGuard()?.canModify(position) !== false;

  movements.exclusionAreasStep.push((block: ExclusionBlock) =>
    permitted(positionOf(block)) ? 0 : EXCLUSION_COST,
  );
  movements.exclusionAreasBreak.push(() => EXCLUSION_COST);
  movements.exclusionAreasPlace.push(() => EXCLUSION_COST);

  // Everything the registry calls hostile, so pathfinder routes around mobs
  // this adapter would also flee from.
  for (const entity of bot.registry.entitiesArray as {
    name: string;
    category?: string;
  }[])
    if (
      entity.category === HOSTILE_CATEGORY ||
      EXTRA_HOSTILE_MOBS.has(entity.name)
    )
      movements.entitiesToAvoid.add(entity.name);

  installNeighborFilter(movements, permitted, modifiable);
  return movements;
}

/** Every block a move would make Person occupy: feet, and the head above it. */
export function occupiedBy(move: {
  x: number;
  y: number;
  z: number;
}): Position[] {
  const feet = floor(move);
  return [feet, { x: feet.x, y: feet.y + 1, z: feet.z }];
}

/**
 * The two block columns a diagonal step threads between.
 *
 * A diagonal changes x and z together, so the floored position passes through
 * `(to.x, from.z)` or `(from.x, to.z)` on the way, whichever axis crosses its
 * block boundary first. That is not something Person controls, and both are
 * positions Person occupies, so both are checked. Returns nothing for a move
 * that is not diagonal.
 */
function cornersOf(from: PathNode, to: GeneratedMove): Position[] {
  if (Math.abs(to.x - from.x) !== 1 || Math.abs(to.z - from.z) !== 1) return [];
  const low = Math.min(from.y, to.y);
  const high = Math.max(from.y, to.y) + 1;
  const corners: Position[] = [];
  for (const column of [
    { x: to.x, z: from.z },
    { x: from.x, z: to.z },
  ])
    for (let y = low; y <= high; y++)
      corners.push({ x: column.x, y, z: column.z });
  return corners;
}

/**
 * Wraps `getNeighbors` so the search never sees a move Person may not make.
 *
 * Dropping the move rather than pricing it means the A* search cannot choose it
 * at any cost, cannot reach it by replanning, and cannot rediscover it when the
 * containment policy is read again on the next search.
 *
 * A move is refused unless every block it would make Person occupy is
 * permitted: the destination's feet and head, the columns a diagonal threads
 * between, and anything it would break or place. Protected areas fail closed,
 * so a diagonal whose outcome depends on which axis crosses first is refused
 * rather than gambled on. The cost is that Person rounds the corner of a
 * protected region in two cardinal steps instead of one diagonal.
 */
function installNeighborFilter(
  movements: MovementPolicy,
  permitted: (position: Position) => boolean,
  modifiable: (position: Position) => boolean,
): void {
  const source = movements as unknown as NeighborSource;
  const generate = source.getNeighbors.bind(source);
  source.getNeighbors = (node: PathNode): GeneratedMove[] =>
    generate(node).filter(
      (move) =>
        occupiedBy(move).every(permitted) &&
        cornersOf(node, move).every(permitted) &&
        move.toBreak.every((position) => modifiable(floor(position))) &&
        move.toPlace.every((position) => modifiable(floor(position))),
    );
}
