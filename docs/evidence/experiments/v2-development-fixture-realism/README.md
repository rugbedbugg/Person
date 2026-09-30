# V2 development rerun, fixture realism

Step 1 of `experiments/v2/PROTOCOL.md`, repeated at the new candidate revision
`9dcfc69` after ADR 0016 (hostiles obey walls), on 2026-09-30. It replaces
`../v2-development/` (candidate `dd4f00a`, superseded, kept as it is) as the
development baseline for V2. Seeds 1 to 5, conditions P0, A15, R2rec and
R2act, horizons 6,000, 24,000 and 72,000 experienced ticks. **TESTED IN
FIXTURE.** Development data: nothing was tuned from it.

## Protocol checks

`protocol-check.txt`:

- All 240 runs are valid: none invalid, none censored, every one at `9dcfc69`
  with a clean tree.
- Hard invariants hold: the negative control diverges nowhere, and nothing
  changed without an opportunity.
- Development A: no priority change under R2act.
- The B criterion, applied descriptively: REPLICATED, 5 of 5 opportunity seeds,
  5 of 5 changed, 5 of 5 divergent.

## What changed with honest hostile physics

- **A, B and C:** the same as at `dd4f00a` in every figure checked (none has a
  hostile).
- **D no longer contains its setback.** In every condition and horizon, the
  zombie arrives while Person is in its shelter, cannot reach it or hit it,
  and is never seen: 0 threat appraisals and 0 health lost. At `dd4f00a` the
  same world gave 7 threat appraisals under A15 and one onset under R2, all
  from the zombie walking and hitting through the walls. R2's long-horizon
  valence of -0.35 in D now comes from hunger alone.

So in development, class D's threat, setback and recovery questions are
**untested**: the encounter the world schedules is not experienced. That is a
result about the world under honest physics, not something to tune away, and
it bears on whether D2 can answer those questions.
