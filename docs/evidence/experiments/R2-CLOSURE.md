# R2 closure: interoceptive affect

**R2 is closed** (2026-09-30). This page states what R2 set out to learn,
what the evidence shows, and what it does not. **TESTED IN FIXTURE**
throughout; nothing here is Minecraft evidence beyond the one live
spot-check, and nothing bears on whether Person feels anything
(`docs/RESEARCH.md`).

## What R2 asked

ADR 0014 (Accepted) let legitimate bodily state (health, hunger, breath)
enter Person's affect. Discrete events became phasic appraisals, and
persistent conditions became tonic pressure integrated over experienced
time. One causal event yields one appraisal, a threat is appraised as onset
and exposure, and idle time is never appraised. The switch `interoception =
off` gives the corrected R1.5 appraisal semantics under the current runtime
(after the phantom-goal fix, ADR 0015), so the two designs can be compared in
one revision.

The predeclared questions: does bodily state alter affect (**state**); when
affect has an opportunity, does interoception alter choices (**behaviour**);
does affect persist and recover coherently in Person's time (**temporal**);
were unchanged decisions insensitive, or did they have no close alternative
(**opportunity**); and what still saturates (**saturation**).

## The evidence chain

| Step                              | Where                                         | Status                                                                       |
| --------------------------------- | --------------------------------------------- | ---------------------------------------------------------------------------- |
| Development, then held-out A to C | `r2-interoception/`                           | historical: produced under the phantom `SECURE_FOOD` defect                  |
| Held-out D                        | `r2-interoception/heldout/d-setback-INVALID/` | INVALID: zero-time livelock (ADR 0015)                                       |
| Correctness fixes                 | ADR 0015, ADR 0016                            | zero-time progress, no phantom goals, bounded snapshots, hostiles obey walls |
| V2 protocol and fresh worlds      | `experiments/v2/PROTOCOL.md`, A2 to D2        | predeclared and frozen before any run                                        |
| V2 development rerun              | `v2-development-fixture-realism/`             | clean: 240 valid                                                             |
| **V2 held-out, run once**         | `v2-heldout/`                                 | **the confirmatory result:** 240 valid, every invariant held                 |

Only V2 is confirmatory. The earlier results explain how the design got
here; they are not pooled with it.

## What V2 shows

- **State: supported, and observed consistently across the held-out
  classes.** In A2, B2 and C2, R2 affect ends the long horizon near valence
  -0.35 and unease 0.15 under persistent hunger, with conditions pressing for
  78 to 100% of the run; R1.5 appraisal ends near 0. In D2, where Person was
  hurt, R2 reaches -0.71 against -0.58. The negative control held everywhere:
  recording affect without letting it act changed no decision.
- **Behaviour: the development effect did not replicate in B2.** B2, the
  primary endpoint: NO REPLICATION OBSERVED. Every seed had
  protocol-defined opportunities, but no priority choice changed and no
  trajectory diverged; R1.5 appraisal changed none either. A protocol-defined
  opportunity is a decision that affect's largest possible swing could
  reorder. In B2 there were 9 per seed, all at ticks 150 to 166 just after the
  home project was adopted, and all the same pair: the tools goal (320) above
  the storage milestone (300), a margin of 20 against a largest possible swing
  of 50. The relative bias affect actually applied at those decisions ranged
  from 0 to -4.37, **toward the leading tools goal**, not the runner-up; the
  largest bias applied anywhere in B2 was 9.46. (The mean margin of 77.5
  covers all multi-candidate decisions, not only the opportunities.) The
  earlier held-out B (historical) showed the same pattern. A2's validated wide
  margin correctly showed no change. V2 therefore did not demonstrate an
  affect-driven priority reorder.
- **Temporal:** tonic affect holds while a condition holds (it does not
  "settle" under persistent hunger) and relaxes when the condition ends;
  cadence invariance is tested exactly. Nothing in V2 contradicts this. D2 is
  the only held-out class that exercised bodily setback and recovery, and all
  five of its seeds satisfied that gate.
- **Opportunity:** most unchanged decisions had no close alternative at all.
  C2 produced no exploration or priority opportunity, so the exploration
  channel is **untested** on held-out data; it was nearly untested in
  development too (one opportunity).
- **Saturation:** V2 did not reproduce the duplicate-appraisal artifact seen
  in the earlier design: no identical appraisal records in any run.
- **Threat:** where a threat exposure occurred on held-out data (D2 seed 203),
  R2 appraised exactly one onset and no spurious repetition. Four of five D2
  seeds had no threat exposure: UNTESTED, not negative. Pre-ADR-0016
  development D also exercised this channel, but under the superseded hostile
  physics, so it is not confirmatory.

## Conclusion

Interoception gives Person's affect a time-coherent representation of the
bodily signals R2 exposes, and V2 did not reproduce the specific
duplicate-appraisal artifact seen in the earlier design. The affect-state
effect was observed consistently across the held-out classes.

The development behaviour effect did not replicate in B2. The
protocol-defined opportunities were present in every seed, but no priority
choice changed and no trajectory diverged. Because B2's five seeds produced
the same trajectory, this is one unique held-out trajectory reproduced five
times, not five independent behavioural replications. C2 produced no
exploration opportunity, so that channel remains untested.

R2 therefore closes with held-out support for interoceptive affect as state,
and without held-out evidence that it changes behaviour in the channels V2
successfully exercised.

## Limits that bound this conclusion

- **Seeds did not vary every world.** In B2, A2, development B and
  development D, all five seed labels produced behaviourally identical runs:
  the same decisions, final affect, health and opportunity counts, checked
  per condition and horizon; not checked byte for byte. So the five-seed count
  there is not five independent trajectories: for B2 it is one unique
  trajectory reproduced under five seeds. C2, D2 and development A and C did
  vary with seed.
- One learner setting per class, one world per class and split, and the
  fixture only.
- Held-out threat evidence rests on one D2 seed. D3, a setback world that
  reliably delivers an experienced encounter under honest physics, is future
  work.
- The kernel still orders `flee` from inside a sealed shelter; stand-fast is
  a deferred safety-model decision.
- Affect's bias is capped at 25 by ADR 0010. Whether a larger or state-driven
  influence on choice is desirable is a design question R2 was not allowed
  to tune, and did not.

## What R2 leaves in place

ADR 0014's architecture stays Accepted and in use, with R2's parameters frozen.
The B2 result does not open another affect-tuning cycle. Any future attempt
to make affect matter for behaviour is a new research step: new predeclared
questions, new held-out worlds (the generators exist), and its own decision
on how affect may bias choice.
