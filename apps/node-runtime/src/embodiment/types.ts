import type { ItemStack, Position } from "#protocol";
import type { GazeDirection } from "./gaze.ts";

/**
 * The embodiment port.
 *
 * This is the whole surface a skill may touch. Two implementations exist: the
 * Mineflayer adapter that drives a real Minecraft client, and the deterministic
 * fixture world used by the test suite. Skills are written once against this
 * interface, so a fixture test exercises the same skill code that runs against
 * Minecraft rather than a parallel imitation of it.
 *
 * Nothing here is reachable from the cognition process. Python proposes a
 * skill; only the runtime holds an Embodiment.
 */

export type BlockKind =
  | "air"
  | "wood"
  | "leaves"
  | "stone"
  | "coal_ore"
  | "dirt"
  | "grass"
  | "plant_food"
  | "water"
  | "lava"
  | "fire"
  | "cactus"
  | "chest"
  | "furnace"
  | "crafting_table"
  | "planks"
  | "cobblestone"
  | "bed"
  | "other";

export interface BlockView {
  position: Position;
  name: string;
  kind: BlockKind;
  solid: boolean;
  hazard: boolean;
  /** True when this block was placed by Person during this world's lifetime. */
  ownedByPerson: boolean;
}

export interface EntityView {
  entityId: number;
  /**
   * The species name, or literally "player" for a person.
   *
   * Minecraft reports every player entity under the same name, so this field
   * says what something is and never who it is. Identity lives in `username`
   * and `uuid`.
   */
  name: string;
  /** The account name, when the client knows one. Players only. */
  username: string | null;
  /** The server's stable entity UUID, when one was sent. */
  uuid: string | null;
  position: Position;
  distance: number;
  /** Attacks without provocation. */
  hostile: boolean;
  /**
   * Harmless until provoked, lethal afterwards: wolves, polar bears, bees,
   * iron golems. Treated as a threat only once Person has taken damage, which
   * is the only honest signal available that one has turned on you.
   */
  neutral: boolean;
  passive: boolean;
  player: boolean;
  villager: boolean;
  named: boolean;
  tamed: boolean;
  ranged: boolean;
}

export interface ContainerView {
  position: Position;
  kind: "chest" | "barrel" | "furnace" | "shulker" | "other";
  contents: ItemStack[];
  /** Set when Person placed this container itself. */
  storageId: string | null;
}

export interface StatusEffectView {
  name: string;
  amplifier: number;
  remainingTicks: number;
}

export interface WorldSnapshot {
  tick: number;
  timeOfDay: number;
  weather: "clear" | "rain" | "thunder";
  dimension: "overworld" | "nether" | "end";
  biome: string;
  lightLevel: number;
  position: Position;
  /**
   * Where Person is looking, in radians, using Mineflayer's convention: the
   * view direction is `(-sin(yaw)cos(pitch), sin(pitch), -cos(yaw)cos(pitch))`.
   *
   * This is privileged motor state. The perception layer reads it to decide
   * what Person can see; it never crosses to cognition, because knowing your
   * own exact heading to the radian is not something a body reports to a mind.
   */
  yaw: number;
  pitch: number;
  health: number;
  food: number;
  saturation: number;
  air: number;
  armor: number;
  alive: boolean;
  statusEffects: StatusEffectView[];
  inventory: ItemStack[];
  freeSlots: number;
  entities: EntityView[];
  containers: ContainerView[];
  /** Blocks of interest in range, already filtered to what the runtime can see. */
  resources: BlockView[];
  hazards: BlockView[];
  stuck: boolean;
  /**
   * Whether there is solid, diggable ground beside Person right now.
   *
   * The safety kernel needs this to choose between running and digging in. On
   * flat open terrain there is no wall to tunnel into, and sending Person to
   * dig a refuge that cannot exist wastes the one chance it had to run.
   */
  diggableGround: boolean;
  lastSafePosition: Position | null;
  connected: boolean;
  /** True when Person lost health recently enough for a neutral mob to count. */
  recentlyDamaged: boolean;
  /** World tick of the last health loss, or null if none observed. */
  lastDamageTick: number | null;
}

export interface FindBlocksQuery {
  kinds: BlockKind[];
  maxDistance: number;
  limit: number;
}

export interface MoveOptions {
  range?: number;
  maxTicks?: number;
}

export interface CraftResult {
  produced: ItemStack[];
  consumed: ItemStack[];
}

export class EmbodimentError extends Error {
  readonly reason: string;
  /**
   * What an operator should try next.
   *
   * The first live connection is the hardest one to diagnose, because nothing
   * downstream has run yet. A reason code tells a program what happened; the
   * hint tells a person what to do about it.
   */
  readonly hint: string | null;
  constructor(reason: string, message?: string, hint?: string) {
    super(message ?? reason);
    this.name = "EmbodimentError";
    this.reason = reason;
    this.hint = hint ?? null;
  }
}

export class DisconnectedError extends EmbodimentError {
  constructor(message = "The Minecraft connection was lost") {
    super("disconnected", message);
    this.name = "DisconnectedError";
  }
}

/**
 * A guard the runtime installs before anything physical happens. The safety
 * kernel owns it; an embodiment must call it and must refuse the action when it
 * throws or returns false. This is what makes protected-area enforcement hold
 * during navigation and replanning rather than only at proposal time.
 */
export interface PhysicalGuard {
  canEnter(position: Position): boolean;
  canModify(position: Position): boolean;
  canTargetEntity(entity: EntityView): boolean;
}

export interface Embodiment {
  readonly kind: "fixture" | "mineflayer";
  /** Installed by the runtime before connect(). Never supplied by cognition. */
  setGuard(guard: PhysicalGuard): void;
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  snapshot(): WorldSnapshot;
  blockAt(position: Position): BlockView | null;
  findBlocks(query: FindBlocksQuery): BlockView[];
  findEntities(): EntityView[];
  containerAt(position: Position): ContainerView | null;
  /**
   * Reads a container's live contents, opening it if necessary.
   *
   * `containerAt` returns a cached view, which is empty until something has
   * been transferred. Deciding what to withdraw needs the real contents, and
   * against a real server the only way to learn them is to open the window.
   */
  inspectContainer(position: Position): Promise<ContainerView | null>;
  moveTo(position: Position, options?: MoveOptions): Promise<void>;
  dig(position: Position): Promise<ItemStack[]>;
  place(position: Position, item: string): Promise<void>;
  craft(
    item: string,
    times: number,
    tablePosition: Position | null,
  ): Promise<CraftResult>;
  smelt(
    input: string,
    times: number,
    furnacePosition: Position,
  ): Promise<CraftResult>;
  consume(item: string): Promise<void>;
  attack(entityId: number): Promise<void>;
  deposit(position: Position, items: ItemStack[]): Promise<ItemStack[]>;
  withdraw(position: Position, items: ItemStack[]): Promise<ItemStack[]>;
  /**
   * Points Person's senses one bounded step in a direction.
   *
   * The only way anything above the body changes where Person is looking. It
   * takes a word rather than an angle, so no caller needs an absolute heading
   * to aim, and cognition could not issue one if it tried: the direction is
   * the whole vocabulary.
   *
   * Locomotion also turns Person, and that is not this. Walking somewhere
   * leaves Person facing along its route as a side effect; calling this is
   * Person deciding to look.
   */
  look(direction: GazeDirection): Promise<void>;
  waitTicks(ticks: number): Promise<void>;
  /** Registers a Person-placed container so its provenance is tracked. */
  registerOwnedStorage(position: Position, storageId: string): void;
}
