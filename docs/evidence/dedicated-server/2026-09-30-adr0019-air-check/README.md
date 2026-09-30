# ADR 0019 targeted live check, 2026-09-30: validation-001

**Infrastructure validation, not research.** One disposable, non-canonical
validation identity, `validation-001` ("AirCheck", account `PersonAirCheck`,
whitelisted alone, never an operator), on the throwaway E3 world of the local
dedicated server, at revision `d4b3beb` (ADR 0019 merged). Only the
air-deprivation scenario was forced. Person-000 does not exist; no world
intended for her exists or was touched.

## Setup

From the server console, before Person joined: a sealed glass tank, a 5 × 5
water column 8 blocks deep (y 91 to 98) under a 2-block air pocket and a
glass lid, so there was air to reach and no fall (`console-commands.txt`).
After Person's first decisions the console teleported the body to the bottom
of the column, head under water (`05-console-tp-at.txt`). The run carried
`--operator-intervention`.

Preflight for the founding and the embodiment: `READY`
(`01`, `03`; config `97ea9899…73fc`, world manifest `db0186ef…36a8`).

## Result: PASS

| Check                                                 | Result                                                                                                                                                                         |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| The air emergency begins the air-restoration response | Twice, air fell to the threshold under water; both times the kernel substituted `restore_air` (`suffocation` → `restore_air`), and `flee` never ran                            |
| It reaches air, or fails in the bounded way           | Both escapes ended `SUCCESS` with `air_restored` after 40 ticks; breath then read `breath_recovered`, from the air the server reported                                         |
| No death                                              | 0 deaths, 0 respawns; 14 decisions, clean end                                                                                                                                  |
| Nothing privileged reaches Person                     | Memory records only `endangered` with `{trigger: suffocation, response: restore_air}`; no coordinates, water geometry, pathfinder state, teleport or console provenance (`08`) |
| Reconstructs read-only                                | `founded`, `validation-001`, alive, 128 events, chain intact, no lock (`06`)                                                                                                   |

## Observation, not a failure

Restoring air does not leave the water. The Mineflayer body sinks again once
jump is released, so in deep water the air emergency recurs, here about
every 15 s, each time one bounded emergency that succeeds. Getting out of
deep water is not part of ADR 0019; it is recorded for the readiness review.

The server logged 82 "moved too quickly" warnings at the teleport, while the
body was mid-route for `gather_wood`: the server correcting the client after
an operator teleport, not a Person action.
