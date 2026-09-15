import {
  blockLine,
  contains,
  type Box,
  type PersonConfig,
  type Position,
} from "#config";

/**
 * Protected areas override every other permission.
 *
 * Enforcement happens at four places: proposal validation, route selection,
 * skill execution and each individual destructive or building interaction.
 * Validating a destination once is not enough, because replanning can walk a
 * route through a region the destination check never looked at.
 */
export class ProtectedAreas {
  readonly exploration: Box;
  readonly protectedBoxes: readonly Box[];
  readonly resourceAreas: readonly Box[];

  constructor(config: PersonConfig) {
    this.exploration = config.world.exploration;
    this.protectedBoxes = config.world.protectedAreas;
    this.resourceAreas = config.world.resourceAreas;
  }

  /** A position Person may occupy or path through. */
  permitted(position: Position): boolean {
    if (!contains(this.exploration, position)) return false;
    return !this.protectedBoxes.some((box) => contains(box, position));
  }

  /** A position whose blocks Person may harvest or mine. */
  harvestable(position: Position): boolean {
    return (
      this.permitted(position) &&
      this.resourceAreas.some((box) => contains(box, position))
    );
  }

  /** Every block on the straight route, so a path cannot clip a protected corner. */
  routePermitted(from: Position, to: Position): boolean {
    return blockLine(from, to).every((step) => this.permitted(step));
  }

  firstViolation(from: Position, to: Position): Position | null {
    return blockLine(from, to).find((step) => !this.permitted(step)) ?? null;
  }
}
