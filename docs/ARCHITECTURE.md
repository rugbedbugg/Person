# Architecture

Person is split across two processes with a deliberately asymmetric
relationship. The Python cognition process decides what Person should try to
do. The Node runtime decides what Person is physically allowed to do, does it,
and reports what actually happened.

This file describes two things and labels which is which: the architecture that
exists today, and the architecture `docs/PERSON_SPEC.md` Part 0 freezes as the
target. Nothing in the target section is implemented.

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

The direction frozen on 2026-09-22. **None of this exists.**

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

| Change                                                   | ADR  |
| -------------------------------------------------------- | ---- |
| The body becomes a motor layer that may be swapped       | 0001 |
| Perception becomes a sense model rather than a budget    | 0002 |
| Memory gains a retrieval layer distinct from the journal | 0003 |
| Research is a deliberate act with untrusted results      | 0004 |

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

| Process                     | Owns                                                                                                                                   |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `person` (Node)             | Minecraft connectivity, navigation, safety kernel, permissions, protected areas, skill execution, outcome attribution, episode reports |
| `person-cognition` (Python) | Decision context, goals, planning, routines, policy, evidence journal, learning, learning reports                                      |

Node is the parent process. It spawns cognition over stdio, and if cognition
crashes, hangs, or starts emitting messages it is not entitled to send, the
runtime keeps control of the body, ends the episode cleanly and writes its
report.

## Packages

```
packages/protocol      canonical JSON Schemas plus TypeScript and Python bindings
packages/skills        the SkillSpec library as data, read by both runtimes
packages/config        configuration schema, loader, legacy migration
packages/planner       symbolic state and means-ends planning (Python)
packages/policy        statistics, safe envelope, policy providers (Python)
packages/persistence   evidence journal, snapshots, restore (Python)

apps/node-runtime      observation builder, validator, safety kernel, executor, IPC, reporting
apps/cognition         decision context, goals, routines, decision loop (Python)
apps/cli               the person command line

adapters/minecraft     Mineflayer embodiment (production body)
fixtures               deterministic fixture world (test body) and protocol corpus
```

Two packages are dual-language on purpose. `protocol` and `skills` hold one
canonical set of JSON files with a thin binding for each runtime, which is what
stops the TypeScript and Python views of a contract from drifting apart. The
skill library computes a revision hash from its spec files; both runtimes
compute the same hash, and the session handshake compares them.

## The decision loop

1. The runtime builds a semantic `Observation` from the embodiment and sends it.
2. Cognition derives a coarse decision context and a symbolic state.
3. The goal provider proposes goals with homeostatic priorities; the goal stack
   activates one, suspending whatever it interrupted.
4. The planner derives candidate plans from skill preconditions and effects.
5. Each plan becomes a routine with a stable, content-derived identifier.
6. The policy provider picks one and says whether the choice was learned or a
   fallback, with the evidence that supported it.
7. Cognition sends `GoalDecision`, `PolicyDecision`, and one `SkillInvocation`
   for the next step of the routine.
8. The runtime validates the invocation, then accepts, rejects, or replaces it.
9. The runtime executes the resulting skill under its cost limits, checking the
   safety kernel at every checkpoint.
10. The runtime sends `SkillOutcome`, naming both the requested and the executed
    skill, and cognition records it as immutable evidence.

## Layers that keep working when the layer above fails

The deterministic policy needs no evidence, so Person behaves sensibly with
learning switched off. The safety kernel needs no policy, so Person flees, eats
and digs in whether or not cognition is healthy. The embodiment needs no
cognition at all, which is why a crashed cognition process ends an episode
rather than stranding a body in a hostile world.

## What is not here

No language model, no neural policy, no affect, no social memory, no belief
store, no world model, no memory system, no projects beyond goal suspension, no
redstone, no web access, no external chat.
`apps/cognition/python/person_cognition/future_providers.py` holds the
interfaces those systems will attach to. Every one of them raises rather than
returning a plausible empty result, so nothing can mistake a placeholder for an
implementation.

One absence is worth naming rather than listing. Person has no beliefs. The
symbolic state the planner reasons over is derived fresh from the latest
observation every tick, so there is nothing that could disagree with what was
just seen. `docs/PERSON_SPEC.md` section 0.3 requires that separation and
section 0.24 records its absence as C6.
