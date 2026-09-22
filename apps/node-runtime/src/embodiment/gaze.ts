/**
 * Gaze: Person pointing its senses, rather than happening to face something.
 *
 * Phase 3 gave Person a bounded field of view and no way to aim it, so what it
 * could discover was decided by where it spawned and by wherever walking left
 * it pointing. This is the smallest fix that keeps the boundary intact.
 *
 * Cognition asks in words: look left, look up, survey what is around. The
 * trusted runtime decides the angles. An absolute heading is motor state and
 * stays on this side of the firewall, so no gaze request and no gaze result
 * ever carries a number of degrees.
 */

/**
 * The whole vocabulary Person has for pointing its eyes.
 *
 * Deliberately semantic and deliberately small. There is no `look_at(x, y, z)`
 * and no `face(entity)`: both would be a coordinate channel wearing a verb,
 * and percepts have no durable identity to refer to yet (C4).
 */
export type GazeDirection = "forward" | "left" | "right" | "up" | "down";

export const GAZE_DIRECTIONS: readonly GazeDirection[] = [
  "forward",
  "left",
  "right",
  "up",
  "down",
];

export const GAZE = {
  /** How far one deliberate turn of the head moves the view, in degrees. */
  yawStepDegrees: 45,
  pitchStepDegrees: 30,
  /** Necks do not bend all the way back. */
  maxPitchDegrees: 60,
  /**
   * The sweep a survey performs, as yaw offsets in degrees from where Person
   * was already facing. Negative is to Person's right.
   *
   * Five fixed orientations, so a survey is a finite, predictable amount of
   * work rather than a spin. It deliberately does not cover the full circle:
   * a survey is a look around, not a free omniscient snapshot, and what falls
   * behind Person during one stays unseen.
   */
  scanOrientations: [0, -45, -90, 45, 90] as readonly number[],
} as const;

const RADIANS = Math.PI / 180;

/** Clamps pitch to what a neck allows. */
export const clampPitch = (pitch: number): number => {
  const limit = GAZE.maxPitchDegrees * RADIANS;
  return Math.max(-limit, Math.min(limit, pitch));
};

/**
 * The yaw and pitch one gaze step in a direction produces.
 *
 * Facing negative Z, Person's right hand points towards positive X. The view
 * direction is `(-sin(yaw), sin(pitch), -cos(yaw))`, so turning right means
 * decreasing yaw, and `forward` levels the head without changing which way
 * Person is facing.
 */
export function stepGaze(
  from: { yaw: number; pitch: number },
  direction: GazeDirection,
): { yaw: number; pitch: number } {
  const yawStep = GAZE.yawStepDegrees * RADIANS;
  const pitchStep = GAZE.pitchStepDegrees * RADIANS;
  switch (direction) {
    case "left":
      return { yaw: from.yaw + yawStep, pitch: from.pitch };
    case "right":
      return { yaw: from.yaw - yawStep, pitch: from.pitch };
    case "up":
      return { yaw: from.yaw, pitch: clampPitch(from.pitch + pitchStep) };
    case "down":
      return { yaw: from.yaw, pitch: clampPitch(from.pitch - pitchStep) };
    case "forward":
      return { yaw: from.yaw, pitch: 0 };
  }
}
