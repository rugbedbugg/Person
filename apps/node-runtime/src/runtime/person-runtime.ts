import { randomUUID } from "node:crypto";
import path from "node:path";
import type { PersonConfig } from "#config";
import {
  PROTOCOL_VERSION,
  envelope,
  type EmergencyEvent,
  type EpisodeEvent,
  type GoalDecision,
  type ItemDelta,
  type PolicyDecision,
  type PreviousOutcome,
  type SessionHello,
  type SessionIdentity,
  type SkillInvocation,
  type SkillOutcome,
  type SkillStarted,
  type TerminalStatus,
  type ValidationDecision,
} from "#protocol";
import { skillRegistry, type SkillRegistry, type SkillSpec } from "#skills";
import type { Embodiment, PhysicalGuard } from "../embodiment/types.ts";
import {
  buildObservation,
  type CognitionState,
} from "../observation/builder.ts";
import { PermissionGate } from "../safety/permissions.ts";
import { ProtectedAreas } from "../safety/protected-areas.ts";
import {
  SafetyKernel,
  type EmergencyAssessment,
} from "../safety/safety-kernel.ts";
import { InvocationValidator } from "../safety/validator.ts";
import { SkillRunner, type ExecutionResult } from "../skills/executor.ts";
import {
  CognitionChannel,
  CognitionUnavailableError,
} from "../ipc/cognition-channel.ts";
import {
  EpisodeReportBuilder,
  summariseEpisode,
  writeEpisodeReport,
  type EpisodeReport,
} from "../reporting/episode-report.ts";
import { WorldMemory } from "./world-memory.ts";

export interface PersonRuntimeOptions {
  config: PersonConfig;
  embodiment: Embodiment;
  registry?: SkillRegistry;
  identity?: Partial<SessionIdentity>;
  episodeId?: string;
  channel?: CognitionChannel;
  cwd?: string;
  onDiagnostic?: (kind: string, detail: Record<string, unknown>) => void;
}

const negativeOnly = (deltas: ItemDelta[]): ItemDelta[] =>
  deltas.filter((item) => item.delta < 0);

