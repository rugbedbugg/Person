# CURRENT_STATE.md — Factual Snapshot of Person

**Last verified against:** branch `feat/effect-learning`, based on `fd52a26` (tip of `feat/lan-validation` after PR #13)
**Tag:** `v0.1.0-foundation` (`6b99830`)
**Date:** 2026-09-25

This file is strictly factual. It describes what exists in the source tree and
what has been run. **`docs/PERSON_SPEC.md` specifies a great deal that is not
here**, including the perception firewall's sense model, semantic, spatial,
social and autobiographical memory, consolidation, belief, affect, language, social cognition, projects, web
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

**23 skills, all implemented** (architecture test asserts spec/impl sets identical, no placeholders):

| Category   | Skills                                                                                             |
| ---------- | -------------------------------------------------------------------------------------------------- |
| Emergency  | `flee`, `dig_in`, `wait_safely`, `return_home`                                                     |
| Food       | `gather_plant_food`, `hunt_safe_passive_animals`, `cook_food`, `eat_to_target`                     |
| Resources  | `gather_wood`, `mine_stone`, `mine_coal`                                                           |
| Crafting   | `craft_basic_tools`, `craft_stone_tools`, `craft_furnace`, `craft_chest`                           |
| Shelter    | `build_basic_shelter`, `repair_shelter`                                                            |
| Storage    | `place_owned_chest`, `deposit_owned_storage`, `withdraw_owned_storage`, `loot_permitted_container` |
| Perception | `look_around`, `look`                                                                              |

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
- **Learned effect reliability (ADR 0011):** uncertain beliefs about how reliably each skill's declared effects follow, learned from audited prediction error, gated by learning mode, and under `supervised` adding a term of at most ±0.1 to routine scores, recorded separately as `learned_effect` (`person_cognition/effect_learning.py`)
- **Affect (ADR 0010):** a continuous, bounded, decaying state (`valence`, `unease`, `control`) appraised by deterministic rules from percepts, the body, reported outcomes and Person's own goal, project and search outcomes; it adjusts non-urgent goal priorities within ±25 (base and adjustment journalled separately) and scales the policy's exploration tolerance; it never runs a skill, touches memory salience, or reaches the runtime (`person_cognition/affect.py`)
- **Projects (ADR 0009):** persistent cognitive commitments (`improve_home`, `secure_food_supply`) taken up only when pressing needs are calm, pursued one milestone at a time at a priority below urgent needs, interrupted by those needs and resumed after, abandoned when repeatedly blocked, and re-examined after a restart (`person_cognition/projects.py`)
- **Spatial sense (ADR 0008):** path integration of the coarse `selfMotion` percept into an estimate that drifts, cognitive places recognised with a confidence, routes between them, and episodes placed where Person believes they happened (`person_cognition/spatial/`)
- **Memory (ADR 0007):** episodic memory encoded from cognition-facing experience, a small unpersisted working memory, and recall by typed cue only, at most 3 memories at a time (`person_cognition/memory/`)

### Evidence & Persistence (`packages/persistence/`)

- **Append-only JSONL journal** (fsynced, chained by `previous_event_id`)
- **Atomic checksummed snapshots** (temp-file + rename)
- **Strict reading:** rejects corruption, ignores duplicates, drops crash-truncated tail
- **Restore:** replay from newest valid snapshot, fallback to full rebuild
- **Statistics keyed by training context** — fixture/live evidence never merges
- **Event types:** episode_started, goal_selected, routine_selected, routine_outcome, skill_started, skill_completed, skill_failed, skill_interrupted, emergency_override, death, episode_ended, prediction_error (schema v2, instrumentation), information_search (schema v3, instrumentation), memory_encoded and memory_recalled (schema v4; the memory store is rebuilt from `memory_encoded` alone), place_formed and place_visited (schema v5; the spatial map is rebuilt from these and `episode_ended`), project_started and project_changed (schema v6; the project book is rebuilt from these alone), affect_appraised (schema v7; trigger, components, before, delta, after), effect_evidence (schema v8; one classified trial per declared effect, and what the learning mode admitted it to)
- **Schema versions:** new records are `person-evidence-v9`; v1 to v8 journals are still read unchanged, and an event type cannot claim a schema older than the one that introduced it

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
| look_around               | ✅ pass | ❌ `bot.look` not in the double | ❌ not run                | returns to start; informs nothing   |
| look                      | ✅ pass | ❌ `bot.look` not in the double | ❌ not run                | one gaze step; Person stays facing  |

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

| Component                                              | Status                                                                    |
| ------------------------------------------------------ | ------------------------------------------------------------------------- |
| Decision context (7 dimensions)                        | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Homeostatic survival goals                             | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Goal stack (suspend/resume)                            | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Symbolic planner (preconditions/effects)               | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Routine model (nesting, stable IDs)                    | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Deterministic fallback policy                          | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Evidence policy (Beta posterior)                       | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Safe exploration envelope                              | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Learning modes (off/shadow/supervised)                 | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Evidence journal (append-only, chained)                | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Atomic snapshots + restore                             | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Restart reuse (evidence survives restart)              | IMPLEMENTED + TESTED IN FIXTURE (integration test)                        |
| Prediction error logging                               | IMPLEMENTED + TESTED IN FIXTURE (feeds only the effect learner, ADR 0011) |
| Learned effect reliability (uncertain, mode-gated)     | IMPLEMENTED + TESTED IN FIXTURE (integration test)                        |
| Tick budget instrumentation                            | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Recognition gates evidence facts                       | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Missing-evidence counterfactual                        | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Bounded information seeking (gaze only)                | IMPLEMENTED + TESTED IN FIXTURE (integration test)                        |
| Episodic memory, legitimate inputs only                | IMPLEMENTED + TESTED IN FIXTURE (integration test)                        |
| Bounded cued recall (typed `Cue`, max 3)               | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Memory survives restart; mind starts empty             | IMPLEMENTED + TESTED IN FIXTURE (integration test)                        |
| Forgetting as inaccessibility (no erasure)             | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Self-motion percept (relative, quantized)              | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Path integration with growing doubt                    | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Cognitive places, routes, recognition                  | IMPLEMENTED + TESTED IN FIXTURE (integration test)                        |
| Place-keyed search memory (shorter search)             | IMPLEMENTED + TESTED IN FIXTURE                                           |
| Persistent projects: start, interrupt, resume, abandon | IMPLEMENTED + TESTED IN FIXTURE (integration test)                        |
| Affect: appraisal, decay, bounded bias                 | IMPLEMENTED + TESTED IN FIXTURE (integration test)                        |

**Future providers (placeholder, raise not implemented):**
WorldModelProvider, AffectProvider, LanguageProvider, SocialProvider, ProjectProvider, ExplorationProvider

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

**Twenty-one of twenty-three skills have never been run live.** The next stage in
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

| ID  | Deviation                                                            | Introduced | Decision needed before                  |
| --- | -------------------------------------------------------------------- | ---------- | --------------------------------------- |
| C1  | The `Observation` carried exact coordinates (resolved)               | `6b99830`  | resolved 2026-09-22, see below          |
| C2  | Protected-area entry is an L0 "hard safety" trigger                  | `6b99830`  | any change to the kernel's levels       |
| C3  | `WorldMemory` is an ownership ledger, not memory, and is named badly | `6b99830`  | **Resolved**: renamed `PlacementLedger` |
| C4  | Skills choose their own targets; cognition cannot name one           | `6b99830`  | any goal about a particular thing       |
| C5  | The `Embodiment` port is shaped by what Mineflayer offers            | `6b99830`  | the Baritone spike (ADR 0001)           |
| C6  | No belief, memory or knowledge representation exists at all          | n/a, a gap | any epistemic claim about Person        |
| C7  | The Mineflayer route veto missed two movement families (repaired)    | `6b99830`  | resolved 2026-09-22, see below          |
| C8  | `home.homeDistance` was a drift-free homing channel (resolved)       | `6b99830`  | resolved 2026-09-25, see below          |

### C1. The observation carried exact coordinates

**Resolved on 2026-09-22.** The structural half of the perception firewall now
exists. Cognition no longer receives a world coordinate anywhere, and what it
does receive is bounded by a first-person visual model rather than by whatever
the body's block search turned up.

**What it used to be.** `Observation.environment.position` and a `position` on
every nearby resource, hazard, container, workstation, entity and owned
storage, plus `navigation.lastSafePosition`, the home coordinate, the
Mineflayer `entityId` and the account `uuid`. Cognition never read any of it,
which was established by inspection, so the firewall was enforced by nothing
but the accident that nobody looked.

**What replaced it.** Two contracts instead of one.

- `WorldSnapshot` is the privileged one. Exact position, the eye pose, every
  block the body found, every entity, the pathfinder's world. The safety
  kernel, the permission gate, the physical guard, the skills and the operator
  reports all read it, and it never crosses to cognition.
- `Observation` is the cognition-facing one. Where something is, is reported
  relative to Person and qualitatively: a bearing relative to facing, an
  elevation, a coarse range band, and a distance rounded to a tenth of a block.
  There is no compass, because a heading in degrees would be the coordinate
  problem in another notation. Distance is an estimate rather than a
  measurement: half a block out to eight, whole blocks out to sixteen, two
  beyond, which is as coarse as the thresholds cognition actually compares
  against allow. Reconstructing a world position from a run of percepts needs
  an anchor, and the contract carries no self position, no heading and no
  odometry, so relative structure is all that composes.

**What Person can see.** `apps/node-runtime/src/observation/vision.ts`. An eye
at Minecraft's standing eye height, a view direction taken from yaw and pitch
using Mineflayer's own convention, a range of 32 blocks, and an opaque-block
line of sight test. The field has two parts, because a human one does. Out to
200 degrees horizontally and 130 vertically Person perceives that something is
there, roughly where, and roughly what sort of thing it is. Only within 60
degrees horizontally and 50 vertically does it recognise what the thing
actually is: outside that, a percept carries its coarse category, bearing,
elevation and estimated distance, and withholds the exact block name, the
species and any nameplate. `PERSON_SPEC` section 8 asks for semantic
aggregation and a human-like sense model, and a cone that recognised everything
equally out to 100 degrees would be neither. Sub-block shapes are ignored, so a fence occludes as a full cube
does. Resources, hazards, entities and found containers are filtered through
it. Workstations and owned storage are not: they come from Person's own
placement ledger, so they are recorded rather than seen. Every workstation
record carries `source: "placement_ledger"` so the channel cannot be mistaken
for current perception or for a recollection, and `home.ownedStorage` sits in
the `home` block for the same reason. Person's own memory reaches cognition by
a separate, bounded path (ADR 0007).

**Proprioception.** Health, food, saturation, air, armour, status effects,
whether Person is alive, and the inventory are reported as body state rather
than as vision. Saturation is a hidden stat in vanilla, and is kept on the
grounds that how recently you ate well is something a body knows about itself.
Exact position is not proprioception and is not reported.

**Hearing does not exist.** Nothing carries sound, chat or event audio into
cognition today, so there was nothing to put behind the firewall. Vision is not
the whole of perception, it is the whole of what is implemented.

**Person can now point its senses.** Added 2026-09-22, after the firewall.
Gaze is a motor capability and nothing more: it moves Person's head, and every
judgement about where to point it is left above the boundary. `look_around` is
a skill like any other: cognition proposes it, the validator
and the safety kernel see it, and the body performs it. The vocabulary is five
words, `forward`, `left`, `right`, `up` and `down`, and the skill takes no
parameters at all, so there is no field in which a coordinate, an angle or an
entity could be named. The runtime turns those words into yaw and pitch on its
own side.

`look_around` sweeps through five fixed orientations, straight ahead and 45 and
90 degrees to each side, and returns to the heading it began with, head
levelled. The endpoint is a fact about where the sweep started and nothing
else.

It deliberately decides nothing. A first version settled facing whichever
orientation had the most in it, which sounds harmless and is not: "the scene
with the most things in it is the most interesting scene" is a judgement about
salience, and salience is cognition's. The sweep module now imports no
perception at all, so it has no way to rank what it turns past, and a test
asserts that it stays that way.

That leaves the skill minimally useful on its own. A sweep establishes nothing
about what is or is not out there, because the views it passed through never
reached cognition. Looking for something is a loop that belongs to the
planner, and since 2026-09-23 the planner runs it: see "Information seeking"
below.

Two causes of turning are worth keeping apart, and the evidence already does:
walking rotates Person as a side effect of going somewhere, while `look_around`
appears in the record as a skill Person chose to run.

**Behaviour changed, deliberately.** Person now misses things it would
previously have been told about, because they are behind it, too far away, or
behind a wall. That is what ADR 0002 predicted and wanted. It has a concrete
consequence: `fixtures/worlds/vertical-slice.json` needed an explicit
`spawnYaw`, because its food is behind the old default facing.

**Information seeking.** Added 2026-09-23 on `feat/information-seeking`. The
planner now distinguishes "not currently perceived" from "known absent".

- _Evidence facts._ `reachable_wood`, `reachable_stone`, `reachable_coal`,
  `reachable_plant_food`, `reachable_animal` and `permitted_container_nearby`
  are the only planning facts that current perception alone establishes; no
  skill produces them, and a test asserts that. `person_planner.EVIDENCE_FACTS`
  names them.
- _Recognition gates action._ Those facts now count only percepts with
  `detail: "central"`. A peripheral percept, which carries a coarse category
  and no identity, is a lead to look at rather than a licence to act on: an
  animal-shaped thing at the edge of vision is not a cow. Hostiles and hazards
  still count in the periphery, because noticing a threat needs no
  identification. **Behaviour change:** Person now glances to recognise food
  and trees it previously acted on unidentified.
- _Missing evidence is named, not assumed._ When a goal has no plan,
  `person_planner.evidence_needed` asks a counterfactual on a copy of the
  state: had the unseen evidence facts been seen, would a plan exist? If so,
  those facts are the purpose of a search; if not, the goal is blocked as
  before (`no_feasible_plan`).
- _The loop._ `person_cognition/search.py`. Each glance is one `look` skill
  invocation (new skill, parameter `direction` from the closed five-word gaze
  vocabulary), through the ordinary validator, kernel and dispatch path. The
  runtime turns the head one step and Person stays facing that way, so the next
  ordinary observation is taken from there. After each observation the planner
  simply plans again: a plan means act, no plan means look again. Direction is
  chosen above the firewall: towards the nearest peripheral glimpse of what is
  sought, by its relative bearing; otherwise a sweep to the left, levelling the
  head first if an earlier glance tilted it.
- _Bounded._ Eight glances per search (`LOOK_BUDGET`). Seven 45-degree turns
  cover the horizon; the eighth is room for a lead. A search ends as
  `satisfied` (a plan exists), `exhausted`, or `abandoned` (the active goal
  changed, or the episode ended).
- _Exhaustion is not absence._ An exhausted search concludes
  `not_found_in_bounded_search`, blocks the goal with that reason, and the goal
  is reopened as soon as any of the sought evidence is recognised. No fact,
  reason code or record claims that anything is absent, and tests search every
  message and record for such a claim.
- _State._ What persists between glances is the goal id, the evidence sought,
  the budget, the words already chosen and how many steps Person has tilted its
  own head. No angle, position, percept or handle. It lives only in the
  cognition process and ends with the search; it is not memory (ADR 0003).
- _Record._ Each phase of a search is journalled as an `information_search`
  event (schema v3), instrumentation only: never scored, never read back by
  cognition. Search routines use the fixed id `r_seek_evidence`, are not
  scored as strategies, and carry `seeking_evidence` in the policy reason codes.

A defect found and fixed on the way: **left and right bearings were mirrored.**
`relative.ts` reported something on Person's right (positive X while facing
negative Z, by the convention `stepGaze` and the Mineflayer adapter share) as
`left`, and vice versa. Nothing in cognition read bearings before, so it was
latent since Phase 3; the first planner to turn towards a glimpse turned away
from it and oscillated. The sign is corrected in the shared observation
builder, so both bodies are affected alike, and a test ties bearings to gaze
directions. TESTED IN FIXTURE; not live-validated.

