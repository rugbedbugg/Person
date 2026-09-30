# V2: the confirmatory R2 suite

**Frozen on 2026-09-30, before any V2 held-out run.** Agreed with the
operator and the external reviewer. The held-out worlds are
`experiments/benchmarks/heldout-v2/` (A2, B2, C2) and
`experiments/benchmarks/heldout-d2/` (D2).

This fixture suite is not the first autonomous Person experiment in
Minecraft. That one still needs the operator's explicit approval, whatever
V2 shows.

## Frozen configuration

- **Code:** a candidate revision, the commit that adds this protocol. If the
  development rerun exposes a correctness or infrastructure defect that needs
  any code change, the candidate is superseded. The defect is fixed and the
  reason recorded; A2 to D2 are statically revalidated (never redrawn);
  development is rerun; and a new candidate is frozen, all before any V2
  held-out data is touched. R2's parameters stay frozen throughout:
  development findings may justify correctness fixes, never tuning.
- **Held-out plans:** `experiments/r2/heldout/a2-wide-margin.json`,
  `b2-near-tie.json`, `c2-exploration.json` and `d2-setback.json`.
- **Conditions:** P0 (affect off), A15 (active, interoception off), R2rec
  (record-only, interoception on) and R2act (active, interoception on).
- **Seeds and horizons:** seeds 201 to 205; horizons of 6,000, 24,000 and
  72,000 experienced ticks; at most 5000 decisions; the learner as each plan
  says (C supervised, the rest off).

## Run order

1. **Development rerun** at the candidate revision: `experiments/r2/development/*`,
   seeds 1 to 5, every condition and horizon. It is development data: inspect
   it freely for correctness and infrastructure.
2. **Final freeze:** if development is clean, record the exact commit and a
   clean tree, verify every manifest, plan and hash, run the full test suite,
   and confirm A2 to D2 are unconsumed. Then stop and report readiness to the
   operator.
3. **V2 held-out, once,** on the operator's authorization: each of the four
   plans with `--heldout`. It is never rerun.
4. **Optional, labelled POST-FIX REPLICATION:** old held-out A to C at the
   frozen revision. Never part of V2's confirmatory evidence.

## Validity

- A run is **invalid** if its episode ended `runtime_livelock`,
  `runtime_error` or `disconnected`, or if it records a dirty tree or a commit
  other than the frozen one.
- A run that reaches the 5000-decision ceiling before its horizon's
  experienced time (episode reason `decision_budget_reached`) is
  **CENSORED_DECISION_LIMIT**. It is kept, and excluded from any measure that
  claims to describe the completed horizon.
- Invalid and censored runs are kept and reported. They are never rerun,
  replaced or substituted. A world × condition × horizon cell with any
  invalid or censored seed is reported **incomplete**, with its valid seeds
  shown individually.
- **Hard invariants:** each violation is a measurement or boundary defect,
  not an affect result.
  - negative control: P0 against R2rec, 0 of 5 divergent seeds, in every
    world and horizon;
  - `priority_changed_without_opportunity` = 0 and
    `exploration_changed_without_opportunity` = 0 everywhere;
  - A2: R2act changes no priority choice, since its validated margin exceeds
    affect's largest swing.

## Questions and measures

Reported per world and horizon, over the five seeds. Development and
held-out are kept apart, V2 is never pooled with the historical R2 results,
and there is never one score.

| Question    | What it asks                                                            | Measures                                                                                                                                |
| ----------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| State       | Does legitimate bodily state alter affect?                              | `affect_*_final`, `affect_*_tonic_time_fraction`, `affect_*_tonic_offset_mean`; R2rec and R2act against A15                             |
| Behaviour   | When affect has an opportunity, does interoception alter choices?       | the B2 criterion below; priority and exploration opportunities and changes; A15 against R2act divergent seeds                           |
| Temporal    | Does affect persist and recover coherently in Person's time?            | `affect_*_ticks_to_settle_after_last_push`; recovery after D2's encounter                                                               |
| Opportunity | Were unchanged decisions insensitive, or had they no close alternative? | `priority_opportunity_rate`, `exploration_opportunity_rate`                                                                             |
| Saturation  | What still saturates, and why?                                          | `affect_*_near_bound_fraction`, saturation episodes, `affect_identical_appraisal_records` (expected 0), moments with several appraisals |
| Threat (D2) | Is a threat felt as onset and escalation, not repetition?               | per exposure: exactly one onset, and zero or more legitimate escalations                                                                |

The worlds' roles: A2 shows that affect cannot alter a validated wide margin,
B2 that it can alter a near tie, C2 the exploration-policy opportunity, and D2
setback, recovery and threat.

## The B2 behaviour criterion

The primary endpoint is the **long horizon (72,000 experienced ticks)**. Short
and medium horizons describe when an effect appears, not whether it
replicated. The unit is the **seed**: opportunities within one seed are not
independent.

For each seed at the long horizon:

- **opportunity seed:** the R2act run has at least one legitimate priority
  opportunity (`priority_opportunities` ≥ 1);
- **changed seed:** the R2act run changed at least one priority decision
  given an opportunity (`priority_changed_given_opportunity` ≥ 1, i.e.
  `priority_changed` ≥ 1 with `priority_changed_without_opportunity` = 0);
- **divergent seed:** A15 and R2act diverge under the harness's
  deterministic comparison.

Classification, descriptive and not a significance claim:

| Result                       | When                                                                                                                                                                   |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **REPLICATED**               | at least 3 of 5 opportunity seeds, at least 3 of 5 changed seeds (all among the opportunity seeds), at least 3 of 5 divergent seeds, and no change without opportunity |
| **NO REPLICATION OBSERVED**  | at least 3 of 5 opportunity seeds and no changed seed                                                                                                                  |
| **MIXED / WEAK**             | at least 3 of 5 opportunity seeds, but only 1 or 2 changed seeds, or the change and divergence criteria disagree                                                       |
| **INSUFFICIENT OPPORTUNITY** | fewer than 3 of 5 opportunity seeds; with none, the behaviour channel was untested in B2                                                                               |

B2's near tie is latent, so failing to reach it is a result, but it is not
evidence that affect had no behavioural effect. Total opportunities,
opportunities per seed, the fraction changed and when in experienced time they
occurred are reported as mechanism diagnostics, not as the replication unit.

## Stop points

- After the development rerun: stop on any invalid run or correctness defect.
- After V2: stop before any interpretive write-up that claims more than the
  predeclared classifications.
- The V2 held-out suite is run once and never rerun.

## Amendments

### 1. Candidate `29d29e5` superseded before any held-out run (2026-09-30)

The final freeze at `29d29e5` was superseded by the operator's decision,
before any of A2 to D2 was run and before any held-out result was inspected.

- **Why:** a known fixture defect. Hostiles walked through solid blocks and
  attacked through them, so D2's health, threat and recovery results would
  partly have measured the artifact.
- **Fixed by ADR 0016:** hostiles obey walls, for movement and for every
  attack, and no kernel, skill, cognition or R2 parameter changed.
- **References:** the R1.5 references gain the fixture-realism baseline, with
  its bridge pinned.
- **Revalidated:** A2, B2 and C2 statically, with records identical to the
  frozen ones; D2 by its manifest and regeneration. None was redrawn.
- **Next:** the development rerun is repeated at the new candidate revision,
  then the final readiness review.
