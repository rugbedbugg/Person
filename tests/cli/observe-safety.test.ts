import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { loadConfig, withConnectionOverride } from "#config";
import { FixtureWorld } from "#fixture-world";
import { readStatus, statusPath, type Embodiment } from "#node-runtime";
import { captureObservation } from "../../apps/cli/src/observe.ts";
import { REPOSITORY } from "../support/harness.ts";

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
  "registerOwnedStorage",
] as const;

/**
 * Wraps a body, recording every call and optionally replacing some.
 *
 * Methods are bound to the real world rather than to the wrapper: the fixture
 * uses private fields, which a naive proxy breaks in a way that looks like a
 * product failure and is not.
 */
function watched(
  world: FixtureWorld,
  replacements: Partial<Record<string, (...args: unknown[]) => unknown>> = {},
): { body: Embodiment; calls: string[] } {
  const calls: string[] = [];
  const body = new Proxy(world, {
    get(target, property) {
      if (typeof property !== "string")
        return Reflect.get(target, property, target);
      const replacement = replacements[property];
      if (replacement)
        return (...args: unknown[]) => {
          calls.push(property);
          return replacement(...args);
        };
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

function fixtureConfig(
  overrides: { outputDirectory?: string; evidenceDirectory?: string } = {},
) {
  const loaded = loadConfig(path.join(REPOSITORY, "examples/fixture.toml"));
  return {
    ...loaded,
    runtime: {
      ...loaded.runtime,
      outputDirectory:
        overrides.outputDirectory ??
        mkdtempSync(path.join(tmpdir(), "person-obs-")),
    },
    learning: {
      ...loaded.learning,
      evidenceDirectory:
        overrides.evidenceDirectory ??
        path.join(mkdtempSync(path.join(tmpdir(), "person-ev-")), "evidence"),
    },
  };
}

test("observe only looks: no skill, no movement, no block touched", async () => {
  const config = fixtureConfig();
  const world = FixtureWorld.fromFile(
    path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
  );
  const before = world.snapshot();
  const { body, calls } = watched(world);

  const captured = await captureObservation(config, REPOSITORY, {
    embodiment: body,
  });
  assert.equal(captured.valid, true, captured.diagnostics.join("; "));

  for (const method of PHYSICAL)
    assert.ok(
      !calls.includes(method),
      `observe called ${method}, which changes the world`,
    );
  assert.ok(calls.includes("connect"));
  assert.ok(calls.includes("snapshot"));
  assert.ok(calls.includes("disconnect"));

  const after = world.snapshot();
  assert.deepEqual(
    after.position,
    before.position,
    "Person must not have moved",
  );
  assert.deepEqual(
    after.inventory,
    before.inventory,
    "inventory must be untouched",
  );
  assert.equal(after.tick, before.tick, "no world time may be spent");
  assert.equal(after.health, before.health);
});

test("observe writes no learning evidence at all", async () => {
  const config = fixtureConfig();
  const world = FixtureWorld.fromFile(
    path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
  );
  await captureObservation(config, REPOSITORY, {
    embodiment: watched(world).body,
  });

  const evidence = config.learning.evidenceDirectory;
  const journal = path.join(evidence, "journal");
  const snapshots = path.join(evidence, "snapshots");
  assert.equal(
    existsSync(journal),
    false,
    "observing the world is not an experience",
  );
  assert.equal(
    existsSync(snapshots),
    false,
    "no policy snapshot may be written",
  );
  if (existsSync(evidence)) assert.deepEqual(readdirSync(evidence), []);
});

test("observe leaves no episode report and no policy change", async () => {
  const config = fixtureConfig();
  const world = FixtureWorld.fromFile(
    path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
  );
  await captureObservation(config, REPOSITORY, {
    embodiment: watched(world).body,
  });
  assert.equal(
    existsSync(path.join(config.runtime.outputDirectory, "reports")),
    false,
    "an observation is not an episode",
  );

  const status = readStatus(
    statusPath(config.runtime.outputDirectory, config.worldId, config.personId),
  );
  assert.ok(
    status,
    "status must be written so an operator can see what happened",
  );
  assert.equal(status.command, "observe");
  assert.equal(status.learningMode, "off");
  assert.equal(status.policyRevision, 0);
  assert.equal(status.decisions, 0);
  assert.equal(
    status.connection,
    "disconnected",
    "observe disconnects before returning",
  );
});

test("observe records an operator intervention when one is declared", async () => {
  const config = fixtureConfig();
  const world = FixtureWorld.fromFile(
    path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
  );
  await captureObservation(config, REPOSITORY, {
    embodiment: watched(world).body,
    operatorIntervention: { reason: "teleported the operator to Person" },
  });
  const status = readStatus(
    statusPath(config.runtime.outputDirectory, config.worldId, config.personId),
  );
  assert.ok(status);
  assert.equal(status.operatorIntervention.flagged, true);
  assert.equal(
    status.operatorIntervention.reason,
    "teleported the operator to Person",
  );
});

test("a failed capture still reports why through the status file", async () => {
  const config = fixtureConfig();
  const world = FixtureWorld.fromFile(
    path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
  );
  const { body: broken } = watched(world, {
    connect: async () => {
      throw Object.assign(
        new Error("Nothing is listening on 127.0.0.1:51234"),
        {
          reason: "connection_refused",
          hint: "Open the world to LAN and pass the port with --port.",
        },
      );
    },
  });

  await assert.rejects(() =>
    captureObservation(config, REPOSITORY, { embodiment: broken }),
  );
  const status = readStatus(
    statusPath(config.runtime.outputDirectory, config.worldId, config.personId),
  );
  assert.ok(status);
  assert.equal(status.connection, "failed");
  assert.equal(status.failureReason, "connection_refused");
  assert.match(status.failureHint ?? "", /--port/);
});

test("a hung disconnect cannot hold the command open", async () => {
  const config = fixtureConfig();
  const world = FixtureWorld.fromFile(
    path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
  );
  const { body: hangs } = watched(world, {
    disconnect: () => new Promise<void>(() => {}),
  });

  const started = Date.now();
  const captured = await captureObservation(config, REPOSITORY, {
    embodiment: hangs,
    disconnectTimeoutMs: 200,
  });
  assert.equal(captured.valid, true);
  assert.ok(
    Date.now() - started < 3000,
    "the disconnect timeout must bound the wait",
  );
});

test("the LAN port override never reaches the configuration file", () => {
  const file = path.join(REPOSITORY, "examples/minecraft-lan.toml");
  const original = loadConfig(file);
  const overridden = withConnectionOverride(original, { port: 51234 });

  assert.equal(overridden.server?.port, 51234);
  assert.equal(
    original.server?.port,
    33759,
    "the loaded config is not mutated",
  );
  assert.equal(
    loadConfig(file).server?.port,
    33759,
    "the file on disk is unchanged, so the next run reads the same thing",
  );
  assert.equal(overridden.server?.version, original.server?.version);
  assert.equal(overridden.worldId, original.worldId);
});
