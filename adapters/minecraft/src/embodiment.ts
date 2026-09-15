import { EventEmitter, once } from "node:events";
import { setTimeout as delay } from "node:timers/promises";
import mineflayer from "mineflayer";
import pathfinderPackage from "mineflayer-pathfinder";
import vec3Package from "vec3";
import {
  contains,
  distance,
  positionKey,
  type PersonConfig,
  type Position,
} from "#config";
import type { ItemStack } from "#protocol";
import {
  DisconnectedError,
  EmbodimentError,
  type BlockKind,
  type BlockView,
  type ContainerView,
  type CraftResult,
  type Embodiment,
  type EntityView,
  type FindBlocksQuery,
  type MoveOptions,
  type PhysicalGuard,
  type WorldSnapshot,
  preferredWood,
  recipesFor,
} from "#node-runtime";
import {
  FUEL_BURN,
  HAZARD_BLOCKS,
  HOSTILE_MOBS,
  PASSIVE_MOBS,
  RANGED_MOBS,
  TAMEABLE_MOBS,
  blockKind,
} from "./registry.ts";

const { pathfinder, Movements, goals } = pathfinderPackage;
const { Vec3 } = vec3Package;

type Bot = ReturnType<typeof mineflayer.createBot>;

const vec = (p: Position): InstanceType<typeof Vec3> => new Vec3(p.x, p.y, p.z);
const point = (v: { x: number; y: number; z: number }): Position => ({
  x: Math.floor(v.x),
  y: Math.floor(v.y),
  z: Math.floor(v.z),
});

export interface MineflayerOptions {
  createBot?: typeof mineflayer.createBot;
  /** Wall-clock milliseconds to allow for a connection. */
  connectTimeoutMs?: number;
}

/**
 * The Mineflayer embodiment.
 *
 * This is the production body. It implements the same port the fixture world
 * implements, so the skill implementations above it are shared: the fixture
 * tests exercise real skill code, and this class is the only place that knows
 * what a Minecraft packet is.
 *
 * The connectivity, navigation and interaction patterns here are adapted from
 * the Shroud runtime, which drove a live 1.16.1 LAN world. The safety
 * decisions are not: those come from the Person safety kernel, and the guard
 * installed by the runtime is consulted on every movement and every block
 * modification, not only when a destination is first chosen.
 */
export class MineflayerEmbodiment extends EventEmitter implements Embodiment {
  readonly kind = "mineflayer" as const;
  readonly #config: PersonConfig;
  readonly #createBot: typeof mineflayer.createBot;
  readonly #connectTimeoutMs: number;
  readonly #ownedStorage = new Map<string, string>();
  readonly #placed = new Set<string>();
  #bot: Bot | null = null;
  #guard: PhysicalGuard | null = null;
  #connected = false;
  #lastSafePosition: Position | null = null;
  #stuck = false;
  #startTick = 0;

  constructor(config: PersonConfig, options: MineflayerOptions = {}) {
    super();
    this.#config = config;
    this.#createBot = options.createBot ?? mineflayer.createBot;
    this.#connectTimeoutMs = options.connectTimeoutMs ?? 120000;
  }

  setGuard(guard: PhysicalGuard): void {
    this.#guard = guard;
  }

  get bot(): Bot {
    if (!this.#bot)
      throw new DisconnectedError("The Minecraft client is not connected");
    return this.#bot;
  }

  // ------------------------------------------------------------------ connect

  async connect(): Promise<void> {
    const server = this.#config.server;
    const botConfig = this.#config.bot;
    if (!server || !botConfig)
      throw new EmbodimentError(
        "configuration",
        "Minecraft embodiment needs server and bot config",
      );

    const bot = this.#createBot({
      host: server.host,
      port: server.port,
      version: server.version,
      username: botConfig.username,
      auth: botConfig.auth,
      respawn: false,
      viewDistance: 4,
      hideErrors: true,
      checkTimeoutInterval: 30000,
    });
    this.#bot = bot;
    bot.loadPlugin(pathfinder);
    bot.on("kicked", (reason: unknown) => {
      this.#connected = false;
      this.emit("fatal", `server_kicked: ${String(reason).slice(0, 200)}`);
    });
    bot.on("error", (error: Error) => {
      this.#connected = false;
      this.emit("fatal", `connection_error: ${error.message}`);
    });
    bot.on("end", () => {
      this.#connected = false;
      this.emit("fatal", "disconnected");
    });