What information seeking does **not** establish:

- The target of an action is still chosen by the skill from privileged state
  (C4). Once a recognised tree makes `gather_wood` plannable, the skill fells
  the nearest permitted tree it knows of, which need not be the one Person saw.
  Tests prove the _planner's_ decisions ignore unperceived wood; they do not
  prove the _body_ does.
- Searches do not share results. Each goal that needs the same unseen evidence
  runs its own bounded search. Total looking is bounded by goals times budget,
  not by one budget. Since Phase C a search is made from a cognitive place
  (ADR 0008): a search at a place Person believes it already searched
  fruitlessly for the same things is shorter, never skipped, and "not found"
  reopens when Person believes it is somewhere else.
- Search is gaze only. Person does not walk anywhere _in order to_ look;
  choosing where to go to search is not attempted.
- ~~`navigation.pathRisk` was derived from the kernel's threat state, which
  counts every hostile the body knows about, including ones Person cannot
  see.~~ Found during Phase E, fixed in `fix/perceived-path-risk`: it is now
  judged from the perceived hostiles, with the kernel's own distance
  thresholds (`observationVersion` 7). The kernel still reads the unshaped
  snapshot and acts on unseen threats, so safety is unchanged.
- ~~Peripheral animal records still carry the `named` and `tamed` booleans.~~
  Fixed in `fix/peripheral-semantic-leak`: a peripheral entity now carries
  only its location fields. `named`, `tamed` and `protectedTarget` (the
  hunting verdict, computed from them) are present only on a `central`
  percept, the schema rejects them in the periphery, and
  `observationVersion` is 3. A peripheral animal stays a search lead until it
  is recognised as someone's. The safety gate still reads the unshaped
  snapshot, so what Person may do is unchanged.
