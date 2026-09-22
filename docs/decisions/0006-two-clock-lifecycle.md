# ADR 0006: The two-clock lifecycle

**Status:** Accepted (rule), Deferred (implementation)
**Date:** 2026-09-22
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder

---

## Context

Person's defining property is continuity: a past, a present situation, and
intentions for the future. Continuity is the property most easily faked, and the
usual way to fake it is to paper over the gaps.

There are two kinds of gap and they are not the same.

Minecraft time is what Person experiences: ticks, day and night, the chronology
of the world it lives in. External time is real elapsed time, dates, and the
hours during which the Person process was not running at all.

If the process is suspended for twelve real hours, no thoughts occurred during
those twelve hours. An architecture that lets Person narrate them afterwards is
producing autobiography from nothing, and every subsequent claim about memory,
learning and continuity is then unfalsifiable.

Minecraft being unavailable is a third case, different from both: the process
runs, cognition could continue, and there is simply no body.

## Decision

Person tracks two clocks and five operational states.

```text
MINECRAFT TIME   ticks, day/night, Minecraft chronology
EXTERNAL TIME    real elapsed time, dates, and periods of unavailability
```

```text
EMBODIED             process running, Minecraft available
WORLD_UNAVAILABLE    process running, Minecraft unavailable, no physical agency
SLEEPING             deliberate rest; cognition greatly reduced or suspended
SUSPENDED            process not running; no cognition happens
TERMINATED           permanent; hardcore or permadeath experiments
```

Rules:

1. **Never fabricate cognition for a period in which the process did not
   execute.** No retroactive thoughts, no invented dreams, no backfilled
   reasoning. This is an integrity rule about the evidence journal.
2. **A gap is learned, not remembered.** On restart Person may discover that
   twelve external hours passed. It has no experience of them, and the
   distinction must survive into whatever memory system is built.
3. **Both clocks are recorded on every event.** Already true: every protocol
   message and every evidence event carries `tick` and `timestamp`.
4. **`WORLD_UNAVAILABLE` is a state, not a crash.** Losing the body is not
   losing the Person. Continuous cognition in that state is an eventual
   capability, not a first-milestone requirement.
5. **Death has two configured semantics.** Normal respawn keeps identity and
   autobiographical memory and lets the world's consequences stand; permadeath
   moves to `TERMINATED`, retains the data for researchers, and that Person does
   not resume.

Rules 1 to 3 are in force now. Rules 4 and 5 are deferred.

## Consequences

### Positive

- Continuity claims become checkable against the journal.
- "Person has been alive for three weeks" acquires two different and both
  honest meanings, and the reports can say which.
- Death becomes a designed event rather than the end of an episode.

### Negative

- Person's autobiography will have holes in it, permanently, and they are
  visible.
- Five states is more lifecycle than the current runtime has, which knows only
  connected and not connected.

### Neutral

- Nothing in the recording changes. Both clocks are already on every event; what
  is missing is anything that reasons about the difference.

## Alternatives Considered

| Alternative                                   | Why rejected                                                                                                                    |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Minecraft time only                           | Person could not know it had been switched off for a week, and could not situate anything it read or was told in real time.     |
| External time only                            | Day and night are the world's chronology and most of Person's survival reasoning is conditioned on them.                        |
| Let the language layer smooth over gaps       | This is the fabrication rule 1 exists to forbid. It is also the single easiest way to make every continuity result meaningless. |
| Treat `SUSPENDED` as equivalent to `SLEEPING` | Sleep is something Person does and can remember doing. Suspension is something done to it and cannot be experienced.            |

## Revisit Conditions

- Continuous cognition during `WORLD_UNAVAILABLE` is implemented, which makes
  that state's evidence semantics a real question rather than a labelling one.
- Permadeath experiments begin.

## Relevant Commits / Documents

| Reference                                      | Description                              |
| ---------------------------------------------- | ---------------------------------------- |
| `docs/PERSON_SPEC.md` sections 0.15, 61        | Lifecycle, two clocks, death             |
| `packages/protocol/schemas/common.schema.json` | `tick` and `timestamp` on every envelope |
| `packages/persistence/`                        | The journal the rule protects            |
