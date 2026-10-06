/**
 * The core, environment-neutral configuration (ADR 0025). The environment
 * named in `environment.kind` owns every other key of the document, through
 * its own configuration schema and its own typed view: Minecraft's is
 * `MinecraftConfig` in `#minecraft`.
 */
export interface CoreConfig {
  configVersion: 3;
  personId: string;
  worldId: string;
  environment: { kind: string };
  runtime: {
    /** Which embodiment of the environment; the profile names the legal ones. */
    embodiment: string;
    outputDirectory: string;
    rngSeed: number | null;
    maxDecisions: number;
    maxTicks: number;
    decisionIntervalMs: number;
    /** ADR 0017, I2: tries to reach the world again before giving up. */
    reconnectAttempts: number;
    reconnectIntervalMs: number;
    fixtureWorld?: string;
  };
  learning: {
    mode: "off" | "shadow" | "supervised";
    evidenceDirectory: string;
    snapshotEveryEvents: number;
    explorationBonus: number;
    minimumSupport: number;
  };
  /** What a death means (ADR 0017, I3); the runtime's alone. */
  lifecycle?: {
    death?: "respawn" | "permadeath";
  };
  /** Who this Person is (ADR 0017): written once, into the founding event. */
  identity?: {
    name?: string;
    designation?: string;
  };
  /** Cognition's alone (ADR 0013): the runtime never reads it. */
  affect?: {
    mode: "off" | "record_only" | "active";
    interoception?: "on" | "off";
  };
  /** ADR 0020: read by cognition only; the runtime ignores it. */
  deliberation?: {
    mode?: "off" | "record_only" | "active";
    backend?: "scripted";
    scriptedAnswers?: string;
    habits?: "off" | "record_only" | "active";
    affectArbitration?: "off" | "record_only" | "active";
  };
  cognition: {
    command: string[];
    startTimeoutMs: number;
    decisionTimeoutMs: number;
  };
}
