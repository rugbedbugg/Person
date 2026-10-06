# Architecture

Person is split across two processes with a deliberately asymmetric
relationship. The Python cognition process decides what Person should try to
do. The Node runtime decides what Person is physically allowed to do, does it,
and reports what actually happened.

This file describes two things and labels which is which: the architecture that
exists today, and the architecture `docs/PERSON_SPEC.md` describes as the
target. Parts of the target now exist; the target section says which.

## Current architecture

```
Python cognition
        |
        |  SkillInvocation
        v
============ TRUST BOUNDARY ============
        |
        v
Node validator  ->  safety kernel  ->  skill executor  ->  embodiment
                                                              |
                                                     Mineflayer or fixture
```

Perception runs the other way, and is the half the diagram above has always
left out:

```
                             embodiment
                                  |
                          WorldSnapshot            complete, runtime-only
                             /        \
              safety kernel /          \ observation builder
              permission gate           |
              physical guard            |  perception shaping
                                        v
                                  Observation      bounded, semantic
                                        |
============ TRUST BOUNDARY ============|============
                                        v
                                 Python cognition
```

The safety kernel, the permission gate and the physical guard all read the
unshaped snapshot. Shaping the observation therefore cannot change what Person
is permitted to do, in either direction. That is the perception firewall's
current form; see ADR 0002.

## Target architecture

The direction frozen on 2026-09-22. Only part of it exists: the perception
firewall and a first vision model (ADR 0002), and a memory retrieval layer
distinct from the journal (ADR 0007). The swappable motor layer (Baritone,
ADR 0001) and deliberate research (ADR 0004) do not exist.

```
                    Person cognition
                            |
                 goals, projects, beliefs, memory
                            |
                       proposed action
                            v
============ TRUST BOUNDARY / CAPABILITY POLICY ============
                            |
              validator -> safety kernel -> executor
                            |
                    ---------------------
                    |                   |
             motor backend        perception filter     <- the firewall
           (Baritone, or           (human-like sense
            Mineflayer, or          model: pose, range,
            the fixture)            occlusion, semantics)
                    |                   ^
                    v                   |
                 Minecraft --------------
```

Four changes from the current picture, each with an ADR:

| Change                                                   | ADR  | Status                                          |
| -------------------------------------------------------- | ---- | ----------------------------------------------- |
| The body becomes a motor layer that may be swapped       | 0001 | Not started                                     |
| Perception becomes a sense model rather than a budget    | 0002 | Partly: vision cone and occlusion, no attention |
| Memory gains a retrieval layer distinct from the journal | 0003 | Done for episodic memory (ADR 0007)             |
| Research is a deliberate act with untrusted results      | 0004 | Not started                                     |

The trust boundary itself does not move. ADR 0005 records why.

## The invariant

Python may propose intentions. Node decides what is physically permitted.

Cognition never holds a Mineflayer object, a socket, a block coordinate it
chose itself, or any way to move, dig, place or attack. The single physical
request it can make is a `SkillInvocation`: a skill id from the published
library, scalar parameters, and cost limits. The protocol schema refuses
anything else, and an architecture test asserts that no `command`, `chat`,
`script` or `code` field can be added without the test failing.

## Processes

| Process                     | Owns                                                                                                                                                                                              |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `person` (Node)             | Minecraft connectivity, navigation, safety kernel, permissions, protected areas, skill execution, outcome attribution, episode reports                                                            |
| `person-cognition` (Python) | Decision context, goals, projects, planning, routines, policy, information seeking, memory, places, affect, effect beliefs, causal hypotheses and experiments, evidence journal, learning reports |

Node is the parent process. It spawns cognition over stdio, and if cognition
crashes, hangs, or starts emitting messages it is not entitled to send, the
runtime keeps control of the body, ends the episode cleanly and writes its
report.

## Packages

```
packages/epistemics    provenance, experience keys, scope, evidence admission,
                       beliefs, perceptual/self/decision state, predictive models (Python)
packages/protocol      canonical JSON Schemas (core envelope) plus bindings, and
                       discovery of installed environment profiles
packages/skills        the generic SkillSpec contract and registry, read by both runtimes
packages/config        core configuration schema and loader
packages/planner       means-ends planning over an environment's facts (Python)
packages/policy        statistics, envelope verdicts, policy providers (Python)
packages/persistence   canonical event journal, snapshots, restore, legacy reading (Python)

environments/minecraft the Minecraft profile: manifest, observation-payload and
                       configuration schemas, skill library and vocabulary,
                       perception, beliefs, facts, goals and envelope (Python),
                       typed observation, configuration and legacy reading (TypeScript)

apps/node-runtime      observation builder, validator, safety kernel, executor, IPC, reporting
apps/cognition         decision context, goals, projects, routines, decision loop,
                       memory/, spatial/, affect, effect learning, hypotheses/ (Python)
apps/cli               the person command line

adapters/minecraft     Mineflayer embodiment (production body)
fixtures               deterministic fixture world (test body) and protocol corpus
```

