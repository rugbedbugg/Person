# ADR 0022: Evidence-backed procedural cognition: the habit lifecycle

**Status:** Accepted (2026-10-01)
**Date:** 2026-10-01
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Direction:** C4 and C5 of the hybrid-cognition phase (ADR 0020), from the
reviewer's design, accepted with its amendments (2026-10-01). Scripted
models and fixtures only. Person-000 stays absent.

---

## Context

ADR 0021 lets Person ask for System-2 help when ordinary cognition is not
enough, and adopt one bounded goal from the answer. The thesis of ADR 0020
is that repeated successful deliberation can become persistent Person-owned
structure, so familiar problems stop needing a general model. That is
proceduralization, not memoization: a strategy becomes a habit only through
lived outcome evidence, and a habit stays defeasible.

## Decision

### What is proceduralized

A **trigger-conditioned goal policy**, not an action sequence:

    WHEN this kind of familiar problem occurs
    IN a sufficiently matching context
    THIS goal has repeatedly resolved it

The ordinary planner still decides how, every time. No plan, routine or
skill sequence is ever stored as executable; the route taken is evidence
only.

### Increments

- **C4:** candidate extraction, stabilization evidence, response grouping
  and the promotion computation, as shadow evidence only. No invocable habit
  state exists.
- **C5:** active candidate evidence, real promotion, invocation, outcome
  tracking, demotion and restart reconstruction. No code path that can invoke
  a habit merges before every demotion path exists and is tested.

**Record-only never acts, now or later.** Record-only writes its own event
stream (`habit_candidate_shadow`, `habit_evidence_shadow`,
`habit_promotion_shadow`, `habit_conflict_shadow`), which active habit
reconstruction ignores. Only evidence gathered while procedural learning was
behaviourally enabled can create an invocable habit, so running record-only
cannot change behaviour in that session or any later active one.

### A successful episode

An adopted deliberation goal that ends `satisfied` is not enough. Success
needs a stabilization window of 1,200 experienced ticks after satisfaction
in which:

- the same trigger key does not recur;
- Person does not die;
- no severe related prediction error occurs.

A world loss or session end inside the window makes the episode inconclusive,
neither success nor failure. The window is 1,200 experienced ticks for every
trigger class (a declared engineering prior).

**Recurrence is any new qualifying raw signal for the same semantic key**,
not the detector firing again: one new suffocation; one new qualifying
failure of that goal; one new no-plan signal after information search gave
up; one new severe evaluable error for that skill and fact. C3's thresholds
answer "should I think?"; the window answers "did that solve it?", and they
stay separate.

### Habit identity: a semantic scope

Never ephemeral ids, coordinates, entity ids or world-private facts:

- trigger kind and semantic key (the emergency trigger; the source goal type
  and desired-fact shape; the skill and evaluable fact);
- a deterministic, versioned **context signature** (`context_signature_v1`)
  over existing coarse, Person-visible categories: health, food and breath
  bands; day phase; weather; the recognised cognitive place (its place id,
  which Person already holds, with a coarse confidence band) or `unknown`;
  visible threats as a sorted set of kind, count band and nearest range band;
  inventory categories mapped deterministically from the response's goal and
  desired facts (absent if no mapping is declared), as `0` or `some`; and the
  source goal type or `none`. Canonical order before hashing; no coordinates
  or runtime-private location. Matching is exact; generalizing across places
  or contexts would be its own increment. If that makes habits rare, that is
  preferable to a habit firing somewhere it does not belong.
- a deterministic **template identity** from the semantic scope, the
  signature version and value, the goal type and the normalized desired
  facts, never from deliberation ids. Both the signature and the response
  template carry schema versions, because changing either changes what every
  learned habit means.

### What a habit holds

`habit_id`, `schema_version`, trigger kind, semantic key, context signature,
response (goal type, normalized desired facts, priority source), provenance
(the founding deliberation ids, outcome evidence refs, `DELIBERATION`
ancestry kept forever), state (`candidate`, `promoted`, `demoted`), and
counts: successful, failed and inconclusive episodes, and the current success
streak. No floating-point confidence: the counts are the evidence, and the
state machine is the confidence model. ADR 0011 already holds probabilistic
reliability where it belongs.

### Promotion

- **Three consecutive independent successes** of the same response template
  (same scope, same context signature, same goal type, same normalized
  desired facts). Independent means three distinct trigger episodes, each its
  own deliberation, adoption and outcome; one long unresolved incident is not
  three. They may fall in one session.
- **Candidate learning still uses System 2.** After a first success, the next
  recurrence is deliberated again, independently. Only after three does the
  template become a habit; the fourth occurrence is the first answered by it.
  One success never influences behaviour.
- A definite failure of the same candidate resets its streak, keeping its
  history.
- After a demotion the streak is zero, and three fresh active deliberative
  successes are needed again; successes of the habit itself after promotion
  never count toward re-promotion.
