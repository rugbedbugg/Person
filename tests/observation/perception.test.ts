import test from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { protocolValidator, type Observation } from "#protocol";
import { PERCEPTION, buildObservation } from "#node-runtime";
import { harness, type Harness } from "../support/harness.ts";

/**
 * What cognition is told about the world, as opposed to what the runtime knows.
 *
 * The first live observation carried eighty passive animals, seventy of them
 * outside the region Person is allowed to walk into, most of them beyond a
 * hundred blocks. None of it was actionable and all of it was noise. Shaping
 * that list is a perception decision, so it happens here, in the one place
 * that also knows what Person is permitted to do, and it is deliberately not a
 * safety mechanism: the snapshot the kernel and the guard read is untouched.
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
    memory: bench.memory,
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

test("animals outside the region Person may enter are not reported", async () => {
  const bench = await harness();
  const near = bench.world.spawn("cow", { x: 6, y: 64, z: 0 });
  // Well outside the exploration box, exactly like the herds the first real
  // observation was full of.
  const far = bench.world.spawn("pig", { x: 200, y: 64, z: 200 });
  const observation = observe(bench);

  const reported = observation.nearby.passiveAnimals.map(
    (animal) => animal.entityId,
  );
  assert.ok(reported.includes(near.entityId), "the usable animal is reported");
  assert.ok(!reported.includes(far.entityId), "the unreachable herd is not");

  // The runtime still knows it exists, and still refuses it for the right
  // reason rather than because perception hid it.
  const snapshot = bench.world.snapshot();
  const view = snapshot.entities.find(
    (entity) => entity.entityId === far.entityId,
  );
  assert.ok(view, "the snapshot keeps every entity the body can see");
  const verdict = bench.permissions.mayHunt(view);
  assert.equal(verdict.allowed, false);
  assert.equal(verdict.reason, "protected_area");
});

test("an animal inside a protected area is not quietly made huntable", async () => {
  const bench = await harness();
  const inside = bench.world.spawn("cow", { x: 24, y: 64, z: 24 });
  const observation = observe(bench);
  assert.ok(
    !observation.nearby.passiveAnimals.some(
      (animal) => animal.entityId === inside.entityId,
    ),
    "a protected area is not part of the region Person may use",
  );
  assert.equal(
    bench.permissions.mayHunt(
      bench.world
        .snapshot()
        .entities.find((entity) => entity.entityId === inside.entityId)!,
    ).allowed,
    false,
  );
});

test("protections on the animals that remain visible are unchanged", async () => {
  const bench = await harness();
  bench.world.spawn("cow", { x: 4, y: 64, z: 0 });
  bench.world.spawn("cow", { x: 5, y: 64, z: 0 }, { named: true });
  bench.world.spawn("wolf", { x: 6, y: 64, z: 0 }, { tamed: true });
  const animals = observe(bench).nearby.passiveAnimals;
  const plain = animals.find((animal) => !animal.named && !animal.tamed);
  const named = animals.find((animal) => animal.named);
  assert.ok(plain && named);
  assert.equal(plain.protectedTarget, false);
  assert.equal(named.protectedTarget, true, "a named animal stays protected");
});

test("the animal list stays bounded and nearest-first", async () => {
  const bench = await harness();
  for (let index = 0; index < 40; index++)
    bench.world.spawn("cow", { x: 40 - index, y: 64, z: 0 });
  const first = observe(bench).nearby.passiveAnimals;
  const second = observe(bench).nearby.passiveAnimals;

  assert.equal(first.length, PERCEPTION.entities.passiveTotal);
  assert.deepEqual(
    first.map((animal) => animal.entityId),
    second.map((animal) => animal.entityId),
    "the same world must produce the same list",
  );
  for (let index = 1; index < first.length; index++)
    assert.ok(
      first[index - 1]!.distance <= first[index]!.distance,
      "the nearest usable animals are the ones kept",
    );
  assert.equal(first[0]!.distance, 1, "and the nearest one is first");
});

test("hostiles are bounded but never region-filtered", async () => {
  const bench = await harness();
  // A skeleton outside the exploration box can still shoot across the fence.
  const outside = bench.world.spawn("skeleton", { x: 60, y: 64, z: 0 });
  for (let index = 0; index < 40; index++)
    bench.world.spawn("zombie", { x: 2 + index, y: 64, z: 4 });
  const hostiles = observe(bench).nearby.hostiles;
  assert.ok(
    hostiles.length <= PERCEPTION.entities.hostileTotal,
    "the hostile list is bounded",
  );
  const all = bench.world
    .snapshot()
    .entities.filter((entity) => entity.hostile);
  assert.ok(
    all.some((entity) => entity.entityId === outside.entityId),
    "and nothing hostile is dropped from what the safety kernel reads",
  );
});

test("two players survive into the observation as two people", async () => {
  const bench = await harness();
  bench.world.spawn(
    "player",
    { x: 4, y: 64, z: 0 },
    { username: "rugbedbugg", uuid: "8a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d" },
  );
  bench.world.spawn(
    "player",
    { x: 8, y: 64, z: 0 },
    { username: "PersonWatcher", uuid: "1f2e3d4c-5b6a-4978-8765-4321fedcba09" },
  );
  const observation = observe(bench);
  const players = observation.nearby.players;
  assert.equal(players.length, 2);
  assert.deepEqual(
    players.map((player) => player.username),
    ["rugbedbugg", "PersonWatcher"],
  );
  assert.equal(
    new Set(players.map((player) => player.uuid)).size,
    2,
    "two distinct people must not collapse into one identity",
  );
  for (const player of players)
    assert.equal(player.protectedTarget, true, "players are never targets");

  const result = protocolValidator().validate(observation);
  assert.ok(result.valid, result.diagnostics.join("; "));
});

test("an observation without identities is still a valid observation", async () => {
  const bench = await harness();
  bench.world.spawn("cow", { x: 3, y: 64, z: 0 });
  const observation = observe(bench);
  const [cow] = observation.nearby.passiveAnimals;
  assert.ok(cow);
  assert.ok(
    !("username" in cow) && !("uuid" in cow),
    "identity fields are added only when the body has them",
  );
  const result = protocolValidator().validate(observation);
  assert.ok(result.valid, result.diagnostics.join("; "));
});
