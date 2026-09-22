# ADR 0003: The memory firewall

**Status:** Accepted (rule), Deferred (retrieval model)
**Date:** 2026-09-22
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder

---

## Context

Person's evidence substrate is an append-only JSONL journal with chained event
ids, atomic checksummed snapshots and a strict reader. It is the most complete
record in the system and it is deliberately immutable: statistics are rebuilt
from it rather than persisted, so changing the scoring function re-reads history
instead of invalidating it.

It would be trivial to let Person query it.

Doing so would give Person perfect, instantaneous, complete recall of its entire
life, indexed and sorted. `docs/PERSON_SPEC.md` sections 24 and 25 specify
memory with recency, significance, emotional salience, decay, interference and
imperfect retrieval. A database query satisfies none of that, and an agent that
has one will never need the rest.

The same confusion already exists in miniature in a name:
`apps/node-runtime/src/runtime/world-memory.ts` is called memory and is not.

## Decision

The full event store is **engineering truth**. Accessible recollection is
**cognitive state**. They are different things and Person has access to the
second only.

1. **No database-level introspection.** Person gets no query interface over the
   journal, the snapshots, the statistics or the provenance records.
2. **Retrieval is cue, salience and context dependent.** Person may deliberately
   try to remember something; recall is not guaranteed to succeed and not
   guaranteed to be accurate.
3. **Forgetting alters accessibility and confidence, never history.** The
   journal is append-only and consolidation may not rewrite or delete the
   episodes that produced a belief.
4. **Researchers, operators and tests read everything.** The journal exists to
   be inspected from outside. `person inspect evidence` is an operator tool and
   stays one.
5. **`WorldMemory` is not memory.** It is a runtime-owned ownership and
   placement ledger: home record, placed blocks, storage provenance, workstation
   positions. It is privileged engineering state read by the observation
   builder, and it must not become a recollection path.

Rules 1, 3, 4 and 5 are in force now. Rule 2 is deferred with the memory system.

## Consequences

### Positive

- Memory retention, interference and catastrophic forgetting become measurable,
  because there is a retrieval layer that can fail. With a database query there
  is nothing to measure.
- Researchers keep complete records regardless of what Person can recall, which
  is what makes "Person misremembered this" a provable statement.

### Negative

- Person will be wrong about its own past, and the journal will prove it was
  wrong, and this will look like a bug every time.
- Two stores where a naive design has one.

### Neutral

- Nothing changes today. Person has no memory system and therefore no access to
  one; this ADR constrains the system that gets built.

## Alternatives Considered

| Alternative                                      | Why rejected                                                                                                                  |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| Let Person query the journal                     | Perfect recall, and the end of every memory research question in the spec.                                                    |
| One store with an access-control layer           | The control layer becomes the firewall, and it is one bug away from opening. The separation is cheaper stated as two stores.  |
| Give Person a summarized rolling context instead | This is how continuity is faked. It hides forgetting instead of modelling it, and makes catastrophic forgetting undetectable. |

## Revisit Conditions

- The memory system is built and retrieval quality becomes a capability axis a
  Super-Person experiment wants to raise. Raise it by name.
- A debugging need cannot be met by operator tooling, which would be surprising.

## Relevant Commits / Documents

| Reference                                              | Description                                 |
| ------------------------------------------------------ | ------------------------------------------- |
| `docs/PERSON_SPEC.md` sections 24, 25                  | The firewall and the memory model           |
| `docs/CURRENT_STATE.md`, "Known Deviations", C3 and C6 | `WorldMemory`, and the absent memory system |
| `packages/persistence/`                                | The event store                             |
| `apps/node-runtime/src/runtime/world-memory.ts`        | The ledger that is not memory               |
