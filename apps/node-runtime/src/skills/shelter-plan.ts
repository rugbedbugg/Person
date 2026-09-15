import type { Position } from "#config";

/**
 * The shelter is a sealed three by three by three shell around the home block.
 * Adapted from the Shroud runtime, which verified the same enclosure against a
 * live world.
 */
export function shelterPlan(home: Position): Position[] {
  const walls: Position[] = [];
  const roof: Position[] = [];
  for (let dx = -1; dx <= 1; dx++)
    for (let dz = -1; dz <= 1; dz++) {
      if (dx !== 0 || dz !== 0)
        for (let dy = 0; dy <= 1; dy++)
          walls.push({ x: home.x + dx, y: home.y + dy, z: home.z + dz });
      roof.push({ x: home.x + dx, y: home.y + 2, z: home.z + dz });
    }
  // The centre roof block attaches to an already placed outer roof block.
  roof.sort(
    (a, b) =>
      Number(a.x === home.x && a.z === home.z) -
      Number(b.x === home.x && b.z === home.z),
  );
  return [...walls, ...roof];
}

/** The two blocks that form the doorway, top first so it can be resealed. */
export function shelterEntrance(home: Position): Position[] {
  return [
    { x: home.x, y: home.y + 1, z: home.z - 1 },
    { x: home.x, y: home.y, z: home.z - 1 },
  ];
}
