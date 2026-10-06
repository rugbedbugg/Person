import { type Position } from "#minecraft";

/**
 * True when a solid block stands between a point and a target block.
 *
 * Pure geometry: it knows nothing of who is looking, where they face, or what
 * they can recognise. Person's vision uses it for occlusion, and the fixture
 * uses it for whether a hostile has a line of attack, so there is one
 * definition of a clear line. It marches the segment from `from` to the
 * target block's centre and stops at the first solid sample; the target's own
 * block never counts against it, and neither does the block `from` sits in.
 */
export function lineBlocked(
  from: { x: number; y: number; z: number },
  target: Position,
  blockAt: (position: Position) => { solid: boolean } | null,
  step = 0.5,
): boolean {
  const centre = { x: target.x + 0.5, y: target.y + 0.5, z: target.z + 0.5 };
  const dx = centre.x - from.x;
  const dy = centre.y - from.y;
  const dz = centre.z - from.z;
  const span = Math.hypot(dx, dy, dz);
  if (span <= step) return false;

  const origin = {
    x: Math.floor(from.x),
    y: Math.floor(from.y),
    z: Math.floor(from.z),
  };
  const steps = Math.floor(span / step);
  for (let index = 1; index < steps; index++) {
    const along = (index * step) / span;
    const block = {
      x: Math.floor(from.x + dx * along),
      y: Math.floor(from.y + dy * along),
      z: Math.floor(from.z + dz * along),
    };
    if (block.x === target.x && block.y === target.y && block.z === target.z)
      continue;
    if (block.x === origin.x && block.y === origin.y && block.z === origin.z)
      continue;
    if (blockAt(block)?.solid === true) return true;
  }
  return false;
}
