# ADR 0027: Canonical events are not epistemic evidence

**Status:** Proposed (2026-10-03; awaiting maintainer review)
**Date:** 2026-10-03
**Authors:** to be confirmed by the operator
**Reviewers:** @rugbedbugg, @upayanmazumder
**Refines:** ADR 0003 (the journal is engineering truth), ADR 0018 (canonical
history)

---

## Context

The journal was called the "evidence journal", its records "evidence
events", its error `EvidenceError`. That naming said every record is
evidence. Most are not: an affect appraisal, a deliberation, a recall, a
session start and a prediction are all canonical history, and none of them
is evidence about the world. As Person gains internal events (recall,
deliberation, prediction, and later replay, counterfactuals and model
rollouts), the naming would invite exactly the mistake the memory firewall
exists to prevent: an internal event becoming evidence by being recorded.

## Decision

1. **Canonical event journal.** The journal's types are `CanonicalEvent`,
   `EventJournal`, `EventStore`, `EventReducer` and `EventRecordError`. The
   former names (`EvidenceEvent`, `EvidenceError`, `EVIDENCE_SCHEMA_VERSION`
   and the store aliases) remain importable as compatibility aliases. Journal
   schema `person-event-v20`; every record carries its `experience` key.
   Records v1 to v19 are read unchanged: their `training_context` is mapped
   to an experience key (`person_persistence/legacy.py`) and written back out
   exactly as it was read. Nothing is rewritten.

2. **Evidence is admitted, not recorded.** Exactly three event types may
   move a belief, each only through the reducer that owns that belief
   (`person_cognition/admission.py`): `belief_revised` (a fact belief, basis
   stated per record), `effect_evidence` (effect reliability, from an
   intervention outcome) and `hypothesis_evidence` (a causal hypothesis).
   An architecture test feeds every other event type to every belief-holding
   reducer and checks nothing moves.

3. **Provenance classes are a closed set** (`person_epistemics.Source`):
   `REAL_OBSERVATION`, `INTERVENTION_OUTCOME`, `RUNTIME_REPORT`,
   `MEMORY_RECALL`, `TESTIMONY`, `RESEARCH`, `REPLAY`, `COUNTERFACTUAL`,
   `MODEL_ROLLOUT`, `OPERATOR_INTERVENTION`, `INFERENCE`,
   `INITIAL_KNOWLEDGE`. `admit()` refuses any class that is never evidence
   (recall, replay, counterfactual, model rollout, inference, initial
   knowledge), refuses reported classes (no channel exists, ADR 0004),
   refuses anything from a replayed experience stream, and refuses evidence
   with no references.

4. **Lived experience is recorded once.** Only the lived classes
   (`REAL_OBSERVATION`, `INTERVENTION_OUTCOME`) become autobiographical
   episodes, and every episode's provenance says so. Recall, deliberation,
   prediction and inference may be canonical internal events; none creates
   an episode, duplicates one or becomes evidence by being journalled.
   Replay is an experience context (ADR 0025), never new lived experience.

5. **Respawn and terminal death are unchanged** (ADR 0017). Respawn is the
   default and continues the same Person, memories, beliefs, projects and
   history. Permadeath is an explicit lifecycle choice; no shipped
   configuration makes it.

## Consequences

### Positive

- "Is this evidence?" has one answer in code, and a test for every event
  type.
- Imagined material (rollouts, counterfactuals) has a class before it has a
  producer, so it cannot arrive unlabelled.

### Negative

- Two names for the journal types exist until the aliases are retired.

### Neutral

- The directory and file layout of the journal is unchanged.

## Alternatives Considered

| Alternative                           | Why Rejected                                                         |
| ------------------------------------- | -------------------------------------------------------------------- |
| Keep "evidence" naming, document rule | The name itself states the opposite of the rule                      |
| Separate journals for evidence        | Splits canonical history; replay and continuity need one ordered log |
| Rename without compatibility aliases  | Breaks readers of old code paths and journals for no epistemic gain  |

## Revisit Conditions

- A channel for testimony or research is built (ADR 0004).
- A producer of counterfactuals or model rollouts is built.

## Relevant Commits / Documents

| Reference                                             | Description                      |
| ----------------------------------------------------- | -------------------------------- |
| `packages/epistemics/.../provenance.py`               | Provenance classes               |
| `packages/epistemics/.../evidence.py`                 | `admit()`                        |
| `apps/cognition/python/person_cognition/admission.py` | Which events are evidence        |
| `packages/persistence/python/person_persistence/`     | Canonical events, legacy mapping |
