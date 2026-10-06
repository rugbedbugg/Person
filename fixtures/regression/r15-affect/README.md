# R1.5 affect references: HISTORICAL, pre-phantom-fix

Recorded at `5548bbd`, before any R2 change. **Immutable: never re-record or
edit these files.**

They include a defect: `SECURE_FOOD` was queued and completed again at every
observation at food 16 and 17, each time appraised as
`goal_complete_secure_food`. The corrected baseline, which the current code
must reproduce exactly, is `../r15-affect-corrected/` (ADR 0015 branch).

The bridge between the two is pinned by
`tests/integration/r15-reference.test.ts`: the same decisions, the same goal
choices and base priorities, and the same appraisals minus exactly those
phantom completions (B 150 → 140, C 54 → 41, D 52 → 39). Affect bias differs
in C and D because the phantom successes are gone.

The R2 results in `docs/evidence/experiments/r2-interoception/` were produced
under this defect and are historical in the same sense.
