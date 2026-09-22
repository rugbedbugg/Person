# CURRENT_STATE.md — Factual Snapshot of Person (Commit d0e9398)

**Last verified against commit:** `d0e9398` (tip of `feat/lan-validation`)
**Branch this snapshot was taken on:** `refactor/person-v1-architecture`
**Tag:** `v0.1.0-foundation` (`6b99830`)
**Date:** 2026-09-22

This file is strictly factual. It describes what exists in the source tree and
what has been run. **`docs/PERSON_SPEC.md` specifies a great deal that is not
here**, including the perception firewall's sense model, the memory firewall's
retrieval layer, belief, affect, language, social cognition, projects, web
research, external chat, the Baritone motor backend and the 1.16.5 target.
Part 0 of that document was frozen on 2026-09-22 and **changed no code**. None
of it appears below, because none of it exists.

The Minecraft target is **Java 1.16.1**. A move to 1.16.5 is planned as part of
the Baritone work (ADR 0001) and has not begun.

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

| Skill                     | Fixture | Adapter (Conformance)           | Live                      | Notes                               |
| ------------------------- | ------- | ------------------------------- | ------------------------- | ----------------------------------- |
| flee                      | ✅ pass | ✅ partial                      | ❌ not run                | neutral mobs, threat set unified    |
| dig_in                    | ✅ pass | ✅ dig/place                    | ❌ not run                | diggable ground check added         |
| wait_safely               | ✅ pass | ✅ waitTicks                    | ✅ **1 run, 2026-09-16**  | SUCCESS; no operator setup          |
| return_home               | ✅ pass | ✅ moveTo/dig/place             | ✅ **2 runs, 2026-09-16** | SUCCESS; both operator-positioned   |
| gather_plant_food         | ✅ pass | ✅ findBlocks/moveTo/dig        | ❌ not run                | drop collection unverified          |
| hunt_safe_passive_animals | ✅ pass | ✅ entity classification/attack | ❌ not run                | metadata crash + named animal fixed |
| cook_food                 | ✅ pass | ✅ smelt                        | ❌ not run                | partial output + empty smelt fixed  |
| eat_to_target             | ✅ pass | ✅ consume                      | ❌ not run                | contract corrected (3 items, not 1) |
| gather_wood               | ✅ pass | ✅ full path                    | ❌ not run                | tool durability unmodelled          |
| mine_stone                | ✅ pass | ✅ full path                    | ❌ not run                | needs exposed stone                 |
| mine_coal                 | ✅ pass | ✅ full path                    | ❌ not run                | needs exposed ore                   |
| craft_basic_tools         | ✅ pass | ✅ craft/place                  | ❌ not run                | server-authoritative recipes        |
| craft_stone_tools         | ✅ pass | ✅ craft                        | ❌ not run                | table placement unverified          |
| craft_furnace             | ✅ pass | ✅ craft/place                  | ❌ not run                | table placement unverified          |
| craft_chest               | ✅ pass | ✅ craft                        | ❌ not run                | table placement unverified          |
| build_basic_shelter       | ✅ pass | ✅ place/blockAt                | ❌ not run                | irregular terrain unverified        |
| repair_shelter            | ✅ pass | ✅ place/blockAt                | ❌ not run                | same                                |
| place_owned_chest         | ✅ pass | ✅ place/provenance             | ❌ not run                | container entity unverified         |
| deposit_owned_storage     | ✅ pass | ✅ deposit refusal              | ❌ not run                | slot handling unverified            |
| withdraw_owned_storage    | ✅ pass | ✅ inspectContainer/withdraw    | ❌ not run                | first-withdrawal bug fixed          |
| loot_permitted_container  | ✅ pass | ✅ inspectContainer/withdraw    | ❌ not run                | takes up to amount of every type    |

**Status vocabulary used strictly:** Fixture / Adapter / Live. Two skills are
marked Live; the other nineteen are not. Live evidence is the three
`person skill-test` reports described in `REALITY_VALIDATION.md`, which are
local operator artifacts under `runs/` and are **not committed** (`runs/` is
gitignored).

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
**First live skill execution (2026-09-16):** three `person skill-test` runs:
`wait_safely` once, `return_home` twice. All SUCCESS, requested and executed
skill identical in every run, effect comparison matched `at_home` on both
navigation runs, learning fingerprint unchanged, all disconnects clean. Details
and provenance in `REALITY_VALIDATION.md`.

**Nineteen of twenty-one skills have never been run live.** The next stage in
the intended order is basic gathering, and it has not been started.

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

**Milestone 2, stages 1 and 2 complete:** Single-skill live validation. `wait_safely` and `return_home` run live through `person skill-test` on 2026-09-16, both SUCCESS. Stages 3–8 (gathering, crafting, mining, placement, containers, hunting) not started.

**Phase 0 architecture reconciliation (2026-09-22):** documentation only. `docs/PERSON_SPEC.md` Part 0 frozen, six ADRs written, no production behaviour changed.

**Remaining blockers for live validation (from REALITY_VALIDATION.md):**

