import type { Position } from "#config";

/**
 * First-person vision.
 *
 * Person perceives from somewhere, facing something. Before this existed the
 * observation reported whatever the body's block search had turned up, which
 * meant Person could act on a tree behind its head or an ore seam through a
 * hill. That is not a perception model, it is a database query, and ADR 0002
 * rule 6 exists because the difference decides whether Person can be
 * surprised.
 *
 * The model is deliberately the smallest Minecraft-native one that preserves
 * the causal boundary: an eye position, a view direction, a bounded range, a
 * field of view, and an opaque-block line of sight test. There is no
 * screenshot, no renderer and no learned recognition. Sub-block shapes are
 * ignored, so a fence or a half slab occludes exactly as a full cube does.
 *
 * Nothing here is a safety boundary. The safety kernel, the permission gate
 * and the physical guard all keep reading the unshaped snapshot, so a hazard
 * Person cannot see is still a hazard the runtime will act on.
 */

export const VISION = {
  /** How far Person can make anything out at all, in blocks. */
  range: 32,
  /**
   * Total horizontal field of view, in degrees.
   *
   * Human peripheral vision spans roughly 200 degrees horizontally and 130
   * vertically. These are those figures rather than a camera frustum: a
   * narrower cone made Person blind to things a standing person would plainly
   * be aware of, which is a different error from the one the firewall exists
   * to prevent. Anything behind Person is still outside both fields.
   */
  horizontalFovDegrees: 200,
  /** Total vertical field of view, in degrees. */
  verticalFovDegrees: 130,
  /** Eye height above the feet block. Minecraft's standing player eye height. */
  eyeHeight: 1.62,
  /** Spacing of the samples taken along a line of sight, in blocks. */
  occlusionStep: 0.5,
  /**
   * How many candidates of one kind may be ray-tested per observation.
   *
   * Range and field of view are cheap and are applied first; the line of sight
   * test is the expensive part, so only the nearest survivors reach it. This
   * is what keeps perception a bounded cost rather than one that grows with
   * how much world the body happens to have loaded.
   */
  maxRayTests: 48,
} as const;

export interface EyePose {
  /** Eye position in world space, not the feet block. */
  eye: { x: number; y: number; z: number };
  /** Unit view direction. */
  look: { x: number; y: number; z: number };
}

const RADIANS = Math.PI / 180;

/**
 * Mineflayer's view-direction convention, from its own ray tracer:
 * `(-sin(yaw)cos(pitch), sin(pitch), -cos(yaw)cos(pitch))`.
 */
export function lookVector(
  yaw: number,
  pitch: number,
): { x: number; y: number; z: number } {
  const cosPitch = Math.cos(pitch);
  return {
    x: -Math.sin(yaw) * cosPitch,
    y: Math.sin(pitch),
    z: -Math.cos(yaw) * cosPitch,
  };
}

/** The eye pose implied by a privileged snapshot. */
export function eyePose(snapshot: {
  position: Position;
  yaw: number;
  pitch: number;
}): EyePose {
  return {
    eye: {
      x: snapshot.position.x + 0.5,
      y: snapshot.position.y + VISION.eyeHeight,
      z: snapshot.position.z + 0.5,
    },
    look: lookVector(snapshot.yaw, snapshot.pitch),
  };
}

/** The point vision aims at for a block or entity occupying `position`. */
export const centreOf = (
  position: Position,
): {
  x: number;
  y: number;
  z: number;
} => ({ x: position.x + 0.5, y: position.y + 0.5, z: position.z + 0.5 });

const sameBlock = (
  a: { x: number; y: number; z: number },
  b: Position,
): boolean =>
  Math.floor(a.x) === b.x && Math.floor(a.y) === b.y && Math.floor(a.z) === b.z;

/**
 * Horizontal and vertical offsets from the view axis, in degrees.
 *
 * Split rather than a single cone angle because human vision is wider than it
 * is tall, and because "just out of view above" and "just out of view to the
 * side" are different enough to be worth modelling separately.
 */
