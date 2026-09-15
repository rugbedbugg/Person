import { distance, positionKey, type Position } from "#config";
import type { ItemStack } from "#protocol";
import {
  SkillFailure,
  itemCount,
  type SkillContext,
  type SkillImplementation,
} from "../execution.ts";
import { isCoal, isEdible, isLog, isStone } from "../materials.ts";
import { approach } from "../navigate.ts";
import { placementSite } from "./crafting.ts";
import type { ContainerView } from "../../embodiment/types.ts";

type Category = "food" | "wood" | "stone" | "coal" | "any";

const MATCHERS: Record<Category, (name: string) => boolean> = {
  food: isEdible,
  wood: isLog,
  stone: isStone,
  coal: isCoal,
  any: () => true,
};

/** Containers Person placed itself, nearest first. */
function ownedContainers(context: SkillContext): ContainerView[] {
  const origin = context.snapshot().position;
  const known = new Set(
    context.memory.ownedStorage.map((record) => positionKey(record.position)),
  );
  return context
    .snapshot()
    .containers.filter(
      (container) =>
        container.storageId !== null ||
        known.has(positionKey(container.position)),
    )
    .sort(
      (a, b) => distance(origin, a.position) - distance(origin, b.position),
    );
}

/**
 * Place a Person-owned chest beside the active home and record its provenance.
 *
 * The provenance record is what later authorises a deposit. A container Person
 * did not place never acquires one.
 */
export const placeOwnedChest: SkillImplementation = async (context) => {
  if (itemCount(context.snapshot().inventory, "chest") === 0)
    throw new SkillFailure(
      "missing_materials",
      "INVALIDATED",
      "No chest to place",
    );
  const home = context.home();
  const site = placementSite(context, home, 3);
  if (!site)
    throw new SkillFailure(
      "no_placement_site",
      "FAILED",
      "No permitted chest site",
    );
  const verdict = context.permissions.mayBuild(site);
  if (!verdict.allowed)
    throw new SkillFailure(
      "protected_area",
      "INVALIDATED",
      `Chest placement denied: ${verdict.reason}`,
    );
  await approach(context, site);
  context.checkpoint();
  await context.embodiment.place(site, "chest");
  const record = context.memory.recordStorage(
    site,
    `place_owned_chest@tick:${context.snapshot().tick}`,
    context.snapshot().dimension,
  );
  context.embodiment.registerOwnedStorage(site, record.storageId);
  context.effect("owned_storage_established");
  context.note("placed_blocks", { chest: positionKey(site) });
  context.note("container_transfer", {
    storage_id: record.storageId,
    created: true,
  });
};

/** Deposit surplus into an owned chest, keeping a working reserve. */
export const depositOwnedStorage: SkillImplementation = async (context) => {
  const category = context.text("category") as Category;
  const keep = context.number("keep");
  const containers = ownedContainers(context);
  if (containers.length === 0)
    throw new SkillFailure(
      "no_owned_storage",
      "INVALIDATED",
      "No Person-owned container exists",
    );
  const container = containers[0];
  if (!container)
    throw new SkillFailure(
      "no_owned_storage",
      "INVALIDATED",
      "No container found",
    );

  const verdict = context.permissions.mayDeposit(container);
  if (!verdict.allowed)
    throw new SkillFailure(
      verdict.reason === "existing_container_deposit_forbidden"
        ? "no_owned_storage"
        : "no_owned_storage",
      "INVALIDATED",
      `Deposit denied: ${verdict.reason}`,
    );

  const matcher = MATCHERS[category] ?? MATCHERS.any;
  const surplus: ItemStack[] = context
    .snapshot()
    .inventory.filter((item) => matcher(item.name) && item.count > keep)
    .map((item) => ({ name: item.name, count: item.count - keep }));
  if (surplus.length === 0)
    throw new SkillFailure(
      "nothing_to_deposit",
      "FAILED",
      "Nothing above the keep threshold",
    );

  await approach(context, container.position);
  context.checkpoint();
  const moved = await context.embodiment.deposit(container.position, surplus);
  if (moved.length === 0)
    throw new SkillFailure(
      "container_full",
      "FAILED",
      "The container accepted nothing",
    );
  const record = context.memory.storageAt(container.position);
  if (record) record.lastVerified = new Date().toISOString();
  context.effect("surplus_stored");
  context.note("container_transfer", {
    storage_id: container.storageId ?? record?.storageId ?? "unknown",
    deposited: moved.reduce((total, item) => total + item.count, 0),
  });
  context.note("inventory_delta", { deposited: moved.length });
};

