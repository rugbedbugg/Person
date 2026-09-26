import type { Position } from "#config";
import type { ItemStack } from "#protocol";

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
  type: "spawn_hostile" | "despawn_hostile" | "break_shelter_block" | "weather";
  name?: string;
  offset?: Position;
  position?: Position;
  weather?: "clear" | "rain" | "thunder";
}

/**
 * A rule of this world that nothing in Person is told.
 *
 * Hidden mechanics exist so discovery can be tested honestly: a relation
 * Person could only learn by experiencing its consequences, and one no
 * language model could already know, because it is not Minecraft's.
 * `barren_while_weather`: while the weather is `weather`, the listed blocks
 * break when dug but drop nothing.
 */
export interface FixtureHiddenRule {
  kind: "barren_while_weather";
  weather: "clear" | "rain" | "thunder";
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
