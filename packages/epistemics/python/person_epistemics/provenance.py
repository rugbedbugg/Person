"""Where a piece of information came from, as a closed set of semantic classes.

Every belief, every piece of evidence, every remembered episode and every
prediction carries one of these classes. They are not labels for the record:
the class decides what the information may become.

    lived experience     REAL_OBSERVATION, INTERVENTION_OUTCOME
    world-state evidence the lived classes, and RUNTIME_REPORT
    reported, untrusted  TESTIMONY, RESEARCH, OPERATOR_INTERVENTION
    never new evidence   MEMORY_RECALL, REPLAY, COUNTERFACTUAL, MODEL_ROLLOUT,
                         INFERENCE, INITIAL_KNOWLEDGE

Three rules follow, and `person_epistemics.evidence` and the memory package
enforce them:

1. Only lived classes become autobiographical episodes. A model rollout or a
   counterfactual is something Person imagined; it is never something Person
   remembers having lived.
2. Recalling a memory is not seeing the world again. A recalled episode may
   cite the evidence it was formed from; recalling it adds none.
3. Replay is re-processing of records Person already has. It is kept apart
   from new lived experience by its experience context, and is never admitted
   as new evidence about the world Person is living in.

Not every class has a producer yet. `TESTIMONY` and `RESEARCH` have no channel
(ADR 0004), and nothing rolls a model out (ADR 0028). They are named now so the
distinction exists before anything could blur it (`PERSON_SPEC` section 22.2).
"""

from __future__ import annotations

from enum import StrEnum


class Source(StrEnum):
    """The semantic class of an item of information."""

    #: Person sensed it, now, through its own body.
    REAL_OBSERVATION = "real_observation"
    #: What followed an action Person took: the outcome of its intervention.
    INTERVENTION_OUTCOME = "intervention_outcome"
    #: The trusted runtime reported a record about Person's own situation that
    #: is not a sense: its placement ledger, its permissions, its affordances.
    RUNTIME_REPORT = "runtime_report"
    #: Person brought a memory back to mind. Not a new encounter with the world.
    MEMORY_RECALL = "memory_recall"
    #: Someone told Person. No channel exists.
    TESTIMONY = "testimony"
    #: Person read it in deliberate research. No channel exists (ADR 0004).
    RESEARCH = "research"
    #: Old records processed again. Never new lived experience.
    REPLAY = "replay"
    #: What would have happened had things been otherwise.
    COUNTERFACTUAL = "counterfactual"
    #: What a predictive model says will happen. Imagined, never lived.
    MODEL_ROLLOUT = "model_rollout"
    #: The operator acted on Person or its world (`PERSON_SPEC` section 51.1).
    OPERATOR_INTERVENTION = "operator_intervention"
    #: Person concluded it from what it already held.
    INFERENCE = "inference"
    #: What Person started with: its skill contracts and vocabularies.
    INITIAL_KNOWLEDGE = "initial_knowledge"


#: Classes that are Person's own lived experience, and so may be remembered.
LIVED: frozenset[Source] = frozenset({Source.REAL_OBSERVATION, Source.INTERVENTION_OUTCOME})

#: Classes admissible as evidence about the current state of the world Person
#: is living in. A runtime report is admissible because it is the trusted
#: record of Person's own works, never a sense of anything else.
WORLD_EVIDENCE: frozenset[Source] = LIVED | {Source.RUNTIME_REPORT}

#: Classes that are claims by someone else. Admissible later only as testimony,
#: weighed as such; never as observation.
REPORTED: frozenset[Source] = frozenset(
    {Source.TESTIMONY, Source.RESEARCH, Source.OPERATOR_INTERVENTION}
)

#: Classes that can never become new evidence about the world, whatever they say.
NEVER_EVIDENCE: frozenset[Source] = frozenset(
    {
        Source.MEMORY_RECALL,
        Source.REPLAY,
        Source.COUNTERFACTUAL,
        Source.MODEL_ROLLOUT,
        Source.INFERENCE,
        Source.INITIAL_KNOWLEDGE,
    }
)

#: Imagined material. It never becomes an episode, evidence or a lived fact.
IMAGINED: frozenset[Source] = frozenset({Source.COUNTERFACTUAL, Source.MODEL_ROLLOUT})

assert WORLD_EVIDENCE.isdisjoint(NEVER_EVIDENCE)
assert REPORTED.isdisjoint(NEVER_EVIDENCE)
assert set(Source) == WORLD_EVIDENCE | REPORTED | NEVER_EVIDENCE


def is_lived(source: Source | str) -> bool:
    return Source(source) in LIVED


def is_world_evidence(source: Source | str) -> bool:
    return Source(source) in WORLD_EVIDENCE
