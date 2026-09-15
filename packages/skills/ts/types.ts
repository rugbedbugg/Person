export type ConditionOp = ">=" | "<=" | "==" | ">" | "<";
export type EffectOp = "+=" | "-=" | "=" | "max";

export interface Condition {
  fact: string;
  op: ConditionOp;
  value: number;
}

export interface Effect {
  fact: string;
  op: EffectOp;
  value: number;
  /** Parameter whose value replaces `value` when the invocation supplies one. */
  scalesWith?: string;
}

export interface ParameterSpec {
  type: "integer" | "number" | "boolean" | "string";
  minimum?: number;
  maximum?: number;
  enum?: string[];
  default: number | string | boolean;
  description?: string;
}

export type SkillCategory =
  "emergency" | "food" | "resources" | "crafting" | "shelter" | "storage";

export type Permission =
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

export interface SkillSpec {
  id: string;
  version: number;
  category: SkillCategory;
  summary: string;
  parameters: Record<string, ParameterSpec>;
  preconditions: Condition[];
  expectedEffects: Effect[];
  possibleFailures: string[];
  requiredPermissions: Permission[];
  costLimits: { maxTicks: number; maxDistance: number; minHealth: number };
  interruptionPolicy: "preemptible" | "atomic_step" | "uninterruptible";
  completionEvidence: string[];
  risk: number;
  emergency: boolean;
}
