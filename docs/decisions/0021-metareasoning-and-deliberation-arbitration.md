# ADR 0021: Metareasoning: when Person deliberates, and what a deliberation may change

**Status:** Accepted (2026-10-01)
**Date:** 2026-10-01
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Direction:** C3 of the hybrid-cognition phase (ADR 0020), accepted by the
reviewer with the amendments below (2026-10-01). Scripted models and fixtures
only; no provider quota is spent on C3. Person-000 stays absent.

---

## Context

ADR 0020 C1 and C2 built a deliberation boundary and sterile backends with no
behavioural path. C3 decides when Person should suspend ordinary cognition
for System-2 reasoning, and what an admitted proposal may then change.

The question is not "when do we call a model". It is: under what bounded,
Person-owned conditions is the expected value of deliberation high enough
to be worth it? Two facts constrain the answer:

- **The world does not wait.** A sterile call took 9 to 12 s of wall clock in
  C2, while the runtime allows cognition 5 s per decision and Minecraft keeps
  running. A deliberation inside a decision would time out, and even a
  noncausal one would spend the world's time.
- **Emergency handling and strategic adequacy are different things.** In the
  ADR 0019 air check, `restore_air` succeeded every time and the same
  suffocation returned about every 15 s, because nothing above the reflex
  could see that staying in deep water was the problem.

## Decision

### The asymmetry

System 1 always continues safely without System 2. System 2 may advise
System 1; its absence, delay, refusal or failure never strands Person.
Emergencies never wait for deliberation and never pass through it (ADR 0019).

### 1. Triggers: why ordinary cognition may be insufficient

Person-owned detectors, each over signals cognition already has, each with
a key, so recurrences of the same problem are recognised as one:

| Trigger                     | Signal (initial parameters)                                                                    | Key               |
| --------------------------- | ---------------------------------------------------------------------------------------------- | ----------------- |
| `emergency_recurrence`      | the same emergency trigger 3 times within 2,400 experienced ticks, the reflex having succeeded | emergency trigger |
| `repeated_failure`          | the same goal failed 3 times in a row (`consecutive_failures`)                                 | goal type         |
| `no_viable_plan`            | the planner found no plan for the active goal 3 decisions running                              | goal type         |
| `repeated_prediction_error` | a severe prediction error for the same skill and fact 3 times within 2,400 ticks               | skill and fact    |
| `project_reconsideration`   | a project one block short of abandonment                                                       | project kind      |

`novel_context`, `belief_conflict`, `high_uncertainty`, `unexpected_outcome`
and `reflection` stay in the vocabulary but have no detector in C3. Each
needs its own evidence that it is worth the cost.

### 2. Eligibility: whether deliberation is allowed now

All of these, or no request:

- mode `active` (or `record_only`, which runs everything below except adoption);
- alive, and the world available;
- no L0 or L1 emergency in the current decision;
- nothing in flight: at most one deliberation at a time.

The request binds an immutable snapshot: deliberation id, session id, life
epoch (deaths and respawns), world-availability epoch, the requesting
decision, experienced tick, trigger type and key, and the source goal or
project. The worker makes the provider call and nothing else: no cognitive
state and no journal is touched off the main thread; the main thread alone
evaluates, adopts or discards the result at a later decision. A request left
in flight by a crash stays an unmatched `deliberation_requested`; nothing is
reconstructed on restart.

### 3. Suppression: cooldowns, duplicates and budgets

- **Asynchronous by construction.** A request is handed to a worker. The
  decision that raised it is answered by System 1 as if nothing happened.
  The answer arrives at a later decision, or not at all.
- **Per-key cooldown:** 6,000 experienced ticks from when a request for the
  same trigger and key resolves or is discarded, whatever its outcome (while
  it is in flight, the one-at-a-time rule already suppresses duplicates).
- **Budget:** at most 4 requests per experienced hour, and at most 16 per
  session: a containment guard, not a psychological claim.
- **Backoff:** after an unavailable or degraded answer, the key's cooldown
  goes 6,000, 12,000, 24,000, 48,000, then at most 72,000 experienced ticks.
  A sterility failure disables the backend for the session.
- **Experienced time only.** Time without the world or without a process
  replenishes nothing, and cooldowns and budgets are rebuilt from the journal,
  so a restart resets none of them.
