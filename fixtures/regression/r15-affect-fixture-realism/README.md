# R1.5 affect references: fixture realism, the current baseline

Recorded on 2026-09-30 after ADR 0016: fixture hostiles no longer step into
solid blocks, and no longer hurt Person without a clear line of attack. With
`interoception = off`, the current code must reproduce these exactly.

The earlier generations stay immutable: `../r15-affect/` (historical,
`5548bbd`, phantom `SECURE_FOOD` appraisals) and `../r15-affect-corrected/`
(after the phantom fix, old hostile physics).

## The bridge from `r15-affect-corrected`

- **B and C:** identical in decisions, appraisals and priority adjustments.
  Neither world has a hostile.
- **D:** identical up to decision 40, then different, and the difference is the
  physics change:

| What                           | Old physics (`r15-affect-corrected`)                                            | Fixture realism (this baseline)                                |
| ------------------------------ | ------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| Up to decision 39 (tick 3814)  | identical                                                                       | identical                                                      |
| Affect records 0 to 16         | identical                                                                       | identical                                                      |
| Tick 4009, first physics event | the zombie, two blocks away with the shelter wall between, attacks and lands    | the same attack is refused: no clear line                      |
| Decision 40, tick 4014         | Person, just hit, chooses SURVIVE_IMMEDIATE                                     | Person, unhurt, keeps MAINTAIN_RESERVES                        |
| After the split                | 5 harm and 7 perceived-threat appraisals; the zombie reaches Person and is seen | none: the zombie stays outside, unseen, and never lands a blow |

The kernel orders `flee` in both, because a hostile is within contact range,
and `flee` fails from inside the shelter in both, six times. That is the
deferred "stand fast in a shelter" limitation, unchanged by this fix. Of the
51 decisions, only decision 40's goal differs; the skills Person ran are
identical.

The first physics event comes from the fixture's operator-side diagnostics
(`PERSON_FIXTURE_PHYSICS_LOG`). They record hostile positions for the
operator only. Nothing of them reaches Person, the journal or any
observation, and no hostile position was added to Person's evidence to make
this record.

`tests/integration/r15-reference.test.ts` pins all of it: B and C equal, and
D split at decision 40 (tick 4014), with the first physics event at tick 4009,
after the last identical decision and no later than the first different one.
