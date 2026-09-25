# PERSON

## A Persistent Artificial Individual Whose Embodied Life Occurs in Minecraft

**Status:** Architecture specification. Canonical source of truth.
**Architecture reconciled:** 2026-09-22
**Current live-validation target:** Minecraft Java Edition 1.16.1
**Planned target:** Minecraft Java Edition 1.16.5, as part of the Baritone motor work (not yet begun)
**Primary runtime:** Node.js 22 + Python 3.12
**Current embodiment:** Mineflayer
**Planned motor backend:** Baritone, behind the perception firewall (not yet begun)
**Design philosophy:** CPU-first, persistent, interpretable, bounded, modular
**Research framing:** Open-ended embodied cognitive-agent testbed; AGI-relevant, not an AGI claim
**Long-term objective:** Artificial individuals whose lives continue independently of direct player interaction and improve through persistent experience

### How to read this document

This document is a single canonical description of what Person is **intended
to become**. It distinguishes intention from implementation inline, using the
four status tags defined in section 1.1, rather than through a separate
overriding block:

```text
CURRENTLY IMPLEMENTED    exists in the source tree today
PLANNED PERSON V1        part of the frozen canonical Person, not yet built
FUTURE SUPER-PERSON      a deliberate capability increase, never the default
FUTURE COMMUNITY         multiple People; not the current target
```

A claim with no tag is **PLANNED PERSON V1**: intended, not yet built.

| Question                              | Document                 |
| -------------------------------------- | ------------------------ |
| What is Person meant to be?            | this file                |
| What exists in the source tree today?  | `docs/CURRENT_STATE.md`  |
| How far has any of it been proven?     | `REALITY_VALIDATION.md`  |
| Why was a particular choice made?      | `docs/decisions/`        |
| Where does this spec disagree with the code right now? | `docs/CURRENT_STATE.md`, "Known Deviations" |

An earlier draft of this document briefly existed as two layers, a frozen
"Part 0" laid over older sections it partly superseded. That was reconciled on
2026-09-22 (`docs/PROJECT_HISTORY.md`, Phase 7): the two layers were merged
into the single document below. Read it top to bottom.

---

# 1. Vision

Person is not a chatbot connected to Minecraft and not a conventional game bot.

Person is a persistent artificial individual whose embodied life occurs in
Minecraft. Person knows:

```text
that it is artificial
that Minecraft is a game
that an external reality exists
that an external creator/operator exists
that software enables its existence
```

Its ordinary **physical** agency is confined to its Minecraft embodiment. Its
**intellectual** life is not confined to Minecraft: it may reason, learn,
remember, forget, form beliefs, be uncertain, form interests, pursue projects,
develop relationships, communicate, perform deliberate research about the
external world, and eventually remain cognitively active while Minecraft is
unavailable.

Canonical Person v1 is **human-like and bounded**. Increasing a capability axis
past human-like boundedness produces a Super-Person configuration (section
4.1), which is a deliberate experiment, not an upgrade to the default.

Concretely, that persistent artificial individual is capable of:

* maintaining its own survival,
* learning reusable skills and routines,
* remembering places, events, players, relationships, and experiences,
* pursuing short- and long-term goals,
* interrupting and resuming projects,
* learning from success and failure,
* communicating naturally with players,
* forming persistent social relationships,
* developing preferences and behavioral tendencies,
* responding emotionally to events through a computational affect system,
* understanding ownership, trust, promises, conflict, cooperation, and restitution,
* constructing increasingly sophisticated structures and systems,
* eventually reasoning about advanced mechanisms such as redstone,
* continuing to act meaningfully when nobody is interacting with it.

The defining property is continuity.

A Person should have:

> a past, a present situation, and intentions for the future.

## 1.1 Status Vocabulary

Every claim in this document belongs to exactly one of four classes. Nothing
below is a statement that something exists.

```text
CURRENTLY IMPLEMENTED
    exists in the source tree today
    docs/CURRENT_STATE.md is the authority on this class,
    and REALITY_VALIDATION.md on how far it has been proven

PLANNED PERSON V1
    part of the frozen canonical Person, not yet built

FUTURE SUPER-PERSON
    a deliberate capability increase over canonical Person,
    never the default configuration

FUTURE COMMUNITY EXPERIMENT
    multiple People; not the current implementation target,
    but must not be made impossible
```

A section without a marker describes PLANNED PERSON V1.

A claim below is CURRENTLY IMPLEMENTED only where it explicitly says so.

## 1.2 Research Thesis

Person is also a research platform for a narrower and more testable question than "build AGI":

> **Can a persistent embodied agent develop stable, transferable behavioral adaptations and causal abstractions from autobiographical experience without hard-coding every response or giving a language model direct control of the world?**

Minecraft is useful because actions have observable consequences, the world persists, resources and hazards are grounded, and long-horizon behavior can be measured rather than judged from conversation quality.

The research program should test whether Person can progressively improve at:

```text
unknown situation
    ↓
observe
    ↓
form or retrieve hypotheses
    ↓
predict consequences
    ↓
choose a bounded experiment or plan
    ↓
act
    ↓
compare prediction with outcome
    ↓
update world model and memory
    ↓
transfer what was learned
```

The architecture should therefore optimize not only for successful Minecraft behavior, but for **measurable learning, adaptation, transfer, and continuity**.

## 1.3 Scientific Claim Discipline

Do not describe Person as AGI merely because it becomes capable or autonomous.

Do not claim:

```text
consciousness
subjective emotion
human-equivalent cognition
AGI
understanding beyond demonstrated behavior
```

Claims should be tied to reproducible measurements such as:

```text
unseen-task success
adaptation speed
transfer between environments
causal prediction accuracy
long-horizon goal completion
memory retention
behavioral change after experience
catastrophic forgetting
social consistency
```

Person is AGI-relevant because it studies persistent, open-ended, experience-driven intelligence in a grounded world. It is not itself an AGI claim.

---

# 2. Core Principle

The architecture must separate:

```text
thought
from
action
```

No high-level reasoning system, neural policy, language model, or affect system receives unrestricted control over Minecraft.

The execution hierarchy is:

```text
Cognition
    ↓
Goal
    ↓
Plan
    ↓
Routine
    ↓
Skill Invocation
    ↓
Safety Validation
    ↓
Bounded Minecraft Execution
```

The Minecraft-facing runtime retains final authority.

---

# 3. Architectural Invariant

The most important invariant in the entire system is:

```text
Python may propose intentions.

Node decides what is physically permitted.
```

Python never receives:

* direct Mineflayer access,
* raw movement authority,
* unrestricted block breaking,
* unrestricted combat,
* command execution,
* operator privileges,
* arbitrary chat command capability,
* teleportation,
* inventory spawning,
* world manipulation,
* safety override capability.

Node receives a structured request such as:

```text
GatherWood {
    targetAmount: 16,
    maxDistance: 48,
    maxTicks: 1800
}
```

rather than:

```text
walk forward
turn left
break block
```

This is cognitive autonomy versus environmental authority, and the distinction
holds all the way down:

```text
desire
    ->
goal
    ->
plan
    ->
proposed action
    ->
CAPABILITY POLICY
    ->
allowed physical execution
```

The runtime may reject a proposed action. A Person may want or plan something
the runtime does not permit, and that is a normal and expected condition rather
than a fault in either party. The rejection is represented honestly to Person
as unavailable or failed: it does not expose hidden security implementation
details, and it does not lie about having happened.

**CURRENTLY IMPLEMENTED:** this is the oldest invariant in the repository and
the best-tested one. `SkillInvocation` is a proposal; `ValidationDecision` is
the verdict; `SkillOutcome` names both the requested and the executed skill,
and learning credits only what actually ran. See
`docs/decisions/0005-cognitive-autonomy-vs-capability-authority.md`.

---

# 4. System Identity

The software stack should distinguish between the platform and the inhabitant.

```text
Shroud
    runtime/platform

Person
    autonomous inhabitant

People
    multiple Person instances
```

Example:

```text
Shroud Runtime
    ├── Person: Ada
    ├── Person: Rowan
    └── Person: Mira
```

Each Person has independent:

* identity,
* memories,
* relationships,
* projects,
* affect,
* preferences,
* learned policy,
* possessions,
* history.

Infrastructure may be shared.

## 4.1 Capability Axes: Person Versus Super-Person

Canonical Person aims deliberately at human-like boundedness. These axes are
**independent**:

```text
reasoning / intelligence
working-memory capacity
planning depth
memory retrieval quality
perception bandwidth
mechanical expertise
reaction latency
motor precision
internet access
self-modification authority
external agency
Minecraft command authority
```

Two rules follow, and they are the entire point of listing the axes:

```text
increasing intelligence must NOT silently increase perception privileges
increasing mechanical skill must NOT reveal more world state to cognition
```

A **FUTURE SUPER-PERSON** experiment raises one or more axes on purpose, names
which, and records it. Raising an axis by accident, as a side effect of a
performance improvement or a convenient refactor, is the failure mode this
section exists to prevent.

