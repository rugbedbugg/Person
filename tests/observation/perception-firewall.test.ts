import test from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { protocolValidator, type Observation } from "#protocol";
import { buildObservation } from "#node-runtime";
import { harness, type Harness } from "../support/harness.ts";

/**
 * The perception firewall, proved by absence.
 *
 * These tests exist to show that things the runtime knows do not reach
 * cognition. That is a harder property to hold than "the visible thing
 * appeared", and it is the one deviation C1 was about: the runtime holds a
 * complete privileged snapshot, and cognition must not receive it merely
 * because the body has it.
 *
 * ADR 0002 rule 2 applies throughout: none of this is a safety boundary. The
 * safety kernel, the permission gate and the physical guard all keep reading
 * the unshaped snapshot, so nothing here can change what Person may do.
 */

function observe(bench: Harness): Observation {
  return buildObservation({
    identity: {
      personId: bench.config.personId,
      sessionId: randomUUID(),
      worldId: bench.config.worldId,
    },
    snapshot: bench.world.snapshot(),
    permissions: bench.permissions,
    kernel: bench.kernel,
    ledger: bench.ledger,
    trainingContext: "fixture",
    cognition: {
      activeGoal: null,
      activeRoutine: null,
      activeSkill: null,
      suspendedGoals: [],
    },
    previousOutcome: null,
    blockAt: (position) => bench.world.blockAt(position),
  });
}

/** Every path in the message whose key looks like a world coordinate. */
function coordinatePaths(value: unknown, path = "$"): string[] {
  if (Array.isArray(value))
    return value.flatMap((item, index) =>
      coordinatePaths(item, `${path}[${index}]`),
    );
  if (value === null || typeof value !== "object") return [];
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record);
  const found: string[] = [];
  // A bare {x, y, z} is a world position whatever the field is called.
  if (
    keys.length === 3 &&
    ["x", "y", "z"].every((axis) => typeof record[axis] === "number")
  )
    found.push(path);
  for (const [key, child] of Object.entries(record)) {
    if (/position|coordinate|coords/i.test(key)) found.push(`${path}.${key}`);
    found.push(...coordinatePaths(child, `${path}.${key}`));
  }
  return found;
}

test("the privileged snapshot knows exactly where Person is", async () => {
  const bench = await harness();
  const snapshot = bench.world.snapshot();
  // The runtime half of the firewall. If this ever stops being true the motor
  // system and the safety kernel have lost the truth they run on.
  assert.equal(typeof snapshot.position.x, "number");
  assert.equal(typeof snapshot.position.y, "number");
  assert.equal(typeof snapshot.position.z, "number");
});

test("no world coordinate reaches cognition anywhere in the observation", async () => {
  const bench = await harness();
  bench.world.spawn("cow", { x: 4, y: 64, z: 0 });
  bench.world.spawn("zombie", { x: 5, y: 64, z: 0 });
  const observation = observe(bench);

  assert.deepEqual(
    coordinatePaths(observation),
    [],
    "cognition must not receive a world coordinate under any key",
  );
});

test("the observation still validates against the protocol schema", async () => {
  const bench = await harness();
  const observation = observe(bench);
  const verdict = protocolValidator().validate(observation);
  assert.equal(
    verdict.valid,
    true,
    `observation must stay valid: ${verdict.diagnostics.join("; ")}`,
  );
});

test("the schema refuses an observation with a position injected", async () => {
  const bench = await harness();
  const observation = observe(bench) as unknown as Record<string, unknown>;
  const environment = { ...(observation["environment"] as object) } as Record<
    string,
    unknown
  >;
  environment["position"] = { x: 1, y: 64, z: 2 };
  const tampered = { ...observation, environment };

  const verdict = protocolValidator().validate(tampered);
  assert.equal(
    verdict.valid,
    false,
    "a privileged coordinate must not be smuggled back in through the schema",
  );
});

test("the observation carries no internal entity handle", async () => {
  const bench = await harness();
  bench.world.spawn("cow", { x: 4, y: 64, z: 0 });
  const observation = observe(bench);
  const serialized = JSON.stringify(observation);

  assert.ok(
    !/"entityId"/.test(serialized),
    "a session-local Mineflayer entity id is a privileged handle",
  );
});

test("the eye pose the perception layer runs on is not reported", async () => {
  const bench = await harness();
  const observation = observe(bench);
  const serialized = JSON.stringify(observation);

  // Where Person is looking is what decides what it can see. Reporting it
  // would hand cognition the camera as well as the picture.
  for (const field of ["yaw", "pitch", "lookDirection", "eye"])
    assert.ok(
      !new RegExp(`"${field}"`).test(serialized),
      `${field} is privileged motor state`,
    );
});

test("a privileged field cannot be smuggled into the cognition contract", async () => {
  const bench = await harness();
  const observation = observe(bench) as unknown as Record<string, unknown>;

  for (const [field, value] of [
    ["chunkCache", { loaded: 42 }],
    ["pathfinderNodes", [{ x: 1, y: 64, z: 1 }]],
    ["snapshot", { position: { x: 0, y: 64, z: 0 } }],
  ] as const) {
    const verdict = protocolValidator().validate({
      ...observation,
      [field]: value,
    });
    assert.equal(
      verdict.valid,
      false,
      `${field} must be refused by the cognition-facing schema`,
    );
  }
});

test("what the runtime knows is strictly larger than what it reports", async () => {
  const bench = await harness();
  bench.world.spawn("cow", { x: 0, y: 64, z: -5 });
  bench.world.spawn("cow", { x: 0, y: 64, z: 5 });
  bench.world.face({ x: 0, y: 64, z: -5 });

  const snapshot = bench.world.snapshot();
  const observation = observe(bench);
  const known = snapshot.entities.filter((entity) => entity.name === "cow");
  const reported = observation.nearby.passiveAnimals.filter(
    (animal) => animal.name === "cow",
  );

  assert.equal(known.length, 2, "the body knows about both");
  assert.equal(reported.length, 1, "Person is only looking at one of them");
});

test("what the ledger supplies is labelled as the ledger, never as recollection", async () => {
  const bench = await harness();
  bench.ledger.craftingTablePosition = { x: 0, y: 64, z: 6 };
  bench.ledger.furnacePosition = { x: 2, y: 64, z: 6 };
  const workstations = observe(bench).nearby.workstations;

  assert.equal(workstations.length, 2, "both are reported, seen or not");
  for (const workstation of workstations)
    assert.equal(workstation.source, "placement_ledger");
  assert.ok(
    !JSON.stringify(observe(bench)).includes("remembered"),
    "nothing the runtime supplies may claim to be remembered",
  );
});
