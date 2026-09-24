import { randomUUID } from "node:crypto";
import { contains, distance, type PersonConfig } from "#config";
import {
  PROTOCOL_VERSION,
  envelope,
  protocolValidator,
  type MessageType,
  type Observation,
  type PreviousOutcome,
  type SessionIdentity,
  type SkillInvocation,
  type SkillParameters,
} from "#protocol";
import { SkillSpecError, skillRegistry, type SkillRegistry } from "#skills";
import type { Embodiment, PhysicalGuard } from "../embodiment/types.ts";
import { buildObservation } from "../observation/builder.ts";
import { StatusWriter, statusPath } from "../reporting/status.ts";
import { PermissionGate } from "../safety/permissions.ts";
import { ProtectedAreas } from "../safety/protected-areas.ts";
import { SafetyKernel } from "../safety/safety-kernel.ts";
import { InvocationValidator } from "../safety/validator.ts";
import { dispatchSkill } from "../skills/dispatch.ts";
import { implementedSkillIds } from "../skills/impl/index.ts";
import { SkillRunner } from "../skills/executor.ts";
import { PlacementLedger } from "../runtime/placement-ledger.ts";
import { compareEffects, type EffectComparison } from "./effects.ts";
import { learningChanged, learningFingerprint } from "./learning-state.ts";
import {
  SKILL_VALIDATION_REPORT_VERSION,
  skillValidationDirectory,
  writeSkillValidationReport,
  type SkillValidationReport,
} from "./report.ts";

/**
 * Validates one already-registered skill against a real body, on purpose,
 * under a human's hand.
 *
 * This is not a second way to run Person. It builds one SkillInvocation and
 * hands it to the same dispatch path the autonomous loop uses, so the safety
 * kernel, the permission gate, the cost limits, the executor and the outcome
 * accounting are all the production ones. If the kernel refuses or substitutes
 * the skill, that is the result and it is reported as such: a harness that
 * quietly reported the requested skill as the executed one would be worse than
 * no harness at all.
 *
 * It selects no goal, runs no planner, starts no learner and writes no
 * learning evidence. What it produces is one report, in its own directory,
 * with both observations in it.
 */

export interface OperatorSetupInfo {
  skillId: string;
  position: { x: number; y: number; z: number };
  home: { x: number; y: number; z: number };
  homeDistance: number;
}

/** Aborts the run before the measured skill begins. */
export class OperatorSetupAborted extends Error {
  readonly reason: string;
  constructor(reason = "operator_setup_aborted", message?: string) {
    super(message ?? "The operator did not confirm the setup");
    this.name = "OperatorSetupAborted";
    this.reason = reason;
  }
}

export interface SkillValidationOptions {
  config: PersonConfig;
  embodiment: Embodiment;
  skillId: string;
  parameters?: Readonly<Record<string, number | string | boolean>>;
  registry?: SkillRegistry;
  operatorSetup?: boolean;
  /**
   * How the operator says "go".
   *
   * Required when `operatorSetup` is set. Person stays physically inert until
   * this resolves, and the measured run never starts if it rejects.
   */
  confirmSetup?: (info: OperatorSetupInfo) => Promise<void>;
  operatorIntervention?: { reason?: string };
  disconnectTimeoutMs?: number;
  cwd?: string;
  /** Progress for a terminal, never for a decision. */
  onEvent?: (kind: string, detail: Record<string, unknown>) => void;
}

export interface SkillValidationRun {
  report: SkillValidationReport;
  reportPath: string | null;
  code: number;
}

const blankSafety = (): SkillValidationReport["safety"] => ({
  decision: null,
  level: null,
  reasonCodes: [],
  executedSkill: null,
  executedParameters: null,
  executedLimits: null,
  emergency: null,
});

