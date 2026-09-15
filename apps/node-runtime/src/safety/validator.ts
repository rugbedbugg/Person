import type {
  CostLimits,
  SafetyLevel,
  SkillInvocation,
  SkillParameters,
  ValidationVerdict,
} from "#protocol";
import { SkillSpecError, type SkillRegistry } from "#skills";
import type { WorldSnapshot } from "../embodiment/types.ts";
import { SKILL_IMPLEMENTATIONS } from "../skills/impl/index.ts";
import type { PermissionGate } from "./permissions.ts";
import type { EmergencyAssessment, SafetyKernel } from "./safety-kernel.ts";

export interface ValidationOutcome {
  decision: ValidationVerdict;
  level: SafetyLevel;
  reasonCodes: string[];
  executedSkill: string | null;
  executedParameters: SkillParameters | null;
  executedLimits: CostLimits | null;
  emergency: EmergencyAssessment | null;
}

const clamp = (
  requested: CostLimits,
  allowed: CostLimits,
): { limits: CostLimits; clamped: boolean } => {
  const limits: CostLimits = {
    maxTicks: Math.min(requested.maxTicks, allowed.maxTicks),
    maxDistance: Math.min(requested.maxDistance, allowed.maxDistance),
    minHealth: Math.max(requested.minHealth, allowed.minHealth),
  };
  const clamped =
    limits.maxTicks !== requested.maxTicks ||
    limits.maxDistance !== requested.maxDistance ||
    limits.minHealth !== requested.minHealth;
  return { limits, clamped };
};

/**
 * The trust boundary.
 *
 * A proposal from cognition is checked against the skill library, the
 * permission gate and the safety kernel before anything physical happens. The
 * verdict is authoritative: cognition is told what will actually run, and
 * learning is credited to that, not to what it asked for.
 */
export class InvocationValidator {
  readonly #registry: SkillRegistry;
  readonly #permissions: PermissionGate;
  readonly #kernel: SafetyKernel;

  constructor(
    registry: SkillRegistry,
    permissions: PermissionGate,
    kernel: SafetyKernel,
  ) {
    this.#registry = registry;
    this.#permissions = permissions;
    this.#kernel = kernel;
  }

  /** The emergency skill Node runs for an assessment, with its default parameters. */
  emergencyInvocation(assessment: EmergencyAssessment): {
    skillId: string;
    parameters: SkillParameters;
    limits: CostLimits;
  } | null {
    if (assessment.action === "cancel_skill") return null;
    const spec = this.#registry.specs.get(assessment.action);
    if (!spec) return null;
    return {
      skillId: spec.id,
      parameters: this.#registry.resolveParameters(spec.id, {}),
      limits: { ...spec.costLimits },
    };
  }

  validate(
    invocation: SkillInvocation,
    snapshot: WorldSnapshot,
  ): ValidationOutcome {
    const reject = (
      level: SafetyLevel,
      ...reasonCodes: string[]
    ): ValidationOutcome => ({
      decision: "REJECT",
      level,
      reasonCodes,
      executedSkill: null,
      executedParameters: null,
      executedLimits: null,
      emergency: null,
    });

    if (!this.#registry.has(invocation.skillId))
      return reject("L0", "unknown_skill");
    if (!(invocation.skillId in SKILL_IMPLEMENTATIONS))
      return reject("L0", "skill_not_implemented");
    const spec = this.#registry.get(invocation.skillId);
    if (spec.version !== invocation.skillVersion)
      return reject("L0", "skill_version_mismatch");

    let parameters: SkillParameters;
    try {
      parameters = this.#registry.resolveParameters(
        invocation.skillId,
        invocation.parameters,
      );
    } catch (error) {
      return reject(
        "L0",
        "invalid_parameters",
        error instanceof SkillSpecError
          ? "parameter_rejected"
          : "parameter_error",
      );
    }

    const missing = this.#permissions.missingFor(spec.requiredPermissions);
    if (missing.length > 0)
      return reject("L0", "permission_denied", ...missing);

    const { limits, clamped } = clamp(invocation.limits, spec.costLimits);
    const reasonCodes: string[] = [];
    if (clamped) reasonCodes.push("limits_clamped_to_spec");

    const assessment = this.#kernel.assess(snapshot);
    if (assessment) {
      const replacement = this.emergencyInvocation(assessment);
      if (replacement && replacement.skillId === invocation.skillId)
        return {
          decision: "ACCEPT",
          level: assessment.level,
          reasonCodes: [
            ...reasonCodes,
            assessment.trigger,
            "proposal_matched_emergency",
          ],
          executedSkill: invocation.skillId,
          executedParameters: parameters,
          executedLimits: limits,
          emergency: assessment,
        };
      if (replacement)
        return {
          decision: "REPLACE",
          level: assessment.level,
          reasonCodes: [
            ...reasonCodes,
            assessment.trigger,
            ...assessment.reasonCodes,
          ],
          executedSkill: replacement.skillId,
          executedParameters: replacement.parameters,
          executedLimits: replacement.limits,
          emergency: assessment,
        };
      return {
        decision: "REJECT",
        level: assessment.level,
        reasonCodes: [
          ...reasonCodes,
          assessment.trigger,
          "no_emergency_skill_available",
        ],
        executedSkill: null,
        executedParameters: null,
        executedLimits: null,
        emergency: assessment,
      };
    }

    return {
      decision: "ACCEPT",
      level: spec.emergency ? "L1" : "L2",
      reasonCodes,
      executedSkill: invocation.skillId,
      executedParameters: parameters,
      executedLimits: limits,
      emergency: null,
    };
  }
}
