import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import path from "node:path";
import { REPOSITORY } from "../support/harness.ts";

/**
 * A validation run has to end by itself, on every path.
 *
 * The last milestone spent a real debugging session on a command that did the
 * right thing and then refused to exit, so this one is checked rather than
 * assumed. The operator setup phase makes it sharper: a command that reads the
 * terminal and forgets to let go of it never returns, and there is no amount of
 * careful code review that proves it did.
 */
const DEADLINE_MS = 30000;

interface ChildResult {
  code: number | null;
  killed: boolean;
  stdout: string;
  stderr: string;
  elapsedMs: number;
}

function runChild(
  mode: string,
  options: { closeStdin?: boolean; replyOn?: RegExp } = {},
): Promise<ChildResult> {
  const child = spawn(
    process.execPath,
    [path.join(REPOSITORY, "tests/support/skill-test-exit-child.ts"), mode],
    { cwd: REPOSITORY, stdio: ["pipe", "pipe", "pipe"] },
  );
  let stdout = "";
  let stderr = "";
  let answered = false;
  const started = Date.now();

  child.stdout.on("data", (chunk: Buffer) => (stdout += chunk.toString()));
  child.stderr.on("data", (chunk: Buffer) => {
    stderr += chunk.toString();
    if (options.replyOn && !answered && options.replyOn.test(stderr)) {
      answered = true;
      child.stdin.write("\n");
    }
  });
  if (options.closeStdin) child.stdin.end();

  return new Promise<ChildResult>((resolve) => {
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      resolve({
        code: null,
        killed: true,
        stdout,
        stderr,
        elapsedMs: Date.now() - started,
      });
    }, DEADLINE_MS);
    child.once("exit", (code) => {
      clearTimeout(timer);
      child.stdin.destroy();
      resolve({
        code,
        killed: false,
        stdout,
        stderr,
        elapsedMs: Date.now() - started,
      });
    });
  });
}

test("a successful skill test exits on its own", async () => {
  const result = await runChild("plain", { closeStdin: true });
  assert.equal(
    result.killed,
    false,
    `the process had to be killed after ${result.elapsedMs}ms: something is holding the event loop open\n${result.stderr}`,
  );
  assert.equal(result.code, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /Skill validation: wait_safely/);
  assert.match(result.stdout, /executed\s+wait_safely/);
  assert.match(result.stdout, /learning\s+unchanged/);
  assert.match(result.stdout, /report\s+\S+skill-tests\S+\.json/);
});

test("a refused skill test exits non-zero, on its own", async () => {
  const result = await runChild("unknown", { closeStdin: true });
  assert.equal(result.killed, false, "a refusal must not hang either");
  assert.equal(result.code, 2);
  assert.match(result.stdout, /is not a registered skill/);
});

test("operator setup releases the terminal once the operator answers", async () => {
  const result = await runChild("operator-setup", {
    replyOn: /READY FOR OPERATOR SETUP/,
  });
  assert.equal(
    result.killed,
    false,
    `the process kept standard input open after the operator answered (${result.elapsedMs}ms)`,
  );
  assert.equal(result.code, 0, result.stdout + result.stderr);
  assert.match(result.stderr, /READY FOR OPERATOR SETUP/);
  assert.match(
    result.stderr,
    /will not begin the measured test until you continue/,
  );
  assert.match(result.stdout, /setup\s+operator, confirmed/);
});

test("operator setup that is never confirmed refuses instead of waiting forever", async () => {
  const result = await runChild("operator-abandoned", { closeStdin: true });
  assert.equal(result.killed, false, "an abandoned setup must still end");
  assert.equal(result.code, 1);
  assert.match(result.stdout, /operator_setup_abandoned/);
  assert.doesNotMatch(
    result.stdout,
    /executed\s+wait_safely/,
    "the measured skill must never have run",
  );
});
