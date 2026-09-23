import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import type { EpisodeReport } from "#node-runtime";
import type { FixtureWorldDefinition } from "#fixture-world";
import { runEpisode } from "../support/runtime.ts";

/**
 * Information seeking, end to end: the real runtime, the real dispatch path,
 * the real cognition process, a fixture body.
 *
 * Person is well fed and has no shelter, which needs wood. What differs
 * between the scenarios is only where the trees are: behind Person, nowhere,
 * too far to see, or behind a wall. The first must be found by looking; the
 * rest must not be, and Person's decisions must not be able to tell them
 * apart, because what separates them is physical truth Person never perceived.
 *
 * TESTED IN FIXTURE. None of this is live Minecraft evidence.
 */

const COGNITION = ["uv", "run", "person-cognition"];
const LOOK_BUDGET = 8;

function world(
  blocks: FixtureWorldDefinition["blocks"],
): Partial<FixtureWorldDefinition> {
  return {
    name: "information-seeking",
    spawn: { x: 0, y: 64, z: 0 },
    // Facing negative Z. Everything interesting is elsewhere.
    spawnYaw: 0,
    vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
    blocks,
  };
}

/** A small tree trunk, the only wood in the world. */
const trunk = (x: number, z: number): FixtureWorldDefinition["blocks"] =>
  [64, 65, 66].map((y) => ({ position: { x, y, z }, name: "oak_log" }));

/** An opaque wall that is not itself anything Person would look for. */
const dirtWall = (z: number): FixtureWorldDefinition["blocks"] => {
  const blocks: FixtureWorldDefinition["blocks"] = [];
  for (let x = -6; x <= 6; x++)
    for (let y = 64; y <= 70; y++)
      blocks.push({ position: { x, y, z }, name: "dirt" });
  return blocks;
};

async function episode(
  blocks: FixtureWorldDefinition["blocks"],
  maxDecisions: number,
): Promise<{ report: EpisodeReport; evidenceDirectory: string }> {
  const { report, evidenceDirectory } = await runEpisode({
    world: world(blocks),
    cognitionCommand: COGNITION,
    maxDecisions,
  });
  return { report, evidenceDirectory };
}

const requests = (report: EpisodeReport): string[] =>
  report.decisions.map(
    (decision) =>
      `${decision.requestedSkill}(${JSON.stringify(decision.requestedParameters)})`,
  );

function searches(evidenceDirectory: string): Record<string, unknown>[] {
  const journal = path.join(evidenceDirectory, "journal");
  return readdirSync(journal)
    .filter((name) => name.endsWith(".jsonl"))
    .sort()
    .flatMap((name) =>
      readFileSync(path.join(journal, name), "utf8").split("\n"),
    )
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as { type: string; payload: never })
    .filter((event) => event.type === "information_search")
    .map((event) => event.payload);
}

test(
  "a tree behind Person is found by looking, then used",
  {
    timeout: 120000,
  },
  async () => {
    const { report, evidenceDirectory } = await episode(trunk(0, 8), 8);
    const skills = report.decisions.map((decision) => decision.requestedSkill);

    // Nothing wood-like was in view, so the first thing Person did was look.
    assert.equal(skills[0], "look", skills.join(", "));
    const firstAct = skills.findIndex((skill) => skill !== "look");
    assert.ok(firstAct > 0 && firstAct <= LOOK_BUDGET, skills.join(", "));
    assert.equal(skills[firstAct], "gather_wood", skills.join(", "));

    // Every glance went through the validator like any other physical act.
    for (const decision of report.decisions.slice(0, firstAct)) {
      assert.equal(decision.validation, "ACCEPT");
      assert.equal(decision.executedSkill, "look");
      assert.deepEqual(Object.keys(decision.requestedParameters), [
        "direction",
      ]);
      assert.ok(decision.policyReasonCodes.includes("seeking_evidence"));
    }

    const phases = searches(evidenceDirectory).map((record) => record["phase"]);
    assert.deepEqual(phases.slice(0, 2), ["started", "satisfied"]);
  },
);

test(
  "with no wood anywhere the search is finite and concludes nothing stronger",
  {
    timeout: 120000,
  },
  async () => {
    const { report, evidenceDirectory } = await episode([], 40);
    const skills = report.decisions.map((decision) => decision.requestedSkill);

    assert.ok(!skills.includes("gather_wood"), skills.join(", "));
    const records = searches(evidenceDirectory);
    const started = records.filter((record) => record["phase"] === "started");
    const concluded = records.filter((record) => record["phase"] !== "started");
    assert.ok(started.length >= 1, "Person looked before giving up");
    assert.equal(concluded.length, started.length, "every search ended");
    for (const record of concluded) {
      assert.equal(record["phase"], "exhausted");
      assert.equal(record["conclusion"], "not_found_in_bounded_search");
      assert.ok((record["looks"] as string[]).length <= LOOK_BUDGET);
    }
    // Bounded overall, not only per search: once every goal that needed to see
    // wood has looked and not found it, Person stops looking.
    const looks = skills.filter((skill) => skill === "look").length;
    assert.ok(looks <= started.length * LOOK_BUDGET, `${looks} looks`);
    assert.equal(skills.at(-1), "wait_safely", skills.join(", "));
    assert.ok(!/absent|none_exist|not_exist/i.test(JSON.stringify(report)));
  },
);

test(
  "wood Person cannot perceive changes nothing Person decides",
  {
    timeout: 300000,
  },
  async () => {
    // The body knows about both of these trees: one is beyond the range of
    // vision, the other is behind an opaque wall. Neither is perceptible from
    // anywhere Person can turn to, so neither is evidence, and the decisions
    // must be identical to a world with no wood at all.
    const decisions = 30;
    const nothing = await episode([], decisions);
    const outOfRange = await episode(trunk(0, 40), decisions);
    const occluded = await episode([...dirtWall(4), ...trunk(0, 8)], decisions);

    const baseline = requests(nothing.report);
    assert.ok(baseline.some((request) => request.startsWith("look(")));
    assert.deepEqual(requests(outOfRange.report), baseline, "out of range");
    assert.deepEqual(requests(occluded.report), baseline, "occluded");
    for (const run of [outOfRange, occluded])
      assert.ok(
        !run.report.decisions.some(
          (decision) => decision.requestedSkill === "gather_wood",
        ),
        "undiscovered wood was never acted on",
      );
  },
);
