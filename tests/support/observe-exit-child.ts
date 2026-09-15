/**
 * A single failed `person observe`, run in its own process.
 *
 * The point is not the failure, which is correct and must stay: Person spawned
 * outside the configured exploration area and refused to continue. The point
 * is what happens afterwards. The first real attempt at first contact reported
 * `spawn_outside_bounds` exactly as designed and then sat there until it was
 * killed by hand, so this child exists to be waited on: if it does not exit on
 * its own, the regression is back.
 *
 * Not a test file by name, because it is meant to be spawned rather than run
 * by the test runner.
 */
import { MineflayerEmbodiment } from "#minecraft-adapter";
import { captureObservation } from "../../apps/cli/src/observe.ts";
import { REPOSITORY, baseConfig } from "./harness.ts";
import { doubleFactory } from "./mineflayer-double.ts";

const base = baseConfig();
const config = {
  ...base,
  runtime: {
    ...base.runtime,
    embodiment: "minecraft" as const,
    trainingContext: "minecraft_peaceful" as const,
  },
  server: { host: "127.0.0.1", port: 25565, version: "1.16.1" as const },
  bot: { username: "PersonAda", auth: "offline" as const },
};

// Far outside the exploration box, with a body whose socket shuts down the way
// minecraft-protocol's really does.
const { createBot } = doubleFactory({
  position: { x: 200, y: 64, z: 200 },
  emulateSocket: true,
  socketCloseDelayMs: 0,
});
const embodiment = new MineflayerEmbodiment(config, {
  createBot: createBot as never,
  connectTimeoutMs: 5000,
});

try {
  await captureObservation(config, REPOSITORY, {
    embodiment,
    disconnectTimeoutMs: 3000,
  });
  process.stdout.write("observed\n");
  process.exitCode = 3;
} catch (error) {
  const failure = error as { reason?: string };
  process.stdout.write(`${failure.reason ?? "unknown_error"}\n`);
  process.exitCode = 1;
}
