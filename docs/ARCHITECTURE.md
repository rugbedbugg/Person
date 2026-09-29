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
packages/protocol      canonical JSON Schemas plus TypeScript and Python bindings
packages/skills        the SkillSpec library as data, read by both runtimes
packages/config        configuration schema, loader, legacy migration
packages/planner       symbolic state and means-ends planning (Python)
packages/policy        statistics, safe envelope, policy providers (Python)
packages/persistence   evidence journal, snapshots, restore (Python)

apps/node-runtime      observation builder, validator, safety kernel, executor, IPC, reporting
apps/cognition         decision context, goals, projects, routines, decision loop,
                       memory/, spatial/, affect, effect learning, hypotheses/ (Python)
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

All of it is TESTED IN FIXTURE only, and none of it reaches the runtime: no
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

## What is not here

No language model (the hypothesis generator accepts one, and none is wired),
no neural policy, no social memory, relationships or social cognition, no
semantic or autobiographical memory, no consolidation, no knowledge store, no
landmark identity, no projects beyond two persistent kinds, no redstone, no web
access, no external chat.
`apps/cognition/python/person_cognition/future_providers.py` holds the
interfaces the remaining systems will attach to (world model, language,
social, exploration). Every one of them raises rather than returning a
plausible empty result, so nothing can mistake a placeholder for an
implementation. Two of them are already partly overtaken, and are kept only
until their own systems are designed: predictions, effect beliefs and
hypotheses are a first world model, and the investigations of ADR 0012 are a
first form of experimentation.

One absence is worth naming rather than listing. Person has beliefs of only
two narrow kinds: how reliably each skill's declared effects follow, and
whether a perceived condition changes that. The symbolic state the planner
reasons over is still derived fresh from the latest observation every tick, so
nothing Person believes can disagree with what was just seen, and nothing is
ever promoted to knowledge. `docs/PERSON_SPEC.md` section 26 requires that
separation, and `docs/CURRENT_STATE.md`, "Known Deviations", records it as C6,
still unresolved.
