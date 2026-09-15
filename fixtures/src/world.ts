import { readFileSync } from "node:fs";
import { distance, positionKey, type Position } from "#config";
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
  FOOD_VALUE,
  FUEL_VALUE,
  SMELTING,
  isFuel,
  recipesFor,
  preferredWood,
} from "#node-runtime";
import {
  BLOCKS,
  HOSTILES,
  NEUTRALS,
  PASSIVE_ANIMALS,
  RANGED_HOSTILES,
  definitionOf,
} from "./blocks.ts";
import {
  DEFAULT_DEFINITION,
  type FixtureWorldDefinition,
} from "./definition.ts";
import { SeededRandom } from "./rng.ts";

interface FixtureEntityState {
  entityId: number;
  name: string;
  position: Position;
  health: number;
  hostile: boolean;
  neutral: boolean;
  passive: boolean;
  player: boolean;
  villager: boolean;
  named: boolean;
  tamed: boolean;
  ranged: boolean;
}

const MAX_SLOTS = 36;
const SCAN_RADIUS = 64;
/** Mirrors the Mineflayer adapter: how long damage keeps a neutral dangerous. */
const DAMAGE_MEMORY_TICKS = 200;

/**
 * A deterministic Minecraft-shaped world.
 *
 * This is not a Mineflayer replacement and does not pretend to be Minecraft.
 * It is the integration-test environment: it implements the same embodiment
 * port the Mineflayer adapter implements, so the skill code exercised here is
 * the skill code that runs against a real server. Every rule in it is explicit
 * and every outcome is reproducible from the recorded seed.
 */
export class FixtureWorld implements Embodiment {
  readonly kind = "fixture" as const;
  readonly definition: FixtureWorldDefinition;
  readonly #random: SeededRandom;
  readonly #blocks = new Map<string, string>();
  readonly #owned = new Set<string>();
  readonly #containers = new Map<
    string,
    {
      kind: ContainerView["kind"];
      contents: Map<string, number>;
      storageId: string | null;
    }
  >();
  readonly #inventory = new Map<string, number>();
  #entities: FixtureEntityState[] = [];
  #nextEntityId = 100;
  #tick: number;
  #position: Position;
  #health: number;
  #food: number;
  #saturation: number;
  #air: number;
  #armor: number;
  #weather: "clear" | "rain" | "thunder" = "clear";
  #connected = false;
  #guard: PhysicalGuard | null = null;
  #lastSafePosition: Position | null = null;
  #lastAttackTick = -1000;
  #firedEvents = new Set<number>();
  #groundLevel: number;
  #snapshotCache: { tick: number; value: WorldSnapshot } | null = null;
  #lastDamageTick: number | null = null;

