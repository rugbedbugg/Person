import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { validateConfig, type PersonConfig, type Position } from "#config";
import { FixtureWorld, type FixtureWorldDefinition } from "#fixture-world";
import {
  PermissionGate,
  ProtectedAreas,
  SafetyKernel,
  SkillRunner,
  PlacementLedger,
  InvocationValidator,
  type ExecutionResult,
  type PhysicalGuard,
} from "#node-runtime";
import { skillRegistry } from "#skills";

export const REPOSITORY = fileURLToPath(new URL("../../", import.meta.url));

export function temporaryDirectory(prefix = "person-test-"): string {
  return mkdtempSync(path.join(tmpdir(), prefix));
}

export interface HarnessOptions {
  world?: Partial<FixtureWorldDefinition>;
  worldFile?: string;
  config?: Partial<PersonConfig>;
  protectedAreas?: PersonConfig["world"]["protectedAreas"];
  home?: Position;
  outputDirectory?: string;
}

export function baseConfig(options: HarnessOptions = {}): PersonConfig {
  const home = options.home ?? { x: 0, y: 64, z: 0 };
  return validateConfig(
    {
      configVersion: 2,
      personId: "ada",
      worldId: "test-world",
      runtime: {
        embodiment: "fixture",
        trainingContext: "fixture",
        outputDirectory: options.outputDirectory ?? temporaryDirectory(),
        rngSeed: 1,
        maxDecisions: 20,
        maxTicks: 48000,
        decisionIntervalMs: 0,
      },
      learning: {
        mode: "off",
        evidenceDirectory: temporaryDirectory("person-evidence-"),
      },
      cognition: { command: ["true"] },
      world: {
        home,
        exploration: {
          min: { x: -48, y: 56, z: -48 },
          max: { x: 48, y: 80, z: 48 },
        },
        resourceAreas: [
          { min: { x: -48, y: 56, z: -48 }, max: { x: 48, y: 80, z: 48 } },
        ],
        protectedAreas: options.protectedAreas ?? [
          { min: { x: 20, y: 56, z: 20 }, max: { x: 28, y: 80, z: 28 } },
        ],
      },
      permissions: {
        containers: {
          existing: { withdraw: true, deposit: false },
          owned: { withdraw: true, deposit: true },
        },
        hunting: {
          passiveUnnamedAnimals: true,
          namedAnimals: false,
          tamedAnimals: false,
        },
        players: { combat: false },
        villagers: { harm: false },
        building: { enabled: true },
        protectedAreas: { enforcement: "strict" },
      },
      ...options.config,
    },
    REPOSITORY,
  );
}

export interface Harness {
  world: FixtureWorld;
  config: PersonConfig;
  ledger: PlacementLedger;
  permissions: PermissionGate;
  kernel: SafetyKernel;
  validator: InvocationValidator;
  runner: SkillRunner;
  guard: PhysicalGuard;
  run(
    skillId: string,
    parameters?: Record<string, number | string | boolean>,
  ): Promise<ExecutionResult>;
}

/** A runtime with a fixture body and no cognition process, for skill-level tests. */
export async function harness(options: HarnessOptions = {}): Promise<Harness> {
  const config = baseConfig(options);
  const world = options.worldFile
    ? FixtureWorld.fromFile(path.join(REPOSITORY, options.worldFile))
    : new FixtureWorld(options.world ?? {});
  const registry = skillRegistry();
  const ledger = new PlacementLedger(
    config.worldId,
    config.personId,
    config.world.home,
  );
  const areas = new ProtectedAreas(config);
  const permissions = new PermissionGate(config, areas);
  const kernel = new SafetyKernel(permissions);
  const validator = new InvocationValidator(registry, permissions, kernel);
  const guard: PhysicalGuard = {
    canEnter: (position) => permissions.mayEnter(position).allowed,
    canModify: (position) =>
      areas.permitted(position) &&
      (areas.harvestable(position) || permissions.mayBuild(position).allowed),
    canTargetEntity: (entity) =>
      permissions.mayHunt(entity).allowed ||
      permissions.mayDefend(entity).allowed,
  };
  world.setGuard(guard);
  await world.connect();
  const runner = new SkillRunner({
    embodiment: world,
    permissions,
    kernel,
    registry,
    ledger,
  });

  return {
    world,
    config,
    ledger,
    permissions,
    kernel,
    validator,
    runner,
    guard,
    run: (skillId, parameters = {}) =>
      runner.run({
        skillId,
        parameters: registry.resolveParameters(skillId, parameters),
        limits: { ...registry.get(skillId).costLimits },
        emergency: registry.get(skillId).emergency,
      }),
  };
}
