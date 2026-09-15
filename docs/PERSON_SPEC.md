# PERSON

## A Persistent Artificial Inhabitant for Minecraft

**Status:** Architecture specification
**Target:** Minecraft Java Edition 1.16.1 initially
**Primary runtime:** Node.js 22 + Python 3.12
**Initial embodiment:** Mineflayer
**Design philosophy:** CPU-first, persistent, interpretable, bounded, modular
**Research framing:** Open-ended embodied cognitive-agent testbed; AGI-relevant, not an AGI claim
**Long-term objective:** Artificial inhabitants whose lives continue independently of direct player interaction and improve through persistent experience

---

# 1. Vision

Person is not a chatbot connected to Minecraft and not a conventional game bot.

Person is a persistent autonomous inhabitant capable of:

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

## 1.1 Research Thesis

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

## 1.2 Scientific Claim Discipline

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
│              Mineflayer                     │
└─────────────────────────────────────────────┘
```

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

---

# 8. Observation Model

Python receives semantic state rather than raw Minecraft internals.

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

Places:

```text
home
farm
mine
village
workshop
hazard
machine
```

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

Nearby raw blocks remain Mineflayer's concern. The cognition layer should reason over semantic state, not reconstruct the entire voxel world in memory.

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

No user-facing text, LLM output, demonstration, memory, or player message may become executable Minecraft commands.

Treat all natural-language content as untrusted input.

All effects require typed capability invocation.

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
