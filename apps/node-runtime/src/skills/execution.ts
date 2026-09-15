import type {
  CostLimits,
  ItemStack,
  Position,
  TerminalStatus,
} from "#protocol";
import type { SkillSpec } from "#skills";
import type { Embodiment, WorldSnapshot } from "../embodiment/types.ts";
import type { PermissionGate } from "../safety/permissions.ts";
import type {
  EmergencyAssessment,
  SafetyKernel,
} from "../safety/safety-kernel.ts";
import type { WorldMemory } from "../runtime/world-memory.ts";

export type EvidenceValue = number | string | boolean | null;

/** Raised when a skill cannot achieve its contract. Carries the terminal state. */
export class SkillFailure extends Error {
  readonly status: TerminalStatus;
  readonly reason: string;
  constructor(
    reason: string,
    status: TerminalStatus = "FAILED",
    message?: string,
  ) {
    super(message ?? reason);
    this.name = "SkillFailure";
    this.reason = reason;
    this.status = status;
  }
}

/** Raised by checkpoint() when the safety kernel takes control mid-skill. */
export class PreemptedError extends Error {
  readonly assessment: EmergencyAssessment;
  constructor(assessment: EmergencyAssessment) {
    super(`preempted by ${assessment.trigger}`);
    this.name = "PreemptedError";
    this.assessment = assessment;
  }
}

export class BudgetExceededError extends Error {
  readonly kind: "ticks" | "health" | "distance";
  constructor(kind: "ticks" | "health" | "distance") {
    super(`skill budget exceeded: ${kind}`);
    this.name = "BudgetExceededError";
    this.kind = kind;
  }
}

export interface SkillContext {
  readonly spec: SkillSpec;
  readonly parameters: Readonly<Record<string, number | string | boolean>>;
  readonly limits: CostLimits;
  readonly embodiment: Embodiment;
  readonly permissions: PermissionGate;
  readonly kernel: SafetyKernel;
  readonly memory: WorldMemory;
  readonly emergency: boolean;
  snapshot(): WorldSnapshot;
  /** Throws if the kernel, the tick budget or the health floor says stop. */
  checkpoint(): void;
  elapsedTicks(): number;
  note(kind: string, detail?: Record<string, EvidenceValue>): void;
  effect(code: string): void;
  number(name: string): number;
  text(name: string): string;
  flag(name: string): boolean;
  home(): Position;
}

export type SkillImplementation = (context: SkillContext) => Promise<void>;

export const countOf = (
  inventory: readonly ItemStack[],
  predicate: (name: string) => boolean,
): number =>
  inventory
    .filter((item) => predicate(item.name))
    .reduce((total, item) => total + item.count, 0);

export const itemCount = (
  inventory: readonly ItemStack[],
  name: string,
): number => inventory.find((item) => item.name === name)?.count ?? 0;
