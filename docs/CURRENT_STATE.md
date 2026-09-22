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
That specification's architecture was reconciled on 2026-09-22 and **changed
no code**. None of it appears below, because none of it exists.

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

**Phase 0 architecture reconciliation (2026-09-22):** documentation only. `docs/PERSON_SPEC.md` architecture frozen, six ADRs written, no production behaviour changed. **Phase 0.5 normalization (2026-09-22):** the frozen architecture was integrated into PERSON_SPEC's numbered sections in place, so it is read linearly rather than as an override layer; see `docs/PROJECT_HISTORY.md`.

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

Found during the Phase 0 reconciliation on 2026-09-22, and **deliberately not
fixed**. Each is a place where the code and `docs/PERSON_SPEC.md` disagree
about what the right shape is. None of them is a bug in the current
implementation. This is the canonical, full-detail record; nothing shorter
exists elsewhere, and `docs/PERSON_SPEC.md` points here rather than repeating
it.

| ID  | Deviation                                                            | Introduced | Decision needed before            |
| --- | -------------------------------------------------------------------- | ---------- | --------------------------------- |
| C1  | The `Observation` carries exact coordinates to cognition             | `6b99830`  | any spatial-memory work           |
| C2  | Protected-area entry is an L0 "hard safety" trigger                  | `6b99830`  | any change to the kernel's levels |
| C3  | `WorldMemory` is an ownership ledger, not memory, and is named badly | `6b99830`  | the memory system, or a rename    |
| C4  | Skills choose their own targets; cognition cannot name one           | `6b99830`  | any goal about a particular thing |
| C5  | The `Embodiment` port is shaped by what Mineflayer offers            | `6b99830`  | the Baritone spike (ADR 0001)     |
| C6  | No belief, memory or knowledge representation exists at all          | n/a, a gap | any epistemic claim about Person  |
| C7  | The Mineflayer route veto missed two movement families (repaired)    | `6b99830`  | resolved 2026-09-22, see below    |

### C1. The observation carries exact coordinates

`Observation.environment.position`, and the `position` field on every nearby
resource, hazard, container, workstation and entity, are exact block
coordinates delivered to cognition on every tick. `docs/PERSON_SPEC.md` section
24.4 says coordinates should reach Person only through a deliberate inspection
capability.

Mitigating facts, established by reading the source rather than assumed: the
cognition process never reads any of them. `person_planner.state` and
`person_cognition.context` use `distance` and counts only, and a search for
coordinate access across `apps/cognition/python/` and `packages/planner/python/`
finds nothing. Cognition also cannot send a coordinate back: `SkillInvocation`
is scalar-only and an architecture test enforces it.

So the outbound half of the perception firewall (section 8) is enforced by
contract, and the inbound half is currently enforced by nothing but the fact
that nobody reads the field. **Decision required** before the first cognitive
subsystem that would be tempted to read them, which is spatial memory.

### C2. Protected areas are modelled as hard safety

`protected_area_entry` is an L0 trigger in `safety-kernel.ts`, beside lava
exposure and suffocation. L0 is described everywhere as hard safety, which
frames operator containment as though it were self-preservation, and frames a
configured fence as though it were an intrinsic property of Person.

`docs/PERSON_SPEC.md` section 13 and `docs/SAFETY.md` now separate
self-preservation, experimental containment and shared-world property policy
conceptually. The runtime behaviour is deliberately unchanged: the fence should
still stop Person. What is wrong is only the claim about why.

**Decision required:** whether the kernel grows a containment level distinct
from L0, or whether the distinction stays documentary. No production change has
been made.

### C3. `WorldMemory` is not memory

`apps/node-runtime/src/runtime/world-memory.ts` is a runtime-owned ownership
and placement ledger: home record, placed blocks, storage provenance, furnace
and crafting-table positions. It is privileged engineering state that the
observation builder reads to derive semantic facts. It is not, and must never
become, Person's recollection (`docs/PERSON_SPEC.md` section 24).

**Decision required:** rename at the next milestone that touches it, or accept
the name and document it. Both are defensible; leaving it ambiguous is not.

### C4. Skills choose their own targets

Every skill picks its own target: `gather_wood` takes the nearest permitted
tree. `docs/PERSON_SPEC.md` section 10.1 requires perceived, validated
referents so that Person can say which tree. `docs/SEMANTIC_TARGETING.md`
already describes the scheme and explains why it has not been built.

**Not a contradiction yet.** It becomes one the moment a goal is about a
particular thing, which is the same moment compositional actions are needed.

