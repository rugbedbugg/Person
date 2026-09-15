/**
 * A stand-in for a Mineflayer bot that mirrors the real API shapes.
 *
 * Every shape here was checked against the installed mineflayer 4.39.0 source
 * rather than against what the adapter wished were true. In particular:
 *
 * - `entity.metadata` is a sparse object keyed by metadata index, not an array
 *   (`parseMetadata` in lib/plugins/entities.js), and index 2 carries the
 *   optional custom name in 1.16.1;
 * - `entity.kind` is the minecraft-data entity category;
 * - players report `type: "player"` and `name: "player"`, with `username` set;
 * - `bot.game.dimension` has already had its `minecraft:` prefix stripped;
 * - `bot.oxygenLevel` is air supply divided by fifteen, so zero to twenty;
 * - `bot.inventory.emptySlotCount()` exists and is authoritative;
 * - `recipesFor` filters by both table availability and current inventory.
 *
 * Block, item and entity data come from the real `minecraft-data` for 1.16.1
 * and recipes from the real `prismarine-recipe`, so a test that passes here is
 * checking the adapter against Minecraft's own tables rather than against a
 * second copy of the adapter's assumptions.
 */
import { EventEmitter } from "node:events";
import { createRequire } from "node:module";
import vec3Package from "vec3";
import type { Position } from "#config";

const require = createRequire(import.meta.url);
const { Vec3 } = vec3Package;

export const MINECRAFT_VERSION = "1.16.1";
export const registry = require("minecraft-data")(MINECRAFT_VERSION);
const Recipe = require("prismarine-recipe")(registry).Recipe;

export interface DoubleEntity {
  id: number;
  name: string;
  type?: string;
  kind?: string;
  username?: string;
  uuid?: string;
  position: InstanceType<typeof Vec3>;
  metadata?: Record<string, unknown>;
  effects?: Record<string, unknown>;
}

export interface DoubleOptions {
  position?: Position;
  health?: number;
  food?: number;
  saturation?: number;
  oxygenLevel?: number;
  gameMode?: string;
  difficulty?: string;
  dimension?: string;
  /** A 1.16.1 biome name. Resolved through the real minecraft-data table. */
  biome?: string;
  doDaylightCycle?: boolean;
  timeOfDay?: number;
  age?: number;
  inventory?: { name: string; count: number }[];
  blocks?: Record<string, string>;
  /** Ticks to withhold chunk data after spawn, to exercise readiness. */
  chunkDelayTicks?: number;
  emptySlots?: number;
  containers?: Record<string, { name: string; count: number }[]>;
  /**
   * Model `minecraft-protocol`'s socket shutdown, close timer included.
   *
   * Off by default, because a leaked thirty-second timer would hang the whole
   * suite rather than fail one test. The lifecycle test turns it on.
   */
  emulateSocket?: boolean;
  /** How long the server takes to close after the client ends. */
  socketCloseDelayMs?: number;
}

/** minecraft-protocol/src/client.js: `const closeTimeout = 30 * 1000`. */
export const CLOSE_TIMEOUT_MS = 30_000;

const key = (p: { x: number; y: number; z: number }): string =>
  `${Math.floor(p.x)},${Math.floor(p.y)},${Math.floor(p.z)}`;

/**
 * The biome every block in this world sits in, as prismarine-block reports it.
 *
 * Faithfully wrong on purpose. `prismarine-block` constructs its Biome class
 * from `registry.version` rather than the registry, so `prismarine-biome`
 * never finds a biome table and hands back its placeholder: the correct
 * numeric id, and an empty name. A double that returned `{ name: "forest" }`
 * would be testing a library that does not exist, which is exactly how
 * `biome: "unknown"` survived every test and reached the first live run.
 */
function makeBiome(name: string): { id: number; name: string } {
  const id = registry.biomesByName[name]?.id;
  if (id === undefined) throw new Error(`No such 1.16.1 biome: ${name}`);
  return { id, name: "" };
}

