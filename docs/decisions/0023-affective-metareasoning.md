# ADR 0023: Affective metareasoning

**Status:** Accepted (2026-10-01)
**Date:** 2026-10-01
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Direction:** C6 of the hybrid-cognition phase (ADR 0020), from the
reviewer's scoping, accepted with its four amendments (2026-10-01). Scripted
models and fixtures only. Person-000 stays absent.

---

## Context

ADR 0010 gives Person affect (valence, unease, control) with a bounded
influence on goal priority. ADR 0021 decides when Person asks System 2 for
help, from evidence counts alone. ADR 0022 lets learned habits answer familiar
problems first. The question C6 asks is narrower than "affect changes
behaviour": **does Person's internal state change how quickly it stops relying
on routine cognition and pays for deliberation?** That is a functional role
for emotion that a model cannot supply from outside.

## Decision

### The one mechanism

Person's pre-existing affective state may lower, by exactly one signal, the
evidence threshold for escalating an otherwise unresolved non-emergency
problem from routine cognition to deliberation. Nothing else.

| Trigger                     | Baseline (ADR 0021) | With affect |
| --------------------------- | ------------------- | ----------- |
| `repeated_failure`          | 3                   | 2 or 3      |
| `repeated_prediction_error` | 3                   | 2 or 3      |
| `no_viable_plan`            | 3                   | 2 or 3      |
| `emergency_recurrence`      | 3                   | 3, always   |

- **Only earlier, never later.** The effective threshold is 2 when unease is
  `high` or control is `low`; otherwise it is the baseline. Calm or confident
  Person never ignores evidence longer than ADR 0021 already allows.
- **Bands, not values.** The arbitration rule sees only coarse bands of the
  existing ADR 0010 state, never the floating-point values:
  - unease `low` < 0.2 <= `normal` < 0.5 <= `high`;
  - control `low` <= -0.25 < `normal` < 0.25 <= `high`.

  These are declared engineering priors.

- **Valence does not participate** in v1; it is too broad to read causally.
- **Emergencies are affect-independent.** `emergency_recurrence` keeps its
  count, its reserved slot and its determinism.
- **Habits keep first refusal.** A promoted, applicable habit answers its
  problem before any of this is consulted (ADR 0022). Affect does not veto a
  habit in C6; affective habit arbitration would confound "the habit failed"
  with "Person distrusted it", and is a later increment of its own.
- **Pre-existing state only.** A signal is judged by Person's affect from
  before its own appraisal. A failure may count as evidence now, and its
  appraisal may lower control for later signals, but it never lowers the
  threshold it is itself counted against. The bands a signal carries are
  those Person had when it dispatched the skill whose outcome produced the
  signal; nothing about that outcome has been appraised by then.
- **Where it is consulted.** Affect is read only at the arbitration point:
  after life and world eligibility, after the one-live-remedy rule, and after
  a matching promoted habit has had first refusal; before the threshold
  comparison. A candidate one signal early that never reaches that point
  (a habit applies, a remedy is live) leaves no trace.
- **Everything else in ADR 0021 still applies** to an affect-advanced
  request: eligibility, one remedy at a time, the in-flight limit, the
  budgets, cooldowns, staleness, admission and the planner. Affect changes
  when a trigger fires, not what may follow.

### What affect may not do here

- Change any priority band or ADR 0010's priority bias; the two paths would
  confound each other.
- Reach the model: `DeliberationContext` carries no affect in C6.
- Create goals, change memory or salience, add appraisal rules, or touch the
  safety layer. C6 consumes affect; it does not redefine it.

### No feedback loop

Deliberation itself is never an appraisal input. `deliberation_requested`,
`deliberation_completed` and `affective_arbitration_shadow` cannot change
affect; otherwise unease would bring deliberation earlier, which would raise
unease, and so on. World and goal outcomes keep their ADR 0010 appraisals,
including those of goals a deliberation or habit produced.

### Modes

`[deliberation] affectArbitration = "off" | "record_only" | "active"`, off by
default. `record_only` requires deliberation `record_only` or `active`, and
affect `active` (ADR 0013); `active` requires deliberation `active` and affect
`active`.

- **record_only (C6a):** every affective signal that reaches the arbitration
  point records `affective_arbitration_shadow`: trigger kind and key, signal
  count, baseline and shadow thresholds, unease and control bands,
  `baseline_threshold_crossed`, `shadow_threshold_crossed` and
  `affect_advanced_threshold` (the shadow crossed and the baseline did not).
  These are detector-level facts; crossing a threshold does not promise a
  request. Behaviour uses the baseline only, and no other record changes.
  Shadow evidence never becomes causal, now or later.
