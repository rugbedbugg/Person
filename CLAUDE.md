# CLAUDE.md — Thin Adapter for Claude Code

**Read and obey AGENTS.md.** AGENTS.md is the canonical repository agent contract.

---

## Project Documents (Read in Order)

1. **AGENTS.md** — Canonical agent contract (this file points there)
2. **docs/PERSON_SPEC.md** — Architectural source of truth
3. **docs/CURRENT_STATE.md** — Factual snapshot of what exists NOW
4. **REALITY_VALIDATION.md** — Canonical live/fixture validation evidence
5. **docs/OWNERSHIP.md** — Human collaboration / review boundaries
6. **docs/decisions/** — Architectural Decision Records (as relevant)
7. **Task-specific implementation files** — Only after the above

---

## Claude-Specific Notes

### Working in This Repository

- **Never rewrite Git history** (rebase, squash, amend, force-push) without explicit human authorization
- **Always sign commits** — repository has `commit.gpgsign=true` configured
- **Branch naming:** `title/work-being-done-in-short`
- **Commit format:** `[Title]: Imperative single-line subject`
- **Run `mise run check` before committing** — all checks must pass

### Validation Honesty

- **Never claim live Minecraft validation** unless you personally ran it against a Minecraft Java 1.16.1 LAN world
- **Distinguish strictly:** IMPLEMENTED / TESTED IN FIXTURE / CONFORMANCE-TESTED / LIVE-VALIDATED IN MINECRAFT / PLANNED
- **REALITY_VALIDATION.md** is the canonical evidence document — keep it honest

### Architecture Boundaries

- Python proposes intentions; Node decides what is physically permitted
- Cognition never receives Mineflayer access, raw movement, or command execution
- Safety kernel (L0–L4) is Node-only; Python cannot override
- Requested skill ≠ executed skill — learning credits executed only
- Validation runs change no learning state (fingerprint verified)

### Implementation Discipline

- **Inspect existing abstractions** before adding parallel implementations
- Check `packages/` for shared protocols, skills, config, planner, policy, persistence
- Check `apps/node-runtime/src/` and `apps/cognition/python/` for runtime/cognition code
- Skills written once against `Embodiment` port — two bodies (Mineflayer + Fixture)

### Commands

```bash
mise run check                    # Full canonical check suite
node apps/cli/src/bin/person.ts run --config examples/fixture.toml  # Fixture episode
node apps/cli/src/bin/person.ts validate examples/fixture.toml      # Config validation
node apps/cli/src/bin/person.ts inspect skills                      # List skill library
```

---

## Quick Reference: Key Invariants (from AGENTS.md)

| Invariant                            | Enforced By                                         |
| ------------------------------------ | --------------------------------------------------- |
| Python proposes; Node decides        | `dispatch.ts`, `validator.ts`, architecture tests   |
| No Mineflayer in cognition           | `adapters/minecraft/` only importer; arch tests     |
| Safety kernel pure function          | `safety-kernel.ts`, `kernel.test.ts`                |
| Requested ≠ executed skill           | `SkillOutcome` schema, attribution tests            |
| Validation doesn't train             | `skill-test.test.ts` fingerprint check              |
| Live validation claimed only if done | `REALITY_VALIDATION.md` vocabulary                  |
| Fixture ≠ live evidence              | Training-context key on all statistics              |
| No legacy Shroud compatibility       | `IMPLEMENTATION_REPORT.md` "Rewritten or discarded" |

---

_This file is a thin adapter. The canonical contract is AGENTS.md._
