# ADR-TEMPLATE.md — Architectural Decision Record Template

**Copy this file** to `docs/decisions/000N-short-title.md` (zero-padded, chronological).

---

# ADR 000N: <Short Title>

**Status:** Proposed | Accepted | Superseded | Deferred
**Date:** YYYY-MM-DD
**Authors:** @github-handle
**Reviewers:** @rugbedbugg, @upayanmazumder
**Supersedes:** ADR-NNN (if applicable)
**Superseded by:** ADR-NNN (if applicable)

---

## Context

What is the architectural problem or opportunity? What forces are at play?

- Reference existing docs, commits, issues
- Explain why the current state is insufficient
- Include relevant constraints (technical, organizational, research)

---

## Decision

What is the decision? State it clearly and unambiguously.

- Use imperative mood: "We will...", "The protocol will...", "The kernel shall..."
- Be specific enough to guide implementation

---

## Consequences

### Positive

- What becomes easier, safer, or possible?

### Negative

- What becomes harder, riskier, or impossible?
- What technical debt is introduced?

### Neutral

- What changes but isn't clearly positive/negative?

---

## Alternatives Considered

| Alternative | Why Rejected |
| ----------- | ------------ |
| Option A    | Reason       |
| Option B    | Reason       |
| Option C    | Reason       |

Include at least 2–3 genuine alternatives. "Do nothing" is a valid alternative.

---

## Revisit Conditions

Under what conditions should this decision be re-evaluated?

- Specific metrics, milestones, or external changes
- "Never" is not a valid answer — all decisions are revisitable

---

## Relevant Commits / Documents

| Reference              | Description           |
| ---------------------- | --------------------- |
| `commit-sha`           | Brief description     |
| `docs/SPEC.md#section` | Relevant spec section |
| `PR #N`                | Discussion context    |

---

## Implementation Notes (Optional)

- Key files to change
- Migration steps if backward-incompatible
- Test strategy

---

_Delete this template section when creating a real ADR._