- A trigger that fires while suppressed is counted and recorded, never queued.

### 4. Adoption: what an admitted proposal may change (mode `active` only)

- **Staleness first.** An answer is discarded, with the reason, if the
  session, life epoch or world epoch changed since the request, or more than
  1,200 experienced ticks passed. Relevance is then trigger-specific, judged
  only from Person-accessible state: for goal triggers the source goal is
  still relevant; for a project, it is still active and near the
  reconsideration boundary; for an emergency recurrence, the historical fact
  of three emergencies is not enough, and a proposal whose completion Person
  can already see satisfied is superseded. Private motor geometry is never
  consulted.
- **A goal-admission gate, then the planner.** The preferred strategy only.
  Its goal type and desired facts must be Person's known goals and goal
  predicates, representable as a completion condition, naming no privileged
  target or state; the strategy must cite the triggering problem; the source
  goal or project must still exist. Then Person's planner must find a plan
  for the desired facts from the current symbolic state. The model's
  capability references are ignored throughout.
- **One goal, at a priority Person assigns.** An admitted strategy adds one
  candidate goal: its goal type, its desired facts as the completion
  condition, source `deliberation:<id>`. **The model never chooses or raises a
  priority.** The band comes from the trigger: `emergency_recurrence` gets the
  strategic-recovery band, 700 (below immediate survival at about 990, above
  urgent hunger at about 560); `repeated_failure`, `no_viable_plan` and
  `repeated_prediction_error` inherit the source goal's pre-deliberation
  priority, capped at 700; `project_reconsideration` gets the project band, 300. `deliberation_adopted` records the band and where it came from.
- **Bounded life.** An adopted goal expires when satisfied, after 3 failures,
  or after 2,400 experienced ticks. Its outcomes feed the ordinary triggers,
  so a strategy that does not work leads back to deliberation later, not to a
  loop.
- **Nothing else changes.** Beliefs, hypotheses, memory, affect, learning,
  projects and policy are untouched. Only the goal, and the evidence that it
  came from a deliberation, exist.

### 4a. Record-only

In `record_only` everything above runs (detection, suppression, the
asynchronous request, the gates, staleness and a side-effect-free planner
check) but no goal is ever inserted or reprioritised. The result is a
`deliberation_shadow_disposition` (would adopt or would discard, why, the
hypothetical goal and band), never `deliberation_adopted`, so a shadow
decision can never be mistaken for lived behaviour. A structural-isolation
test shows `record_only` changes nothing but deliberation evidence.

### 5. Failure

An unavailable, degraded, rejected, stale or unadoptable answer changes
nothing. System 1 carries on, and the trigger stays subject to its cooldown
and backoff. No retry within a deliberation.

### 6. Evidence

- `deliberation_requested` gains the trigger, its key and the signal values
  that fired it.
- New records (evidence schema v15):
  - `deliberation_suppressed`: trigger, key and why (cooldown, budget,
    ineligible, in flight);
  - `deliberation_adopted`: id, goal, priority band and its source, plan
    found;
  - `deliberation_discarded`: id and why (stale, irrelevant, superseded,
    inadmissible, infeasible, died, world lost);
  - `deliberation_shadow_disposition`: record-only's would-adopt or
    would-discard.
- Metrics: deliberations per experienced hour by trigger; suppression,
  adoption and discard rates; the outcomes of adopted goals.

### 7. The canonical tests

A fixture pool where the body sinks after surfacing, in two cases. Every
suffocation goes straight to `restore_air`, deterministically; the third
recurrence within the window raises one asynchronous `emergency_recurrence`
deliberation; the cooldown holds, and nothing loops even when the model is
unavailable.

- **A. A known home.** A scripted model proposes `RECOVER_HOME` with
  `at_home`; the planner finds a genuine `return_home` plan; the goal is
  adopted at 700, and the body leaves the recurring hazard.
- **B. No known home.** The same deliberation happens, but no admissible,
  plannable goal exists, so the proposal is discarded and System 1 carries on
  safely. This is not a failure: knowing that ordinary behaviour is
  inadequate is not the same as having a capability that solves it. No
  "reach dry land" goal is added to make the test pass; a capability like
  that would be its own deliberate increment.

## Implementation status