### C5. The embodiment port is a Mineflayer-shaped port

`Embodiment` exposes `moveTo`, `dig`, `place`, `craft`, `smelt`, `consume`,
`attack`, `deposit`, `withdraw`, `waitTicks`, `inspectContainer`, `blockAt`,
`findBlocks`, `findEntities` and `snapshot`. It is already an abstraction
rather than a Mineflayer passthrough, and the fixture world proves a second
implementation is possible. It is nonetheless shaped by what Mineflayer
happens to offer: there is no `look`, no `use held item`, no generic entity
interaction, and `snapshot()` is synchronous and total.

A Baritone backend implements `moveTo` naturally and `findBlocks` naturally,
and would want to supply far more geometry than the port asks for.
`docs/PERSON_SPEC.md` section 8 says it must not.

**Decision required before the Baritone spike**, and only about the shape of
`snapshot()`: see ADR 0001.

### C6. No belief, memory or knowledge representation exists

`docs/PERSON_SPEC.md` sections 24, 25 and 26 specify episodic, semantic,
spatial, social and autobiographical memory, consolidation, forgetting and a
predictive-causal world model. None of it exists. The symbolic state is
recomputed from the latest observation every tick, so Person currently has no
way to be wrong about the world in the sense section 26 requires: it has no
belief that could disagree with an observation.

Prediction error is recorded, which is the input such a model needs, and
nothing consumes it.

**Not a contradiction, a gap.** Recorded here because the difference between
"specified" and "implemented" is the thing this reconciliation exists to keep
visible.

### C7. The Mineflayer route veto did not cover every movement family

Found on 2026-09-22 during the Baritone feasibility spike, then **re-diagnosed
and repaired** the same day once the real pathfinder was actually driven rather
than read. **Resolved for the enabled movement families**, with the limits
below. Working in `docs/BARITONE_FEASIBILITY.md` section 3.3 (corrected) and
`tests/safety/pathfinder-containment.test.ts`.

**The first diagnosis was wrong.** It read `exclusionStep` adding 100 to a move
cost and concluded the veto was a price. It is not. Every movement generator
that consults the exclusion ends with `if (cost > 100) return`, and base move
costs are 1 or 2, so a forbidden step totals 101 and the move is never
generated. Measured: against a 120-block forbidden wall, Person walks a
124-step detour rather than a 12-step crossing that a penalty model would have
preferred.

**The real defect was narrower.** Two generators in `mineflayer-pathfinder`
2.4.5 do not participate in the exclusion at all:

- `getMoveUp` never reads the block it climbs into. It checks the block two
  above the node, which is the destination's head, and the destination's feet
  block is never fetched. A ladder or vine crossing a region boundary could
  therefore be climbed into. This family is enabled.
- `getMoveParkourForward` adds the exclusion cost but has no `cost > 100` check,
  and charges the cost against the block above its landing square rather than
  the square itself. It also skips the blocks jumped over. This family is
  disabled in Person's configuration (`allowParkour = false`), so it was latent
  rather than live.

Both were reproduced against the real search before the repair, and both now
fail the build if the repair is removed.

**The repair** is in `adapters/minecraft/src/movements.ts`. Person's movement
policy now wraps `getNeighbors`, the single point the A* search takes its
candidate moves from, and drops any move whose destination feet or head block,
or whose `toBreak`/`toPlace` positions, the physical guard refuses. Generators
that ignore the exclusion cost are covered because the filter is applied after
generation, and families that do not exist yet are covered for the same reason.
The exclusion callbacks are kept, and are still load-bearing for two reasons:
they hard-reject breaking and placing, and `postProcessPath` disables path
shortcutting only while `exclusionAreasStep` is non-empty, so removing them
would silently re-enable straight-line splicing across avoided ground.

**What is established.** No path the search returns contains a step whose feet
or head block is forbidden, nor a diagonal threading past a forbidden corner
column, for cardinal walking, diagonals, jump-up, drop-down, move-down, ladder
climbing, and parkour even when parkour is switched on. This holds for
replanning because every search reads the guard again, and for shortcutting
because shortcutting is off. Proved by deterministic tests against the real
pathfinder over a synthetic world. **Not live-validated in Minecraft.**

**What containment means here.** A protected area is a set of whole blocks. The
configuration schema types every coordinate as an integer, `contains` is an
inclusive integer box test, `PhysicalGuard.canEnter` takes a block position, and
the safety kernel samples the floored feet block. Sub-block geometry is not
representable anywhere in the system, so the invariant is block occupancy: no
Person-controlled movement may leave Person occupying a forbidden block. The
avatar's collision volume is a finer thing than the contract describes, and is
not part of this invariant.

