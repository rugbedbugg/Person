/**
 * Declarations for the two mineflayer-pathfinder internals the containment
 * bench needs. The package root exports only pathfinder/Movements/goals, but
 * the search itself is exactly what has to be exercised: a test that stubs the
 * search proves nothing about which paths Person can generate.
 *
 * Test-only. Production code never imports past the package root.
 */

declare module "mineflayer-pathfinder/lib/move.js" {
  export default class Move {
    constructor(
      x: number,
      y: number,
      z: number,
      remainingBlocks: number,
      cost: number,
      toBreak?: unknown[],
      toPlace?: unknown[],
      parkour?: boolean,
    );
    x: number;
    y: number;
    z: number;
    hash: string;
  }
}

declare module "mineflayer-pathfinder/lib/astar.js" {
  export default class AStar {
    constructor(
      start: unknown,
      movements: unknown,
      goal: unknown,
      timeout: number,
      tickTimeout?: number,
      searchRadius?: number,
    );
    compute(): {
      status: "success" | "partial" | "timeout" | "noPath";
      cost: number;
      path: { x: number; y: number; z: number }[];
    };
  }
}
