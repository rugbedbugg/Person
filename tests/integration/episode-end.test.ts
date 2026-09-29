import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
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
