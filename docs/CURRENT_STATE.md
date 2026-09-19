# CURRENT_STATE.md — Factual Snapshot of Person (Commit 7501194)

**Last verified against commit:** `7501194` (HEAD, feat/lan-validation)
**Tag:** `v0.1.0-foundation` (`6b99830`)
**Date:** 2026-09-19

---

## 1. Current Architecture

### Processes

| Process                     | Language   | Responsibility                                                                                                                         |
| --------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `person` (Node)             | TypeScript | Minecraft connectivity, navigation, safety kernel, permissions, protected areas, skill execution, outcome attribution, episode reports |
| `person-cognition` (Python) | Python     | Decision context, goals, planning, routines, policy, evidence journal, learning, learning reports                                      |

**Relationship:** Node is parent; spawns cognition over stdio. If cognition crashes/hangs/violates protocol, Node keeps body control and ends episode cleanly.

### Trust Boundary

```
Python cognition  →  SkillInvocation  →  [TRUST BOUNDARY]  →  Node validator  →  Safety kernel  →  Skill executor  →  Embodiment
```

- Cognition never holds Mineflayer objects, sockets, or coordinates it chose
- Only physical request: `SkillInvocation` (skill id + scalar parameters + cost limits)
- Protocol schema rejects anything else (`unevaluatedProperties: false`)

---

## 2. Implemented Runtime Components

### Protocol (`packages/protocol/`)

- **Version:** `shroud-learning-v2`
- **11 message types** with canonical JSON Schemas
- Dual runtime validation: Ajv (Node) + jsonschema (Python)
- Shared corpus: 11 valid, 18 invalid messages — both runtimes agree on all
- Framing: newline-delimited JSON, 1 MB cap, bounded reader

### Skills (`packages/skills/`, `apps/node-runtime/src/skills/impl/`)

**21 skills, all implemented** (architecture test asserts spec/impl sets identical, no placeholders):

| Category  | Skills                                                                                             |
| --------- | -------------------------------------------------------------------------------------------------- |
| Emergency | `flee`, `dig_in`, `wait_safely`, `return_home`                                                     |
| Food      | `gather_plant_food`, `hunt_safe_passive_animals`, `cook_food`, `eat_to_target`                     |
| Resources | `gather_wood`, `mine_stone`, `mine_coal`                                                           |
| Crafting  | `craft_basic_tools`, `craft_stone_tools`, `craft_furnace`, `craft_chest`                           |
| Shelter   | `build_basic_shelter`, `repair_shelter`                                                            |
| Storage   | `place_owned_chest`, `deposit_owned_storage`, `withdraw_owned_storage`, `loot_permitted_container` |

**Terminal states:** SUCCESS, FAILED, INTERRUPTED, PREEMPTED, TIMED_OUT, INVALIDATED, UNREACHABLE, DEATH, DISCONNECTED

### Safety Kernel (`apps/node-runtime/src/safety/`)

- **L0–L4 hierarchy** (pure function of world snapshot)
- **Verdicts:** ACCEPT, REJECT, PREEMPT, REPLACE
- **Protected areas** enforced at 4 levels: proposal, route selection, skill execution, each destructive interaction
- **Cost limits clamped down** to skill spec (never up)
- **Attribution:** `SkillOutcome` always carries `requestedSkill` + `executedSkill`

### Embodiment Port (`apps/node-runtime/src/embodiment/types.ts`)

Two implementations, same skill code:

- `MineflayerEmbodiment` — drives real Minecraft 1.16.1 client
- `FixtureWorld` — deterministic simulation (tests exercise same skill code)

### Cognition (`apps/cognition/python/person_cognition/`)

- **Decision context:** 7 bounded dimensions (health_band, food_band, day_phase, threat, home_state, tool_tier, food_state)
- **Goal system:** SurvivalGoalProvider, goal stack with queue/activate/suspend/resume/block/complete
- **Planner:** Symbolic means-ends from skill preconditions/effects; minimal deterministic plans
- **Routines:** Content-derived stable identifiers, nesting supported
- **Policy:** DeterministicFallback + EvidencePolicy (Beta posterior, risk-dominant scoring, safe envelope)
- **Learning modes:** off / shadow / supervised (never auto-enabled)

