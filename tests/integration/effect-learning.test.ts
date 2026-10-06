import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import type { FixtureWorldDefinition } from "#fixture-world";
import { baseConfig } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

/**
 * Learned effect reliability, end to end (ADR 0011): the real runtime, the
 * real cognition process in supervised learning, a fixture body.
 *
 * What Person learns about its skills comes from what it felt happen, so
 * hidden world state that changes nothing Person experiences changes nothing
 * it learns, and a world shifted along Minecraft's grid teaches the same.
 *
 * TESTED IN FIXTURE. None of this is live Minecraft evidence.
 */

const COGNITION = ["uv", "run", "person-cognition"];
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g;

interface JournalEvent {
  type: string;
  payload: Record<string, unknown>;
}

function learned(evidenceDirectory: string): string[] {
  const journal = path.join(evidenceDirectory, "journal");
  return readdirSync(journal)
    .filter((name) => name.endsWith(".jsonl"))
    .sort()
    .flatMap((name) =>
      readFileSync(path.join(journal, name), "utf8").split("\n"),
    )
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as JournalEvent)
    .filter((event) => event.type === "effect_evidence")
    .map((event) => JSON.stringify(event.payload).replace(UUID, "<id>"));
}

async function life(dx: number, hiddenLava: boolean): Promise<string[]> {
  const at = (x: number, y: number, z: number) => ({ x: x + dx, y, z });
  const blocks: FixtureWorldDefinition["blocks"] = [
    // A tree Person faces, so it cuts wood and feels its inventory change.
    ...[64, 65, 66].map((y) => ({ position: at(0, y, -6), name: "oak_log" })),
  ];
  if (hiddenLava) {
    // Behind Person and behind a wall: physically there, never perceived,
    // and too far for the kernel to act on.
    for (let x = -3; x <= 3; x++)
      for (let y = 64; y <= 67; y++)
        blocks.push({ position: at(x, y, 3), name: "dirt" });
    blocks.push({ position: at(0, 64, 6), name: "lava" });
  }
  const config = baseConfig();
  type Box = (typeof config.world.resourceAreas)[number];
  const shifted = (box: Box): Box => ({
    min: at(box.min.x, box.min.y, box.min.z),
    max: at(box.max.x, box.max.y, box.max.z),
  });
  const { evidenceDirectory } = await runEpisode({
    home: at(0, 64, 0),
    world: {
      name: "effect-learning",
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
    learningMode: "supervised",
    cognitionCommand: COGNITION,
    maxDecisions: 6,
  });
  return learned(evidenceDirectory);
}

test(
  "Person learns from what it felt, not from where the world is or what is hidden",
  { timeout: 300000 },
  async () => {
    const plain = await life(0, false);
    assert.ok(
      plain.some(
        (record) =>
          record.includes('"gather_wood"') &&
          record.includes('"admitted_to":"active"'),
      ),
      plain.join("\n"),
    );
    assert.deepEqual(await life(0, true), plain, "hidden lava teaches nothing");
    assert.deepEqual(
      await life(1000, false),
      plain,
      "+1000 X teaches the same",
    );
  },
);
