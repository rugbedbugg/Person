import type { SkillImplementation } from "../execution.ts";
import { SkillFailure } from "../execution.ts";
import { GAZE_DIRECTIONS, type GazeDirection } from "../../embodiment/gaze.ts";
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
 * On its own it is not the way Person looks for something, because the views it
 * passes through never reach cognition: see `look` below for that.
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

/**
 * One deliberate glance, and Person stays looking that way.
 *
 * This is the motor half of information seeking. Cognition names a direction
 * from the closed gaze vocabulary; the runtime turns the head one step on its
 * own side of the firewall; the next ordinary observation is taken from the
 * new pose. Whether that glance was the right one, and whether to take
 * another, is decided above the boundary from what the observation shows.
 *
 * The skill reports nothing about what came into view, and no angle. It
 * cannot, because it never looks at the snapshot's contents: which way is
 * worth looking is cognition's judgement, not the body's.
 */
export const look: SkillImplementation = async (context) => {
  context.checkpoint();
  const direction = context.parameters["direction"];
  // The validator already enforced the enum; this is the executor refusing to
  // trust that nothing between them changed.
  if (!GAZE_DIRECTIONS.includes(direction as GazeDirection))
    throw new SkillFailure(
      "invalid_direction",
      "INVALIDATED",
      "look was asked for a direction outside the gaze vocabulary",
    );
  await context.embodiment.look(direction as GazeDirection);
  context.checkpoint();
  context.effect("looked");
  context.note("elapsed_ticks", { gazeSteps: 1 });
};

export const perceptionSkills: Record<string, SkillImplementation> = {
  look_around: lookAround,
  look,
};