- The Mineflayer `look` path is not exercised by the conformance double, so
  that the adapter turns the head the way `stepGaze` and the corrected
  bearings assume is established by reading Mineflayer's convention, not by a
  test. The smallest live check is in `REALITY_VALIDATION.md`, "Information
  seeking".
- None of it has been run against Minecraft.

**What is not established.** Recognition is by block and entity name, so Person
identifies a cow as a cow with no notion of having learned what a cow is. There
is no attention model: what survives the visual filter is capped
deterministically and nearest-first, which bounds the output without modelling
what Person would actually notice. A percept has no identity across ticks, so
cognition cannot yet refer to a particular perceived thing, which is C4 and is
deliberately untouched.

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

### C3. `WorldMemory` is not memory — RESOLVED

`apps/node-runtime/src/runtime/world-memory.ts` was a runtime-owned ownership
and placement ledger: home record, placed blocks, storage provenance, furnace
and crafting-table positions. It is privileged engineering state that the
observation builder reads to derive semantic facts. It is not, and must never
become, Person's recollection (`docs/PERSON_SPEC.md` section 24).

**Decided (operator, 2026-09-24): rename.** It is now `PlacementLedger` in
`runtime/placement-ledger.ts`, and every variable that held it is `ledger`.
Workstations read from it reach cognition marked
`source: "placement_ledger"` (they were marked `"remembered"`), and
`observationVersion` is 4, so nothing the runtime supplies can be mistaken
for a recollection. The persisted file keeps its name
(`world-<world>-<person>.json`) so existing ledgers still load. "Memory" in
this repository now means Person's cognitive memory only (ADR 0007).

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