export async function runSkillValidation(
  options: SkillValidationOptions,
): Promise<SkillValidationRun> {
  const config = options.config;
  const registry = options.registry ?? skillRegistry();
  const started = Date.now();
  const startedAt = new Date().toISOString();
  const testId = `st_${Date.now().toString(36)}_${randomUUID().slice(0, 8)}`;
  const identity: SessionIdentity = {
    personId: config.personId,
    sessionId: randomUUID(),
    worldId: config.worldId,
  };
  const emit = options.onEvent ?? ((): void => {});

  const report: SkillValidationReport = {
    schemaVersion: SKILL_VALIDATION_REPORT_VERSION,
    testId,
    startedAt,
    finishedAt: startedAt,
    personId: identity.personId,
    worldId: identity.worldId,
    sessionId: identity.sessionId,
    embodiment: config.runtime.embodiment,
    minecraftVersion: config.server?.version ?? null,
    trainingContext: config.runtime.trainingContext,
    protocolVersion: PROTOCOL_VERSION,
    skillLibraryRevision: registry.revision,
    requestedSkill: options.skillId,
    requestedParameters: { ...(options.parameters ?? {}) },
    requestedLimits: null,
    invocation: null,
    safety: blankSafety(),
    actualSkill: null,
    operatorSetup: options.operatorSetup === true,
    operatorIntervention: {
      flagged: options.operatorIntervention !== undefined,
      reason: options.operatorIntervention?.reason ?? null,
    },
    timeline: {
      connectedAt: null,
      setupStartedAt: null,
      setupCompletedAt: null,
      skillStartedAt: null,
      skillFinishedAt: null,
      disconnectedAt: null,
      elapsedMs: 0,
    },
    preObservation: null,
    preObservationValid: false,
    postObservation: null,
    postObservationValid: false,
    postObservationReason: null,
    outcome: null,
    terminalStatus: null,
    requestedSkillStatus: null,
    elapsedTicks: 0,
    completionEvidence: null,
    expectedEffects: [],
    observedEffects: [],
    effectComparison: null,
    navigation: {
      homePosition: null,
      startPosition: null,
      endPosition: null,
      homeDistanceBefore: null,
      homeDistanceAfter: null,
      routeStatusBefore: null,
      routeStatusAfter: null,
      stuckStateBefore: null,
      stuckStateAfter: null,
    },
    learning: {
      mode: config.learning.mode,
      policyRevisionBefore: 0,
      policyRevisionAfter: 0,
      evidenceBefore: null,
      evidenceAfter: null,
      changed: false,
    },
    disconnect: { status: "clean", detail: null },
    result: "failed",
    failure: null,
  };

  const finish = async (
    reason: string | null,
    detail: string | null,
    result: SkillValidationReport["result"],
  ): Promise<SkillValidationRun> => {
    report.result = result;
    report.failure = reason ? { reason, detail } : null;
    report.finishedAt = new Date().toISOString();
    report.timeline.elapsedMs = Date.now() - started;

    const after = learningFingerprint(config.learning.evidenceDirectory);
    report.learning.evidenceAfter = after;
    report.learning.policyRevisionAfter = after.policyRevision;
    report.learning.changed = report.learning.evidenceBefore
      ? learningChanged(report.learning.evidenceBefore, after)
      : false;

    let reportPath: string | null = null;
    try {
      reportPath = writeSkillValidationReport(
        skillValidationDirectory(config.runtime.outputDirectory),
        report,
      );
    } catch (error) {
      // The run happened whether or not the file landed. Say so rather than
      // pretending the validation itself failed.
      report.result = "failed";
      report.failure = {
        reason: "report_write_failed",
        detail: (error as Error).message.slice(0, 160),
      };
      emit("report_write_failed", { message: (error as Error).message });
    }
    return {
      report,
      reportPath,
      code: report.result === "completed" && !report.failure ? 0 : 1,
    };
  };

  // Nothing about the world is touched until the request itself is known to be
  // a real one. An unknown skill must never cost a connection.
  if (!registry.has(options.skillId))
    return finish(
      "unknown_skill",
      `${options.skillId} is not in the skill library. Known skills: ${registry.ids.join(", ")}`,
      "refused",
    );
  const spec = registry.get(options.skillId);
  if (!implementedSkillIds().includes(options.skillId))
    return finish(
      "skill_not_implemented",
      `${options.skillId} has no runtime implementation in this embodiment`,
      "refused",
    );

  let parameters: SkillParameters;
  try {
    parameters = registry.resolveParameters(
      options.skillId,
      options.parameters ?? {},
    );
  } catch (error) {
    return finish(
      "invalid_parameters",
      error instanceof SkillSpecError
        ? error.message
        : (error as Error).message,
      "refused",
    );
  }
  report.requestedParameters = parameters;
  report.requestedLimits = { ...spec.costLimits };
  report.expectedEffects = spec.expectedEffects.map((effect) => ({
    fact: effect.fact,
    op: effect.op,
    value:
      effect.scalesWith && typeof parameters[effect.scalesWith] === "number"
        ? (parameters[effect.scalesWith] as number)
        : effect.value,
  }));

  const areas = new ProtectedAreas(config);
  const permissions = new PermissionGate(config, areas);
  const kernel = new SafetyKernel(permissions);
  const validator = new InvocationValidator(registry, permissions, kernel);
  const ledger = PlacementLedger.load(
    config.runtime.outputDirectory,
    identity.worldId,
    identity.personId,
    config.world.home,
  );
  const runner = new SkillRunner({
    embodiment: options.embodiment,
    permissions,
    kernel,
    registry,
    ledger,
  });
  const guard: PhysicalGuard = {
    canEnter: (position) => permissions.mayEnter(position).allowed,
    canModify: (position) =>
      areas.permitted(position) &&
      (areas.harvestable(position) || permissions.mayBuild(position).allowed),
    canTargetEntity: (entity) =>
      permissions.mayHunt(entity).allowed ||
      permissions.mayDefend(entity).allowed,
  };
  report.navigation.homePosition = ledger.home.position;

  const before = learningFingerprint(config.learning.evidenceDirectory);
  report.learning.evidenceBefore = before;
  report.learning.policyRevisionBefore = before.policyRevision;
  report.learning.policyRevisionAfter = before.policyRevision;

  const status = new StatusWriter(
    statusPath(
      config.runtime.outputDirectory,
      identity.worldId,
      identity.personId,
    ),
    {
      command: "skill-test",
      phase: "connecting",
      connection: "connecting",
      readiness: "connecting",
      personId: identity.personId,
      botUsername: config.bot?.username ?? null,
      worldId: identity.worldId,
      sessionId: identity.sessionId,
      server: config.server ?? null,
      embodiment: config.runtime.embodiment,
      trainingContext: config.runtime.trainingContext,
      learningMode: config.learning.mode,
      policyRevision: before.policyRevision,
      skill: options.skillId,
      home: {
        position: ledger.home.position,
        distance: null,
        shelterState: ledger.home.shelterState,
      },
      operatorIntervention: report.operatorIntervention,
    },
  );

  /** Mirrors the live facts into the status file, for an operator watching. */
  const syncStatus = (
    patch: Partial<Parameters<StatusWriter["update"]>[0]> = {},
  ): void => {
    const snapshot = options.embodiment.snapshot();
    status.update({
      tick: snapshot.tick,
      dimension: snapshot.dimension,
      position: snapshot.position,
      health: snapshot.health,
      food: snapshot.food,
      lastSafePosition: snapshot.lastSafePosition,
      home: {
        position: ledger.home.position,
        distance: distance(snapshot.position, ledger.home.position),
        shelterState: ledger.home.shelterState,
      },
      safety: {
        threat: kernel.threatState(snapshot),
        emergencies: status.status.safety.emergencies,
        lastEmergency: status.status.safety.lastEmergency,
      },
      ...patch,
    });
  };

  const observe = (previousOutcome: PreviousOutcome | null): Observation =>
    buildObservation({
      identity,
      snapshot: options.embodiment.snapshot(),
      permissions,
      kernel,
      ledger,
      trainingContext: config.runtime.trainingContext,
      cognition: {
        activeGoal: null,
        activeRoutine: null,
        activeSkill: null,
        suspendedGoals: [],
      },
      previousOutcome,
      blockAt: (position) => options.embodiment.blockAt(position),
    });

  let failureReason: string | null = null;
  let failureDetail: string | null = null;
  let result: SkillValidationReport["result"] = "failed";

  try {
    options.embodiment.setGuard(guard);
    await options.embodiment.connect();
    report.timeline.connectedAt = new Date().toISOString();
    syncStatus({
      connection: "ready",
      readiness: "world ready",
      phase: "ready",
    });
    emit("connected", { skill: options.skillId });

    if (options.operatorSetup) {
      if (!options.confirmSetup)
        throw new OperatorSetupAborted(
          "operator_setup_unavailable",
          "Operator setup was requested but there is no way to confirm it",
        );
      report.timeline.setupStartedAt = new Date().toISOString();
      syncStatus({
        phase: "operator_setup",
        readiness: "waiting for operator setup",
      });
      const here = options.embodiment.snapshot();
      emit("operator_setup", {
        position: here.position,
        home: ledger.home.position,
      });
      // Person does nothing at all from here until the operator says go. The
      // body still experiences Minecraft, which is not the same as acting.
      await options.confirmSetup({
        skillId: options.skillId,
        position: here.position,
        home: ledger.home.position,
        homeDistance: distance(here.position, ledger.home.position),
      });
      report.timeline.setupCompletedAt = new Date().toISOString();
    }

    // Whatever the operator did during setup, the measured run only starts from
    // a state the test is actually about.
    const ready = options.embodiment.snapshot();
    if (!ready.connected)
      throw new OperatorSetupAborted(
        "disconnected_before_skill",
        "The connection was lost before the measured skill could start",
      );
    if (!ready.alive)
      throw new OperatorSetupAborted(
        "person_died_before_skill",
        "Person is not alive",
      );
    if (ready.dimension !== "overworld")
      throw new OperatorSetupAborted(
        "invalid_dimension",
        `Person is in the ${ready.dimension}, which this test does not cover`,
      );
    if (!contains(config.world.exploration, ready.position))
      throw new OperatorSetupAborted(
        "outside_bounds_before_skill",
        `Person is at ${ready.position.x},${ready.position.y},${ready.position.z}, outside the configured exploration area`,
      );
    if (!areas.permitted(ready.position))
      throw new OperatorSetupAborted(
        "inside_protected_area",
        "Person is standing in a protected area",
      );

    syncStatus({
      phase: "pre_observation",
      readiness: "taking the pre-skill observation",
    });
    const pre = observe(null);
    const preResult = protocolValidator().validate(pre);
    report.preObservation = pre;
    report.preObservationValid = preResult.valid;
    report.navigation.startPosition = options.embodiment.snapshot().position;
    report.navigation.homeDistanceBefore = pre.home.homeDistance;
    report.navigation.routeStatusBefore = pre.navigation.routeStatus;
    report.navigation.stuckStateBefore = pre.navigation.stuckState;
    if (!preResult.valid)
      throw new OperatorSetupAborted(
        "pre_observation_invalid",
        preResult.diagnostics.join("; ").slice(0, 200),
      );

    const invocation: SkillInvocation = {
      ...envelope(
        identity,
        "SkillInvocation" as MessageType,
        options.embodiment.snapshot().tick,
      ),
      type: "SkillInvocation",
      decisionId: randomUUID(),
      // A validation run is honest about being one. These attributions never
      // reach a learner; they exist so the outcome is readable.
      goalId: "validation",
      routineId: "skill_test",
      routineStepIndex: 0,
      skillId: options.skillId,
      skillVersion: spec.version,
      parameters,
      limits: { ...spec.costLimits },
    };
    report.invocation = invocation;

    report.timeline.skillStartedAt = new Date().toISOString();
    syncStatus({
      phase: "executing",
      readiness: `executing ${options.skillId}`,
      skill: options.skillId,
    });

    const dispatched = await dispatchSkill(
      invocation,
      {
        goalId: "validation",
        routineId: "skill_test",
        contextId: "validation",
      },
      {
        registry,
        validator,
        runner,
        embodiment: options.embodiment,
        envelope: (type, tick) => envelope(identity, type, tick),
      },
      {
        onValidation: (validation, verdict) => {
          report.safety = {
            decision: verdict.decision,
            level: verdict.level,
            reasonCodes: [...verdict.reasonCodes],
            executedSkill: verdict.executedSkill,
            executedParameters: verdict.executedParameters,
            executedLimits: verdict.executedLimits,
            emergency: verdict.emergency
              ? {
                  level: verdict.emergency.level,
                  trigger: verdict.emergency.trigger,
                  action: verdict.emergency.action,
                }
              : null,
          };
          status.update({
            lastValidation: {
              decision: validation.decision,
              level: validation.level,
              requestedSkill: validation.requestedSkill,
              executedSkill: validation.executedSkill,
              reasonCodes: validation.reasonCodes,
            },
            skill: validation.executedSkill ?? options.skillId,
          });
          emit("validated", {
            decision: verdict.decision,
            executedSkill: verdict.executedSkill,
          });
        },
        onEmergency: (assessment, _decisionId, preemptedSkill) => {
          report.safety.emergency = {
            level: assessment.level,
            trigger: assessment.trigger,
            action: assessment.action,
          };
          emit("emergency", {
            trigger: assessment.trigger,
            action: assessment.action,
            preemptedSkill,
          });
        },
      },
    );
    report.timeline.skillFinishedAt = new Date().toISOString();

    const outcome = dispatched.outcome;
    report.outcome = outcome;
    report.actualSkill = outcome.executedSkill;
    report.terminalStatus = outcome.status;
    report.requestedSkillStatus = outcome.requestedSkillStatus;
    report.elapsedTicks = outcome.elapsedTicks;
    report.completionEvidence = outcome.completionEvidence;
    report.expectedEffects = outcome.expectedEffects;
    report.observedEffects = outcome.effects;
    ledger.save();

    syncStatus({
      phase: "post_observation",
      readiness: "taking the post-skill observation",
      skill: outcome.executedSkill,
    });
    const settled = options.embodiment.snapshot();
    if (!settled.connected) {
      report.postObservationReason = "disconnected";
    } else {
      try {
        const post = observe({
          requestedSkill: outcome.requestedSkill,
          executedSkill: outcome.executedSkill,
          status: outcome.status,
          effects: outcome.effects,
          healthCost: outcome.healthCost,
          resourceCost: outcome.resourceCost,
          elapsedTicks: outcome.elapsedTicks,
          interruptReason: outcome.interruptReason,
        });
        const postResult = protocolValidator().validate(post);
        report.postObservation = post;
        report.postObservationValid = postResult.valid;
        report.postObservationReason = postResult.valid
          ? null
          : postResult.diagnostics.join("; ").slice(0, 200);
        report.navigation.endPosition = options.embodiment.snapshot().position;
        report.navigation.homeDistanceAfter = post.home.homeDistance;
        report.navigation.routeStatusAfter = post.navigation.routeStatus;
        report.navigation.stuckStateAfter = post.navigation.stuckState;
      } catch (error) {
        report.postObservationReason = (error as Error).message.slice(0, 160);
      }
    }

    result =
      report.safety.decision === "ACCEPT" && outcome.status === "SUCCESS"
        ? "completed"
        : report.safety.decision === "REJECT"
          ? "refused"
          : "failed";
    if (result !== "completed") {
      failureReason =
        report.safety.decision === "REJECT"
          ? "safety_rejected"
          : outcome.executedSkill !== options.skillId
            ? "skill_replaced"
            : `skill_${outcome.status.toLowerCase()}`;
      failureDetail = outcome.reasonCodes.join(", ") || null;
    }
  } catch (error) {
    const failure = error as {
      reason?: string;
      hint?: string | null;
      message?: string;
    };
    failureReason = failure.reason ?? "unknown_error";
    failureDetail = (failure.message ?? String(error)).slice(0, 200);
    result = error instanceof OperatorSetupAborted ? "refused" : "failed";
    status.update({
      connection: "failed",
      failureReason,
      failureHint: failure.hint ?? null,
    });
    emit("failed", { reason: failureReason, detail: failureDetail });
  } finally {
    // Every path releases the body, and a server that stops answering must not
    // be able to hold the command open.
    const timeout = options.disconnectTimeoutMs ?? 10000;
    let timer: NodeJS.Timeout | undefined;
    let timedOut = true;
    await Promise.race([
      options.embodiment.disconnect().then(() => {
        timedOut = false;
      }),
      new Promise<void>((resolve) => {
        timer = setTimeout(resolve, timeout);
      }),
    ])
      .catch((error: unknown) => {
        timedOut = false;
        report.disconnect = {
          status: "failed",
          detail: (error as Error).message.slice(0, 160),
        };
      })
      .finally(() => {
        if (timer) clearTimeout(timer);
      });
    if (timedOut && report.disconnect.status === "clean")
      report.disconnect = { status: "timed_out", detail: null };
    report.timeline.disconnectedAt = new Date().toISOString();
    status.update({
      phase: "stopped",
      connection:
        status.status.connection === "failed" ? "failed" : "disconnected",
      readiness: "stopped",
    });
  }

  // The body is released before anything is analysed: the comparison is
  // arithmetic over two JSON documents and has no business holding a session
  // to a Minecraft server open.
  if (report.preObservation) {
    const request = {
      expectedEffects: report.expectedEffects,
      before: report.preObservation,
      after: report.postObservation,
    };
    const comparison: EffectComparison = await compareEffects(request, {
      command: config.cognition.command,
      cwd: options.cwd ?? process.cwd(),
    });
    report.effectComparison = comparison;
  }

  return finish(failureReason, failureDetail, result);
}
