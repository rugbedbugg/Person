import type { ItemStack } from "#protocol";
import { type Position } from "#minecraft";

export interface FixtureBlock {
  position: Position;
  name: string;
}

export interface FixtureCluster {
  name: string;
  center: Position;
  count: number;
  spread: number;
}

export interface FixtureEntity {
  name: string;
  position: Position;
  named?: boolean;
  tamed?: boolean;
  player?: boolean;
  villager?: boolean;
  health?: number;
}

export interface FixtureContainer {
  position: Position;
  kind: "chest" | "barrel" | "furnace" | "shulker" | "other";
  contents: ItemStack[];
  ownedByPerson?: boolean;
}

export interface FixtureEvent {
  atTick: number;
  type:
    | "spawn_hostile"
    | "despawn_hostile"
    | "break_shelter_block"
    | "weather"
    | "unrest"
    | "rest_stops_helping"
    | "withdrawal_stops_helping"
    | "remove_items"
    | "set_vitals";
  name?: string;
  offset?: Position;
  position?: Position;
  weather?: "clear" | "rain" | "thunder";
  /** `remove_items`: what the world takes away, recreating a problem. */
  items?: string[];
  /** `set_vitals`: holds a test's context steady between episodes. */
  vitals?: { health?: number; food?: number; saturation?: number };
}

/**
 * A rule of this world that nothing in Person is told.
 *
 * `barren_until_withdrawn` (test machinery for ADR 0022, C5): after an
 * `unrest` event the listed blocks drop nothing until the body has taken
 * something out of a container Person owns. What was taken does not matter
 * and never helps by itself; the relation is the cure. A
 * `withdrawal_stops_helping` regime change makes withdrawing useless.
 *
 * `barren_until_rested` (test machinery for ADR 0022): after an `unrest`
 * event the listed blocks drop nothing until the body has waited `restTicks`
 * in all (default 100), unless a `rest_stops_helping` regime change has made waiting useless. The
 * world creates the problem; it never supplies the solution.
 *
 * Hidden mechanics exist so discovery can be tested honestly: a relation
 * Person could only learn by experiencing its consequences, and one no
 * language model could already know, because it is not Minecraft's.
 * `barren_while_weather`: while the weather is `weather`, the listed blocks
 * break when dug but drop nothing.
 */
export interface FixtureHiddenRule {
  kind:
    "barren_while_weather" | "barren_until_rested" | "barren_until_withdrawn";
  weather?: "clear" | "rain" | "thunder";
  /** `barren_until_rested`: how long the body must have waited. */
  restTicks?: number;
  blocks: string[];
}

export interface FixtureWorldDefinition {
  name: string;
  seed: number;
  startTick: number;
  timeOfDay: number;
  biome: string;
  groundLevel: number;
  spawn: Position;
  /**
   * Which way Person is facing when the world starts, in radians.
   *
   * Perception depends on facing, so a spawn heading is part of the scenario
   * rather than an implementation detail. Zero faces negative Z, matching
   * Mineflayer's convention.
   */
  spawnYaw?: number;
  vitals: {
    health: number;
    food: number;
    saturation: number;
    air: number;
    armor: number;
  };
  inventory: ItemStack[];
  blocks: FixtureBlock[];
  clusters: FixtureCluster[];
  entities: FixtureEntity[];
  containers: FixtureContainer[];
  events: FixtureEvent[];
  hiddenRules?: FixtureHiddenRule[];
}

export const DEFAULT_DEFINITION: FixtureWorldDefinition = {
  name: "empty",
  seed: 1,
  startTick: 0,
  timeOfDay: 1000,
  biome: "forest",
  groundLevel: 63,
  spawn: { x: 0, y: 64, z: 0 },
  spawnYaw: 0,
  vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
  inventory: [],
  blocks: [],
  clusters: [],
  entities: [],
  containers: [],
  events: [],
};
