# PROJECT_HISTORY.md — Evidence-Based Development History

**Derived from:** Git commit history (11 commits, `6b99830` → `48728e8`)
**Date:** 2026-09-22
**Baseline for this update:** `48728e8` (tip of `feat/lan-validation`)
**Tag:** `v0.1.0-foundation` (`6b99830`)

This file records what happened, in the order it happened. **It is not
retroactively harmonised with the architecture frozen on 2026-09-22.** The
perception firewall, the memory firewall, the Baritone direction, the external
awareness boundary and the two-clock lifecycle are a later evolution, and the
decisions recorded above them were made without them.

---

## Commit Timeline

```
6b99830 2026-09-15 [Person]: Survival vertical slice & evidence substrate established  ← TAG v0.1.0-foundation
d557275 2026-09-15 [Adapter]: Mineflayer entity, container & world-readiness handling corrected
0f6cc1a 2026-09-15 [Instrumentation]: Prediction error, tick timing & observation comparison added
2d2b48f 2026-09-15 [Validation]: Protected-area routing tested, planner cost fixed & reality report written
3313622 2026-09-15 [Docs]: Milestone 1 test totals corrected
062f7fe 2026-09-15 [LAN]: Port override, status telemetry & connection diagnostics added
f0b3ff8 2026-09-15 [Observation]: Live biome, player identity, perception balance & exit hang fixed
9ff7778 2026-09-15 [Docs]: First contact results, 4 corrections & test world recorded
b692153 2026-09-16 [Validation]: Single-skill harness, shared dispatch path & operator setup added
5b9a395 2026-09-16 [Docs]: Second contact results, skill validation stage & traceability recorded
48728e8 2026-09-20 [Docs]: Establish canonical documentation system and GitHub collaboration files  ← baseline
```

One event in the timeline is not a commit. On **2026-09-16**, after `5b9a395`,
the operator ran three live `person skill-test` validations against the LAN
world. They produced local report artifacts under `runs/`, which is gitignored,
so they left no trace in the history above. They were located and read during
the 2026-09-22 reconciliation; see `REALITY_VALIDATION.md`.

---

## Phase 1: Foundation — Survival Vertical Slice & Evidence Substrate

**Commit:** `6b99830` (tagged `v0.1.0-foundation`)
**Date:** 2026-09-15
**Scope:** 212 files, 29,029 lines added — entire initial implementation

### Objective

Establish the complete survival vertical slice: Node runtime + Python cognition, versioned protocol, safety kernel, 21 skills, evidence journal, deterministic fixture, and restart persistence.

### Architectural Changes

- **Two-process architecture:** Node (parent) spawns Python cognition over stdio
- **Trust boundary:** Python proposes `SkillInvocation`; Node validates, executes, attributes
- **Protocol `shroud-learning-v2`:** 11 message types, canonical JSON Schemas, dual-runtime validation
- **Embodiment port:** Skills written once, two bodies (Mineflayer + FixtureWorld)
- **Safety kernel (L0–L4):** Pure function of snapshot; ACCEPT/REJECT/PREEMPT/REPLACE
- **21 skills implemented:** Emergency, Food, Resources, Crafting, Shelter, Storage
- **Cognition:** Decision context (7 dims), homeostatic goals, goal stack, symbolic planner, routines, deterministic + evidence policy
- **Evidence:** Append-only JSONL journal, atomic snapshots, strict restore, training-context separation
- **CLI:** `person run|learn|validate|inspect`, `shroud`/`shroud-train` aliases
- **Configuration:** TOML + JSON Schema, legacy V1 migration, V1 checkpoint refusal

### Significant Bugs Discovered (During Implementation)

- Legacy Shroud Q-learning, 7-action space, epsilon-greedy, V1 checkpoints — **discarded deliberately**
- `src/routine-primitives.js`, `routine-learner.js`, `routine-journal.js` — built around V1 action space, **discarded**
- Request-response lockstep (`enforceDecision`) — replaced by typed validator at trust boundary
- `gymnasium`/`numpy` dependencies — not needed for evidence-guided learner
- Inventory reconciliation on resume — **not reimplemented** (tracked as limitation)

