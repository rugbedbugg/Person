# Migrations

Person versions three things that outlive a single run, and each has its own
migration rule.

## Configuration: `configVersion`

Current version: 3.

Migration is explicit. `person validate <file>` recognises a legacy Shroud V1
configuration and refuses to guess; `person validate <file> --migrate` prints
the Person configuration it maps to, along with every decision the migration
made. The mapping is implemented in `environments/minecraft/ts/legacy.ts` and
documented in `0001-shroud-v1-to-person-v2.md`. A configVersion 2 document is
read as version 3 in memory and never rewritten
(`0002-person-v2-to-person-v3.md`).

Nothing migrates silently, and learning is never carried across a migration.

## Protocol: `protocolVersion`

Current version: `person-v3` (`0002-person-v2-to-person-v3.md`); before it,
`shroud-learning-v2`.

There is no in-place protocol migration. A backward-incompatible change takes a
new version string, and both runtimes reject an unrecognised one by name. The
reason is that recorded evidence embeds the protocol version: silently
reinterpreting an old trace under new rules would corrupt the history rather
than migrate it.

## Journal: `schema_version`

Current version: `person-event-v20`; `person-evidence-v1` to `-v19` are read
alongside it (`0002-person-v2-to-person-v3.md`).

The canonical event journal is append-only and is never rewritten. Each schema
version is read alongside the current one by a reader that understands both,
not by converting records on disk. `CanonicalEvent.from_json` refuses an
unknown schema version outright, so a mixed journal fails loudly instead of
being partially misread. A journal record is history; whether it is also
evidence is decided separately (ADR 0027).

## Learning checkpoints

Legacy Shroud V1 Q-learning checkpoints are recognised and refused. There is no
conversion and there will not be one: the V1 table is indexed by seven integer
action ids over a bucketed state vector, while Person scores routines built
from typed skills within a coarse semantic context. Any mapping between them
would be invented rather than learned, and it would enter the evidence store
looking like experience Person had actually had.

Historical traces can enter through the reviewed demonstration mechanism
instead; see `docs/LEARNING.md`.
