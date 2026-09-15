# Migrations

Person versions three things that outlive a single run, and each has its own
migration rule.

## Configuration: `configVersion`

Current version: 2.

Migration is explicit. `person validate <file>` recognises a legacy Shroud V1
configuration and refuses to guess; `person validate <file> --migrate` prints
the Person configuration it maps to, along with every decision the migration
made. The mapping is implemented in `packages/config/ts/migrate.ts` and
documented in `0001-shroud-v1-to-person-v2.md`.

Nothing migrates silently, and learning is never carried across a migration.

## Protocol: `protocolVersion`

Current version: `shroud-learning-v2`.

There is no in-place protocol migration. A backward-incompatible change takes a
new version string, and both runtimes reject an unrecognised one by name. The
reason is that recorded evidence embeds the protocol version: silently
reinterpreting an old trace under new rules would corrupt the history rather
than migrate it.

## Evidence: `schema_version`

Current version: `person-evidence-v1`.

Evidence is append-only and is never rewritten. A future schema version will be
read alongside the current one by a reader that understands both, not by
converting records on disk. `EvidenceEvent.from_json` refuses an unknown schema
version outright, so a mixed journal fails loudly instead of being partially
misread.

## Learning checkpoints

Legacy Shroud V1 Q-learning checkpoints are recognised and refused. There is no
conversion and there will not be one: the V1 table is indexed by seven integer
action ids over a bucketed state vector, while Person scores routines built
from typed skills within a coarse semantic context. Any mapping between them
would be invented rather than learned, and it would enter the evidence store
looking like experience Person had actually had.

Historical traces can enter through the reviewed demonstration mechanism
instead; see `docs/LEARNING.md`.