### Validation Improvements

- Architecture tests assert: boundary integrity, no command channel, no code generation, learning off by default
- Vertical slice integration test: full survival routine ×2 with restart, evidence chain unbroken
- 173 tests total (71 Node + 102 Python) — all passing

### Intentionally Out of Scope

- Language model, neural policy, affect, social memory, projects, redstone
- Live Minecraft validation (no server available)
- Multi-Person support
- SQLite (using JSONL journal + snapshots instead)

---

## Phase 2: Adapter Audit & Correction — Mineflayer Reality Hardening

**Commits:** `d557275` → `2d2b48f` (4 commits, same day)
**Constraint:** **No Minecraft server reachable** — all work done against installed libraries and data tables

### Objective

Audit Mineflayer adapter against `mineflayer` 4.39.0, `mineflayer-pathfinder` 2.4.5, `minecraft-data` 1.16.1 sources. Fix defects the fixture could never reveal.

### Commits & Changes

| Commit    | Focus                                | Key Changes                                                      |
| --------- | ------------------------------------ | ---------------------------------------------------------------- |
| `d557275` | Entity, container, world-readiness   | Entity metadata handling, container caching, spawn readiness     |
| `0f6cc1a` | Instrumentation                      | Prediction error, tick timing, observation comparison            |
| `2d2b48f` | Protected-area routing, planner cost | Route detour tests, planner parameter-aware cost, reality report |
| `3313622` | Docs                                 | Test totals correction                                           |

### Six Critical Defects Found (Adapter Audit)

| #   | Defect                                              | Impact                                                                                 | Fix                                                                |
| --- | --------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| 1   | Entity metadata is sparse object, not array         | **Fatal** — `TypeError: metadata.some is not a function` on first entity with metadata | Read index 2 (custom name), handle string/chat-component/absent    |
| 2   | Named animals never detected                        | **Safety** — named cow was legal hunting target                                        | Same fix; unrecognised shape → treat as named                      |
| 3   | Hostile classification missed registry-unknown mobs | **Safety** — hoglins/zoglins not fled from                                             | Registry category + explicit hostile-on-sight list                 |
| 4   | Neutral mobs invisible to safety kernel             | **Safety** — wolves/bees/golems could kill unarmoured Person                           | `neutral` classification + `recentlyDamaged` signal                |
| 5   | First container withdrawal always failed            | **Functional** — `containerAt` returns empty cache                                     | `inspectContainer` on embodiment port; live read before withdraw   |
| 6   | Crafting failed on wood-species bookkeeping         | **Functional** — recipe lookup used wrong wood type                                    | Server-authoritative `recipesFor()`; static table for planner only |

### Smaller Corrections

- `freeSlots`: `36 - stacks` → `bot.inventory.emptySlotCount()`
- Empty craft/smelt → explicit failure (not silent success)
- Smelting: collect output as ready (not wait for full batch)
- Connection: wait for entity, position, chunks, clock, inventory, vitals, dimension (30s bound, no reconnect loop)
- World rules: validate game mode, dimension, difficulty, daylight cycle
- `dig_in`: report diggable ground; kernel prefers fleeing when none

### Validation Improvements

- **Mineflayer conformance double** built on real 1.16.1 data tables (27 tests)
- **Prediction error** instrument: compares declared effects vs observed state, recorded as evidence, **inert** (changes no policy)
- **Tick budget instrumentation:** port-wrapper measures navigation/interaction/waiting per skill
- **Planner cost fix:** cost now scales with parameter magnitude (cooking 2 items → hunt 3, not 12)
- **Protected-area routing tests:** detour found, no detour = refusal, replanning guard in pathfinder step exclusion

### Test Count After Phase

- **228 tests** (108 Node + 120 Python), up from 173

