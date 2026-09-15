import type { SkillImplementation } from "../execution.ts";
import { craftingSkills } from "./crafting.ts";
import { emergencySkills } from "./emergency.ts";
import { foodSkills } from "./food.ts";
import { resourceSkills } from "./resources.ts";
import { shelterSkills } from "./shelter.ts";
import { storageSkills } from "./storage.ts";

/**
 * Every skill in the library has a real implementation here. There are no
 * placeholder success returns: each one drives the embodiment port, and the
 * fixture world implements that port exactly as the Mineflayer adapter does.
 */
export const SKILL_IMPLEMENTATIONS: Readonly<
  Record<string, SkillImplementation>
> = Object.freeze({
  ...emergencySkills,
  ...foodSkills,
  ...resourceSkills,
  ...craftingSkills,
  ...shelterSkills,
  ...storageSkills,
});

export const implementedSkillIds = (): string[] =>
  Object.keys(SKILL_IMPLEMENTATIONS).sort();
