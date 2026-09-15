import path from "node:path";
import type { PersonConfig } from "#config";
import type { Embodiment } from "#node-runtime";
import { FixtureWorld } from "#fixture-world";

/**
 * Chooses the body for a run.
 *
 * Fixture and Mineflayer implement the same port, so nothing above this
 * function needs to know which one it is talking to. The Mineflayer adapter is
 * imported lazily so a fixture run never loads a Minecraft client.
 */
export async function createEmbodiment(
  config: PersonConfig,
  baseDirectory: string,
): Promise<Embodiment> {
  if (config.runtime.embodiment === "fixture") {
    const world = config.runtime.fixtureWorld;
    if (!world)
      throw new Error(
        "runtime.fixtureWorld is required for the fixture embodiment",
      );
    return FixtureWorld.fromFile(path.resolve(baseDirectory, world));
  }
  const { MineflayerEmbodiment } = await import("#minecraft-adapter");
  return new MineflayerEmbodiment(config);
}