/** A block shaped like prismarine-block, with the fields the adapter reads. */
function makeBlock(
  name: string,
  position: InstanceType<typeof Vec3>,
  biome: { id: number; name: string },
): Record<string, unknown> {
  const data = registry.blocksByName[name];
  return {
    name,
    type: data?.id ?? 0,
    position,
    boundingBox:
      data && data.boundingBox
        ? data.boundingBox
        : name === "air"
          ? "empty"
          : "block",
    transparent: Boolean(data?.transparent),
    light: 0,
    skyLight: 15,
    biome,
    getProperties: () => ({}),
  };
}

export class MineflayerDouble extends EventEmitter {
  readonly registry = registry;
  username = "PersonAda";
  /** Set to null to model a chunk whose biome data never arrived. */
  biome: { id: number; name: string } | null;
  entity: DoubleEntity;
  entities: Record<string, DoubleEntity> = {};
  health: number;
  food: number;
  foodSaturation: number;
  oxygenLevel: number;
  isRaining = false;
  thunderState = 0;
  game: Record<string, unknown>;
  time: Record<string, unknown>;
  inventory: {
    items: () => { name: string; count: number; type: number }[];
    emptySlotCount: () => number;
    slots: ({ name: string } | null)[];
  };
  heldItem: { name: string } | null = null;
  pathfinder: Record<string, unknown>;
  readonly calls: string[] = [];
  #blocks = new Map<string, string>();
  #items = new Map<string, number>();
  #containers = new Map<string, Map<string, number>>();
  #chunksReadyAt: number;
  #emptySlots: number;
  #armorSlots: ({ name: string } | null)[] = [];
  #nextEntityId = 100;
  /** Set by a test to make the next container transfer fail like mineflayer. */
  failNextTransfer: string | null = null;
  /** Present only when socket emulation is on, mirroring `bot._client`. */
  _client?: {
    ended: boolean;
    closeTimer?: NodeJS.Timeout;
    socket: { destroy: () => void };
  };
  #socketCloseDelayMs = 0;

  constructor(options: DoubleOptions = {}) {
    super();
    const start = options.position ?? { x: 0, y: 64, z: 0 };
    this.biome = makeBiome(options.biome ?? "forest");
    this.entity = {
      id: 1,
      name: "player",
      type: "player",
      username: this.username,
      position: new Vec3(start.x + 0.5, start.y, start.z + 0.5),
      metadata: {},
      effects: {},
    };
    this.entities = { 1: this.entity };
    this.health = options.health ?? 20;
    this.food = options.food ?? 20;
    this.foodSaturation = options.saturation ?? 5;
    this.oxygenLevel = options.oxygenLevel ?? 20;
    this.game = {
      gameMode: options.gameMode ?? "survival",
      difficulty: options.difficulty ?? "peaceful",
      dimension: options.dimension ?? "overworld",
      minY: 0,
      height: 256,
    };
    this.time = {
      age: options.age ?? 1000,
      time: options.timeOfDay ?? 1000,
      timeOfDay: options.timeOfDay ?? 1000,
      doDaylightCycle: options.doDaylightCycle ?? true,
    };
    for (const [position, name] of Object.entries(options.blocks ?? {}))
      this.#blocks.set(position, name);
    for (const item of options.inventory ?? [])
      this.#items.set(
        item.name,
        (this.#items.get(item.name) ?? 0) + item.count,
      );
    for (const [position, contents] of Object.entries(
      options.containers ?? {},
    )) {
      this.#containers.set(
        position,
        new Map(contents.map((item) => [item.name, item.count])),
      );
      this.#blocks.set(position, "chest");
    }
    if (options.emulateSocket) {
      this.#socketCloseDelayMs = options.socketCloseDelayMs ?? 0;
      this._client = {
        ended: false,
        socket: {
          destroy: () => {
            clearTimeout(this._client?.closeTimer);
            this.#endSocket();
          },
        },
      };
    }
    this.#chunksReadyAt = Date.now() + (options.chunkDelayTicks ?? 0) * 50;
    this.#emptySlots = options.emptySlots ?? 30;

