# AGENTS.md — Canonical Agent Contract for Person

This is the **canonical, tool-neutral operating contract** for all coding agents (Claude, Codex, Nemotron, OMP/Astra, future agents) and human contributors working on Person.

**Read this first.** Then read the documents it references, in order.

---

## 1. Reading Order

Every agent must read and operate under these documents, in this sequence:

1. **AGENTS.md** (this file) — Canonical agent contract
2. **docs/PERSON_SPEC.md** — Architectural source of truth
3. **docs/CURRENT_STATE.md** — Factual snapshot of what exists NOW
4. **REALITY_VALIDATION.md** — Canonical live/fixture validation evidence
5. **docs/OWNERSHIP.md** — Human collaboration / review boundaries
6. **docs/decisions/** — Architectural Decision Records (as relevant)
7. **Task-specific implementation files** — Only after the above

---

## 2. Scope Discipline

- **Do not redesign Person.** Implement what the architecture specifies.
- **Do not continue the Minecraft body-validation roadmap.** That is a separate track.
- **Repository governance / documentation / publication work only** unless explicitly directed otherwise.
- **No production behavior changes** without explicit human authorization.
- **Inspect existing abstractions** before adding parallel implementations.

---

## 3. Architectural Invariants (Non-Negotiable)

These invariants are established by the repository's implementation and commit history. Audit them before documenting or changing anything.

| Invariant                                                                        | Evidence                                                                                |
| -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Python proposes intentions; Node decides what is physically permitted            | `apps/node-runtime/src/skills/dispatch.ts`, `apps/node-runtime/src/safety/validator.ts` |
| Cognition must not receive unrestricted Mineflayer access                        | `adapters/minecraft/` is the only Mineflayer importer; architecture tests assert this   |
| Physical actions pass through the Node safety/authorization boundary             | `SafetyKernel.assess` pure function; validator returns ACCEPT/REJECT/PREEMPT/REPLACE    |
| Requested skill and actual executed skill remain distinguishable                 | `SkillOutcome` carries both `requestedSkill` and `executedSkill`                        |
| Validation execution does not silently train the policy                          | `tests/validation/skill-test.test.ts`: fingerprint before/after, asserts unchanged      |
| Live Minecraft validation must not be claimed unless Minecraft was actually used | `REALITY_VALIDATION.md` explicitly distinguishes fixture/adapter/live                   |
| Fixture/conformance evidence must not be mislabeled as live evidence             | Skill matrix in `REALITY_VALIDATION.md` uses strict vocabulary                          |
| Legacy Shroud behavior is not preserved merely for compatibility                 | `IMPLEMENTATION_REPORT.md` "Rewritten or discarded" section                             |

---

## 4. Verification Expectations

- **Automated tests:** `mise run check` (typecheck, build, lint, Node tests, Python tests)
- **Fixture tests:** Deterministic simulation — exercises same skill code as Mineflayer
- **Conformance tests:** Adapter against Mineflayer double built on real 1.16.1 data tables
- **Live validation:** Only via `docs/LAN_TESTING.md` ladder on a disposable LAN world
- **Never claim live validation** that has not been performed
- **Never upgrade status:** IMPLEMENTED ≠ TESTED IN FIXTURE ≠ CONFORMANCE-TESTED ≠ LIVE-VALIDATED

---

## 5. Documentation Update Rules

- **AGENTS.md** is the canonical agent contract — update when operating rules change
- **docs/PERSON_SPEC.md** is the architectural source of truth — update when architecture changes
- **docs/CURRENT_STATE.md** must reflect actual source tree, tests, current branch
- **REALITY_VALIDATION.md** is canonical for validation evidence — keep it honest
- **docs/PROJECT_HISTORY.md** — evidence-based, derived from Git commits
- **docs/decisions/** — ADRs for future architectural decisions
- **Tool-specific files (CLAUDE.md, etc.) must be THIN ADAPTERS** — point to AGENTS.md

---

## 6. Git Discipline

- **Branch naming:** `title/work-being-done-in-short`
- **Commit messages:** `[Title]: Imperative single-line subject` (e.g., `[Docs]: Add contribution guide`)
- **Always sign commits:** `commit.gpgsign=true` is configured
- **Never rewrite history:** No rebase, squash, amend, force-push, filter-repo without explicit human authorization
- **Existing signed commits and tags (v0.1.0-foundation) must remain unchanged**
- **Create new focused signed commits** for governance/documentation work

---

## 7. Handling Architectural Deviations

If you discover a deviation from documented architecture:

1. **Document it** in `docs/CURRENT_STATE.md` under "Known Deviations"
2. **Reference the commit(s)** where it was introduced
3. **Do not silently "fix" it** — the deviation may be intentional
4. **Escalate to human reviewers** (see `docs/OWNERSHIP.md`)

---

## 8. Instruction Precedence Within This Repository

1. **AGENTS.md** (this file) — Highest authority for agent behavior
2. **docs/PERSON_SPEC.md** — Architectural requirements
3. **docs/CURRENT_STATE.md** — Current implementation reality
4. **REALITY_VALIDATION.md** — Validation evidence
5. **docs/OWNERSHIP.md** — Human review boundaries
6. **docs/decisions/*** — ADRs for specific decisions
7. **Task-specific files** — Lowest, most contextual

Tool-specific instruction files (CLAUDE.md, etc.) **must not contradict** the above. They are adapters only.

---

## 9. Requirement: Inspect Before Implementing

Before adding any new implementation:

- Search for existing abstractions that solve the same problem
- Check `packages/` for shared protocols, skills, config, planner, policy, persistence
- Check `apps/node-runtime/src/` and `apps/cognition/python/` for runtime/cognition code
- Check `adapters/minecraft/` and `fixtures/src/` for embodiment implementations
- **Do not create parallel implementations** of existing capabilities

---

## 10. Validation Status Vocabulary (Use Exactly)

When documenting any capability, use only these terms:

- **IMPLEMENTED** — Code exists and compiles
- **TESTED IN FIXTURE** — Exercises skill code against deterministic simulation
- **CONFORMANCE-TESTED** — Adapter exercised against Mineflayer double with real data tables
- **LIVE-VALIDATED IN MINECRAFT** — Actually run against a Minecraft Java 1.16.1 LAN world
- **PLANNED** — Documented in PERSON_SPEC.md but not yet implemented

**Never upgrade one status into another.** Be explicit about what has and has not been done.

---

## 11. Quick Reference: Key Files

| Area         | Key Files                                                            |
| ------------ | -------------------------------------------------------------------- |
| Architecture | `docs/ARCHITECTURE.md`, `docs/PERSON_SPEC.md`                        |
| Protocol     | `packages/protocol/schemas/`, `docs/PROTOCOL.md`                     |
| Skills       | `packages/skills/specs/*.json`, `apps/node-runtime/src/skills/impl/` |
| Safety       | `apps/node-runtime/src/safety/`, `docs/SAFETY.md`                    |
| Cognition    | `apps/cognition/python/person_cognition/`                            |
| Learning     | `packages/policy/`, `packages/persistence/`, `docs/LEARNING.md`      |
| Validation   | `REALITY_VALIDATION.md`, `docs/LAN_TESTING.md`, `docs/EVALUATION.md` |
| Traceability | `TRACEABILITY.md`                                                    |
| History      | `IMPLEMENTATION_REPORT.md`, `docs/PROJECT_HISTORY.md`                |

---

_Last updated: 2026-09-19_
_Current HEAD: `7501194` (feat/lan-validation)_
_Tag: `v0.1.0-foundation` (`6b99830`)_
