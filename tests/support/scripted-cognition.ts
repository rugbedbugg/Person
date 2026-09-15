#!/usr/bin/env node
/**
 * A scripted stand-in for the cognition process.
 *
 * It speaks the real protocol over the real transport but always proposes the
 * same skill, which is how a test can put the runtime in a position the real
 * learner would never choose: asking to gather wood while a hostile is in
 * contact range. What the runtime does about that is the thing under test.
 *
 * Parameters are sent as given, without checking them against the skill spec,
 * so a test can also prove that the runtime rejects a malformed proposal
 * rather than relying on the proposer to behave.
 *
 * Usage: scripted-cognition.ts <skillId> [--name=value ...]
 */
import { randomUUID } from "node:crypto";
import {
  LineReader,
  PROTOCOL_VERSION,
  decodeFrame,
  encodeFrame,
  protocolValidator,
  type Envelope,
} from "#protocol";
import { skillRegistry } from "#skills";

const [, , skillId = "gather_wood", ...rest] = process.argv;
const overrides: Record<string, number | string | boolean> = {};
for (const argument of rest) {
  const [name, value] = argument.replace(/^--/, "").split("=");
  if (!name || value === undefined) continue;
  overrides[name] = Number.isNaN(Number(value)) ? value : Number(value);
}

const registry = skillRegistry();
const validator = protocolValidator();
const reader = new LineReader();
let identity = { personId: "ada", sessionId: randomUUID(), worldId: "world" };
let counter = 0;

const envelope = (type: string, tick: number): Envelope =>
  ({
    protocolVersion: PROTOCOL_VERSION,
    messageId: randomUUID(),
    personId: identity.personId,
    sessionId: identity.sessionId,
    worldId: identity.worldId,
    tick,
    timestamp: new Date().toISOString(),
    type,
  }) as Envelope;

const send = (message: Record<string, unknown>): void => {
  const result = validator.validate(message);
  if (!result.valid) {
    process.stderr.write(
      `scripted cognition refused to send: ${result.diagnostics.join("; ")}\n`,
    );
    return;
  }
  process.stdout.write(encodeFrame(message));
};

const goalRecord = (tick: number) => ({
  goalId: "goal_secure_shelter",
  goalType: "SECURE_SHELTER",
  priority: 400,
  source: "homeostasis",
  createdAtTick: tick,
  status: "ACTIVE",
  completionCondition: [{ fact: "shelter_complete", op: ">=", value: 1 }],
  suspensionReason: null,
});

process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk: string) => {
  const { lines } = reader.push(chunk);
  for (const line of lines) {
    const frame = decodeFrame(line);
    if (!frame.ok) continue;
    const message = frame.value as Record<string, unknown>;
    const tick = Number(message["tick"] ?? 0);
    if (message["type"] === "SessionHello") {
      identity = {
        personId: String(message["personId"]),
        sessionId: String(message["sessionId"]) as typeof identity.sessionId,
        worldId: String(message["worldId"]),
      };
      send({
        ...envelope("CognitionReady", tick),
        type: "CognitionReady",
        cognitionVersion: "scripted",
        policyRevision: 0,
        learningMode: String(message["learningMode"]),
        restoredEvents: 0,
        restoredRoutines: 0,
        snapshotTick: null,
      });
      continue;
    }
    if (message["type"] !== "Observation") continue;
    counter += 1;
    const decisionId = randomUUID();
    const spec = registry.get(skillId);
    send({
      ...envelope("GoalDecision", tick),
      type: "GoalDecision",
      decisionId,
      goal: goalRecord(tick),
      reasonCodes: ["scripted"],
      stack: [goalRecord(tick)],
    });
    send({
      ...envelope("PolicyDecision", tick),
      type: "PolicyDecision",
      decisionId,
      goalId: "goal_secure_shelter",
      contextId:
        "h_healthy.f_full.d_day.t_immediate.hm_at_home.tt_none.fs_none",
      routineId: "r_scripted",
      routineName: "scripted_routine",
      steps: [skillId],
      confidence: 0.5,
      reasonCodes: ["scripted"],
      evidenceRefs: [],
      policyRevision: 0,
      learnedOrFallback: "fallback",
      candidates: [],
      shadowRoutineId: null,
    });
    send({
      ...envelope("SkillInvocation", tick),
      type: "SkillInvocation",
      decisionId,
      goalId: "goal_secure_shelter",
      routineId: "r_scripted",
      routineStepIndex: Math.min(counter - 1, 63),
      skillId,
      skillVersion: spec.version,
      parameters: {
        ...Object.fromEntries(
          Object.entries(spec.parameters).map(([name, parameter]) => [
            name,
            parameter.default,
          ]),
        ),
        ...overrides,
      },
      limits: { ...spec.costLimits },
    });
  }
});
