# ADR 0029: Architectural rules live in the specification, ADRs and tests

**Status:** Accepted (2026-10-06)
**Date:** 2026-10-03
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder

---

## Context

`AGENTS.md` and `CLAUDE.md` carried tables of architectural invariants. Some
of those invariants were enforced by nothing but an agent reading them. A
human contributor, or an agent that does not read those files, could break
them without any signal, and the same rule written in three places drifts.

## Decision

1. **Architecture is stated in `docs/PERSON_SPEC.md`, decided in
   `docs/decisions/`, and held by tests.** `docs/ARCHITECTURE.md`,
   "Invariants and where they are held", is the one table that maps each
   invariant to its decision and its test.
2. **Agent instruction files point there and carry no architecture of their
   own.** `AGENTS.md` keeps its operating contract (reading order, scope
   discipline, validation vocabulary, repository workflow); `CLAUDE.md`
   stays a thin adapter to it.
3. **An invariant with no test says so.** The table marks each rule that is
   still documentary, so its absence of enforcement is visible.

## Consequences

### Positive

- A contributor who never opens an agent file still meets every enforced
  rule as a failing test.

### Negative

- None.

### Neutral

- No new instruction file is added for any tool.

## Alternatives Considered

| Alternative                        | Why Rejected                                     |
| ---------------------------------- | ------------------------------------------------ |
| Keep invariants in `AGENTS.md`     | Only agents read it; humans and tests do not     |
| Duplicate invariants in every file | Drifts; the copies already disagreed about C1-C8 |

## Revisit Conditions

- An invariant cannot be expressed as a test; record why in the table.

## Relevant Commits / Documents

| Reference                | Description               |
| ------------------------ | ------------------------- |
| `docs/ARCHITECTURE.md`   | Invariants and where held |
| `AGENTS.md`, `CLAUDE.md` | Pointers                  |
