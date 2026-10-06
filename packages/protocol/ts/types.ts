import type { MessageType } from "./version.ts";

export interface ItemStack {
  name: string;
  count: number;
}

export interface ItemDelta {
  name: string;
  delta: number;
}

export const TERMINAL_STATUSES = [
  "SUCCESS",
  "FAILED",
  "INTERRUPTED",
  "PREEMPTED",
  "TIMED_OUT",
  "INVALIDATED",
  "UNREACHABLE",
  "DEATH",
  "DISCONNECTED",
] as const;
export type TerminalStatus = (typeof TERMINAL_STATUSES)[number];

export type SafetyLevel = "L0" | "L1" | "L2" | "L3" | "L4";
export type LearningMode = "off" | "shadow" | "supervised";
/**
 * Which experience stream a message belongs to (ADR 0025). The environment,
 * embodiment and variant names are owned by environment profiles; the core
 * knows only whether the stream is lived or replayed.
 */
export type ExperienceContext = "lived" | "replay";
export interface Experience {
  context: ExperienceContext;
  environmentKind: string;
  embodimentKind: string;
  environmentVariant: string | null;
}
export type ValidationVerdict = "ACCEPT" | "REJECT" | "PREEMPT" | "REPLACE";
export type SkillParameters = Readonly<
  Record<string, number | string | boolean>
>;

export interface CostLimits {
  maxTicks: number;
  maxDistance: number;
  minHealth: number;
}

export interface Envelope {
  protocolVersion: string;
  messageId: string;
  personId: string;
  sessionId: string;
  worldId: string;
  tick: number;
  timestamp: string;
  type: MessageType;
}

export interface PreviousOutcome {
  requestedSkill: string;
  executedSkill: string | null;
  status: TerminalStatus;
  effects: string[];
  healthCost: number;
  resourceCost: ItemDelta[];
  elapsedTicks: number;
  interruptReason: string | null;
}

/**
 * Person's felt sense of its own motion since the previous observation, in
 * the frame of its facing at that observation (ADR 0008). Coarse, relative,
 * and with no absolute position or heading anywhere in it.
 */
export interface SelfMotionPercept {
  continuity: "start" | "continuous" | "discontinuous";
  translation: {
    direction:
      | "ahead"
      | "ahead_left"
      | "ahead_right"
      | "left"
      | "right"
      | "behind_left"
      | "behind_right"
      | "behind"
      | "none"
      | "unknown";
    band: "none" | "tiny" | "short" | "moderate" | "far" | "unknown";
    distance: number | null;
  };
  rotation:
    | "none"
    | "slight_left"
    | "left"
    | "sharp_left"
    | "about_face"
    | "sharp_right"
    | "right"
    | "slight_right"
    | "unknown";
  vertical: "level" | "up" | "down" | "unknown";
}

/** What the runtime echoes of cognition's own state. */
export interface CognitionEcho {
  activeGoal: string | null;
  activeRoutine: string | null;
  activeSkill: string | null;
  suspendedGoals: string[];
}

/**
 * One observation: an environment-neutral envelope around an
 * environment-owned payload (ADR 0025). `Payload` is the environment
 * profile's own strongly typed percept record; the core never looks inside it.
 */
export interface Observation<Payload = unknown> extends Envelope {
  type: "Observation";
  observationVersion: number;
  experience: Experience;
  selfMotion: SelfMotionPercept;
  cognition: CognitionEcho;
  previousOutcome: PreviousOutcome | null;
  payload: Payload;
}

export interface SkillInvocation extends Envelope {
  type: "SkillInvocation";
  decisionId: string;
  goalId: string;
  routineId: string;
  routineStepIndex: number;
  skillId: string;
  skillVersion: number;
  parameters: SkillParameters;
  limits: CostLimits;
}

export interface ValidationDecision extends Envelope {
  type: "ValidationDecision";
  decisionId: string;
  requestedSkill: string;
  decision: ValidationVerdict;
  level: SafetyLevel;
  reasonCodes: string[];
  executedSkill: string | null;
  executedParameters: SkillParameters | null;
  executedLimits: CostLimits | null;
}

export interface SkillStarted extends Envelope {
  type: "SkillStarted";
  decisionId: string;
  requestedSkill: string;
  executedSkill: string;
  parameters: SkillParameters;
  limits: CostLimits;
  startTick: number;
  startHealth: number;
  startFood: number;
  startInventory: ItemStack[];
}

