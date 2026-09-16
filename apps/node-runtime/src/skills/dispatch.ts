import type {
  Envelope,
  ItemDelta,
  MessageType,
  SkillInvocation,
  SkillOutcome,
  SkillStarted,
  TerminalStatus,
  ValidationDecision,
} from "#protocol";
import type { SkillRegistry, SkillSpec } from "#skills";
import type { Embodiment } from "../embodiment/types.ts";
import type { EmergencyAssessment } from "../safety/safety-kernel.ts";
import type {
  InvocationValidator,
  ValidationOutcome,
} from "../safety/validator.ts";
import type { ExecutionResult, SkillRunner } from "./executor.ts";

/**
 * The one road from a SkillInvocation to a SkillOutcome.
 *
 * Everything that wants Person to do something physical comes through here:
 * the autonomous decision loop, and the operator's single-skill validation
 * harness. There is deliberately no second implementation of this sequence,
 * because a second one would be a second place where the safety kernel could
 * be forgotten.
 *
 * The order is fixed and every step is mandatory: validate against the skill
 * library, the permission gate and the safety kernel; run only what the verdict
 * authorised; hand control to the emergency skill if the kernel takes over
 * mid-flight; and credit the outcome to what actually ran.
 */

/** Where a decision came from, for the record. */
export interface DispatchAttribution {
  goalId: string;
  routineId: string;
  contextId: string;
}

export interface DispatchDependencies {
  registry: SkillRegistry;
  validator: InvocationValidator;
  runner: SkillRunner;
  embodiment: Embodiment;
  envelope: (type: MessageType, tick: number) => Envelope;
}

/**
 * Observers, not participants.
 *
 * A caller uses these to report what happened: the decision loop sends each
 * message to cognition, the validation harness writes them into a report.
 * Nothing a hook does can change what runs.
 */
export interface DispatchHooks {
  onValidation?: (
    validation: ValidationDecision,
    verdict: ValidationOutcome,
  ) => void;
  onEmergency?: (
    assessment: EmergencyAssessment,
    decisionId: string | null,
    preemptedSkill: string | null,
  ) => void;
  onStarted?: (started: SkillStarted) => void;
}

export interface DispatchResult {
  verdict: ValidationOutcome;
  validation: ValidationDecision;
  started: SkillStarted | null;
  result: ExecutionResult | null;
  outcome: SkillOutcome;
  requestedSpec: SkillSpec | null;
  executedSkill: string | null;
}

const negativeOnly = (deltas: ItemDelta[]): ItemDelta[] =>
  deltas.filter((item) => item.delta < 0);

/** A skill's declared effects, with any parameter-scaled value filled in. */
export const resolveEffects = (
  spec: SkillSpec,
  parameters: Readonly<Record<string, number | string | boolean>>,
): { fact: string; op: "+=" | "-=" | "=" | "max"; value: number }[] =>
  spec.expectedEffects.map((effect) => {
    const scaled = effect.scalesWith
      ? parameters[effect.scalesWith]
      : undefined;
    return {
      fact: effect.fact,
      op: effect.op,
      value: typeof scaled === "number" ? scaled : effect.value,
    };
  });

interface OutcomeInput {
  invocation: SkillInvocation;
  attribution: DispatchAttribution;
  executedSkill: string | null;
  executedParameters: Readonly<
    Record<string, number | string | boolean>
  > | null;
  requestedSkillStatus: TerminalStatus;
  status: TerminalStatus;
  emergency: boolean;
  reasonCodes: string[];
  result: ExecutionResult | null;
  expectedEffects: {
    fact: string;
    op: "+=" | "-=" | "=" | "max";
    value: number;
  }[];
}

function buildOutcome(
  deps: DispatchDependencies,
  input: OutcomeInput,
): SkillOutcome {
  const snapshot = deps.embodiment.snapshot();
  const result = input.result;
  const interruptReason =
    input.status === "PREEMPTED" || input.requestedSkillStatus === "PREEMPTED"
      ? (result?.preemption?.trigger ?? "preempted")
      : input.status === "TIMED_OUT"
        ? "tick_budget_exceeded"
        : null;
  return {
    ...deps.envelope("SkillOutcome", snapshot.tick),
    type: "SkillOutcome",
    decisionId: input.invocation.decisionId,
    goalId: input.attribution.goalId,
    routineId: input.attribution.routineId,
    contextId: input.attribution.contextId,
    requestedSkill: input.invocation.skillId,
    requestedParameters: input.invocation.parameters,
    requestedSkillStatus: input.requestedSkillStatus,
    executedSkill: input.executedSkill,
    executedParameters: input.executedParameters,
    status: input.status,
    emergency: input.emergency,
    reasonCodes: [...new Set(input.reasonCodes)].slice(0, 32),
    effects: result?.effects ?? [],
    expectedEffects: input.expectedEffects,
    healthBefore: result?.healthBefore ?? snapshot.health,
    healthAfter: result?.healthAfter ?? snapshot.health,
    foodBefore: result?.foodBefore ?? snapshot.food,
    foodAfter: result?.foodAfter ?? snapshot.food,
    healthCost: Math.max(
      0,
      (result?.healthBefore ?? 0) - (result?.healthAfter ?? 0),
    ),
    resourceCost: negativeOnly(result?.inventoryDelta ?? []),
    inventoryDelta: result?.inventoryDelta ?? [],
    elapsedTicks: result?.elapsedTicks ?? 0,
    interruptReason,
    completionEvidence: {
      kinds: result?.evidenceKinds ?? [],
      details: result?.evidenceDetails ?? {},
    },
  };
}

