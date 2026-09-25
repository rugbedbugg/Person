# Architectural Decision Records (ADRs)

**Purpose:** Document significant architectural decisions for Person, with context, alternatives, and consequences.

---

## When to Create an ADR

Create an ADR for any decision that:

- Changes the trust boundary (Node/Python relationship, protocol schemas, safety hierarchy)
- Modifies safety semantics (protected areas, permissions, emergency triggers)
- Alters SkillSpec schema or skill library composition
- Changes evidence format, learning semantics, or persistence model
- Adds/removes a runtime process or package
- Changes the persistent state model (what survives restart)
- Introduces multi-Person architecture

Do **not** create ADRs for:

- Bug fixes within established boundaries
- Test additions
- Documentation updates
- Refactoring that preserves public interfaces

---

## ADR Lifecycle

```
Proposed → [Discussion] → Accepted → Implemented
                ↓
            Deferred (intentionally not decided)
                ↓
            Superseded (replaced by later ADR)
```

---

## ADR Format

Use `ADR-TEMPLATE.md`. Each ADR must include:

| Section                 | Required?                                   |
| ----------------------- | ------------------------------------------- |
| Status                  | Yes (Proposed/Accepted/Superseded/Deferred) |
| Context                 | Yes                                         |
| Decision                | Yes                                         |
| Consequences            | Yes                                         |
| Alternatives Considered | Yes                                         |
| Revisit Conditions      | Yes                                         |
| Relevant Commits/Docs   | Yes                                         |

---

## Index

| ADR                                                        | Title                                             | Status                             | Date       |
| ---------------------------------------------------------- | ------------------------------------------------- | ---------------------------------- | ---------- |
| [0001](0001-baritone-motor-backend.md)                     | Baritone as the planned primary motor backend     | Accepted (direction) / Deferred    | 2026-09-22 |
| [0002](0002-perception-firewall.md)                        | The perception firewall                           | Accepted (rule) / Deferred (model) | 2026-09-22 |
| [0003](0003-memory-firewall.md)                            | The memory firewall                               | Accepted (rule) / model: ADR 0007  | 2026-09-22 |
| [0004](0004-external-awareness-and-research-boundary.md)   | External awareness and the research boundary      | Accepted (rule) / Deferred         | 2026-09-22 |
| [0005](0005-cognitive-autonomy-vs-capability-authority.md) | Cognitive autonomy is not environmental authority | Accepted                           | 2026-09-22 |
| [0006](0006-two-clock-lifecycle.md)                        | The two-clock lifecycle                           | Accepted (rule) / Deferred         | 2026-09-22 |
| [0007](0007-episodic-memory-and-bounded-recall.md)         | Episodic memory and bounded recall                | Accepted                           | 2026-09-24 |
| [0008](0008-self-motion-and-cognitive-places.md)           | Self-motion and cognitive places                  | Accepted                           | 2026-09-25 |

All six were written during the Phase 0 canonical architecture reconciliation
(`docs/PERSON_SPEC.md`, frozen 2026-09-22). None of them changed production
code. 0005 records an invariant that has held since `6b99830`; the other five
constrain work that has not started.

---

## Process

1. **Create ADR** from template: `cp docs/decisions/ADR-TEMPLATE.md docs/decisions/000N-title.md`
2. **Fill in** all sections with evidence-based reasoning
3. **Discuss** in PR — both maintainers must approve for architectural-boundary ADRs
4. **Merge** → status becomes `Accepted`
5. **Implement** (may happen before or after merge)
6. **Update** `docs/CURRENT_STATE.md`, `AGENTS.md`, `TRACEABILITY.md` as needed
7. **If superseded later:** Create new ADR, mark old as `Superseded`, link both

---

## Retroactive ADRs

**Do not manufacture retroactive ADRs from memory.** Only create historical ADRs if:

- The decision is clearly evidenced by existing documentation, AND
- The implementation/commit history clearly shows the decision point

Otherwise, document the ADR process and use it going forward. The commit history (`docs/PROJECT_HISTORY.md`) serves as the historical record for pre-ADR decisions.

---

## Key Historical Decisions (Pre-ADR, Documented in PROJECT_HISTORY.md)

| Decision                                                         | Evidence                                                          | Commit              |
| ---------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------- |
| Two-process architecture (Node parent, Python cognition)         | `docs/ARCHITECTURE.md`, `IMPLEMENTATION_REPORT.md`                | `6b99830`           |
| Trust boundary: Python proposes, Node decides                    | `AGENTS.md`, `docs/SAFETY.md`, `TRACEABILITY.md`                  | `6b99830`           |
| Protocol `shroud-learning-v2` with canonical JSON Schemas        | `packages/protocol/`, `docs/PROTOCOL.md`                          | `6b99830`           |
| Embodiment port with two implementations (Mineflayer + Fixture)  | `apps/node-runtime/src/embodiment/types.ts`, `fixtures/src/`      | `6b99830`           |
| Safety kernel L0–L4 hierarchy, pure function of snapshot         | `apps/node-runtime/src/safety/safety-kernel.ts`, `docs/SAFETY.md` | `6b99830`           |
| 21 skills with typed SkillSpec contracts                         | `packages/skills/specs/`, `docs/SKILLS.md`                        | `6b99830`           |
| Evidence: append-only JSONL journal + atomic snapshots           | `packages/persistence/`, `docs/LEARNING.md`                       | `6b99830`           |
| Training-context separation (fixture/live evidence never merges) | `packages/persistence/`, `docs/LEARNING.md`                       | `6b99830`           |
| Legacy Shroud V1 discarded (Q-table, 7 actions, epsilon-greedy)  | `IMPLEMENTATION_REPORT.md` "Rewritten or discarded"               | `6b99830`           |
| No SQLite — JSONL journal + snapshots instead                    | `IMPLEMENTATION_REPORT.md` "Architectural deviations"             | `6b99830`           |
| Adapter audit against installed libraries (no live server)       | `REALITY_VALIDATION.md`, `IMPLEMENTATION_REPORT.md` Milestone 1   | `7e97e54`–`554ae64` |
| LAN port as runtime override (never written to config)           | `packages/config/ts/override.ts`, `docs/LAN_TESTING.md`           | `5e51c8c`           |
| Single-skill validation harness (shared dispatch path)           | `apps/node-runtime/src/skills/dispatch.ts`, `docs/LAN_TESTING.md` | `1c07bc5`           |

These are **recorded for reference**, not as formal ADRs. Future decisions use the ADR process.
