# Founding and first embodiment runbook

The procedure for founding a Person and beginning its first session on the
local dedicated server (ADR 0017, ADR 0018). The validation rehearsal (E3)
follows it with `validation-000`. Person-000 follows it only after the
operator's explicit authorization, which names the protocol, the revision
and the world manifest; any change to those, to the server or identity
configuration, or to the death, affect or learning modes voids it.

Nothing here gives Person operator privileges, exposes the server beyond
`127.0.0.1`, or touches any world but the one named.

## 1. The world, once

1. Choose the world's seed **once**, at random, and record it before the world
   exists. It is never redrawn because of the terrain:

   ```bash
   python3 -c 'import secrets; print(secrets.randbelow(2**63))'
   ```

2. Point the server at a new level: set `level-name` to a name never used
   before and `level-seed` to that seed in `runs/servers/<server>/server.properties`,
   with `difficulty`, `spawn-monsters`, `white-list=true`,
   `enforce-whitelist=true`, `gamemode=survival` and `force-gamemode=true`.
   The whitelist holds exactly the Person's account (its offline UUID, as
   `scripts/dedicated-server/setup.sh` writes it) and `ops.json` is `[]`.
3. Start the server once, so the world is generated, and stop it cleanly
   (`echo stop > console.fifo`). No account connects.
4. Record the world's identity, once:

   ```bash
   node apps/cli/src/bin/person.ts world-manifest \
     --server-dir runs/servers/<server> --purpose "<validation rehearsal | Person-000 first life>"
   ```

   The manifest is written inside the world directory and never rewritten.

## 2. Preflight

With the revision to be used checked out, a clean tree, and the server
stopped or idle:

```bash
node apps/cli/src/bin/person.ts preflight --config <config> \
  --server-dir runs/servers/<server> --backup <backup-directory> --found
```

Every line must read `PASS` and the last `READY`. The printed revision,
config SHA-256 and world manifest SHA-256 are what an authorization names.
A single `FAIL` stops the procedure; nothing is overridden.

## 3. Founding

```bash
uv run person-cognition --config <config> --found
uv run person-cognition --inspect-root <evidence-directory>
```

The inspection must show `founded`, the expected Person, `alive`, and no
live lock. Then take the first backup (section 5).

## 4. First session

1. Preflight again, now without `--found`: the root must be `founded`.
2. Start the server and hold its console pipe open.
3. Run the session named by the protocol:

   ```bash
   node apps/cli/src/bin/person.ts run --config <config>
   ```

4. During a canonical observation the operator only observes, collects
   telemetry, stops at the protocol's endpoint, or stops early for an
   infrastructure, safety or correctness defect. The operator never
   instructs, supplies items, teleports, changes time or weather, kills
   hostiles, repairs, hints, frees a stuck Person or changes configuration
   because behaviour looks bad. If intervention seems needed, end the run and
   report why.
5. After the session: inspect the root, then back it up.

## 5. Backups

```bash
uv run python scripts/evidence/backup-root.py <evidence-directory> <backup-directory>
```

It refuses while any process holds the root, copies every file, writes
`SHA256SUMS` and `BACKUP.json`, and verifies the copy before reporting it.
Take one after founding and one after every session.

## 6. Crashes, deaths and termination

- **A crash** writes nothing further. The next session learns that the
  previous one ended uncleanly; nothing is repaired by hand. Check with
  `--inspect-root` that the lock is stale, not live, before restarting.
- **A death with `respawn`** is lived history. If the runtime could not
  respawn the body, the root shows `awaiting_respawn` and the next run
  respawns it before Person perceives anything.
- **A terminated Person** refuses to start whatever the configuration says.
  Its evidence is inspected read-only with `--inspect-root` and the ordinary
  evidence tools.

## 7. Canonical history is never rolled back

A canonical Person is never restored to erase a lived event: not a death, a
bad decision, a failed project, lost resources or strange behaviour. A backup
is restored only for storage or integrity failure: disk corruption, journal
truncation, filesystem loss, or a verified persistence defect. A recovery
keeps the latest valid causal history it can. If it must lose committed
lived history, that is a **continuity incident**: record, outside the root,
what was lost, why, which backup was restored and by whom, and treat the lost
interval as having happened.

## 8. Validation identities

`validation-NNN` roots take exactly this path and are infrastructure
validation evidence, never research about behaviour. A console-caused death
(`kill <account>`) is permitted only for them, and is recorded as the
harness's doing. No `person-NNN` serial is used for any rehearsal.
