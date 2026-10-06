import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import type { FixtureWorldDefinition } from "#fixture-world";
import { temporaryDirectory } from "../support/harness.ts";
import { runEpisode } from "../support/runtime.ts";

/**
 * Person's memory, end to end: the real runtime, the real cognition process,
 * a fixture body, and the journal the memory store is rebuilt from.
 *
 * What is checked is what memory is allowed to hold. It holds what Person
 * perceived and did, never what only the body knew; it survives a restart;
 * it comes back a few memories at a time; and it never claims that Person
 * acted on the particular thing it saw.
 *
 * TESTED IN FIXTURE. None of this is live Minecraft evidence.
 */

const COGNITION = ["uv", "run", "person-cognition"];
const RECALL_LIMIT = 3;

interface JournalEvent {
  event_id: string;
  session_id: string;
  type: string;
  payload: Record<string, unknown>;
}

interface Encoded {
  kind: string;
  subjects: string[];
  details: Record<string, unknown>;
  provenance: Record<string, unknown>;
}

function readJournal(evidenceDirectory: string): JournalEvent[] {
  const journal = path.join(evidenceDirectory, "journal");
  return readdirSync(journal)
    .filter((name) => name.endsWith(".jsonl"))
    .sort()
    .flatMap((name) =>
      readFileSync(path.join(journal, name), "utf8").split("\n"),
    )
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as JournalEvent);
}

const memories = (events: JournalEvent[]): (Encoded & { id: string })[] =>
  events
    .filter((event) => event.type === "memory_encoded")
    .map((event) => ({
      id: event.event_id,
      ...(event.payload as unknown as Encoded),
    }));

function world(
  blocks: FixtureWorldDefinition["blocks"],
): Partial<FixtureWorldDefinition> {
  return {
    name: "memory",
    spawn: { x: 0, y: 64, z: 0 },
    // Facing negative Z.
    spawnYaw: 0,
    vitals: { health: 20, food: 20, saturation: 5, air: 300, armor: 0 },
    blocks,
  };
}

const trunk = (x: number, z: number): FixtureWorldDefinition["blocks"] =>
  [64, 65, 66].map((y) => ({ position: { x, y, z }, name: "oak_log" }));

const dirtWall = (z: number): FixtureWorldDefinition["blocks"] => {
  const blocks: FixtureWorldDefinition["blocks"] = [];
  for (let x = -6; x <= 6; x++)
    for (let y = 64; y <= 70; y++)
      blocks.push({ position: { x, y, z }, name: "dirt" });
  return blocks;
};

/** The only keys each kind of episode may carry in its details. */
const WHITELIST: Record<string, string[]> = {
  perceived: ["what", "count", "recognised", "nearest_range", "day_phase"],
  acted: [
    "skill",
    "status",
    "emergency",
    "effects",
    "inventory",
    "health_cost",
    "requested",
  ],
  endangered: ["trigger", "response"],
  hurt: ["health_lost", "health_after"],
  searched: ["sought", "conclusion", "looks"],
};

test(
  "wood Person never perceived never becomes a memory of wood",
  { timeout: 180000 },
  async () => {
    // Behind a wall and out of range: the body knows both trees are there.
    const { evidenceDirectory } = await runEpisode({
      world: world([...dirtWall(4), ...trunk(0, 8), ...trunk(0, 40)]),
      cognitionCommand: COGNITION,
      maxDecisions: 20,
    });
    const remembered = memories(readJournal(evidenceDirectory));
    assert.ok(remembered.length > 0, "Person remembered something");
    assert.ok(
      !remembered.some(
        (memory) =>
          memory.kind === "perceived" && memory.subjects.includes("wood"),
      ),
      JSON.stringify(remembered.map((memory) => memory.subjects)),
    );
    // What it does remember about wood is that it looked and did not find it.
    const searched = remembered.filter((memory) => memory.kind === "searched");
    assert.ok(searched.length > 0);
    for (const memory of searched)
      assert.equal(memory.details["conclusion"], "not_found_in_bounded_search");
  },
);

