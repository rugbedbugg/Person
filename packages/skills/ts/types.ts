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

/**
 * An environment's skill vocabulary (its `skills/vocabulary.json`, ADR 0025):
 * what its specs may name as a category, a permission or a completion
 * evidence kind, the bounds on cost limits, and how each planning fact may be
 * used. The generic registry checks every spec against it.
 */
export interface SkillVocabulary {
  description: string;
  categories: string[];
  permissions: string[];
  completionEvidence: string[];
  limits: { maxTicks: number; maxDistance: number; minHealth: number };
  factClasses: {
    /** Only current perception establishes these; no skill produces them. */
    evidence: string[];
    tracked: string[];
    evaluable: string[];
    unobservable: string[];
    action: string[];
  };
  failures: { notAttempted: string[] };
  planning?: { plannableEmergency: string[]; recovery: string[] };
  unremarkable?: string[];
  roles?: Record<string, string>;
}

/**
 * One bounded capability. Generic: the category, permission and evidence
 * vocabularies are type parameters an environment fills in.
 */
export interface SkillSpec<
  Category extends string = string,
  RequiredPermission extends string = string,
  Evidence extends string = string,
> {
  id: string;
  version: number;
  category: Category;
  summary: string;
  parameters: Record<string, ParameterSpec>;
  preconditions: Condition[];
  expectedEffects: Effect[];
  possibleFailures: string[];
  requiredPermissions: RequiredPermission[];
  costLimits: { maxTicks: number; maxDistance: number; minHealth: number };
  interruptionPolicy: "preemptible" | "atomic_step" | "uninterruptible";
  completionEvidence: Evidence[];
  risk: number;
  emergency: boolean;
}