### C6. No belief, memory or knowledge representation exists — PARTLY ADDRESSED FURTHER

`docs/PERSON_SPEC.md` sections 24, 25 and 26 specify episodic, semantic,
spatial, social and autobiographical memory, consolidation, forgetting and a
predictive-causal world model.

**Now implemented (ADR 0007, Phase B):** episodic memory and a small working
memory. Episodes are encoded through a whitelist from what cognition was given
or did: things newly recognised, skill outcomes as reported, emergencies,
health lost between observations, and concluded searches. They carry salience
and provenance. The journal records each encoding, and the memory store is
rebuilt from those records alone. Recall takes a typed cue, returns at most
three memories labelled as memory, and never feeds the planner's symbolic
state. Old, weak memories become inaccessible without being erased.
Everything is TESTED IN FIXTURE only.

**Now implemented (ADR 0008, Phase C):** a first spatial memory. The runtime
reports a coarse, relative sense of Person's own motion in every observation
(`selfMotion`: a direction in eight sectors relative to the previous facing,
a distance band, a rotation in eighths of a turn, rise or fall, and whether
the scene jumped). Cognition integrates it into an estimate in a frame of its
own whose uncertainty only grows, forms cognitive places (`place_1`, ...) at
searches, actions and the shelter it built, recognises them with a
confidence, records routes between them, and places its episodes. Places and
the estimate persist through `place_formed`, `place_visited` and
`episode_ended`; a restart resumes the estimate with added doubt. Moving the
entire fixture world by +1000 X changes nothing in Person's mind (integration
test). TESTED IN FIXTURE only.

