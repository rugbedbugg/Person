# ADR 0010: Affect as a bounded bias on cognition

**Status:** Proposed
**Date:** 2026-09-25
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Operator decision:** affect acts on goal/project priority and on exploration
tolerance, bounded; not on memory salience; rule-based; no relationships
(2026-09-25)

---

## Context

`PERSON_SPEC` section 30 asks for affect that is causal rather than cosmetic,
biases cognition and never selects behaviour, and forbids
`if anger > X -> attack`. Phase D gave Person competing goals and projects
whose priorities are close enough for a bias to matter. ADR 0007 (accepted)
says memory salience is not affect, and that stays true here.

## Decision

1. **Appraisal, then affect, then bias.** An experienced event is appraised
   by deterministic rules, the appraisal moves a continuous state, and the
   state biases the ordinary goal and policy machinery. Affect never runs a
   skill and never chooses a goal.
2. **Legitimate inputs only.** Appraisal reads percepts (threats in view),
   the body (health lost between observations), outcomes the runtime
   reported, and Person's own goal, project and search outcomes. It reads no
   snapshot, coordinate, hidden entity, pathfinder state, debug data or
   safety geometry. The same cognitive evidence yields the same affect,
   whatever the hidden world holds.
3. **A small continuous state.** `valence` in [-1, 1] (how things are going),
   `unease` in [0, 1] (threat and harm activation), `control` in [-1, 1]
   (whether Person's own actions seem to work). Deterministic, bounded,
   interpretable.
4. **Appraisal components.** Threat, harm, success and failure, being
   overridden by the runtime (controllability), goal congruence from goals
   completed or blocked and projects progressed, completed or abandoned, and
   search outcomes. No social appraisal. No memory-driven appraisal in this
   foundation.
5. **Bounded priority bias.** A goal's effective priority is its base
   priority plus an affect term within a small fixed bound, recorded
   separately (`base_priority`, `affect_bias`, `priority`). The term is
   generic: a goal's character (protective or outgoing) is read from its
   completion condition, and each dimension pulls on each character with a
   fixed sensitivity. Emergency goals are never adjusted. Affect adds and
   removes no candidates.
6. **Preference, not script.** Nothing maps a state to a project, an
   abandonment, a flight or a rest. Interruption and abandonment remain the
   project and goal machinery's.
7. **Exploration tolerance above trusted safety.** A tolerance factor scales
   the policy's exploration bonus and, below 1, adds weight to risk. It
   reorders routines the runtime would accept. It cannot reach the runtime:
   no protocol message carries affect, and the kernel, the permission gate
   and the protected areas read only the body.
8. **No memory-salience coupling.** Encoding salience, the accessibility
   equation, recall ranking and half-lives are untouched. Any future coupling
   is a separate amendment to ADR 0007.
9. **Decay in experienced time.** Each dimension returns toward baseline with
   its own half-life, measured in Person's experienced time (ADR 0006), so no
   single event changes Person for good and nothing settles while the process
   is not running.
10. **Temperament slots.** Baseline, reactivity and recovery come from a
    temperament, neutral for now, so a later profile changes them without
    touching appraisal.
11. **No threshold-to-action.** An architecture test forbids reading the
    affect state anywhere outside the affect module; only the bias and the
    tolerance leave it.
12. **Causal record.** Every appraisal is journalled as `affect_appraised`
    with its trigger, components, state before, delta and state after
    (journal schema v7). Engineering evidence, not something Person perceives.
13. **Persistence.** The affect record is rebuilt from those events alone,
    and a restart resumes the recorded state. It is not in the placement
    ledger and no runtime snapshot feeds it.
14. **Affect is not belief.** Unease is not knowledge of danger, calm is not
    proof of safety, and no affect value enters the planner's facts.

The bias bound, sensitivities, half-lives, appraisal magnitudes and tolerance
range are current implementation parameters.

## Consequences

### Positive

- Two Persons with the same world and different histories can make different
  near choices, and the journal says exactly why.
- Affect cannot touch authority, memory or belief, by construction and by
  test.

### Negative

- The first appraisal table is hand-tuned and coarse.
- Only near-tied goals are affected; that is deliberate, and it means affect
  is rarely visible.

### Neutral

- Journal schema v7. No protocol change.

## Alternatives Considered

| Alternative                            | Why rejected                                                                                                     |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Discrete emotions as the state machine | Labels are interpretations of state, not the state (spec section 30).                                            |
| An LLM to generate feelings            | Unreproducible and unaccountable; the operator excluded it.                                                      |
| Affect on memory salience now          | Contradicts accepted ADR 0007; deferred to an explicit amendment.                                                |
| An unbounded priority term             | Could replace the drive system and outrank urgent needs.                                                         |
| Affect in the safety envelope's gate   | Would let a feeling close or open what is really a policy judgement; the tolerance factor keeps it a preference. |

## Revisit Conditions

- Social memory exists, and relationships should carry affect (Phase G).
- Memory salience should depend on affect (an ADR 0007 amendment).
- A temperament profile is introduced.

## Relevant Commits / Documents

| Reference                                          | Description                 |
| -------------------------------------------------- | --------------------------- |
| `docs/PERSON_SPEC.md` sections 30-32               | Affect, and its persistence |
| ADR 0006, ADR 0007, ADR 0009                       | Clocks, memory, projects    |
| `apps/cognition/python/person_cognition/affect.py` | The implementation          |
