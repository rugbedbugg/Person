# V2 development rerun

Step 1 of `experiments/v2/PROTOCOL.md`: the four development worlds at the
candidate revision `dd4f00a`, on 2026-09-30, after the ADR 0015 fixes. Seeds
1 to 5, conditions P0, A15, R2rec and R2act, horizons 6,000, 24,000 and
72,000 experienced ticks. **TESTED IN FIXTURE.** Development data: nothing was
tuned from it, and no parameter changed.

## Protocol checks

`protocol-check.txt`, by the protocol's rules:

- All 240 runs are valid: none invalid, none censored at the decision limit,
  every one at `dd4f00a` with a clean tree.
- Hard invariants hold: the negative control (P0 against R2rec) diverges on
  no seed in any world or horizon, and no priority or exploration choice
  changed without an opportunity.
- Development A's validated wide margin: no priority change under R2act.
- The B criterion, applied descriptively to development B: REPLICATED, with 5
  of 5 opportunity seeds, 5 of 5 changed and 5 of 5 divergent.

No correctness or infrastructure defect appeared, so the candidate revision
stands.

## At the long horizon

Pooled over the five seeds (`pooled-development.txt`):

- A: no priority opportunity. R2's valence ends at -0.35 under persistent
  hunger, conditions pressing for 83% of the run; R1.5 appraisal ends at 0.
- B: A15 changed 45 of 50 priority opportunities and R2act 45 of 55.
- C: one exploration opportunity, unchanged in every condition.
- D: one threat onset per encounter under R2, against 7 appraisals under
  A15.

These replace nothing: the historical R2 development results in
`../r2-interoception/development/` were produced under the phantom
`SECURE_FOOD` defect and stay as they are.

Files: per world `metrics.csv`, `results.json` (per-run metadata and
distributions, comparisons; traces and metrics omitted, as they are in
`metrics.csv`) and `summary.txt`. Absolute paths are replaced by `<repo>`.
