import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import type { PersonConfig } from "#config";
import { FixtureWorld } from "#fixture-world";
import {
  readStatus,
  runSkillValidation,
  skillValidationDirectory,
  statusPath,
  type Embodiment,
  type OperatorSetupInfo,
  type SkillValidationReport,
} from "#node-runtime";
import { protocolValidator } from "#protocol";
import { skillRegistry } from "#skills";
import {
  REPOSITORY,
  baseConfig,
  temporaryDirectory,
} from "../support/harness.ts";

/**
 * The single-skill validation harness.
 *
 * Everything here runs against the fixture world, which implements the same
 * embodiment port Mineflayer does. What these tests are actually about is not
 * the fixture: it is that the harness reaches the body only through the
 * production safety kernel and executor, tells the truth about what ran, and
 * leaves the learner exactly as it found it.
 */

const PHYSICAL = [
  "moveTo",
  "dig",
  "place",
  "craft",
  "smelt",
  "consume",
  "attack",
  "deposit",
  "withdraw",
  "inspectContainer",
  "waitTicks",
] as const;

/** Records every call made to a body without changing what it does. */
function watched(world: FixtureWorld): {
  body: Embodiment;
  calls: string[];
} {
  const calls: string[] = [];
  const body = new Proxy(world, {
    get(target, property) {
      if (typeof property !== "string")
        return Reflect.get(target, property, target);
      const value = Reflect.get(target, property, target);
      if (typeof value !== "function") return value;
      return (...args: unknown[]) => {
        calls.push(property);
        return (value as (...rest: unknown[]) => unknown).apply(target, args);
      };
    },
  }) as unknown as Embodiment;
  return { body, calls };
}

interface Fixture {
  config: PersonConfig;
  world: FixtureWorld;
}

function fixture(
  options: {
    spawn?: { x: number; y: number; z: number };
    entities?: {
      name: string;
      position: { x: number; y: number; z: number };
    }[];
    config?: Partial<PersonConfig>;
    outputDirectory?: string;
    evidenceDirectory?: string;
  } = {},
): Fixture {
  const base = baseConfig({
    home: { x: 0, y: 64, z: 0 },
    ...(options.outputDirectory
      ? { outputDirectory: options.outputDirectory }
      : {}),
    ...(options.config ? { config: options.config } : {}),
  });
  const config: PersonConfig = options.evidenceDirectory
    ? {
        ...base,
        learning: {
          ...base.learning,
          evidenceDirectory: options.evidenceDirectory,
        },
      }
    : base;
  const world = new FixtureWorld({
    spawn: options.spawn ?? { x: 0, y: 64, z: 0 },
    ...(options.entities ? { entities: options.entities } : {}),
  });
  return { config, world };
}

const reportsIn = (config: PersonConfig): string[] => {
  const directory = skillValidationDirectory(config.runtime.outputDirectory);
  return existsSync(directory) ? readdirSync(directory) : [];
};

test("a registered skill runs end to end and is reported honestly", async () => {
  const { config, world } = fixture();
  const { body, calls } = watched(world);

  const run = await runSkillValidation({
    config,
    embodiment: body,
    skillId: "wait_safely",
    parameters: { ticks: 40 },
  });

  assert.equal(run.code, 0, JSON.stringify(run.report.failure));
  assert.equal(run.report.requestedSkill, "wait_safely");
  assert.equal(run.report.actualSkill, "wait_safely");
  assert.equal(run.report.safety.decision, "ACCEPT");
  assert.equal(run.report.terminalStatus, "SUCCESS");
  assert.equal(run.report.result, "completed");
  assert.ok(run.report.elapsedTicks >= 40, "the wait must cost world time");
  assert.deepEqual(run.report.observedEffects, ["waited_safely"]);
  assert.deepEqual(run.report.expectedEffects, [
    { fact: "rested", op: "=", value: 1 },
  ]);
  // The measured skill is allowed to wait; it is not allowed to do anything
  // else, and the parameters it ran under are the library's, not the caller's.
  assert.ok(calls.includes("waitTicks"));
  for (const method of PHYSICAL.filter((name) => name !== "waitTicks"))
    assert.ok(!calls.includes(method), `wait_safely called ${method}`);
  assert.deepEqual(run.report.safety.executedParameters, { ticks: 40 });
});