C3 (`person_cognition/deliberation/arbiter.py`, `metareasoning.py`):
detectors, eligibility, journal-rebuilt suppression (cooldowns, backoff and
budgets survive a restart; a request a crash left unanswered never blocks
the next session), the asynchronous worker (the provider call alone runs off
the main thread), staleness and relevance, the goal-admission gate,
planner feasibility, trigger-assigned priority, one expiring adopted goal,
and record-only shadow dispositions. Evidence schema v15; goals a
deliberation led to carry the protocol goal source `deliberation`. A
`scripted` backend (answers in a local file, no network) lets the runtime's
cognition subprocess run it in fixture tests.

Two detector refinements came from the first runs, inside this ADR's
definitions: a prediction error counts only for facts Person can evaluate
(ADR 0011; unobservable expectations are not surprises), and a goal without
a plan counts only once information search has given up on it. Without them,
ordinary looking and searching spent the hourly budget before a real
problem arrived.

The fixture now lets a body in water sink when not swimming up and swim at
the surface, so the canonical case runs: case A adopts `RECOVER_HOME` at
700 and the goal is satisfied; case B (a recovery Person cannot plan) is
discarded as infeasible. **The "no known home" form of case B cannot occur
in this architecture:** the runtime's home record always exists (configured
`world.home`), so `home_known` is always true and `return_home` always
plannable. TESTED IN FIXTURE with scripted models.

### Amendments before merge (reviewer, 2026-10-01)

- **`project_reconsideration` has no detector** in C3; its vocabulary is
  reserved. "One block short of abandonment" had not shown that System 2 is
  warranted, and it overlaps `repeated_failure` and `no_viable_plan`; it was
  most of the early long-run requests.
- **One hourly slot is reserved for `emergency_recurrence`:** at most 4
  deliberations per experienced hour, of which at most 3 for any other
  trigger, so ordinary failures cannot spend the hour before a recurring
  hazard appears. A budget contains cost; it must not hide an over-eager
  detector.
- **A detector that fires resets:** the same problem needs three new signals
  to fire again.
- **Diagnostic:** a 2,000-decision scripted pool run (47,704 experienced
  ticks, about 0.66 experienced hour) fired three triggers in all, each a
  distinct key once: the suffocation recurrence (adopted, satisfied) and two
  no-plan problems after search gave up. No suppression was needed; nothing
  stormed.
- **E4 readiness item:** Ada begins with a trusted, operator-configured home
  anchor that makes `return_home` plannable before she has chosen or built a
  home. Before E4, decide whether that anchor stays purely trusted motor
  infrastructure, is renamed, or whether cognition's `home_known` semantics
  change, so it never silently stands for "Ada has chosen a home".

## Consequences

### Positive

- Deliberation happens when Person has evidence that its routines are not
  enough, not on a timer or on every observation.
- A deliberation can change what Person does in only one bounded, inspectable
  way: one goal, admitted and planner-checked, at a priority Person assigns,
  expiring.

### Negative

- Asynchrony makes every answer possibly stale; the staleness rules decide
  how often a good answer arrives too late.
- The parameters are declared engineering priors. C7 may characterise how
  often triggers fire, but does not tune them; they change before Ada only for
  a demonstrated pathology, recorded.

## Alternatives considered

| Alternative                                   | Why not                                                        |
| --------------------------------------------- | -------------------------------------------------------------- |
| Deliberate synchronously inside a decision    | Times out, and spends the world's time either way              |
| Let an adopted strategy override urgent needs | Makes the model's judgement outrank Person's homeostasis       |
| One fixed band for every adopted goal         | A failing minor goal would escalate itself by asking the model |
| Use the model's capability references to plan | "How" leaves Person's planner (ADR 0020 rule 2)                |
| Queue suppressed triggers                     | A backlog of stale questions is a loop by another name         |
| Trigger on every novel context                | Novelty is common, and most of it needs no deliberation        |

## Revisit conditions

- C7 measurements of trigger frequency, staleness and adoption outcomes.
- C4 and C5 habits, which may answer a recurring trigger without a model.
- C6 affect in arbitration.

## Relevant commits and docs

- ADR 0019 and the air check,
  `docs/evidence/dedicated-server/2026-09-30-adr0019-air-check/`; ADR 0020,
  PRs #40 and #41.
