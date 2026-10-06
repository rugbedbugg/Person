import type { ItemStack, Observation } from "#protocol";

/**
 * The Minecraft observation payload: what a Minecraft observation reports, as
 * Person perceives it (ADR 0002, ADR 0025). Owned by the Minecraft environment
 * profile and validated against `schemas/observation-payload.schema.json`;
 * the core protocol carries it in `Observation.payload` without looking inside.
 */

/**
 * Where something is, as Person perceives it.
 *
 * Relative to Person and qualitative, because a world coordinate is a fact
 * about the server rather than a fact about anyone's experience. Bearings are
 * relative to where Person is facing: Person has no compass, and a heading in
 * degrees would be the coordinate problem in another notation.
 */
export interface RelativeLocation {
  bearing:
    | "ahead"
    | "ahead_left"
    | "ahead_right"
    | "left"
    | "right"
    | "behind_left"
    | "behind_right"
    | "behind";
  elevation: "above" | "level" | "below";
  rangeBand: "reach" | "near" | "mid" | "far";
  /** Estimated straight-line distance. Coarser the further away it is. */
  distance: number;
  /**
   * Whether Person is looking at this, or merely aware of it.
   *
   * Everything reported is perceptible. Only a `central` percept was close
   * enough to the view axis to be identified: a `peripheral` one carries a
   * bearing and a coarse category and withholds precise identity, because
   * recognising what a thing is happens near the middle of the field.
   */
  detail: "central" | "peripheral";
}

export interface EntityRecord extends RelativeLocation {
  /** The species, when Person is looking straight enough at it to tell. */
  name?: string;
  /**
   * Whose it is, and whether the runtime would let Person hunt it. Like the
   * species, these are present only on a `central` percept: a nametag or a
   * collar is read off a thing Person is looking at, and the hunting verdict
   * is derived from them.
   */
  named?: boolean;
  tamed?: boolean;
  protectedTarget?: boolean;
  /**
   * The account name on the nameplate above a player's head.
   *
   * Optional rather than required: a mob has no account name, and an
   * observation recorded before this existed is still a valid observation. The
   * account UUID is deliberately not reported, because it is a protocol
   * identifier rather than anything Person could perceive.
   */
  username?: string;
}

export interface ResourceRecord extends RelativeLocation {
  kind: "wood" | "stone" | "coal" | "plant_food" | "dirt" | "other";
  /** The exact block, when it was recognised rather than merely noticed. */
  name?: string;
  harvestPermitted: boolean;
}

export interface ContainerRecord extends RelativeLocation {
  kind: "chest" | "barrel" | "furnace" | "shulker" | "other";
  provenance: "owned" | "existing";
  storageId: string | null;
}

export interface WorkstationRecord extends RelativeLocation {
  kind: "crafting_table" | "furnace" | "anvil" | "other";
  provenance: "owned" | "existing";
  /**
   * Where this came from. Workstations are read out of Person's own placement
   * ledger rather than seen, so they are reported even when Person is facing
   * the other way, and they are the one channel in `nearby` that is not
   * current perception. Marked so it cannot be mistaken for one, and named
   * for the runtime record it is, so it cannot be mistaken for something
   * Person recalled either.
   */
  source: "placement_ledger";
}

export interface HazardRecord extends RelativeLocation {
  kind:
    | "lava"
    | "fire"
    | "water"
    | "cactus"
    | "magma"
    | "fall"
    | "suffocation"
    | "other";
}

export interface OwnedStorageView {
  storageId: string;
  contents: ItemStack[];
}

export interface MinecraftObservationPayload {
  vitals: {
    health: number;
    food: number;
    /** Bubbles, 0 to 10 (ADR 0014). */
    breath: number;
    armor: number;
    statusEffects: {
      name: string;
      amplifier: number;
      remainingTicks: number;
    }[];
    alive: boolean;
  };
  environment: {
    dimension: "overworld" | "nether" | "end";
    dayPhase: "dawn" | "day" | "dusk" | "night";
    timeOfDay: number;
    weather: "clear" | "rain" | "thunder";
    lightLevel: number;
    biome: string;
  };
  inventory: {
    items: ItemStack[];
    categories: Record<string, number>;
    freeSlots: number;
  };
  permissions: {
    harvest: boolean;
    mine: boolean;
    build: boolean;
    huntPassive: boolean;
    depositOwned: boolean;
    withdrawOwned: boolean;
    withdrawExisting: boolean;
    craft: boolean;
    consume: boolean;
  };
  affordances: {
    diggableGround: boolean;
    shelterSite: boolean;
    storageSite: boolean;
  };
  nearby: {
    resources: ResourceRecord[];
    hostiles: EntityRecord[];
    passiveAnimals: EntityRecord[];
    players: EntityRecord[];
    containers: ContainerRecord[];
    workstations: WorkstationRecord[];
    hazards: HazardRecord[];
  };
  home: {
    activeHome: { homeId: string } | null;
    shelterState: "none" | "partial" | "complete" | "breached" | "unknown";
    ownedStorage: OwnedStorageView[];
    bedKnown: boolean;
    foodReserve: number;
    fuelReserve: number;
  };
  navigation: {
    routeStatus: "idle" | "ok" | "blocked" | "unknown";
    pathRisk: "low" | "moderate" | "high";
    stuckState: "free" | "slow" | "stuck";
    returnPathKnown: boolean;
  };
}

/** An observation in the Minecraft environment. */
export type MinecraftObservation = Observation<MinecraftObservationPayload>;
