import type { Position } from "#config";
import type { Embodiment } from "../embodiment/types.ts";
import { GAZE } from "../embodiment/gaze.ts";
import { eyePose, visible, VISION } from "../observation/vision.ts";

/**
 * Looking around.
 *
 * Person turns through a short fixed sweep, notices how much is perceptible
 * from each orientation, and settles facing the one that showed the most. The
 * sweep is the whole mechanism: there is no merged scene at the end of it, and
 * nothing is remembered from the orientations Person turned away from.
 *
 * That last part is deliberate rather than unfinished. Person has no memory
 * yet (C6), so a survey that handed cognition everything it had glimpsed would
 * be inventing one, and a perfect one at that. What a survey can honestly do
 * without memory is leave Person looking at something it could not see before,
 * which the next ordinary observation then reports through the Phase 3
 * firewall like any other percept.
 *
 * The cost is fixed: `GAZE.scanOrientations.length` orientations, one
 * perception pass each, each pass bounded by the same range, field of view and
 * ray budget every other pass uses.
 */

export interface SurveyResult {
  /** How many orientations were sampled. Always the same number. */
  orientationsSampled: number;
  /** How much was perceptible from the orientation Person settled on. */
  perceptsAtSettled: number;
  /**
   * Where Person ended up looking, relative to where the survey started, in
   * whole gaze steps. Engineering detail: it is never reported to cognition.
   */
  settledStep: number;
}

const stepsFor = (degrees: number): number =>
  Math.round(degrees / GAZE.yawStepDegrees);

/** How much Person can perceive from where it is standing and looking now. */
function perceptibleCount(embodiment: Embodiment): number {
  const snapshot = embodiment.snapshot();
  const pose = eyePose(snapshot);
  const blockAt = (position: Position): { solid: boolean } | null =>
    embodiment.blockAt(position);

  const entities = visible(
    snapshot.entities,
    (entity) => entity.position,
    pose,
    blockAt,
    { limit: VISION.maxRayTests },
  ).length;
  const resources = visible(
    snapshot.resources,
    (block) => block.position,
    pose,
    blockAt,
    { limit: VISION.maxRayTests },
  ).length;
  return entities + resources;
}

/** Turns by whole gaze steps, negative to Person's right. */
async function turnSteps(embodiment: Embodiment, steps: number): Promise<void> {
  const direction = steps < 0 ? "right" : "left";
  for (let taken = 0; taken < Math.abs(steps); taken++)
    await embodiment.look(direction);
}

export async function survey(embodiment: Embodiment): Promise<SurveyResult> {
  // Level the head first, so a survey means the same thing whatever Person was
  // looking at before it.
  await embodiment.look("forward");

  let current = 0;
  let bestStep = 0;
  let bestCount = -1;

  for (const offset of GAZE.scanOrientations) {
    const wanted = stepsFor(offset);
    await turnSteps(embodiment, wanted - current);
    current = wanted;

    const count = perceptibleCount(embodiment);
    // Strictly greater, so the earliest orientation in the sweep wins a tie
    // and the survey is deterministic.
    if (count > bestCount) {
      bestCount = count;
      bestStep = current;
    }
  }

  await turnSteps(embodiment, bestStep - current);
  return {
    orientationsSampled: GAZE.scanOrientations.length,
    perceptsAtSettled: Math.max(0, bestCount),
    settledStep: bestStep,
  };
}
