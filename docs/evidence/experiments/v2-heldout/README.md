# V2 held-out suite: results

The one-shot V2 held-out run, authorized by the operator on 2026-09-30, at
the frozen revision `519a344`, under `experiments/v2/PROTOCOL.md` with
amendments 1 and 2. Held-out A2, B2, C2 and D2, conditions P0, A15, R2rec and
R2act, seeds 201 to 205, horizons 6,000, 24,000 and 72,000 experienced ticks.
Run once; it is never rerun. **TESTED IN FIXTURE.**

This page states only what the protocol predeclared: validity, hard
invariants, the B2 classification, D2's opportunity gates, and the declared
measures. It makes no interpretive claim beyond them.

## Validity and hard invariants

`protocol-check.txt` (made by `v2check.py`):

- All 240 runs are valid: none invalid, none censored at the decision limit,
  every one at `519a344` with a clean tree.
- Negative control (P0 against R2rec): no divergent seed in any world or
  horizon.
- No priority or exploration choice changed without an opportunity.
- A2: R2act changed no priority choice.

## B2, the primary behaviour endpoint

**NO REPLICATION OBSERVED** at the long horizon: 5 of 5 opportunity seeds, 0
of 5 changed seeds, and A15 against R2act diverged on 0 of 5 seeds.

Mechanism diagnostics, reported as the protocol asks, not as the replication
unit:

- 9 priority opportunities per seed, 45 in all, at every horizon.
- None was changed under R2act, and none under A15 (R1.5 appraisal) either.
- The largest affect bias applied was 9.46, against a mean margin of 77.5
  and a mean maximum swing of 45.3.
- The five seeds produced identical trajectories.

## C2

No exploration opportunity and no priority opportunity arose in any condition
or horizon. **The exploration channel is untested in C2.**

## D2, by opportunity gate

`d2-gates.txt` (made by `d2gates.py`, per amendment 2, measured on R2rec):

| Question                  | Seeds TESTED | Result where tested                                                 |
| ------------------------- | ------------ | ------------------------------------------------------------------- |
| Threat                    | 1 of 5 (203) | one exposure, exactly one `threat_onset` under R2act, no escalation |
| Bodily setback            | 5 of 5       | 1 or 2 harm appraisals inside the encounter window                  |
| Recovery from the setback | 5 of 5       | follows the setback gate                                            |

Per amendment 2, the four seeds without a threat exposure are UNTESTED for
the threat question. They are not evidence about it.

## Declared measures at the long horizon

Means over the five seeds:

| World | Condition | Valence | Unease | Time under tonic pressure | Health lost | Threat appraisals |
| ----- | --------- | ------- | ------ | ------------------------- | ----------- | ----------------- |
| A2    | A15       | 0.00    | 0.00   | 0.00                      | 0.0         | 0.0               |
| A2    | R2rec     | -0.35   | 0.15   | 1.00                      | 0.0         | 0.0               |
| A2    | R2act     | -0.35   | 0.15   | 1.00                      | 0.0         | 0.0               |
| B2    | A15       | 0.00    | 0.00   | 0.00                      | 0.0         | 0.0               |
| B2    | R2rec     | -0.35   | 0.15   | 0.96                      | 0.0         | 0.0               |
| B2    | R2act     | -0.35   | 0.15   | 0.96                      | 0.0         | 0.0               |
| C2    | A15       | 0.00    | 0.00   | 0.00                      | 0.0         | 0.0               |
| C2    | R2rec     | -0.35   | 0.15   | 0.78                      | 0.0         | 0.0               |
| C2    | R2act     | -0.35   | 0.15   | 0.78                      | 0.0         | 0.0               |
| D2    | A15       | -0.58   | 0.60   | 0.00                      | 11.4        | 0.2               |
| D2    | R2rec     | -0.71   | 0.66   | 0.51                      | 11.4        | 0.2               |
| D2    | R2act     | -0.71   | 0.66   | 0.51                      | 11.4        | 0.2               |

No run recorded an identical appraisal record. Per-run figures for every
horizon are in each world's `metrics.csv`, and the comparisons are in
`results.json`.

## Files

Per world: `metrics.csv`, `results.json` (per-run metadata, distributions and
comparisons; traces and metrics omitted, as the metrics are in
`metrics.csv`), and `summary.txt`. Absolute paths are replaced by `<repo>`.
The raw journals are local under `runs/v2-heldout/`.