Person's core names no environment (ADR 0025). An environment is a profile
under `environments/<kind>/`, declared by its `environment.json` manifest and
discovered as data; the core never imports its code.

Two packages are dual-language on purpose. `protocol` and `skills` hold one
canonical set of JSON files with a thin binding for each runtime, which is what
stops the TypeScript and Python views of a contract from drifting apart. The
skill library computes a revision hash from its spec files; both runtimes
compute the same hash, and the session handshake compares them.

## The decision loop

1. The runtime builds a semantic `Observation` from the embodiment and sends it:
   a core envelope around the environment's payload.
2. Cognition crosses the epistemic boundary once (ADR 0026): the environment
   profile turns the observation into a perceptual state, admissible runtime
   reports revise beliefs (journalled as `belief_revised`), and a
   `DecisionState` is composed of percepts, beliefs, self-state, recalled
   memories and initial knowledge. The environment derives the decision
   context, the planning facts and the safe envelope from that state, never
   from the observation.
3. The goal provider proposes goals with homeostatic priorities. Open projects
   add their next milestone, and an open investigation may add one trial goal.
   Affect adjusts non-urgent priorities within a small bound, recorded apart
   from the base priority. The goal stack activates one, suspending whatever
   it interrupted.
4. The planner derives candidate plans from skill preconditions and effects.
   If none exists only because evidence is unseen, cognition searches by gaze
   instead, cued by what it remembers of searching at the place it believes
   it is at.
5. Each plan becomes a routine with a stable, content-derived identifier.
6. The policy provider picks one and says whether the choice was learned or a
   fallback, with the evidence that supported it. Under `supervised` learning,
   effect beliefs and supported hypotheses add small bounded terms. Affect
   scales the evidence policy's exploration bonus and risk weight whenever
   that policy is in use; the deterministic fallback ignores it. Each term is
   recorded separately.
7. Cognition sends `GoalDecision`, `PolicyDecision`, and one `SkillInvocation`
   for the next step of the routine.
8. The runtime validates the invocation, then accepts, rejects, or replaces it.
9. The runtime executes the resulting skill under its cost limits, checking the
   safety kernel at every checkpoint.
10. The runtime sends `SkillOutcome`, naming both the requested and the executed
    skill, and cognition records it as immutable evidence. The outcome is then
    appraised (affect), encoded if it is worth remembering (memory), judged
    against the prediction made for it (effect beliefs), and counted for or
    against any hypothesis it bears on.

## Layers that keep working when the layer above fails

The deterministic policy needs no evidence, so Person behaves sensibly with
learning switched off. The safety kernel needs no policy, so Person flees, eats
and digs in whether or not cognition is healthy. The embodiment needs no
cognition at all, which is why a crashed cognition process ends an episode
rather than stranding a body in a hostile world.

## What exists above the boundary

All of it is TESTED IN FIXTURE (the dedicated-server checkpoint of 2026-09-29
exercised restart reconstruction of memory, places and affect live once), and
none of it reaches the runtime: no
protocol message carries a memory, a place, an affect value, a belief or a
hypothesis.

| Capability                  | Where                                 | ADR  |
| --------------------------- | ------------------------------------- | ---- |
| Bounded information seeking | `person_cognition/search.py`          | 0002 |
| Episodic memory, typed cues | `person_cognition/memory/`            | 0007 |
| Self-motion and places      | `person_cognition/spatial/`           | 0008 |
| Persistent projects         | `person_cognition/projects.py`        | 0009 |
| Affect                      | `person_cognition/affect.py`          | 0010 |
| Learned effect reliability  | `person_cognition/effect_learning.py` | 0011 |
| Causal hypotheses           | `person_cognition/hypotheses/`        | 0012 |

Each is rebuilt from its own journal events and nothing else, so a restart
resumes it. Person's experienced time, reconstructed from `episode_ended`
records, is the clock memory accessibility, affect decay, project cooldowns
and experiment patience run on (ADR 0006, partly implemented).

## Invariants and where they are held

Architectural rules live here, in `docs/PERSON_SPEC.md` and the ADRs, and in
tests; agent instruction files only point here (ADR 0029). A rule whose last
column says "No" is enforced by nothing but review.