**Still absent:** semantic, social and autobiographical memory,
consolidation, belief and the world model. The symbolic state is still
recomputed from the latest observation, so Person still has no belief that
could disagree with an observation. It can now remember having seen something
that is no longer there, and nothing yet concludes anything from that.

**Now implemented (ADR 0011, Phase F):** the first generalised belief, and
only one kind: how reliable each skill's declared effects have been in
Person's experience, one belief per (skill, effect fact). Prediction error
feeds it after an audit: only genuine attempts count (refusals, kernel
takeovers, preemptions and prerequisites found before acting are
inconclusive), and only facts Person evaluates itself (inventory, body,
perceived threat) teach anything. Each belief keeps supporting and
contradicting evidence, has no estimate without evidence, and a strength
separate from its estimate. The learning mode decides where evidence goes:
nowhere (`off`), an isolated shadow table (`shadow`), or the active table
(`supervised`), which adds a small, separately recorded term to routine
scores. Person still has no general belief or knowledge architecture, no
causal hypotheses and no consolidation.

**Memory uses so far.** Recall is cued at the start of each information
search, with the place Person believes it is at. Recalling an earlier search
at that place, for the same things, that found none of them makes the new
search shorter in proportion to the recognition confidence, down to a minimum
of two glances, and adds `searched_here_before`. The conclusion is still
`not_found_in_bounded_search`, never absence, and a goal blocked by a
fruitless search reopens when Person believes it is somewhere else.

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

