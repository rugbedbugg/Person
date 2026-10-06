# CLAUDE.md — Thin Adapter for Claude Code

**Read and obey AGENTS.md.** AGENTS.md is the canonical repository agent contract.

---

## Project Documents (Read in Order)

1. **AGENTS.md** — Canonical agent contract (this file points there)
2. **docs/PERSON_SPEC.md** — Architectural source of truth, read top to bottom
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

### Architecture

Architectural rules are not restated here. See `docs/ARCHITECTURE.md`,
"Invariants and where they are held", and the ADRs it cites.

The known disagreements between the code and the frozen architecture are
`docs/CURRENT_STATE.md`, "Known Deviations". Do not resolve one silently.

### Implementation Discipline

- **Inspect existing abstractions** before adding parallel implementations
- Check `packages/` for shared protocols, skills, config, planner, policy, persistence, epistemics
- Check `environments/minecraft/` for everything Minecraft owns
- Check `apps/node-runtime/src/` and `apps/cognition/python/` for runtime/cognition code

### Commands

```bash
mise run check                    # Full canonical check suite
node apps/cli/src/bin/person.ts run --config examples/fixture.toml  # Fixture episode
node apps/cli/src/bin/person.ts validate examples/fixture.toml      # Config validation
node apps/cli/src/bin/person.ts inspect skills                      # List skill library
```

---

_This file is a thin adapter. The canonical contract is AGENTS.md._
_Last updated: 2026-09-29._
