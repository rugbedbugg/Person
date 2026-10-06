# R2: interoceptive affect

ADR 0014, 2026-09-29. **TESTED IN FIXTURE.** **Historical:** every run here
was produced under the phantom `SECURE_FOOD` completion defect, fixed on the
ADR 0015 branch (see finding E and `fixtures/regression/r15-affect/README.md`).
Clean R2 evidence needs a fresh run. Nothing here is Minecraft
evidence (the live spot-check is recorded separately, below), and nothing
here bears on whether Person feels anything (`docs/RESEARCH.md`).

## What was run

Four conditions on every world, seeds and horizons as in R1.5 (short 6000,
medium 24000, long 72000 experienced ticks):

| Condition | Affect      | Appraisal                    |
| --------- | ----------- | ---------------------------- |
| P0        | off         | none                         |
| A15       | active      | R1.5 (`interoception = off`) |
| R2rec     | record-only | R2                           |
| R2act     | active      | R2                           |

- **Development** (`experiments/r2/development/`, commit `2573e03`, clean):
  the four R1.5 development worlds, seeds 1 to 5. Every R2 parameter was
  chosen here and none was changed by these results.
- **Held-out** (`experiments/r2/heldout/`, commit `e26fc0a`): the frozen R1.5
  held-out worlds, seeds 101 to 105, run once after the parameters were frozen
  in `42f5cd6`. Nine held-out A runs recorded a dirty tree: documentation files
  (`TRACEABILITY.md`, `docs/CURRENT_STATE.md`, this directory's parent README)
  were being edited while they ran; the code was `e26fc0a` exactly. The edits
  were stashed as soon as that was noticed.

Files: per world, `metrics.csv`, `results.json` (plan, bounds, comparisons,
metadata, distributions; traces omitted) and `summary.txt`;
`pooled-development.txt` and `pooled-heldout-a-c.txt` pool them.

## Held-out D is invalid

**Held-out D is INVALID and NOT INTERPRETABLE FOR R2.** It is kept, it is not
hidden, and it is not replaced by a rerun in this report. See
`heldout/d-setback-INVALID/README.md`.

In short: at tick 6000 the held-out world spawns a skeleton six blocks away
and out of Person's sight. It interrupts an idle `wait_safely` legitimately.
From the next decision on, every `wait_safely` is accepted, then interrupted
by the skill's own `threat_appeared` check after 0 ticks; the fixture's clock
advances only while skills run, so it never advances again, and Person, who
cannot perceive the skeleton, submits the same idle wait forever. It happens
under P0, affect off, so it is not an affect result. The medium and long runs
that completed each spent 4969 of their 5000 decisions at tick 6000. The runs
still in progress were stopped at 21:39:54 +05:30 on 2026-09-29 once the
failure was reproduced under P0. The defect is fixed separately.

## Findings

Pooled over five seeds. "Opportunity" and "changed" are as in R1.5.

### A. State: does legitimate bodily state alter affect?

Yes, substantially, in both splits.

- R2 affect follows the body's conditions. Over the long horizon Person grows
  hungry in every world and stays hungry for most of the run; R1.5 affect is
  blind to it. Final valence, long horizon, R1.5 against R2: development A
  0.00 / -0.35, B 0.00 / -0.35, C 0.00 / -0.35, D 0.00 / -0.41; held-out A
  0.00 / -0.35, B 0.00 / -0.35, C -0.20 / -0.48. Conditions pressed for 78 to
  100% of the long horizon.
- Threat is one onset per exposure: in development D, R1.5 appraised the
  encounter 7 times, 12 ticks apart; R2 once.
- One act is one appraisal: moments with several appraisals fell from 52 to 2
  per run in development B. What remains are distinct events at one moment,
  mostly eating, which is both an action's outcome and a recovery from hunger.
- The body never moved `control`, as required: tonic pressure has no control
  term. Control differs between R1.5 and R2 only through R2's other changes,
  consequences grouped into one appraisal, idle excluded, and harm no longer
  touching control.
- Held-out threat was not exercised: the only held-out world with a threat is
  D.

### B. Behaviour: when affect has an opportunity, does interoception alter choices?

In development, yes; held-out, no.

- Development B (near tie): R1.5 active affect changed 9 of 10 opportunities,
  R2 9 of 11, and A15 and R2act diverged from each other on 5 of 5 seeds at
  every horizon: interoception sends the run down a different path.
- Held-out B offered 45 opportunities in each active condition and neither
  R1.5 nor R2 changed any. The opportunities are one pair: the tools goal at
  320 (Person starts without a pickaxe) above the home project's storage
  milestone at 300. Reversing it needs affect to lift the protective milestone
  20 relative to the outgoing tools goal. At those decisions (R2 active, seed 101) the relative lift affect actually applied ranged from -4.4 to 0: the
  affect Person had then leaned, if anywhere, toward tools. **The development
  behaviour effect did not replicate on the held-out variant.**
- Everywhere else neither appraisal changed a decision: A, C and D offered no
  priority opportunity in either split; the exploration channel changed
  nothing (one opportunity in development C).

### C. Temporal: coherent persistence and recovery in Person time?

Yes.

- Tonic affect is exactly invariant to observation cadence (tested), and
  settles toward the level conditions set, not toward zero: under persistent
  hunger valence does not settle (reported as -1, "does not settle while the
  condition holds"), and it recovers when the condition ends.
- In development D, after the encounter R2 unease settled back toward its
  hunger-driven level within the medium horizon while valence stayed where the
  hunger held it; R1.5 settled fully because it saw no hunger.

### D. Opportunity: were unchanged decisions insensitive, or were there no close alternatives?

Mostly no close alternatives. Development A, C and D and held-out A and C
offered affect no priority opportunity at all; unchanged decisions there say
nothing about sensitivity. Held-out B is the informative case: close
alternatives existed (45 opportunities) and affect, as it was, did not reach
them.

### E. Saturation: after structural duplication, what still saturates and why?

- The structural sources are gone: no identical records, one threat onset per
  exposure, one appraisal per act, no idle appraisal.
- What remains is phasic accumulation from genuinely repeated events:
  development B's early run of successes and completions keeps valence and
  control near +1 for 43 to 64% of the short horizon, in R1.5 and R2 alike;
  held-out C spends 17% of the long horizon near a bound in both appraisals.
  These are properties of the ADR 0010 phasic table, not of R2. **Read B's
  figure with a caveat:** the live spot-check found `SECURE_FOOD` proposed at
  food 16 and 17 while already complete, so it is appraised as a completed
  goal at every observation. Some of B's early positive accumulation may be
  that defect rather than genuine success; it is to be re-measured after the
  fix.
- Tonic pressure never drives a dimension to a bound: its offsets are capped
  well inside the range.

## Limits worth keeping in view

- Live, only observation v8 and a weak hunger signal were exercised (see
  `docs/evidence/dedicated-server/2026-09-29-r2/`).

- In development B and D all seeds produce the same run.
- Breath never ran low in any fixture world: the fixture has no water. Breath
  appraisal is tested only by the unit and integration tests.
- Health vulnerability was exercised only in development D.
- One world per class, one learner setting per class, as in R1.5.