### C8. `homeDistance` was a drift-free homing channel — RESOLVED

Found during the Phase C audit (2026-09-25). `Observation.home.homeDistance`
was the runtime's estimate of the straight-line distance from Person to its
configured home, computed from exact positions, at any range, through walls,
with no drift: more spatial certainty than ADR 0008 allows a sense of place.

**Decided (operator, 2026-09-25): retire it from cognition.** Exact physical
home distance may exist in trusted containment and operator tooling. It is
not a Person sense.

- It is gone from the observation and the schema rejects it
  (`observationVersion` 6).
- Person's relation to home (`at_home`, `near`, `far`, `unknown`) is derived
  from its own places and accumulated doubt (`Spatial.home_relation`). It is
  `near` or `far` only when that holds whichever way the drift has gone.
  Home is the place Person labelled home when it built its shelter or
  successfully went home.
- That relation drives the planner's `at_home` and `sheltered` facts, the
  night return-home goal (`far` at night), the decision context's home band,
  and the cognition-side exploration envelope (`far` closes it).
- The trusted runtime never had a home-distance safety rule: containment is
  the exploration and protected areas, enforced on the exact position, and
  unchanged. The one exact home distance left is the operator's
  `navigation.physicalHomeDistanceBefore/After` in skill-test reports.