| Invariant                                                                                | Decided in                         | Held by                                                                                                                                                                                                              |
| ---------------------------------------------------------------------------------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python proposes intentions; Node decides what is physically permitted                    | PERSON_SPEC 3, ADR 0005            | `dispatch.ts`, `validator.ts`; `tests/architecture/architecture.test.ts`                                                                                                                                             |
| Cognition has no Mineflayer access; only the adapter imports it                          | PERSON_SPEC 6.1                    | `the Minecraft client is only reachable from the adapter`                                                                                                                                                            |
| Requested and executed skill stay distinct; learning credits what executed               | PERSON_SPEC 12                     | `every SkillOutcome names the skill that actually executed`, attribution tests                                                                                                                                       |
| Validation runs change no learning state                                                 | `docs/LAN_TESTING.md`              | `tests/validation/skill-test.test.ts` (fingerprint)                                                                                                                                                                  |
| Fixture, live and replay experience never merge                                          | ADR 0025                           | `test_statistics_never_merge_across_experience_streams`                                                                                                                                                              |
| Person's core is environment-neutral; Minecraft lives in its profile                     | ADR 0025                           | `tests/python/test_epistemic_architecture.py` (incl. `test_environment_vocabulary_never_leaks_into_core_cognition`), `tests/architecture/environment-boundary.test.ts`                                               |
| Physical truth, perception, belief, memory, knowledge and reasoning stay distinct        | PERSON_SPEC 26, ADR 0026           | `test_nothing_downstream_of_the_boundary_reads_a_raw_observation`, `test_planning_never_queries_the_memory_store`, `test_recalled_memory_reaches_planning_but_never_as_a_current_fact`, `test_epistemic_boundary.py` |
| Environment-specific belief never silently becomes general                               | ADR 0026                           | `test_no_code_widens_a_belief_but_the_explicit_gate`                                                                                                                                                                 |
| Knowledge is not omniscient; nothing is promoted to it without an evidence-backed gate   | ADR 0026                           | `test_knowledge_is_initial_until_an_explicit_promotion_exists`                                                                                                                                                       |
| A canonical event is not evidence unless admitted; recall, replay and rollouts never are | ADR 0027                           | `test_a_canonical_event_is_not_evidence_unless_admitted`, `test_every_episode_source_is_lived`                                                                                                                       |
| Predictions are model rollouts; no predictive model reaches the body                     | ADR 0028                           | `test_prediction_is_plural_and_a_prediction_is_never_evidence`, `test_a_predictive_model_has_no_route_to_the_body`                                                                                                   |
| A body's world knowledge does not become Person's perception                             | PERSON_SPEC 8, ADR 0002            | `tests/observation/perception-firewall.test.ts`, `test_privileged_world_truth_has_no_way_into_cognition`                                                                                                             |
| The journal is engineering truth; Person gets recollection, not a query                  | PERSON_SPEC 24, ADR 0003           | `test_memory_cannot_read_the_journal_for_itself`, `test_no_arbitrary_query_interface_to_memory_exists`                                                                                                               |
| Respawn continues the same Person; terminal death is explicit and final                  | ADR 0017                           | `test_respawn_continues_the_same_person_and_terminal_death_is_final`, `test_respawn_is_the_default_and_permadeath_is_an_explicit_choice`                                                                             |
| Live validation is claimed only when run against Minecraft                               | `REALITY_VALIDATION.md` vocabulary | No: review                                                                                                                                                                                                           |
| Targets are runtime-issued referents, never coordinates chosen by cognition              | PERSON_SPEC 10.1                   | No: skills still choose their own targets (C4)                                                                                                                                                                       |
| Baritone is motor cortex; no command strings reach cognition                             | PERSON_SPEC 6.1, ADR 0001          | No Baritone exists; the command-field test covers the protocol                                                                                                                                                       |
| Unrestricted subjects is not unrestricted external agency                                | PERSON_SPEC 45.2, ADR 0004         | No: nothing external exists                                                                                                                                                                                          |
| Raising one capability axis must not silently raise another                              | PERSON_SPEC 4.1                    | No                                                                                                                                                                                                                   |
| No cognition is fabricated for a period when the process did not run                     | PERSON_SPEC 60, ADR 0006           | Partly: experienced-time restart tests                                                                                                                                                                               |
| Containment, self-preservation and property policy are separate concerns                 | PERSON_SPEC 13                     | No: still documentary (C2)                                                                                                                                                                                           |
| Operator intervention stays distinguishable from natural causality                       | PERSON_SPEC 51.1                   | Partly: `operatorIntervention` on skill-test reports; `OPERATOR_INTERVENTION` provenance class                                                                                                                       |

## What is not here

No language model (the hypothesis generator accepts one, and none is wired),
no neural policy, no social memory, relationships or social cognition, no
semantic or autobiographical memory, no consolidation, no knowledge store, no
landmark identity, no projects beyond two persistent kinds, no redstone, no web
access, no external chat.
`apps/cognition/python/person_cognition/future_providers.py` holds the
interfaces the remaining systems will attach to (language, social,
exploration). Every one of them raises rather than returning a plausible
empty result, so nothing can mistake a placeholder for an implementation. The
world-model placeholder is gone (ADR 0028): prediction is the plural
`PredictiveModel` interface, implemented once by the declared-effect model.
The investigations of ADR 0012 are a first form of experimentation.

One absence is worth naming rather than listing. Person now holds fact
beliefs, but only those the trusted runtime reports about its own situation
(its shelter, home, storage, stations and food reserve), plus effect
reliability and causal hypotheses. What it senses still reaches planning as
percepts, not beliefs, and nothing is ever promoted to knowledge.
`docs/CURRENT_STATE.md`, "Known Deviations", records this as C6, partly
addressed.
