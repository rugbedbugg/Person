import type { Position } from "#config";
import type { WorldSnapshot } from "../embodiment/types.ts";
import { estimateDistance, type Bearing } from "./relative.ts";

/**
 * Person's sense of its own motion (ADR 0008).
 *
 * A body feels that it moved, roughly how far and roughly which way, and that
 * it turned. It does not feel where it is. This module turns two exact poses,
 * which only the runtime has, into that feeling and nothing more: a direction
 * in eight equal sectors, a distance band, a rotation rounded to the nearest
 * eighth of a turn, and whether it went up or down. Integrating a sequence of
 * these drifts, which is the point.
 *
 * The reference frame is fixed and explicit. Translation is the horizontal
 * displacement of Person's feet between the previous observation and this
 * one, expressed relative to the facing Person had at the previous one.
 * Rotation is the change in facing between the two. Directions use the
 * percept bearing words and the same left/right convention as `stepGaze`:
 * facing negative Z, left is negative X, and turning left increases yaw.
 */

export type TranslationBand = "none" | "tiny" | "short" | "moderate" | "far";

export type Rotation =
  | "none"
  | "slight_left"
  | "left"
  | "sharp_left"
  | "about_face"
  | "sharp_right"
  | "right"
  | "slight_right";

export interface SelfMotion {
  /**
   * `start`: the first observation of a session, with nothing to compare.
   * `continuous`: ordinary felt motion. `discontinuous`: the scene jumped in
   * a way no locomotion explains, and how far is not known.
   */
  continuity: "start" | "continuous" | "discontinuous";
  translation: {
    direction: Bearing | "none" | "unknown";
    band: TranslationBand | "unknown";
    /** A felt estimate on the percept distance grid; null when unknown. */
    distance: number | null;
  };
  rotation: Rotation | "unknown";
  vertical: "level" | "up" | "down" | "unknown";
}

/** The exact pose this sense is derived from. Privileged; never reported. */
export interface BodyPose {
  position: Position;
  yaw: number;
  tick: number;
  dimension: WorldSnapshot["dimension"];
  alive: boolean;
}

/** Band edges, in blocks of horizontal travel. Implementation parameters. */
export const TRANSLATION_BANDS = {
  none: 0.5,
  tiny: 2,
  short: 8,
  moderate: 24,
} as const;

/** Blocks of rise or fall before it is felt. */
const VERTICAL = 1.5;

/**
 * The most horizontal distance locomotion can explain per elapsed tick, plus
 * a margin. Sprint-jumping is well under half a block a tick; anything beyond
 * this was not walked, whatever it was.
 */
const MAX_BLOCKS_PER_TICK = 1;
const MAX_UNEXPLAINED = 16;

const SECTOR = Math.PI / 4;

/** Sector index, counted anticlockwise (towards the left) from ahead. */
const SECTOR_BEARINGS: readonly Bearing[] = [
  "ahead",
  "ahead_left",
  "left",
  "behind_left",
  "behind",
  "behind_right",
  "right",
  "ahead_right",
];

const ROTATIONS: Readonly<Record<number, Rotation>> = {
  0: "none",
  1: "slight_left",
  2: "left",
  3: "sharp_left",
  4: "about_face",
  [-4]: "about_face",
  [-3]: "sharp_right",
  [-2]: "right",
  [-1]: "slight_right",
};

export function poseOf(snapshot: WorldSnapshot): BodyPose {
  return {
    position: { ...snapshot.position },
    yaw: snapshot.yaw,
    tick: snapshot.tick,
    dimension: snapshot.dimension,
    alive: snapshot.alive,
  };
}

function band(distance: number): TranslationBand {
  if (distance < TRANSLATION_BANDS.none) return "none";
  if (distance < TRANSLATION_BANDS.tiny) return "tiny";
  if (distance < TRANSLATION_BANDS.short) return "short";
  if (distance < TRANSLATION_BANDS.moderate) return "moderate";
  return "far";
}

/** An angle folded into (-pi, pi]. */
function fold(angle: number): number {
  const turned = angle % (2 * Math.PI);
  if (turned > Math.PI) return turned - 2 * Math.PI;
  if (turned <= -Math.PI) return turned + 2 * Math.PI;
  return turned;
}

/** Eighths of a turn, rounded, positive to the left. */
function eighths(angle: number): number {
  const steps = Math.round(fold(angle) / SECTOR);
  return steps === -4 ? 4 : steps;
}

const UNKNOWN: SelfMotion["translation"] = {
  direction: "unknown",
  band: "unknown",
  distance: null,
};

/** What moving from `previous` to `current` felt like. */
export function selfMotion(
  previous: BodyPose | null,
  current: BodyPose,
): SelfMotion {
  if (previous === null)
    return {
      continuity: "start",
      translation: UNKNOWN,
      rotation: "unknown",
      vertical: "unknown",
    };

  const dx = current.position.x - previous.position.x;
  const dz = current.position.z - previous.position.z;
  const dy = current.position.y - previous.position.y;
  const travelled = Math.hypot(dx, dz);
  const elapsed = Math.max(0, current.tick - previous.tick);
  const jumped =
    current.dimension !== previous.dimension ||
    (current.alive && !previous.alive) ||
    travelled > MAX_BLOCKS_PER_TICK * elapsed + MAX_UNEXPLAINED;
  if (jumped)
    return {
      continuity: "discontinuous",
      translation: UNKNOWN,
      rotation: "unknown",
      vertical: "unknown",
    };

  // Displacement in the frame of the previous facing: ahead and to the left.
  const ahead = -Math.sin(previous.yaw) * dx - Math.cos(previous.yaw) * dz;
  const leftward = -Math.cos(previous.yaw) * dx + Math.sin(previous.yaw) * dz;
  const felt = band(travelled);
  const sector = ((eighths(Math.atan2(leftward, ahead)) % 8) + 8) % 8;

  return {
    continuity: "continuous",
    translation: {
      direction: felt === "none" ? "none" : SECTOR_BEARINGS[sector]!,
      band: felt,
      distance: felt === "none" ? 0 : estimateDistance(travelled),
    },
    rotation: ROTATIONS[eighths(current.yaw - previous.yaw)]!,
    vertical: dy >= VERTICAL ? "up" : dy <= -VERTICAL ? "down" : "level",
  };
}

/**
 * The sense itself: remembers the last pose it reported from, per session.
 *
 * One instance lives as long as one runtime session. A new session starts
 * with nothing to compare, which is exactly what a restart feels like.
 */
export class SelfMotionSense {
  #previous: BodyPose | null = null;

  sense(snapshot: WorldSnapshot): SelfMotion {
    const current = poseOf(snapshot);
    const felt = selfMotion(this.#previous, current);
    this.#previous = current;
    return felt;
  }
}
