# Experiment evidence

Results of `person experiment` runs (ADR 0013), preserved because `runs/` is
not tracked. Each directory holds the plan's per-run metrics (`metrics.csv`),
the comparisons and per-run metadata (`results.json`, decision traces
omitted), and the printed summary (`summary.txt`). Absolute paths are
replaced by `<repo>`. Every run can be repeated exactly from its commit, plan,
condition and seed.

**All of this is TESTED IN FIXTURE.** None of it is Minecraft evidence, and
none of it bears on whether Person feels anything (`docs/RESEARCH.md`).

## R1: affect modes, 2026-09-29

> **Superseded for scientific comparison (operator decision, 2026-09-29).**
> Every R1 run was affected by at least one correctness defect fixed during
> R1.5 (the lost episode end, the repeated re-block appraisal, the abandoned
> project's lingering goal). These results are kept as the historical record;
> the first trustworthy affect baseline is the R1.5 state at `5548bbd`, and no
> effect-size claim should rest on the numbers below.

Plans `experiments/r1-affect-modes.json` (learning off, commit `aaac2bd`) and
`experiments/r1-affect-modes-supervised.json` (learning supervised, commit
`cc5f408`), both with a clean tree. The vertical-slice fixture world, world
seeds 1 to 10, 60 decisions per run, fresh evidence for every run. Conditions:
P0 affect off, P1 affect record-only, P2 affect active (ADR 0010 behaviour).

### What the runs show

- **The negative control holds.** P0 and P1 made the same 60 decisions on all
  10 seeds, in both plans. Affect that is appraised and journalled but not
  consumed changed no decision.
- **Active affect changed decisions on 1 seed of 10**, in both plans (seed 4,
  from decision 15). On the other 9 seeds P1 and P2 made identical decisions.
- **Where it did, the change was a protective near choice.** On seed 4, just
  after a hostile forced an emergency, P2 pursued its project's storage
  milestone (base priority 300) ahead of making tools (base 320), where P1
  made tools. P2's unease and low sense of control raised the protective
  milestone by 12.5 and lowered the outgoing tools goal enough to reverse the
  20-point gap. Its episode then took longer
  (8016 against 4488 ticks), lost more food (14 against 5) and less health
  (3 against 5), searched less (7 against 13 searches) and later abandoned
  its project where P1's was interrupted and resumed. One seed is an
  anecdote; these numbers describe it and establish no trend.
- **Affect is active nearly everywhere and decisive almost nowhere.** P2
  adjusted a goal's priority on 43 to 58 of 60 selections per run, by up to
  the ±25 bound. The bound is well inside the gaps between the tiers of need
  (ADR 0010), so it reordered a choice only once.
- **Exploration tolerance had nothing to reorder.** With the learner
  supervised, P1 and P2 explored equally often (13.8 against 13.7 exploring
  decisions per run) although P2's tolerance was below 1: most decisions
  offered a single candidate routine.
- **The state drifts negative and saturates.** Across P1 and P2, final
  valence averaged about -0.2 and final control about -0.5; on three seeds
  valence ended at -0.94 or lower, and on one both reached -1. Failures,
  kernel overrides and harm are appraised more strongly than success in the
  ADR 0010 table, and 60 decisions is well under the control half-life. The
  bias then sits at its bound for most of a run.

### What they do not show

- Anything about minds, feelings or experience.
- That affect helps or harms survival: no condition died, and the one
  divergent seed moves metrics in both directions.
- Anything beyond this world, these seeds and 60 decisions per run.

### What they suggest for the next increment

The harness can detect a single changed decision and separates it cleanly
from its control. With the current appraisal table and bound, affect is
almost always saturated negative and almost never decisive. Before richer
appraisal (R2) is judged, the same harness should be run on worlds and lengths
where near-tied choices are common, so that an effect has room to appear.

## R1.5: affect benchmark characterisation, 2026-09-29

Four development worlds, three horizons, P0/P1/P2 on five seeds, after four
correctness fixes. The answers to the R1.5 questions, the bugs and their
evidence are in `r1.5-benchmarks/README.md`. Among them: R1's single divergent
seed and its saturation both ran on the code before those fixes, so R1's
numbers describe that code, not the current one.