### Evidence & Persistence (`packages/persistence/`)

- **Append-only JSONL journal** (fsynced, chained by `previous_event_id`)
- **Atomic checksummed snapshots** (temp-file + rename)
- **Strict reading:** rejects corruption, ignores duplicates, drops crash-truncated tail
- **Restore:** replay from newest valid snapshot, fallback to full rebuild
- **Statistics keyed by training context** — fixture/live evidence never merges
- **Event types:** episode_started, goal_selected, routine_selected, routine_outcome, skill_started, skill_completed, skill_failed, skill_interrupted, emergency_override, death, episode_ended

### Configuration (`packages/config/`)

- TOML, validated against JSON Schema by both runtimes
- Legacy Shroud V1 migration supported (`validate --migrate`)
- V1 Q-learning checkpoints recognised and refused (not converted)
- LAN port/host are **runtime overrides** (`--port`, `--host`) — never written to file

---

## 3. Protocol

**Message types:**

| From Runtime       | From Cognition  |
| ------------------ | --------------- |
| SessionHello       | CognitionReady  |
| Observation        | GoalDecision    |
| ValidationDecision | PolicyDecision  |
| SkillStarted       | SkillInvocation |
| SkillOutcome       |                 |
| EmergencyEvent     |                 |
| EpisodeEvent       |                 |

Every message carries: `protocolVersion`, `messageId`, `personId`, `sessionId`, `worldId`, `tick`, `timestamp`, `type`

**SkillInvocation** — only physical request cognition can make:

```json
{
  "skillId": "gather_wood",
  "skillVersion": 1,
  "parameters": { "target_amount": 16, "max_distance": 48 },
  "limits": { "maxTicks": 2400, "maxDistance": 64, "minHealth": 6 }
}
```

Parameters: scalars only. No command, script, chat, or coordinate fields possible.

---

## 4. Skill Library Status

| Skill                     | Fixture | Adapter (Conformance)           | Live       | Notes                                  |
| ------------------------- | ------- | ------------------------------- | ---------- | -------------------------------------- |
| flee                      | ✅ pass | ✅ partial                      | ❌ not run | neutral mobs, threat set unified       |
| dig_in                    | ✅ pass | ✅ dig/place                    | ❌ not run | diggable ground check added            |
| wait_safely               | ✅ pass | ✅ waitTicks                    | ❌ not run | harness prepared                       |
| return_home               | ✅ pass | ✅ moveTo/dig/place             | ❌ not run | harness prepared, needs operator setup |
| gather_plant_food         | ✅ pass | ✅ findBlocks/moveTo/dig        | ❌ not run | drop collection unverified             |
| hunt_safe_passive_animals | ✅ pass | ✅ entity classification/attack | ❌ not run | metadata crash + named animal fixed    |
| cook_food                 | ✅ pass | ✅ smelt                        | ❌ not run | partial output + empty smelt fixed     |
| eat_to_target             | ✅ pass | ✅ consume                      | ❌ not run | contract corrected (3 items, not 1)    |
| gather_wood               | ✅ pass | ✅ full path                    | ❌ not run | tool durability unmodelled             |
| mine_stone                | ✅ pass | ✅ full path                    | ❌ not run | needs exposed stone                    |
| mine_coal                 | ✅ pass | ✅ full path                    | ❌ not run | needs exposed ore                      |
| craft_basic_tools         | ✅ pass | ✅ craft/place                  | ❌ not run | server-authoritative recipes           |
| craft_stone_tools         | ✅ pass | ✅ craft                        | ❌ not run | table placement unverified             |
| craft_furnace             | ✅ pass | ✅ craft/place                  | ❌ not run | table placement unverified             |
| craft_chest               | ✅ pass | ✅ craft                        | ❌ not run | table placement unverified             |
| build_basic_shelter       | ✅ pass | ✅ place/blockAt                | ❌ not run | irregular terrain unverified           |
| repair_shelter            | ✅ pass | ✅ place/blockAt                | ❌ not run | same                                   |
| place_owned_chest         | ✅ pass | ✅ place/provenance             | ❌ not run | container entity unverified            |
| deposit_owned_storage     | ✅ pass | ✅ deposit refusal              | ❌ not run | slot handling unverified               |
| withdraw_owned_storage    | ✅ pass | ✅ inspectContainer/withdraw    | ❌ not run | first-withdrawal bug fixed             |
| loot_permitted_container  | ✅ pass | ✅ inspectContainer/withdraw    | ❌ not run | takes up to amount of every type       |

