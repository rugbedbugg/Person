# ADR 0017: Identity, continuity and operational lifetime

**Status:** Proposed
**Date:** 2026-09-30
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Operator decision:** start the Person-000 identity and continuity phase
(2026-09-30). Scope and design reviewed before implementation; this ADR goes
to the operator before it is Accepted, and before the canonical Person-000
continuity root is created.

---

## Context

Person's defining property is continuity: a past, a present situation, and
intentions for the future (PERSON_SPEC section 1). Until now identity was one
string, `personId = "ada"`, carried on every message and event. Nothing
recorded when a Person began, nothing tied an evidence directory to one
Person, and nothing marked where one process's life ended and the next began.
ADR 0006 has experienced time; external time is recorded on every event and
never compared, and none of its operational states or death semantics exist.

The historical `"ada"` journals are benchmark runs, development worlds and
spot-checks. They were never one continuous individual.

## Decision

### Identity

1. **Person-000 is the immutable identity; Ada is her name.** The canonical
   identity is `personId = "person-000"`, designation `Person-000`, name
   `Ada`. Later Persons are `person-001` and onward.
2. **`"ada"` is a legacy prototype identifier.** Historical `"ada"` evidence
   stays historical. It is never rewritten, and never silently converted into
   Person-000's autobiography. Person-000 begins from a fresh continuity root.
3. **Founding is the first event.** A new continuity root begins with
   `person_founded` (personId, name, designation, founding external time,
   founding experienced tick 0, identity schema version). No other event may
   precede it, and it never changes. The identity record is rebuilt from it,
   like every other record: the journal is authoritative.
4. **A canonical Person is founded only explicitly.** For an identifier of the
   form `person-NNN`, an empty root is founded only by the operator's
   founding command, never by ordinary startup, so a second Person-000
   lineage cannot appear by accident. Non-canonical identities (tests,
   experiments, legacy prototypes) are founded automatically on an empty
   root.
5. **A root belongs to one Person, and fails closed.**
   - Opening a founded root under another personId refuses to start.
   - Snapshots carry the personId and the founding record's fingerprint; one
     that does not match its journal is refused before it is loaded.
   - One process at a time holds a root, through a lock in the directory.
   - Copying a whole root and resuming both copies is unsupported. A
     deliberate fork would be a new Person serial with recorded ancestry.
6. **Legacy journals stay readable, unmodified.** A journal with no founding
   event is read and resumed as before. It is never given a founding event
   after the fact, since its first timestamp proves only that evidence
   existed by then. Adopting a legacy lineage into a canonical Person would
   need an explicit, recorded binding with provenance. Person-000 needs none.

### Continuity

7. **Sessions:** each cognition process writes `session_started` and, on a
   clean end, `session_ended`, paired by session id. After a crash there is
   no end event, and none is invented: the next start records that the
   previous session ended uncleanly.
8. **A gap is learned, not remembered (ADR 0006 rule 2).** At session start,
   the external time since the root's most recent recorded event is reduced
   to a coarse category:

   | Gap                              | Category  |
   | -------------------------------- | --------- |
   | under an hour                    | `minutes` |
   | under a day                      | `hours`   |
   | under a week                     | `days`    |
   | a week or more                   | `longer`  |
   | no earlier event                 | none      |
   | clock went backwards, or missing | `unknown` |

   The gap does not advance experienced time, decay affect, create episodes,
   or fabricate anything for the time away.

9. **Self-knowledge is a bounded projection.** A trusted identity component
   rebuilds identity and continuity from the journal. Cognition receives only
   a projection: its designation, name, founding information, and the most
   recent gap category. It gets no journal access (ADR 0003).
   - Home, preferences, tendencies, values and current projects stay with
     their own subsystems; the identity layer is not a second source of
     truth for them.
   - Nothing in decisions consumes the projection yet.

### Operational lifetime

10. **States (increment I2):** EMBODIED, WORLD_UNAVAILABLE, and SUSPENDED.
    SUSPENDED is known only retrospectively, from session continuity, and is
    never written by a process that crashed. EMBODIED and WORLD_UNAVAILABLE
    transitions are journalled. Neither WORLD_UNAVAILABLE nor SUSPENDED
    advances experienced time. SLEEPING is deferred.
11. **Death (increment I3):** configured `respawn` or `permadeath`.
    - **Respawn:** the same Person continues, with death as a major
      autobiographical event holding only what Person could legitimately
      know.
    - **Permadeath:** TERMINATED. Normal startup then refuses to resume that
      identity physically, though read-only inspection stays possible.
      Changing the configuration afterwards does not resurrect it.
    - No privileged information, such as coordinates, enters the death
      record.

### Scope and gates

- Implemented in three increments, each its own PR: I1 identity and
  continuity of self; I2 operational states; I3 death semantics.
- Tests use synthetic identities (`test-person-000`, `fixture-person-a`).
  Canonical Person-000 is never created as a test fixture.
- Any live identity-persistence check uses a disposable validation identity.
- Ada's first real embodiment happens only when the operator explicitly
  authorizes it, never under the label of a validation run.
- Out of scope: values, preferences, personality and any self-model beyond
  the identity record.

## Implementation status

- **I1 (PR #29):** founding, root binding, session continuity, the coarse gap
  and the self-knowledge projection. TESTED IN FIXTURE with synthetic
  identities.
- **I2:** operational state as an explicit state machine, WORLD_AVAILABLE and
  WORLD_UNAVAILABLE, reported by the runtime's `WorldAvailability` and
  journalled as `world_availability_changed` only on a change. Losing the
  world ends an episode as interrupted, never failed, after the configured
  reconnection budget; reconnecting continues the same Person in the same
  session. Suspension is classified at the next session start (after a clean
  end or a crash, with the world's state then); a crash writes nothing, and
  nothing is invented for it. Absence is not experienced and no transition is
  felt across it. Legacy roots acquire no lifecycle events. Cognition sees only
  whether the world is available. TESTED IN FIXTURE with synthetic identities.
- **I3:** not started. DEAD, TERMINATED and respawn belong to it.
- **Separate by design:** identity and continuity (I1), cognitive lifecycle
  (sessions), embodiment connection (the runtime's), operational state (I2)
  and death (I3).

## Consequences

### Positive

- Person-000 has a real beginning, and her evidence can never merge with
  another Person's or with the prototype's experiments.
- Restarts become visible to Person as a fact, without fabricated experience.

### Negative

- The evidence schema gains event types (version 11); every journal written
  from now on starts with a founding event.
- Founding a canonical Person is an extra, deliberate operator step.

## Alternatives considered

| Alternative                                         | Why not                                                                                    |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Keep `"ada"` as Person-000's key                    | Fossilises a convenience identifier, and invites merging experiment evidence into her life |
| Give legacy journals a retrospective founding event | Their first timestamp does not prove when anything was founded                             |
| Expose the raw external gap to cognition            | A clock-access decision this ADR does not make                                             |
| Let identity own home, projects and preferences     | A second source of truth for records other subsystems own                                  |
