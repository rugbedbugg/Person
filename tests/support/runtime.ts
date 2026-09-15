import path from "node:path";
import { PersonRuntime, type EpisodeReport } from "#node-runtime";
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
  worldObject?: FixtureWorld;
  episodeId?: string;
  personId?: string;
  operatorIntervention?: { reason?: string };
}

/** Runs a complete episode with a real cognition subprocess over stdio. */
export async function runEpisode(options: RuntimeRunOptions): Promise<{
  report: EpisodeReport;
  world: FixtureWorld;
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
    runtime: { ...config.runtime, maxDecisions: options.maxDecisions ?? 12 },
    learning: {
      ...config.learning,
      mode: options.learningMode ?? "off",
      evidenceDirectory,
    },
    cognition: { ...config.cognition, command: options.cognitionCommand },
  };
  const world =
    options.worldObject ??
    (options.worldFile
      ? FixtureWorld.fromFile(path.join(REPOSITORY, options.worldFile))
      : new FixtureWorld(options.world ?? {}));
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
