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
  no decision and records one stable success.
- **C4.1 (shadow formation through the runtime):** with the amendment below,
  `tests/integration/habit-formation.test.ts` runs three independent episodes
  of one fixture problem through the real runtime and cognition: each a
  `repeated_failure:ESTABLISH_TOOLS` trigger, one deliberation, an adopted
  `MAINTAIN_RESERVES`/`rested` goal satisfied by its own `wait_safely`
  routine, exactly one source retry that gathers wood and crafts tools, and a
  stable success; one template, one exact context signature, one
  `habit_promotion_shadow` naming the three founding deliberations, and no
  active-stream event at all. Evidence schema v17. TESTED IN FIXTURE with
  scripted models. The behavioural form of the mode-switch invariant still
  needs C5's active mode.

- **C5 (active habits):** `[deliberation] habits = "active"` (valid only
  with `mode = "active"`) writes the active stream, and a promoted habit
  answers its problem. TESTED IN FIXTURE with scripted models:
  `tests/integration/habit-lifecycle.test.ts` runs five episodes, one day
  apart, of one fixture problem through the real runtime and cognition.
  Episodes 1 to 3 are deliberated, adopted, remedied and resolved, and
  promote one habit. In episode 4 the habit answers with zero deliberation
  requests, its source goal gets one retry, and the episode is a stable
  success. In episode 5 the world changes: the habit is invoked, its retry
  fails, it is demoted, and `habit_breakdown` asks System 2 again.
  State-machine tests (`test_habits_active.py`) cover each rule below,
  including the mode switch (G2) and a habit-derived recovery goal keeping
  the recovery planning profile. Evidence schema v18.

### Amendment with C4.1 (reviewer, 2026-10-01)

- **Silence is not resolution.** For `repeated_failure` and
  `no_viable_plan`, the failing goal is blocked by the failures that raised
  the trigger, so a window without recurrence proved only that Person had
  stopped trying. For these classes success now needs both positive
  resolution evidence (the source goal, granted its one retry by ADR 0021's
  amendment, runs a routine that succeeds after the remedy is satisfied) and
  no same-key recurrence for the rest of the 1,200-tick window. A retry that
  fails again is the recurrence (failure). No retry by the end of the window
  is `inconclusive`, reason `no_retry`, never success, including when a
  legitimate higher priority kept the goal from being retried. Emergency and
  prediction-error scopes are unchanged.
