"""Minecraft decision states from single observations: for offline tools and tests.

The loop never uses this module. It builds a `DecisionState` the way the loop
does, but from one observation with no history: beliefs revised from that
observation's reports alone, home only as the caller says, no memory. The
validation harness's effect comparison and the test suites use it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from person_cognition.interoception import BodyReading
from person_epistemics import BeliefState, DecisionState, Knowledge, SelfState
from person_policy import EnvelopeVerdict
from person_skills import skill_registry

from . import body, facts
from .beliefs import belief_evidence
from .envelope import safe_envelope
from .perception import MinecraftPercepts, perceive

Decision = DecisionState[MinecraftPercepts, BodyReading]


def snapshot_decision(
    observation: Mapping[str, Any],
    *,
    home: str = "unknown",
    recalled: Sequence[Any] = (),
) -> Decision:
    """A decision state from one observation alone, for offline tools and tests.

    Beliefs are revised from that observation's reports and nothing else, so
    the result is what Person would decide from a standing start: no memory,
    no earlier beliefs, home only as `home` says. The validation harness's
    effect comparison and the test suites use it; the loop never does.
    """
    state = perceive(observation)
    beliefs = BeliefState()
    for revision in beliefs.revise(belief_evidence(state, 0)):
        beliefs.admit_revision(revision)
    registry = skill_registry("minecraft")
    return DecisionState(
        percepts=state,
        beliefs=beliefs.view(state.situation),
        self_state=SelfState(
            body=body.body_reading(state.percepts),
            life="alive",
            world_available=None,
            place=None,
            home_relation=home,
            affect=None,
            capabilities=tuple(registry.ids),
        ),
        knowledge=Knowledge(skills=registry, facts=registry.facts),
        recalled=tuple(recalled),
    )


def facts_from_observation(
    observation: Mapping[str, Any], *, home: str = "unknown"
) -> dict[str, float]:
    """The planning facts of `snapshot_decision`: for offline tools and tests."""
    return facts.planning_facts(snapshot_decision(observation, home=home))


def envelope_of(observation: Mapping[str, Any], *, home: str = "unknown") -> EnvelopeVerdict:
    return safe_envelope(snapshot_decision(observation, home=home))


def threat_of(observation: Mapping[str, Any]) -> float:
    return body.threat_intensity(perceive(observation).percepts)


def body_of(observation: Mapping[str, Any]) -> BodyReading:
    return body.body_reading(perceive(observation).percepts)


def percepts_of(observation: Mapping[str, Any]) -> MinecraftPercepts:
    return perceive(observation).percepts
