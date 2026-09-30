/**
 * The observation a fixture world gives Person before its first decision.
 *
 *   node scripts/benchmarks/initial-observation.ts <world.json> [config.toml]
 *
 * Prints the Observation as JSON. It connects the fixture body and reads it
 * once; it never starts cognition, never decides and never acts, so it can be
 * used on a held-out world without consuming any behavioural evidence. The
 * class validators (`validate-class.py`) take their input from here.
 */
import { mkdtempSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { loadConfig } from "#config";
import { FixtureWorld } from "#fixture-world";
import { captureObservation } from "../../apps/cli/src/observe.ts";

const [worldFile, configFile = "examples/fixture.toml"] = process.argv.slice(2);
if (!worldFile) {
  process.stderr.write(
    "usage: initial-observation.ts <world.json> [config.toml]\n",
  );
  process.exit(2);
}
const scratch = mkdtempSync(path.join(os.tmpdir(), "person-initial-"));
const base = loadConfig(configFile);
const config = {
  ...base,
  runtime: {
    ...base.runtime,
    embodiment: "fixture" as const,
    outputDirectory: scratch,
  },
};
const { observation, valid, diagnostics } = await captureObservation(
  config,
  process.cwd(),
  { embodiment: FixtureWorld.fromFile(path.resolve(worldFile)) },
);
if (!valid) {
  process.stderr.write(`invalid observation: ${diagnostics.join("; ")}\n`);
  process.exit(1);
}
process.stdout.write(`${JSON.stringify(observation)}\n`);
