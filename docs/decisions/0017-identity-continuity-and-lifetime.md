# ADR 0017: Identity, continuity and operational lifetime

**Status:** Accepted (2026-09-30)
**Date:** 2026-09-30
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Operator decision:** start the Person-000 identity and continuity phase
(2026-09-30). Scope and design reviewed before implementation. After I3 the
operator reviewed identity, world availability and death as one lifetime
model and accepted this ADR (2026-09-30), approving the legacy-root death
behaviour as implemented. Acceptance does not found Person-000: the canonical
root is created only by a separate, explicit operator authorization.

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
- **I2 (PR #30):** operational state as an explicit state machine, WORLD_AVAILABLE and
  WORLD_UNAVAILABLE, reported by the runtime's `WorldAvailability` and
  journalled as `world_availability_changed` only on a change. Losing the
  world ends an episode as interrupted, never failed, after the configured
  reconnection budget; reconnecting continues the same Person in the same
  session. Suspension is classified at the next session start (after a clean
  end or a crash, with the world's state then); a crash writes nothing, and
  nothing is invented for it. Absence is not experienced and no transition is
  felt across it. Legacy roots acquire no lifecycle events. Cognition sees only
  whether the world is available. TESTED IN FIXTURE with synthetic identities.
- **I3 (PR #31):** life status as its own axis, with alive, awaiting a respawn
  (engineering-facing) and terminated, rebuilt by `LifeRecord`. The trusted
  runtime alone reports a death (`LifeEvent`) and decides by configuration
  whether it is terminal; cognition cannot die or end itself.
  - A **respawn** continues the same Person, session, memories, experienced
    time and projects. In-flight work is interrupted, and body continuity is
    dropped, so the respawned body is the body as it is now.
  - A **permadeath** is terminal by its death record alone, so a crash
    immediately after it still reconstructs a terminated Person.
    `person_terminated` is for readability only. Startup refuses a terminated
    Person whatever the configuration now says, and its evidence stays
    readable.
  - After a crash before a respawn, the next run respawns the body before
    Person perceives anything.
  - The death is one salient `died` memory holding only what Person knew:
    body condition, threat in view, goal and project. Its affect is recorded
    in the `person_died` evidence rather than in memory, because ADR 0010
    (Accepted) keeps affect out of memory by construction.
  - A death on a legacy root is recorded too: it is real new history, not
    silent, and without it permadeath could not be enforced on that root.
    Legacy roots still acquire no session or world events. The operator
    approved this at acceptance.
  - TESTED IN FIXTURE with synthetic identities.
- **Mineflayer lifetime parity (first-Ada readiness, E1):** the adapter
  respawns through `bot.respawn()` and reports the body back only once the
  server has spawned it and the world is as ready as at a first connection;
  a refused, lost, timed-out or out-of-bounds respawn is not reported, and the
  Person stays awaiting one. A player who left dead rejoins at the death
  screen, where mineflayer never emits `spawn`, so connecting completes with a
  dead body that the runtime then handles. Every connection and explicit
  disconnect starts a new client generation, and a retired client's events
  change nothing. Losing the world while dead goes through reconnection, and
  the death is recorded once. CONFORMANCE-TESTED over the double; never run
  against Minecraft.
- **Separate by design:** identity and continuity (I1), cognitive lifecycle
  (sessions), embodiment connection (the runtime's), operational state (I2)
  and death (I3).

## Consequences

### Positive

- Person-000 has a real beginning, and her evidence can never merge with
  another Person's or with the prototype's experiments.
- Restarts become visible to Person as a fact, without fabricated experience.

### Negative

- The evidence schema gains event types (versions 11 to 13); every journal
  written from now on starts with a founding event.
- Founding a canonical Person is an extra, deliberate operator step.

## Alternatives considered

| Alternative                                         | Why not                                                                                    |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Keep `"ada"` as Person-000's key                    | Fossilises a convenience identifier, and invites merging experiment evidence into her life |
| Give legacy journals a retrospective founding event | Their first timestamp does not prove when anything was founded                             |
| Expose the raw external gap to cognition            | A clock-access decision this ADR does not make                                             |
| Let identity own home, projects and preferences     | A second source of truth for records other subsystems own                                  |

## Revisit conditions

- A second Person, or a deliberate fork, needs recorded ancestry (rule 5)
  and the multi-Person ADR.
- Adopting any legacy `"ada"` lineage into a canonical Person needs an
  explicit binding with provenance (rule 6).
- SLEEPING, or any clock access beyond the coarse gap category.
- A decision that consumes the self-knowledge projection.
- The Mineflayer respawn and reconnection ran live once, in the E3
  rehearsal (ADR 0018); a wider live record may revisit their limits.

## Relevant commits and docs

- PR #29 (I1), PR #30 (I2), PR #31 (I3)
- `packages/persistence/python/person_persistence/identity.py`
- `apps/cognition/python/person_cognition/continuity.py`
- `docs/PROTOCOL.md` (`WorldAvailability`, `LifeEvent`)
- `TRACEABILITY.md`, "Identity and continuity", "Operational state", "Life
  status"
