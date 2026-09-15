import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
import { positionKey, type Position } from "#config";

/**
 * Ownership provenance for a container Person placed itself.
 *
 * Deposit authorisation requires one of these records. A container Person did
 * not create has no record, so there is no code path that can authorise a
 * deposit into it.
 */
export interface StorageRecord {
  storageId: string;
  worldId: string;
  dimension: string;
  position: Position;
  createdByPerson: string;
  creationEvent: string;
  homeId: string;
  lastVerified: string;
}

export interface HomeRecord {
  homeId: string;
  position: Position;
  shelterState: "none" | "partial" | "complete" | "breached";
  bedKnown: boolean;
}

interface PersistedState {
  version: 1;
  worldId: string;
  personId: string;
  home: HomeRecord;
  storage: StorageRecord[];
  placedBlocks: string[];
  furnacePosition: Position | null;
  craftingTablePosition: Position | null;
}

/**
 * Durable, runtime-owned world facts: where home is, what Person built, and
 * which containers it owns. Written atomically so a crash mid-write cannot
 * leave a half-parsed provenance file behind.
 */
export class WorldMemory {
  readonly worldId: string;
  readonly personId: string;
  home: HomeRecord;
  furnacePosition: Position | null = null;
  craftingTablePosition: Position | null = null;
  readonly storage = new Map<string, StorageRecord>();
  readonly placedBlocks = new Set<string>();
  #file: string | null = null;

  constructor(worldId: string, personId: string, home: Position) {
    this.worldId = worldId;
    this.personId = personId;
    this.home = {
      homeId: "home_primary",
      position: home,
      shelterState: "none",
      bedKnown: false,
    };
  }

  static load(
    directory: string,
    worldId: string,
    personId: string,
    home: Position,
  ): WorldMemory {
    const memory = new WorldMemory(worldId, personId, home);
    memory.#file = path.join(directory, `world-${worldId}-${personId}.json`);
    try {
      const saved: PersistedState = JSON.parse(
        readFileSync(memory.#file, "utf8"),
      );
      if (
        saved.version !== 1 ||
        saved.worldId !== worldId ||
        saved.personId !== personId
      )
        return memory;
      memory.home = saved.home;
      memory.furnacePosition = saved.furnacePosition;
      memory.craftingTablePosition = saved.craftingTablePosition;
      for (const record of saved.storage)
        memory.storage.set(record.storageId, record);
      for (const key of saved.placedBlocks) memory.placedBlocks.add(key);
    } catch {
      // A missing or unreadable file is simply an unremembered world. The
      // evidence journal, not this cache, is the authoritative history.
    }
    return memory;
  }

  save(): void {
    if (!this.#file) return;
    const state: PersistedState = {
      version: 1,
      worldId: this.worldId,
      personId: this.personId,
      home: this.home,
      storage: [...this.storage.values()],
      placedBlocks: [...this.placedBlocks],
      furnacePosition: this.furnacePosition,
      craftingTablePosition: this.craftingTablePosition,
    };
    mkdirSync(path.dirname(this.#file), { recursive: true, mode: 0o700 });
    const temporary = `${this.#file}.tmp`;
    writeFileSync(temporary, `${JSON.stringify(state, null, 2)}\n`, {
      mode: 0o600,
    });
    renameSync(temporary, this.#file);
  }

  recordPlacement(position: Position): void {
    this.placedBlocks.add(positionKey(position));
  }

  isOwnedBlock(position: Position): boolean {
    return this.placedBlocks.has(positionKey(position));
  }

  recordStorage(
    position: Position,
    creationEvent: string,
    dimension: string,
  ): StorageRecord {
    const storageId = `storage_${positionKey(position).replace(/,/g, "_")}`;
    const record: StorageRecord = {
      storageId,
      worldId: this.worldId,
      dimension,
      position,
      createdByPerson: this.personId,
      creationEvent,
      homeId: this.home.homeId,
      lastVerified: new Date().toISOString(),
    };
    this.storage.set(storageId, record);
    this.recordPlacement(position);
    return record;
  }

  storageAt(position: Position): StorageRecord | null {
    const key = positionKey(position);
    for (const record of this.storage.values())
      if (positionKey(record.position) === key) return record;
    return null;
  }

  get ownedStorage(): StorageRecord[] {
    return [...this.storage.values()];
  }
}