---

## Phase 3: Pre-LAN Readiness — Connection Instrumentation

**Commit:** `062f7fe`
**Date:** 2026-09-15

### Objective

Prepare for first live LAN connection. LAN port changes every world open — must be runtime override, not file config. First connection is least diagnosable moment.

### Changes

- **Port/host overrides** (`--port`, `--host`) applied in memory, never written back
- **Connection diagnostics:** 14 failure classes (refused, unresolved, timeout, reset, closed, protocol mismatch, identity conflict, auth refused, login refused, kick, spawn timeout, chunk data, world not ready)
- **Connection races spawn against error/kick/close** — refused login fails immediately
- **Readiness distinguishes** missing chunk data from general unreadiness
- **`person observe`**: captures one observation, validates schema, prints, disconnects — **runs no skill, writes no evidence**
- **`person status`**: reads atomic status file (runtime writes, CLI reads) — **never connects, one-way telemetry**
- **Operator intervention** (`--operator-intervention`): marks episode contaminated in evidence + status
- **Architecture tests:** no server-command path, no teleport, telemetry one-way

### New Tests: 30 added (138 Node + 120 Python = 258 total)

---

## Phase 4: First Live Contact — Observation Validation

**Commits:** `f0b3ff8` → `9ff7778`
**Date:** 2026-09-15 (hours after pre-LAN patch)

### Event

First successful `person observe` against Minecraft Java 1.16.1 LAN (Peaceful, disposable world).

### What Worked First Time

- Connection established, identity check passed
- Spawned inside configured exploration bounds
- Readiness held: chunks, clock, inventory, vitals, dimension all arrived
- One observation captured, **schema-valid with no diagnostics**
- Home reported correctly at distance 0
- World rules accepted: survival, Peaceful, daylight cycle, Overworld
- Clean disconnect, command exited

### Four Defects Exposed (Fixture/Double Could Not Find)

| #   | Defect                                                  | Root Cause                                                                                          | Fix                                                                         |
| --- | ------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| 1   | `biome` = `"unknown"` in loaded chunk                   | `prismarine-block` passes Version object to `prismarine-biome` (expects string) → empty biome table | Resolve biome from numeric ID against `bot.registry`                        |
| 2   | Human player reported as `"player"`                     | Minecraft names all players `player`; identity in username/UUID                                     | Entity records carry `username` + `uuid` (additive protocol fields)         |
| 3   | Perception saturated (64 stone, 0 wood)                 | Single nearest-N search standing on stone returns only stone                                        | Category-balanced resource perception: quota per category + shared overflow |
| 4   | Passive entities = noise (80 animals, 70 out of region) | No region filtering on passive entities                                                             | Shape to permitted region + reachable, nearest-first, bounded               |

### Exit Hang Fixed

- `disconnect` called `client.end()` twice → `minecraft-protocol` close timer armed twice → 30s hang if server close arrived between calls
- **Fix:** End once, await close with bound, clear timer explicitly, destroy socket if server never answers
- **Regression test:** Child process — old code 31.5s, fixed code exits immediately

### Test Artifacts

- `first-contact.json` — captured observation (kept as evidence)
- Fixture world recorded for comparison (`person compare`)

---

## Phase 5: Single-Skill Validation Harness

**Commit:** `b692153`
**Date:** 2026-09-16

### Objective

Build `person skill-test` — validates one skill at a time through the **same safety kernel and executor** as autonomous runs. No planner, no goal selection, learner unchanged.

### Implementation