    const spawned = once(bot, "spawn");
    const timer = delay(this.#connectTimeoutMs).then(() => {
      throw new EmbodimentError(
        "connect_timeout",
        "Minecraft did not spawn the bot in time",
      );
    });
    await Promise.race([spawned, timer]);
    await bot.waitForChunksToLoad();
    if (bot.time.age === null) await once(bot, "time");

    if (bot.username.toLowerCase() !== botConfig.username.toLowerCase())
      throw new EmbodimentError(
        "identity_mismatch",
        "Authenticated identity differs from the dedicated bot username",
      );
    const here = point(bot.entity.position);
    if (!contains(this.#config.world.exploration, here))
      throw new EmbodimentError(
        "spawn_outside_bounds",
        `Spawned at ${positionKey(here)}, outside the configured exploration area`,
      );

    this.#configureMovement();
    this.#startTick = Number(bot.time.age ?? 0);
    this.#connected = true;
    this.#lastSafePosition = here;
  }

  #configureMovement(): void {
    const bot = this.bot;
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
    // The guard is consulted for every step the planner considers, so a route
    // cannot drift into a protected area while replanning around an obstacle.
    movements.exclusionAreasStep.push(
      (block: { position?: Position } | Position) => {
        const position =
          "position" in block && block.position
            ? block.position
            : (block as Position);
        return this.#guard?.canEnter(point(position)) === false ? 100 : 0;
      },
    );
    movements.exclusionAreasBreak.push(() => 100);
    movements.exclusionAreasPlace.push(() => 100);
    for (const name of HOSTILE_MOBS) movements.entitiesToAvoid.add(name);
    bot.pathfinder.setMovements(movements);
    bot.pathfinder.thinkTimeout = 4000;
    bot.pathfinder.tickTimeout = 20;
    (bot.pathfinder as unknown as { searchRadius?: number }).searchRadius = 96;
  }

  async disconnect(): Promise<void> {
    this.#connected = false;
    const bot = this.#bot;
    this.#bot = null;
    if (!bot) return;
    bot.pathfinder?.setGoal(null);
    bot.quit?.("Person session finished");
    await delay(200);
    bot.end?.();
  }

  // ----------------------------------------------------------------- reading

  blockAt(position: Position): BlockView | null {
    const block = this.#bot?.blockAt(vec(position));
    if (!block) return null;
    const kind = blockKind(block.name);
    return {
      position,
      name: block.name,
      kind,
      solid: block.boundingBox === "block",
      hazard: HAZARD_BLOCKS.has(block.name),
      ownedByPerson: this.#placed.has(positionKey(position)),
    };
  }

  findBlocks(query: FindBlocksQuery): BlockView[] {
    const bot = this.bot;
    const wanted = new Set<BlockKind>(query.kinds);
    const found = bot.findBlocks({
      matching: (block: { name: string }) => wanted.has(blockKind(block.name)),
      maxDistance: query.maxDistance,
      count: query.limit,
    });
    return found
      .map((position: { x: number; y: number; z: number }) =>
        this.blockAt(point(position)),
      )
      .filter((block: BlockView | null): block is BlockView => block !== null);
  }

  containerAt(position: Position): ContainerView | null {
    const block = this.blockAt(position);
    if (!block) return null;
    if (block.kind !== "chest" && block.kind !== "furnace") return null;
    const key = positionKey(position);
    return {
      position,
      kind: block.kind === "furnace" ? "furnace" : "chest",
      contents: this.#containerContents.get(key) ?? [],
      storageId: this.#ownedStorage.get(key) ?? null,
    };
  }

  /** Last observed contents, refreshed whenever a container is opened. */
  readonly #containerContents = new Map<string, ItemStack[]>();

  #entities(): EntityView[] {
    const bot = this.bot;
    const self = bot.entity?.id;
    const here = bot.entity?.position;
    if (!here) return [];
    const views: EntityView[] = [];
    for (const entity of Object.values(bot.entities) as unknown as Record<
      string,
      unknown
    >[]) {
      const record = entity as {
        id: number;
        name?: string;
        username?: string;
        type?: string;
        position: { x: number; y: number; z: number };
        metadata?: unknown[];
      };
      if (record.id === self) continue;
      const name = record.name ?? record.username ?? "unknown";
      const isPlayer = record.type === "player";
      const villager = name === "villager" || name === "wandering_trader";
      const named = Boolean(
        (record.metadata ?? []).some(
          (entry) => typeof entry === "string" && entry.length > 0,
        ),
      );
      const tamed = TAMEABLE_MOBS.has(name);
      views.push({
        entityId: record.id,
        name: isPlayer ? "player" : name,
        position: point(record.position),
        distance: distance(point(here), point(record.position)),
        hostile: HOSTILE_MOBS.has(name),
        passive: PASSIVE_MOBS.has(name) && !tamed,
        player: isPlayer,
        villager,
        named,
        tamed,
        ranged: RANGED_MOBS.has(name),
      });
    }
    return views;
  }

  snapshot(): WorldSnapshot {
    const bot = this.#bot;
    if (!bot || !bot.entity) {
      return {
        tick: this.#startTick,
        timeOfDay: 0,
        weather: "clear",
        dimension: "overworld",
        biome: "unknown",
        lightLevel: 0,
        position: this.#lastSafePosition ?? this.#config.world.home,
        health: 0,
        food: 0,
        saturation: 0,
        air: 300,
        armor: 0,
        alive: false,
        statusEffects: [],
        inventory: [],
        freeSlots: 0,
        entities: [],
        containers: [],
        resources: [],
        hazards: [],
        stuck: false,
        lastSafePosition: this.#lastSafePosition,
        connected: false,
      };
    }
    const here = point(bot.entity.position);
    const inventory: ItemStack[] = bot.inventory
      .items()
      .map((item: { name: string; count: number }) => ({
        name: item.name,
        count: item.count,
      }));
    const resources = this.#connected
      ? this.findBlocks({
          kinds: ["wood", "stone", "coal_ore", "plant_food", "leaves"],
          maxDistance: 48,
          limit: 64,
        })
      : [];
    const hazards = this.#connected
      ? this.findBlocks({
          kinds: ["lava", "fire", "water", "cactus"],
          maxDistance: 12,
          limit: 32,
        })
      : [];
    const containers = this.#connected
      ? this.findBlocks({
          kinds: ["chest", "furnace"],
          maxDistance: 32,
          limit: 16,
        })
          .map((block) => this.containerAt(block.position))
          .filter((container): container is ContainerView => container !== null)
      : [];

    const timeOfDay = Number(bot.time.timeOfDay ?? 0);
    const snapshot: WorldSnapshot = {
      tick: Number(bot.time.age ?? this.#startTick),
      timeOfDay,
      weather: bot.isRaining
        ? bot.thunderState > 0
          ? "thunder"
          : "rain"
        : "clear",
      dimension: "overworld",
      biome: "unknown",
      lightLevel: timeOfDay < 12000 ? 15 : 4,
      position: here,
      health: bot.health ?? 0,
      food: bot.food ?? 0,
      saturation: bot.foodSaturation ?? 0,
      air: bot.oxygenLevel === undefined ? 300 : bot.oxygenLevel * 15,
      armor: 0,
      alive: (bot.health ?? 0) > 0,
      statusEffects: [],
      inventory,
      freeSlots: Math.max(0, 36 - inventory.length),
      entities: this.#entities(),
      containers,
      resources,
      hazards,
      stuck: this.#stuck,
      lastSafePosition: this.#lastSafePosition,
      connected: this.#connected,
    };
    if (
      snapshot.alive &&
      !snapshot.entities.some((entity) => entity.hostile && entity.distance < 8)
    )
      this.#lastSafePosition = here;
    return snapshot;
  }

  findEntities(): EntityView[] {
    return this.#entities();
  }

  // ----------------------------------------------------------------- acting

  #requireGuard(position: Position, action: "enter" | "modify"): void {
    const guard = this.#guard;
    if (!guard) return;
    const allowed =
      action === "enter" ? guard.canEnter(position) : guard.canModify(position);
    if (!allowed)
      throw new EmbodimentError(
        "protected_area",
        `${action} denied at ${positionKey(position)}`,
      );
  }

  async moveTo(target: Position, options: MoveOptions = {}): Promise<void> {
    const bot = this.bot;
    if (!this.#connected) throw new DisconnectedError();
    this.#requireGuard(target, "enter");
    const range = options.range ?? 0;
    const goal = range
      ? new goals.GoalNear(target.x, target.y, target.z, range)
      : new goals.GoalBlock(target.x, target.y, target.z);
    const timeoutMs = Math.max(
      2000,
      Math.min(60000, (options.maxTicks ?? 600) * 50),
    );

    let timer: NodeJS.Timeout | undefined;
    let onReset: ((reason: string) => void) | undefined;
    try {
      const failure = new Promise<never>((_resolve, reject) => {
        onReset = (reason: string) => {
          if (reason === "stuck")
            reject(new EmbodimentError("navigation_stuck", "Navigation stuck"));
        };
        bot.on("path_reset", onReset);
        timer = setTimeout(
          () =>
            reject(
              new EmbodimentError("navigation_timeout", "Navigation timeout"),
            ),
          timeoutMs,
        );
      });
      await Promise.race([bot.pathfinder.goto(goal), failure]);
      this.#stuck = false;
      const arrived = point(bot.entity.position);
      if (distance(arrived, target) > Math.max(range, 1))
        throw new EmbodimentError(
          "no_route",
          "Pathfinder stopped short of the destination",
        );
    } catch (error) {
      this.#stuck = true;
      bot.pathfinder.setGoal(null);
      bot.clearControlStates?.();
      throw error instanceof EmbodimentError
        ? error
        : new EmbodimentError("no_route", (error as Error).message);
    } finally {
      if (timer) clearTimeout(timer);
      if (onReset) bot.off("path_reset", onReset);
    }
  }

  async dig(position: Position): Promise<ItemStack[]> {
    const bot = this.bot;
    if (!this.#connected) throw new DisconnectedError();
    this.#requireGuard(position, "modify");
    const block = bot.blockAt(vec(position));
    if (!block)
      throw new EmbodimentError("unknown_block", "Block is not loaded");
    if (blockKind(block.name) === "air")
      throw new EmbodimentError("nothing_to_dig", "Block is already air");
    const feet = point(bot.entity.position);
    if (position.x === feet.x && position.z === feet.z && position.y <= feet.y)
      throw new EmbodimentError(
        "unsafe_dig",
        "Cannot dig the supporting block",
      );
    for (const [dx, dy, dz] of [
      [1, 0, 0],
      [-1, 0, 0],
      [0, 1, 0],
      [0, -1, 0],
      [0, 0, 1],
      [0, 0, -1],
    ] as [number, number, number][]) {
      const neighbour = bot.blockAt(
        vec({ x: position.x + dx, y: position.y + dy, z: position.z + dz }),
      );
      if (!neighbour)
        throw new EmbodimentError(
          "unknown_block",
          "Neighbouring block is not loaded",
        );
      if (["water", "lava", "sand", "gravel"].includes(neighbour.name))
        throw new EmbodimentError(
          "unsafe_dig",
          `Unsafe excavation neighbour ${neighbour.name}`,
        );
    }
    if (!bot.canDigBlock(block) || !bot.canSeeBlock(block))
      throw new EmbodimentError(
        "out_of_reach",
        "Block is not safely reachable",
      );

    const axe = bot.inventory
      .items()
      .find((item: { name: string }) => item.name.endsWith("_axe"));
    const pickaxe = bot.inventory
      .items()
      .find((item: { name: string }) => item.name.endsWith("_pickaxe"));
    const kind = blockKind(block.name);
    const tool =
      kind === "wood"
        ? axe
        : kind === "stone" || kind === "coal_ore"
          ? pickaxe
          : null;
    if (tool) await bot.equip(tool, "hand");

    const before = this.#tally();
    await bot.dig(block, true);
    this.#placed.delete(positionKey(position));
    await this.#collectNearbyDrops();
    return this.#gained(before);
  }

  async #collectNearbyDrops(): Promise<void> {
    const bot = this.bot;
    await delay(350);
    const drops = Object.values(bot.entities).filter(
      (entity) =>
        (entity as { name?: string }).name === "item" &&
        distance(
          point((entity as { position: Position }).position),
          point(bot.entity.position),
        ) < 6,
    );
    for (const drop of drops.slice(0, 6)) {
      const target = point((drop as { position: Position }).position);
      if (this.#guard && !this.#guard.canEnter(target)) continue;
      try {
        await this.moveTo(target, { range: 1, maxTicks: 60 });
      } catch {
        // A drop that cannot be reached safely is simply left where it is.
      }
    }
  }

  #tally(): Map<string, number> {
    const totals = new Map<string, number>();
    for (const item of this.bot.inventory.items() as {
      name: string;
      count: number;
    }[])
      totals.set(item.name, (totals.get(item.name) ?? 0) + item.count);
    return totals;
  }

  #gained(before: Map<string, number>): ItemStack[] {
    const after = this.#tally();
    const gained: ItemStack[] = [];
    for (const [name, count] of after) {
      const delta = count - (before.get(name) ?? 0);
      if (delta > 0) gained.push({ name, count: delta });
    }
    return gained;
  }

  async place(position: Position, item: string): Promise<void> {
    const bot = this.bot;
    if (!this.#connected) throw new DisconnectedError();
    this.#requireGuard(position, "modify");
    const stack = bot.inventory
      .items()
      .find((candidate: { name: string }) => candidate.name === item);
    if (!stack)
      throw new EmbodimentError("missing_item", `No ${item} to place`);
    const existing = bot.blockAt(vec(position));
    if (existing && existing.boundingBox === "block")
      throw new EmbodimentError("occupied", "Placement would replace a block");

    const references: [number, number, number][] = [
      [0, -1, 0],
      [1, 0, 0],
      [-1, 0, 0],
      [0, 0, 1],
      [0, 0, -1],
      [0, 1, 0],
    ];
    for (const [dx, dy, dz] of references) {
      const referencePosition = {
        x: position.x + dx,
        y: position.y + dy,
        z: position.z + dz,
      };
      const reference = bot.blockAt(vec(referencePosition));
      if (!reference || reference.boundingBox !== "block") continue;
      if (this.#guard && !this.#guard.canEnter(referencePosition)) continue;
      // Right-click only inert ground or blocks Person placed. Never a
      // container or a player workstation.
      const inert = ["dirt", "grass_block", "stone", "cobblestone"].includes(
        reference.name,
      );
      if (!inert && !this.#placed.has(positionKey(referencePosition))) continue;
      if (reference.name === "crafting_table" || reference.name === "chest")
        continue;

      await bot.equip(stack, "hand");
      await bot.placeBlock(reference, new Vec3(-dx, -dy, -dz));
      for (let attempt = 0; attempt < 4; attempt++) {
        if (bot.blockAt(vec(position))?.name === item) {
          this.#placed.add(positionKey(position));
          return;
        }
        await delay(100 * (attempt + 1));
      }
      throw new EmbodimentError(
        "placement_refused",
        `The server refused to place ${item} at ${positionKey(position)}`,
      );
    }
    throw new EmbodimentError(
      "no_placement_reference",
      "No safe placement reference",
    );
  }

  async craft(
    item: string,
    times: number,
    tablePosition: Position | null,
  ): Promise<CraftResult> {
    const bot = this.bot;
    if (!this.#connected) throw new DisconnectedError();
    const recipes = recipesFor(preferredWood(this.snapshot().inventory));
    const contract = recipes[item];
    if (!contract)
      throw new EmbodimentError("no_recipe", `No Person recipe for ${item}`);
    let table = null;
    if (contract.requiresTable) {
      if (!tablePosition)
        throw new EmbodimentError("no_crafting_table", `${item} needs a table`);
      table = bot.blockAt(vec(tablePosition));
      if (!table || table.name !== "crafting_table")
        throw new EmbodimentError(
          "no_crafting_table",
          "No crafting table at the given position",
        );
      if (!this.#placed.has(positionKey(tablePosition)))
        throw new EmbodimentError(
          "unowned_table",
          "Person may only use a table it placed",
        );
    }
    const id = bot.registry.itemsByName[item]?.id;
    if (id === undefined)
      throw new EmbodimentError("no_recipe", `Unknown item ${item}`);
    const recipe = bot.recipesFor(id, null, 1, table)[0];
    if (!recipe)
      throw new EmbodimentError("no_recipe", `Recipe unavailable: ${item}`);
    const before = this.#tally();
    await bot.craft(recipe, times, table ?? undefined);
    const after = this.#tally();
    const consumed: ItemStack[] = [];
    for (const [name, count] of before) {
      const delta = count - (after.get(name) ?? 0);
      if (delta > 0) consumed.push({ name, count: delta });
    }
    return { produced: this.#gained(before), consumed };
  }

  async smelt(
    input: string,
    times: number,
    furnacePosition: Position,
  ): Promise<CraftResult> {
    const bot = this.bot;
    if (!this.#connected) throw new DisconnectedError();
    if (!this.#placed.has(positionKey(furnacePosition)))
      throw new EmbodimentError(
        "unowned_furnace",
        "Person may only use a furnace it placed",
      );
    const block = bot.blockAt(vec(furnacePosition));
    if (!block || blockKind(block.name) !== "furnace")
      throw new EmbodimentError(
        "no_furnace",
        "No furnace at the given position",
      );

    const before = this.#tally();
    const furnace = await bot.openFurnace(block);
    try {
      const fuel = bot.inventory
        .items()
        .find((item: { name: string }) => item.name in FUEL_BURN);
      if (!fuel) throw new EmbodimentError("no_fuel", "No fuel available");
      const perUnit = FUEL_BURN[fuel.name] ?? 1;
      const fuelNeeded = Math.max(1, Math.ceil(times / perUnit));
      await furnace.putFuel(fuel.type, null, Math.min(fuelNeeded, fuel.count));
      const raw = bot.inventory
        .items()
        .find((item: { name: string }) => item.name === input);
      if (!raw)
        throw new EmbodimentError("missing_materials", `No ${input} to smelt`);
      const runs = Math.min(times, raw.count);
      await furnace.putInput(raw.type, null, runs);
      // Ten seconds of furnace time per item, plus a margin for server lag.
      for (let waited = 0; waited < runs * 12000 + 4000; waited += 500) {
        await delay(500);
        if (furnace.outputItem()?.count === runs) break;
      }
      if (furnace.outputItem()) await furnace.takeOutput();
    } finally {
      furnace.close();
    }
    await delay(200);
    const after = this.#tally();
    const consumed: ItemStack[] = [];
    for (const [name, count] of before) {
      const delta = count - (after.get(name) ?? 0);
      if (delta > 0) consumed.push({ name, count: delta });
    }
    return { produced: this.#gained(before), consumed };
  }

  async consume(item: string): Promise<void> {
    const bot = this.bot;
    if (!this.#connected) throw new DisconnectedError();
    const stack = bot.inventory
      .items()
      .find((candidate: { name: string }) => candidate.name === item);
    if (!stack) throw new EmbodimentError("missing_item", `No ${item} to eat`);
    await bot.equip(stack, "hand");
    await bot.consume();
  }

  async attack(entityId: number): Promise<void> {
    const bot = this.bot;
    if (!this.#connected) throw new DisconnectedError();
    const entity = bot.entities[entityId];
    if (!entity) throw new EmbodimentError("no_target", "Entity is gone");
    const view = this.#entities().find(
      (candidate) => candidate.entityId === entityId,
    );
    if (!view) throw new EmbodimentError("no_target", "Entity is not visible");
    if (this.#guard && !this.#guard.canTargetEntity(view))
      throw new EmbodimentError(
        "forbidden_target",
        `Targeting ${view.name} is not permitted`,
      );
    if (view.distance > 4)
      throw new EmbodimentError("out_of_reach", "Target is out of reach");
    const weapon = bot.inventory
      .items()
      .find(
        (item: { name: string }) =>
          item.name.endsWith("_sword") || item.name.endsWith("_axe"),
      );
    if (weapon) await bot.equip(weapon, "hand");
    await bot.attack(entity);
    await delay(650);
  }

  async deposit(position: Position, items: ItemStack[]): Promise<ItemStack[]> {
    const storageId = this.#ownedStorage.get(positionKey(position));
    if (!storageId)
      throw new EmbodimentError(
        "existing_container_deposit_forbidden",
        "Person never deposits into a container it did not place",
      );
    const bot = this.bot;
    const block = bot.blockAt(vec(position));
    if (!block)
      throw new EmbodimentError(
        "no_container",
        "No container at that position",
      );
    const chest = await bot.openContainer(block);
    const moved: ItemStack[] = [];
    try {
      for (const item of items) {
        const type = bot.registry.itemsByName[item.name]?.id;
        if (type === undefined) continue;
        const held = bot.inventory
          .items()
          .filter((candidate: { name: string }) => candidate.name === item.name)
          .reduce(
            (total: number, candidate: { count: number }) =>
              total + candidate.count,
            0,
          );
        const amount = Math.min(item.count, held);
        if (amount <= 0) continue;
        await chest.deposit(type, null, amount);
        moved.push({ name: item.name, count: amount });
      }
      this.#containerContents.set(
        positionKey(position),
        (chest.containerItems() as { name: string; count: number }[]).map(
          (item) => ({
            name: item.name,
            count: item.count,
          }),
        ),
      );
    } finally {
      chest.close();
    }
    return moved;
  }

  async withdraw(position: Position, items: ItemStack[]): Promise<ItemStack[]> {
    const bot = this.bot;
    const block = bot.blockAt(vec(position));
    if (!block)
      throw new EmbodimentError(
        "no_container",
        "No container at that position",
      );
    const chest = await bot.openContainer(block);
    const moved: ItemStack[] = [];
    try {
      for (const item of items) {
        const type = bot.registry.itemsByName[item.name]?.id;
        if (type === undefined) continue;
        const available = (
          chest.containerItems() as { name: string; count: number }[]
        )
          .filter((candidate) => candidate.name === item.name)
          .reduce((total, candidate) => total + candidate.count, 0);
        const amount = Math.min(item.count, available);
        if (amount <= 0) continue;
        await chest.withdraw(type, null, amount);
        moved.push({ name: item.name, count: amount });
      }
      this.#containerContents.set(
        positionKey(position),
        (chest.containerItems() as { name: string; count: number }[]).map(
          (item) => ({
            name: item.name,
            count: item.count,
          }),
        ),
      );
    } finally {
      chest.close();
    }
    return moved;
  }

  async waitTicks(ticks: number): Promise<void> {
    if (!this.#connected) throw new DisconnectedError();
    await delay(Math.max(0, ticks) * 50);
  }

  registerOwnedStorage(position: Position, storageId: string): void {
    this.#ownedStorage.set(positionKey(position), storageId);
    this.#placed.add(positionKey(position));
  }
}
