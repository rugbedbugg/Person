import type { SkillImplementation } from "../execution.ts";
import { SkillFailure } from "../execution.ts";
import { survey } from "../survey.ts";

/**
 * Looking around, as something Person decides to do.
 *
 * This is the only skill that changes nothing, including about Person: the
 * sweep returns to the heading it began with. What it costs is time, and what
 * it is for is being the motor half of looking for something. The other half,
 * deciding where to look next and what a failure to see means, belongs to the
 * planner and is not built yet.
 *
 * It goes through dispatch like every other physical act, which is the point.
 * Gaze is motor control, and a motor capability that bypassed the validator
 * and the safety kernel would be a second way into the body.
 *
 * It establishes nothing about what is or is not out there. A sweep that ended
 * with "and therefore no food exists nearby" would be the motor layer drawing
 * an epistemic conclusion from views cognition never received.
 */
export const lookAround: SkillImplementation = async (context) => {
  context.checkpoint();
  const snapshot = context.snapshot();
  // Turning your back on something that is already on top of you is not a
  // survey, it is a mistake. The kernel will preempt anyway; failing here says
  // why rather than leaving it to look like an interrupted sweep.
  if (context.kernel.threats(snapshot).some((entity) => entity.distance <= 8))
    throw new SkillFailure(
      "threat_appeared",
      "INTERRUPTED",
      "Person will not stand and look around with a hostile in contact range",
    );

  const result = await survey(context.embodiment);
  context.checkpoint();

  context.effect("surveyed");
  // Engineering detail only: counts of orientations and gaze steps, never an
  // angle, and none of it reaches cognition. It lands in the skill outcome's
  // evidence, which is operator-facing.
  context.note("elapsed_ticks", {
    orientationsSampled: result.orientationsSampled,
    gazeSteps: result.gazeSteps,
  });
};

export const perceptionSkills: Record<string, SkillImplementation> = {
  look_around: lookAround,
};