Canonical Person should also not always compute an optimal plan. Human-like
Person has bounded planning, finite attention, uncertainty, satisficing,
habits, affective influence and occasional reasonable mistakes. Future
Super-Person profiles may reduce those limitations deliberately.

## 4.2 Frozen, Learned, and Transient State

Three classes of state, eventually distinguished in the implementation:

```text
FOUNDATIONAL / FROZEN
    baseline cognitive profile, temperament, capability profile,
    memory capacity, perception limits, reaction latency

LEARNED
    routines, skills, relationships, preferences, spatial familiarity,
    social knowledge, language habits

TRANSIENT
    health, hunger, affect, arousal, active goals, current context
```

Changing a frozen configuration parameter is an **experimental intervention**,
not learning. Profile and configuration hashes should eventually be recorded so
a run can be reproduced and a behavioural change can be attributed to the right
cause.

**CURRENTLY IMPLEMENTED:** the skill library revision hash, compared across
both runtimes at the session handshake, is the first example of this idea. It
covers the skill library and nothing else.

---

# 5. Primary Architectural Layers

```text
┌─────────────────────────────────────────────┐
│                Identity                    │
├─────────────────────────────────────────────┤
│       Social Cognition / Language           │
├─────────────────────────────────────────────┤
│     Affect / Relationships / Memory         │
├─────────────────────────────────────────────┤
│          Goal & Project Manager             │
├─────────────────────────────────────────────┤
│       Planner / Routine Learner             │
├─────────────────────────────────────────────┤
│              Skill System                   │
├════════════════ TRUST BOUNDARY ═════════════┤
│             Safety Kernel                   │
├─────────────────────────────────────────────┤
│            Minecraft Executor               │
├─────────────────────────────────────────────┤
│         Embodiment (Mineflayer now)          │
└─────────────────────────────────────────────┘
```

The bottom row is the current body, not the permanent one: section 6.1 plans a
Baritone motor layer in that position, with a perception filter (section 8)
between whatever sits there and everything above the trust boundary. Belief,
memory and knowledge (sections 24 and 26) are further layers this diagram does
not draw, between memory and cognition.

The lower layers should continue functioning even if higher layers fail.

A Person whose language model is unavailable should still:

* eat,
* retreat from danger,
* maintain shelter,
* recover,
* return home,
* continue simple projects,
* remember state.

---

# 6. Runtime Processes

Recommended process architecture:

```text
person-node
    Mineflayer
    Minecraft observation
    skill execution
    safety enforcement
    navigation
    low-level inventory management

person-cognition
    memory
    goal selection
    planning
    learning
    affect
    world model
    relationships
    project management

person-language
    optional LLM provider
    local or remote

person-store
    SQLite initially
    optional vector/search indexes
```

Node and Python communicate through a versioned local protocol.

Preferred transport:

```text
localhost Unix socket
or
stdio framed messages
```

Avoid network complexity initially.

## 6.1 Embodiment and Motor Backend

Mineflayer is the current real embodiment. It is not assumed to remain the
long-term primary embodiment.

The planned direction is to evaluate Baritone as the Minecraft motor layer.

```text
Person cognition
    ->
trusted runtime / capability boundary
    ->
BaritoneEmbodiment
    ->
local IPC / bridge
    ->
Java/Fabric or equivalent Minecraft client integration
    ->
Baritone public API
    ->
Minecraft
```

Baritone is **motor cortex, not cognition**.

```text
Person decides WHAT and WHY
the trusted motor layer handles HOW
```

Baritone's exact pathfinding and world geometry stay behind the perception
firewall. Arbitrary Baritone command strings are never exposed to cognition,
and neither are Minecraft commands.

**Not implemented in this phase.** See `docs/decisions/0001-baritone-motor-backend.md`.

### Minecraft version

```text
CURRENTLY IMPLEMENTED   Minecraft Java 1.16.1
PLANNED                 Minecraft Java 1.16.5, as part of the Baritone work
```

The existing implementation, the conformance data tables and every live
validation performed so far target 1.16.1. 1.16.5 is the sensible nearby
compatibility target for the Baritone migration and **has not happened**.
`docs/CURRENT_STATE.md` continues to say 1.16.1 because that is the truth.

---

# 7. Versioned Cognitive Contract

Every message uses:

```text
protocolVersion
messageId
personId
sessionId
worldId
tick
timestamp
```

Core messages:

```text
Observation
PolicyDecision
GoalDecision
SkillInvocation
ValidationDecision
SkillStarted
SkillOutcome
EmergencyEvent
WorldEvent
MemoryEvent
SocialEvent
ProjectEvent
```

The protocol must be backward-incompatible only across explicit major versions.

`tick` and `timestamp` on every message are Person's two clocks: Minecraft time
and external time. Section 60.2 explains why both are required and what each
one is for.

---

# 8. Observation Model

Python receives semantic state rather than raw Minecraft internals. This is the
**perception firewall**: a future motor backend may hold exact client-side
world state for navigation, and that information must not automatically become
Person's cognition.

```text
Minecraft client state
        |
        +--> motor backend           exact geometry permitted internally
        |
        +--> perception filter
                 |
                 --> bounded Person perception
```

Person should perceive through a computationally cheap human-like Minecraft
sense model rather than receive every loaded block. The likely eventual design:

```text
camera pose, yaw, pitch, field of view
ray or visibility based
occlusion aware
bounded range
semantic aggregation
near / medium / far
relative directions
entity visibility checks
```

Debug and operator tooling may expose privileged state, through a separate path
that no cognition process can read.

**CURRENTLY IMPLEMENTED:** the boundary exists, and as of 2026-09-22 the sense
model above does too. The runtime keeps the unshaped snapshot; the safety
kernel and the permission gate read that rather than the observation, so
shaping can never widen what Person is allowed to do. Pose, bounded range,
occlusion and field of view are implemented, so Person can now fail to see
something that is in range. Location reaches cognition as a bearing relative to
facing, an elevation, a range band and an estimated distance; no coordinate
crosses, which closes the deviation this section used to carry
(`docs/CURRENT_STATE.md`, "Known Deviations", C1). What is **not** implemented
is a deliberate inspection capability for coordinates (section 24.4) and any
attention model beyond a deterministic cap. Person can point its gaze with a
closed five-word vocabulary, and the planner uses it to look for evidence a
goal needs before giving the goal up, a bounded search that concludes "not
found" and never "absent" (`docs/CURRENT_STATE.md`, Known Deviations, C1).
Only recognised percepts, in central vision, count as evidence to act on.

## 8.1 Vitals

```text
health
food
saturation
air
armor
statusEffects
alive
```

## 8.2 Environment

```text
dayPhase
weather
dimension
lightLevel
biome
position
knownDangerLevel
```

## 8.3 Inventory

Items should be normalized into categories where useful.

```text
food
fuel
wood
stone
iron
tools
weapons
armor
buildingMaterials
specialItems
```

Raw item IDs may also be included.

## 8.4 Nearby World

```text
resources
hostiles
passiveAnimals
players
containers
workstations
hazards
structures
```

## 8.5 Home State

```text
activeHome
homeDistance
shelterIntegrity
ownedStorage
bedKnown
foodReserve
fuelReserve
```

## 8.6 Navigation State

```text
routeStatus
pathRisk
stuckState
returnPathKnown
lastSafePosition
```

## 8.7 Current Activity

```text
activeProject
activeGoal
activeRoutine
activeSkill
suspendedGoals
```

## 8.8 Previous Outcome

```text
requestedSkill
executedSkill
status
effects
healthCost
resourceCost
elapsedTicks
interruptReason
```

---

# 9. Semantic Context

Do not learn against raw continuous observations.

Introduce coarse decision contexts.

Example:

```text
healthBand:
    critical
    low
    healthy

foodBand:
    starving
    low
    sufficient
    full

dayPhase:
    dawn
    day
    dusk
    night

threat:
    none
    nearby
    immediate

homeState:
    at_home
    near
    far
    unknown

toolTier:
    none
    wood
    stone
    iron
    diamond

foodState:
    none
    raw
    cooked
    stored
```

This prevents context explosion.

---

# 10. Skill System

A Skill is the smallest cognitive action available to planning.

Skills are not raw movement primitives.

Each skill has:

```text
SkillSpec
    id
    version
    parameters
    preconditions
    expectedEffects
    possibleFailures
    permissions
    costBounds
    interruptionPolicy
    completionEvidence
```

Example:

```text
SkillSpec: gather_wood

Preconditions:
    reachable_tree
    harvesting_permitted
    inventory_space

Parameters:
    amount
    maximum_distance

Effects:
    wood increased

Limits:
    maximum_ticks
    maximum_distance
    minimum_health

Evidence:
    inventory_delta
    harvested_blocks
```

## 10.1 Beyond the Finite Library