export interface ExpectedEffect {
  fact: string;
  op: "+=" | "-=" | "=" | "max";
  value: number;
}

export interface SkillOutcome extends Envelope {
  type: "SkillOutcome";
  decisionId: string;
  goalId: string;
  routineId: string;
  contextId: string;
  requestedSkill: string;
  requestedParameters: SkillParameters;
  requestedSkillStatus: TerminalStatus;
  executedSkill: string | null;
  executedParameters: SkillParameters | null;
  status: TerminalStatus;
  emergency: boolean;
  reasonCodes: string[];
  effects: string[];
  expectedEffects: ExpectedEffect[];
  healthBefore: number;
  healthAfter: number;
  foodBefore: number;
  foodAfter: number;
  healthCost: number;
  resourceCost: ItemDelta[];
  inventoryDelta: ItemDelta[];
  elapsedTicks: number;
  interruptReason: string | null;
  completionEvidence: {
    kinds: string[];
    details: Record<string, number | string | boolean | null>;
  };
}

export interface EmergencyEvent extends Envelope {
  type: "EmergencyEvent";
  decisionId: string | null;
  level: "L0" | "L1";
  /** The environment profile's emergency vocabulary (environment.json). */
  trigger: string;
  reasonCodes: string[];
  /** The environment profile's emergency vocabulary (environment.json). */
  action: string;
  preemptedSkill: string | null;
}

export interface EpisodeEvent extends Envelope {
  type: "EpisodeEvent";
  episodeId: string;
  phase: "started" | "ended";
  experience: Experience;
  rngSeed: number | null;
  reasonCodes: string[];
}

/** Whether the world is available to the body now (ADR 0017, I2). */
export interface WorldAvailability extends Envelope {
  type: "WorldAvailability";
  state: "available" | "unavailable";
  reasonCodes: string[];
}

/** The runtime observed a death, or a respawn (ADR 0017, I3). */
export interface LifeEvent extends Envelope {
  type: "LifeEvent";
  event: "died" | "respawned";
  terminal: boolean;
  reasonCodes: string[];
}

export interface SessionHello extends Envelope {
  type: "SessionHello";
  learningMode: LearningMode;
  experience: Experience;
  policyRevision: number;
  skillLibraryRevision: string;
  rngSeed: number | null;
  evidenceDirectory: string;
  skillIds: string[];
}

export interface CognitionReady extends Envelope {
  type: "CognitionReady";
  cognitionVersion: string;
  policyRevision: number;
  learningMode: LearningMode;
  restoredEvents: number;
  restoredRoutines: number;
  snapshotTick: number | null;
  /** ADR 0017, I3: whether the reconstructed Person awaits a respawn. */
  lifeStatus?: "alive" | "awaiting_respawn";
}

export interface GoalRecord {
  goalId: string;
  goalType: string;
  priority: number;
  source: string;
  createdAtTick: number;
  status: string;
  completionCondition: { fact: string; op: string; value: number }[];
  suspensionReason: string | null;
}

export interface GoalDecision extends Envelope {
  type: "GoalDecision";
  decisionId: string;
  goal: GoalRecord;
  reasonCodes: string[];
  stack: GoalRecord[];
}

export interface PolicyDecision extends Envelope {
  type: "PolicyDecision";
  decisionId: string;
  goalId: string;
  contextId: string;
  routineId: string;
  routineName: string;
  steps: string[];
  confidence: number;
  reasonCodes: string[];
  evidenceRefs: string[];
  policyRevision: number;
  learnedOrFallback: "learned" | "fallback";
  candidates: {
    routineId: string;
    routineName: string;
    score: number;
    attempts: number;
    successes: number;
    meanSuccess: number;
  }[];
  shadowRoutineId: string | null;
}

export type CognitionMessage =
  CognitionReady | GoalDecision | PolicyDecision | SkillInvocation;
export type NodeMessage =
  | SessionHello
  | Observation
  | ValidationDecision
  | SkillStarted
  | SkillOutcome
  | EmergencyEvent
  | EpisodeEvent
  | WorldAvailability
  | LifeEvent;
export type ProtocolMessage = CognitionMessage | NodeMessage;
