import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import type { FixtureWorldDefinition } from "#fixture-world";
import { baseConfig } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

/**
 * Affect, end to end (ADR 0010): the real runtime, the real cognition
 * process, a fixture body.
 *
 * Affect is appraised from what Person perceives and feels, so a threat it
 * cannot perceive is no threat to it, and a world shifted along Minecraft's
 * grid is the same world to it. Lava three blocks ahead is close enough to be
 * unsettling and too far for the kernel to act on, so the runtime behaves the
 * same in every variant and only what Person perceives differs.
 *
 * TESTED IN FIXTURE. None of this is live Minecraft evidence.
 */

const COGNITION = ["uv", "run", "person-cognition"];
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g;

interface JournalEvent {
  type: string;
  payload: Record<string, unknown>;
}

function affect(evidenceDirectory: string): string[] {
  const journal = path.join(evidenceDirectory, "journal");
  return readdirSync(journal)
    .filter((name) => name.endsWith(".jsonl"))
    .sort()
    .flatMap((name) =>
      readFileSync(path.join(journal, name), "utf8").split("\n"),
    )
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as JournalEvent)
    .filter((event) => event.type === "affect_appraised")
    .map((event) => JSON.stringify(event.payload).replace(UUID, "<id>"));
}

async function life(
  dx: number,
  { lava, wall }: { lava: boolean; wall: boolean },
): Promise<string[]> {
  const at = (x: number, y: number, z: number) => ({ x: x + dx, y, z });
  const blocks: FixtureWorldDefinition["blocks"] = [];
  if (lava) blocks.push({ position: at(0, 64, -3), name: "lava" });
  if (wall)
    for (let x = -3; x <= 3; x++)
      for (let y = 64; y <= 67; y++)
        blocks.push({ position: at(x, y, -2), name: "dirt" });
  const config = baseConfig();
  type Box = (typeof config.world.resourceAreas)[number];
  const shifted = (box: Box): Box => ({
    min: at(box.min.x, box.min.y, box.min.z),
    max: at(box.max.x, box.max.y, box.max.z),
  });
  const { evidenceDirectory } = await runEpisode({
    home: at(0, 64, 0),
    world: {
      name: "affect",
      spawn: at(0, 64, 0),
      spawnYaw: 0,
      vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
      blocks,
    },
    config: {
      world: {
        home: at(0, 64, 0),
        exploration: shifted(config.world.exploration),
        resourceAreas: config.world.resourceAreas.map(shifted),
        protectedAreas: config.world.protectedAreas.map(shifted),
      },
    },
    cognitionCommand: COGNITION,
    maxDecisions: 4,
  });
  return affect(evidenceDirectory);
}

test(
  "a threat behind a wall moves nothing; the same threat in view does",
  { timeout: 300000 },
  async () => {
    const seen = await life(0, { lava: true, wall: false });
    const hidden = await life(0, { lava: true, wall: true });
    const absent = await life(0, { lava: false, wall: true });

    assert.ok(
      seen.some((record) => record.includes('"perceived_threat"')),
      "lava in view is unsettling",
    );
    assert.deepEqual(hidden, absent, "unperceived lava is no lava to Person");
    assert.ok(!hidden.some((record) => record.includes('"perceived_threat"')));
  },
);

test(
  "the same experience a thousand blocks away is the same affect",
  { timeout: 300000 },
  async () => {
    const here = await life(0, { lava: true, wall: false });
    const there = await life(1000, { lava: true, wall: false });
    assert.ok(here.length > 0);
    assert.deepEqual(there, here);
  },
);
