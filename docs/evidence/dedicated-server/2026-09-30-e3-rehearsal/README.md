# E3 live rehearsal, 2026-09-30: validation-000

**Infrastructure validation, not research** (ADR 0018). One continuous
validation lineage, `validation-000` ("Rehearsal", designation
`Validation-000`), on a throwaway world of the local 1.16.1 dedicated server.
No behavioural conclusion is drawn from anything here. Person-000 does not
exist and was not involved.

## What was exercised

|                 |                                                                                                                                                                                                   |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Server          | `runs/servers/person-1161`, bound to 127.0.0.1, offline accounts, whitelist of one (`PersonRehearsal`), `ops.json` empty                                                                          |
| World           | new level `validation-e3-rehearsal`, seed `6016296545845284926` drawn once at random before generation (`e3-seed.txt`), easy, monsters on; the earlier `person-dedicated-1` world was not touched |
| World manifest  | `person-world-manifest.json`, SHA-256 `db0186ef…36a8` (`world-manifest.sha256`)                                                                                                                   |
| Configuration   | `validation-000.toml`, SHA-256 `0f0125df…6f4b` (`config.sha256`); reconnect budget 5 × 5 s, death `respawn`, affect `active`, learning `off`, all written explicitly                              |
| Revisions       | sessions 1 and 2 at `413740d`; session 3, the repeat after the fix, at `17a62a0`                                                                                                                  |
| Root at the end | `root-final.tar.gz` (the verified final backup, with its own `SHA256SUMS`), SHA-256 in `root-final.sha256`                                                                                        |

Every preflight (`01`, `06`, `10`, `19`) printed `READY` with the same config
and manifest hashes.

## Pass criteria

| Criterion                                                                    | Result                                                                                                                                                                                                                                                                                               | Evidence                     |
| ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| Founded exactly once                                                         | PASS: one founding; a second is refused (`already founded`)                                                                                                                                                                                                                                          | `02`, `03`, `04`             |
| Preflight passes, for the founding and each embodiment                       | PASS                                                                                                                                                                                                                                                                                                 | `01`, `06`, `10`, `19`       |
| Embodies in the fresh world                                                  | PASS: session 1, 40 decisions, clean end                                                                                                                                                                                                                                                             | `07`, `08`                   |
| Clean restart recovers its continuity gap                                    | PASS: session 2 and 3 start with `previous_ended_cleanly: true`, gap `minutes`, suspension `clean_end`                                                                                                                                                                                               | `27`                         |
| Loses the world while cognition stays alive                                  | PASS: console `kick` at 14:49:51Z; `unavailable/connection_lost` at 14:49:55, `available/reconnected` at 14:50:01; the same cognition process (PID 987334) before and after; no new session                                                                                                          | `12`, `13`, `14`, `27`       |
| Reconnects through the real Mineflayer path, with no stale-client corruption | PASS: one loss, one reconnection, decisions continued, no spurious disconnect afterwards                                                                                                                                                                                                             | `11`, `14`, `27`             |
| Dies from the server-console `kill`                                          | PASS: `kill` at 14:51:14Z (session 2), and twice more in session 3                                                                                                                                                                                                                                   | `15`, `22`, `24`, server log |
| Actually respawns through Mineflayer                                         | PASS: every death followed by `person_respawned` within 0.4 s, the body alive and deciding                                                                                                                                                                                                           | `27`                         |
| Continues as the same identity and session                                   | PASS: one founding, one Person, no session boundary at any death or reconnection                                                                                                                                                                                                                     | `27`                         |
| Shuts down cleanly                                                           | PASS: three `session_ended`, each after `decision_budget_reached`                                                                                                                                                                                                                                    | `07`, `11`, `20`             |
| Reconstructs correctly, read-only                                            | PASS: `founded`, `validation-000`, alive, 5 deaths and 5 respawns, 1024 events, none truncated, chain intact, no lock                                                                                                                                                                                | `25`, `27`                   |
| Nothing privileged reaches Person                                            | PASS: death memories hold only outcome, health and food before, threat in view, goal and project; no cause, coordinates, console, kick, kill or operator provenance in any Person-facing record. The console actions appear only as the engineering `operator_intervention` marker on episode events | `18`, `27`                   |

The server log (`server-log-excerpt.txt`) records five deaths: drowned, the
console `kill`, shot by a skeleton, and two console `kill`s. The journal
records five deaths and five respawns.

## Defect found and fixed (PR #36)

In session 2 a skeleton killed the body during the 40th and final
decision's flee. The flee kept pathing on the dead body for 2 min 21 s and
ended `FAILED`; the loop then left on its decision budget before its next
life check, and the session ended with the death unreported, the root saying
alive and the body dead on the server. The console `kill` earlier in that
session showed the same lag in a milder form: the running `gather_wood`
noticed the death 56 s later.

PR #36 checks the world and the body before the budgets, reports `DEATH` for
any skill whose body is dead at its end, and makes a Mineflayer move reject
the moment the body dies. The affected validation alone was repeated, as
session 3 at `17a62a0`:

- joining found the body still dead from session 2, reported the missed
  death and respawned it, before anything was perceived;
- a console `kill` between skills was caught at the next check (0.9 s);
- a console `kill` 14 s into a running `gather_wood` ended the skill as
  `DEATH` 0.62 s later (it had been 56 s), recorded in its own session.

The lineage therefore records its third death late, at the start of
session 3 rather than in session 2 when it happened. That is left as lived
(ADR 0018 rule 6): the history is not repaired, the defect is documented here.

## Finding for the readiness review, not fixed here

Session 1's death was a drowning. At night a spider's attack set off an L1
flee, which failed twice and left the body in water; the L0 `suffocation`
emergency then chose `flee` again, which moves away from threats rather than
up to air, and it failed. The respawn transport worked; the body-safety
response to suffocation does not surface. This is a safety-semantics change
(ADR required) and is recorded for the first-Ada readiness review.
