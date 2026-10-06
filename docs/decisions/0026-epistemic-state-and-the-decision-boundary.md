# ADR 0026: Epistemic state: percepts, beliefs, self-state and the decision boundary

**Status:** Accepted (2026-10-06)
**Date:** 2026-10-03
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Addresses:** `docs/CURRENT_STATE.md`, Known Deviations, C6 (in part)

---

## Context

`PERSON_SPEC` section 26 requires physical truth, perceptual truth, belief,
memory, knowledge and reasoning to stay distinct. Before this decision the
cognition loop had one category for all of them: the latest observation.
Planning facts, goals, the safe envelope, affect appraisal, context
signatures and memory encoding each read the raw observation themselves.
Person could remember having seen coal, but could hold no belief that could
disagree with an observation, because no belief existed apart from it. A
runtime report (Person's own placement ledger: "you built a shelter here")
and a sense ("a zombie is ahead") arrived in the same dictionary and were
used identically.

## Decision

1. **One boundary, crossed once per observation.** The loop hands each
   observation to its environment profile exactly once
   (`CognitiveEnvironment.perceive`), and receives a `PerceptualState`: the
   environment's typed percepts, its tick and message id, and the experience
   key it belongs to. Nothing downstream reads the observation again; an
   architecture test fails if any cognition, planner or policy module indexes
   observation payload fields.

2. **Percepts are channelled by how they are known.** `MinecraftPercepts`
   separates what Person senses (`nearby`, `sky`), its body (`vitals`,
   `inventory`) and what the trusted runtime reports about Person's own
   situation (`home`, `permissions`, `affordances`, `navigation`). Privileged
   environment state has no channel: the profile reads only the observation
   payload, which is already behind the perception firewall (ADR 0002).

3. **Beliefs are persistent, scoped and revisable.** A `FactBelief` has a
   key, a value, a confidence, a basis (its provenance class, ADR 0027), the
   evidence references it rests on, when it was updated and last observed,
   and a `Scope` (`world`, `embodiment`, `environment` or `general`). The
   `BeliefState` is rebuilt from `belief_revised` journal records only, and
   refuses any record whose basis is not world evidence. Freshness (when an
   unchanged belief was last confirmed) is ephemeral and journals nothing, so
   a belief re-confirmed every observation does not flood the journal.

4. **Scope never widens by itself.** Every belief Minecraft forms is
   `world`-scoped: learned in this world. `check_widening` permits one level
   at a time, only with stated evidence, and no code calls it today; an
   architecture test fails if anything but the explicit gate constructs a
   wider scope. Environment-specific knowledge cannot silently become
   environment-general.

5. **Knowledge is not omniscient; promotion is possible but not built.**
   `Knowledge` has two parts that are never merged. Initial knowledge is what
   Person started with: its skill contracts and vocabularies, with source
   `INITIAL_KNOWLEDGE`. Learned knowledge (`Knowledge.learned`) is a tuple of
   `KnownFact`s, each a belief an explicit, evidence-backed promotion would
   produce: it keeps the belief's value, confidence, basis, evidence
   references and scope (never widened), and names the canonical event that
   recorded the promotion. No promotion gate exists, so `learned` is empty
   for Ada, and a test fails if any production code constructs a
   `KnownFact`. What can never become knowledge is settled now: `KnownFact`
   refuses inference, recall, replay, counterfactuals, model rollouts and
   anything without evidence. The gate, when proposed, is its own decision
   and needs no redesign of `Knowledge`.

6. **SelfState is composed, not duplicated.** `SelfState` is assembled per
   decision from the mechanisms that own each part: interoception (body
   reading), lifecycle (life status, world availability), spatial (place
   estimate and home relation), affect, the skill registry (capabilities) and
   identity. It stores nothing of its own.

7. **The decision is made from a `DecisionState`.** Percepts, beliefs (a
   read-only view), self-state, recalled memories and initial knowledge. The
   environment derives planning facts, the safe envelope, goal proposals and
   the decision context from it. Planning facts, the table of what is true
   now, read beliefs for what the runtime reports and percepts for what is
   sensed now, so a remembered resource is never a reachable one. Planning
   as a whole may use memory, but only as the epistemic pipeline supplies it:
   `MemoryStore` → bounded recall by typed cue (made by the loop) →
   `DecisionState.recalled`, or a recall the loop hands over → planning.
   Planning never reaches the memory store, the journal or recall for
   itself, and a recalled episode stays labelled as memory: never a percept,
   never new evidence.

## Consequences

### Positive

- Belief can now disagree with an observation and is revised by evidence,
  with its provenance, scope and references journalled.
- Each consumer that used to parse the observation is now given the part of
  epistemic state it is entitled to.

### Negative

- Two more journal record types to reason about when replaying
  (`belief_revised`, and the scope it carries).

### Neutral

- Only runtime reports form beliefs today (shelter state, home known, owned
  storage and stations, food reserve). Sensed facts still feed planning as
  percepts. Turning sensed facts into beliefs is a later, separate decision.

## Alternatives Considered

| Alternative                                       | Why Rejected                                                                |
| ------------------------------------------------- | --------------------------------------------------------------------------- |
| Keep reading the observation; document the rule   | The rule had no enforcement and was already broken in several modules       |
| A world-model object holding state and prediction | Merges belief, prediction and history again (ADR 0028)                      |
| Store SelfState as its own record                 | Duplicates interoception, affect, lifecycle and spatial; drifts             |
| Promote stable beliefs to knowledge now           | No evidence-backed promotion rule exists; it would be an unaudited shortcut |

## Revisit Conditions

- Sensed facts are to become beliefs (object permanence beyond memory).
- A promotion from belief to knowledge is proposed.

## Relevant Commits / Documents

| Reference                                                      | Description                      |
| -------------------------------------------------------------- | -------------------------------- |
| `packages/epistemics/python/person_epistemics/`                | Beliefs, scope, state types      |
| `environments/minecraft/python/person_minecraft/perception.py` | Minecraft percept channels       |
| `environments/minecraft/python/person_minecraft/beliefs.py`    | What Minecraft admits as belief  |
| `apps/cognition/tests/test_epistemic_boundary.py`              | The boundary in the running loop |
| `PERSON_SPEC.md` section 26                                    | The distinctions                 |
