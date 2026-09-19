# CONTRIBUTING.md — Human Contributor Guide

**For:** Human contributors to Person (Partha, Upayan, future collaborators)
**Date:** 2026-09-19
**HEAD:** `7501194` (feat/lan-validation)
**Canonical checks:** `mise run check`

---

## 1. Environment Setup

Person uses **mise** for toolchain management and **uv** for Python environments. Exact versions are pinned.

### Prerequisites

- [mise](https://mise.jdx.dev) installed
- Git with GPG signing configured (`commit.gpgsign=true`)

### One-Time Setup

```bash
cd /path/to/Person
mise trust           # trust the repository's mise.toml
mise install         # installs Node 22.23.2, Python 3.12, uv 0.12.13
npm install          # Node dependencies (exact pins via package-lock.json)
uv sync --all-packages  # Python workspace (exact pins via uv.lock)
```

### Verify Setup

```bash
mise run check       # runs ALL canonical checks (see §3)
```

**Do not** install project dependencies globally with npm/pip. Use the repository's declared package managers and local installation.

---

## 2. Branch Workflow

### Branch Naming

```
title/work-being-done-in-short
```

Examples:

- `docs/agents-contract`
- `fix/skill-test-harness`
- `feat/prediction-error`

### Branch Discipline

- **Main branches:** `main` (tagged releases), `feat/lan-validation` (current feature)
- **Create branches from `main`** for new work
- **No force-push** to shared branches
- **No history rewriting** (rebase, squash, amend) on shared branches without explicit authorization

---

## 3. Canonical Checks (`mise run check`)

**Run before committing and before opening PR.**

```bash
mise run check
```

This executes, in order:

| Task        | Command                                                                           | Purpose                                  |
| ----------- | --------------------------------------------------------------------------------- | ---------------------------------------- |
| typecheck   | `npx tsc --noEmit -p tsconfig.json` + `uv run mypy`                               | TypeScript + Python strict type checking |
| build       | `npm run build`                                                                   | TypeScript compilation to `dist/`        |
| lint        | `uv run ruff check .` + `uv run ruff format --check .` + `npx prettier --check .` | Python + JS/TS formatting & lint         |
| test-node   | `npm test`                                                                        | 188 Node tests (unit + integration)      |
| test-python | `uv run pytest`                                                                   | 129 Python tests                         |

**All must pass.** No partial check subsets for PRs.

---

## 4. Commit Messages

**Exact format:**

```
[Title]: Imperative single-line subject
```

| Title        | Use For                                |
| ------------ | -------------------------------------- |
| `[Docs]`     | Documentation only                     |
| `[Fix]`      | Bug fix                                |
| `[Feat]`     | New capability                         |
| `[Refactor]` | Code restructuring, no behavior change |
| `[Test]`     | Test additions/improvements            |
| `[Chore]`    | Maintenance (deps, config, CI)         |
| `[Arch]`     | Architectural boundary change          |

**Examples:**

```
[Docs]: Add AGENTS.md canonical agent contract
[Fix]: Correct eat_to_target contract from 1 to 3 items
[Feat]: Add person skill-test harness for single-skill validation
[Test]: Add conformance tests for biome resolution
```

**Always sign commits.** The repository has `commit.gpgsign=true` configured. If signing fails, **stop and resolve** — do not create unsigned commits.

---

## 5. Pull Request Workflow

### Before Opening PR

1. `mise run check` passes locally
2. Commit messages follow format above
3. Commits are signed
4. Branch is up to date with target (usually `main` or `feat/lan-validation`)
5. Documentation updated if architecture/behavior changed

### PR Requirements

- **Scope:** Clear description of what changed and why
- **Architectural impact:** Explicit statement (none / minor / major — see `docs/OWNERSHIP.md`)
- **Tests run:** `mise run check` result
- **Validation distinctions:** Fixture / Conformance / Live — be explicit
- **Protocol changes:** If any schema changed, note version impact
- **Safety/trust-boundary changes:** If any, flag explicitly
- **Docs updated:** Which canonical docs (AGENTS.md, CURRENT_STATE.md, etc.)

### Review

- **Architectural-boundary changes** (per `docs/OWNERSHIP.md`): Require approval from **both** @rugbedbugg and @upayanmazumder
- **Other changes:** Single approval sufficient once trust established
- **No auto-merge** — human merges after approval

---

## 6. Testing: Automated vs Live Validation

### Automated Suite (What `mise run check` Proves)

| Tier         | What It Exercises                                                        | What It Proves                                                 |
| ------------ | ------------------------------------------------------------------------ | -------------------------------------------------------------- |
| Unit         | Schemas, skill preconditions, goal scoring, planner, policy, persistence | Logic correctness in isolation                                 |
| Fixture      | Full skill implementations against deterministic simulation              | Skill logic, evidence pipeline, restart reuse                  |
| Conformance  | Mineflayer adapter against double built on real 1.16.1 data tables       | Adapter code paths, entity classification, recipes, containers |
| Architecture | Boundary assertions (no command channel, no code gen, learning off)      | Architectural invariants as executable tests                   |
| Integration  | Full survival routine ×2 with restart across two processes               | Vertical slice end-to-end                                      |

**None of the above touches a Minecraft server.**

### Live Minecraft Validation (What `docs/LAN_TESTING.md` Covers)

| Stage          | Command                       | Changes World? | Learning?                        |
| -------------- | ----------------------------- | -------------- | -------------------------------- |
| Observe        | `person observe`              | ❌ No          | ❌ No evidence written           |
| Skill-test     | `person skill-test --skill X` | ✅ Yes         | ❌ Fingerprint asserts unchanged |
| Autonomous run | `person run`                  | ✅ Yes         | Config-dependent (default off)   |

**Validation Evidence Treatment:**

- Fixture/conformance evidence: Stored in `runs/evidence/` (training-context keyed)
- Live validation evidence: Stored in `runs/evidence/` with `trainingContext: "minecraft_peaceful"` or `"minecraft_normal"`
- **Never merge** across training contexts — enforced by code
- Skill validation reports: `runs/validation/skill-tests/` (separate from learning evidence)
- Operator-intervention runs: Marked `contaminated` in evidence + status

### Claim Discipline

| Status                        | Meaning                                            | When to Use                  |
| ----------------------------- | -------------------------------------------------- | ---------------------------- |
| `IMPLEMENTED`                 | Code exists, compiles                              | Always accurate              |
| `TESTED IN FIXTURE`           | Exercises skill code vs deterministic sim          | After fixture tests pass     |
| `CONFORMANCE-TESTED`          | Adapter exercised vs Mineflayer double + real data | After conformance tests pass |
| `LIVE-VALIDATED IN MINECRAFT` | Actually run against Minecraft Java 1.16.1 LAN     | **Only after doing it**      |
| `PLANNED`                     | In PERSON_SPEC.md, not yet built                   | Spec only                    |

**Never upgrade one status into another.** Be honest about what has/hasn't been done.

---

## 7. Architecture Change Expectations

### Adding Capabilities

1. Check `docs/PERSON_SPEC.md` — is it in the spec?
2. Check `docs/CURRENT_STATE.md` — is it already implemented?
3. Check `packages/` — does an existing package cover it?
4. If new package needed: propose ADR first (`docs/decisions/`)

### Modifying Architectural Boundaries

**Requires:**

- ADR documenting context, decision, consequences, alternatives
- Cross-review per `docs/OWNERSHIP.md`
- Updates to: `AGENTS.md`, `docs/PERSON_SPEC.md`, `docs/CURRENT_STATE.md`, `TRACEABILITY.md`
- Architecture tests updated/extended

### Deprecating / Removing

- Never remove without ADR and migration path
- Legacy Shroud V1: migration supported, checkpoints refused — follow this pattern

---

## 8. ADR Policy (Architectural Decision Records)

### When to Create an ADR

- Any change to categories in `docs/OWNERSHIP.md` §3
- New package / process / protocol version
- Changing trust boundary, safety semantics, skill contracts
- Changing evidence format, learning semantics, persistence model

### ADR Location

```
docs/decisions/
  README.md          # index & process
  ADR-TEMPLATE.md    # template
  0001-example.md    # chronological, zero-padded
```

### ADR Statuses

- `Proposed` — under discussion
- `Accepted` — approved, implemented or ready to implement
- `Superseded` — replaced by later ADR
- `Deferred` — intentionally not decided yet

---

## 9. Documentation Expectations

### Canonical Documents (Update When Relevant)

| Document                  | When to Update                                              |
| ------------------------- | ----------------------------------------------------------- |
| `AGENTS.md`               | Agent operating rules change                                |
| `docs/PERSON_SPEC.md`     | Architecture specification changes                          |
| `docs/CURRENT_STATE.md`   | Implementation reality changes (every PR that changes code) |
| `REALITY_VALIDATION.md`   | Live validation performed, new defects found                |
| `docs/PROJECT_HISTORY.md` | New phase completed (not every commit)                      |
| `TRACEABILITY.md`         | New requirement→code→test mappings                          |
| `docs/decisions/*`        | New ADR accepted                                            |

### Tool-Specific Files (Thin Adapters Only)

- `CLAUDE.md`, `AGENTS.md` (root) — canonical
- Any tool-specific file **must** point to `AGENTS.md` as authority
- Do not duplicate project truth in tool-specific files

---

## 10. No False Claims of Validation

**Hard rule:** Do not claim live validation that hasn't happened.

- `REALITY_VALIDATION.md` is the canonical record — keep it honest
- `docs/EVALUATION.md` explicitly states what suite does/doesn't prove
- PR descriptions must distinguish fixture/conformance/live
- If you didn't run it against Minecraft, don't say it works in Minecraft

---

## 11. Signed Commits

This repository requires signed commits (`commit.gpgsign=true`).

### If Signing Fails

```bash
# Check GPG setup
git config --get user.signingkey
gpg --list-secret-keys

# Test signing
git commit -S -m "test"
```

**Do not commit unsigned.** Fix GPG setup first.

---

## 12. Quick Reference: Common Commands

| Task                          | Command                                                                                 |
| ----------------------------- | --------------------------------------------------------------------------------------- |
| Full check suite              | `mise run check`                                                                        |
| Typecheck only                | `mise run typecheck`                                                                    |
| Build only                    | `mise run build`                                                                        |
| Lint only                     | `mise run lint`                                                                         |
| Node tests only               | `mise run test-node`                                                                    |
| Python tests only             | `mise run test-python`                                                                  |
| Run fixture episode           | `node apps/cli/src/bin/person.ts run --config examples/fixture.toml`                    |
| Validate config               | `node apps/cli/src/bin/person.ts validate examples/fixture.toml`                        |
| Capture observation (fixture) | `node apps/cli/src/bin/person.ts observe --config examples/fixture.toml --out obs.json` |
| Compare observations          | `node apps/cli/src/bin/person.ts compare fixture.json actual.json`                      |
| Inspect skills                | `node apps/cli/src/bin/person.ts inspect skills`                                        |
| Inspect evidence              | `node apps/cli/src/bin/person.ts inspect evidence --config examples/fixture.toml`       |
| Inspect predictions           | `node apps/cli/src/bin/person.ts inspect predictions --config examples/fixture.toml`    |
| Status (read-only)            | `node apps/cli/src/bin/person.ts status --config examples/fixture.toml`                 |

---

## 13. Getting Help

- **Architecture questions:** Read `docs/PERSON_SPEC.md` → `docs/ARCHITECTURE.md` → `TRACEABILITY.md`
- **Validation questions:** Read `REALITY_VALIDATION.md` → `docs/LAN_TESTING.md` → `docs/EVALUATION.md`
- **Agent/Claude questions:** Read `AGENTS.md` first
- **Ownership/review questions:** Read `docs/OWNERSHIP.md`

---

_This guide is part of the repository's canonical documentation. Keep it accurate._