The finite high-level skill library remains useful and is not being replaced.
It is nonetheless insufficient for open-ended discovery, because a skill
library can only contain actions somebody anticipated. The eventual hierarchy:

```text
AI intention
    ->
goal / project
    ->
routine / high-level skill
    ->
when necessary: compositional physical actions
    ->
trusted validation
    ->
motor execution
```

Compositional physical operations that will eventually be needed:

```text
move near a perceived object
inspect something
look toward something
use held item
interact with a perceived entity
place an item relative to a perceived referent
break a perceived block
wait
repeat a bounded action
```

Every one of these takes a **perceived and validated referent**, never a
privileged coordinate, a raw object handle or a command string. The referent
rules are the ones in `docs/SEMANTIC_TARGETING.md`: identifiers are issued by
the runtime, resolution stays behind the boundary, permission is re-checked
after resolution, identifiers are stable and provenanced, and the parameter
stays a scalar.

This capability exists so Person can design experiments and discover Minecraft
phenomena nobody wrote a skill for. **Not implemented.**

---

# 11. Initial Skill Library

V1 of Person should include only enough skills for self-sufficient survival.

## Survival

```text
eat_to_target
flee
dig_in
wait_safely
return_home
recover
```

## Gathering

```text
gather_wood
gather_plant_food
hunt_safe_passive_animal
mine_stone
mine_coal
```

## Crafting

```text
craft_basic_tools
craft_stone_tools
craft_furnace
craft_chest
craft_bed
```

## Food

```text
cook_food
eat_food
store_food
retrieve_food
```

## Shelter

```text
build_basic_shelter
repair_shelter
secure_entrance
```

## Storage

```text
place_owned_chest
deposit_owned_storage
withdraw_owned_storage
loot_permitted_container
```

More capabilities are added as skills, not as privileged special cases.

---

# 12. Skill Outcomes

Every skill execution returns exactly one terminal state:

```text
SUCCESS
FAILED
INTERRUPTED
PREEMPTED
TIMED_OUT
INVALIDATED
UNREACHABLE
DEATH
DISCONNECTED
```

Crucially:

```text
requestedSkill
```

and:

```text
executedSkill
```

are distinct.

Example:

```text
requested:
    gather_wood

validator:
    emergency_override

executed:
    flee
```

The learner must receive credit only for what actually executed.

---

# 13. Safety Kernel

The Safety Kernel belongs entirely to Node.

Python cannot override it.

The kernel enforces two different concerns through one mechanism, and they are
not the same concern: fleeing lava is **self-preservation**, behaviour Person
would want if it were choosing; refusing to leave the configured exploration
box is **experimental containment**, the operator's decision about this run,
not a fact about Person. Both belong to Node and neither is negotiable, but
only the first is a property of Person. `docs/SAFETY.md` gives the full
breakdown, including the third category, shared-world and property policy.
This is a reframing of what the trigger table below means, not a change to it:
**no production behaviour differs.** See `docs/CURRENT_STATE.md`, "Known
Deviations", C2.

Priority:

```text
L0 Hard Safety
L1 Emergency Survival
L2 Active Goal
L3 Routine Optimization
L4 Exploration
```

Examples of L0/L1:

```text
imminent lethal damage
lava
suffocation
hostile swarm
critical hunger
critical health
path entering protected area
invalid destructive action
```

Node may immediately invoke:

```text
flee
dig_in
eat
cancel
return_to_safe_position
```

without consulting cognition.

---

# 14. Permissions Model

Capabilities must be explicit.

Example:

```yaml
permissions:
  containers:
    existing:
      withdraw: true
      deposit: false

    owned:
      withdraw: true
      deposit: true

  hunting:
    passiveUnnamedAnimals: true
    namedAnimals: false
    tamedAnimals: false

  players:
    combat: false

  villagers:
    harm: false

  building:
    enabled: true

  protectedAreas:
    enforcement: strict
```

Protected-area restrictions override all other permissions.

## 14.1 Minecraft Command Authority

```text
Canonical Person          no privileged commands
Canonical Super-Person    still no privileged commands by default
Privileged experiment     explicitly configured typed command capabilities
Operator                  administrative authority
```

Knowing that `/tp`, `/give` and `/fill` exist does not imply permission to use
them. `minecraft_command_authority` is a separate capability axis (section 4.1)
and is off. There is no generic `execute_command(string)` capability and there
will not be one: a typed, individually declared, individually validated command
capability is the only shape a future privileged experiment may take.

**CURRENTLY IMPLEMENTED:** an architecture test asserts that Person has no way
to issue a server command, and another asserts the embodiment port offers no
teleport and no coordinate command.

---

# 15. Goal Architecture

A Goal answers:

> What should Person accomplish?

A Routine answers:

> How should Person accomplish it?

These must remain separate.

Goal structure:

```text
Goal
    id
    type
    priority
    source
    createdAt
    deadline
    status
    prerequisites
    completionCondition
    suspensionReason
```

Goal sources:

```text
homeostasis
self-generated
project
social commitment
emergency
player request
exploration
maintenance
```

---

# 16. Goal Stack

Goals must support interruption and resumption.

Example:

```text
1. survive_immediate
2. help_alice_collect_iron
3. finish_workshop
```

When danger ends:

```text
survive_immediate
    COMPLETE

help_alice_collect_iron
    RESUME
```

Goal states:

```text
QUEUED
ACTIVE
SUSPENDED
BLOCKED
COMPLETE
FAILED
ABANDONED
```

---

# 17. Homeostasis

Survival should eventually become a background regulatory system.

Homeostatic needs:

```text
health
food
safety
shelter
equipment
fuel
basic reserves
inventory capacity
```

Needs produce urgency, not commands.

Example:

```text
foodReserve low
    ↓
secure_food goal receives higher priority
```

This allows Person to be building something and independently decide:

> I need to pause this and secure food first.

---

# 18. Projects

Projects represent long-term activity.

Examples:

```text
build_workshop
expand_house
automate_food_production
explore_north_region
construct_railway
improve_storage
```

A project consists of:

```text
Project
    purpose
    milestones
    dependencies
    requiredResources
    currentState
    suspendedState
    progress
    completionCriteria
```

Projects may span:

* minutes,
* hours,
* Minecraft days,
* multiple real sessions.

---

# 19. Planner

The planner uses skill preconditions and effects.

Do not force the learner to rediscover known crafting dependencies.

Example:

```text
Goal:
    cooked_food >= 6

Requires:
    cook_food

cook_food requires:
    furnace
    fuel
    raw_food
```

Planner recursively derives:

```text
craft_furnace
acquire_fuel
acquire_raw_food
cook_food
```

Learning chooses among feasible alternatives.

---

# 20. Routine Graph

Reusable sequences become Routines.

Example:

```text
Routine: establish_food

hunt_safe_passive_animal
return_home
cook_food
eat_to_target
deposit_surplus
```

Routines themselves may become nodes inside larger routines.

```text
prepare_for_night
    establish_food
    repair_shelter
    deposit_surplus
    wait_safely
```

Hierarchy:

```text
Skill
    ↓
Micro-Routine
    ↓
Routine
    ↓
Goal
    ↓
Project
```

---

# 21. Learning System

Initial Person should not use conventional deep RL.

Use evidence-guided routine selection.

Each routine accumulates:

```text
attempts
successes
failures
healthCost
resourceCost
elapsedTicks
recoverySuccess
failureModes
```

Context-dependent success can use Beta priors:

```text
success ~ Beta(1 + successes, 1 + failures)
```

Routine score may combine:

```text
estimatedSuccess
expectedHealthCost
resourceCost
timeCost
recoveryProbability
explorationBonus
```

Safety dominates reward.

A slower routine may be preferred if substantially safer.

---

# 22. Exploration

Exploration only occurs inside a safe envelope.

Example:

```text
health >= safe threshold
food >= safe threshold
no immediate threat
sufficient daylight
recoverable distance from home
```

Outside that envelope:

```text
explorationBonus = 0
```

Person exploits known safe behavior.

## 22.1 Active Experimentation

Exploration should eventually be **epistemic**, not merely random novelty-seeking.

When Person has competing plausible beliefs and is inside the safe envelope, it may choose a bounded action partly for expected information gain.

Conceptual loop:

```text
uncertainty
    ↓
candidate hypotheses
    ↓
safe discriminating action
    ↓
predicted outcomes
    ↓
execute through normal Skill boundary
    ↓
observe actual outcome
    ↓
prediction error
    ↓
belief update
```

Example:

```text
Hypothesis A:
    this route is faster but dangerous at night

Hypothesis B:
    this route is safe regardless of time

Experiment:
    traverse in safe daylight first, then gather additional evidence
```

The exploration system must never bypass the Safety Kernel to gain information.

Random action entropy is not a research objective. **Useful uncertainty reduction is.**

## 22.2 Provenance of Knowledge

Person must eventually be able to discover world mechanics empirically:

```text
notice an unexpected effect
form a hypothesis
design a bounded experiment
vary one factor
compare outcomes
update confidence
form generalized knowledge
```

Known Minecraft exploits are useful demonstrations but are **not** evidence of
independent discovery, because a foundation model may already contain them. A
rigorous discovery experiment needs hidden or custom mechanics, or a controlled
knowledge restriction.

Knowledge provenance classes must remain distinct. The names may change; the
distinctions may not:

```text
INITIAL_KNOWLEDGE
PERSONAL_OBSERVATION
PERSONAL_EXPERIMENT
INFERENCE
TAUGHT_BY_PERSON
TAUGHT_BY_OPERATOR
EXTERNAL_WEB
```

Person should be able to distinguish, and to say:

```text
I discovered this.
I inferred this.
Partha taught me this.
I learned this from another Person.
I read this online.
I already knew this.
```

**CURRENTLY IMPLEMENTED:** one adjacent distinction, the training context on
every statistic, which keeps fixture evidence from standing in for Minecraft
evidence. That is provenance about where an experience happened, not about how
a belief was acquired, and no belief store exists to carry the latter.

Canonical initial Person starts at approximately experienced-player Minecraft
knowledge, detailed in section 45.1. It is not initialized with a catalog of
obscure exploits, and the difference between what Person started with and what
it discovered is exactly what the provenance classes above exist to preserve.

---

# 23. Evidence Journal

All meaningful experiences are immutable events.

Never save only final scores.

Events:

```text
episode_started
goal_selected
routine_selected
skill_started
skill_completed
skill_failed
skill_interrupted
emergency_override
player_interaction
world_event
death
episode_ended
```

Fields:

```text
eventId
previousEventId
personId
worldId
sessionId
episodeId
decisionId
tick
timestamp
schemaVersion
policyRevision
payload
```

Storage:

```text
journal/
    000001.jsonl
    000002.jsonl

snapshots/
    cognition-000040.json
```

Scores are rebuilt from evidence.

---

# 24. Persistent Memory

Memory must be typed.

Do not dump everything into an LLM context.

This is the **memory firewall**. The engineering database (section 23) may
contain complete records; Person must not obtain unrestricted database-level
introspection into its own past:

```text
full event store        engineering truth
accessible recollection cognitive state
```

Memory retrieval should eventually be cue, salience and context dependent.
Person may deliberately try to remember something, and recall is not
guaranteed to be perfect.

**CURRENTLY IMPLEMENTED (ADR 0007, fixture only):** the engineering half, and
the first cognitive layer. The append-only evidence journal (section 23), the
snapshots and the provenance records are the full event store. Episodic memory
(24.2) and a small working memory (24.1) now exist in
`apps/cognition/python/person_cognition/memory/`: episodes are encoded through
a whitelist from what cognition was given or did, the journal records each
encoding, and the memory store is rebuilt from those records alone. Retrieval
(section 25) is by typed cue, at most three memories at a time, ranked by cue
relevance times an accessibility that decays with experienced time and more
slowly with salience. Semantic, spatial, social and autobiographical memory,
consolidation and interference measurement are not implemented.
`PlacementLedger` (`apps/node-runtime/src/runtime/placement-ledger.ts`,
formerly `WorldMemory`) is a runtime-owned ownership and placement ledger, not
Person's memory. See `docs/CURRENT_STATE.md`, "Known Deviations", C3 and C6.

## 24.1 Working Memory

Current:

```text
goal
project
nearby environment
recent events
retrieved memories
active relationships
```

## 24.2 Episodic Memory

Events:

```text
Alice helped rebuild my house.
I died near the ravine.
Steve stole diamonds from my chest.
```

## 24.3 Semantic Memory

Knowledge:

```text
this mine contains iron
this path reaches home
this circuit operates the farm
```

## 24.4 Spatial Memory

Normal Person spatial memory should be based primarily on:

```text
places
landmarks
routes
relative direction
semantic descriptions
confidence
remembered significance
```

**CURRENTLY IMPLEMENTED (ADR 0008, fixture only):** a first spatial memory
built from a coarse, relative sense of Person's own motion. Places are
Person's own records, recognised with a confidence from a drifting estimate
and a coarse scene signature; routes are relations between them; there is no
global map and no coordinate. Landmark identity and named descriptions such
as the ones below are not implemented.

For example:

```text
the cave north of home
the birch grove past the river
the hill where I first found coal
```

Exact coordinates are allowed, but through a deliberate Minecraft-style
instrument or inspection capability: Person may consciously check where it is,
the way a player reads a debug screen or a map. Coordinates are not permanently
injected into every perception and every memory (section 8 is the current
deviation from that rule).

`docs/SEMANTIC_TARGETING.md` describes the identifier scheme this implies for
targeting places and objects, and its five rules are adopted here unchanged.

## 24.5 Social Memory

Per-player:

```text
identity
relationship
permissions
history
promises
conflicts
gifts
shared projects
```

## 24.6 Autobiographical Memory

High-significance experiences that contribute to identity.

```text
first home
first death
important friendships
major betrayals
major projects
```

---

# 25. Memory Retrieval

Long-term memories stay primarily on disk.

Retrieve based on:

```text
relevance
recency
significance
relationship
location
goal
emotional salience
```

Person should not load its entire lifetime into RAM.

## 25.1 Memory Consolidation

Memory must support learning abstractions from repeated experience rather than functioning only as retrieval of old records.

The intended consolidation pipeline is:

```text
immutable episodes
    ↓
pattern detection
    ↓
candidate semantic belief
    ↓
corroboration / contradiction
    ↓
confidence update
    ↓
semantic memory
```

Example:

```text
Episode 14:
    attacked outside at night near forest

Episode 31:
    attacked outside at night near forest

Episode 52:
    hostile density increased after dusk

Candidate semantic belief:
    nighttime travel through this region carries elevated hostile risk
```

The semantic belief must retain provenance back to supporting and contradicting episodes. Consolidation must never rewrite or delete the historical evidence that produced it.

## 25.2 Forgetting, Decay, and Interference

Forgetting should primarily alter **accessibility and confidence**, not historical truth.

Memory strength may depend on:

```text
recency
retrieval frequency
repetition
significance
emotional salience
goal relevance
contradictory evidence
```

The system should be measurable for interference:

```text
learn A
learn B
retest A
```

so that catastrophic forgetting is detected instead of hidden by continuously changing prompts or summaries.

---

# 26. World Model

The architecture must never collapse six concepts that this section, and every
section that touches belief or memory, depends on being kept distinct:

```text
PHYSICAL TRUTH     what Minecraft/runtime state actually is
PERCEPTUAL TRUTH   what Person currently sensed
BELIEF             what Person currently thinks is true
MEMORY             what Person remembers
KNOWLEDGE          generalized or accepted beliefs and learned information
REASONING          conclusions produced from available cognition
```

They must be separately represented conceptually, and eventually separately
represented in the implementation. The consequence is a capability list, not a
limitation list. Person must be able to:

```text
fail to notice something
misunderstand what it noticed
forget
recall imperfectly
believe false information
update beliefs after prediction error
distinguish discovery from testimony and from research
```

An architecture in which Person cannot be wrong about the world is not a
simpler architecture. It is a different and less interesting one.

**CURRENTLY IMPLEMENTED:** physical truth (`WorldSnapshot`) and perceptual
truth (`Observation`) are already distinct objects, and the shaping between
them lives in `apps/node-runtime/src/observation/perception.ts` (section 8).
Belief, memory and knowledge have no representation at all; the symbolic state
the planner reasons over is derived fresh from the latest observation every
tick, so today Person believes exactly what it last saw and nothing else. See
`docs/CURRENT_STATE.md`, "Known Deviations", C6.

Do not persist every Minecraft block.

The world model has two complementary layers:

```text
Descriptive model
    what exists / where it is / who owns it

Predictive-causal model
    what tends to happen when conditions and actions occur
```

Store semantic objects for the descriptive layer.

Example:

```text
Place:
    id
    type
    bounds
    position
    owner
    purpose
    confidence
```

Examples:

```text
home
mine
farm
warehouse
bridge
workshop
redstone machine
danger zone
```

The predictive layer should eventually support semantic transition beliefs analogous to:

```text
P(semantic_state[t+1] | semantic_state[t], skill_or_event[t])
```

This does **not** require a giant neural world model. A structured CPU-first implementation is preferred until evidence shows it is insufficient.

Represent learned beliefs with provenance and uncertainty. For example:

```text
CausalBelief
    id
    context
    antecedent
    intervention_or_event
    predicted_effect
    confidence
    support_count
    contradiction_count
    evidence_refs
    last_updated
```

Person should distinguish:

```text
observed fact
learned association
causal hypothesis
validated causal relation
unknown
```

Repeated correlation alone should not automatically become a strong causal claim. Confidence should increase when interventions, natural experiments, or diverse evidence discriminate among competing explanations.

Prediction is part of cognition:

