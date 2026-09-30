import path from "node:path";
import {
  PersonRuntime,
  type Embodiment,
  type EpisodeReport,
} from "#node-runtime";
import { FixtureWorld } from "#fixture-world";
import {
  REPOSITORY,
  baseConfig,
  temporaryDirectory,
  type HarnessOptions,
} from "./harness.ts";

export interface RuntimeRunOptions extends HarnessOptions {
  cognitionCommand: string[];
  maxDecisions?: number;
  learningMode?: "off" | "shadow" | "supervised";
  evidenceDirectory?: string;
  world?: HarnessOptions["world"];
  episodeId?: string;
  personId?: string;
  operatorIntervention?: { reason?: string };
  /** ADR 0017, I2: reconnection budget after the world is lost. */
  reconnectAttempts?: number;
  /** ADR 0017, I3: what a death means. */
  death?: "respawn" | "permadeath";
}

/**
 * Runs a complete episode with a real cognition subprocess over stdio, in the
 * fixture world unless another body is given.
 */
export async function runEpisode<W extends Embodiment = FixtureWorld>(
  options: RuntimeRunOptions & { worldObject?: W },
): Promise<{
  report: EpisodeReport;
  world: W;
  evidenceDirectory: string;
  outputDirectory: string;
}> {
  const outputDirectory =
    options.outputDirectory ?? temporaryDirectory("person-run-");
  const evidenceDirectory =
    options.evidenceDirectory ?? temporaryDirectory("person-evidence-");
  const config = baseConfig({ ...options, outputDirectory });
  const runtimeConfig = {
    ...config,
    ...(options.personId ? { personId: options.personId } : {}),
    runtime: {
      ...config.runtime,
      maxDecisions: options.maxDecisions ?? 12,
      reconnectAttempts: options.reconnectAttempts ?? 0,
      reconnectIntervalMs: 0,
    },
    learning: {
      ...config.learning,
      mode: options.learningMode ?? "off",
      evidenceDirectory,
    },
    cognition: { ...config.cognition, command: options.cognitionCommand },
    ...(options.death ? { lifecycle: { death: options.death } } : {}),
  };
  const world =
    options.worldObject ??
    ((options.worldFile
      ? FixtureWorld.fromFile(path.join(REPOSITORY, options.worldFile))
      : new FixtureWorld(options.world ?? {})) as unknown as W);
  const runtime = new PersonRuntime({
    config: runtimeConfig,
    embodiment: world,
    cwd: REPOSITORY,
    ...(options.episodeId ? { episodeId: options.episodeId } : {}),
    ...(options.operatorIntervention
      ? { operatorIntervention: options.operatorIntervention }
      : {}),
  });
  const report = await runtime.run();
  return { report, world, evidenceDirectory, outputDirectory };
}
