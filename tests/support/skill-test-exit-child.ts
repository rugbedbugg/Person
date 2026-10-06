/**
 * One `person skill-test` invocation, in its own process.
 *
 * A validation run holds more things open than an observation does: a body, a
 * status writer, a comparison subprocess, and during operator setup the
 * terminal itself. Every one of them has to be released without help. This
 * child exists to be waited on, so a leak shows up as a process that will not
 * end rather than as a comment claiming it cannot happen.
 *
 * Not named as a test file, because it is meant to be spawned.
 */
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { main } from "../../apps/cli/src/bin/person.ts";
import { REPOSITORY } from "./harness.ts";

const mode = process.argv[2] ?? "plain";
const directory = mkdtempSync(path.join(tmpdir(), "person-skill-test-"));
const source = readFileSync(
  path.join(REPOSITORY, "examples/fixture.toml"),
  "utf8",
);
const configFile = path.join(directory, "fixture.toml");
writeFileSync(
  configFile,
  source
    .replace('outputDirectory = "../runs"', `outputDirectory = "${directory}"`)
    .replace(
      'evidenceDirectory = "../runs/evidence"',
      `evidenceDirectory = "${path.join(directory, "evidence")}"`,
    )
    .replace(
      'fixtureWorld = "../fixtures/worlds/vertical-slice.json"',
      `fixtureWorld = "${path.join(REPOSITORY, "fixtures/worlds/vertical-slice.json")}"`,
    ),
);

const argv = [
  process.execPath,
  "person",
  "skill-test",
  "--config",
  configFile,
  "--skill",
  mode === "unknown" ? "definitely_not_a_skill" : "wait_safely",
  ...(mode === "operator-setup" || mode === "operator-abandoned"
    ? ["--operator-setup"]
    : []),
];

const code = await main(argv);
process.stdout.write(`\nexit=${code}\n`);
process.exitCode = code;