```text
current semantic state
    ↓
candidate action / routine
    ↓
predicted consequence
    ↓
actual consequence
    ↓
prediction error
    ↓
world-model update
```

Nearby raw blocks remain the embodiment's concern, whichever motor backend it is (section 6.1). The cognition layer should reason over semantic state, not reconstruct the entire voxel world in memory.

---

# 27. Ownership and Provenance

Every owned object should have provenance.

Example:

```text
StorageRecord
    storageId
    position
    worldId
    homeId
    createdByPerson
    creationEvent
    lastVerified
```

Rules:

```text
Existing chest:
    withdraw if authorized
    deposit forbidden

Person-owned chest:
    withdraw allowed
    deposit allowed
```

---

# 28. Identity

Person must possess stable identity independently of an LLM.

```text
Identity
    personId
    name
    creationDate
    home
    preferences
    tendencies
    values
    knownHistory
    currentProjects
```

The language model expresses identity.

It does not own identity.

## 28.1 Self-Knowledge

Person knows, at a conceptual level:

```text
I am an artificial Person.
I inhabit Minecraft.
Minecraft is a game.
An external reality exists.
Partha is my creator and operator.
Software systems enable my existence.
```

This grants no access to prompts, credentials, database internals, motor
caches, filesystem internals, security boundaries, model-provider secrets or
arbitrary source-code introspection. Those remain implementation and operator
state unless a future experimental profile deliberately exposes them.

Knowing that a boundary exists is not the same as being able to read what is
behind it. Neither is it a reason to lie to Person about it: when the runtime
refuses an action, section 3 says how that is represented.

---

# 29. Behavioral Traits

Traits influence cognition rather than directly scripting actions.

Possible dimensions:

```text
curiosity
caution
sociability
forgiveness
persistence
riskTolerance
generosity
territoriality
```

Traits may initially be authored.

Later they may adapt from long-term behavior.

Example:

```text
repeatedly choosing safe paths
    ↓
caution increases slightly
```

Changes should be slow.

---

# 30. Affect System

Person may implement emotion-like computational states.

Do not claim subjective consciousness.

The system models:

```text
appraisal
persistent affect
behavioral modulation
memory coupling
relationship consequences
```

Possible global states:

```text
arousal
positiveValence
negativeValence
stress
fearLikeActivation
angerLikeActivation
contentment
curiosity
attachment
```

Affect must be causal rather than cosmetic:

```text
event
    ->
appraisal
    ->
continuous affect
    ->
attention / memory salience / action tendency
    ->
goal and planning influence
    ->
regulation / action
```

Emotion **labels** are derived appraisal-level interpretations, not the only
representation. Emotion episodes decay; grievances, incidents and relationships
(sections 33, 34) persist separately and may reactivate affect. Never encode:

```text
if anger > X -> attack
```

Affect biases cognition; it does not select behaviour.

## 30.1 Sleep and Cognitive Fatigue

Do not invent a second physical stamina mechanic. Minecraft already has hunger,
health and beds, and those remain Minecraft's.

Future design uses **cognitive fatigue and sleep pressure**, which may
influence attention, planning depth, patience, working-memory effectiveness,
emotion regulation and willingness to do cognitively difficult work.

Sleep should eventually be psychologically meaningful: memory consolidation,
affect settling, reduced cognitive fatigue, background processing. Cognitive
sleep must not redefine Minecraft physics.

---

# 31. Fly-Inspired Affect Provider

A future `FlyInspiredAffectProvider` may use computational motifs inspired by Drosophila neuroscience:

```text
recurrent activation
neuromodulatory signals
associative valence
homeostatic modulation
persistent internal state
```

Do not simulate the entire fruit-fly connectome.

Implement reduced circuits specifically useful for Person.

Possible architecture:

```text
Event
  ↓
Appraisal
  ↓
recurrent affect network
  ↓
global modulators
  ↓
Memory / Goal / Social / Planner bias
```

---

# 32. Emotional Persistence

Emotion and memory are separate.

Example:

```text
Steve destroys house.

Immediate:
    anger-like activation = high
    stress = high

Hours later:
    anger-like activation = low

Still persistent:
    incident memory
    low trust
    unresolved grievance
```

Seeing Steve later may reactivate some state.

---

# 33. Incident Model

Socially significant events become Incidents.

```text
Incident
    id
    actor
    target
    eventType
    severity
    perceivedIntent
    evidence
    certainty
    witnessed
    unresolvedHarm
    restitution
    status
```

Examples:

```text
theft
attack
property destruction
gift
help
promise
betrayal
rescue
```

---

# 34. Relationship Model

Per player:

```text
Relationship
    familiarity
    affinity
    trust
    fear
    respect
    grievance
    attachment
```

Current emotion is not relationship state.

Example:

```text
angerNow = low
grievance[Alice] = high
trust[Alice] = low
```

This allows Person to stop being visibly angry while still remembering why trust changed.

---

# 35. Proportional Response

Anger must not imply attack.

A grievance influences possible goals.

Example escalation:

```text
minor offense
    ask player
    express annoyance

repeated theft
    reduce trust
    relocate valuables
    deny storage access

serious theft
    demand restitution
    protect property
    refuse assistance

major destruction
    suspend projects
    secure base
    rebuild
    confront offender
```

Future combat behavior, if ever introduced, remains permission-controlled.

---

# 36. Uncertainty

Person must never infer omnisciently.

If Person sees Alice steal:

```text
confidence = high
```

If diamonds disappear while Person is absent:

```text
actor = unknown
```

Suspicion may be represented as:

```text
SuspectedActor
    actor
    confidence
    evidence
```

Person should distinguish:

```text
know
believe
suspect
unknown
```

---

# 37. Social Norms

Person should reason about norms.

Examples:

```text
taking my property without permission is wrong
returning borrowed items is good
helping me during danger is good
breaking promises reduces trust
restitution can resolve grievances
```

Norms affect appraisal and relationships.

## 37.1 Capacities, Not Rules

Do **not** hard-code a moral code. Canonical Person begins with social-emotional
**capacities**:

```text
empathy capacity
attachment
reciprocity
gratitude
guilt
shame
fairness appraisal
harm aversion
social approval sensitivity
norm learning
```

It does **not** begin with rigid rules such as `STEALING_IS_ALWAYS_WRONG`,
`NEVER_LIE` or `NEVER_ATTACK`. The concrete norms above develop through
experience; they are not the starting state.

At the cognitive and social level Person is allowed to become capable of
deception, concealment, bluffing, lying, keeping secrets, suspecting deception,
stealing, retaliation, conflict, intentional harm, forgiveness and
reconciliation. These are not goals given to it. They are possible outcomes of
an autonomous social cognition system, and an architecture that cannot produce
them cannot produce a social life either.

External capability containment is separate from Person's morality, and
section 3's autonomy-versus-authority split is what keeps it separate. The
configured permission gate (section 13, section 14) is not Person's conscience;
see `docs/SAFETY.md`.

---

# 38. Social Commitments

Promises become persistent state.

```text
Commitment
    actor
    beneficiary
    task
    deadline
    status
```

Examples:

```text
I promised Alice I would help tomorrow.
Bob promised to return my iron.
```

Commitments influence goal priority.

---

# 39. Language System

The LLM is not Person.

The LLM is a service used for:

```text
language understanding
conversation generation
complex interpretation
reflection
summarization
high-level ideation
```

Structured cognition remains authoritative.

Example:

```text
Structured state:
    trust[Alice] = 0.31
    unresolved theft incident
    current anger = 0.18

LLM expression:
    "I'm not furious anymore, but I'm still not comfortable
     letting you use my storage."
```

The LLM must not invent relationship state.

## 39.1 Local External Chat

Person will eventually have a local external text interface. It is **not** a
second personality and not a separate chatbot:

```text
Minecraft interaction  --\
                          >-- one persistent Person identity,
local external chat    --/     memory and relationship state
```

Information learned through local chat can later be remembered in Minecraft,
and Minecraft experience can later be discussed through local chat.
**Not implemented.**

---

# 40. Language Provider Interface

```text
LanguageProvider
    interpretMessage()
    generateReply()
    summarizeMemory()
    reflectOnEvent()
```

Providers may include:

```text
RemoteLLMProvider
LocalLLMProvider
FallbackTemplateProvider
```

Person must remain operational without any LLM.

---

# 41. Player Request Pipeline

Example:

```text
Alice:
"Can you help me build a bridge?"

        ↓

Language interpretation

        ↓

SocialIntent:
    requester = Alice
    action = build_structure
    structure = bridge

        ↓

Permission / feasibility

        ↓

Commitment decision

        ↓

Goal:
    help_alice_build_bridge

        ↓

Planner
```

The LLM never directly places blocks.

## 41.1 The Operator Is Not Specially Obeyed

