# Learning

Person learns which of several valid strategies works best in a given kind of
situation. It does not learn Minecraft mechanics: crafting dependencies are
declared in skill contracts and derived by the planner, because rediscovering
them from experience would waste episodes on facts that are already known.

## Modes

Learning never enables itself.

| Mode         | Behaviour                                                                                     |
| ------------ | --------------------------------------------------------------------------------------------- |
| `off`        | Deterministic fallback only. No policy update influences a decision.                          |
| `shadow`     | The learner scores every candidate and its preference is recorded, but the fallback executes. |
| `supervised` | The learner may choose, still inside every safety limit.                                      |

`off` is what the shipped configurations use. `person learn --mode ...` is the
only way to put a learner in control, and the mode is announced in
`SessionHello`, recorded in every evidence event, and printed in both reports.

## Decision context

Learning is conditioned on a coarse context, not the raw observation:

```
health_band  critical | low | healthy
food_band    starving | low | sufficient | full
day_phase    dawn | day | dusk | night
threat       none | nearby | immediate
home_state   at_home | near | far | unknown
tool_tier    none | wood | stone | iron | diamond
food_state   none | raw | cooked | stored
```

Serialised as `h_healthy.f_low.d_day.t_none.hm_near.tt_none.fs_none`. The whole
space is under twelve thousand cells, and a test asserts that. Nudging health
by a fraction, moving three blocks, or picking up some dirt does not create a
new learning context; losing most of your health does.

## What is counted

Per training context, per decision context, per routine:

```
attempts  successes  failures  inconclusive
health_cost  resource_cost  elapsed_ticks
recoveries  failure_modes  evidence_refs
```

And separately, per executed skill, the same counts plus `preemptions`.

Interruptions are counted but are not evidence for or against a routine: being
preempted by a hostile says nothing about whether the routine works.

Statistics never merge across training contexts. Evidence from the fixture and
evidence from a live world stay in separate cells, so a fixture success cannot
quietly stand in for a Minecraft one.

## Success estimate

A routine's success probability is a Beta posterior:

```
success ~ Beta(1 + successes, 1 + failures)
```

Scoring uses a conservative lower bound, `mean - sqrt(variance)`, so one
success out of one does not look like a hundred out of a hundred. The former
scores about 0.43; the latter about 0.98.

## Scoring

```
score =  1.00 * conservative success estimate
       - 0.90 * mean health cost, normalised
       - 0.70 * plan risk
       - 0.15 * mean resource cost, normalised
       - 0.20 * time cost, normalised
       + 0.25 * (recovery probability - 0.5)
       + exploration bonus, only inside the safe envelope
```

Safety dominates convenience deliberately. A slower routine wins if it is
meaningfully safer, and a test asserts that two routines with identical records
are separated by their health cost.

## Safe exploration

The exploration bonus is exactly zero outside the safe envelope. The envelope
is open only when Person is alive, above the health and food thresholds, with
no hostile within sixteen blocks, no hazard within three, a known route home, a
recoverable distance from home, and either daylight or a completed shelter.

Outside the envelope, an unsupported routine gets no bonus, and when nothing is
well supported the deterministic fallback runs instead.

## Evidence

Evidence is immutable and append-only. Scores are never persisted; they are
recomputed from counts that were themselves rebuilt from the journal, so
changing the scoring function re-reads history instead of invalidating it.

```
runs/evidence/
  journal/000001.jsonl      append-only, fsynced, chained by previous_event_id
  snapshots/cognition-000004.json   atomic temp-file-and-rename, checksummed
  reports/learning-ep_first.json
```

Event types: `episode_started`, `goal_selected`, `routine_selected`,
`routine_outcome`, `skill_started`, `skill_completed`, `skill_failed`,
`skill_interrupted`, `emergency_override`, `death`, `episode_ended`.

Reading is strict. A duplicate event id with identical content is ignored and
counted; a malformed record raises rather than being skipped; an unreadable
final line with no trailing newline is treated as a crash-truncated write,
dropped, and counted.

## Restart

```
load the newest valid snapshot
    then replay every event recorded after it
    then rebuild the routine and skill statistics
```

A snapshot is an optimisation, never a source of truth. A failed checksum, an
unsupported version, or a snapshot pointing at an event the journal does not
contain all lead to the same place: ignore it and rebuild from the journal.
Tests cover each case, and the integration test shows a restarted process
continuing the same event chain and making a decision informed by evidence from
before the restart.

## Attribution

When the runtime replaces a proposal, the executed skill gets the attempt and
the requested skill gets a preemption. A skill can never accumulate a record
for work it did not do. The canonical case is in the tests: requested
`gather_wood`, executed `flee`, and `flee` is what learning credits.

## Historical logs

Old logs are not training evidence. Importing a trace requires a reviewed
manifest naming the file, its sha256, the reviewer, the purpose, and which
events are included and excluded. An unapproved manifest or a hash mismatch is
refused. Demonstrations carry lower evidential weight than instrumented live
experience. This milestone implements the schema, validation and provenance; it
does not implement a demonstration learner.

Legacy Shroud V1 Q-learning checkpoints are recognised and refused with a clear
diagnostic. There is no conversion: the V1 table is indexed by seven integer
action ids over a bucketed vector, and Person scores routines built from typed
skills in a semantic context. Any mapping between them would be invented rather
than learned.