test(
  "nothing only the body knew reaches memory",
  { timeout: 180000 },
  async () => {
    const { evidenceDirectory, world: body } = await runEpisode({
      world: world(trunk(0, 8)),
      cognitionCommand: COGNITION,
      maxDecisions: 12,
    });
    const remembered = memories(readJournal(evidenceDirectory));
    assert.ok(
      remembered.some(
        (memory) =>
          memory.kind === "perceived" && memory.subjects.includes("wood"),
      ),
      "the tree was found by looking, and remembered",
    );
    for (const memory of remembered) {
      for (const key of Object.keys(memory.details))
        assert.ok(
          WHITELIST[memory.kind]?.includes(key),
          `${memory.kind} carries ${key}`,
        );
    }
    const serialized = JSON.stringify(remembered);
    const position = body.snapshot().position;
    for (const forbidden of [
      '"x"',
      '"y"',
      '"z"',
      "position",
      "entityId",
      "uuid",
      "yaw",
      "pitch",
      `${position.x},${position.y},${position.z}`,
    ])
      assert.ok(!serialized.includes(forbidden), `memory holds ${forbidden}`);
  },
);

test(
  "memory survives a restart and still comes back only when cued, a few at a time",
  { timeout: 300000 },
  async () => {
    const evidenceDirectory = temporaryDirectory("person-memory-evidence-");
    // No wood anywhere: Person searches, fails, and remembers failing.
    await runEpisode({
      world: world([]),
      cognitionCommand: COGNITION,
      maxDecisions: 24,
      evidenceDirectory,
      episodeId: "ep_first",
    });
    const before = readJournal(evidenceDirectory);
    const earlier = new Set(memories(before).map((memory) => memory.id));
    assert.ok(earlier.size > 0);

    await runEpisode({
      world: world([]),
      cognitionCommand: COGNITION,
      maxDecisions: 12,
      evidenceDirectory,
      episodeId: "ep_second",
    });
    const after = readJournal(evidenceDirectory).slice(before.length);
    const recalls = after.filter((event) => event.type === "memory_recalled");
    assert.ok(recalls.length > 0, "the new session cued recall");
    const returned = new Set<string>();
    for (const recall of recalls) {
      const ids = recall.payload["recalled"] as string[];
      assert.ok(ids.length <= RECALL_LIMIT, `${ids.length} memories at once`);
      for (const id of ids) returned.add(id);
    }
    assert.ok(
      [...returned].some((id) => earlier.has(id)),
      "something from before the restart came back",
    );
    // Every recall was asked for, by a search, with a cue. That the store
    // never comes back whole when it is large is the Python suite's
    // `test_restart_does_not_inject_the_store`; this world is too small for
    // the difference to show.
    for (const recall of recalls)
      assert.equal(
        (recall.payload["cue"] as Record<string, unknown>)["purpose"],
        "search",
      );
    const search = after.find(
      (event) =>
        event.type === "information_search" &&
        event.payload["phase"] === "started",
    );
    assert.ok(
      search,
      "Person still looked: memory of a failed search is not absence",
    );
  },
);

test(
  "felling some tree is not remembered as felling the tree Person saw",
  { timeout: 180000 },
  async () => {
    // Tree A is ahead, in view. Tree B is nearer and behind Person, out of
    // view. Under C4 the motor fells the nearest tree it knows of, which is B.
    const treeA = trunk(0, -10);
    const treeB = trunk(0, 4);
    const { evidenceDirectory, world: body } = await runEpisode({
      world: world([...treeA, ...treeB]),
      cognitionCommand: COGNITION,
      maxDecisions: 2,
    });
    assert.ok(
      treeB.some((block) => body.blockAt(block.position)?.name !== "oak_log"),
      "the scenario needs the motor to have chosen tree B",
    );

    const remembered = memories(readJournal(evidenceDirectory));
    const saw = remembered.filter(
      (memory) =>
        memory.kind === "perceived" && memory.subjects.includes("wood"),
    );
    const cut = remembered.filter(
      (memory) =>
        memory.kind === "acted" && memory.details["skill"] === "gather_wood",
    );
    assert.equal(saw.length, 1, "Person saw a tree");
    assert.equal(cut.length, 1, "Person cut wood");
    const action = JSON.stringify(cut[0]);
    assert.ok(!action.includes(saw[0]!.id), "no link to the tree it saw");
    assert.ok(
      !action.includes(String(saw[0]!.provenance["message_id"])),
      "not even through the observation it came from",
    );
    for (const binding of ["target", "referent", '"what"'])
      assert.ok(!action.includes(binding), `the action claims a ${binding}`);
  },
);