test("an unknown skill is refused without touching the world", async () => {
  const { config, world } = fixture();
  const { body, calls } = watched(world);

  const run = await runSkillValidation({
    config,
    embodiment: body,
    skillId: "summon_dragon",
  });

  assert.equal(run.code, 1);
  assert.equal(run.report.result, "refused");
  assert.equal(run.report.failure?.reason, "unknown_skill");
  assert.equal(run.report.actualSkill, null);
  assert.deepEqual(calls, [], "an unknown skill must not cost a connection");
  assert.equal(reportsIn(config).length, 1, "the refusal is still recorded");
});

test("a parameter the skill does not accept is refused before connecting", async () => {
  const { config, world } = fixture();
  const { body, calls } = watched(world);

  const run = await runSkillValidation({
    config,
    embodiment: body,
    skillId: "wait_safely",
    parameters: { coordinates: "0,64,0" },
  });

  assert.equal(run.report.failure?.reason, "invalid_parameters");
  assert.match(run.report.failure?.detail ?? "", /coordinates/);
  assert.deepEqual(calls, []);

  const outOfRange = await runSkillValidation({
    config,
    embodiment: watched(world).body,
    skillId: "wait_safely",
    parameters: { ticks: 999999 },
  });
  assert.equal(outOfRange.report.failure?.reason, "invalid_parameters");
});

test("the safety kernel refuses a skill whose permission is switched off", async () => {
  const { config, world } = fixture({
    config: {
      permissions: {
        ...baseConfig().permissions,
        hunting: {
          passiveUnnamedAnimals: false,
          namedAnimals: false,
          tamedAnimals: false,
        },
      },
    } as Partial<PersonConfig>,
  });

  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "hunt_safe_passive_animals",
  });

  assert.equal(run.report.safety.decision, "REJECT");
  assert.ok(run.report.safety.reasonCodes.includes("permission_denied"));
  assert.ok(run.report.safety.reasonCodes.includes("hunt_passive_animal"));
  assert.equal(run.report.actualSkill, null, "nothing may have executed");
  assert.equal(run.report.terminalStatus, "INVALIDATED");
  assert.equal(run.report.result, "refused");
  assert.equal(run.report.failure?.reason, "safety_rejected");
});

test("a replaced skill is never reported as the skill that ran", async () => {
  // A hostile in contact range makes the kernel take control. The requested
  // skill is then preempted and the emergency skill runs in its place, which
  // is exactly the case a harness must not paper over.
  const { config, world } = fixture({
    entities: [{ name: "zombie", position: { x: 3, y: 64, z: 0 } }],
  });

  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "wait_safely",
    parameters: { ticks: 40 },
  });

  assert.equal(run.report.safety.decision, "REPLACE");
  assert.equal(run.report.requestedSkill, "wait_safely");
  assert.equal(run.report.actualSkill, "flee");
  assert.equal(run.report.requestedSkillStatus, "PREEMPTED");
  assert.ok(run.report.safety.emergency);
  assert.equal(run.report.safety.emergency?.trigger, "immediate_threat");
  assert.equal(run.report.failure?.reason, "skill_replaced");
  assert.notEqual(run.report.result, "completed");
  // The effects credited are the ones the executed skill promised.
  assert.ok(
    run.report.expectedEffects.every((effect) => effect.fact !== "rested"),
    "the preempted skill's contract must not be credited to the emergency one",
  );
});

test("both observations are captured and both validate against the schema", async () => {
  const { config, world } = fixture();
  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "wait_safely",
    parameters: { ticks: 40 },
  });

  assert.ok(run.report.preObservation, "a pre-skill observation is required");
  assert.ok(run.report.postObservation, "a post-skill observation is required");
  assert.equal(run.report.preObservationValid, true);
  assert.equal(run.report.postObservationValid, true);

  const validator = protocolValidator();
  assert.equal(validator.validate(run.report.preObservation).valid, true);
  assert.equal(validator.validate(run.report.postObservation).valid, true);
  assert.ok(
    (run.report.postObservation?.tick ?? 0) >
      (run.report.preObservation?.tick ?? 0),
    "the post observation must be taken after the skill, not before it",
  );
  // The post observation carries what just happened, the way a live run's next
  // observation does.
  assert.equal(
    run.report.postObservation?.previousOutcome?.executedSkill,
    "wait_safely",
  );
});

