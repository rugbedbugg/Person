import type { Position } from "#config";
import {
  centreOf,
  inCentralVision,
  viewAngles,
  type EyePose,
} from "./vision.ts";

/**
 * Where something is, described the way a person would describe it.
 *
 * Cognition used to receive the world coordinate of everything it could see,
 * which is a fact about the server rather than a fact about Person's
 * experience. What replaces it is relative and qualitative: to my left, a
 * little above, about that far away. It is enough to choose between two
 * things, prefer the nearer one, or say where something was, and it is not
 * enough to reconstruct the map.
 *
 * Bearings are relative to where Person is facing, not to any compass. Person
 * has no compass, and a heading in degrees would be the coordinate problem
 * again in another notation.
 */

export type Bearing =
  | "ahead"
  | "ahead_left"
  | "ahead_right"
  | "left"
  | "right"
  | "behind_left"
  | "behind_right"
  | "behind";

export type Elevation = "above" | "level" | "below";

/** Coarse distance bands, named for what Person could do at that distance. */
export type RangeBand = "reach" | "near" | "mid" | "far";

export const RANGE_BANDS = {
  /** Close enough to touch, mine or hit. */
  reach: 4.5,
  /** A few steps away. */
  near: 12,
  /** Across a clearing. */
  mid: 24,
} as const;

/** Degrees off the view axis before something stops being straight ahead. */
const AHEAD = 20;
const SIDE = 70;
const BEHIND = 130;

/** Degrees above or below the view axis before elevation is worth reporting. */
const LEVEL = 15;

export function rangeBand(distance: number): RangeBand {
  if (distance <= RANGE_BANDS.reach) return "reach";
  if (distance <= RANGE_BANDS.near) return "near";
  if (distance <= RANGE_BANDS.mid) return "mid";
  return "far";
}

/**
 * Which side of the view axis the target sits on.
 *
 * The horizontal angle from `viewAngles` is unsigned, so the side is recovered
 * from the sign of the cross product of the view direction and the target
 * direction in the horizontal plane.
 */
function side(pose: EyePose, target: { x: number; z: number }): number {
  const dx = target.x - pose.eye.x;
  const dz = target.z - pose.eye.z;
  return Math.sign(pose.look.z * dx - pose.look.x * dz);
}

export function bearingOf(pose: EyePose, position: Position): Bearing {
  const centre = centreOf(position);
  const { horizontal } = viewAngles(pose, centre);
  if (horizontal <= AHEAD) return "ahead";
  const left = side(pose, centre) < 0;
  if (horizontal <= SIDE) return left ? "ahead_left" : "ahead_right";
  if (horizontal <= BEHIND) return left ? "left" : "right";
  if (horizontal < 180 - AHEAD) return left ? "behind_left" : "behind_right";
  return "behind";
}

export function elevationOf(pose: EyePose, position: Position): Elevation {
  const centre = centreOf(position);
  const flat = Math.hypot(centre.x - pose.eye.x, centre.z - pose.eye.z);
  const rise = centre.y - pose.eye.y;
  const degrees = (Math.atan2(rise, flat) * 180) / Math.PI;
  if (degrees > LEVEL) return "above";
  if (degrees < -LEVEL) return "below";
  return "level";
}

/**
 * How far away something looks, as an estimate rather than a measurement.
 *
 * Judging distance is an ordinary perceptual act and every decision cognition
 * makes about distance is a comparison, so a number is the useful shape. The
 * precision is not: a tenth of a block is a survey, not a glance. Estimates
 * get coarser with distance the way real ones do, which also means a far-off
 * thing is reported less precisely than a near one.
 *
 * The grid stays fine enough near Person for the thresholds cognition actually
 * uses, the closest of which is a hazard within 1.5 blocks.
 */
export function estimateDistance(distance: number): number {
  const step = distance <= 8 ? 0.5 : distance <= 16 ? 1 : 2;
  return Math.round(distance / step) * step;
}

/** Whether Person is looking at the thing or merely aware of it. */
export type Detail = "central" | "peripheral";

export interface RelativeLocation {
  bearing: Bearing;
  elevation: Elevation;
  rangeBand: RangeBand;
  /** Estimated straight-line distance. Coarser further away. */
  distance: number;
  /**
   * Whether this percept came from the part of the field Person can identify
   * things in. A peripheral percept carries position and coarse category and
   * withholds precise identity.
   */
  detail: Detail;
}

export function relativeTo(
  pose: EyePose,
  position: Position,
  distance: number,
): RelativeLocation {
  return {
    bearing: bearingOf(pose, position),
    elevation: elevationOf(pose, position),
    rangeBand: rangeBand(distance),
    distance: estimateDistance(distance),
    detail: inCentralVision(pose, centreOf(position))
      ? "central"
      : "peripheral",
  };
}
