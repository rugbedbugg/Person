import type { SkillImplementation } from "../execution.ts";
import { SkillFailure } from "../execution.ts";
import { survey } from "../survey.ts";

/**
 * Looking around, as something Person decides to do.
 *
 * This is the only skill that changes nothing about the world. Its whole
 * effect is on Person: it ends with Person facing somewhere else, and the next
 * observation is therefore about somewhere else. Everything it learns it
 * learns through the ordinary perception path, so a wall is still a wall and
 * range is still range while it runs.
 *
 * It goes through dispatch like every other physical act, which is the point.
 * Gaze is motor control, and a motor capability that bypassed the validator
 * and the safety kernel would be a second way into the body.
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
  // Engineering detail only. `settledStep` is a count of gaze steps rather
  // than an angle, and none of this reaches cognition: it lands in the skill
  // outcome's evidence, which is operator-facing.
  context.note("elapsed_ticks", {
    orientationsSampled: result.orientationsSampled,
    perceptsAtSettled: result.perceptsAtSettled,
  });
};

export const perceptionSkills: Record<string, SkillImplementation> = {
  look_around: lookAround,
};