  constructor(definition: Partial<FixtureWorldDefinition> = {}) {
    this.definition = { ...DEFAULT_DEFINITION, ...definition };
    this.#random = new SeededRandom(this.definition.seed);
    this.#tick = this.definition.startTick;
    this.#position = { ...this.definition.spawn };
    this.#health = this.definition.vitals.health;
    this.#food = this.definition.vitals.food;
    this.#saturation = this.definition.vitals.saturation;
    this.#air = this.definition.vitals.air;
    this.#armor = this.definition.vitals.armor;
    this.#groundLevel = this.definition.groundLevel;

    for (const block of this.definition.blocks)
      this.#blocks.set(positionKey(block.position), block.name);
    for (const cluster of this.definition.clusters) this.#growCluster(cluster);
    for (const item of this.definition.inventory)
      this.#inventory.set(
        item.name,
        (this.#inventory.get(item.name) ?? 0) + item.count,
      );
    for (const container of this.definition.containers) {
      this.#blocks.set(
        positionKey(container.position),
        container.kind === "furnace" ? "furnace" : "chest",
      );
      this.#containers.set(positionKey(container.position), {
        kind: container.kind,
        contents: new Map(
          container.contents.map((item) => [item.name, item.count]),
        ),
        storageId: container.ownedByPerson
          ? `storage_${positionKey(container.position).replace(/,/g, "_")}`
          : null,
      });
      if (container.ownedByPerson)
        this.#owned.add(positionKey(container.position));
    }
    for (const entity of this.definition.entities)
      this.spawn(entity.name, entity.position, entity);
  }

  static fromFile(filename: string): FixtureWorld {
    return new FixtureWorld(
      JSON.parse(readFileSync(filename, "utf8")) as FixtureWorldDefinition,
    );
  }

  #growCluster(cluster: {
    name: string;
    center: Position;
    count: number;
    spread: number;
  }): void {
    let placed = 0;
    let attempts = 0;
    while (placed < cluster.count && attempts < cluster.count * 40) {
      attempts += 1;
      const position: Position = {
        x:
          cluster.center.x +
          this.#random.int(cluster.spread * 2 + 1) -
          cluster.spread,
        y: cluster.center.y + this.#random.int(2),
        z:
          cluster.center.z +
          this.#random.int(cluster.spread * 2 + 1) -
          cluster.spread,
      };
      const key = positionKey(position);
      if (this.#blocks.has(key)) continue;
      this.#blocks.set(key, cluster.name);
      placed += 1;
    }
  }

  // ---------------------------------------------------------------- terrain

  #naturalName(position: Position): string {
    if (position.y > this.#groundLevel) return "air";
    if (position.y === this.#groundLevel) return "grass_block";
    return position.y >= this.#groundLevel - 3 ? "dirt" : "stone";
  }

  #nameAt(position: Position): string {
    return (
      this.#blocks.get(positionKey(position)) ?? this.#naturalName(position)
    );
  }

  blockAt(position: Position): BlockView | null {
    const name = this.#nameAt(position);
    const definition = definitionOf(name);
    return {
      position: { ...position },
      name,
      kind: definition.kind,
      solid: definition.solid,
      hazard: definition.hazard,
      ownedByPerson: this.#owned.has(positionKey(position)),
    };
  }

  #invalidate(): void {
    this.#snapshotCache = null;
  }

  #setBlock(position: Position, name: string): void {
    this.#invalidate();
    if (name === this.#naturalName(position))
      this.#blocks.delete(positionKey(position));
    else this.#blocks.set(positionKey(position), name);
  }

  findBlocks(query: FindBlocksQuery): BlockView[] {
    const wanted = new Set<BlockKind>(query.kinds);
    const found: BlockView[] = [];
    const radius = Math.min(query.maxDistance, SCAN_RADIUS);
    // Explicit blocks first: natural terrain only ever contributes dirt,
    // grass and stone, which are scanned separately and cheaply.
    for (const [key, name] of this.#blocks) {
      if (!wanted.has(definitionOf(name).kind)) continue;
      const [x, y, z] = key.split(",").map(Number) as [number, number, number];
      const position = { x, y, z };
      if (distance(this.#position, position) > radius) continue;
      found.push(this.blockAt(position) as BlockView);
    }
    if (wanted.has("stone") || wanted.has("dirt") || wanted.has("grass")) {
      // Natural terrain is uniform, so a short scan finds as much of it as any
      // long one would; the explicit block map above covers everything placed.
      const origin = this.#position;
      const near = Math.min(radius, 12);
      for (let dx = -near; dx <= near && found.length < query.limit * 2; dx++)
        for (let dz = -near; dz <= near && found.length < query.limit * 2; dz++)
          for (let dy = -4; dy <= 1; dy++) {
            const position = {
              x: origin.x + dx,
              y: origin.y + dy,
              z: origin.z + dz,
            };
            if (this.#blocks.has(positionKey(position))) continue;
            const kind = definitionOf(this.#naturalName(position)).kind;
            if (!wanted.has(kind)) continue;
            if (distance(origin, position) > radius) continue;
            found.push(this.blockAt(position) as BlockView);
          }
    }
    return found
      .sort(
        (a, b) =>
          distance(this.#position, a.position) -
          distance(this.#position, b.position),
      )
      .slice(0, query.limit);
  }

  /**
   * The fixture always knows what is in a container, but the port promises an
   * asynchronous read because a real server only reveals contents once the
   * window is open. Both bodies must present the same shape or the skills
   * would be written against the easier one.
   */
  async inspectContainer(position: Position): Promise<ContainerView | null> {
    const view = this.containerAt(position);
    if (!view) return null;
    this.#advance(4);
    return this.containerAt(position);
  }

  containerAt(position: Position): ContainerView | null {
    const container = this.#containers.get(positionKey(position));
    if (!container) return null;
    return {
      position: { ...position },
      kind: container.kind,
      contents: [...container.contents]
        .filter(([, count]) => count > 0)
        .map(([name, count]) => ({ name, count })),
      storageId: container.storageId,
    };
  }

  // ---------------------------------------------------------------- guards

  setGuard(guard: PhysicalGuard): void {
    this.#guard = guard;
  }

  #assertEnter(position: Position): void {
    if (this.#guard && !this.#guard.canEnter(position))
      throw new EmbodimentError(
        "protected_area",
        `Entry denied at ${positionKey(position)}`,
      );
  }

  #assertModify(position: Position): void {
    if (this.#guard && !this.#guard.canModify(position))
      throw new EmbodimentError(
        "protected_area",
        `Modification denied at ${positionKey(position)}`,
      );
  }

  // ---------------------------------------------------------------- lifecycle

  async connect(): Promise<void> {
    this.#connected = true;
    this.#lastSafePosition = { ...this.#position };
    this.#advance(0);
  }

  async disconnect(): Promise<void> {
    this.#connected = false;
  }

  /** Test hook: simulate the Minecraft connection dropping. */
  dropConnection(): void {
    this.#connected = false;
  }

  // ---------------------------------------------------------------- time

  #advance(ticks: number): void {
    this.#invalidate();
    for (let step = 0; step < Math.max(0, ticks); step++) {
      this.#tick += 1;
      this.#runEvents();
      this.#stepEntities();
      this.#stepVitals();
    }
    if (ticks === 0) {
      this.#runEvents();
    }
  }

  #runEvents(): void {
    for (const [index, event] of this.definition.events.entries()) {
      if (this.#firedEvents.has(index) || event.atTick > this.#tick) continue;
      this.#firedEvents.add(index);
      if (event.type === "spawn_hostile" && event.name) {
        const offset = event.offset ?? { x: 4, y: 0, z: 0 };
        this.spawn(event.name, {
          x: this.#position.x + offset.x,
          y: this.#position.y + offset.y,
          z: this.#position.z + offset.z,
        });
      } else if (event.type === "despawn_hostile") {
        this.#entities = this.#entities.filter((entity) => !entity.hostile);
      } else if (event.type === "break_shelter_block" && event.position) {
        this.#setBlock(event.position, "air");
      } else if (event.type === "weather" && event.weather) {
        this.#weather = event.weather;
      }
    }
  }

  #stepEntities(): void {
    for (const entity of this.#entities) {
      if (!entity.hostile) continue;
      const gap = distance(entity.position, this.#position);
      if (gap > 24) continue;
      if (gap > 1.5 && this.#tick % 6 === 0) {
        entity.position = {
          x:
            entity.position.x + Math.sign(this.#position.x - entity.position.x),
          y: this.#position.y,
          z:
            entity.position.z + Math.sign(this.#position.z - entity.position.z),
        };
      }
      const reach = entity.ranged ? 12 : 2.5;
      if (gap <= reach && this.#tick - (this.#lastAttackTick ?? -1000) >= 20) {
        this.#lastAttackTick = this.#tick;
        this.#damage(2);
      }
    }
  }

  /** Every health loss is recorded, so a neutral mob can become a threat. */
  #damage(amount: number): void {
    if (amount <= 0) return;
    this.#invalidate();
    this.#health = Math.max(0, this.#health - amount);
    this.#lastDamageTick = this.#tick;
  }

  #stepVitals(): void {
    if (this.#tick % 400 === 0) {
      if (this.#saturation > 0)
        this.#saturation = Math.max(0, this.#saturation - 1);
      else this.#food = Math.max(0, this.#food - 1);
    }
    if (this.#health > 0 && this.#food >= 18 && this.#tick % 80 === 0)
      this.#health = Math.min(20, this.#health + 1);
    const feet = this.blockAt(this.#position);
    if (feet?.hazard && feet.kind === "lava" && this.#tick % 10 === 0)
      this.#damage(4);
    if (!this.blockAt(this.#position)?.hazard && this.#air < 300)
      this.#air = Math.min(300, this.#air + 10);
    if (this.#health > 0 && this.#threatFree())
      this.#lastSafePosition = { ...this.#position };
  }

  #threatFree(): boolean {
    return !this.#entities.some(
      (entity) =>
        entity.hostile && distance(entity.position, this.#position) <= 8,
    );
  }

  // ---------------------------------------------------------------- snapshot

  snapshot(): WorldSnapshot {
    // Skills call this on every checkpoint. Scanning the world each time turns
    // a cheap safety check into the dominant cost, so the view is memoised
    // until the world actually changes.
    const cached = this.#snapshotCache;
    if (cached && cached.tick === this.#tick) return cached.value;
    const value = this.#buildSnapshot();
    this.#snapshotCache = { tick: this.#tick, value };
    return value;
  }

  #buildSnapshot(): WorldSnapshot {
    const inventory = this.inventory();
    const resources = this.findBlocks({
      kinds: ["wood", "stone", "coal_ore", "plant_food", "leaves"],
      maxDistance: 48,
      limit: 64,
    });
    const hazards = this.findBlocks({
      kinds: ["lava", "fire", "water", "cactus"],
      maxDistance: 16,
      limit: 32,
    });
    return {
      tick: this.#tick,
      timeOfDay: (this.definition.timeOfDay + this.#tick) % 24000,
      weather: this.#weather,
      dimension: "overworld",
      biome: this.definition.biome,
      lightLevel:
        (this.definition.timeOfDay + this.#tick) % 24000 < 12000 ? 15 : 4,
      position: { ...this.#position },
      health: this.#health,
      food: this.#food,
      saturation: this.#saturation,
      air: this.#air,
      armor: this.#armor,
      alive: this.#health > 0,
      statusEffects: [],
      inventory,
      freeSlots: Math.max(0, MAX_SLOTS - inventory.length),
      entities: this.#entities.map((entity) => this.#view(entity)),
      containers: [...this.#containers.keys()]
        .map((key) => {
          const [x, y, z] = key.split(",").map(Number) as [
            number,
            number,
            number,
          ];
          return this.containerAt({ x, y, z });
        })
        .filter((container): container is ContainerView => container !== null)
        .filter(
          (container) => distance(this.#position, container.position) <= 48,
        ),
      resources,
      hazards,
      stuck: false,
      diggableGround: this.#diggableGround(),
      lastSafePosition: this.#lastSafePosition,
      connected: this.#connected,
      recentlyDamaged:
        this.#lastDamageTick !== null &&
        this.#tick - this.#lastDamageTick <= DAMAGE_MEMORY_TICKS,
      lastDamageTick: this.#lastDamageTick,
    };
  }

  /** Mirrors the adapter: solid diggable ground beside Person. */
  #diggableGround(): boolean {
    const diggable = new Set(["dirt", "grass", "stone", "cobblestone"]);
    const here = this.#position;
    for (const [dx, dz] of [
      [1, 0],
      [-1, 0],
      [0, 1],
      [0, -1],
    ] as [number, number][])
      for (const dy of [0, 1]) {
        const block = this.blockAt({
          x: here.x + dx,
          y: here.y + dy,
          z: here.z + dz,
        });
        if (block && block.solid && diggable.has(block.kind)) return true;
      }
    return false;
  }

  #view(entity: FixtureEntityState): EntityView {
    return {
      entityId: entity.entityId,
      name: entity.name,
      position: { ...entity.position },
      distance: distance(this.#position, entity.position),
      hostile: entity.hostile,
      neutral: entity.neutral,
      passive: entity.passive,
      player: entity.player,
      villager: entity.villager,
      named: entity.named,
      tamed: entity.tamed,
      ranged: entity.ranged,
    };
  }

  inventory(): ItemStack[] {
    return [...this.#inventory]
      .filter(([, count]) => count > 0)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  findEntities(): EntityView[] {
    return this.#entities.map((entity) => this.#view(entity));
  }

  // ---------------------------------------------------------------- actions

  #requireConnection(): void {
    if (!this.#connected) throw new DisconnectedError();
  }

  /** A position Person can stand in: clear feet and head, solid floor, permitted. */
  #walkable(position: Position): boolean {
    const feet = definitionOf(this.#nameAt(position));
    const head = definitionOf(this.#nameAt({ ...position, y: position.y + 1 }));
    const floor = definitionOf(
      this.#nameAt({ ...position, y: position.y - 1 }),
    );
    if (feet.solid || head.solid || !floor.solid) return false;
    if (feet.hazard || head.hazard || floor.hazard) return false;
    return this.#guard ? this.#guard.canEnter(position) : true;
  }

  /**
   * Bounded best-first route search.
   *
   * Mineflayer routes around obstacles, so the fixture must too: a body that
   * only ever walked in straight lines would fail skills for reasons the real
   * one would not, and those failures would look like skill defects. The
   * heuristic keeps a long journey affordable, which matters because Person
   * genuinely does walk back across the map to reach its own workstations.
   */
  #findPath(target: Position, range: number): Position[] | null {
    const start = this.#position;
    const reached = (position: Position): boolean =>
      distance(position, target) <= Math.max(range, 0.5);
    if (reached(start)) return [];

    const startKey = positionKey(start);
    const cameFrom = new Map<string, string | null>([[startKey, null]]);
    const positions = new Map<string, Position>([[startKey, start]]);
    const cost = new Map<string, number>([[startKey, 0]]);
    const frontier: { key: string; estimate: number }[] = [
      { key: startKey, estimate: distance(start, target) },
    ];
    const steps: [number, number][] = [
      [1, 0],
      [-1, 0],
      [0, 1],
      [0, -1],
      [1, 1],
      [1, -1],
      [-1, 1],
      [-1, -1],
    ];

    const take = (): string | null => {
      if (frontier.length === 0) return null;
      let best = 0;
      for (let index = 1; index < frontier.length; index++)
        if (
          (frontier[index] as { estimate: number }).estimate <
          (frontier[best] as { estimate: number }).estimate
        )
          best = index;
      const [entry] = frontier.splice(best, 1);
      return entry ? entry.key : null;
    };

    const route = (key: string): Position[] => {
      const path: Position[] = [];
      let cursor: string | null = key;
      while (cursor && cursor !== startKey) {
        path.push(positions.get(cursor) as Position);
        cursor = cameFrom.get(cursor) ?? null;
      }
      return path.reverse();
    };

    for (let expansions = 0; expansions < 20000; expansions++) {
      const currentKey = take();
      if (currentKey === null) break;
      const current = positions.get(currentKey) as Position;
      if (reached(current)) return route(currentKey);
      const walked = cost.get(currentKey) ?? 0;
      for (const [dx, dz] of steps)
        for (const dy of [0, -1, 1]) {
          const next: Position = {
            x: current.x + dx,
            y: current.y + dy,
            z: current.z + dz,
          };
          const key = positionKey(next);
          const nextCost = walked + 1;
          if ((cost.get(key) ?? Number.POSITIVE_INFINITY) <= nextCost) continue;
          if (distance(next, target) > 160) continue;
          if (!this.#walkable(next)) continue;
          cost.set(key, nextCost);
          cameFrom.set(key, currentKey);
          positions.set(key, next);
          if (reached(next)) return route(key);
          frontier.push({ key, estimate: nextCost + distance(next, target) });
        }
    }
    return null;
  }

  async moveTo(position: Position, options: MoveOptions = {}): Promise<void> {
    this.#requireConnection();
    const range = options.range ?? 0;
    if (distance(this.#position, position) <= Math.max(range, 0.5)) return;
    const route = this.#findPath(position, range);
    if (route === null)
      throw new EmbodimentError(
        "no_route",
        `No walkable route to ${positionKey(position)}`,
      );
    const budget = options.maxTicks ?? 2400;
    let spent = 0;
    for (const step of route) {
      this.#assertEnter(step);
      this.#position = step;
      this.#advance(4);
      spent += 4;
      if (this.#health <= 0)
        throw new EmbodimentError("death", "Died while moving");
      if (spent > budget)
        throw new EmbodimentError(
          "navigation_timeout",
          "Route exceeded its tick budget",
        );
    }
  }

  async dig(position: Position): Promise<ItemStack[]> {
    this.#requireConnection();
    this.#assertModify(position);
    if (distance(this.#position, position) > 5)
      throw new EmbodimentError("out_of_reach", "Block is out of reach");
    const name = this.#nameAt(position);
    const definition = definitionOf(name);
    if (name === "air")
      throw new EmbodimentError("nothing_to_dig", "Block is already air");
    const toolTier = this.#bestPickaxeTier();
    if (definition.tool > toolTier)
      throw new EmbodimentError(
        "missing_tool",
        `${name} needs a better pickaxe`,
      );
    this.#setBlock(position, "air");
    this.#owned.delete(positionKey(position));
    this.#containers.delete(positionKey(position));
    const drops = definition.drops.map((drop) => ({ ...drop }));
    for (const drop of drops) this.#give(drop.name, drop.count);
    this.#advance(12);
    return drops;
  }

  #bestPickaxeTier(): number {
    const tiers: Record<string, number> = {
      wooden: 1,
      stone: 2,
      iron: 3,
      diamond: 4,
    };
    let best = 0;
    for (const name of this.#inventory.keys())
      if (name.endsWith("_pickaxe"))
        best = Math.max(best, tiers[name.replace("_pickaxe", "")] ?? 0);
    return best;
  }

  async place(position: Position, item: string): Promise<void> {
    this.#requireConnection();
    this.#assertModify(position);
    if ((this.#inventory.get(item) ?? 0) < 1)
      throw new EmbodimentError("missing_item", `No ${item} to place`);
    if (definitionOf(this.#nameAt(position)).solid)
      throw new EmbodimentError("occupied", "Placement would replace a block");
    if (distance(this.#position, position) > 5)
      throw new EmbodimentError(
        "out_of_reach",
        "Placement target is out of reach",
      );
    this.#take(item, 1);
    this.#setBlock(position, item);
    this.#owned.add(positionKey(position));
    if (item === "chest")
      this.#containers.set(positionKey(position), {
        kind: "chest",
        contents: new Map(),
        storageId: null,
      });
    this.#advance(6);
  }

  async craft(
    item: string,
    times: number,
    tablePosition: Position | null,
  ): Promise<CraftResult> {
    this.#requireConnection();
    const recipes = recipesFor(preferredWood(this.inventory()));
    const recipe = recipes[item];
    if (!recipe)
      throw new EmbodimentError("no_recipe", `No fixture recipe for ${item}`);
    if (recipe.requiresTable) {
      if (!tablePosition)
        throw new EmbodimentError("no_crafting_table", `${item} needs a table`);
      if (this.#nameAt(tablePosition) !== "crafting_table")
        throw new EmbodimentError(
          "no_crafting_table",
          "No crafting table at the given position",
        );
      if (distance(this.#position, tablePosition) > 5)
        throw new EmbodimentError(
          "out_of_reach",
          "Crafting table is out of reach",
        );
    }
    const consumed: ItemStack[] = [];
    for (let run = 0; run < times; run++) {
      for (const [ingredient, per] of Object.entries(recipe.inputs))
        if ((this.#inventory.get(ingredient) ?? 0) < per)
          throw new EmbodimentError(
            "missing_materials",
            `Missing ${ingredient}`,
          );
      for (const [ingredient, per] of Object.entries(recipe.inputs)) {
        this.#take(ingredient, per);
        consumed.push({ name: ingredient, count: per });
      }
      this.#give(recipe.item, recipe.output);
    }
    this.#advance(8 * times);
    return {
      produced: [{ name: recipe.item, count: recipe.output * times }],
      consumed,
    };
  }

  async smelt(
    input: string,
    times: number,
    furnacePosition: Position,
  ): Promise<CraftResult> {
    this.#requireConnection();
    if (this.#nameAt(furnacePosition) !== "furnace")
      throw new EmbodimentError(
        "no_furnace",
        "No furnace at the given position",
      );
    if (distance(this.#position, furnacePosition) > 5)
      throw new EmbodimentError("out_of_reach", "Furnace is out of reach");
    const output = SMELTING[input];
    if (!output)
      throw new EmbodimentError("no_recipe", `${input} cannot be smelted`);
    const available = this.#inventory.get(input) ?? 0;
    const runs = Math.min(times, available);
    if (runs <= 0)
      throw new EmbodimentError("missing_materials", `No ${input} to smelt`);
    const fuelName = [...this.#inventory.keys()].find((name) => isFuel(name));
    if (!fuelName) throw new EmbodimentError("no_fuel", "No fuel available");
    const perUnit = FUEL_VALUE[fuelName] ?? 1.5;
    const fuelNeeded = Math.max(1, Math.ceil(runs / perUnit));
    if ((this.#inventory.get(fuelName) ?? 0) < fuelNeeded)
      throw new EmbodimentError("no_fuel", "Not enough fuel");
    this.#take(fuelName, fuelNeeded);
    this.#take(input, runs);
    this.#give(output, runs);
    this.#advance(40 * runs);
    return {
      produced: [{ name: output, count: runs }],
      consumed: [
        { name: input, count: runs },
        { name: fuelName, count: fuelNeeded },
      ],
    };
  }

  async consume(item: string): Promise<void> {
    this.#requireConnection();
    if ((this.#inventory.get(item) ?? 0) < 1)
      throw new EmbodimentError("missing_item", `No ${item} to eat`);
    const value = FOOD_VALUE[item] ?? 2;
    this.#take(item, 1);
    this.#food = Math.min(20, this.#food + value);
    this.#saturation = Math.min(20, this.#saturation + value / 2);
    this.#advance(32);
  }

  async attack(entityId: number): Promise<void> {
    this.#requireConnection();
    const entity = this.#entities.find(
      (candidate) => candidate.entityId === entityId,
    );
    if (!entity) throw new EmbodimentError("no_target", "Entity is gone");
    if (this.#guard && !this.#guard.canTargetEntity(this.#view(entity)))
      throw new EmbodimentError(
        "forbidden_target",
        `Targeting ${entity.name} is not permitted`,
      );
    if (distance(this.#position, entity.position) > 4)
      throw new EmbodimentError("out_of_reach", "Target is out of reach");
    entity.health -= this.#inventory.has("stone_axe") ? 5 : 3;
    this.#advance(12);
    if (entity.health <= 0) {
      this.#invalidate();
      this.#entities = this.#entities.filter(
        (candidate) => candidate.entityId !== entityId,
      );
      const drop = PASSIVE_ANIMALS[entity.name]?.drop;
      if (drop) this.#give(drop, 2);
    }
  }

  async deposit(position: Position, items: ItemStack[]): Promise<ItemStack[]> {
    this.#requireConnection();
    const container = this.#containers.get(positionKey(position));
    if (!container)
      throw new EmbodimentError(
        "no_container",
        "No container at that position",
      );
    if (container.storageId === null)
      throw new EmbodimentError(
        "existing_container_deposit_forbidden",
        "The fixture refuses deposits into containers Person did not place",
      );
    this.#invalidate();
    const moved: ItemStack[] = [];
    for (const item of items) {
      const available = Math.min(
        item.count,
        this.#inventory.get(item.name) ?? 0,
      );
      if (available <= 0) continue;
      this.#take(item.name, available);
      container.contents.set(
        item.name,
        (container.contents.get(item.name) ?? 0) + available,
      );
      moved.push({ name: item.name, count: available });
    }
    this.#advance(10);
    return moved;
  }

  async withdraw(position: Position, items: ItemStack[]): Promise<ItemStack[]> {
    this.#requireConnection();
    const container = this.#containers.get(positionKey(position));
    if (!container)
      throw new EmbodimentError(
        "no_container",
        "No container at that position",
      );
    this.#invalidate();
    const moved: ItemStack[] = [];
    for (const item of items) {
      const available = Math.min(
        item.count,
        container.contents.get(item.name) ?? 0,
      );
      if (available <= 0) continue;
      container.contents.set(
        item.name,
        (container.contents.get(item.name) ?? 0) - available,
      );
      this.#give(item.name, available);
      moved.push({ name: item.name, count: available });
    }
    this.#advance(10);
    return moved;
  }

  async waitTicks(ticks: number): Promise<void> {
    this.#requireConnection();
    this.#advance(ticks);
  }

  registerOwnedStorage(position: Position, storageId: string): void {
    this.#invalidate();
    const container = this.#containers.get(positionKey(position));
    if (container) container.storageId = storageId;
    this.#owned.add(positionKey(position));
  }

  // ---------------------------------------------------------------- test hooks

  spawn(
    name: string,
    position: Position,
    options: Partial<FixtureEntityState> = {},
  ): FixtureEntityState {
    this.#invalidate();
    const passive = name in PASSIVE_ANIMALS;
    const entity: FixtureEntityState = {
      entityId: this.#nextEntityId++,
      name,
      position: { ...position },
      health: options.health ?? PASSIVE_ANIMALS[name]?.health ?? 20,
      hostile: HOSTILES.has(name),
      neutral: options.neutral ?? NEUTRALS.has(name),
      passive,
      player: options.player ?? name === "player",
      villager: options.villager ?? name === "villager",
      named: options.named ?? false,
      tamed: options.tamed ?? false,
      ranged: RANGED_HOSTILES.has(name),
    };
    this.#entities.push(entity);
    return entity;
  }

  despawnHostiles(): void {
    this.#invalidate();
    this.#entities = this.#entities.filter((entity) => !entity.hostile);
  }

  give(name: string, count: number): void {
    this.#give(name, count);
  }

  setVitals(
    vitals: Partial<{ health: number; food: number; air: number }>,
  ): void {
    this.#invalidate();
    if (vitals.health !== undefined) this.#health = vitals.health;
    if (vitals.food !== undefined) this.#food = vitals.food;
    if (vitals.air !== undefined) this.#air = vitals.air;
  }

  setBlock(position: Position, name: string): void {
    this.#setBlock(position, name);
  }

  get tick(): number {
    return this.#tick;
  }

  #give(name: string, count: number): void {
    this.#invalidate();
    this.#inventory.set(name, (this.#inventory.get(name) ?? 0) + count);
  }

  #take(name: string, count: number): void {
    this.#invalidate();
    const held = this.#inventory.get(name) ?? 0;
    if (held < count)
      throw new EmbodimentError("missing_item", `Not enough ${name}`);
    if (held === count) this.#inventory.delete(name);
    else this.#inventory.set(name, held - count);
  }
}

export { BLOCKS };