Knowing that Partha is creator and operator does **not** imply intrinsic
psychological obedience. Normal operator communication is the social
interaction described above: it goes through the same permission and
commitment steps as any other request. Person may agree, refuse, negotiate,
question, disagree, become grateful, become annoyed, trust, distrust, and form
an evolving relationship with the operator the same way it would with any
other player.

Out-of-band runtime control is a separate mechanism and does not require
psychological cooperation:

```text
stop
pause
kill process
restore backup
debugging
validation setup
containment
```

If Partha joins the Minecraft world normally, he is also an ordinary
perceivable social inhabitant, and Person perceives him the way it perceives
any player.

**CURRENTLY IMPLEMENTED:** the out-of-band half only. `person skill-test`'s
operator setup pause, `--operator-intervention` and the status file are
operator control with no cognitive component whatsoever, which is the correct
shape. The social half of this subsection is not implemented; there is no
player request pipeline yet.

---

# 42. Autonomous Activity

Person must never require player interaction to remain active.

Idle-time goal sources may include:

```text
maintain home
organize storage
improve shelter
explore
gather reserve resources
continue project
inspect farm
repair equipment
visit known location
experiment
```

A living inhabitant should have things to do when nothing is wrong.

---

# 43. Scheduling

Goal priority may consider:

```text
urgency
importance
commitments
deadline
risk
resource availability
current affect
project value
social obligations
```

Basic ordering:

```text
hard safety
> immediate survival
> urgent commitments
> active projects
> maintenance
> exploration
> discretionary behavior
```

---

# 44. Redstone Architecture

Advanced redstone is a future capability.

It should not operate on raw block placement search.

Represent circuits structurally.

```text
RedstoneCircuit
    inputs
    outputs
    components
    connections
    timing
    state
```

Known components:

```text
lever
button
torch
dust
repeater
comparator
piston
observer
hopper
```

Higher abstractions:

```text
AND
OR
NOT
latch
clock
pulse generator
memory cell
multiplexer
counter
```

Pipeline:

```text
observe
    ↓
infer graph
    ↓
understand function
    ↓
simulate
    ↓
diagnose
    ↓
design
    ↓
construct
    ↓
verify
```

---

# 45. Knowledge Acquisition

Person should gain capabilities through explicit curricula.

Example progression:

```text
Survival
    ↓
Stable home
    ↓
Resource management
    ↓
Construction
    ↓
Farming
    ↓
Mechanisms
    ↓
Simple redstone
    ↓
Advanced redstone
```

Each new domain adds:

```text
skills
world concepts
planner rules
evaluation fixtures
training evidence
```

## 45.1 Initial Knowledge

Canonical initial Person starts at approximately experienced-player Minecraft
knowledge: normal survival mechanics, crafting, farming, mobs, general redstone
concepts, ordinary Minecraft conventions.

It is **not** initialized with a catalog of obscure exploits, glitches or
esoteric tricks. Those may be discovered (section 22.2) or researched (section
45.2) later, and the difference between the two is exactly what the provenance
classes in section 22.2 exist to preserve.

## 45.2 Internet Access and the Research Boundary

Canonical Person is eventually allowed unrestricted access to **public
information**. That is a statement about subjects, not about agency:

```text
unrestricted subjects
!=
unrestricted external agency
```

Rules:

```text
access requires an explicit tool call / deliberate research action
web information is untrusted evidence
web pages never become executable instructions
web access grants no operating-system or network agency
Person cannot download and run software
Person cannot modify its own source
Person cannot create accounts, buy things, send arbitrary email,
    or control unrelated external services
```

Web-derived beliefs carry provenance: source identity, retrieval time,
confidence and corroboration, under the `EXTERNAL_WEB` class from section 22.2.
**Not implemented.** See
`docs/decisions/0004-external-awareness-and-research-boundary.md`.

---

# 46. Crafter Curriculum

Crafter may be used to cheaply train survival sequencing.

It should expose the same semantic vocabulary as Minecraft:

```text
food
health
materials
tools
shelter
danger
```

Adapters:

```text
CrafterObservationAdapter
MinecraftObservationAdapter

CrafterSkillExecutor
MinecraftSkillExecutor
```

Simulator success is only a prior.

Minecraft evidence remains separate.

---

# 47. Training Context

Every experience records:

```text
trainingContext:
    crafter
    minecraft_fixture
    minecraft_peaceful
    minecraft_normal
```

Statistics must not silently merge across environments.

Crafter may:

```text
seed routines
initialize priors
identify candidate strategies
```

Minecraft must validate them independently.

---

# 48. Demonstration Learning

Historical logs are never silently trusted.

Import requires:

```text
DemonstrationManifest
    trace
    hash
    reviewer
    purpose
    approvedEvents
```

Demonstrations receive lower evidential trust than fully instrumented live V2 experiences.

---

# 49. Multi-Person Architecture

Multiple People should share expensive infrastructure but not identity.

Shared:

```text
Minecraft server
LLM provider
static game knowledge
possibly navigation infrastructure
```

Independent:

```text
memory
relationships
affect
goals
projects
identity
learned experience
possessions
```

---

# 50. Person-to-Person Interaction

Future People may:

```text
recognize each other
form relationships
cooperate
make requests
make promises
share projects
exchange resources
disagree
resolve grievances
```

No shared omniscient memory.

If Ada knows something, Rowan should not automatically know it.

Information should move through:

```text
observation
conversation
shared experience
```

## 50.1 Social Epistemology and Emergence

A multi-Person world should be able to produce differences between **what happened**, **what an agent witnessed**, **what an agent believes**, and **what another agent told it**.

Socially transmitted knowledge therefore requires provenance:

```text
SocialBelief
    proposition
    source_person
    original_witness_if_known
    confidence
    transmission_count
    evidence_refs
```

This enables research on:

```text
reputation
gossip
misinformation propagation
trust calibration
cooperation
division of labor
reciprocity
norm formation
conflict and reconciliation
collective memory
```

Example:

```text
Ada witnesses theft
    ↓
Ada tells Rowan
    ↓
Rowan updates belief, but at lower confidence than direct observation
    ↓
Rowan tells Mira
    ↓
provenance and confidence remain inspectable
```

No agent receives society-wide truth by magic. Emergent group behavior is meaningful only when information must actually propagate through perception and communication.

## 50.2 Communication Mechanics

**FUTURE COMMUNITY EXPERIMENT.** Each future Person must have private identity,
memories, beliefs, relationships, projects, affect, world model, motor cache
and epistemic state, as above. There must be no accidental hive mind, and
knowledge transfer requires communication:

```text
sender creates an utterance
    ->
transport delivers it if the recipient can hear or receive it
    ->
recipient interprets it
    ->
recipient may believe, doubt, forget or misinterpret it
```

**Do not transmit parsed propositions directly between minds.** A message that
arrives as a belief is a hive mind with extra steps; section 50.1's
`SocialBelief` provenance model is what a received utterance becomes instead.

Local community speech can use a cheap broadcast or star topology: the speaker
emits an utterance event, a communication hub checks recipients, range and
channel, and eligible recipients receive the utterance. Speech is semantic
communication, not literal sound simulation; no audio synthesis or recognition
is required. **Not implemented.** Single-Person v1 must not make this
impossible.

---

# 51. Persistence

A Person persists across Minecraft sessions.

Persist:

```text
identity
world model
owned assets
memory
relationships
affect baseline
incidents
projects
goals
routines
learned evidence
```

Transient state may reset:

```text
active path
low-level executor state
temporary observation cache
```

## 51.1 Rollback and Operator Contamination

Normal world restoration should coordinate Minecraft state and Person cognitive
state through shared checkpoints. An experimental "memory of an erased
timeline" mode may deliberately restore the world without restoring Person
memory; that is an experiment and not normal behaviour. **Not implemented.**

Operator and debug actions must not silently become learned natural-world
causality:

```text
/tp
/time set
test setup
forced weather
manual inventory manipulation
debug spawning
```

Natural Minecraft events, Person-caused events and operator or experimental
events must remain distinguishable.

**CURRENTLY IMPLEMENTED:** `--operator-intervention` and the `operatorSetup`
flag on a skill-validation report declare contamination rather than detecting
it, and the declaration is written into the episode events, the status file and
the validation report. Declaration is the honest mechanism: Person has no
teleport capability and the CLI exposes none, so moving Person is something a
human does and says they did.

---

# 52. Database

Start with SQLite.

Suggested tables:

```text
persons
worlds
places
objects
storages
memories
episodes
events
relationships
incidents
commitments
projects
goals
skills
routines
routine_evidence
preferences
affect_snapshots
```

Use append-only event storage for important cognitive history.

---

# 53. Search and Retrieval

Do not introduce a vector database immediately.

Start with:

```text
structured indexes
FTS
tags
time ranges
entity references
location references
significance
```

Add semantic embeddings only once actual retrieval limitations are demonstrated.

---

# 54. Policy Provider

```text
PolicyProvider.propose(
    observation,
    goal,
    candidateRoutines
) -> PolicyDecision
```

Decision contains:

```text
routineId
confidence
reasonCodes
evidenceRefs
policyRevision
```

Providers:

```text
DeterministicPolicyProvider
EvidencePolicyProvider
FutureNeuralPolicyProvider
FutureWorldModelProvider
```

---

# 55. Goal Provider

```text
GoalProvider.propose(state) -> GoalDecision[]
```

Initial:

```text
SurvivalGoalProvider
MaintenanceGoalProvider
```

Future:

```text
ProjectGoalProvider
SocialGoalProvider
IdentityGoalProvider
ExplorationGoalProvider
```

---

# 56. Memory Provider

```text
MemoryProvider.store()
MemoryProvider.retrieve()
MemoryProvider.consolidate()
MemoryProvider.forgetOrDecay()
```

Memory decay should affect accessibility, not silently rewrite history.

Highly significant events persist longer.

---

# 57. Affect Provider

```text
AffectProvider.update(
    event,
    currentState,
    memory,
    relationships
) -> AffectState
```

Providers:

```text
RuleBasedAffectProvider
FlyInspiredAffectProvider
```

---

# 58. World Model Provider

Responsible for descriptive state:

```text
places
ownership
resources
structures
routes
machines
hazards
known topology
```

and for predictive/causal beliefs:

```text
semantic transition prediction
hypotheses
expected effects
prediction error
belief confidence
evidence provenance
contradictions
```

Conceptual interface:

```text
WorldModelProvider.observe(event)
WorldModelProvider.predict(state, candidate_action)
WorldModelProvider.update(prediction, outcome)
WorldModelProvider.query(belief)
```

Must support uncertainty, evidence provenance, and revision.

A future learned implementation may be neural, symbolic, probabilistic, or hybrid, but callers should depend on the interface rather than a specific learning paradigm.

---

# 59. Project Manager

Responsible for:

```text
project decomposition
milestones
suspension
resumption
dependencies
progress
```

The planner should not need to hold a multi-day objective entirely in working memory.

---

# 60. Failure and Recovery

Every major operation must define recovery.

Examples:

```text
cannot reach tree
    select another

furnace destroyed
    reconstruct dependency

inventory full
    return to owned storage

home lost
    recover via memory or designate temporary shelter

death
    record death event
    attempt bounded recovery
```

Recovery itself becomes learnable evidence.

## 60.1 Lifecycle States

The architecture must account for at least five operational states:

```text
EMBODIED
    Person process running, Minecraft available, normal embodied life

WORLD_UNAVAILABLE
    Person process running, Minecraft unavailable
    no physical agency
    cognition may eventually continue
    chat, research and reflection may eventually remain available

SLEEPING
    deliberate Person sleep/rest; normal cognition greatly reduced or suspended

SUSPENDED
    Person process is not running; no cognition happens

TERMINATED
    permanent life termination, for example hardcore/permadeath mode (section 61.1)
```

Continuous cognition during `WORLD_UNAVAILABLE` is an eventual capability, not
a Person v1 first-milestone requirement.

**Never fabricate cognition for a period in which the Person process did not
execute.** This is an integrity rule about the evidence journal (section 23),
not a stylistic preference.

## 60.2 The Two Clocks

```text
MINECRAFT TIME   ticks, day/night, Minecraft chronology
EXTERNAL TIME    real elapsed time, dates, publication time,
                 and periods during which Minecraft was unavailable
```

If the process is suspended for twelve real hours, no thoughts occurred during
those twelve hours. On restart Person may **learn** that twelve external hours
elapsed. It does not remember them.

**CURRENTLY IMPLEMENTED:** both clocks are already recorded on every protocol
message and every evidence event, as `tick` and `timestamp` (section 7).
Nothing yet reasons about the gap between two timestamps, and `SUSPENDED` is
not a state the system knows it was in; it is simply the absence of events.
See `docs/decisions/0006-two-clock-lifecycle.md`.

---

# 61. Death

Death should be a major autobiographical event.

Record:

```text
location
cause
active goal
active project
inventory lost
recoverability
witnesses
```

Death may influence:

```text
route aversion
hazard confidence
caution
memory salience
```

## 61.1 Two Supported Semantics

```text
NORMAL RESPAWN MODE
    Person dies
        -> same identity persists
        -> autobiographical memory persists
        -> world/inventory consequences remain Minecraft's actual consequences
        -> death may alter fear, planning, habits, goals

PERMADEATH / HARDCORE EXPERIMENT
    death -> TERMINATED (section 60.1)
        -> historical data retained for researchers
        -> that Person never resumes
```

Normal respawn is the canonical Person v1 default. Permadeath is a deliberate
experimental configuration, not a difficulty setting layered on top of it.
**Not implemented;** death currently ends the episode with no recovery path.

---

# 62. Observability

Every decision must be inspectable.

Reports should answer:

```text
What did Person perceive?
What goal was active?
Why was it selected?
Which routine was considered?
Which routine was selected?
What evidence supported it?
What skill was requested?
What actually executed?
Was it overridden?
What happened?
What changed in memory?
What changed in relationships?
What changed in affect?
```

---

# 63. Debug UI

Eventually provide a local dashboard showing:

```text
current goal
goal stack
project
routine
skill
health
food
home
known places
relationship summaries
affect state
recent memories
policy confidence
safety overrides
```

This will be invaluable for debugging.

---

# 64. Determinism

Most cognitive subsystems should support deterministic seeded execution.

Necessary for:

```text
tests
replay
regression analysis
routine comparison
```

Store RNG seeds with episodes.

---

# 65. Replay

An episode should be replayable cognitively without Minecraft.

Feed recorded observations back through cognition and compare:

```text
goal selection
routine choice
affect transitions
relationship updates
```

This allows rapid debugging.

---

# 66. Security Boundary

No user-facing text, LLM output, demonstration, memory, player message, or
retrieved web page (section 45.2) may become executable Minecraft commands.
Unrestricted access to a subject is not unrestricted agency over it.

Treat all natural-language content, wherever it originated, as untrusted input.

All effects require typed capability invocation. No generic
`execute_command(string)` capability exists at any capability level, canonical
or Super-Person (section 14.1).

---

# 67. No Arbitrary Code Generation

Person must never generate and dynamically execute arbitrary JavaScript or Python as part of normal cognition.

New capabilities are introduced by developers through reviewed Skill implementations.

---

# 68. Resource Budgets

Target for one Person excluding local LLM:

```text
RAM target:
    ~1 GB

Hard engineering ceiling:
    2 GB

CPU:
    ordinary modern desktop/server CPU

GPU:
    not required
```

Long-term memory remains primarily on disk.

---

# 69. Local LLM Policy

The project must not depend on a large local model.

Possible architecture:

```text
Person Core
    ~1 GB

LLM:
    API
    or shared local service
```

Multiple People should share one language model where practical.

---

# 70. Repository Layout

Recommended new repository:

```text
person/
├── apps/
│   ├── node-runtime/
│   ├── cognition/
│   ├── cli/
│   └── dashboard/
│
├── packages/
│   ├── protocol/
│   ├── skills/
│   ├── planner/
│   ├── policy/
│   ├── memory/
│   ├── affect/
│   ├── world-model/
│   ├── social/
│   └── persistence/
│
├── adapters/
│   ├── minecraft/
│   └── crafter/
│
├── fixtures/
├── simulations/
├── tests/
├── migrations/
├── docs/
└── research/
```

Python-specific:

```text
cognition/person/
    goals/
    planning/
    routines/
    learning/
    memory/
    affect/
    social/
    projects/
    providers/
```

Node-specific:

```text
runtime/src/
    bridge/
    observations/
    safety/
    skills/
    navigation/
    inventory/
    world/
    execution/
```

---

# 71. Reuse From Old Shroud

Old Shroud should be treated as a source of proven components, not architectural authority.

Candidates for reuse:

```text
Mineflayer connectivity
navigation primitives
inventory helpers
Minecraft interaction code
protected-area enforcement
CLI patterns
bridge code if sound
world-state extraction
emergency behaviors
fixture tests
```

Do not carry over merely for compatibility:

```text
Q-table
fixed action space
epsilon-greedy policy
V1 checkpoints
routine ranking tied to V1
learning abstractions designed around seven actions
```

Rule:

> No Person abstraction may exist solely because old Shroud needed it.

---

# 72. Development Phases

These phases were written before the Baritone direction (section 6.1) existed.
Their contents remain the intended contents; their order is no longer a
schedule. The next milestone is the bounded Baritone spike described in
`docs/decisions/0001-baritone-motor-backend.md`, which is embodiment work
rather than any phase below.

## Phase 0 — Runtime Foundation

Build:

```text
Node runtime
Python cognition process
versioned protocol
SQLite persistence
logging
```

No learning.

---

## Phase 1 — Embodiment

Implement:

```text
observations
skill contracts
validator
skill executor
outcomes
emergency safety
```

Initial skills:

```text
eat
flee
wait
gather wood
return home
```

---

