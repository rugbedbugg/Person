# ADR 0002: The perception firewall

**Status:** Accepted (rule), Deferred (sense model)
**Date:** 2026-09-22
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder

---

## Context

The runtime holds a complete `WorldSnapshot`. A future Baritone motor layer will
hold considerably more: the exact geometry of every loaded chunk, which is what
makes it good at moving.

There is no technical obstacle to handing all of that to cognition, and several
convenient reasons to do it. A planner with perfect world knowledge plans
better. A debugging session is easier when the agent can see everything. Each
individual widening is small.

The result of enough small widenings is an agent that cannot fail to notice
anything, cannot be surprised, cannot form a wrong belief about where something
is, and therefore cannot demonstrate any of the epistemic behaviour
`docs/PERSON_SPEC.md` section 0.3 requires.

The first live observation already produced the concrete version of this
problem in the opposite direction: a nearest-64 search standing on stone
returned 55 stone and 9 coal, and every tree in the valley was invisible to
cognition. The fix was to shape perception rather than truncate it. That fix is
the firewall's first real implementation, and it was written for informativeness
rather than for boundedness.

## Decision

A perception firewall separates what the body knows from what Person perceives.

```text
Minecraft client state  /  motor backend      exact geometry permitted here
        |
        v
   perception filter                          the firewall
        |
        v
   bounded Person perception
```

The rules:

1. **Nothing crosses by default.** A field reaches cognition because the
   observation builder was changed to put it there, deliberately, and never
   because a body started reporting it.
2. **The firewall is not a safety boundary and must never be used as one.** The
   safety kernel, the permission gate and the physical guard all read the
   unshaped snapshot. Dropping an animal from the observation cannot make it
   huntable; keeping one cannot make it a legal target. This rule is already
   written into `apps/node-runtime/src/observation/perception.ts` and is
   restated here because it is the rule most likely to be violated by accident.
3. **Shaping is deterministic.** The same snapshot produces the same
   observation, with explicit tie-breaks, so an observation is reproducible
   evidence rather than a function of chunk scan order.
4. **Capability axes are independent.** Raising Person's reasoning, planning
   depth or mechanical expertise must not widen perception. A Super-Person
   experiment that wants more perception says so and raises that axis by name.
5. **Privileged state has a separate path.** Operator and debug tooling may
   expose anything. `person status` is the existing example: the runtime writes
   it, the operator reads it, and an architecture test asserts that nothing on
   the decision path or in cognition can read it back.
6. **The eventual filter is a human-like sense model**, not a larger budget:
   camera pose, bounded range, occlusion, semantic aggregation, near/medium/far,
   relative direction, entity visibility.

Rule 6 is deferred. Rules 1 to 5 are in force now.

## Consequences

### Positive

- Person can be surprised, which is a prerequisite for hypothesis formation,
  prediction error that means anything, and discovery.
- A motor backend can be as omniscient as it likes without that omniscience
  becoming a cognitive capability.
- Perception cost stays bounded regardless of how much the body knows.

### Negative

- Person will sometimes plan badly because it did not see something that was
  there. That is intended, and it will repeatedly look like a bug.
- Every future cognitive subsystem that wants a new field has to justify it.
- The eventual visibility model costs CPU that a flat chunk dump would not.

### Neutral

- Observation shaping already exists and already has tests. This ADR mostly
  names what those tests are defending.

## Alternatives Considered

| Alternative                             | Why rejected                                                                                                                  |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Give cognition the full snapshot        | Removes the possibility of Person being wrong about the world, which removes most of the research question.                   |
| Filter at the cognition end             | Puts the boundary on the untrusted side of it. Whatever cognition can read, cognition can use.                                |
| Make the firewall a safety boundary too | Couples two independent concerns, and creates a path where a perception tweak silently changes what Person may physically do. |
| Defer the whole question until Baritone | The widening happens during the Baritone work, not after it.                                                                  |

## Revisit Conditions

- A cognitive subsystem needs a field the firewall does not pass and cannot be
  built without it. Widen deliberately, in an ADR, naming the axis.
- Measurement shows the sense model dominates per-tick cost.

## Relevant Commits / Documents

| Reference                                         | Description                                         |
| ------------------------------------------------- | --------------------------------------------------- |
| `docs/PERSON_SPEC.md` sections 0.3, 0.4, 0.20     | Epistemic separation, the firewall, capability axes |
| `docs/PERSON_SPEC.md` section 0.24, C1            | Coordinates currently cross the firewall            |
| `apps/node-runtime/src/observation/perception.ts` | The firewall's current implementation               |
| `REALITY_VALIDATION.md`, first contact, finding 3 | Why shaping exists                                  |
| `2d7f9d2`                                         | Perception balance commit                           |

## Implementation Notes

The open question is contradiction C1: the observation carries exact
coordinates for Person's own position and for every nearby thing. Cognition
never reads them today, which was established by inspection rather than
assumed, and cannot send one back because `SkillInvocation` is scalar-only.

Resolving C1 means one of:

- removing the coordinate fields and giving cognition a deliberate "check where
  I am" capability, per `docs/PERSON_SPEC.md` section 0.6; or
- keeping them and adding an architecture test that asserts cognition does not
  read them, which makes the current accident into a checked rule.

The second is cheap and honest and does not decide the first. Neither is done.
