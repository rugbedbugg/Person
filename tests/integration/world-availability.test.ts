/**
 * Losing the world while Person lives (ADR 0017, I2), through the real runtime
 * and real cognition, with synthetic identities.
 *
 * "In Minecraft" is an operational state, not a verdict on the run: losing the
 * world ends an episode as interrupted, never failed, and reaching it again
 * continues the same Person in the same session.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { FixtureWorld } from "#fixture-world";
import { REPOSITORY, temporaryDirectory } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

const COGNITION = ["uv", "run", "person-cognition"];

/** A world that loses its connection once, when its clock first passes `at`. */
class FlakyWorld extends FixtureWorld {
  #dropped = false;
  readonly at: number;
  constructor(
    definition: ConstructorParameters<typeof FixtureWorld>[0],
    at: number,
  ) {
    super(definition);
    this.at = at;
  }
  override snapshot() {
    const now = super.snapshot();
    if (!this.#dropped && now.connected && now.tick >= this.at) {
      this.#dropped = true;
      this.dropConnection();
      return super.snapshot();
    }
    return now;
  }
}

const definition = JSON.parse(
  readFileSync(
    path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
    "utf8",
  ),
);

function journal(
  evidence: string,
): { type: string; payload: Record<string, unknown> }[] {
  const directory = path.join(evidence, "journal");
  return readdirSync(directory)
    .filter((name) => name.endsWith(".jsonl"))
    .sort()
    .flatMap((name) =>
      readFileSync(path.join(directory, name), "utf8").split("\n"),
    )
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

test(
  "losing the world with no reconnection budget interrupts the episode, it does not fail it",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-world-");
    const { report } = await runEpisode({
      worldObject: new FlakyWorld(definition, 1),
      cognitionCommand: COGNITION,
      evidenceDirectory,
      personId: "test-person-000",
      maxDecisions: 30,
    });
    assert.equal(report.outcome, "interrupted");
    assert.equal(report.reason, "world_unavailable");
    const events = journal(evidenceDirectory);
    const world = events
      .filter((e) => e.type === "world_availability_changed")
      .map((e) => e.payload["state"]);
    assert.deepEqual(world, ["available", "unavailable"]);
    const ended = events.filter((e) => e.type === "session_ended");
    assert.equal(ended.length, 1, "a clean end, not a crash");
    assert.ok(
      (ended[0]!.payload["reasons"] as string[]).includes("world_unavailable"),
    );
  },
);

test(
  "reaching the world again continues the same Person in the same session",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-world-");
    const { report } = await runEpisode({
      worldObject: new FlakyWorld(definition, 1),
      cognitionCommand: COGNITION,
      evidenceDirectory,
      personId: "test-person-000",
      maxDecisions: 12,
      reconnectAttempts: 2,
    });
    assert.notEqual(report.outcome, "failed");
    assert.notEqual(report.reason, "world_unavailable");
    assert.equal(report.decisions.length, 12, "the episode ran on");
    const events = journal(evidenceDirectory);
    const world = events
      .filter((e) => e.type === "world_availability_changed")
      .map((e) => e.payload["state"]);
    assert.deepEqual(world, ["available", "unavailable", "available"]);
    const count = (type: string) =>
      events.filter((e) => e.type === type).length;
    assert.equal(count("person_founded"), 1, "reconnection is not rebirth");
    assert.equal(count("session_started"), 1, "nor a new session");
  },
);