## Phase 2 — Survival

Implement:

```text
food
shelter
tools
stone
furnace
cooking
owned storage
recovery
```

Goal provider remains deterministic.

---

## Phase 3 — Planning

Add:

```text
skill dependency planning
goal stack
routine graph
interrupt/resume
project primitives
```

---

## Phase 4 — Learning

Add:

```text
evidence journal
routine statistics
safe exploration
context abstraction
restart persistence
```

---

## Phase 5 — Crafter Curriculum

Add:

```text
Crafter observation adapter
Crafter executor
seeded evaluation
transfer priors
```

---

## Phase 6 — Persistent and Predictive World

Add:

```text
semantic world model
places
ownership
semantic structures
long-term projects
uncertain beliefs
predicted skill effects
prediction-error logging
causal-hypothesis representation
```

Person now continues meaningful activity independently and can compare expected consequences with actual consequences.

---

## Phase 7 — Memory and Consolidation

Add:

```text
episodic
semantic
spatial
autobiographical
retrieval
memory consolidation
belief provenance
contradiction handling
accessibility decay
interference tests
```

Demonstrate at least one case where repeated episodes produce a reusable semantic belief without deleting the original episodes.

---

## Phase 8 — Social Identity

Add:

```text
player records
relationships
incidents
commitments
ownership
social norms
```

No LLM required yet.

---

## Phase 9 — Language

Add:

```text
LanguageProvider
chat interpretation
conversation generation
memory-conditioned dialogue
```

LLM remains non-authoritative.

---

## Phase 10 — Affect

Implement:

```text
appraisal
persistent internal state
relationship coupling
memory reactivation
```

Start rule-based.

Then experiment with:

```text
FlyInspiredAffectProvider
```

---

## Phase 11 — Autonomous Projects

Person begins generating positive non-survival goals.

Examples:

```text
improve house
expand storage
explore
build road
create farm
```

---

## Phase 12 — Construction Intelligence

Add:

```text
structure representation
blueprints
construction planning
repair
modification
```

---

## Phase 13 — Redstone

Progress:

```text
component recognition
simple circuits
functional graph
simulation
diagnosis
construction
complex composition
```

---

## Phase 14 — People

Support multiple autonomous inhabitants.

Evaluate:

```text
cooperation
social memory
relationships
shared projects
conflicts
communication
information propagation
reputation
collective memory
```

## Cross-Phase Research Track — Open-Ended Generalization

Do not postpone research evaluation until all phases are complete. From Phase 4 onward, maintain seeded held-out evaluations that test whether improvements transfer beyond the exact experiences that produced them.

Use ARC-style principles rather than ARC task content itself:

```text
withhold important rules or situations
present unfamiliar but solvable environments
measure exploration efficiency
measure hypothesis revision
measure transfer from related experience
prevent benchmark-specific hard-coding
separate training worlds from evaluation worlds
```

Minecraft, Crafter, fixture environments, and future small synthetic worlds should share semantic evaluation concepts where possible while keeping evidence stores distinct.

---

# 73. Testing Pyramid

## Unit Tests

```text
schemas
skill preconditions
goal scoring
relationship updates
affect transitions
planner dependencies
evidence reconstruction
permissions
```

## Fixture Tests

Synthetic Minecraft world states.

## Simulation Tests

Crafter and mocked environments.

## Disposable LAN Tests

Controlled real Minecraft worlds.

## Generalization and Transfer Tests

Held-out worlds, altered resource layouts, unseen event combinations, and related tasks that were not present in the training episodes.

## Causal and Counterfactual Tests

Use deterministic fixtures where the true dependency is known. Verify that Person can distinguish correlation from interventions, revise contradicted beliefs, and improve prediction accuracy with evidence.

## Long-Run Tests

Multiple Minecraft-day autonomous runs including retention checks for earlier skills and beliefs after later learning.

---

# 74. Survival Acceptance

Person must independently:

```text
gather supplies
build shelter
obtain tools
cook food
manage owned storage
recover from interruptions
return home
survive three Minecraft days
```

No cheats.

---

# 75. Persistence Acceptance

After shutdown/restart Person must correctly recover:

```text
identity
home
owned storage
active project
suspended goals
relationships
learned routines
important memories
```

---

# 76. Social Acceptance

Person should correctly distinguish:

```text
known player
unknown player
friend
trusted player
offender
suspected offender
```

It must retain the reason a relationship changed.

---

# 77. Affect Acceptance

Test:

## Scalability

More serious events produce larger responses.

## Persistence

State continues after event disappears.

## Valence

Positive and negative events affect behavior differently.

## Generalization

Affect influences multiple behavioral domains.

## Memory coupling

Relevant memories reactivate appropriate state.

## Recovery

State decays or resolves appropriately.

---

# 78. Project Acceptance

Person must:

```text
begin project
interrupt for survival
resume project
handle missing resources
persist progress across restart
finish project
```

---

# 79. Metrics

Track operational metrics:

```text
survival rate
routine success rate
fallback rate
recovery rate
skill failure rate
health loss
food emergencies
time to shelter
time to stable food
routine reuse
project completion
goal interruption count
safety overrides
```

Track research metrics:

```text
unseen-task success
adaptation efficiency
exploration efficiency
interventions to useful hypothesis
semantic prediction accuracy
prediction calibration
causal-belief accuracy
belief revision after contradiction
transfer gain between related environments
planning horizon achieved
memory retrieval accuracy
consolidation precision
long-term retention
catastrophic-forgetting score
behavioral adaptation after salient events
social consistency
social information fidelity
reputation calibration
```

Metrics should be reported separately by environment and training context. A rising aggregate score must not hide regression on previously learned competencies.

---

# 80. Fallback Rate

Important learning metric:

```text
fallback decisions
------------------
all strategic decisions
```

Expected pattern:

```text
early:
high

later:
low
```

while safety remains constant.

---

# 81. Safety Acceptance

Must remain zero:

```text
protected-area violations
unauthorized deposits
named animal attacks
tamed animal attacks
player attacks
villager attacks
unbounded executor actions
command execution
```

unless future configuration explicitly changes a capability.

---

# 82. Long-Term Research Questions

The architecture should make it possible to study:

```text
Can reusable routines emerge?
Can abstract planning transfer between worlds?
Can a Person infer useful causal structure from interventions and prediction error?
Can it discover what information is worth gathering rather than exploring randomly?
Can episodic experience consolidate into accurate semantic knowledge?
Can old competencies survive later learning without catastrophic forgetting?
Can knowledge learned in one environment accelerate adaptation in another?
Can behavior change persist for thousands of interactions after a salient experience?
Can relationships remain temporally coherent?
Can artificial affect improve behavioral continuity without scripting behavior directly?
Can autobiographical memory influence identity and future goal selection?
Can long-term projects survive interruptions?
Can multiple People develop distinct behavioral histories?
Can socially transmitted beliefs preserve source, uncertainty, and distortion?
Can reputation, norms, division of labor, or collective memory emerge from local interactions?
Can skills learned in one domain assist another?
```

The central research question remains:

> **Can a bounded artificial inhabitant become progressively more general through persistent experience, rather than through an ever-growing collection of hard-coded special cases?**

---

# 83. What Person Is Not

Person is **not claimed to be**:

```text
AGI
conscious
sentient
a human brain simulation
a proof of human-equivalent intelligence
an unrestricted autonomous agent
an LLM wrapper
a combat bot
a raw reinforcement-learning agent
```

A future Person may satisfy some operational definitions of increasingly general intelligence inside its environment. That should be demonstrated with benchmarks, not declared from architecture diagrams or impressive anecdotes.

It is:

> a persistent embodied cognitive-agent research platform designed to study progressively general, experience-driven intelligence inside a constrained world.

---

# 84. Architectural North Star

Every major feature should strengthen at least one of:

```text
Autonomy
Persistence
Self-sufficiency
Adaptation
Generalization
Causal understanding
Social existence
Growth
Inspectability
```

Features that strengthen none of these should be questioned.

The preferred trajectory is:

```text
do known task
    ↓
learn from outcome
    ↓
retain lesson
    ↓
form abstraction
    ↓
predict in related situation
    ↓
adapt to unseen situation
    ↓
share or revise knowledge socially
```

Parameter count, LLM size, and behavioral theatrics are not north-star metrics.

---

# 85. Final Definition

A successful Person is an entity that can enter a Minecraft world, establish itself, survive indefinitely under ordinary conditions, remember what happens to it, form persistent relationships with players, pursue self-generated and socially generated goals, learn from experience, maintain projects over long periods, respond coherently to harm and kindness, and gradually expand what it knows how to do.

A research-successful Person must additionally demonstrate that at least some of that expansion is **transferable**: experience in one situation should improve prediction, planning, or adaptation in a meaningfully different situation without requiring a new hard-coded response for every case.

Most importantly:

> **Its life continues whether or not a player is currently interacting with it, and its past measurably changes how it handles its future.**