1. ~~No server available~~. Closed: connection, readiness and shutdown exercised live
2. Conformance double is a model, not the real API
3. Pathfinder on real terrain: partly addressed (2 successful routes), still the largest risk
4. Server-side placement/crafting/smelting/container timing untested
5. Real mob behavior / flee adequacy unknown (both live worlds were Peaceful)
6. Tick budgets still not revised on live measurement
7. Death/respawn not designed

---

## 11a. Known Deviations from the Frozen Architecture

Found during the Phase 0 reconciliation on 2026-09-22 and **deliberately not
fixed**. Each is a place where the code and `docs/PERSON_SPEC.md` Part 0
disagree. Full statements are in PERSON_SPEC section 0.24; this is the index.

| ID  | Deviation                                                            | Introduced | Decision needed before            |
| --- | -------------------------------------------------------------------- | ---------- | --------------------------------- |
| C1  | The `Observation` carries exact coordinates to cognition             | `6b99830`  | any spatial-memory work           |
| C2  | Protected-area entry is an L0 "hard safety" trigger                  | `6b99830`  | any change to the kernel's levels |
| C3  | `WorldMemory` is an ownership ledger, not memory, and is named badly | `6b99830`  | the memory system, or a rename    |
| C4  | Skills choose their own targets; cognition cannot name one           | `6b99830`  | any goal about a particular thing |
| C5  | The `Embodiment` port is shaped by what Mineflayer offers            | `6b99830`  | the Baritone spike (ADR 0001)     |
| C6  | No belief, memory or knowledge representation exists at all          | n/a, a gap | any epistemic claim about Person  |

Two facts that soften C1, both established by reading the source rather than
assumed:

- Cognition never reads a coordinate. `person_planner.state` and
  `person_cognition.context` use `distance` and counts only, and a search across
  `apps/cognition/python/` and `packages/planner/python/` finds no positional
  access.
- Cognition cannot send one back. `SkillInvocation` is scalar-only, enforced by
  the schema and by `tests/architecture/architecture.test.ts`.

So the outbound half of the perception firewall is enforced by contract, and the
inbound half is currently enforced only by the fact that nobody reads the field.

---

## 12. Known Limitations / Backlog

| Limitation                                                                         | Source                    |
| ---------------------------------------------------------------------------------- | ------------------------- |
| Mineflayer adapter exercised live for observation and 2 skills only                | REALITY_VALIDATION.md     |
| No dig-down skill (mine_stone/coal need exposed stone)                             | IMPLEMENTATION_REPORT.md  |
| Fixture is simulation, not Minecraft                                               | IMPLEMENTATION_REPORT.md  |
| Planner bounded (depth/branch/node caps) — may return no plan                      | IMPLEMENTATION_REPORT.md  |
| Goals: survival only (projects/social/self-generated future)                       | IMPLEMENTATION_REPORT.md  |
| Death ends episode — no respawn/recovery loop                                      | IMPLEMENTATION_REPORT.md  |
| Evidence written by cognition — last outcome missing if cognition dies mid-episode | IMPLEMENTATION_REPORT.md  |
| Inventory reconciliation on resume not reimplemented                               | IMPLEMENTATION_REPORT.md  |
| `loot_permitted_container` withdraws all types up to amount                        | IMPLEMENTATION_REPORT.md  |
| One Person per runtime (multi-Person not supported)                                | IMPLEMENTATION_REPORT.md  |
| Tick budgets invented in fixture (4 ticks/step, 12/dig)                            | REALITY_VALIDATION.md     |
| Prediction error recorded but inert (no world model consumes it)                   | REALITY_VALIDATION.md     |
| Single-skill live validation: stages 1 and 2 done, 3 to 8 not started              | REALITY_VALIDATION.md     |
| No belief, memory, affect, language, social or project system exists               | PERSON_SPEC 0.24 C6       |
| Perception has no visibility, occlusion or pose model                              | PERSON_SPEC 0.4, ADR 0002 |

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

`mise run check` **PASSES** (typecheck, build, lint, test-node, test-python).
Verified at `d0e9398` on 2026-09-22: Node 188 pass / 0 fail, Python 129 pass.

---

## 14. Key Files for Understanding Current State

| File                         | Purpose                                                           |
| ---------------------------- | ----------------------------------------------------------------- |
| `REALITY_VALIDATION.md`      | Canonical validation evidence (fixture/adapter/live distinctions) |
| `IMPLEMENTATION_REPORT.md`   | Cumulative implementation record (Milestone 0 + 1)                |
| `TRACEABILITY.md`            | Requirements → code → tests mapping                               |
| `docs/LAN_TESTING.md`        | Manual validation ladder                                          |
| `docs/EVALUATION.md`         | What automated suite proves / does not prove                      |
| `docs/ARCHITECTURE.md`       | Current and target process diagrams, packages, decision loop      |
| `docs/PERSON_SPEC.md`        | Full architectural specification (source of truth); Part 0 first  |
| `docs/decisions/`            | ADRs 0001–0006, frozen 2026-09-22                                 |
| `docs/SEMANTIC_TARGETING.md` | The referent scheme compositional actions will need               |