test("a validation run leaves the learner exactly as it found it", async () => {
  const evidenceDirectory = temporaryDirectory("person-evidence-");
  const { config, world } = fixture({ evidenceDirectory });

  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "wait_safely",
    parameters: { ticks: 40 },
  });

  assert.equal(run.report.learning.mode, "off");
  assert.equal(run.report.learning.changed, false);
  assert.equal(run.report.learning.policyRevisionBefore, 0);
  assert.equal(run.report.learning.policyRevisionAfter, 0);
  assert.equal(
    run.report.learning.evidenceBefore?.digest,
    run.report.learning.evidenceAfter?.digest,
  );
  assert.equal(
    existsSync(path.join(evidenceDirectory, "journal")),
    false,
    "a validation run is not an experience",
  );
  assert.equal(existsSync(path.join(evidenceDirectory, "snapshots")), false);
  assert.equal(
    existsSync(path.join(config.runtime.outputDirectory, "reports")),
    false,
    "and it is not an episode either",
  );
});

test("the report is written where validation reports belong, and is complete", async () => {
  const { config, world } = fixture();
  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "wait_safely",
    parameters: { ticks: 40 },
  });

  assert.ok(run.reportPath, "a report path is required");
  assert.match(
    run.reportPath ?? "",
    /validation[/\\]skill-tests[/\\].*wait_safely.*\.json$/,
  );
  const stored = JSON.parse(
    readFileSync(run.reportPath as string, "utf8"),
  ) as SkillValidationReport;

  assert.equal(stored.schemaVersion, 1);
  for (const field of [
    "testId",
    "startedAt",
    "finishedAt",
    "personId",
    "worldId",
    "sessionId",
    "trainingContext",
    "protocolVersion",
    "skillLibraryRevision",
    "requestedSkill",
    "requestedParameters",
    "invocation",
    "safety",
    "actualSkill",
    "operatorSetup",
    "operatorIntervention",
    "timeline",
    "preObservation",
    "postObservation",
    "outcome",
    "terminalStatus",
    "elapsedTicks",
    "completionEvidence",
    "expectedEffects",
    "observedEffects",
    "effectComparison",
    "navigation",
    "learning",
    "disconnect",
    "result",
  ])
    assert.ok(field in stored, `the report must record ${field}`);

  assert.equal(stored.invocation?.skillId, "wait_safely");
  assert.equal(stored.invocation?.type, "SkillInvocation");
  assert.equal(
    protocolValidator().validate(stored.invocation).valid,
    true,
    "the proposal in the report is a real protocol message",
  );
  assert.equal(stored.minecraftVersion, null, "the fixture is not Minecraft");
  assert.ok(stored.completionEvidence?.kinds.includes("elapsed_ticks"));
  assert.equal(stored.disconnect.status, "clean");
});

test("the status file says a validation run is happening, and which phase", async () => {
  const { config, world } = fixture();
  const seen: string[] = [];
  const file = statusPath(
    config.runtime.outputDirectory,
    config.worldId,
    config.personId,
  );
  const body = new Proxy(world, {
    get(target, property) {
      if (property === "waitTicks")
        return async (ticks: number) => {
          seen.push(readStatus(file)?.phase ?? "none");
          return (
            target as unknown as { waitTicks(t: number): Promise<void> }
          ).waitTicks(ticks);
        };
      const value = Reflect.get(target, property, target);
      return typeof value === "function"
        ? (...args: unknown[]) =>
            (value as (...rest: unknown[]) => unknown).apply(target, args)
        : value;
    },
  }) as unknown as Embodiment;

  await runSkillValidation({
    config,
    embodiment: body,
    skillId: "wait_safely",
    parameters: { ticks: 40 },
  });

  assert.ok(
    seen.includes("executing"),
    `status must report the executing phase, saw ${seen.join(", ")}`,
  );
  const final = readStatus(file);
  assert.ok(final);
  assert.equal(final.command, "skill-test");
  assert.equal(final.phase, "stopped");
  assert.equal(final.connection, "disconnected");
  assert.equal(final.learningMode, "off");
  assert.equal(final.lastValidation?.requestedSkill, "wait_safely");
  assert.equal(final.lastValidation?.executedSkill, "wait_safely");
  // An operator watching from another terminal needs the live facts too, not
  // just the phase name.
  assert.deepEqual(final.position, { x: 0, y: 64, z: 0 });
  assert.equal(final.dimension, "overworld");
  assert.equal(final.health, 20);
  assert.equal(final.home?.distance, 0);
  assert.equal(final.tick, 40);
});

