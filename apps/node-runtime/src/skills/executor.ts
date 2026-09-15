import type {
  CostLimits,
  ItemDelta,
  ItemStack,
  TerminalStatus,
} from "#protocol";
import { type SkillRegistry } from "#skills";
import type { Position } from "#config";
import type { Embodiment, WorldSnapshot } from "../embodiment/types.ts";
import { DisconnectedError } from "../embodiment/types.ts";
import type { PermissionGate } from "../safety/permissions.ts";
import type {
  EmergencyAssessment,
  SafetyKernel,
} from "../safety/safety-kernel.ts";
import type { WorldMemory } from "../runtime/world-memory.ts";
import {
  BudgetExceededError,
  PreemptedError,
  SkillFailure,
  type EvidenceValue,
  type SkillContext,
} from "./execution.ts";
import { SKILL_IMPLEMENTATIONS } from "./impl/index.ts";
import { inventoryDelta } from "./materials.ts";

/**
 * Evidence keys travel over the protocol, which requires lower snake case.
 * Normalising here means a new skill cannot fail an entire episode by naming
 * one piece of evidence awkwardly.
 */
export function evidenceKey(kind: string, key: string): string {
  const combined = `${kind}_${key}`
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, "_")
    .replace(/^[^a-z]+/, "");
  return (combined || "detail").slice(0, 64);
}

export interface ExecutionRequest {
  skillId: string;
  parameters: Readonly<Record<string, number | string | boolean>>;
  limits: CostLimits;
  emergency: boolean;
}

export interface ExecutionResult {
  skillId: string;
  status: TerminalStatus;
  reasonCodes: string[];
  effects: string[];
  evidenceKinds: string[];
  evidenceDetails: Record<string, EvidenceValue>;
  elapsedTicks: number;
  healthBefore: number;
  healthAfter: number;
  foodBefore: number;
  foodAfter: number;
  inventoryBefore: ItemStack[];
  inventoryAfter: ItemStack[];
  inventoryDelta: ItemDelta[];
  preemption: EmergencyAssessment | null;
}

export interface SkillRunnerOptions {
  embodiment: Embodiment;
  permissions: PermissionGate;
  kernel: SafetyKernel;
  registry: SkillRegistry;
  memory: WorldMemory;
}

/**
 * Runs one skill under its declared bounds.
 *
 * Bounds are enforced here rather than inside each skill, so a new skill
 * cannot forget them: every checkpoint re-reads the world, re-asks the safety
 * kernel, and re-checks the tick and health budget.
 */
export class SkillRunner {
  readonly #embodiment: Embodiment;
  readonly #permissions: PermissionGate;
  readonly #kernel: SafetyKernel;
  readonly #registry: SkillRegistry;
  readonly #memory: WorldMemory;

  constructor(options: SkillRunnerOptions) {
    this.#embodiment = options.embodiment;
    this.#permissions = options.permissions;
    this.#kernel = options.kernel;
    this.#registry = options.registry;
    this.#memory = options.memory;
  }

  get memory(): WorldMemory {
    return this.#memory;
  }

  async run(request: ExecutionRequest): Promise<ExecutionResult> {
    const spec = this.#registry.get(request.skillId);
    const implementation = SKILL_IMPLEMENTATIONS[request.skillId];
    if (!implementation)
      throw new Error(`Skill ${request.skillId} has no runtime implementation`);

    const start = this.#embodiment.snapshot();
    const effects: string[] = [];
    const evidenceKinds = new Set<string>();
    const evidenceDetails: Record<string, EvidenceValue> = {};
    const reasonCodes: string[] = [];
    let preemption: EmergencyAssessment | null = null;

    const context: SkillContext = {
      spec,
      parameters: request.parameters,
      limits: request.limits,
      embodiment: this.#embodiment,
      permissions: this.#permissions,
      kernel: this.#kernel,
      memory: this.#memory,
      emergency: request.emergency,
      snapshot: () => this.#embodiment.snapshot(),
      elapsedTicks: () => this.#embodiment.snapshot().tick - start.tick,
      checkpoint: () => {
        const now = this.#embodiment.snapshot();
        if (!now.connected) throw new DisconnectedError();
        if (!now.alive)
          throw new SkillFailure(
            "death",
            "DEATH",
            "Person died during the skill",
          );
        if (now.tick - start.tick > request.limits.maxTicks)
          throw new BudgetExceededError("ticks");
        if (!request.emergency && now.health < request.limits.minHealth)
          throw new BudgetExceededError("health");
        if (!request.emergency) {
          const assessment = this.#kernel.assess(now);
          if (assessment) throw new PreemptedError(assessment);
        }
      },
      note: (kind, detail) => {
        evidenceKinds.add(kind);
        for (const [key, value] of Object.entries(detail ?? {}))
          evidenceDetails[evidenceKey(kind, key)] = value;
      },
      effect: (code) => {
        if (!effects.includes(code)) effects.push(code);
      },
      number: (name) => {
        const value = request.parameters[name];
        if (typeof value !== "number")
          throw new SkillFailure(
            "invalid_parameter",
            "INVALIDATED",
            `${name} is not a number`,
          );
        return value;
      },
      text: (name) => {
        const value = request.parameters[name];
        if (typeof value !== "string")
          throw new SkillFailure(
            "invalid_parameter",
            "INVALIDATED",
            `${name} is not a string`,
          );
        return value;
      },
      flag: (name) => request.parameters[name] === true,
      home: (): Position => this.#memory.home.position,
    };

    let status: TerminalStatus = "SUCCESS";
    try {
      context.checkpoint();
      await implementation(context);
      context.checkpoint();
    } catch (error) {
      if (error instanceof PreemptedError) {
        status = "PREEMPTED";
        preemption = error.assessment;
        reasonCodes.push(
          error.assessment.trigger,
          ...error.assessment.reasonCodes,
        );
      } else if (error instanceof BudgetExceededError) {
        status = error.kind === "ticks" ? "TIMED_OUT" : "FAILED";
        reasonCodes.push(
          error.kind === "ticks"
            ? "tick_budget_exceeded"
            : "health_floor_reached",
        );
      } else if (error instanceof DisconnectedError) {
        status = "DISCONNECTED";
        reasonCodes.push("connection_lost");
      } else if (error instanceof SkillFailure) {
        status = error.status;
        reasonCodes.push(error.reason);
        evidenceDetails["failure_message"] = error.message.slice(0, 128);
      } else {
        status = "FAILED";
        reasonCodes.push("unexpected_error");
        evidenceDetails["failure_message"] = (error as Error).message.slice(
          0,
          128,
        );
      }
    }

    const end = this.#embodiment.snapshot();
    if (status === "SUCCESS" && !end.alive) status = "DEATH";
    evidenceKinds.add("elapsed_ticks");

    return {
      skillId: request.skillId,
      status,
      reasonCodes,
      effects,
      evidenceKinds: [...evidenceKinds].sort(),
      evidenceDetails,
      elapsedTicks: Math.max(0, end.tick - start.tick),
      healthBefore: start.health,
      healthAfter: end.health,
      foodBefore: start.food,
      foodAfter: end.food,
      inventoryBefore: start.inventory,
      inventoryAfter: end.inventory,
      inventoryDelta: inventoryDelta(start.inventory, end.inventory),
      preemption,
    };
  }

  snapshot(): WorldSnapshot {
    return this.#embodiment.snapshot();
  }
}
