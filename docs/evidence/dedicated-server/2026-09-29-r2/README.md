# R2 live spot-check, 2026-09-29 (dedicated server)

A small live check of what R2 (ADR 0014) could exercise safely and
reproducibly on the local 1.16.1 dedicated server. It is dedicated-server
evidence, recorded apart from the LAN runs, and it validates only what it
lists.

| What                                      | Result                                                                                                                                                                                                                                                                                                     |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Observation v8 through Mineflayer         | PASS: `person observe` schema-valid, `observationVersion` 8, `vitals` = health 20, food 18, **breath 10**, no saturation, no air counter (`observe-v8.json`)                                                                                                                                               |
| Hunger reaches affect live                | PASS, weakly: the operator applied the Hunger status effect (10 s, amplifier 2) from the server console two seconds after Person joined (`server-log-excerpt.txt`); food fell from 18 to 17, a `hunger_onset` phasic appraisal followed, and every tonic update carried hunger pressure 0.056 (`journal/`) |
| One causal event, one appraisal, live     | observed: action outcomes appraised with their consequences under `action:<decision>` causes                                                                                                                                                                                                               |
| Episode length measured before disconnect | observed: the report records 959 elapsed ticks (the fix of `6f7e567`)                                                                                                                                                                                                                                      |

**Not validated live:** health vulnerability, harm under R2, breath, threat
onset and exposure. Inducing them would have needed damage or water, and was
not attempted.

**Found here:** `SECURE_FOOD` is proposed at food 16 and 17 although its
completion condition (food 16 or more) already holds, so it was queued,
found complete and appraised as a completed goal at every observation (seven
times, +0.1 valence each). A goal-provider inconsistency older than R2; see
the correctness work that follows it.

The run was marked operator-contaminated. Files: `observe-v8.json`,
`person-r2live.toml`, `run.out` (the terminal summary), the episode report,
the journal, and the server log lines for the join and the effect.
