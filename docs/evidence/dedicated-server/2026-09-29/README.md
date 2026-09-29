# Dedicated-server validation evidence, 2026-09-29

The six-check live checkpoint against a local Minecraft Java 1.16.1
dedicated server (not a LAN world), and the first autonomous episodes Person
ran against Minecraft. The account of it is `REALITY_VALIDATION.md`,
"Dedicated-server validation"; the tooling is `scripts/dedicated-server/` and
`scripts/dedicated-checkpoint.ts`.

Copied from `runs/servers/person-1161/` on 2026-09-29 with absolute paths
replaced by `<repo>` and `<home>`; the JSON was then formatted. The hashes
below are of these copies. The originals remain on the operator's machine.

| File                                                                    | What it is                                                                       |
| ----------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `server.properties`, `whitelist.json`, `ops.json`, `eula.txt`, `run.sh` | the server as it ran                                                             |
| `person-dedicated.toml`, `person-restart.toml`                          | Person's configuration for the checks, and for the two short episodes            |
| `observe-1.json`                                                        | check 1 and 5: the `person observe` capture                                      |
| `probe.json`                                                            | checks 2 to 5: gaze, the three threat placements, the operator's console actions |
| `person-dedicated-1-ada-look_around-*.json`                             | check 2 through the full skill path                                              |
| `restart/`                                                              | check 6: both episodes' reports, the shared journal and the learning reports     |
| `server-latest.log`                                                     | the server's own log, including every console command                            |

The two episode reports record `elapsedTicks: 0`. That is the defect this
checkpoint exposed (fixed in `6f7e567`); the journal's experienced time and the
decision ticks are correct.

## SHA-256

| File                                                           | SHA-256                                                            |
| -------------------------------------------------------------- | ------------------------------------------------------------------ |
| `eula.txt`                                                     | `138bd08e3eb63904676e7e489251c4ebc58fc6e3c1b363545de1b7f13022200b` |
| `observe-1.json`                                               | `fd8311de7b6d7538374e1d2c8460e70ae26574e8508739336850701bde796776` |
| `ops.json`                                                     | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `person-dedicated-1-ada-look_around-st_muml8mn2_12e4875a.json` | `2f051de7ec255a56753c64b6a08b8023fce276c6a1e17369d8866a54e32088ae` |
| `person-dedicated.toml`                                        | `d458e2df605d852beb40e326df4040adc5ed165de7a60ed66ef248216b874ff3` |
| `person-restart.toml`                                          | `d21482c4e0c6571799da3843d46bf125c55d501f601fa8a6453569624df40580` |
| `probe.json`                                                   | `0d63fc451a13dc5c14d575ccd06f6b6ea1447a1c88a532c82b71e9f0c6532bb6` |
| `restart/episode-ep_live_1.json`                               | `47aa325f110b465197f69dfdd1206d291af49c2a82e6274d1801ef9b3856dbe3` |
| `restart/episode-ep_live_2.json`                               | `59ab194d44ccd0d12e429a4f233ad119754410ee961550b2ddb31106ec87bf17` |
| `restart/journal/000001.jsonl`                                 | `5826ebd7feb29aadf2032488c7366cde21438d5b6c1ce797be92dda91cc0d000` |
| `restart/reports/learning-ep_live_1.json`                      | `f5a772db97c6d0478c9bd7d41aa2d7519666ae575de5c8bb54d4be551e6f1529` |
| `restart/reports/learning-ep_live_2.json`                      | `db4d92bdd223deb54acdc020d0aff9f060fa735c91e9704f6f77b3b92c497a93` |
| `run.sh`                                                       | `381863b96172d2c9a8b1a19afcb91468180d9cfe9b37728948be964f27bac6ae` |
| `server-latest.log`                                            | `1640aeed84e1e96bfc9c38a8c9f7428b44dca783d5625aadeb24e535f4f5aa04` |
| `server.properties`                                            | `1ef2911e14c03180a4e3c3fa860704e61603902c95acd4837d726b4102794b9f` |
| `whitelist.json`                                               | `3ba33d3b32a6720750e6766010d679965d7e1841c073e42bc2cd87ac28a27a3e` |
