/**
 * The wire contract between the Python cognition process and the Node runtime.
 *
 * The version string is embedded in every message and in every persisted
 * evidence record. A backward-incompatible change must take a new name so old
 * evidence stays interpretable instead of being silently reinterpreted.
 */
export const PROTOCOL_VERSION = "shroud-learning-v2";

/** Message types the Node runtime is allowed to emit. */
export const NODE_MESSAGE_TYPES = [
  "SessionHello",
  "Observation",
  "ValidationDecision",
  "SkillStarted",
  "SkillOutcome",
  "EmergencyEvent",
  "EpisodeEvent",
] as const;

/** Message types the cognition process is allowed to emit. */
export const COGNITION_MESSAGE_TYPES = [
  "CognitionReady",
  "GoalDecision",
  "PolicyDecision",
  "SkillInvocation",
] as const;

export const MESSAGE_TYPES = [
  ...NODE_MESSAGE_TYPES,
  ...COGNITION_MESSAGE_TYPES,
] as const;

export type NodeMessageType = (typeof NODE_MESSAGE_TYPES)[number];
export type CognitionMessageType = (typeof COGNITION_MESSAGE_TYPES)[number];
export type MessageType = (typeof MESSAGE_TYPES)[number];

/** Schema file for each message type, relative to the schemas directory. */
export const SCHEMA_FILES: Readonly<Record<MessageType, string>> =
  Object.freeze({
    SessionHello: "session-hello.schema.json",
    Observation: "observation.schema.json",
    ValidationDecision: "validation-decision.schema.json",
    SkillStarted: "skill-started.schema.json",
    SkillOutcome: "skill-outcome.schema.json",
    EmergencyEvent: "emergency-event.schema.json",
    EpisodeEvent: "episode-event.schema.json",
    CognitionReady: "cognition-ready.schema.json",
    GoalDecision: "goal-decision.schema.json",
    PolicyDecision: "policy-decision.schema.json",
    SkillInvocation: "skill-invocation.schema.json",
  });
