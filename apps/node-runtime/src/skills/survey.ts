import type { Embodiment } from "../embodiment/types.ts";
import { GAZE } from "../embodiment/gaze.ts";

/**
 * A sweep of the head. Nothing more than that.
 *
 * Person turns through a short fixed sequence of orientations and comes back to
 * where it started, with its head levelled. It is a motor primitive: a bounded
 * amount of turning that costs a bounded amount of time.
 *
 * It deliberately does not decide anything. An earlier version settled facing
 * whichever orientation had the most in it, which sounds harmless and is not:
 * "the scene with the most things in it is the most interesting scene" is a
 * judgement about salience, and salience is cognition's to make. A motor
 * capability that quietly picked what Person should be looking at would be the
 * body deciding what matters, which is the one thing the architecture is built
 * to prevent.
 *
 * So this file cannot see. It imports no perception, reads no snapshot, and
 * has no way to know whether it swept past a forest or a blank wall. The
 * endpoint depends only on where the sweep began.
 *
 * That leaves it minimally useful on its own, which is correct for this phase.
 * Looking for something is a loop that belongs to the planner: look in a
 * direction, receive an ordinary observation, reason about it, look again if
 * needed. That loop is built from `Embodiment.look`, and the goal relevance
 * lives in the planner where it can be argued with.
 */

export interface SurveyResult {
  /** How many orientations the sweep visited. Always the same number. */
  orientationsSampled: number;
  /** How many individual gaze steps that took. Always the same number. */
  gazeSteps: number;
}

const stepsFor = (degrees: number): number =>
  Math.round(degrees / GAZE.yawStepDegrees);

/** Turns by whole gaze steps. Negative is to Person's right. */
async function turnSteps(
  embodiment: Embodiment,
  steps: number,
): Promise<number> {
  const direction = steps < 0 ? "right" : "left";
  const count = Math.abs(steps);
  for (let taken = 0; taken < count; taken++) await embodiment.look(direction);
  return count;
}

/**
 * Sweeps through `GAZE.scanOrientations` and returns to the starting heading.
 *
 * The endpoint is fixed: the yaw Person began with, and a level head. It does
 * not depend on what was in any of the orientations, so two sweeps from the
 * same heading end identically whether Person is in an empty field or a crowd.
 */
export async function survey(embodiment: Embodiment): Promise<SurveyResult> {
  // Level the head first, so a sweep means the same thing whatever Person
  // happened to be looking at, and so the endpoint is reachable by yaw alone.
  await embodiment.look("forward");

  let current = 0;
  let steps = 1;
  for (const offset of GAZE.scanOrientations) {
    const wanted = stepsFor(offset);
    steps += await turnSteps(embodiment, wanted - current);
    current = wanted;
  }
  steps += await turnSteps(embodiment, -current);

  return {
    orientationsSampled: GAZE.scanOrientations.length,
    gazeSteps: steps,
  };
}