**Status vocabulary used strictly:** Fixture / Adapter / Live (nothing marked Live)

---

## 5. Safety

**Proven in fixture and against conformance double:**

- Protected-area harvest/build/movement denial at all 4 enforcement levels
- Detour around protected strip; refusal with no legal detour; no partial movement
- Replanning cannot cross protected area (guard installed in pathfinder step exclusion)
- Existing-container deposit denied (schema constant + runtime guard + embodiment refusal)
- Owned-container deposit/withdrawal with provenance
- Villager, named-animal, tamed-animal, player protection (schema constants with single legal value)
- Hostile emergency preemption with attribution to executed skill
- Refuge chosen only where diggable ground exists

**NOT proven against Minecraft server:** All mechanisms untested in real world.

---

## 6. Cognition / Planning / Learning Status

| Component                                 | Status                                                     |
| ----------------------------------------- | ---------------------------------------------------------- |
| Decision context (7 dimensions)           | IMPLEMENTED + TESTED IN FIXTURE                            |
| Homeostatic survival goals                | IMPLEMENTED + TESTED IN FIXTURE                            |
| Goal stack (suspend/resume)               | IMPLEMENTED + TESTED IN FIXTURE                            |
| Symbolic planner (preconditions/effects)  | IMPLEMENTED + TESTED IN FIXTURE                            |
| Routine model (nesting, stable IDs)       | IMPLEMENTED + TESTED IN FIXTURE                            |
| Deterministic fallback policy             | IMPLEMENTED + TESTED IN FIXTURE                            |
| Evidence policy (Beta posterior)          | IMPLEMENTED + TESTED IN FIXTURE                            |
| Safe exploration envelope                 | IMPLEMENTED + TESTED IN FIXTURE                            |
| Learning modes (off/shadow/supervised)    | IMPLEMENTED + TESTED IN FIXTURE                            |
| Evidence journal (append-only, chained)   | IMPLEMENTED + TESTED IN FIXTURE                            |
| Atomic snapshots + restore                | IMPLEMENTED + TESTED IN FIXTURE                            |
| Restart reuse (evidence survives restart) | IMPLEMENTED + TESTED IN FIXTURE (integration test)         |
| Prediction error logging                  | IMPLEMENTED + TESTED IN FIXTURE (inert, changes no policy) |
| Tick budget instrumentation               | IMPLEMENTED + TESTED IN FIXTURE                            |

**Future providers (placeholder, raise not implemented):**
MemoryProvider, WorldModelProvider, AffectProvider, LanguageProvider, SocialProvider, ProjectProvider, ExplorationProvider

---

## 7. Persistence / Evidence

| Feature                              | Status                          |
| ------------------------------------ | ------------------------------- |
| Immutable append-only journal        | IMPLEMENTED + TESTED IN FIXTURE |
| Event chaining (`previous_event_id`) | IMPLEMENTED + TESTED IN FIXTURE |
| Duplicate detection                  | IMPLEMENTED + TESTED IN FIXTURE |
| Corruption rejection                 | IMPLEMENTED + TESTED IN FIXTURE |
| Crash-truncated tail handling        | IMPLEMENTED + TESTED IN FIXTURE |
| Atomic snapshots (checksummed)       | IMPLEMENTED + TESTED IN FIXTURE |
| Snapshot invalidation → rebuild      | IMPLEMENTED + TESTED IN FIXTURE |
| Training-context separation          | IMPLEMENTED + TESTED IN FIXTURE |
| Raw counts (not scores) persisted    | IMPLEMENTED + TESTED IN FIXTURE |
| `evidence_refs` on statistics        | IMPLEMENTED + TESTED IN FIXTURE |
| RNG seeds on fixture episodes        | IMPLEMENTED + TESTED IN FIXTURE |