/** Withdraw from an owned chest. */
export const withdrawOwnedStorage: SkillImplementation = async (context) => {
  const category = context.text("category") as Category;
  const amount = context.number("amount");
  const containers = ownedContainers(context);
  if (containers.length === 0)
    throw new SkillFailure(
      "no_owned_storage",
      "INVALIDATED",
      "No Person-owned container exists",
    );
  const container = containers[0];
  if (!container)
    throw new SkillFailure(
      "no_owned_storage",
      "INVALIDATED",
      "No container found",
    );
  const verdict = context.permissions.mayWithdraw(container);
  if (!verdict.allowed)
    throw new SkillFailure(
      "no_owned_storage",
      "INVALIDATED",
      `Withdrawal denied: ${verdict.reason}`,
    );

  await approach(context, container.position);
  context.checkpoint();
  const matcher = MATCHERS[category] ?? MATCHERS.any;
  // The cached view is empty until something has been transferred, so the
  // contents have to be read from the container itself before choosing.
  const live = await context.embodiment.inspectContainer(container.position);
  const wanted: ItemStack[] = (live?.contents ?? [])
    .filter((item) => matcher(item.name))
    .map((item) => ({ name: item.name, count: Math.min(amount, item.count) }));
  if (wanted.length === 0)
    throw new SkillFailure(
      "empty_container",
      "FAILED",
      "The container holds nothing of that kind",
    );
  const moved = await context.embodiment.withdraw(container.position, wanted);
  if (moved.length === 0)
    throw new SkillFailure(
      "empty_container",
      "FAILED",
      "The withdrawal moved nothing",
    );
  context.effect("withdrew_from_owned_storage");
  context.note("container_transfer", {
    storage_id: container.storageId ?? "unknown",
    withdrawn: moved.reduce((total, item) => total + item.count, 0),
  });
  context.note("inventory_delta", { withdrawn: moved.length });
};

/**
 * Withdraw from a pre-existing container that configuration permits.
 * This skill has no deposit path at all; that is deliberate.
 */
export const lootPermittedContainer: SkillImplementation = async (context) => {
  const amount = context.number("amount");
  const origin = context.snapshot().position;
  const candidates = context
    .snapshot()
    .containers.filter((container) => container.storageId === null)
    .filter((container) => context.permissions.mayWithdraw(container).allowed)
    .sort(
      (a, b) => distance(origin, a.position) - distance(origin, b.position),
    );
  const container = candidates[0];
  if (!container)
    throw new SkillFailure(
      "no_permitted_container",
      "UNREACHABLE",
      "No permitted pre-existing container is in range",
    );

  await approach(context, container.position);
  context.checkpoint();
  const live = await context.embodiment.inspectContainer(container.position);
  const wanted: ItemStack[] = (live?.contents ?? []).map((item) => ({
    name: item.name,
    count: Math.min(amount, item.count),
  }));
  if (wanted.length === 0)
    throw new SkillFailure(
      "empty_container",
      "FAILED",
      "The container is empty",
    );
  const moved = await context.embodiment.withdraw(container.position, wanted);
  if (moved.length === 0)
    throw new SkillFailure(
      "empty_container",
      "FAILED",
      "The withdrawal moved nothing",
    );
  context.effect("looted_permitted_container");
  context.note("container_transfer", {
    provenance: "existing",
    withdrawn: moved.reduce((total, item) => total + item.count, 0),
  });
  context.note("inventory_delta", { withdrawn: moved.length });
};

export const storageSkills: Record<string, SkillImplementation> = {
  place_owned_chest: placeOwnedChest,
  deposit_owned_storage: depositOwnedStorage,
  withdraw_owned_storage: withdrawOwnedStorage,
  loot_permitted_container: lootPermittedContainer,
};

export type { Position };
