# ADR 0013: Affect modes and a reproducible experiment harness

**Status:** Accepted (operator, 2026-09-29)
**Date:** 2026-09-29
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Operator decision:** research track R1: an explicit affect mode (`off`,
`record_only`, `active`), a deterministic seeded batch runner over the fixture
world, and a first P0/P1/P2 matrix; no new affect psychology (2026-09-29)

---

> **Operator decision, 2026-09-29: accepted.** The accepted architecture is
> the three affect modes, one shared appraisal and state-update path for
> `record_only` and `active` with only the explicit consumption points
> differing, deterministic seeded runs, reproducibility metadata, and metrics
> reported individually rather than as one score. World sets, seeds, run
> lengths, the metric list and any thresholds are experiment parameters.

## Context

ADR 0010 gave Person a small functional affect, and it has been on in every
run since. There is no way to ask what it changes: no run of Person without
affect exists to compare against, and nothing runs the same world many times
and measures what happened. Every claim about affect is therefore an
anecdote.

The research programme that follows (richer interoception, anticipation,
learned dynamics, a bounded self-model) needs a control condition first, and
a measurement procedure that cannot itself leak privileged information into
Person.

## Decision

### Affect modes

1. **Three modes.** `off`, `record_only`, `active`, set in the Person
   configuration as `[affect] mode`. Unset means `active`, which is the
   behaviour since ADR 0010. Shipped examples state the mode explicitly.
2. **`off`.** No appraisal is applied and the affect state does not evolve,
   decay included: no `affect_appraised` record is written, and the recorded
   state is left exactly as it was. Affect contributes nothing to any
   decision. Everything else in cognition is unchanged.
3. **`record_only`.** The same appraisal and state-update code as `active`,
   and the same `affect_appraised` records. Affect contributes exactly zero
   to goal and project priority, exploration, risk tolerance and experiment
   value.
4. **`active`.** Unchanged from ADR 0010.
5. **One boundary.** `record_only` and `active` differ only where affect is
   consumed. `Affect` has exactly two outputs that reach a decision, the
   priority bias and the exploration tolerance, and both return their
   neutral value (0 and 1) unless the mode is `active`. There is one
   appraisal implementation; the mode never selects between two.
6. **Not in the protocol.** The runtime does not learn the mode and no
   protocol message carries it (ADR 0010, decision 7). Cognition reads it
   from its own configuration, like its learning settings.
7. **Recorded.** The mode Person ran under is written on `episode_started`,
   so every journal says which condition produced it. It is not written on
   `affect_appraised`, so `record_only` and `active` journals of the same
   experience are identical there.

### The experiment harness

8. **Research tooling, outside Person.** `person experiment` runs a plan: a
   fixture world, a fixed Person configuration, a set of world seeds, a set
   of conditions (affect modes) and a decision budget. Every (condition,
   seed) pair is an independent run with a fresh evidence directory, so no
   run inherits another's experience.
9. **The seed varies the world only.** It is the fixture world's own seed,
   which lays out its resource clusters. It is never given to cognition,
   which receives only what it would in any fixture run.
10. **Instrumentation is not experience.** Metrics are computed after a run
    from the episode report (the runtime's engineering record) and the
    evidence journal. The harness may read privileged engineering data;
    nothing it reads or computes is sent to Person, and no Person code
    imports the harness.
11. **Reproducible.** Each run records the commit, whether the tree was
    clean, the plan, the configuration and world definition it used with
    their hashes, the seed, the condition, the skill-library revision and
    the cognition command, so any run can be repeated exactly. The same plan
    at the same commit yields the same metrics.
12. **No aggregate score.** Metrics are reported one by one, per run and per
    condition. There is no single "human-likeness" or fitness number, and
    nothing is optimised against the metrics.
13. **Negative control first.** P0 (`off`) and P1 (`record_only`) must make
    the same decisions on the same seeds. The harness reports every decision
    divergence between them; if any exists, it is a leak to investigate
    before any P1-versus-P2 result is read.

### Claims

14. Results may support claims of the form "persistent affect causally
    changes how decisions are organised over time under these fixture
    conditions". They cannot establish that Person feels emotion, is
    conscious, or has phenomenal experience (`docs/RESEARCH.md`).
15. New research code names affect functionally (`affect_mode`,
    `affective_state`, `apply_appraisal`). Existing names are not renamed in
    this phase.

## Consequences

### Positive

- The effect of affect on behaviour becomes a measurable difference between
  conditions rather than a reading of one journal.
- A leak of affect into decisions it should not reach is detectable as a P0
  and P1 divergence.
- Later affect variants (R2 onwards) are compared on the same footing.

### Negative

- A run of `off` leaves the affect record untouched, so a later `active` run
  resumes from the old state and decays across the whole gap at once.
- The fixture world has few situations where affect can matter: it adjusts
  only near-tied goal priorities and the evidence policy's exploration.
  Small or zero effects are an expected result, not a failure.
- Hunger, harm and recovery metrics are computed from the runtime's
  per-decision deltas, not from continuous sampling.

### Neutral

- Journal schema unchanged: `affect_mode` is an added payload field on an
  existing event type.
- The runtime and the safety kernel are unchanged.

## Alternatives Considered

| Alternative                                     | Why rejected                                                                                          |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Carry the mode in `SessionHello`                | The runtime has no use for it, and ADR 0010 keeps affect out of every protocol message.               |
| Implement `record_only` as a second code path   | Two appraisal paths could drift; the negative control would then test the fork, not the consumption.  |
| Vary the cognition seed instead of the world    | Cognition is deterministic and uses no random numbers; only the world has anything to vary.           |
| Sample the body continuously inside the runtime | Adds a hook in the trusted runtime for research; the report's per-decision deltas are enough for now. |
| One composite score per run                     | Invites optimising against it, and hides which behaviour changed.                                     |

## Revisit Conditions

- A metric needs continuous sampling of the body (R2 interoception).
- An affect variant needs its own mode.
- Experiments move to a live world, where runs are not independent.

## Relevant Commits / Documents

| Reference            | Description                              |
| -------------------- | ---------------------------------------- |
| ADR 0010             | The affect this ADR switches             |
| ADR 0006             | Experienced time, which affect decays in |
| `docs/RESEARCH.md`   | Claim discipline                         |
| `docs/EVALUATION.md` | What the suite proves                    |