    this.inventory = {
      items: () =>
        [...this.#items]
          .filter(([, count]) => count > 0)
          .map(([name, count]) => ({
            name,
            count,
            type: registry.itemsByName[name]?.id ?? 0,
          })),
      emptySlotCount: () => this.#emptySlots,
      // Slots five to eight hold armour in the player window.
      slots: this.#armorSlots,
    };
    this.pathfinder = {
      setMovements: () => {},
      setGoal: () => {},
      goto: async () => {},
      thinkTimeout: 5000,
      tickTimeout: 40,
    };
  }

  // ------------------------------------------------------------- lifecycle

  loadPlugin(): void {}

  async waitForChunksToLoad(): Promise<void> {}

  quit(): void {
    this.calls.push("quit");
    // Real mineflayer: `bot.quit = reason => bot.end(reason)`.
    this.end();
  }

  /**
   * A port of `Client.end` from minecraft-protocol 1.x.
   *
   * Every call arms a close timer that destroys the socket if it has not
   * closed on its own. The handler that clears that timer runs once, on the
   * first close, and then removes itself. So a second end after the socket has
   * already gone arms a timer that nothing will ever clear, and the process
   * stays alive for thirty seconds with no work left to do. That is the bug
   * that made a failed `person observe` need Ctrl-C, reproduced here rather
   * than described.
   */
  end(): void {
    const client = this._client;
    if (!client) return;
    this.calls.push("end");
    client.closeTimer = setTimeout(
      () => client.socket.destroy(),
      CLOSE_TIMEOUT_MS,
    );
    if (client.ended) return;
    setTimeout(() => this.#endSocket(), this.#socketCloseDelayMs);
  }

  #endSocket(): void {
    const client = this._client;
    if (!client || client.ended) return;
    client.ended = true;
    clearTimeout(client.closeTimer);
    this.emit("end", "socketClosed");
  }

  spawn(): void {
    queueMicrotask(() => {
      this.emit("login");
      this.emit("spawn");
    });
  }

  // ----------------------------------------------------------------- world

  blockAt(position: {
    x: number;
    y: number;
    z: number;
  }): Record<string, unknown> | null {
    // Chunks arrive after the spawn packet. Until then, blockAt returns null,
    // exactly as it does against a real server.
    if (Date.now() < this.#chunksReadyAt) return null;
    const floored = new Vec3(
      Math.floor(position.x),
      Math.floor(position.y),
      Math.floor(position.z),
    );
    const biome = this.#biomeOrVoid();
    const explicit = this.#blocks.get(key(floored));
    if (explicit) return makeBlock(explicit, floored, biome);
    return makeBlock(
      floored.y > 63 ? "air" : floored.y === 63 ? "grass_block" : "stone",
      floored,
      biome,
    );
  }

  /** An id no registry knows, which is what an unloaded chunk looks like. */
  #biomeOrVoid(): { id: number; name: string } {
    return this.biome ?? { id: -1, name: "" };
  }

