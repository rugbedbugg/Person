# ADR 0019: Air-deprivation emergency response

**Status:** Accepted (2026-09-30)
**Date:** 2026-09-30
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Operator decision:** fix the suffocation response before E4, under a narrow
ADR, and validate it once live with a disposable validation identity
(2026-09-30). A known safety defect on the critical path to Person-000's
first session.

---

## Context

In the E3 live rehearsal the validation body drowned. At night a spider's
attack set off an L1 flee that left the body in water; air fell below the
threshold and the kernel's L0 `suffocation` emergency answered with `flee`
again. Flee moves away from hostiles and hazards at the same height. It never
goes up, so the body stayed under water and drowned. Nothing in the fixture
could show this, because no fixture world lowered air. The lifecycle stack
behaved correctly; the emergency policy mapped an air emergency onto a threat
response.

## Decision

1. **Air deprivation restores air.** When the kernel finds air below its
   threshold (L0 `suffocation`), the emergency action is `restore_air`, never
   `flee`. The kernel's order of emergencies is unchanged, so an air emergency
   still outranks a hostile nearby.
2. **`restore_air` is an emergency motor response.** It is not a goal,
   project, preference or plannable skill: like every emergency skill it is
   excluded from planning, runs only when the kernel substitutes it, and
   teaches nothing.
3. **Simple and bounded.** Air is restored by the nearest locally reachable
   breathable space: straight up where the column above is open, otherwise a
   nearby open column. At most three attempts within the skill's tick budget.
   If no breathable space is within reach, the skill fails with
   `no_reachable_air`. It never digs, and it is not a general fluid planner.
4. **Trusted geometry stays trusted.** The motor layer reads local blocks to
   find air, as other trusted motor behaviour does. None of it reaches
   cognition: Person keeps the bounded signals it already has (breath and the
   emergency's trigger and response) and receives no coordinates, water
   topology or pathfinder state.
5. **No lingering state.** The response is a skill run, checked at every
   step; a death, a respawn or a lost world ends it like any other skill, and
   the kernel reassesses the new body from its own snapshot.
6. **Ordinary flee keeps its meaning.** Hostile avoidance and lava and fire
   exposure are untouched.
7. **A body primitive to go up.** The port gains an optional `ascend`, a
   bounded upward swim that stops when the head is in breathable space, the
   budget is spent, or the body dies or is disconnected. Mineflayer holds
   jump; the fixture rises one swimmable cell at a time. The fixture now also
   loses air while its head is in water, and can swim while submerged; land
   paths are unchanged.

## Implementation status

TESTED IN FIXTURE and CONFORMANCE-TESTED; one targeted live validation with a
validation identity is required before E4.

## Consequences

### Positive

- A submerged Person goes for air instead of fleeing sideways under water.
- The fixture can now show air loss, so breath and its emergency are no
  longer exercised only by unit tests.

### Negative

- One more emergency skill and port method to keep in step across bodies.
- The skill library revision changes.

## Alternatives considered

| Alternative                           | Why not                                                         |
| ------------------------------------- | --------------------------------------------------------------- |
| Keep `flee` and add "prefer up" to it | Changes what hostile avoidance means                            |
| A general fluid-navigation planner    | Far beyond the defect; the surface is almost always straight up |
| Dig up through a blocked ceiling      | Hidden excavation the emergency permissions do not grant        |
| Tell cognition where the air is       | Privileged geometry across the perception firewall (ADR 0002)   |

## Revisit conditions

- Live evidence of drowning with an open surface in reach.
- Lava, flowing water or bubble columns making "up" the wrong answer.
- Any change to emergency-dig permissions.

## Relevant commits and docs

- E3 rehearsal: `docs/evidence/dedicated-server/2026-09-30-e3-rehearsal/`
- `apps/node-runtime/src/safety/safety-kernel.ts`
- `apps/node-runtime/src/skills/impl/emergency.ts`
- `packages/skills/specs/restore_air.json`