export function viewAngles(
  pose: EyePose,
  target: { x: number; y: number; z: number },
): { horizontal: number; vertical: number } {
  const dx = target.x - pose.eye.x;
  const dy = target.y - pose.eye.y;
  const dz = target.z - pose.eye.z;

  const lookFlat = Math.hypot(pose.look.x, pose.look.z);
  const targetFlat = Math.hypot(dx, dz);
  let horizontal = 0;
  if (lookFlat > 0 && targetFlat > 0) {
    const cosine =
      (pose.look.x * dx + pose.look.z * dz) / (lookFlat * targetFlat);
    horizontal = Math.acos(Math.min(1, Math.max(-1, cosine))) / RADIANS;
  }

  const lookPitch = Math.atan2(pose.look.y, lookFlat) / RADIANS;
  const targetPitch = Math.atan2(dy, targetFlat) / RADIANS;
  return { horizontal, vertical: Math.abs(targetPitch - lookPitch) };
}

/** True when the target falls inside the field of view. */
export function inFieldOfView(
  pose: EyePose,
  target: { x: number; y: number; z: number },
): boolean {
  const angles = viewAngles(pose, target);
  return (
    angles.horizontal <= VISION.horizontalFovDegrees / 2 &&
    angles.vertical <= VISION.verticalFovDegrees / 2
  );
}

/**
 * True when an opaque block stands between the eye and the target.
 *
 * Marches the segment and stops at the first solid sample. The target's own
 * block never counts against it, or no block would ever be visible, and
 * neither does the block the eye sits in.
 */
export function occluded(
  pose: EyePose,
  target: Position,
  blockAt: (position: Position) => { solid: boolean } | null,
): boolean {
  const centre = centreOf(target);
  const dx = centre.x - pose.eye.x;
  const dy = centre.y - pose.eye.y;
  const dz = centre.z - pose.eye.z;
  const span = Math.hypot(dx, dy, dz);
  if (span <= VISION.occlusionStep) return false;

  const steps = Math.floor(span / VISION.occlusionStep);
  for (let step = 1; step < steps; step++) {
    const along = (step * VISION.occlusionStep) / span;
    const sample = {
      x: pose.eye.x + dx * along,
      y: pose.eye.y + dy * along,
      z: pose.eye.z + dz * along,
    };
    if (sameBlock(sample, target)) continue;
    const block = {
      x: Math.floor(sample.x),
      y: Math.floor(sample.y),
      z: Math.floor(sample.z),
    };
    if (
      block.x === Math.floor(pose.eye.x) &&
      block.y === Math.floor(pose.eye.y) &&
      block.z === Math.floor(pose.eye.z)
    )
      continue;
    if (blockAt(block)?.solid === true) return true;
  }
  return false;
}

/** True when the target is in range, in view, and not occluded. */
export function canSee(
  pose: EyePose,
  target: Position,
  blockAt: (position: Position) => { solid: boolean } | null,
  range = VISION.range,
): boolean {
  const centre = centreOf(target);
  const span = Math.hypot(
    centre.x - pose.eye.x,
    centre.y - pose.eye.y,
    centre.z - pose.eye.z,
  );
  if (span > range) return false;
  if (!inFieldOfView(pose, centre)) return false;
  return !occluded(pose, target, blockAt);
}

/**
 * Keeps the candidates Person can actually see.
 *
 * Order matters for cost: range and field of view are arithmetic, the line of
 * sight test walks the world, so the cheap filters run first and only the
 * nearest `maxRayTests` survivors are traced.
 */
export function visible<T>(
  candidates: readonly T[],
  positionOf: (candidate: T) => Position,
  pose: EyePose,
  blockAt: (position: Position) => { solid: boolean } | null,
  options: { limit: number; range?: number } = { limit: VISION.maxRayTests },
): T[] {
  const range = options.range ?? VISION.range;
  const reachable = candidates
    .map((candidate) => {
      const position = positionOf(candidate);
      const centre = centreOf(position);
      return {
        candidate,
        position,
        span: Math.hypot(
          centre.x - pose.eye.x,
          centre.y - pose.eye.y,
          centre.z - pose.eye.z,
        ),
        centre,
      };
    })
    .filter((entry) => entry.span <= range && inFieldOfView(pose, entry.centre))
    .sort((a, b) => a.span - b.span)
    .slice(0, VISION.maxRayTests);

  const seen: T[] = [];
  for (const entry of reachable) {
    if (seen.length >= options.limit) break;
    if (!occluded(pose, entry.position, blockAt)) seen.push(entry.candidate);
  }
  return seen;
}
