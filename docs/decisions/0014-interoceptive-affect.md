# ADR 0014: Interoceptive affect, phasic events and tonic conditions

**Status:** Proposed
**Date:** 2026-09-29
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Operator decision:** research track R2: legitimate bodily state enters
affect; discrete events and persistent conditions are separated; tonic
pressure integrates in experienced time; one causal event is one appraisal;
a persisting threat is onset plus exposure; the idle placeholder has no
affective meaning; nothing downstream of affect changes (2026-09-29)

---

## Context

ADR 0010 gave Person a small affect appraised from events. R1.5 (ADR 0013)
measured it and found that most of what it recorded was not experience but
bookkeeping: the same visible threat was appraised again at every
observation, so its weight depended on how often Person looked; one act that
completed three goals was appraised three times; and the idle placeholder
goal, which is scheduling infrastructure, was appraised as a goal. Meanwhile
the body reached affect only as health lost between observations: being
hungry, badly hurt or short of breath moved nothing.

R2 adds the body and removes the bookkeeping. It changes what affect is
formed from, not what affect may do.

## Decision

### What affect may feel

1. **Legitimate interoceptive inputs only.** Health (reserve and trend), food
   (reserve and trend) and breath, as the body reports them to cognition. The
   Minecraft mechanics a player is not shown, saturation and exhaustion, are
   not given to cognition at all: saturation leaves the `Observation`
   (`observationVersion` 8), and nothing replaces it. Hidden saturation that
   changes while everything Person can perceive stays the same cannot move
   affect.
2. **Breath is a body sense, coarsely.** Raw air, a server tick counter, is
   replaced in the `Observation` by `breath`, the ten bubbles a player sees.
   Breath says that breath is running low; it says nothing about water.
3. **The body bears on valence and unease, not on control.** Control remains
   whether Person's own attempted actions seem to work. Recovering health, or
   a hunger that passes because time passed, is not evidence that an action
   worked.

### Events and conditions

4. **Phasic and tonic are distinct.** A phasic appraisal answers a bounded
   event or transition: harm taken, an action's outcome, a goal reached or
   blocked, a project's transition, a threat appearing or growing, hunger or
   breath crossing into a worse band or recovering. Tonic pressure answers an
   ongoing condition: being hungry, badly hurt, short of breath, or in
   perceived danger.
5. **Tonic pressure integrates in experienced time.** A condition shifts the
   level each affect dimension settles toward, and the state relaxes toward
   that level with the dimension's own half-life, in Person's experienced
   time. Between two observations the condition in force is the one last
   perceived. The same trajectory observed twice as often produces the same
   affect: tonic affect never depends on how often Person observes.
6. **Tonic pressure is bounded and ends with its condition.** Each
   condition's contribution is capped, and so is their sum; when a condition
   clears, its pressure stops and ordinary decay and recovery proceed.
7. **"I was hurt" and "I am still badly hurt" are different.** Damage is one
   phasic appraisal of the health lost; remaining low health is tonic
   vulnerability. Nothing else appraises the same change.

### One event, one appraisal

8. **One causal event is appraised once.** An action's outcome and every goal
   completed or blocked and every project transition that follows from it
   form one appraisal, which lists all of those consequences in its record.
   Its magnitude is the action's own appraisal plus the strongest good and the
   strongest bad consequence; it is never multiplied by the number of goals a
   single act satisfied. A search's conclusion and the goal it blocks are one
   event in the same way. Consequences with no action or search behind them,
   in one observation, are one event.
9. **Event identity is cognitive.** Events are identified by what cognition
   has: the decision whose outcome was reported, the search that concluded,
   the observation in which a change was perceived. No runtime entity
   identity is used (C4 stays open).
10. **A persisting threat is onset plus exposure.** Perceived threat is
    aggregated to one intensity (none, present, how close). Its appearing is
    one phasic onset; its growing past what this exposure has already reached
    is one phasic escalation; its continuing is tonic pressure; its clearing
    ends the exposure, and a later threat is a new onset. No hostile is
    tracked individually.
11. **The idle placeholder has no affective meaning.** The goal the scheduler
    uses when nothing is wanted is not appraised: not when queued, blocked,
    completed or kept.

### What does not change

12. Affect's authority is unchanged: the ±25 priority bias, the exploration
    tolerance, their bounds, the emergency exemption and the three affect
    modes of ADR 0013. Memory salience, safety, the capability boundary,
    temperament, social affect and any self-model are untouched.

### Research switch

13. **`[affect] interoception = "on" | "off"`**, default `on`. `off` is a
    frozen research baseline that reproduces R1.5 appraisal exactly, its
    duplications included, so R1.5 and R2 can be compared inside one code
    revision; a test checks the reproduction against reference runs recorded
    at `5548bbd`. The two settings share the appraisal and state code; the
    switch is consulted only where R2 contributes (tonic pressure, grouping of
    consequences, the idle exclusion, threat onset and exposure, body
    transitions). It is independent of the affect mode.
14. **The causal record grows.** Each tonic update is journalled as
    `affect_tonic` (journal schema v10) with the pressures, the resulting
    offset, the state before and after, and the experienced time it covered;
    phasic appraisals record their cause and consequences. The affect record
    is rebuilt from both.

Weights, band thresholds, caps, tonic coefficients and recovery constants are
implementation parameters, chosen on development worlds only and frozen before
any held-out evaluation.

## Consequences

### Positive

- Affect reflects the body Person has, and a sustained condition keeps
  weighing on it without a stream of repeated events.
- Affect no longer depends on observation cadence, on how many goals one act
  touched, or on the scheduler's idle bookkeeping.
- R1.5 and R2 can be compared in one revision.

### Negative

- Observation version 8 removes two fields; anything reading `saturation` or
  raw `air` from an observation must change (only operator tooling did).
- A journal record per observation while a condition persists.
- `interoception = off` deliberately keeps R1.5's duplications for
  comparison; it is not a supported way to run Person.

### Neutral

- Journal schema v10.

## Alternatives Considered

| Alternative                                       | Why rejected                                                                                          |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Keep saturation in the observation, unused        | A value cognition receives is a value some later code can read; the rule is that it never arrives.    |
| Tonic pressure as a fixed impulse per observation | Exactly the cadence dependence R2 removes.                                                            |
| Integrate tonic pressure as an unbounded rate     | Accumulates without limit under a steady condition; an equilibrium offset is bounded by construction. |
| Deduplicate by hostile or target identity         | Needs referents Person does not have (C4).                                                            |
| Give idle a psychological meaning ("boredom")     | Invents a goal to have something to appraise; idle is infrastructure.                                 |

## Revisit Conditions

- R3 adds anticipation: predicted bodily states may add pressure.
- A body sense beyond health, food and breath becomes legitimate.
- Whether several goals satisfied by one act should matter more is tested
  explicitly (the consequences are recorded for that).

## Relevant Commits / Documents

| Reference                                    | Description                           |
| -------------------------------------------- | ------------------------------------- |
| ADR 0010, ADR 0013                           | Affect, its modes and its measurement |
| ADR 0006                                     | Experienced time                      |
| `docs/evidence/experiments/r1.5-benchmarks/` | The R1.5 findings R2 answers          |
| `fixtures/regression/r15-affect/`            | R1.5 reference runs                   |