  findBlocks(options: {
    matching: (block: Record<string, unknown>) => boolean;
    maxDistance: number;
    count: number;
  }): InstanceType<typeof Vec3>[] {
    // Real mineflayer calls the matcher on palette entries that have no
    // position, which is why a matcher may only look at the block name.
    options.matching({ name: "oak_log", position: undefined } as never);
    const found: InstanceType<typeof Vec3>[] = [];
    for (const [position, name] of this.#blocks) {
      const [x, y, z] = position.split(",").map(Number) as [
        number,
        number,
        number,
      ];
      const point = new Vec3(x, y, z);
      if (point.distanceTo(this.entity.position) > options.maxDistance)
        continue;
      if (!options.matching(makeBlock(name, point, this.#biomeOrVoid())))
        continue;
      found.push(point);
    }
    // Real findBlocks sorts by distance and then truncates, so a caller that
    // asks for eight gets the eight nearest rather than the first eight the
    // scan happened to touch.
    return found
      .sort(
        (a, b) =>
          a.distanceTo(this.entity.position) -
          b.distanceTo(this.entity.position),
      )
      .slice(0, options.count);
  }

  canDigBlock(): boolean {
    return true;
  }

  canSeeBlock(): boolean {
    return true;
  }

  // ---------------------------------------------------------------- acting

  async equip(item: { name: string }): Promise<void> {
    this.heldItem = item;
    this.calls.push(`equip:${item.name}`);
  }

  async dig(block: {
    name: string;
    position: InstanceType<typeof Vec3>;
  }): Promise<void> {
    this.calls.push(`dig:${block.name}`);
    this.#blocks.set(key(block.position), "air");
    const drop = block.name === "stone" ? "cobblestone" : block.name;
    this.#items.set(drop, (this.#items.get(drop) ?? 0) + 1);
  }

  async placeBlock(
    reference: { position: InstanceType<typeof Vec3> },
    face: InstanceType<typeof Vec3>,
  ): Promise<void> {
    const held = this.heldItem?.name;
    if (!held) throw new Error("Nothing held");
    this.calls.push(`place:${held}`);
    this.#items.set(held, (this.#items.get(held) ?? 0) - 1);
    this.#blocks.set(key(reference.position.plus(face)), held);
  }

  recipesFor(
    itemType: number,
    _metadata: unknown,
    minResultCount: number,
    craftingTable: unknown,
  ): unknown[] {
    return Recipe.find(itemType, null).filter((recipe: never) => {
      const entry = recipe as {
        requiresTable: boolean;
        delta: { id: number; count: number }[];
        result: { count: number };
      };
      if (entry.requiresTable && !craftingTable) return false;
      const runs = Math.ceil(Math.max(1, minResultCount) / entry.result.count);
      return entry.delta
        .filter((d) => d.count < 0)
        .every(
          (d) =>
            (this.#items.get(registry.items[d.id].name) ?? 0) >=
            -d.count * runs,
        );
    });
  }

  async craft(recipe: unknown, times: number): Promise<void> {
    const entry = recipe as { delta: { id: number; count: number }[] };
    this.calls.push("craft");
    for (let run = 0; run < times; run++)
      for (const delta of entry.delta) {
        const name = registry.items[delta.id].name;
        this.#items.set(name, (this.#items.get(name) ?? 0) + delta.count);
      }
  }

  async consume(): Promise<void> {
    const name = this.heldItem?.name;
    if (!name) throw new Error("Nothing to eat");
    this.calls.push(`consume:${name}`);
    this.#items.set(name, (this.#items.get(name) ?? 0) - 1);
    this.food = Math.min(20, this.food + 6);
  }

  async attack(entity: DoubleEntity): Promise<void> {
    this.calls.push(`attack:${entity.name}`);
  }

  async openContainer(block: {
    position: InstanceType<typeof Vec3>;
  }): Promise<unknown> {
    const position = key(block.position);
    const contents =
      this.#containers.get(position) ?? new Map<string, number>();
    this.#containers.set(position, contents);
    const self = this;
    return {
      containerItems: () =>
        [...contents]
          .filter(([, count]) => count > 0)
          .map(([name, count]) => ({
            name,
            count,
            type: registry.itemsByName[name]?.id ?? 0,
          })),
      async deposit(type: number, _metadata: unknown, count: number) {
        if (self.failNextTransfer) {
          const message = self.failNextTransfer;
          self.failNextTransfer = null;
          throw new Error(message);
        }
        const name = registry.items[type].name;
        self.#items.set(name, (self.#items.get(name) ?? 0) - count);
        contents.set(name, (contents.get(name) ?? 0) + count);
      },
      async withdraw(type: number, _metadata: unknown, count: number) {
        if (self.failNextTransfer) {
          const message = self.failNextTransfer;
          self.failNextTransfer = null;
          throw new Error(message);
        }
        const name = registry.items[type].name;
        contents.set(name, (contents.get(name) ?? 0) - count);
        self.#items.set(name, (self.#items.get(name) ?? 0) + count);
      },
      close() {
        self.calls.push("container_close");
      },
    };
  }

  async openFurnace(): Promise<unknown> {
    const self = this;
    let pending = 0;
    let output: { name: string; count: number } | null = null;
    return {
      async putFuel(type: number, _metadata: unknown, count: number) {
        const name = registry.items[type].name;
        self.#items.set(name, (self.#items.get(name) ?? 0) - count);
      },
      async putInput(type: number, _metadata: unknown, count: number) {
        const name = registry.items[type].name;
        self.#items.set(name, (self.#items.get(name) ?? 0) - count);
        pending = count;
        // A real furnace cooks over time; the output appears in stages.
        output = {
          name: `cooked_${name}`,
          count: Math.max(1, Math.floor(count / 2)),
        };
      },
      outputItem: () => output,
      async takeOutput() {
        const taken = output;
        if (taken)
          self.#items.set(
            taken.name,
            (self.#items.get(taken.name) ?? 0) + taken.count,
          );
        output =
          pending > (taken?.count ?? 0)
            ? { name: taken?.name ?? "", count: pending - (taken?.count ?? 0) }
            : null;
        pending = 0;
        return taken;
      },
      close() {
        self.calls.push("furnace_close");
      },
    };
  }

  // ------------------------------------------------------------ test hooks

  /** Equips armour in the player window's armour slots. */
  wear(pieces: string[]): void {
    this.#armorSlots = [null, null, null, null, null];
    for (const [index, name] of pieces.entries())
      this.#armorSlots[5 + index] = { name };
    this.inventory.slots = this.#armorSlots;
  }

  spawnEntity(
    name: string,
    position: Position,
    extra: Partial<DoubleEntity> = {},
  ): DoubleEntity {
    const data = registry.entitiesByName[name];
    const entity: DoubleEntity = {
      id: this.#nextEntityId++,
      name,
      type: data?.type ?? "mob",
      kind: data?.category,
      position: new Vec3(position.x, position.y, position.z),
      metadata: {},
      ...extra,
    };
    this.entities[entity.id] = entity;
    return entity;
  }

  spawnPlayer(
    username: string,
    position: Position,
    uuid?: string,
  ): DoubleEntity {
    return this.spawnEntity("player", position, {
      name: "player",
      type: "player",
      username,
      ...(uuid === undefined ? {} : { uuid }),
      kind: undefined,
    });
  }

  setBlock(position: Position, name: string): void {
    this.#blocks.set(key(position), name);
  }

  give(name: string, count: number): void {
    this.#items.set(name, (this.#items.get(name) ?? 0) + count);
  }

  held(name: string): number {
    return this.#items.get(name) ?? 0;
  }

  containerContents(position: Position): { name: string; count: number }[] {
    const contents = this.#containers.get(key(position)) ?? new Map();
    return [...contents]
      .filter(([, count]) => count > 0)
      .map(([name, count]) => ({ name, count }));
  }

  damage(amount: number): void {
    this.health = Math.max(0, this.health - amount);
    this.emit("health");
  }
}

/** A `createBot` replacement that hands back the double and spawns it. */
export function doubleFactory(options: DoubleOptions = {}): {
  createBot: () => MineflayerDouble;
  bot: MineflayerDouble;
} {
  const bot = new MineflayerDouble(options);
  return {
    bot,
    createBot: () => {
      bot.spawn();
      return bot;
    },
  };
}