---

## 8. CLI / Debug / Validation Capabilities

| Command                                                | Purpose                                                       | Live-Safe                                      |
| ------------------------------------------------------ | ------------------------------------------------------------- | ---------------------------------------------- |
| `person run`                                           | Autonomous episode                                            | ✅ (learning off by default)                   |
| `person learn --mode shadow\|supervised`               | Put learner in control                                        | ⚠️ safety kernel still decides                 |
| `person validate <config>`                             | Config schema + cognition cross-check                         | ✅ no connection                               |
| `person inspect skills\|evidence\|config\|predictions` | Debug introspection                                           | ✅ no connection                               |
| `person observe`                                       | Connect, capture one observation, validate schema, disconnect | ✅ runs no skill, writes no evidence           |
| `person compare <ref> <actual>`                        | Diff observations, flag suspicious defaults                   | ✅ no connection                               |
| `person status`                                        | Read runtime telemetry (never connects)                       | ✅ read-only                                   |
| `person skill-test --skill X`                          | Single-skill validation through shared dispatch               | ⚠️ changes world, marks operator contamination |

**Aliases:** `shroud` = `person`, `shroud-train` = `person learn`

---

## 9. Minecraft Embodiment Status

| Aspect                                                             | Status                           |
| ------------------------------------------------------------------ | -------------------------------- |
| Mineflayer connection / auth / spawn                               | CONFORMANCE-TESTED (double)      |
| Entity metadata (sparse object, not array)                         | FIXED + CONFORMANCE-TESTED       |
| Custom name extraction (named animals)                             | FIXED + CONFORMANCE-TESTED       |
| Hostile classification (registry + explicit list)                  | FIXED + CONFORMANCE-TESTED       |
| Neutral mobs (threat only after damage)                            | FIXED + CONFORMANCE-TESTED       |
| Armour points from equipped slots                                  | FIXED + CONFORMANCE-TESTED       |
| Biome from block registry (not prismarine-block bug)               | FIXED + CONFORMANCE-TESTED       |
| Light level from block (fallback to clock)                         | FIXED + CONFORMANCE-TESTED       |
| Dimension from `bot.game.dimension`                                | FIXED + CONFORMANCE-TESTED       |
| Free slots from inventory window                                   | FIXED + CONFORMANCE-TESTED       |
| Server-authoritative recipes                                       | FIXED + CONFORMANCE-TESTED       |
| Empty craft/smelt → explicit failure                               | FIXED + CONFORMANCE-TESTED       |
| Partial smelt collection                                           | FIXED + CONFORMANCE-TESTED       |
| Container inspection before withdrawal                             | FIXED + CONFORMANCE-TESTED       |
| Connection diagnostics (14 failure classes)                        | IMPLEMENTED + CONFORMANCE-TESTED |
| Readiness validation (chunks, clock, inventory, vitals, dimension) | IMPLEMENTED + CONFORMANCE-TESTED |
| World rules validation (survival, difficulty, daylight, overworld) | IMPLEMENTED + CONFORMANCE-TESTED |
| Bounded disconnect (no orphan timer)                               | FIXED + CONFORMANCE-TESTED       |

**First contact (2026-09-15):** `person observe` connected, spawned in bounds, produced schema-valid observation, disconnected cleanly. 4 observation defects found and fixed.
**Second contact (2026-09-16):** All 4 corrections verified against real Minecraft.

**No skill has been run live against Minecraft.** `wait_safely` and `return_home` harnesses prepared; pending.

---

## 10. Fixture / Conformance Status

