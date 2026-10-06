# ADR 0028: Predictive models are plural; the singleton world-model provider is retired

**Status:** Accepted (2026-10-06)
**Date:** 2026-10-03
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Supersedes:** the `WorldModelProvider` reservation in
`person_cognition/future_providers.py` and `PERSON_SPEC` section 58's single
provider shape

---

## Context

`future_providers.py` reserved one `WorldModelProvider` with `observe`,
`predict`, `update` and `query`: one object holding world state, predicting,
learning from outcomes and answering belief queries. That shape merges three
things this course correction separates: belief (ADR 0026), history (ADR 0027) and prediction. Meanwhile Person already predicts, and has since its
first milestone: the planner treats each skill's declared effects as
predictions, `prediction.py` compares them with what follows, and effect
reliability (ADR 0011) is learned about exactly those predictions.

## Decision

1. **`WorldModelProvider` and its unimplemented placeholder are removed.** A
   placeholder that outlives the shape it reserved is a false claim.

2. **`PredictiveModel` is a generic, plural interface**
   (`person_epistemics.prediction`): a model has an id, a version, a domain
   and a temporal scale, and answers a `PredictionQuery` (state, intervention,
   belief-store version, horizon) with a `Prediction` or nothing.
   `Predictors` holds several.

3. **The first implementation is the existing predictor.**
   `DeclaredEffectModel` (`person_cognition/predictors.py`) predicts a skill's
   effects to be what its contract declares. Its model version includes the
   skill-library revision; it states no confidence, because a contract states
   none. Every settled prediction now records which model made it and under
   which belief version.

4. **A prediction is a model rollout, always.** `Prediction.source` is
   `MODEL_ROLLOUT` and cannot be anything else; `admit()` refuses it as
   evidence. A predictive model has no route to the body: it cannot emit a
   message, invoke a skill or reach the runtime (architecture test).

5. **No speculative world model.** No learned dynamics, simulator, rollout
   search or counterfactual engine is added. Those are post-Ada work and
   will arrive as further `PredictiveModel` implementations.

## Consequences

### Positive

- The one prediction mechanism Person has is named, versioned and
  attributable; prediction-error records say which model erred.
- Adding a model later does not change the interface or the loop.

### Negative

- None material; the removed placeholder had no callers.

### Neutral

- Learned effect reliability stays a belief about the declared-effect
  model's predictions, not a second model.

## Alternatives Considered

| Alternative                              | Why Rejected                                                     |
| ---------------------------------------- | ---------------------------------------------------------------- |
| Keep the placeholder alongside the model | Two names for the same capability, one of them false             |
| Implement `WorldModelProvider` now       | Speculative post-Ada functionality; merges belief and prediction |
| Treat learned reliability as a model     | It is evidence about a model, not a source of predictions        |

## Revisit Conditions

- A second predictive model is proposed (learned dynamics, a simulator).

## Relevant Commits / Documents

| Reference                                              | Description                            |
| ------------------------------------------------------ | -------------------------------------- |
| `packages/epistemics/.../prediction.py`                | The interface                          |
| `apps/cognition/python/person_cognition/predictors.py` | `DeclaredEffectModel`                  |
| `tests/python/test_epistemic_architecture.py`          | Plural prediction, never evidence      |
| `tests/python/test_architecture.py`                    | No placeholder outlives its capability |