test("operator setup keeps Person inert until it is explicitly confirmed", async () => {
  const { config, world } = fixture({ spawn: { x: 10, y: 64, z: 0 } });
  const { body, calls } = watched(world);
  let callsAtConfirmation: string[] = [];
  let info: OperatorSetupInfo | null = null;

  const run = await runSkillValidation({
    config,
    embodiment: body,
    skillId: "wait_safely",
    parameters: { ticks: 40 },
    operatorSetup: true,
    confirmSetup: async (given) => {
      info = given;
      callsAtConfirmation = [...calls];
    },
  });

  assert.equal(run.report.operatorSetup, true);
  assert.ok(run.report.timeline.setupStartedAt);
  assert.ok(run.report.timeline.setupCompletedAt);
  assert.ok(
    (run.report.timeline.skillStartedAt ?? "") >=
      (run.report.timeline.setupCompletedAt ?? ""),
    "the measured run starts after setup, never during it",
  );
  assert.ok(info, "the operator is told where Person is standing");
  assert.equal((info as unknown as OperatorSetupInfo).skillId, "wait_safely");
  assert.equal((info as unknown as OperatorSetupInfo).homeDistance, 10);
  for (const method of PHYSICAL)
    assert.ok(
      !callsAtConfirmation.includes(method),
      `Person acted (${method}) while waiting for operator setup`,
    );
});

test("a setup the operator does not confirm never runs the skill", async () => {
  const { config, world } = fixture();
  const { body, calls } = watched(world);

  const run = await runSkillValidation({
    config,
    embodiment: body,
    skillId: "wait_safely",
    operatorSetup: true,
    confirmSetup: async () => {
      throw new Error("operator walked away");
    },
  });

  assert.equal(run.code, 1);
  assert.equal(run.report.result, "failed");
  assert.equal(run.report.actualSkill, null);
  assert.equal(run.report.safety.decision, null, "validation never happened");
  assert.equal(run.report.timeline.skillStartedAt, null);
  assert.ok(!calls.includes("waitTicks"));
  assert.ok(calls.includes("disconnect"), "the body is released anyway");
});

test("operator setup requested with no way to confirm it refuses to guess", async () => {
  const { config, world } = fixture();
  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "wait_safely",
    operatorSetup: true,
  });
  assert.equal(run.report.failure?.reason, "operator_setup_unavailable");
  assert.equal(run.report.timeline.skillStartedAt, null);
});

test("a setup that leaves Person invalid prevents the measured run", async () => {
  const { config, world } = fixture();
  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "wait_safely",
    operatorSetup: true,
    confirmSetup: async () => {
      // Exactly the case the operator phase exists for: something happened to
      // Person while a human was handling it, and the test can no longer be
      // about what it was supposed to be about.
      world.dropConnection();
    },
  });

  assert.equal(run.report.failure?.reason, "disconnected_before_skill");
  assert.equal(run.report.timeline.skillStartedAt, null);
  assert.equal(run.report.actualSkill, null);
  assert.equal(run.report.result, "refused");
});

test("a body that dies during setup refuses the measured run", async () => {
  const { config, world } = fixture();
  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "wait_safely",
    operatorSetup: true,
    confirmSetup: async () => {
      world.setVitals({ health: 0 });
    },
  });
  assert.equal(run.report.failure?.reason, "person_died_before_skill");
  assert.equal(run.report.timeline.skillStartedAt, null);
});

