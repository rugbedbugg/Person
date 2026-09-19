# OWNERSHIP.md — Human Collaboration & Review Boundaries

**Status:** Conservative baseline — exact subsystem ownership may evolve as collaboration settles.
**Date:** 2026-09-19
**HEAD:** `7501194`

---

## 1. Current Maintainers

| Role                                          | Person              | GitHub          | Notes                                                                 |
| --------------------------------------------- | ------------------- | --------------- | --------------------------------------------------------------------- |
| Primary Maintainer / Architectural Originator | Partha Pratim Gogoi | @rugbedbugg     | Created repository, authored architecture, implemented Milestones 0–1 |
| Collaborator (joining)                        | Upayan Mazumder     | @upayanmazumder | Onboarding; subsystem ownership to be agreed                          |

---

## 2. Collaboration Principles

- **No invented subsystem ownership.** Document only what has been explicitly agreed.
- **Architectural-boundary changes require cross-review** while collaboration settles.
- **Agents do not decide human ownership disputes.** This document is for humans.
- **Conservative default:** Changes to architectural boundaries (below) require explicit human review from both maintainers until ownership is formalized.

---

## 3. Changes Requiring Explicit Human Review

The following categories of changes **must receive explicit review** from both Partha (@rugbedbugg) and Upayan (@upayanmazumder) before merging. This list is conservative and may be narrowed by mutual agreement later.

### 3.1 Trust Boundary & Runtime Architecture

- Node/Python process relationship (spawning, IPC, failure handling)
- Protocol schemas (`packages/protocol/schemas/*.json`) — any version change
- `SkillInvocation` / `SkillOutcome` / `Observation` message shapes
- Safety kernel verdicts (ACCEPT/REJECT/PREEMPT/REPLACE) or priority hierarchy (L0–L4)
- Embodiment port (`apps/node-runtime/src/embodiment/types.ts`) — adding/removing methods
- Cognition channel direction filter (what cognition may send)

### 3.2 Safety & Permissions Semantics

- Protected-area enforcement (4 levels: proposal, route, execution, interaction)
- Permission schema constants (existing-container deposit, named/tamed animal hunting, player combat, villager harm)
- `PermissionGate` logic
- Emergency triggers (lava, air, health, hunger, hostile count, protected area)

### 3.3 Skill System Semantics

- `SkillSpec` schema (`packages/skills/specs/skill-spec.schema.json`)
- Skill library composition (adding/removing skills, changing categories)
- Terminal status set (SUCCESS, FAILED, PREEMPTED, etc.)
- Completion evidence kinds
- Cost limit semantics (clamping vs rejection)

### 3.4 Evidence & Learning Semantics

- Evidence journal format (event types, chaining, schema versioning)
- Training-context separation (fixture vs minecraft_peaceful vs minecraft_normal)
- Statistics key structure (routine × context × decision-context)
- Beta posterior / scoring weights / exploration envelope
- Learning mode transitions (off ↔ shadow ↔ supervised)
- Attribution rule: executed skill gets attempt, requested skill gets preemption

### 3.5 Persistent State Model

- Snapshot format, checksum, restore logic
- What persists across restart (identity, home, storage, goals, routines, evidence, relationships, affect)
- What resets (active path, executor state, observation cache)
- Demonstration manifest schema & review process

### 3.6 Major Runtime Architecture

- Adding/removing Node or Python processes
- Changing transport (stdio ↔ Unix socket)
- Mineflayer version upgrade (currently 4.39.0, pinned to 1.16.1)
- `mineflayer-pathfinder` integration changes
- Fixture world rules changes that alter skill behavior

### 3.7 Multi-Person Architecture (Future)

- Shared infrastructure vs independent state boundaries
- Person-to-Person interaction protocols
- Social belief provenance

---

## 4. Changes That Do NOT Require Cross-Review (Once Architecture Settled)

- Bug fixes within established skill implementations
- Test additions / test improvements
- Documentation updates (this file, AGENTS.md, CURRENT_STATE.md, etc.)
- CLI usability improvements (flags, output formatting, help text)
- Configuration file examples
- Performance optimizations that don't change semantics
- Refactoring within a single package (e.g., `packages/planner/`) that preserves public interfaces

**Rule of thumb:** If a change could cause a test in a _different_ package to fail, or changes a schema/shared contract, it needs review.

---

## 5. Review Process (Lightweight)

1. **PR opened** with clear scope and architectural impact statement
2. **Both maintainers** receive review request (GitHub CODEOWNERS or manual @mention)
3. **Explicit approval** from both required for architectural-boundary changes
4. **Single approval** sufficient for non-boundary changes (once trust established)
5. **No auto-merge** — human merges after approvals

---

## 6. Agent Boundaries

- **Agents (Claude, Codex, Nemotron, etc.)** follow `AGENTS.md` and referenced docs
- **Agents do not:**
  - Decide ownership disputes
  - Approve architectural-boundary changes
  - Invent new subsystem boundaries
  - Override human review requirements
- **Agents may:**
  - Implement within established boundaries
  - Propose ADRs for human decision
  - Flag when a change appears to touch a review-required area

---

## 7. Escalation

If maintainers disagree on an architectural-boundary change:

1. Document the disagreement in an ADR (`docs/decisions/`)
2. Seek third-party technical input if needed
3. **Status quo prevails** until consensus — no forced merges

---

## 8. Future Formalization

When collaboration patterns stabilize (suggested: after 3–5 joint PR cycles):

- Define explicit subsystem ownership areas
- Narrow the mandatory-review list above
- Possibly introduce `CODEOWNERS` with granular paths
- Document in this file

**Until then: conservative cross-review on all architectural boundaries.**

---

## 9. Contact

- **Partha (@rugbedbugg):** Primary architectural authority, final say on invariant violations
- **Upayan (@upayanmazumder):** Collaborator, equal review weight on boundary changes

_This document is part of the repository's canonical documentation. Update it when ownership agreements change._
