import type { MessageType } from "./version.ts";

export interface Position {
  x: number;
  y: number;
  z: number;
}

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
export type TrainingContext =
  "fixture" | "minecraft_peaceful" | "minecraft_normal" | "replay";
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

/**
 * Where something is, as Person perceives it.
 *
 * Relative to Person and qualitative, because a world coordinate is a fact
 * about the server rather than a fact about anyone's experience. Bearings are
 * relative to where Person is facing: Person has no compass, and a heading in
 * degrees would be the coordinate problem in another notation.
 */
export interface RelativeLocation {
  bearing:
    | "ahead"
    | "ahead_left"
    | "ahead_right"
    | "left"
    | "right"
    | "behind_left"
    | "behind_right"
    | "behind";
  elevation: "above" | "level" | "below";
  rangeBand: "reach" | "near" | "mid" | "far";
  /** Estimated straight-line distance. Coarser the further away it is. */
  distance: number;
  /**
   * Whether Person is looking at this, or merely aware of it.
   *
   * Everything reported is perceptible. Only a `central` percept was close
   * enough to the view axis to be identified: a `peripheral` one carries a
   * bearing and a coarse category and withholds precise identity, because
   * recognising what a thing is happens near the middle of the field.
   */
  detail: "central" | "peripheral";
}

export interface EntityRecord extends RelativeLocation {
  /** The species, when Person is looking straight enough at it to tell. */
  name?: string;
  /**
   * Whose it is, and whether the runtime would let Person hunt it. Like the
   * species, these are present only on a `central` percept: a nametag or a
   * collar is read off a thing Person is looking at, and the hunting verdict
   * is derived from them.
   */
  named?: boolean;
  tamed?: boolean;
  protectedTarget?: boolean;
  /**
   * The account name on the nameplate above a player's head.
   *
   * Optional rather than required: a mob has no account name, and an
   * observation recorded before this existed is still a valid observation. The
   * account UUID is deliberately not reported, because it is a protocol
   * identifier rather than anything Person could perceive.
   */
  username?: string;
}

export interface ResourceRecord extends RelativeLocation {
  kind: "wood" | "stone" | "coal" | "plant_food" | "dirt" | "other";
  /** The exact block, when it was recognised rather than merely noticed. */
  name?: string;
  harvestPermitted: boolean;
}

export interface ContainerRecord extends RelativeLocation {
  kind: "chest" | "barrel" | "furnace" | "shulker" | "other";
  provenance: "owned" | "existing";
  storageId: string | null;
}

export interface WorkstationRecord extends RelativeLocation {
  kind: "crafting_table" | "furnace" | "anvil" | "other";
  provenance: "owned" | "existing";
  /**
   * Where this came from. Workstations are read out of Person's own placement
   * ledger rather than seen, so they are reported even when Person is facing
   * the other way, and they are the one channel in `nearby` that is not
   * current perception. Marked so it cannot be mistaken for one, and named
   * for the runtime record it is, so it cannot be mistaken for something
   * Person recalled either.
   */
  source: "placement_ledger";
}

export interface HazardRecord extends RelativeLocation {
  kind:
    | "lava"
    | "fire"
    | "water"
    | "cactus"
    | "magma"
    | "fall"
    | "suffocation"
    | "other";
}

export interface OwnedStorageView {
  storageId: string;
  contents: ItemStack[];
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

export interface Observation extends Envelope {
  type: "Observation";
  observationVersion: number;
  trainingContext: TrainingContext;
  selfMotion: SelfMotionPercept;
  vitals: {
    health: number;
    food: number;
    saturation: number;
    air: number;
    armor: number;
    statusEffects: {
      name: string;
      amplifier: number;
      remainingTicks: number;
    }[];
    alive: boolean;
  };
  environment: {
    dimension: "overworld" | "nether" | "end";
    dayPhase: "dawn" | "day" | "dusk" | "night";
    timeOfDay: number;
    weather: "clear" | "rain" | "thunder";
    lightLevel: number;
    biome: string;
  };
  inventory: {
    items: ItemStack[];
    categories: Record<string, number>;
    freeSlots: number;
  };
  permissions: {
    harvest: boolean;
    mine: boolean;
    build: boolean;
    huntPassive: boolean;
    depositOwned: boolean;
    withdrawOwned: boolean;
    withdrawExisting: boolean;
    craft: boolean;
    consume: boolean;
  };
  affordances: {
    diggableGround: boolean;
    shelterSite: boolean;
    storageSite: boolean;
  };
  nearby: {
    resources: ResourceRecord[];
    hostiles: EntityRecord[];
    passiveAnimals: EntityRecord[];
    players: EntityRecord[];
    containers: ContainerRecord[];
    workstations: WorkstationRecord[];
    hazards: HazardRecord[];
  };
  home: {
    activeHome: { homeId: string } | null;
    shelterState: "none" | "partial" | "complete" | "breached" | "unknown";
    ownedStorage: OwnedStorageView[];
    bedKnown: boolean;
    foodReserve: number;
    fuelReserve: number;
  };
  navigation: {
    routeStatus: "idle" | "ok" | "blocked" | "unknown";
    pathRisk: "low" | "moderate" | "high";
    stuckState: "free" | "slow" | "stuck";
    returnPathKnown: boolean;
  };
  cognition: {
    activeGoal: string | null;
    activeRoutine: string | null;
    activeSkill: string | null;
    suspendedGoals: string[];
  };
  previousOutcome: PreviousOutcome | null;
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
  trigger: string;
  reasonCodes: string[];
  action:
    | "flee"
    | "dig_in"
    | "eat_to_target"
    | "return_home"
    | "cancel_skill"
    | "reject_proposal";
  preemptedSkill: string | null;
}

export interface EpisodeEvent extends Envelope {
  type: "EpisodeEvent";
  episodeId: string;
  phase: "started" | "ended";
  trainingContext: TrainingContext;
  rngSeed: number | null;
  reasonCodes: string[];
}

export interface SessionHello extends Envelope {
  type: "SessionHello";
  learningMode: LearningMode;
  trainingContext: TrainingContext;
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
  | EpisodeEvent;
export type ProtocolMessage = CognitionMessage | NodeMessage;
