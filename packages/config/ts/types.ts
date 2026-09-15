export interface Position {
  x: number;
  y: number;
  z: number;
}

export interface Box {
  min: Position;
  max: Position;
}

export interface ContainerPermissions {
  existing: { withdraw: boolean; deposit: false };
  owned: { withdraw: boolean; deposit: boolean };
}

export interface Permissions {
  containers: ContainerPermissions;
  hunting: {
    passiveUnnamedAnimals: boolean;
    namedAnimals: false;
    tamedAnimals: false;
  };
  players: { combat: false };
  villagers: { harm: false };
  building: { enabled: boolean };
  protectedAreas: { enforcement: "strict" };
}

export interface PersonConfig {
  configVersion: 2;
  personId: string;
  worldId: string;
  runtime: {
    embodiment: "fixture" | "minecraft";
    trainingContext:
      "fixture" | "minecraft_peaceful" | "minecraft_normal" | "replay";
    outputDirectory: string;
    rngSeed: number | null;
    maxDecisions: number;
    maxTicks: number;
    decisionIntervalMs: number;
    fixtureWorld?: string;
  };
  learning: {
    mode: "off" | "shadow" | "supervised";
    evidenceDirectory: string;
    snapshotEveryEvents: number;
    explorationBonus: number;
    minimumSupport: number;
  };
  cognition: {
    command: string[];
    startTimeoutMs: number;
    decisionTimeoutMs: number;
  };
  server?: { host: string; port: number; version: "1.16.1" };
  bot?: { username: string; auth: "offline" };
  authorization?: Record<string, boolean>;
  world: {
    home: Position;
    exploration: Box;
    resourceAreas: Box[];
    protectedAreas: Box[];
  };
  permissions: Permissions;
}
