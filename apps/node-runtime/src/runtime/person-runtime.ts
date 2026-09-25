import { randomUUID } from "node:crypto";
import path from "node:path";
import { distance, type PersonConfig } from "#config";
import {
  PROTOCOL_VERSION,
  envelope,
  type EmergencyEvent,
  type EpisodeEvent,
  type GoalDecision,
  type MessageType,
  type PolicyDecision,
  type PreviousOutcome,
  type SessionHello,
  type SessionIdentity,
  type SkillInvocation,
  type SkillOutcome,
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
import { SkillRunner } from "../skills/executor.ts";
import {
  dispatchSkill,
  type DispatchDependencies,
} from "../skills/dispatch.ts";
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
import { StatusWriter, statusPath } from "../reporting/status.ts";
import { PlacementLedger } from "./placement-ledger.ts";
import { SelfMotionSense } from "../observation/self-motion.ts";

export interface PersonRuntimeOptions {
  config: PersonConfig;
  embodiment: Embodiment;
  registry?: SkillRegistry;
  identity?: Partial<SessionIdentity>;
  episodeId?: string;
  channel?: CognitionChannel;
  cwd?: string;
  onDiagnostic?: (kind: string, detail: Record<string, unknown>) => void;
  /**
   * Marks a run as contaminated by a human acting on the world.
   *
   * A debug run where the operator moved Person or handed it items is not an
   * acceptance run, and the difference has to be recorded at the time. It is
   * declared, not detected: guessing which world changes were a person would
   * be unreliable in exactly the cases that matter.
   */
  operatorIntervention?: { reason?: string };
}

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
  readonly ledger: PlacementLedger;
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
  /** Person's sense of its own motion, for the life of this session. */
  readonly #selfMotion = new SelfMotionSense();
  readonly #status: StatusWriter;
  readonly #operatorIntervention: { flagged: boolean; reason: string | null };
  #emergencyCount = 0;
  #decisionCount = 0;

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
    this.ledger = PlacementLedger.load(
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
      ledger: this.ledger,
    });
    this.#operatorIntervention = {
      flagged: options.operatorIntervention !== undefined,
      reason: options.operatorIntervention?.reason ?? null,
    };
    this.#status = new StatusWriter(
      statusPath(
        options.config.runtime.outputDirectory,
        this.identity.worldId,
        this.identity.personId,
      ),
      {
        command: "run",
        personId: this.identity.personId,
        botUsername: options.config.bot?.username ?? null,
        worldId: this.identity.worldId,
        sessionId: this.identity.sessionId,
        episodeId: this.#episodeId,
        server: options.config.server ?? null,
        embodiment: options.config.runtime.embodiment,
        trainingContext: options.config.runtime.trainingContext,
        learningMode: options.config.learning.mode,
        operatorIntervention: this.#operatorIntervention,
        home: {
          position: this.ledger.home.position,
          distance: null,
          shelterState: this.ledger.home.shelterState,
        },
      },
    );
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

  /** The one road to the embodiment, wired for this session. */
  dispatchDependencies(): DispatchDependencies {
    return {
      registry: this.registry,
      validator: this.validator,
      runner: this.runner,
      embodiment: this.#embodiment,
      envelope: (type: MessageType, tick: number) => this.#envelope(type, tick),
    };
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
      this.#status.update({
        connection: "connecting",
        readiness: "connecting",
      });
      await this.#embodiment.connect();
      builder.report.startTick = this.#embodiment.snapshot().tick;
      this.#status.update({ connection: "ready", readiness: "world ready" });
      this.#syncStatus();
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
        this.#decisionCount = decisions;
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
      this.ledger.save();
      await this.#channel.stop();
      await this.#embodiment.disconnect();
      this.#status.update({
        connection:
          this.#status.status.connection === "failed"
            ? "failed"
            : "disconnected",
        readiness: "stopped",
        decisions: builder.report.decisions.length,
      });
    }

    builder.setStorageProvenance(this.ledger.ownedStorage);
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

  /** Mirrors the live facts into the status file for an operator watching. */
  #syncStatus(
    patch: Partial<Parameters<StatusWriter["update"]>[0]> = {},
  ): void {
    const snapshot = this.#embodiment.snapshot();
    const home = this.ledger.home.position;
    this.#status.update({
      tick: snapshot.tick,
      dimension: snapshot.dimension,
      position: snapshot.position,
      health: snapshot.health,
      food: snapshot.food,
      lastSafePosition: snapshot.lastSafePosition,
      home: {
        position: home,
        distance: distance(snapshot.position, home),
        shelterState: this.ledger.home.shelterState,
      },
      safety: {
        threat: this.kernel.threatState(snapshot),
        emergencies: this.#emergencyCount,
        lastEmergency: this.#status.status.safety.lastEmergency,
      },
      goal: this.#cognitionState.activeGoal,
      routine: this.#cognitionState.activeRoutine,
      skill: this.#cognitionState.activeSkill,
      ...patch,
    });
  }

  #sendEpisodeEvent(phase: "started" | "ended", reasonCodes: string[]): void {
    const event: EpisodeEvent = {
      ...this.#envelope("EpisodeEvent", this.#embodiment.snapshot().tick),
      type: "EpisodeEvent",
      episodeId: this.#episodeId,
      phase,
      trainingContext: this.config.runtime.trainingContext,
      rngSeed: this.config.runtime.rngSeed,
      // The contamination marker travels with the evidence, so an episode
      // recorded during a debug session can never be mistaken for a counted one.
      reasonCodes: this.#operatorIntervention.flagged
        ? [...reasonCodes, "operator_intervention"]
        : reasonCodes,
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
      ledger: this.ledger,
      trainingContext: this.config.runtime.trainingContext,
      cognition: this.#cognitionState,
      previousOutcome: this.#previousOutcome,
      blockAt: (position) => this.#embodiment.blockAt(position),
      selfMotion: this.#selfMotion.sense(snapshot),
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

    // Everything physical goes through the one dispatch path, the same one an
    // operator validation run uses. The hooks below only report what happened.
    const dispatched = await dispatchSkill(
      invocation,
      {
        goalId: goal.goal.goalId,
        routineId: policy.routineId,
        contextId: policy.contextId,
      },
      this.dispatchDependencies(),
      {
        onValidation: (validation, verdict) => {
          this.#channel.send(validation);
          this.#syncStatus({
            goalType: goal.goal.goalType,
            decisions: this.#decisionCount,
            lastValidation: {
              decision: verdict.decision,
              level: verdict.level,
              requestedSkill: invocation.skillId,
              executedSkill: verdict.executedSkill,
              reasonCodes: verdict.reasonCodes,
            },
          });
        },
        onEmergency: (assessment, decisionId, preemptedSkill) => {
          this.#sendEmergency(assessment, decisionId, preemptedSkill);
          builder.addSafetyOverride({
            tick: this.#embodiment.snapshot().tick,
            level: assessment.level,
            trigger: assessment.trigger,
            action: assessment.action,
            preemptedSkill,
          });
        },
        onStarted: (started) => this.#channel.send(started),
      },
    );

    const outcome = dispatched.outcome;
    this.#channel.send(outcome);
    if (dispatched.executedSkill !== null) {
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
      this.ledger.save();
    }
    this.#record(
      builder,
      goal,
      policy,
      invocation,
      dispatched.verdict.decision,
      dispatched.verdict.level,
      dispatched.verdict.reasonCodes,
      outcome,
      dispatched.requestedSpec,
    );
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
      budgetTicks: Number(
        outcome.completionEvidence.details["timing_budget_ticks"] ?? 0,
      ),
      budgetPressure: Number(
        outcome.completionEvidence.details["timing_budget_pressure"] ?? 0,
      ),
      navigationTicks: Number(
        outcome.completionEvidence.details["timing_navigation_ticks"] ?? 0,
      ),
      interactionTicks: Number(
        outcome.completionEvidence.details["timing_interaction_ticks"] ?? 0,
      ),
      waitingTicks: Number(
        outcome.completionEvidence.details["timing_waiting_ticks"] ?? 0,
      ),
      inventoryDelta: outcome.inventoryDelta,
      outcomeMessageId: outcome.messageId,
    });
  }
}

export { summariseEpisode };