- Different successful responses are grouped by template; only one reaching
  the rule may be promoted, and at most one per exact scope and signature. A
  competing template that reaches the rule while one is promoted stays
  inactive and is recorded as a conflict.

### Invocation (C5)

On a trigger whose scope and context signature match a promoted habit:
C3's current-relevance check, then the goal-admission gate, then planner
feasibility, then the same trigger-derived priority band C3 would assign
(automatic is not weaker), then one temporary goal. The model is not called;
`habit_invoked` is recorded, and the avoided deliberation counts as a metric,
not a fabricated event. A habit never calls skills, supplies a plan, chooses
a priority, or touches beliefs, memory, affect or projects.

### Demotion (C5)

Definite contrary outcomes while the habit applies:

- the habit goal reaches its failure limit, or expires unresolved;
- the planner finds it infeasible in a matching context;
- the same trigger recurs inside the stabilization window after a claimed
  resolution;
- a severe related prediction error;
- death during the attempt (conservatively, without claiming the habit caused
  it).

Not failures: a context mismatch (the habit simply does not apply; no
penalty, and C3 deliberation stays available), preemption by a higher-priority
need, world unavailability, a session ending first. `habit_not_applicable`
is recorded only when a promoted habit exists for the same semantic scope
and its signature does not match, never for unrelated habits. After demotion the
trigger goes through C3 again; re-promotion needs the full rule again.

### Evidence and metrics

Rebuilt from the journal (evidence schema v16): active `habit_candidate_formed`,
`habit_evidence` (success, failure or inconclusive, with refs),
`habit_promoted` (only for an invocable habit), `habit_conflict`,
`habit_invoked`, `habit_not_applicable`, `habit_demoted`; and record-only's
`habit_candidate_shadow`, `habit_evidence_shadow`, `habit_promotion_shadow`
and `habit_conflict_shadow`. Metrics: candidates formed, success and failure evidence,
promotions, invocations, resolution successes, demotions, not-applicable,
deliberations avoided, and deliberations per experienced hour. A falling
model-call rate is learning only if unresolved problems, failures, deaths and
invalidations do not rise with it.

### Canonical tests (synthetic problems, not the home-from-water case)

A deliberately synthetic goal and problem vocabulary in the test harness,
through the same production admission, planning and habit code; mostly
in-process state-machine tests, plus end to end: a C4 shadow formation
trajectory; for C5 a full active lifecycle (three resolutions, promotion, an
invocation with no model request, a stable success) and an invalidation
(invocation, definite failure, demotion, System 2 again).

- **A, formation:** three deliberated, stable successes; the fourth occurrence
  answered by the habit, with no model call.
- **B:** one success is insufficient; the next occurrence is deliberated.
- **C:** conflicting solutions (A, B, A) do not promote.
- **D:** a promoted habit does not fire in another context, with no penalty.
- **E:** a promoted habit's definite failure demotes it at once; the next
  recurrence goes through System 2.
- **F:** a goal satisfied while the trigger recurs inside the window is not
  success.
- **G:** a restart reconstructs exactly the same habits from the journal.
- **Isolation:** C4 `record_only` against off changes nothing but its own
  evidence, and across a mode switch (off then active, against record-only
  then active, with the same lived active evidence) the active habit state
  and behaviour are identical.

## Implementation status

- **C4 (shadow only):** `person_cognition/deliberation/habits.py`:
  `context_signature_v1`, deterministic template identity, the episode
  tracker (stabilization window, recurrence by raw signal, death, world and
  session), the promotion computation with streaks and conflicts, and two
  books, each rebuilt from its own event stream. `[deliberation] habits =
"record_only"` turns it on beside an active C3; nothing invokes a habit.
  Evidence schema v16. TESTED with scripted models: state-machine tests for
  every rule, and an end-to-end runtime run in which shadow learning changes
  no decision and records one stable success. Not yet shown end to end: a
  three-episode formation through the runtime, which needs a synthetic
  recurring problem; the reducer-level form of the mode-switch invariant
  (the active book never reads shadow events) is tested, its behavioural form
  needs C5's active mode.

## Consequences

### Positive

- Competence in familiar situations can come to depend less on a model,
  measurably, while every habit remains a Person-owned, revocable structure
  with its deliberative ancestry visible.

### Negative

- Exact context matching will make habits rare at first.
- A stabilization window delays every success by 1,200 experienced ticks.

## Alternatives considered

| Alternative                         | Why not                                            |
| ----------------------------------- | -------------------------------------------------- |
| Cache the planner's action sequence | Moves how out of the planner; stale recipes        |
| Promote after one success           | Memoization, not habit formation                   |
| A floating-point habit confidence   | An arbitrary scalar where auditable counts suffice |
| Penalize context mismatch           | A habit for one situation is not wrong in another  |
| Trial a candidate before promotion  | Lets one success influence behaviour               |

## Revisit conditions

- Evidence that exact matching prevents useful habits; generalization would
  be its own increment.
- Plan or routine compilation, if the planner proves a bottleneck.

## Relevant commits and docs

- ADRs 0011, 0020 and 0021.
