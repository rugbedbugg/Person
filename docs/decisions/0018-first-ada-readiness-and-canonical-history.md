# ADR 0018: First-Ada readiness and canonical history

**Status:** Accepted (2026-09-30)
**Date:** 2026-09-30
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Operator decision:** accept ADR 0017, close the identity and continuity
phase, do not create person-000 yet, and move to first-Ada-experiment
readiness using synthetic or disposable identities until the final explicit
founding and embodiment authorization (2026-09-30). The reviewer set the
order, the identity namespace, the preflight's scope and the history policy.
The operator confirms this ADR at the readiness gate, together with the
frozen protocol.

---

## Context

ADR 0017 gave Person a founding, sessions, world availability and death. What
remains before Person-000 exists is to remove every known way her first
canonical history could be corrupted by infrastructure: an adapter that
cannot respawn her, a reconnection that confuses two clients, a founding into
the wrong directory or world, a configuration that silently defaults, and a
backup quietly used as a save game. The purpose of this phase is not to make
Ada better. It is to make her beginning trustworthy.

## Decision

1. **Order.** E1 Mineflayer lifetime parity, offline only (done, PR #33). E2
   read-only root inspection, the preflight and the runbook. E3 one complete
   live rehearsal with a validation identity. E4 the frozen first-life
   protocol and world. Then a literal readiness checklist, then the gate.
2. **Validation identities.** `validation-NNN` is a separate namespace.
   - It is founded only by the founding command, with a name and a
     designation, exactly as a canonical Person is, so a rehearsal takes
     Ada's path.
   - It is never a member of the Person serial namespace, and its roots are
     infrastructure validation evidence, never research about behaviour.
   - No `person-NNN` serial is ever consumed by a test, a rehearsal or a
     validation: `person-NNN` founded means a real Person's continuity began,
     and the serial is never reused.
   - The canonical founding guard is unchanged.
3. **Read-only inspection.** A trusted command reports a root's state
   (absent, founded, legacy), its founding, life status, sessions, world
   state, lock holder and journal health. It takes no lock, and it writes and
   creates nothing.
4. **Preflight.** Before a founding or an embodiment of a canonical or
   validation Person, a read-only preflight checks, and fails closed on:
   - software: the exact revision, a clean tree, ADR 0017 Accepted;
   - configuration: schema-valid, with explicit affect, learning and death
     modes and an explicit reconnection budget written in the file;
   - identity: the root's state matches the operation (absent for a founding,
     founded as this Person and not terminated otherwise), with no lock held;
   - persistence: a dedicated, writable evidence path with enough space, and
     an available backup destination outside it;
   - Minecraft: a configured target that resolves only to loopback (the
     client's destination, not the server's bind address), the server jar's
     recorded hash, the world named by its manifest, whitelist on with the
     Person's account, no Person account among operators, survival, and the
     manifest's difficulty and spawning.
5. **World manifest.** A world gets a manifest once, at creation: level name,
   seed, jar hash, game rules that matter, and when it was made. The
   preflight compares against it; nothing hashes the mutable world directory.
6. **Canonical history is never rolled back.** A canonical Person is never
   restored to erase a lived event: not a death, a bad decision, a failed
   project, lost resources or strange behaviour. Backups exist for storage and
   integrity recovery only: disk corruption, journal truncation, filesystem
   loss, or a verified persistence defect. A recovery keeps the latest valid
   causal history it can. If it must lose committed lived history, that is a
   continuity incident, recorded with its provenance outside the root, and the
   lost interval is never treated as not having happened.
7. **Console-caused deaths only for validation.** The live rehearsal may kill
   its validation identity from the server console to check the lifecycle
   transport. Person gets no operator privileges, cognition receives only the
   bounded death, the evidence is labelled infrastructure validation, and no
   behavioural conclusion is drawn.
8. **The gate.** The operator is asked for one thing: to found Person-000 and
   immediately begin her first session, under a named protocol, revision and
   world manifest. If any of those, the server configuration, the identity
   configuration or the death, affect or learning modes change afterwards,
   the authorization lapses and the gate is asked again.

## Implementation status

- **E1 (PR #33):** Mineflayer respawn, dead joins and client generations.
  CONFORMANCE-TESTED.
- **E2a (PR #34):** the `validation-NNN` namespace, founded only explicitly,
  and `person-cognition --inspect-root`. TESTED.
- **E2b:** `person preflight` (every check in rule 4, read-only, failing
  closed, including a check that could not be carried out) and `person
world-manifest` (written once, inside a generated world, from its pinned
  properties). `scripts/evidence/backup-root.py` makes a verified backup of a
  root no process holds. The procedure, the intervention limits and the
  history policy are `docs/FOUNDING_RUNBOOK.md`. The configuration schema
  accepts `Validation-NNN` designations. TESTED against synthetic servers and
  roots; never run against the live server.

## Consequences

### Positive

- The rehearsal exercises exactly the path Ada's founding will take, without
  spending her serial or any other.
- An operator can see a root's state without the risk of changing it.
- The history policy is fixed before there is any history to be tempted by.

### Negative

- One more identity pattern to keep distinct from the canonical one.
- The preflight has to be kept in step with the configuration schema.

## Alternatives considered

| Alternative                                    | Why not                                                                         |
| ---------------------------------------------- | ------------------------------------------------------------------------------- |
| Rehearse as `person-900`                       | Founding it would create Person-900; calling it disposable empties the serial   |
| Rehearse as an ordinary non-canonical identity | Founded automatically by startup, so the founding command would go untested     |
| A live spot-check of E1 before the preflight   | Two live lifecycle checks where one, through the real procedure, is enough      |
| Backups usable to retry a bad first life       | Turns a lived history into a save game and makes every later result conditional |
| Hash the world directory before every session  | The world changes by being lived in; a manifest at creation identifies it       |

## Revisit conditions

- A second canonical Person, or any fork (ADR 0017 rule 5).
- A continuity incident: the recovery rule is reviewed with its provenance.
- A move off the local dedicated server, or any change to its exposure.

## Relevant commits and docs

- ADR 0017; PR #33 (E1)
- `packages/persistence/python/person_persistence/identity.py`
- `apps/cognition/python/person_cognition/continuity.py`