That distinction was examined on 2026-09-22 rather than assumed, and it changed
one answer. A diagonal step changes x and z together, so the floored position
passes through one of the two corner columns before arriving, whichever axis
crosses first. Those are blocks Person occupies, so that is inside the contract,
not a collision-volume aside. The planner was measured emitting exactly such a
move: a diagonal from `(0,-1)` to `(1,0)` threading past a forbidden `(0,0)`.
Since protected areas fail closed and Person does not control which axis crosses
first, the neighbour filter now refuses a diagonal whose either corner column is
forbidden. Person rounds such a corner in two cardinal steps instead. Ordinary
diagonals in open ground are unaffected and are covered by a test.

**What is not established.** Two things, honestly:

- Containment is read when a path is searched. If a protected area were changed
  while Person was already walking, the path in flight would not be re-checked;
  the next search would honour the change. This is not reachable today because
  protected areas come from config and are fixed for the life of a run, so
  there is no runtime path that tightens them mid-episode.
- Only motor-caused entry is covered. Knockback, explosions, flowing water,
  gravity after a support is removed, server correction, and operator teleports
  are world-caused or external, and the L0 `protected_area_entry` assessment
  remains the response to those. A path planner cannot make the avatar
  incapable of appearing in a region under all Minecraft physics.

## 12. Known Limitations / Backlog

| Limitation                                                                         | Source                          |
| ---------------------------------------------------------------------------------- | ------------------------------- |
| Mineflayer adapter exercised live for observation and 2 skills only                | REALITY_VALIDATION.md           |
| No dig-down skill (mine_stone/coal need exposed stone)                             | IMPLEMENTATION_REPORT.md        |
| Fixture is simulation, not Minecraft                                               | IMPLEMENTATION_REPORT.md        |
| Planner bounded (depth/branch/node caps) — may return no plan                      | IMPLEMENTATION_REPORT.md        |
| Goals: survival only (projects/social/self-generated future)                       | IMPLEMENTATION_REPORT.md        |
| Death ends episode — no respawn/recovery loop                                      | IMPLEMENTATION_REPORT.md        |
| Evidence written by cognition — last outcome missing if cognition dies mid-episode | IMPLEMENTATION_REPORT.md        |
| Inventory reconciliation on resume not reimplemented                               | IMPLEMENTATION_REPORT.md        |
| `loot_permitted_container` withdraws all types up to amount                        | IMPLEMENTATION_REPORT.md        |
| One Person per runtime (multi-Person not supported)                                | IMPLEMENTATION_REPORT.md        |
| Tick budgets invented in fixture (4 ticks/step, 12/dig)                            | REALITY_VALIDATION.md           |
| Prediction error recorded but inert (no world model consumes it)                   | REALITY_VALIDATION.md           |
| Single-skill live validation: stages 1 and 2 done, 3 to 8 not started              | REALITY_VALIDATION.md           |
| No belief, memory, affect, language, social or project system exists               | Known Deviations C6, above      |
| Perception has no visibility, occlusion or pose model                              | PERSON_SPEC section 8, ADR 0002 |

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

| File                           | Purpose                                                                |
| ------------------------------ | ---------------------------------------------------------------------- |
| `REALITY_VALIDATION.md`        | Canonical validation evidence (fixture/adapter/live distinctions)      |
| `IMPLEMENTATION_REPORT.md`     | Cumulative implementation record (Milestone 0 + 1)                     |
| `TRACEABILITY.md`              | Requirements → code → tests mapping                                    |
| `docs/LAN_TESTING.md`          | Manual validation ladder                                               |
| `docs/EVALUATION.md`           | What automated suite proves / does not prove                           |
| `docs/ARCHITECTURE.md`         | Current and target process diagrams, packages, decision loop           |
| `docs/PERSON_SPEC.md`          | Full architectural specification (source of truth); read top to bottom |
| `docs/decisions/`              | ADRs 0001–0006, frozen 2026-09-22                                      |
| `docs/SEMANTIC_TARGETING.md`   | The referent scheme compositional actions will need                    |
| `docs/evidence/skill-tests/`   | Tracked copies of the three live skill-test reports, with provenance   |
| `docs/BARITONE_FEASIBILITY.md` | Phase 1 spike: the Baritone 1.16.5 navigation verdict and its evidence |
