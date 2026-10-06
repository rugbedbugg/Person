# ADR 0009: Projects as persistent cognitive commitments

**Status:** Accepted (operator, 2026-09-25)
**Date:** 2026-09-25
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder

---

> **Operator decision, 2026-09-25: accepted.** The accepted architecture is a
> project as a persistent, interruptible, resumable, restart-persistent,
> bounded cognitive commitment anchored in Person's own cognitive state. The
> current policy is not canonical: the project kinds, the fixed ordering,
> priority 300, the open-project limit, the blocked-twice rule, the one-day
> retry delay and the calm thresholds are implementation parameters to be
> calibrated.

## Context

Until now Person had needs and goals but no commitments. Homeostasis produced
urgency, the survival provider turned it into goals, and the goal stack
suspended and resumed them, but nothing Person decided to do outlived the goal
of the moment or a restart. `PERSON_SPEC` sections 18 and 59 ask for projects
with purpose, milestones, progress, suspension and resumption, spanning
sessions. Adding a new kind of state that survives a restart needs an ADR
(`docs/decisions/README.md`).

## Decision

1. **A project is cognitive state.** It has an identity (`project_N`), a
   kind, a purpose, milestones, a status (`ACTIVE`, `SUSPENDED`, `COMPLETE`,
   `ABANDONED`), the reasons it was taken up, the interruptions it suffered,
   the blocks it met, and an anchor: a place in Person's own map (ADR 0008).
   It holds no coordinate, heading or runtime target.
2. **Needs press; cognition chooses.** Drives stay homeostatic urgency. A
   project is taken up only when the pressing needs (health, food, safety)
   are calm, it is day, and Person believes it has a home. Templates are
   tried in a fixed order and the first that the world does not already
   satisfy is taken. This is satisficing, not optimisation.
3. **Bounded pursuit.** At most two projects are open, and only the oldest
   pursues a milestone. Its next unmet milestone becomes a goal of an
   existing goal type with source `self_generated`, at a fixed priority
   below urgent needs. The goal stack decides the rest: a more urgent need
   suspends the project's goal, and the project records the interruption; it
   resumes when the need passes.
4. **Giving up and closing.** A milestone blocked repeatedly makes the
   project impossible, and it is abandoned; its kind is not taken up again
   for a while. A project whose milestones the world already satisfies is
   closed, not resumed.
5. **Persistence through Person's records.** Projects are journalled as
   `project_started` and `project_changed` (journal schema v6) and rebuilt
   from those alone. After a restart each open project is re-examined before
   it is pursued: closed if already done, held if Person cannot place its
   home, otherwise resumed. Re-examination may use bounded, cued recall of
   how that kind of work went (ADR 0007), and never reads the journal.
6. **Two kinds to start (a parameter, not a boundary).** `improve_home` (shelter, then storage, anchored to
   home) and `secure_food_supply` (cooked food in hand). More kinds are added
   when the capabilities they need exist, not to fill a list.

Priorities, limits, the calm threshold, the block count and the cooldown are
current implementation parameters.

## Consequences

### Positive

- Person can be in the middle of something, be interrupted, and come back to
  it, including across a restart, and every step is in the journal with its
  reason.
- Projects anchor to Person's own home, so they inherit the spatial firewall.

### Negative

- A project's milestone and a survival goal can ask for the same thing; both
  complete together, and the project's is the one pursued.
- Project selection is a fixed order. Person does not yet weigh projects
  against each other, learn which are worth taking up, or invent new kinds.

### Neutral

- Journal schema v6. No protocol change: project goals use existing goal
  types and the existing `self_generated` source.

## Alternatives Considered

| Alternative                             | Why rejected                                                                  |
| --------------------------------------- | ----------------------------------------------------------------------------- |
| New goal types per project              | A protocol change for what the goal stack already expresses.                  |
| A utility score over all projects       | Opaque and optimising; the spec asks for inspectable, bounded choice.         |
| Persist the goal stack instead          | Goals are momentary; a commitment is the thing that should persist.           |
| Resume every project blindly on restart | The world may have moved on. Re-examining first is cheap and honest.          |
| Exploration as a first project          | Needs a skill that chooses where to go from Person's map, which is not built. |

## Revisit Conditions

- Affect or preferences are built and should bias which project to take up.
- Learning should decide which projects are worth their cost.
- Construction or exploration skills that take a cognitive place as a target.

## Relevant Commits / Documents

| Reference                                            | Description                             |
| ---------------------------------------------------- | --------------------------------------- |
| `docs/PERSON_SPEC.md` sections 15-18, 55, 59         | Goals, the stack, homeostasis, projects |
| ADR 0007, ADR 0008                                   | The memory and places projects rely on  |
| `apps/cognition/python/person_cognition/projects.py` | The implementation                      |
