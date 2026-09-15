import { distance, type Position } from "#config";
import {
  SkillFailure,
  type SkillContext,
  type SkillImplementation,
} from "../execution.ts";
import {
  FOOD_VALUE,
  SMELTING,
  isEdible,
  isFuel,
  isRawFood,
  tally,
} from "../materials.ts";
import { approach } from "../navigate.ts";

/**
 * Take raw food from unnamed, untamed passive animals only.
 *
 * Every candidate passes through the permission gate, which refuses players,
 * villagers, named animals and tamed animals outright. There is no parameter
 * or configuration that widens this set.
 */
export const huntSafePassiveAnimals: SkillImplementation = async (context) => {
  const target = context.number("target_amount");
  const maxDistance = context.number("max_distance");
  const rawHeld = (): number =>
    [...tally(context.snapshot().inventory)].reduce(
      (total, [name, count]) => total + (isRawFood(name) ? count : 0),
      0,
    );
  const before = rawHeld();
  const refused = new Set<number>();
  let kills = 0;

  while (rawHeld() - before < target) {
    context.checkpoint();
    const snapshot = context.snapshot();
    const candidates = snapshot.entities
      .filter(
        (entity) =>
          entity.distance <= maxDistance && !refused.has(entity.entityId),
      )
      .filter((entity) => context.permissions.mayHunt(entity).allowed)
      .sort((a, b) => a.distance - b.distance);
    if (candidates.length === 0) break;
    const animal = candidates[0];
    if (!animal) break;
    try {
      await approach(context, animal.position);
      context.checkpoint();
      const live = context
        .snapshot()
        .entities.find((entity) => entity.entityId === animal.entityId);
      if (!live) {
        refused.add(animal.entityId);
        continue;
      }
      const verdict = context.permissions.mayHunt(live);
      if (!verdict.allowed)
        throw new SkillFailure(
          "no_permitted_target",
          "INVALIDATED",
          verdict.reason,
        );
      const lastSeen: Position = { ...live.position };
      for (let swing = 0; swing < 12; swing++) {
        context.checkpoint();
        if (
          !context
            .snapshot()
            .entities.some((e) => e.entityId === animal.entityId)
        )
          break;
        await context.embodiment.attack(animal.entityId);
      }
      if (
        context.snapshot().entities.some((e) => e.entityId === animal.entityId)
      ) {
        refused.add(animal.entityId);
        continue;
      }
      kills += 1;
      // Walk over the drop so the pickup is attributed to this skill.
      try {
        await context.embodiment.moveTo(lastSeen, { range: 1, maxTicks: 120 });
      } catch {
        // The drop may already have been collected on approach.
      }
    } catch (error) {
      if (error instanceof SkillFailure && error.status === "INVALIDATED")
        throw error;
      refused.add(animal.entityId);
    }
  }

  const gained = rawHeld() - before;
  if (gained <= 0) {
    if (kills > 0)
      throw new SkillFailure(
        "inventory_full",
        "FAILED",
        "Kills produced no food",
      );
    throw new SkillFailure(
      "no_permitted_target",
      "UNREACHABLE",
      "No unnamed untamed passive animal was reachable",
    );
  }
  context.effect("raw_food_increased");
  context.note("inventory_delta", { gained, kills });
  context.note("vitals_delta", { health: context.snapshot().health });
};

/** Smelt raw food at a furnace Person placed itself. */
export const cookFood: SkillImplementation = async (context) => {
  const target = context.number("target_amount");
  const snapshot = context.snapshot();
  const furnace =
    context.memory.furnacePosition ??
    context.embodiment
      .findBlocks({ kinds: ["furnace"], maxDistance: 16, limit: 4 })
      .find((block) => block.ownedByPerson)?.position ??
    null;
  if (!furnace)
    throw new SkillFailure(
      "no_furnace",
      "INVALIDATED",
      "No owned furnace is available",
    );

  const raw = snapshot.inventory.find(
    (item) => isRawFood(item.name) && item.name in SMELTING,
  );
  if (!raw)
    throw new SkillFailure("no_raw_food", "INVALIDATED", "Nothing to cook");
  const fuel = snapshot.inventory.find((item) => isFuel(item.name));
  if (!fuel)
    throw new SkillFailure("no_fuel", "INVALIDATED", "No fuel for the furnace");

  await approach(context, furnace);
  context.checkpoint();
  const times = Math.min(target, raw.count);
  const result = await context.embodiment.smelt(raw.name, times, furnace);
  if (result.produced.length === 0)
    throw new SkillFailure("no_fuel", "FAILED", "The furnace produced nothing");
  context.effect("cooked_food_increased");
  context.note("smelted_items", {
    input: raw.name,
    output: result.produced[0]?.name ?? SMELTING[raw.name] ?? "unknown",
    times,
  });
  context.note("inventory_delta", {
    cooked: result.produced.reduce((n, i) => n + i.count, 0),
  });
};

/** Eat until the hunger target is reached or edible food runs out. */
export const eatToTarget: SkillImplementation = async (context) => {
  const target = context.number("target_food");
  const start = context.snapshot().food;
  if (start >= target) {
    context.effect("already_fed");
    context.note("vitals_delta", { food: start, eaten: 0 });
    return;
  }
  let eaten = 0;
  for (let bite = 0; bite < 12; bite++) {
    context.checkpoint();
    const snapshot = context.snapshot();
    if (snapshot.food >= target) break;
    // Prefer the smallest food that still closes the gap, so large meals are
    // not wasted on a nearly full hunger bar.
    const options = snapshot.inventory
      .filter((item) => isEdible(item.name))
      .sort((a, b) => (FOOD_VALUE[a.name] ?? 1) - (FOOD_VALUE[b.name] ?? 1));
    const needed = target - snapshot.food;
    const choice =
      options.find((item) => (FOOD_VALUE[item.name] ?? 1) >= needed) ??
      options.at(-1) ??
      null;
    if (!choice) break;
    await context.embodiment.consume(choice.name);
    eaten += 1;
  }
  const end = context.snapshot();
  if (eaten === 0)
    throw new SkillFailure("no_food", "INVALIDATED", "No edible food held");
  context.effect("food_level_raised");
  context.note("vitals_delta", {
    food_before: start,
    food_after: end.food,
    eaten,
  });
  context.note("inventory_delta", { eaten });
};

export const foodSkills: Record<string, SkillImplementation> = {
  hunt_safe_passive_animals: huntSafePassiveAnimals,
  cook_food: cookFood,
  eat_to_target: eatToTarget,
};

export { distance };
