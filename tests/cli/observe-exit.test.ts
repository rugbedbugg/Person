import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import path from "node:path";
import { REPOSITORY } from "../support/harness.ts";

/**
 * A failed observe has to end by itself.
 *
 * Person's first attempt at first contact spawned outside the configured
 * exploration area and refused to go on, which is the correct answer. It then
 * held the terminal open until it was killed by hand. The cause was in
 * disconnect: the session was ended twice, and `minecraft-protocol` arms a
 * thirty-second close timer on every end while clearing it only on the first
 * close, so the second end left a timer nothing would ever clear.
 *
 * This runs the whole failure in a real child process and waits for it. Thirty
 * seconds is the exact length of the stall being guarded against, so the
 * deadline sits well below it: a child that has not finished in twelve seconds
 * has the bug back.
 */
const DEADLINE_MS = 12000;

test("a rejected spawn exits on its own, without Ctrl-C", async () => {
  const child = spawn(
    process.execPath,
    [path.join(REPOSITORY, "tests/support/observe-exit-child.ts")],
    { cwd: REPOSITORY, stdio: ["ignore", "pipe", "pipe"] },
  );
  let output = "";
  child.stdout.on("data", (chunk: Buffer) => (output += chunk.toString()));
  child.stderr.on("data", () => {});

  const started = Date.now();
  const outcome = await new Promise<{ code: number | null; killed: boolean }>(
    (resolve) => {
      const timer = setTimeout(() => {
        child.kill("SIGKILL");
        resolve({ code: null, killed: true });
      }, DEADLINE_MS);
      child.once("exit", (code) => {
        clearTimeout(timer);
        resolve({ code, killed: false });
      });
    },
  );
  const elapsed = Date.now() - started;

  assert.equal(
    outcome.killed,
    false,
    `the process had to be killed after ${elapsed}ms: a failed observe is holding the event loop open`,
  );
  assert.equal(outcome.code, 1, "a failed observation exits non-zero");
  assert.match(
    output,
    /spawn_outside_bounds/,
    "and it still reports precisely why it refused",
  );
});