/**
 * Validates one proposal and executes whatever the verdict allows.
 *
 * A REJECT produces an INVALIDATED outcome and nothing physical happens. A
 * REPLACE runs the emergency skill the kernel chose, and the outcome says the
 * requested skill was PREEMPTED. Mid-flight preemption does the same thing
 * again, because a threat that appears during a skill deserves the same answer
 * as one that was already there.
 */
export async function dispatchSkill(
  invocation: SkillInvocation,
  attribution: DispatchAttribution,
  deps: DispatchDependencies,
  hooks: DispatchHooks = {},
): Promise<DispatchResult> {
  const verdict = deps.validator.validate(
    invocation,
    deps.embodiment.snapshot(),
  );
  const validation: ValidationDecision = {
    ...deps.envelope("ValidationDecision", deps.embodiment.snapshot().tick),
    type: "ValidationDecision",
    decisionId: invocation.decisionId,
    requestedSkill: invocation.skillId,
    decision: verdict.decision,
    level: verdict.level,
    reasonCodes: verdict.reasonCodes,
    executedSkill: verdict.executedSkill,
    executedParameters: verdict.executedParameters,
    executedLimits: verdict.executedLimits,
  };
  hooks.onValidation?.(validation, verdict);

  const requestedSpec = deps.registry.has(invocation.skillId)
    ? deps.registry.get(invocation.skillId)
    : null;

  if (verdict.emergency)
    hooks.onEmergency?.(
      verdict.emergency,
      invocation.decisionId,
      verdict.decision === "REPLACE" ? invocation.skillId : null,
    );

  if (
    verdict.decision === "REJECT" ||
    !verdict.executedSkill ||
    !verdict.executedLimits
  ) {
    const outcome = buildOutcome(deps, {
      invocation,
      attribution,
      executedSkill: null,
      executedParameters: null,
      requestedSkillStatus: "INVALIDATED",
      status: "INVALIDATED",
      emergency: Boolean(verdict.emergency),
      reasonCodes: verdict.reasonCodes,
      result: null,
      expectedEffects: requestedSpec
        ? resolveEffects(requestedSpec, invocation.parameters)
        : [],
    });
    return {
      verdict,
      validation,
      started: null,
      result: null,
      outcome,
      requestedSpec,
      executedSkill: null,
    };
  }

  const startSnapshot = deps.embodiment.snapshot();
  const started: SkillStarted = {
    ...deps.envelope("SkillStarted", startSnapshot.tick),
    type: "SkillStarted",
    decisionId: invocation.decisionId,
    requestedSkill: invocation.skillId,
    executedSkill: verdict.executedSkill,
    parameters: verdict.executedParameters ?? {},
    limits: verdict.executedLimits,
    startTick: startSnapshot.tick,
    startHealth: startSnapshot.health,
    startFood: startSnapshot.food,
    startInventory: startSnapshot.inventory,
  };
  hooks.onStarted?.(started);

  let executedSkill = verdict.executedSkill;
  let executedParameters = verdict.executedParameters ?? {};
  let result = await deps.runner.run({
    skillId: executedSkill,
    parameters: executedParameters,
    limits: verdict.executedLimits,
    emergency:
      deps.registry.get(executedSkill).emergency || Boolean(verdict.emergency),
  });

  let requestedSkillStatus: TerminalStatus =
    verdict.decision === "REPLACE" ? "PREEMPTED" : result.status;
  const reasonCodes = [...verdict.reasonCodes, ...result.reasonCodes];

  // A skill preempted mid-flight hands control to the emergency skill. The
  // outcome then credits what actually ran, and says explicitly that the
  // requested skill was preempted.
  if (result.status === "PREEMPTED" && result.preemption) {
    const assessment = result.preemption;
    hooks.onEmergency?.(assessment, invocation.decisionId, executedSkill);
    const replacement = deps.validator.emergencyInvocation(assessment);
    requestedSkillStatus = "PREEMPTED";
    if (replacement) {
      const emergencyResult = await deps.runner.run({
        skillId: replacement.skillId,
        parameters: replacement.parameters,
        limits: replacement.limits,
        emergency: true,
      });
      executedSkill = replacement.skillId;
      executedParameters = replacement.parameters;
      reasonCodes.push(assessment.trigger, ...emergencyResult.reasonCodes);
      result = { ...emergencyResult, preemption: assessment };
    }
  }

  const executedSpec = deps.registry.get(executedSkill);
  const outcome = buildOutcome(deps, {
    invocation,
    attribution,
    executedSkill,
    executedParameters,
    requestedSkillStatus,
    status: result.status,
    emergency: Boolean(verdict.emergency) || Boolean(result.preemption),
    reasonCodes,
    result,
    expectedEffects: resolveEffects(executedSpec, executedParameters),
  });

  return {
    verdict,
    validation,
    started,
    result,
    outcome,
    requestedSpec,
    executedSkill,
  };
}
