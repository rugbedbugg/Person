import path from "node:path";
import {
  ConfigError,
  readConfigDocument,
  parseConfigDocument,
  validateConfig,
  type CoreConfig,
} from "#config";
import type { Experience } from "#protocol";
import { contains, intersects, type Box, type Position } from "./geometry.ts";
import { upgradeConfigDocument } from "./legacy.ts";

/** The environment kind this profile implements. */
export const MINECRAFT = "minecraft";
/** The two bodies of the one Minecraft environment (ADR 0025). */
export const MINECRAFT_EMBODIMENTS = ["fixture", "mineflayer"] as const;
export type MinecraftEmbodiment = (typeof MINECRAFT_EMBODIMENTS)[number];
export type MinecraftDifficulty = "peaceful" | "normal";

export interface ContainerPermissions {
  existing: { withdraw: boolean; deposit: false };
  owned: { withdraw: boolean; deposit: boolean };
}

export interface Permissions {
  containers: ContainerPermissions;
  hunting: {
    passiveUnnamedAnimals: boolean;
    namedAnimals: false;
    tamedAnimals: false;
  };
  players: { combat: false };
  villagers: { harm: false };
  building: { enabled: boolean };
  protectedAreas: { enforcement: "strict" };
}

/**
 * A Person configuration in the Minecraft environment: the core, plus the
 * sections Minecraft owns (`schemas/config.schema.json`).
 */
export interface MinecraftConfig extends Omit<
  CoreConfig,
  "environment" | "runtime"
> {
  environment: { kind: "minecraft"; difficulty?: MinecraftDifficulty };
  runtime: CoreConfig["runtime"] & { embodiment: MinecraftEmbodiment };
  server?: { host: string; port: number; version: "1.16.1" };
  bot?: { username: string; auth: "offline" };
  authorization?: Record<string, boolean>;
  world: {
    home: Position;
    exploration: Box;
    resourceAreas: Box[];
    protectedAreas: Box[];
  };
  permissions: Permissions;
}

const wellFormed = (box: Box): boolean =>
  box.min.x <= box.max.x && box.min.y <= box.max.y && box.min.z <= box.max.z;

/**
 * Validates a Minecraft configuration: the core and Minecraft schemas
 * together, then Minecraft's own semantic checks.
 *
 * Schema validation alone is not enough: the safety-relevant invariants are
 * geometric (home inside the exploration bounds, protected areas not
 * overlapping what Person is told to use). Those are checked here, by the
 * environment that owns the geometry, for the runtime that owns physical
 * permission. A configuration written for an earlier version is upgraded
 * first (`legacy.ts`), and never written back.
 */
export function validateMinecraftConfig(
  input: unknown,
  baseDirectory: string = process.cwd(),
): MinecraftConfig {
  const config = validateConfig(
    upgradeConfigDocument(input).document,
    baseDirectory,
  ) as unknown as MinecraftConfig;
  if (config.environment.kind !== MINECRAFT)
    throw new ConfigError("Configuration is not usable", [
      `/environment/kind is ${JSON.stringify(config.environment.kind)}, not minecraft`,
    ]);
  const problems: string[] = [];

  const { world } = config;
  if (!wellFormed(world.exploration))
    problems.push("/world/exploration has reversed bounds");
  for (const [index, area] of world.resourceAreas.entries()) {
    if (!wellFormed(area))
      problems.push(`/world/resourceAreas/${index} has reversed bounds`);
    if (
      !contains(world.exploration, area.min) ||
      !contains(world.exploration, area.max)
    )
      problems.push(
        `/world/resourceAreas/${index} must fit inside the exploration bounds`,
      );
  }
  for (const [index, area] of world.protectedAreas.entries())
    if (!wellFormed(area))
      problems.push(`/world/protectedAreas/${index} has reversed bounds`);
  if (!contains(world.exploration, world.home))
    problems.push("/world/home must lie inside the exploration bounds");

  const homeFootprint: Box = {
    min: { x: world.home.x - 2, y: world.home.y - 1, z: world.home.z - 2 },
    max: { x: world.home.x + 2, y: world.home.y + 3, z: world.home.z + 2 },
  };
  for (const [index, area] of world.protectedAreas.entries())
    if (intersects(area, homeFootprint))
      problems.push(
        `/world/protectedAreas/${index} overlaps the home footprint; Person would be unable to build where it is told to live`,
      );

  if (config.runtime.embodiment === "mineflayer") {
    if (!config.server)
      problems.push(
        "/server is required when runtime.embodiment is mineflayer",
      );
    if (!config.bot)
      problems.push("/bot is required when runtime.embodiment is mineflayer");
    if (!config.authorization)
      problems.push(
        "/authorization is required when runtime.embodiment is mineflayer",
      );
  }

  if (config.permissions.containers.existing.deposit !== false)
    problems.push("/permissions/containers/existing/deposit must be false");

  if (problems.length)
    throw new ConfigError("Configuration is not usable", problems);
  return config;
}

export function parseMinecraftConfigText(
  text: string,
  filename: string,
  baseDirectory: string,
): MinecraftConfig {
  return validateMinecraftConfig(
    parseConfigDocument(text, filename),
    baseDirectory,
  );
}

export function loadMinecraftConfig(filename: string): MinecraftConfig {
  const { document, absolute } = readConfigDocument(filename);
  return validateMinecraftConfig(document, path.dirname(absolute));
}

/**
 * The experience stream a configuration lives in. The difficulty is the
 * environment variant for the Mineflayer body; the fixture world defines its
 * own dynamics and has none.
 */
export function experienceOf(config: MinecraftConfig): Experience {
  return {
    context: "lived",
    environmentKind: MINECRAFT,
    embodimentKind: config.runtime.embodiment,
    environmentVariant:
      config.runtime.embodiment === "mineflayer"
        ? (config.environment.difficulty ?? null)
        : null,
  };
}

/** A short human-readable name for the stream, for reports and logs. */
export function describeExperience(experience: Experience): string {
  const variant = experience.environmentVariant
    ? `/${experience.environmentVariant}`
    : "";
  return `${experience.context}:${experience.environmentKind}/${experience.embodimentKind}${variant}`;
}