test("return_home travels to the configured home and says how far it got", async () => {
  const { config, world } = fixture({ spawn: { x: 10, y: 64, z: 0 } });
  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "return_home",
  });

  assert.equal(run.report.safety.decision, "ACCEPT");
  assert.equal(run.report.actualSkill, "return_home");
  assert.equal(run.report.terminalStatus, "SUCCESS");
  assert.equal(run.report.navigation.homeDistanceBefore, 10);
  assert.ok(
    (run.report.navigation.homeDistanceAfter ?? 99) <= 2.5,
    "the spec's own completion criterion is what decides this",
  );
  assert.deepEqual(run.report.navigation.homePosition, config.world.home);
  assert.deepEqual(run.report.navigation.startPosition, {
    x: 10,
    y: 64,
    z: 0,
  });
  assert.ok(
    run.report.navigation.endPosition,
    "the report must say where Person ended up",
  );
  assert.ok(run.report.navigation.routeStatusAfter);
  assert.ok(run.report.completionEvidence?.kinds.includes("position_reached"));
  assert.deepEqual(run.report.observedEffects, ["arrived_home"]);
  // Home came from configuration, never from the caller: the CLI has no way to
  // say where home is, and neither does cognition.
  assert.ok(
    !JSON.stringify(run.report.invocation?.parameters).includes("64"),
    "no coordinate may travel in the invocation",
  );
});

test("home is never a parameter of any registered skill", () => {
  // The harness can only send parameters a SkillSpec declares, so this is what
  // actually stops a coordinate from reaching the executor through --skill.
  const registry = skillRegistry();
  const SCALARS = ["integer", "number", "string", "boolean"];
  for (const id of registry.ids)
    for (const [name, parameter] of Object.entries(
      registry.get(id).parameters,
    )) {
      assert.ok(
        !/^(x|y|z|position|coordinate|home|destination|block|entity)/i.test(
          name,
        ),
        `${id} exposes ${name}, which looks like a coordinate channel`,
      );
      assert.ok(
        SCALARS.includes(parameter.type),
        `${id}.${name} is not a scalar`,
      );
    }
});

test("a disconnect during the skill is reported, not hidden", async () => {
  const { config, world } = fixture();
  const body = new Proxy(world, {
    get(target, property) {
      if (property === "waitTicks")
        return async (ticks: number) => {
          await (
            target as unknown as { waitTicks(t: number): Promise<void> }
          ).waitTicks(ticks);
          target.dropConnection();
        };
      const value = Reflect.get(target, property, target);
      return typeof value === "function"
        ? (...args: unknown[]) =>
            (value as (...rest: unknown[]) => unknown).apply(target, args)
        : value;
    },
  }) as unknown as Embodiment;

  const run = await runSkillValidation({
    config,
    embodiment: body,
    skillId: "wait_safely",
    parameters: { ticks: 60 },
  });

  assert.equal(run.report.terminalStatus, "DISCONNECTED");
  assert.equal(run.report.postObservation, null);
  assert.equal(run.report.postObservationReason, "disconnected");
  assert.equal(run.report.disconnect.status, "clean");
  assert.ok(run.reportPath, "the report still lands");
  // An effect nobody could observe is not a failed prediction.
  for (const fact of run.report.effectComparison?.facts ?? [])
    assert.ok(["inconclusive", "not_observable"].includes(fact.verdict));
});

test("a body that will not let go cannot hold the command open", async () => {
  const { config, world } = fixture();
  const body = new Proxy(world, {
    get(target, property) {
      if (property === "disconnect") return () => new Promise<void>(() => {});
      const value = Reflect.get(target, property, target);
      return typeof value === "function"
        ? (...args: unknown[]) =>
            (value as (...rest: unknown[]) => unknown).apply(target, args)
        : value;
    },
  }) as unknown as Embodiment;

  const started = Date.now();
  const run = await runSkillValidation({
    config,
    embodiment: body,
    skillId: "wait_safely",
    parameters: { ticks: 40 },
    disconnectTimeoutMs: 200,
  });

  assert.ok(
    Date.now() - started < 5000,
    "the disconnect timeout must bound it",
  );
  assert.equal(run.report.disconnect.status, "timed_out");
  assert.ok(run.reportPath);
});

test("a report that cannot be written is reported as such", async () => {
  const { config, world } = fixture({
    outputDirectory: path.join(REPOSITORY, "package.json"),
  });
  const run = await runSkillValidation({
    config,
    embodiment: world,
    skillId: "wait_safely",
    parameters: { ticks: 40 },
  });
  assert.equal(run.reportPath, null);
  assert.equal(run.report.failure?.reason, "report_write_failed");
  assert.equal(run.code, 1);
});
