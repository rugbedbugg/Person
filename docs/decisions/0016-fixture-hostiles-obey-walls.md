# ADR 0016: Fixture hostiles obey walls

**Status:** Accepted (2026-09-30)
**Date:** 2026-09-30
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Operator decision:** fix the fixture's hostile line of fire before the V2
held-out suite is consumed; defer any kernel "stand fast in shelter" change
(2026-09-30). The reviewer widened the scope to movement and melee, because
line of fire alone would not remove the artifact.

---

## Context

The fixture world moved each hostile one block toward Person every 6 ticks
with no block check, and let any hostile within reach (12 blocks ranged, 2.5
melee) hurt Person with no line check. So hostiles walked into sealed
shelters, skeletons shot through walls, and zombies hit through them. In the
held-out D regression rerun, a sheltered Person lost 12 health this way. D2,
the frozen replacement for held-out D, spawns a skeleton six blocks away, so
its health, threat and recovery results would partly measure the artifact.
Held-out results cannot be rerun, so the fixture is fixed first.

## Decision

1. **Movement:** a hostile's step is taken only into open space, meaning its
   feet block and the block above are not solid. It tries the diagonal step,
   then the x step alone, then the z step alone, and otherwise stays. There is
   no pathfinding, jumping, door opening, digging or shelter awareness.
2. **Attack:** every hostile attack, ranged or melee, needs a clear line from
   the attacker's eye to Person's upper body.
3. **One definition of a clear line:** `lineBlocked`
   (`apps/node-runtime/src/embodiment/geometry.ts`) is pure geometry, with no
   field of view, range or recognition. Person's vision uses it for occlusion,
   and the fixture uses it for attacks. Hostile physics never depends on
   whether Person perceives the attacker.
4. **Unchanged:** movement cadence and speed, reach, attack cadence, damage,
   spawning, the kernel's threat distances, the flee policy, skills,
   cognition, R2's parameters and the held-out worlds.
5. **Operator-side diagnostics:** when `PERSON_FIXTURE_PHYSICS_LOG` names a
   file, the fixture appends each refused step or attack there. Off by
   default, and never part of anything Person receives.

## Consequences

- A sheltered Person is no longer hurt through walls, and a hostile outside a
  sealed shelter stays outside.
- The kernel still rates threats by distance alone, so a sheltered Person
  with a hostile within contact range is still ordered to flee, and flee
  still fails. That is the deferred stand-fast question.
- With no pathfinding, a hostile lined up directly behind a single block on
  Person's axis cannot get around it. Recorded by a test, not a goal.
- In class D, an encounter can now pass without Person perceiving or feeling
  anything, if Person is sheltered when the hostile arrives. D's threat and
  setback measures may then be untested; that is a result about the world,
  not something to tune away.
- The R1.5 references gain a third generation,
  `fixtures/regression/r15-affect-fixture-realism/`. Its bridge from the
  previous one is pinned: B and C identical, and D split exactly at the first
  physics event.

## Alternatives considered

| Alternative                             | Why not                                                                                                          |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Ranged line of fire only                | Hostiles would still walk into the shelter and attack from inside.                                               |
| Pathfinding hostiles                    | A new behaviour model, beyond correcting physics; a separate decision.                                           |
| Reuse `occluded` from vision directly   | It lives in vision and takes its step from `VISION`: privileged physics must not depend on perception semantics. |
| Make the kernel stand fast in a shelter | A safety-model change the operator deferred.                                                                     |

## Verification

`tests/fixture/hostile-physics.test.ts`:

- wall on and off for a skeleton;
- melee through a one-block wall;
- open-field attacks still land;
- feet and head clearance;
- the x-only and z-only fallbacks;
- a sealed enclosure holding indefinitely;
- the diagonal detour and the axis-aligned limit;
- nothing new in the observation;
- the primitive's geometry.

Removing either rule fails several of these. The R1.5 bridge is in
`tests/integration/r15-reference.test.ts`.