- Tests prove the separation both ways: corrupting Person's estimate changes
  its home belief and goals without moving the body; pushing the body across
  a containment boundary changes enforcement and reaches Person only as a
  felt push. Moving the whole world +1000 X changes nothing in cognition.

`navigation.returnPathKnown` remains: it is a permission fact (whether the
runtime would allow a direct route home), not a distance.

## 12. Known Limitations / Backlog

| Limitation                                                                                                                        | Source                     |
| --------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| Mineflayer adapter exercised live for observation and 2 skills only                                                               | REALITY_VALIDATION.md      |
| No dig-down skill (mine_stone/coal need exposed stone)                                                                            | IMPLEMENTATION_REPORT.md   |
| Fixture is simulation, not Minecraft                                                                                              | IMPLEMENTATION_REPORT.md   |
| Planner bounded (depth/branch/node caps) — may return no plan                                                                     | IMPLEMENTATION_REPORT.md   |
| Goals: survival and two project kinds; no social, exploration or invented projects                                                | ADR 0009                   |
| Affect appraisal is a hand-tuned table; no social, memory-driven or novelty appraisal                                             | ADR 0010                   |
| Death ends episode — no respawn/recovery loop                                                                                     | IMPLEMENTATION_REPORT.md   |
| Evidence written by cognition — last outcome missing if cognition dies mid-episode                                                | IMPLEMENTATION_REPORT.md   |
| Inventory reconciliation on resume not reimplemented                                                                              | IMPLEMENTATION_REPORT.md   |
| `loot_permitted_container` withdraws all types up to amount                                                                       | IMPLEMENTATION_REPORT.md   |
| One Person per runtime (multi-Person not supported)                                                                               | IMPLEMENTATION_REPORT.md   |
| Tick budgets invented in fixture (4 ticks/step, 12/dig)                                                                           | REALITY_VALIDATION.md      |
| Effect beliefs cover inventory, body and threat facts only; ledger-derived effects (building, storage, furnace) teach nothing yet | ADR 0011                   |
| Single-skill live validation: stages 1 and 2 done, 3 to 8 not started                                                             | REALITY_VALIDATION.md      |
| No belief, semantic/spatial memory, affect, language, social or project system                                                    | Known Deviations C6, above |
| Memory changes one decision: how long a search at a recognised place lasts                                                        | ADR 0007, ADR 0008         |
| Place recognition is by drifting estimate and coarse scene only; no landmark identity                                             | ADR 0008, C4               |
| A small teleport inside the locomotion bound is felt as ordinary motion                                                           | ADR 0008                   |
| Actions are remembered without their referent until C4 is resolved                                                                | ADR 0007, C4               |
| No attention model: perception is capped deterministically, nearest first                                                         | Known Deviations C1, above |
| Information seeking is gaze only and per goal                                                                                     | Known Deviations C1        |

---

## 13. Test Counts

| Suite        | Tests   | Pass    |
| ------------ | ------- | ------- |
| Node (all)   | 269     | 269     |
| Python (all) | 265     | 265     |
| **Total**    | **534** | **534** |

**Coverage by area, as last broken down at `d0e9398` (188 Node / 129 Python);
not recounted since:**

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
Verified on `feat/effect-learning` on 2026-09-26: Node 269 pass / 0 fail,
Python 265 pass. History: 188 / 129 at `d0e9398`; 234 / 129 after PR #5;
242 / 148 after PR #6; 243 / 151 after PR #7; 248 / 176 after PR #8;
261 / 197 after PR #9; 264 / 211 after PR #10; 265 / 223 after PR #11;
267 / 240 after PR #12; 268 / 240 after PR #13.

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