- **Single dispatch path:** `apps/node-runtime/src/skills/dispatch.ts` used by both runtime and harness
- **Harness cannot bypass executor:** No `runner.run`, no `SKILL_IMPLEMENTATIONS` access
- **Normal safety kernel decides:** `InvocationValidator` + `SafetyKernel` built exactly as runtime
- **REJECT reported, nothing runs** | **REPLACE never credits requested skill**
- **`--skill` resolves only to registered SkillSpec** (no free-form actions)
- **Parameters validated by canonical rules** (`SkillRegistry.resolveParameters`)
- **Cost limits from spec, clamped by validator**
- **Pre/post observations** (both schema-valid), effects compared via prediction machinery
- **Validation runs change no learning state:** `learningFingerprint` before/after, recorded in report
- **Validation evidence stored separately:** `runs/validation/skill-tests/`
- **Operator setup (`--operator-setup`):** Human moves Person during pause; recorded as contamination; explicit continuation required; invalid post-setup state refuses measured run
- **No teleport capability added** — setup is human action
- **Every path releases body, timers, input** (bounded disconnect, readline closed)

### Skills Prepared for Harness

1. `wait_safely` — fixture end-to-end passing
2. `return_home` — fixture end-to-end passing (needs operator setup for positioning)

**No skill has been run live through this harness.**

---

## Phase 6: Second Contact & Traceability

**Commit:** `5b9a395` (HEAD)
**Date:** 2026-09-16

### Event

Second live `person observe` against same LAN world — verified all four first-contact corrections against real Minecraft.

### Results

| Field           | Value                                                |
| --------------- | ---------------------------------------------------- |
| biome           | `plains` (real name, not `unknown`)                  |
| player username | `Shroud`                                             |
| player uuid     | `1ed03c15-b62c-33e4-8e93-cd19bc1d57e3`               |
| resources       | stone 28, coal 12, plant_food 12, wood 12 (balanced) |
| passive animals | 8 (nearby, in region, reachable)                     |
| position        | -218, 66, 164                                        |
| home distance   | 0                                                    |
| learning        | off                                                  |

**All four corrections hold against Minecraft.** Observation milestone closed.

### Documentation Added

- `TRACEABILITY.md` — requirements → code → tests mapping (14 sections, ~300 rows)
- Updated `REALITY_VALIDATION.md` with second contact results
- Updated `docs/LAN_TESTING.md` with single-skill validation ladder

---

## Phase 6: Canonical Documentation System

**Commit:** `48728e8`
**Date:** 2026-09-20

### Objective

Establish a single documented reading order and the collaboration files a
published repository needs.

### Added

- `AGENTS.md` as the canonical tool-neutral agent contract, with `CLAUDE.md`
  reduced to a thin adapter pointing at it
- `docs/CURRENT_STATE.md`, `docs/OWNERSHIP.md`, `docs/PROJECT_HISTORY.md`,
  `docs/decisions/` with the ADR process and template
- `CONTRIBUTING.md` and `.github/` collaboration files

No production behaviour changed.

---

## Phase 7: Canonical Person v1 Architecture Reconciliation

**Commit:** this one
**Date:** 2026-09-22
**Branch:** `refactor/person-v1-architecture`

### Objective

Make the canonical documents describe what Person is now intended to become,
while keeping an exact account of what is actually implemented. Documentation
and audit only.

### What changed

- `docs/PERSON_SPEC.md` gained **Part 0**, the frozen north star: epistemic
  separation, perception firewall, memory firewall, spatial cognition, the
  Baritone embodiment direction, the action hierarchy, discovery provenance,
  internet access, self-knowledge, the operator relationship, lifecycle and two
  clocks, capability authority, Super-Person axes, and the community
  constraints. Sections 1–85 were left as they were, with cross-references
  where Part 0 reinterprets them.
- Six ADRs written: 0001 Baritone, 0002 perception firewall, 0003 memory
  firewall, 0004 external awareness, 0005 autonomy versus authority, 0006 two
  clocks.
- `docs/SAFETY.md` reframed so self-preservation, experimental containment and
  shared-world property policy are distinct concerns. **The kernel was not
  touched.**
- `docs/CURRENT_STATE.md` corrected to `48728e8`, with a Known Deviations
  section listing C1–C6.
- `REALITY_VALIDATION.md` records the three live skill validations of
  2026-09-16 with their provenance, including the fact that the artifacts are
  local and uncommitted.

