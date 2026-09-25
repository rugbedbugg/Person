import { createInterface } from "node:readline";
import {
  describeConnection,
  loadConfig,
  withConnectionOverride,
  type ConnectionOverride,
} from "#config";
import {
  OperatorSetupAborted,
  runSkillValidation,
  summariseSkillValidation,
  type OperatorSetupInfo,
} from "#node-runtime";
import { skillRegistry } from "#skills";
import { createEmbodiment } from "./embodiment.ts";
import { resolveBase } from "./observe.ts";

/**
 * `person skill-test`: validate one existing skill against a real body.
 *
 * A debugging instrument, not a way to operate Person. It takes the name of a
 * skill that is already in the library, builds one proposal from that skill's
 * own specification, and sends it down the same road a decision from cognition
 * would take. There is no way to pass it an action the library does not
 * already contain.
 */

export interface SkillTestOptions {
  configPath: string;
  skillId: string;
  json: boolean;
  operatorSetup?: boolean;
  connection?: ConnectionOverride;
  operatorIntervention?: { reason?: string };
  /** Injected by tests; the real command waits on the terminal. */
  confirmSetup?: (info: OperatorSetupInfo) => Promise<void>;
}

export interface SkillTestResult {
  code: number;
  output: string;
}

const SETUP_BANNER = (info: OperatorSetupInfo): string =>
  [
    "",
    "READY FOR OPERATOR SETUP",
    "Person will not begin the measured test until you continue.",
    "",
    `  skill      ${info.skillId}`,
    `  standing   ${info.position.x},${info.position.y},${info.position.z}`,
    `  home       ${info.home.x},${info.home.y},${info.home.z}`,
    `  distance   ${info.physicalHomeDistance.toFixed(1)} blocks from home (physical)`,
    "",
    "Position Person yourself now, using your own Minecraft controls.",
    "Person is inert: it will not move, act, or decide anything until you",
    "press Enter. Ctrl-C abandons the test without running the skill.",
    "",
  ].join("\n");

/**
 * Waits for the operator, and releases the terminal afterwards.
 *
 * Standard input is a resource like any other: a command that reads it and
 * forgets to let go never exits, which is precisely the failure this milestone
 * already had to fix once elsewhere.
 */
export async function confirmOnStdin(info: OperatorSetupInfo): Promise<void> {
  process.stderr.write(SETUP_BANNER(info));
  process.stderr.write("Press Enter when Person is where you want it: ");
  const input = process.stdin;
  const readline = createInterface({ input });
  try {
    await new Promise<void>((resolve, reject) => {
      readline.once("line", () => resolve());
      readline.once("close", () =>
        reject(
          new OperatorSetupAborted(
            "operator_setup_abandoned",
            "Standard input closed before the operator confirmed the setup",
          ),
        ),
      );
    });
    process.stderr.write("\nContinuing. The measured run starts now.\n");
  } finally {
    readline.close();
    input.pause();
    input.unref?.();
  }
}

export async function skillTestCommand(
  options: SkillTestOptions,
): Promise<SkillTestResult> {
  const config = withConnectionOverride(
    loadConfig(options.configPath),
    options.connection ?? {},
  );
  const registry = skillRegistry();
  if (!registry.has(options.skillId))
    return {
      code: 2,
      output:
        `${options.skillId} is not a registered skill.\n` +
        `Known skills: ${registry.ids.join(", ")}\n`,
    };

  const identity = describeConnection(config, options.connection ?? {});
  if (!options.json && config.runtime.embodiment === "minecraft")
    process.stderr.write(`person: connecting to ${identity}\n`);

  const embodiment = await createEmbodiment(
    config,
    resolveBase(options.configPath),
  );
  // Positioning Person by hand is an intervention, and a validation run that
  // needed one says so in its own record without being asked twice.
  const intervention =
    options.operatorIntervention ??
    (options.operatorSetup
      ? { reason: "operator positioned Person for a skill validation run" }
      : undefined);

  const run = await runSkillValidation({
    config,
    embodiment,
    skillId: options.skillId,
    ...(options.operatorSetup ? { operatorSetup: true } : {}),
    ...(options.operatorSetup
      ? { confirmSetup: options.confirmSetup ?? confirmOnStdin }
      : {}),
    ...(intervention ? { operatorIntervention: intervention } : {}),
    cwd: process.cwd(),
    onEvent: (kind, detail) => {
      if (options.json) return;
      if (kind === "validated")
        process.stderr.write(
          `person: safety ${String(detail["decision"])}, executing ${String(detail["executedSkill"] ?? "nothing")}\n`,
        );
      if (kind === "emergency")
        process.stderr.write(
          `person: emergency ${String(detail["trigger"])} -> ${String(detail["action"])}\n`,
        );
    },
  });

  if (options.json)
    return {
      code: run.code,
      output: `${JSON.stringify({ reportPath: run.reportPath, report: run.report }, null, 2)}\n`,
    };
  return {
    code: run.code,
    output: `${summariseSkillValidation(run.report, run.reportPath)}\n`,
  };
}
