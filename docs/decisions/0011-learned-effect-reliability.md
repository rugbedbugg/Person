# ADR 0011: Learned reliability of skill effects

**Status:** Proposed
**Date:** 2026-09-26
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Operator decision:** option (a), narrow uncertain beliefs about skill-effect
reliability learned from prediction error, gated by learning mode
(2026-09-26)

---

## Context

Every skill contract declares expected effects, the planner reasons with them
as if they were true, and since Phase 3 the loop has measured each settled
prediction against the next observation. That measurement was inert by
design. This ADR makes it teach one thing, carefully: how far Person can trust
a skill to do what its contract says.

### Audit of the prediction stream

- **Target:** the executed skill's declared effects, resolved by the runtime
  from the public skill contract and returned in `SkillOutcome`.
- **Before:** the planner state Person reasoned over, from its observation and
  its own home belief, captured when the decision was made.
- **After:** the same state from the next observation.
- **Privileged inputs:** none. `completionEvidence` is not read.
- **Problems found:** three kinds of fact in that state cannot legitimately
  teach reliability. `at_home` and `sheltered` are Person's beliefs, and a
  successful `return_home` makes the first true by labelling the place, so
  judging the skill by it is circular. `rested`, `stored_surplus`,
  `withdrawn` and `looted` are never carried by an observation, so they always
  read as absent. `shelter_complete`, `owned_storage_available` and
  `furnace_placed` come from the runtime's placement ledger, which is
  bookkeeping rather than experience. All are excluded from learning.
- **Failure statuses:** most `FAILED` outcomes are prerequisites found before
  anything physical happened (`missing_materials`, `no_placement_site`,
  `obstructed_site`, `inventory_full`, ...). Status alone does not show an
  attempt.

### Learning modes, as they exist

Routine statistics accumulate evidence in every mode. The modes gate its
use: `off` executes the deterministic fallback, `shadow` records the learned
proposal and executes the fallback, `supervised` executes the learned choice
within support and envelope rules. That is unchanged.

## Decision

1. **A belief is not a memory.** A learned effect belief is an aggregate,
   "from experience I expect this to work with this much confidence". It is
   not an episode and is not stored in episodic memory, and recalling one
   failure is not a belief.
2. **A belief is not the contract.** The contract supplies the prediction
   target. Reliability is learned, and starts with no estimate at all.
3. **Only genuine, evaluable attempts teach.** A trial is inconclusive, with
   its reason recorded, when the runtime refused it, the kernel took over,
   it was preempted or interrupted, a prerequisite or target was missing
   before anything physical happened, or no observation followed. A genuine
   attempt is judged per declared effect on facts Person evaluates itself
   (inventory, body state, perceived threat): `supports`, `partial` or
   `contradicts`.
4. **No invented target.** Beliefs are keyed by skill and effect fact only,
   never by the thing acted on (C4).
5. **Narrow domain.** One belief per (training context, skill, fact). No
   propositions, no free text, no general belief graph.
6. **Uncertainty is first-class.** A belief keeps its supporting and
   contradicting evidence separately. With no evidence it has no estimate;
   its estimate uses a uniform prior, so one outcome cannot reach 0 or 1; its
   strength is separate from its estimate. "Balanced and well-evidenced" and
   "unknown" are different states.
7. **Revisable.** Later evidence can reverse any trend.
8. **Provenance.** Each belief keeps its latest evidence records; each record
   points at the prediction-error event it came from. Cognition has no
   journal access.
9. **Learning modes gate the update.** Every trial is journalled as
   `effect_evidence` (schema v8) with what the mode then admitted it to:
   nothing under `off`, an isolated shadow table under `shadow`, the active
   table under `supervised`. Unlike routine statistics, `off` updates no
   belief; this is the operator's decision and changes no existing mode.
10. **Shadow is not belief.** The shadow table is for evaluation. No planner,
    goal or policy code can read it.
11. **Persistence.** Both tables are rebuilt from `effect_evidence` alone and
    survive restarts; nothing is injected into working memory.
12. **Bounded policy effect.** Under `supervised`, a routine's score gains a
    learned term, the mean over its steps of each skill's (estimate - 0.5) x
    strength, scaled into a small fixed bound and recorded separately on each
    candidate (`learned_effect`). It cannot create a goal, make an
    inapplicable routine win, or touch any runtime check.
13. **Separations.** Routine statistics, memory salience and recall, and
    affect ignore `effect_evidence`. No affect coupling in this phase.
14. **No causal world model.** Hypotheses, experiments and causal induction
    are later work.

The prior, the strength constant, the verdict weights, the bound and the
evaluable-fact list are implementation parameters.

## Consequences

### Positive

- A contract that is quietly wrong now costs Person something it can notice,
  and the journal says exactly why it came to distrust it.
- The learned term is visible beside every other part of a routine's score.

### Negative

- Skills whose effects are only visible through the ledger (building,
  storage, furnace) learn nothing yet.
- Net effects over a whole skill are all Person sees, so a skill that does
  half its job reads as `partial`, not as which half.

### Neutral

- Journal schema v8. No protocol change.

## Alternatives Considered

| Alternative                                   | Why rejected                                                                    |
| --------------------------------------------- | ------------------------------------------------------------------------------- |
| Fold prediction error into routine statistics | Routine performance and belief about an effect are different claims (operator). |
| A general causal world model now              | Much larger; later phase.                                                       |
| Count every non-success as a failure          | Refusals, takeovers and missing prerequisites say nothing about the effect.     |
| Start reliability at the contract's claim     | That makes the contract's word evidence.                                        |
| Point estimates without strength              | Cannot tell "unknown" from "balanced".                                          |

## Revisit Conditions

- Hypotheses and controlled experiments (the next learning phase).
- Ledger-derived facts gain a perceptual equivalent, and building skills can
  be judged.
- Affect or memory should use beliefs (separate decisions).

## Relevant Commits / Documents

| Reference                                                   | Description                    |
| ----------------------------------------------------------- | ------------------------------ |
| `docs/PERSON_SPEC.md` sections 21, 26                       | Learning, the world model      |
| ADR 0007, ADR 0010                                          | Memory and affect, left alone  |
| `apps/cognition/python/person_cognition/effect_learning.py` | The implementation             |
| `apps/cognition/python/person_cognition/prediction.py`      | The prediction stream it reads |