| Environment                                                          | Purpose                                           | Status                                             |
| -------------------------------------------------------------------- | ------------------------------------------------- | -------------------------------------------------- |
| Deterministic fixture world (`fixtures/src/`)                        | Integration tests, skill logic, evidence pipeline | Fully exercised — 184 Node tests, 129 Python tests |
| Mineflayer conformance double (`tests/support/mineflayer-double.ts`) | Adapter vs real 1.16.1 data tables                | 27 tests — exercises adapter code paths            |
| Protocol corpus (`fixtures/protocol-corpus/`)                        | Cross-runtime schema agreement                    | 29 messages — both runtimes agree                  |

---

## 11. Current Validation Milestone

**Milestone 1 complete:** Reality validation — adapter audited, 6 defects fixed, observation validated live (2 contacts), single-skill harness built.

**Milestone 2 (current):** Single-skill live validation — `person skill-test` harness ready for `wait_safely` and `return_home`. No live runs performed yet.

**Blockers for live validation (from REALITY_VALIDATION.md):**

1. No server available in development environment
2. Conformance double is a model, not the real API
3. Pathfinder on real terrain untested
4. Server-side placement/crafting/smelting/container timing untested
5. Real mob behavior / flee adequacy unknown
6. Tick budgets meaningless until measured live
7. Death/respawn not designed

---

## 12. Known Limitations / Backlog

| Limitation                                                                         | Source                   |
| ---------------------------------------------------------------------------------- | ------------------------ |
| Mineflayer adapter never run against real server                                   | IMPLEMENTATION_REPORT.md |
| No dig-down skill (mine_stone/coal need exposed stone)                             | IMPLEMENTATION_REPORT.md |
| Fixture is simulation, not Minecraft                                               | IMPLEMENTATION_REPORT.md |
| Planner bounded (depth/branch/node caps) — may return no plan                      | IMPLEMENTATION_REPORT.md |
| Goals: survival only (projects/social/self-generated future)                       | IMPLEMENTATION_REPORT.md |
| Death ends episode — no respawn/recovery loop                                      | IMPLEMENTATION_REPORT.md |
| Evidence written by cognition — last outcome missing if cognition dies mid-episode | IMPLEMENTATION_REPORT.md |
| Inventory reconciliation on resume not reimplemented                               | IMPLEMENTATION_REPORT.md |
| `loot_permitted_container` withdraws all types up to amount                        | IMPLEMENTATION_REPORT.md |
| One Person per runtime (multi-Person not supported)                                | IMPLEMENTATION_REPORT.md |
| Tick budgets invented in fixture (4 ticks/step, 12/dig)                            | REALITY_VALIDATION.md    |
| Prediction error recorded but inert (no world model consumes it)                   | REALITY_VALIDATION.md    |
| Single-skill live validation not started                                           | REALITY_VALIDATION.md    |

---

## 13. Test Counts

| Suite        | Tests   | Pass    |
| ------------ | ------- | ------- |
| Node (all)   | 188     | 188     |
| Python (all) | 129     | 129     |
| **Total**    | **317** | **317** |

**Coverage by area:**

- Protocol: 47 (Node + Python)
- Skills: 14
- Safety: 22
- Architecture: 20 (Node + Python)
- Planner: 20
- Policy: 11
- Persistence: 10
- Cognition: 15
- CLI: 20
- Integration: 10
- Adapter/Conformance: 27
- Validation: 13
- Observation: 4

`mise run check` **PASSES** (typecheck, build, lint, test-node, test-python)

---

## 14. Key Files for Understanding Current State

| File                       | Purpose                                                           |
| -------------------------- | ----------------------------------------------------------------- |
| `REALITY_VALIDATION.md`    | Canonical validation evidence (fixture/adapter/live distinctions) |
| `IMPLEMENTATION_REPORT.md` | Cumulative implementation record (Milestone 0 + 1)                |
| `TRACEABILITY.md`          | Requirements → code → tests mapping                               |
| `docs/LAN_TESTING.md`      | Manual validation ladder                                          |
| `docs/EVALUATION.md`       | What automated suite proves / does not prove                      |
| `docs/ARCHITECTURE.md`     | Process diagram, packages, decision loop                          |
| `docs/PERSON_SPEC.md`      | Full architectural specification (source of truth)                |