- **active (C6b):** the effective threshold applies. A request records
  `baseline_would_fire` and `affect_changed_outcome` (true only when the
  request exists because the lowered threshold was crossed). A suppression
  records `baseline_would_fire` and `affect_advanced_threshold`, so a case
  where affect wanted earlier deliberation and the budgets overruled it is
  kept too.

### Evidence

Evidence schema v19: `affective_arbitration_shadow`, and the counterfactual
fields on `deliberation_requested` and `deliberation_suppressed`. Metrics: affect-advanced requests per experienced
hour, set beside their outcomes (adopted, resolved, failed), so a rise in
earlier deliberation is judged by whether it resolved anything.

### Canonical tests (scripted models only)

- **A, baseline equivalence:** normal affect, three failures: deliberation on
  the third.
- **B, affect advances deliberation:** high unease, two failures: active C6
  deliberates on the second, and records that the baseline would not have.
- **C, record-only isolation:** the same, record-only: the shadow says
  "would fire" and nothing fires. Off against record-only on the same fixture
  gives identical requests, goals, skills and final state; only the shadow
  evidence differs.
- **D, habit precedence:** a promoted applicable habit and high unease or low
  control: the habit handles the trigger, with no affect-arbitration event for
  it and no model request.
- **E, emergencies unchanged:** high unease and two suffocations: no strategic
  deliberation; the third fires as in ADR 0021.
- **F, decay restores the baseline:** high unease at first gives threshold 2;
  after experienced-time decay to normal, 3 again.
- **G, restart:** the same affect state and trigger history before and after
  a restart give the same effective decision.
- **H, no same-event bootstrap:** from normal affect, a signal whose own
  appraisal would move control to low is judged without it; the next signal
  may use it. Also tested separately: high unease with normal control, and
  normal unease with low control, each give threshold 2.

## Implementation status

- **C6a (record-only):** `person_cognition/deliberation/metareasoning.py`
  (`affect_bands`, `affective_threshold`; detectors offer a candidate one
  signal early only when arbitration is on) and
  `person_cognition/deliberation/arbiter.py` (the arbitration point; the
  bands snapshot taken at skill dispatch). Evidence schema v19. TESTED IN
  FIXTURE with scripted models: the rule, the bands, decay (F), restart (G),
  pre-signal judgement (H), habit precedence (D), emergencies outside C6 (E),
  record-only changing no request or payload (C), and
  `tests/integration/affect-arbitration.test.ts`. That test runs the same
  quiet-grove episode, with Person hurt early so unease is high, off and
  record-only. Record-only records affect wanting deliberation on the second
  failure, while requests, goals, skills and final state are identical, and
  no deliberation ever reaches appraisal.
- **C6b (active):** `affectArbitration = "active"`, valid only with active
  deliberation and active affect. The effective threshold applies. A request
  records `baseline_would_fire` and `affect_changed_outcome`; a suppression
  records `baseline_would_fire` and `affect_advanced_threshold`. Once an
  affect-advanced request is made, its evidence is spent, and the detector
  counts afresh. TESTED IN FIXTURE with scripted models: A (normal affect
  deliberates on the third signal), B (high unease, and separately low
  control, on the second), budgets overruling affect kept as evidence, D, E
  and H in active mode. The second runtime test runs the hurt-early
  quiet-grove episode, off and active. Active asks on the second failure,
  earlier than off, which asks on the third; it records that the baseline
  would not yet have fired. The earlier remedy still resolves the episode
  (stable success), and no request carries affect.

## Consequences

### Positive

- A narrow, testable functional role for emotion, with the counterfactual
  recorded for every affect-caused deliberation.

### Negative

- Earlier deliberation costs model calls; the budgets of ADR 0021 still bound
  it, and the metrics must show it resolves problems, not just spends calls.
- Band thresholds are priors and may need tuning on evidence.

## Alternatives considered

| Alternative                           | Why not                                                    |
| ------------------------------------- | ---------------------------------------------------------- |
| Affect shifts priority bands          | ADR 0010 already biases priority; two paths would confound |
| Affect in the deliberation context    | Outsources emotional interpretation to the model           |
| Calm raises thresholds above baseline | Lets Person ignore evidence longer than ADR 0021 permits   |
| Affect vetoes habits                  | Confounds habit failure with distrust; a later increment   |
| Valence participates                  | Too broad to interpret causally in v1                      |

## Revisit conditions

- Evidence that earlier deliberation under unease does not resolve problems
  more often than it wastes calls.
- Affective habit arbitration, as its own ADR.

## Relevant commits and docs

- ADRs 0010, 0013, 0020, 0021 and 0022.
