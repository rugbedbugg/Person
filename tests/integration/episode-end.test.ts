import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { FixtureWorld } from "#fixture-world";
import { REPOSITORY } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

/**
 * An episode's end reaches Person before its process is stopped.
 *
 * `episode_ended` carries Person's experienced time (ADR 0006) and is where
 * cognition writes its final snapshot. If the runtime stops cognition before
 * it has handled the end, the clock loses everything since Person's last
 * memory and no snapshot is written. TESTED IN FIXTURE.
 */

const COGNITION = ["uv", "run", "person-cognition"];

function journal(
  evidenceDirectory: string,
): { type: string; payload: Record<string, unknown> }[] {
  const directory = path.join(evidenceDirectory, "journal");
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
  "an episode that runs out of decisions still ends in Person's record",
  { timeout: 300000 },
  async () => {
    const { evidenceDirectory, report } = await runEpisode({
      worldFile: "fixtures/worlds/vertical-slice.json",
      cognitionCommand: COGNITION,
      maxDecisions: 6,
    });
    assert.equal(report.outcome, "completed");
    const ended = journal(evidenceDirectory).filter(
      (event) => event.type === "episode_ended",
    );
    assert.equal(ended.length, 1, "the end was handled, once");
    assert.ok(
      Number(ended[0]!.payload["experienced_ticks"]) > 0,
      "and it carries the experienced time",
    );
    assert.ok(
      existsSync(path.join(evidenceDirectory, "snapshots")) &&
        readdirSync(path.join(evidenceDirectory, "snapshots")).length > 0,
      "and cognition wrote its final snapshot",
    );
  },
);

/** A body that, like Mineflayer, forgets the world's clock once disconnected. */
class ForgetfulWorld extends FixtureWorld {
  #gone = false;
  override async disconnect(): Promise<void> {
    this.#gone = true;
    await super.disconnect();
  }
  override snapshot(): ReturnType<FixtureWorld["snapshot"]> {
    const snapshot = super.snapshot();
    return this.#gone ? { ...snapshot, tick: 0 } : snapshot;
  }
}

test(
  "an episode's length is measured before the body is let go",
  { timeout: 300000 },
  async () => {
    const definition = JSON.parse(
      readFileSync(
        path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json"),
        "utf8",
      ),
    );
    const { report } = await runEpisode({
      worldObject: new ForgetfulWorld(definition),
      cognitionCommand: COGNITION,
      maxDecisions: 4,
    });
    assert.ok(report.elapsedTicks > 0, `elapsed ${report.elapsedTicks}`);
    assert.ok(report.endTick >= report.decisions.at(-1)!.tick);
  },
);
