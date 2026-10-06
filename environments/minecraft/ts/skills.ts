import type { SkillSpec } from "#skills";

/**
 * The Minecraft skill vocabulary, as types (ADR 0025). The same lists are in
 * `skills/vocabulary.json`, which the generic skill registry validates every
 * Minecraft SkillSpec against; a test keeps the two in step.
 */
export type MinecraftSkillCategory =
  | "emergency"
  | "food"
  | "resources"
  | "crafting"
  | "shelter"
  | "storage"
  | "perception";

export type MinecraftPermission =
  | "harvest_resource"
  | "mine_resource"
  | "build"
  | "hunt_passive_animal"
  | "place_owned_storage"
  | "deposit_owned_storage"
  | "withdraw_owned_storage"
  | "withdraw_existing_container"
  | "emergency_dig"
  | "craft"
  | "consume";

export type MinecraftCompletionEvidence =
  | "inventory_delta"
  | "harvested_blocks"
  | "placed_blocks"
  | "crafted_items"
  | "smelted_items"
  | "position_reached"
  | "threat_clearance"
  | "vitals_delta"
  | "container_transfer"
  | "shelter_verified"
  | "elapsed_ticks";

/** A SkillSpec of the Minecraft library, with its vocabulary typed. */
export type MinecraftSkillSpec = SkillSpec<
  MinecraftSkillCategory,
  MinecraftPermission,
  MinecraftCompletionEvidence
>;