- **The prediction-error scope** is the skill and the canonical set of its
  severe failing facts (ADR 0021's amendment); recurrence is one new failed
  invocation with that same set.
- **Limitation: correlational, not causal.** Promotion rests on repeated
  contextual outcome evidence, not causal identification, so a correlated but
  non-causal response could in principle proceduralize. C4 and C5 claim no
  causal learning; causal hypotheses stay with ADR 0012. No anti-superstition
  mechanism is added now.
- **Limitation: exact scope.** `repeated_failure:ESTABLISH_TOOLS` and
  `repeated_failure:ESTABLISH_STORAGE` are different problems even when one
  hidden condition caused both. Root-cause equivalence belongs to hypothesis
  learning, not habit formation.
- **The canonical fixture problem** (test machinery only): the hidden rule
  `barren_until_rested`. After an `unrest` event the listed blocks break but
  drop nothing until the body has waited a configured number of ticks, counted
  a tick at a time and only after the `unrest`; a `rest_stops_helping` regime
  change, for C5's breakdown test, makes waiting useless. Between episodes
  `remove_items` (from the body and every chest) and `set_vitals` reset the
  problem and hold the signature steady. The world creates the problem and
  never supplies the remedy. Person's idle routine is also a rest, so the
  test's rest requirement exceeds one idle wait and the adopted rest is the
  one that completes the cure; the test asserts that no wood was gathered in
  an episode before the remedy was adopted. Habit learning still only learns
  "pursuing rest has resolved this here".

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

### Amendment with C5 (reviewer, 2026-10-01)

- **Invocation order.** A trigger reaches its threshold. If Person is alive,
  the world is available and no emergency is being handled, Person looks for
  a promoted habit with the same scope and the exact signature, captured when
  the trigger fires. That lookup comes before any model suppression: a
  provider's cooldown, quota or unavailability never stops a learned habit.
  Every pending problem gets that first refusal before any model is asked
  about any of them. The habit's goal must then pass the checks a
  deliberation's answer passes: relevance, goal admission and the planner.
  Then it becomes the one temporary goal, at the band C3 would assign, and
  `habit_invoked` is recorded. The model is not called; the avoided
  deliberation is a metric (`habit_metrics`), not an event.
- **Contradiction at invocation.** If what the habit aims at already holds
  while its problem is present, or the planner finds it infeasible, the habit
  is demoted (`satisfied_at_invocation`, `infeasible_at_invocation`) and never
  invoked.
- **Outcome and demotion.** A habit's episode is judged like a deliberated
  one, including the C4.1 positive-resolution rule, and its evidence is
  marked `via: habit`. A definite failure (recurrence inside the window, the
  goal failing or expiring, death) demotes it at once and zeroes its streak.
  A prediction error demotes only when it is attributable to the habit, which
  v1 does not attempt. The habit's own successes never count toward promotion
  or re-promotion: after a demotion, three fresh deliberated successes are
  needed again.
- **Breakdown.** A demotion raises `habit_breakdown:<template_id>`. It
  bypasses the original trigger's threshold and cooldown, but obeys the life,
  world and emergency checks, the in-flight limit, the hourly and session
  budgets, and backend availability. It is budgeted as its originating
  problem, so a habit descended from `emergency_recurrence` may use the
  reserved slot, and it gets its own key's cooldown once its request is
  resolved. Its context cites the originating problem. Its answer's band, and
  the scope its evidence counts toward, are the originating problem's.
- **Planning profile.** Temporary remedy goals carry `planning_profile =
recovery`, whether a deliberation or a habit produced them; ordinary goals
  are `ordinary`. Only the recovery profile may use the planner's recovery
  operators (`wait_safely`), which no model is ever offered. Ordinary
  planning is unchanged.
- **One remedy at a time.** While a temporary remedy is live, new requests
  are suppressed (`remedy_in_progress`), and an answer that arrives anyway is
  discarded (`superseded`). A live remedy is never silently replaced. C3 had
  this overwrite latent; habits exposed it, because the prediction-error
  trigger raised by the same failed gathers is no longer masked by an
  in-flight request.
- **Habit source retry.** A satisfied habit remedy grants its source goal
  the same one bounded retry as a deliberation's. It is recorded as
  `habit_source_retry` (template id, invocation id, source goal id, type and
  creation tick, prior block reason). The authority is Person's recovery
  machinery, never the habit. A habit's goal ending is `habit_goal_ended`.
- **Mode switch (G2).** The active book reads only the active stream, so the
  same active evidence rebuilds the same habits and the same next decision,
  whether the shadow stream exists or not.
- **The canonical active-lifecycle fixture changed** from C4.1's rest
  construction to `barren_until_withdrawn`. After `unrest`, the trees drop
  nothing until Person takes something from a chest it already owns, within
  reach. What it takes never helps by itself. System 1 never withdraws idly,
  and a `withdrawal_stops_helping` regime change makes the cure useless for
  the breakdown episode. The reason is asynchrony. A deliberation's answer is
  consumed at a later decision, so after the source goal blocks, Person
  first idles (its idle routine is a 600-tick rest) and only then performs
  the adopted remedy. A habit acts at once, without the idle. No single rest
  threshold can then be causally clean in both deliberative and habitual
  episodes. The merged C4.1 rest test stays as regression evidence for
  shadow formation, the source retry and action-fact satisfaction, with its
  documented idle caveat.