const resolveEffects = (
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

/**
 * The decision loop, and the place where the trust boundary is actually
 * enforced.
 *
 * Cognition proposes; this class validates, executes, observes and reports.
 * Nothing cognition sends reaches the embodiment without passing through the
 * validator and the safety kernel, and what cognition learns from is the
 * outcome of what ran, not of what it asked for.
 */
export class PersonRuntime {
  readonly config: PersonConfig;
  readonly identity: SessionIdentity;
  readonly registry: SkillRegistry;
  readonly memory: WorldMemory;
  readonly permissions: PermissionGate;
  readonly kernel: SafetyKernel;
  readonly validator: InvocationValidator;
  readonly runner: SkillRunner;
  readonly #embodiment: Embodiment;
  readonly #channel: CognitionChannel;
  readonly #episodeId: string;
  readonly #onDiagnostic: (
    kind: string,
    detail: Record<string, unknown>,
  ) => void;
  #cognitionState: CognitionState = {
    activeGoal: null,
    activeRoutine: null,
    activeSkill: null,
    suspendedGoals: [],
  };
  #previousOutcome: PreviousOutcome | null = null;

  constructor(options: PersonRuntimeOptions) {
    this.config = options.config;
    this.#embodiment = options.embodiment;
    this.registry = options.registry ?? skillRegistry();
    this.identity = {
      personId: options.identity?.personId ?? options.config.personId,
      sessionId: options.identity?.sessionId ?? randomUUID(),
      worldId: options.identity?.worldId ?? options.config.worldId,
    };
    this.#episodeId = options.episodeId ?? `ep_${Date.now().toString(36)}`;
    this.#onDiagnostic = options.onDiagnostic ?? (() => {});
    this.memory = WorldMemory.load(
      options.config.runtime.outputDirectory,
      this.identity.worldId,
      this.identity.personId,
      options.config.world.home,
    );
    const areas = new ProtectedAreas(options.config);
    this.permissions = new PermissionGate(options.config, areas);
    this.kernel = new SafetyKernel(this.permissions);
    this.validator = new InvocationValidator(
      this.registry,
      this.permissions,
      this.kernel,
    );
    this.runner = new SkillRunner({
      embodiment: this.#embodiment,
      permissions: this.permissions,
      kernel: this.kernel,
      registry: this.registry,
      memory: this.memory,
    });
    this.#channel =
      options.channel ??
      new CognitionChannel({
        command: options.config.cognition.command,
        cwd: options.cwd ?? process.cwd(),
        startTimeoutMs: options.config.cognition.startTimeoutMs,
        decisionTimeoutMs: options.config.cognition.decisionTimeoutMs,
        onDiagnostic: this.#onDiagnostic,
      });
  }

  get guard(): PhysicalGuard {
    const areas = this.permissions.areas;
    return {
      canEnter: (position) => this.permissions.mayEnter(position).allowed,
      canModify: (position) =>
        areas.permitted(position) &&
        (areas.harvestable(position) ||
          this.permissions.mayBuild(position).allowed),
      canTargetEntity: (entity) =>
        this.permissions.mayHunt(entity).allowed ||
        this.permissions.mayDefend(entity).allowed,
    };
  }

  #envelope<T extends string>(
    type: T,
    tick: number,
  ): ReturnType<typeof envelope> {
    return envelope(this.identity, type as never, tick);
  }

  async run(): Promise<EpisodeReport> {
    const runtime = this.config.runtime;
    this.#embodiment.setGuard(this.guard);
    const builder = new EpisodeReportBuilder({
      schemaVersion: 1,
      episodeId: this.#episodeId,
      personId: this.identity.personId,
      worldId: this.identity.worldId,
      sessionId: this.identity.sessionId,
      trainingContext: runtime.trainingContext,
      learningMode: this.config.learning.mode,
      rngSeed: runtime.rngSeed,
      policyRevision: 0,
      skillLibraryRevision: this.registry.revision,
      protocolVersion: PROTOCOL_VERSION,
      startedAt: new Date().toISOString(),
      startTick: 0,
    });

    let outcome: EpisodeReport["outcome"] = "completed";
    let reason: string | null = null;

    try {
      await this.#embodiment.connect();
      builder.report.startTick = this.#embodiment.snapshot().tick;
      this.#channel.start();

      const hello: SessionHello = {
        ...this.#envelope("SessionHello", this.#embodiment.snapshot().tick),
        type: "SessionHello",
        learningMode: this.config.learning.mode,
        trainingContext: runtime.trainingContext,
        policyRevision: 0,
        skillLibraryRevision: this.registry.revision,
        rngSeed: runtime.rngSeed,
        evidenceDirectory: this.config.learning.evidenceDirectory,
        skillIds: this.registry.ids,
      };
      this.#channel.send(hello);
      const ready = await this.#channel.waitForReady();
      builder.report.policyRevision = (
        ready as { policyRevision: number }
      ).policyRevision;

      this.#sendEpisodeEvent("started", ["session_start"]);

      let decisions = 0;
      while (decisions < runtime.maxDecisions) {
        const snapshot = this.#embodiment.snapshot();
        if (!snapshot.connected) {
          outcome = "failed";
          reason = "disconnected";
          break;
        }
        if (!snapshot.alive) {
          outcome = "failed";
          reason = "death";
          break;
        }
        if (snapshot.tick - builder.report.startTick >= runtime.maxTicks) {
          reason = "tick_budget_reached";
          break;
        }
        decisions += 1;
        await this.#decide(builder);
        if (runtime.decisionIntervalMs > 0)
          await new Promise((resolve) =>
            setTimeout(resolve, runtime.decisionIntervalMs),
          );
      }
      if (decisions >= runtime.maxDecisions)
        reason ??= "decision_budget_reached";
      this.#sendEpisodeEvent("ended", [reason ?? "completed"]);
    } catch (error) {
      outcome =
        error instanceof CognitionUnavailableError ? "failed" : "failed";
      reason =
        error instanceof Error ? error.message.slice(0, 160) : "unknown_error";
      this.#onDiagnostic("runtime_error", { reason });
      try {
        this.#sendEpisodeEvent("ended", ["runtime_error"]);
      } catch {
        // Cognition is already gone; the report below is the record that matters.
      }
    } finally {
      this.memory.save();
      await this.#channel.stop();
      await this.#embodiment.disconnect();
    }

    builder.setStorageProvenance(this.memory.ownedStorage);
    const report = builder.finish(
      outcome,
      reason,
      this.#embodiment.snapshot().tick,
    );
    writeEpisodeReport(
      path.join(this.config.runtime.outputDirectory, "reports"),
      report,
    );
    return report;
  }

  #sendEpisodeEvent(phase: "started" | "ended", reasonCodes: string[]): void {
    const event: EpisodeEvent = {
      ...this.#envelope("EpisodeEvent", this.#embodiment.snapshot().tick),
      type: "EpisodeEvent",
      episodeId: this.#episodeId,
      phase,
      trainingContext: this.config.runtime.trainingContext,
      rngSeed: this.config.runtime.rngSeed,
      reasonCodes,
    };
    this.#channel.send(event);
  }

  #sendEmergency(
    assessment: EmergencyAssessment,
    decisionId: string | null,
    preempted: string | null,
  ): void {
    const event: EmergencyEvent = {
      ...this.#envelope("EmergencyEvent", this.#embodiment.snapshot().tick),
      type: "EmergencyEvent",
      decisionId,
      level: assessment.level,
      trigger: assessment.trigger,
      reasonCodes: assessment.reasonCodes,
      action: assessment.action,
      preemptedSkill: preempted,
    };
    this.#channel.send(event);
  }

  async #decide(builder: EpisodeReportBuilder): Promise<void> {
    const snapshot = this.#embodiment.snapshot();
    const observation = buildObservation({
      identity: this.identity,
      snapshot,
      permissions: this.permissions,
      kernel: this.kernel,
      memory: this.memory,
      trainingContext: this.config.runtime.trainingContext,
      cognition: this.#cognitionState,
      previousOutcome: this.#previousOutcome,
      blockAt: (position) => this.#embodiment.blockAt(position),
    });
    this.#channel.send(observation);

    const goal = (await this.#channel.expect("GoalDecision")) as GoalDecision;
    const policy = (await this.#channel.expect(
      "PolicyDecision",
    )) as PolicyDecision;
    const invocation = (await this.#channel.expect(
      "SkillInvocation",
    )) as SkillInvocation;

    this.#cognitionState = {
      activeGoal: goal.goal.goalId,
      activeRoutine: policy.routineId,
      activeSkill: invocation.skillId,
      suspendedGoals: goal.stack
        .filter((entry) => entry.status === "SUSPENDED")
        .map((entry) => entry.goalId),
    };

    const verdict = this.validator.validate(
      invocation,
      this.#embodiment.snapshot(),
    );
    const validation: ValidationDecision = {
      ...this.#envelope("ValidationDecision", this.#embodiment.snapshot().tick),
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
    this.#channel.send(validation);

    const requestedSpec = this.registry.has(invocation.skillId)
      ? this.registry.get(invocation.skillId)
      : null;

    if (verdict.emergency) {
      this.#sendEmergency(
        verdict.emergency,
        invocation.decisionId,
        verdict.decision === "REPLACE" ? invocation.skillId : null,
      );
      builder.addSafetyOverride({
        tick: this.#embodiment.snapshot().tick,
        level: verdict.emergency.level,
        trigger: verdict.emergency.trigger,
        action: verdict.emergency.action,
        preemptedSkill:
          verdict.decision === "REPLACE" ? invocation.skillId : null,
      });
    }

    if (
      verdict.decision === "REJECT" ||
      !verdict.executedSkill ||
      !verdict.executedLimits
    ) {
      const outcome = this.#buildOutcome({
        invocation,
        policy,
        goal,
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
      this.#channel.send(outcome);
      this.#record(
        builder,
        goal,
        policy,
        invocation,
        verdict.decision,
        verdict.level,
        verdict.reasonCodes,
        outcome,
        requestedSpec,
      );
      return;
    }

    const started: SkillStarted = {
      ...this.#envelope("SkillStarted", this.#embodiment.snapshot().tick),
      type: "SkillStarted",
      decisionId: invocation.decisionId,
      requestedSkill: invocation.skillId,
      executedSkill: verdict.executedSkill,
      parameters: verdict.executedParameters ?? {},
      limits: verdict.executedLimits,
      startTick: this.#embodiment.snapshot().tick,
      startHealth: this.#embodiment.snapshot().health,
      startFood: this.#embodiment.snapshot().food,
      startInventory: this.#embodiment.snapshot().inventory,
    };
    this.#channel.send(started);

    let executedSkill = verdict.executedSkill;
    let executedParameters = verdict.executedParameters ?? {};
    let result = await this.runner.run({
      skillId: executedSkill,
      parameters: executedParameters,
      limits: verdict.executedLimits,
      emergency:
        this.registry.get(executedSkill).emergency ||
        Boolean(verdict.emergency),
    });

    let requestedSkillStatus: TerminalStatus =
      verdict.decision === "REPLACE" ? "PREEMPTED" : result.status;
    const reasonCodes = [...verdict.reasonCodes, ...result.reasonCodes];

    // A skill preempted mid-flight hands control to the emergency skill. The
    // outcome then credits what actually ran, and says explicitly that the
    // requested skill was preempted.
    if (result.status === "PREEMPTED" && result.preemption) {
      const assessment = result.preemption;
      this.#sendEmergency(assessment, invocation.decisionId, executedSkill);
      builder.addSafetyOverride({
        tick: this.#embodiment.snapshot().tick,
        level: assessment.level,
        trigger: assessment.trigger,
        action: assessment.action,
        preemptedSkill: executedSkill,
      });
      const replacement = this.validator.emergencyInvocation(assessment);
      requestedSkillStatus = "PREEMPTED";
      if (replacement) {
        const emergencyResult = await this.runner.run({
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

    const executedSpec = this.registry.get(executedSkill);
    const outcome = this.#buildOutcome({
      invocation,
      policy,
      goal,
      executedSkill,
      executedParameters,
      requestedSkillStatus,
      status: result.status,
      emergency: Boolean(verdict.emergency) || Boolean(result.preemption),
      reasonCodes,
      result,
      expectedEffects: resolveEffects(executedSpec, executedParameters),
    });
    this.#channel.send(outcome);
    this.#previousOutcome = {
      requestedSkill: outcome.requestedSkill,
      executedSkill: outcome.executedSkill,
      status: outcome.status,
      effects: outcome.effects,
      healthCost: outcome.healthCost,
      resourceCost: outcome.resourceCost,
      elapsedTicks: outcome.elapsedTicks,
      interruptReason: outcome.interruptReason,
    };
    this.#cognitionState = { ...this.#cognitionState, activeSkill: null };
    this.memory.save();
    this.#record(
      builder,
      goal,
      policy,
      invocation,
      verdict.decision,
      verdict.level,
      verdict.reasonCodes,
      outcome,
      requestedSpec,
    );
  }

  #buildOutcome(input: {
    invocation: SkillInvocation;
    policy: PolicyDecision;
    goal: GoalDecision;
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
  }): SkillOutcome {
    const snapshot = this.#embodiment.snapshot();
    const result = input.result;
    const interruptReason =
      input.status === "PREEMPTED" || input.requestedSkillStatus === "PREEMPTED"
        ? (result?.preemption?.trigger ?? "preempted")
        : input.status === "TIMED_OUT"
          ? "tick_budget_exceeded"
          : null;
    return {
      ...this.#envelope("SkillOutcome", snapshot.tick),
      type: "SkillOutcome",
      decisionId: input.invocation.decisionId,
      goalId: input.goal.goal.goalId,
      routineId: input.policy.routineId,
      contextId: input.policy.contextId,
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

  #record(
    builder: EpisodeReportBuilder,
    goal: GoalDecision,
    policy: PolicyDecision,
    invocation: SkillInvocation,
    decision: string,
    level: string,
    validationReasonCodes: string[],
    outcome: SkillOutcome,
    requestedSpec: SkillSpec | null,
  ): void {
    builder.addDecision({
      decisionId: invocation.decisionId,
      tick: invocation.tick,
      contextId: policy.contextId,
      goalId: goal.goal.goalId,
      goalType: goal.goal.goalType,
      goalReasonCodes: goal.reasonCodes,
      routineId: policy.routineId,
      routineName: policy.routineName,
      routineSteps: policy.steps,
      learnedOrFallback: policy.learnedOrFallback,
      policyConfidence: policy.confidence,
      policyReasonCodes: policy.reasonCodes,
      evidenceRefs: policy.evidenceRefs,
      requestedSkill: invocation.skillId,
      requestedParameters: { ...invocation.parameters },
      preconditions: requestedSpec
        ? requestedSpec.preconditions.map((c) => ({ ...c }))
        : [],
      expectedEffects: outcome.expectedEffects,
      validation: decision,
      validationLevel: level,
      validationReasonCodes,
      executedSkill: outcome.executedSkill,
      status: outcome.status,
      requestedSkillStatus: outcome.requestedSkillStatus,
      emergency: outcome.emergency,
      healthDelta: outcome.healthAfter - outcome.healthBefore,
      foodDelta: outcome.foodAfter - outcome.foodBefore,
      elapsedTicks: outcome.elapsedTicks,
      inventoryDelta: outcome.inventoryDelta,
      outcomeMessageId: outcome.messageId,
    });
  }
}

export { summariseEpisode };
