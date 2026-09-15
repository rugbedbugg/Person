import type { Box, Position } from "./types.ts";

export const contains = (box: Box, p: Position): boolean =>
  p.x >= box.min.x &&
  p.x <= box.max.x &&
  p.y >= box.min.y &&
  p.y <= box.max.y &&
  p.z >= box.min.z &&
  p.z <= box.max.z;

export const intersects = (a: Box, b: Box): boolean =>
  a.min.x <= b.max.x &&
  b.min.x <= a.max.x &&
  a.min.y <= b.max.y &&
  b.min.y <= a.max.y &&
  a.min.z <= b.max.z &&
  b.min.z <= a.max.z;

export const distance = (a: Position, b: Position): number =>
  Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);

export const positionKey = (p: Position): string => `${p.x},${p.y},${p.z}`;

/** Every block the segment between two block positions passes through, inclusive. */
export function blockLine(from: Position, to: Position): Position[] {
  const steps = Math.max(
    Math.abs(to.x - from.x),
    Math.abs(to.y - from.y),
    Math.abs(to.z - from.z),
  );
  if (steps === 0) return [{ ...from }];
  const line: Position[] = [];
  for (let step = 0; step <= steps; step++) {
    const t = step / steps;
    line.push({
      x: Math.round(from.x + (to.x - from.x) * t),
      y: Math.round(from.y + (to.y - from.y) * t),
      z: Math.round(from.z + (to.z - from.z) * t),
    });
  }
  return line;
}