### What did not change

No source file, no schema, no test. `mise run check` passes unchanged.

---

## Phase 8: Canonicalization, Evidence Preservation, and CI

**Commit:** this one
**Date:** 2026-09-22
**Branch:** `refactor/person-v1-architecture`

### Objective

A small cleanup pass before Baritone integration: fold the frozen architecture
directly into `docs/PERSON_SPEC.md`'s numbered sections instead of carrying it
as a separate overriding layer, preserve the live validation evidence Phase 7
found but did not commit, and add CI. Documentation and evidence preservation
only.

### What changed

- `docs/PERSON_SPEC.md` **normalized**. Phase 7's "Part 0" block (997 lines)
  was distributed into the relevant existing numbered sections (1, 3, 4, 6, 8,
  10, 13, 14, 22, 24, 26, 28, 30, 37, 39, 41, 45, 50, 51, 60, 61), each new
  subsection landing beside the material it extends. No "Part 0 overrides
  section N" note remains anywhere in the document; a reader goes through it
  once, top to bottom. The status-tag legend (CURRENTLY IMPLEMENTED / PLANNED
  PERSON V1 / FUTURE SUPER-PERSON / FUTURE COMMUNITY) moved to section 1.1 and
  is used the same way throughout. The architectural contradictions (C1-C6)
  moved out entirely, into `docs/CURRENT_STATE.md`, "Known Deviations", with
  full text rather than an index, since that document's job is to say where
  the code and the spec disagree. Every cross-reference to the old `0.X`
  numbering, across `AGENTS.md`, `CLAUDE.md`, `docs/SAFETY.md`,
  `docs/ARCHITECTURE.md` and all six ADRs, was updated to the new section
  numbers. **No architectural decision from Phase 7 changed**; this is
  document structure only.
- Three local live validation reports from 2026-09-16 (`wait_safely` once,
  `return_home` twice), found by Phase 7 but left uncommitted under
  gitignored `runs/`, were audited for sensitive fields and copied into a
  tracked validation-evidence directory with SHA-256 provenance recorded.
- A CI workflow was added running the repository's own canonical check
  command on push and pull request.

### What did not change

No source file, no schema, no test, no architectural decision. `mise run
check` passes unchanged.

---

## Summary: Major Historical Phase SHAs

| Phase                          | Commit Range          | Key SHA                                |
| ------------------------------ | --------------------- | -------------------------------------- |
| Foundation (vertical slice)    | `6b99830`             | `6b99830` (tagged `v0.1.0-foundation`) |
| Adapter audit & 6 defects      | `d557275` → `2d2b48f` | `d557275`, `0f6cc1a`, `2d2b48f`        |
| Pre-LAN readiness              | `062f7fe`             | `062f7fe`                              |
| First contact (4 defects)      | `f0b3ff8`, `9ff7778`  | `f0b3ff8`, `9ff7778`                   |
| Single-skill harness           | `b692153`             | `b692153`                              |
| Second contact + traceability  | `5b9a395`             | `5b9a395`                              |
| Canonical documentation        | `48728e8`             | `48728e8`                              |
| Person v1 reconciliation       | `af304a3`             | documentation only                     |
| Canonicalization, evidence, CI | this commit           | documentation + evidence + CI config   |

---

## What Intentionally Remained Out of Scope (Through All Phases)

- Language model integration
- Neural policy / deep RL
- Affect / emotion systems
- Social memory / relationships / incidents
- Projects (beyond goal suspension)
- Redstone / advanced construction
- Multi-Person architecture
- Death/respawn/recovery loop
- SQLite persistence
- Live skill execution (only `observe` has run live)
- Any capability not required for survival vertical slice

---

## Commit Signing

All commits signed with GPG key `8BBCB014DE46077B` (Oxide 1-6 <yes.par781@gmail.com>).
Tag `v0.1.0-foundation` also signed.
**History must not be rewritten.**
