"""Looking for something: bounded, deliberate, and honest about what it found.

When a goal cannot be planned only because the evidence it needs is out of
view (`person_planner.evidence_needed`), Person looks for it. One glance is one
ordinary `look` skill through the ordinary dispatch path; what the glance
revealed comes back as an ordinary observation; the planner plans again from
that. The loop is:

    planner needs evidence
        -> choose a direction to look
        -> the runtime turns Person's head
        -> a new observation
        -> plan again: act, look again, or stop

What this module keeps between glances is what Person decided and why: which
goal the search serves, which evidence it wants, how many glances it allows
itself, the directions it has already chosen, and how far it has tilted its
own head. It keeps no angle, no position and no percept, so nothing seen during
a search outlives the observation it arrived in. It is not memory, and it ends
with the search.

A search that runs out of glances concludes "not found in this bounded
search". It never concludes that the thing is not there, and the goal it
served is reopened as soon as the evidence is actually seen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from person_planner import evidence_percepts

#: The fixed identifier of every search routine. Searching is not a strategy
#: the learner scores, so it never gets a content-derived routine identity.
SEARCH_ROUTINE_ID = "r_seek_evidence"

#: Glances one search may spend. Seven turns of the runtime's gaze step cover
#: the whole horizon; the eighth is room to turn towards a glimpse or level
#: the head. The number is cognition's and could be a trait one day.
LOOK_BUDGET = 8

#: How far Person can tilt its head, in gaze steps, as the runtime allows it.
#: Tracked so a sweep starts level; this is Person's sense of its own neck.
MAX_PITCH_STEPS = 2

#: What a search concludes when it runs out. Deliberately not "absent".
NOT_FOUND = "not_found_in_bounded_search"

#: The fewest glances a search spends at a place Person believes it already
#: searched fruitlessly: enough to notice that something changed. A parameter.
REVISIT_MIN_LOOKS = 2


def revisit_budget(confidence: float) -> int:
    """Glances for a search, given confidence that this place was searched before.

    Full budget with no such memory, shrinking linearly to the minimum as the
    belief that it is the same place approaches certainty, which it never
    reaches. The evidence justifies a shorter look, never no look.
    """
    confidence = max(0.0, min(1.0, confidence))
    return LOOK_BUDGET - round((LOOK_BUDGET - REVISIT_MIN_LOOKS) * confidence)


_LEFT = {"ahead_left", "left", "behind_left", "behind"}
_RIGHT = {"ahead_right", "right", "behind_right"}


def _toward(percept: dict[str, Any]) -> str:
    """The glance that would bring a glimpsed thing into central vision."""
    bearing = percept["bearing"]
    if bearing in _LEFT:
        return "left"
    if bearing in _RIGHT:
        return "right"
    # Straight ahead but not recognised: it is above or below the part of the
    # field Person can identify things in, or the head is tilted away from it.
    elevation = percept["elevation"]
    return "up" if elevation == "above" else "down" if elevation == "below" else "forward"


@dataclass
class InformationSearch:
    goal_id: str
    purpose: tuple[str, ...]
    budget: int = LOOK_BUDGET
    looks: list[str] = field(default_factory=list)
    pitch_steps: int = 0
    #: Memories recalled when the search began. Reported, not acted on.
    recalled: tuple[str, ...] = ()
    #: Whether one of them was an earlier search that found nothing.
    recalls_unfound: bool = False
    #: The cognitive place Person believed it searched from (ADR 0008).
    place: dict[str, Any] | None = None
    #: Confidence that this place was searched fruitlessly before.
    revisit: float = 0.0

    @property
    def remaining(self) -> int:
        return self.budget - len(self.looks)

    def leads(self, observation: dict[str, Any]) -> list[dict[str, Any]]:
        """Glimpses of what is sought: perceived, not yet recognised."""
        percepts = evidence_percepts(observation)
        glimpses = [
            percept
            for fact in self.purpose
            for percept in percepts.get(fact, [])
            if percept["detail"] == "peripheral"
        ]
        return sorted(glimpses, key=lambda percept: (percept["distance"], percept["bearing"]))

    def next_direction(self, observation: dict[str, Any]) -> str:
        """Where to look next, decided from the current observation alone.

        A glimpse of what is sought comes first, nearest first. Otherwise the
        search sweeps the horizon in one direction, levelling the head first
        if an earlier glance tilted it.
        """
        leads = self.leads(observation)
        if leads:
            return _toward(leads[0])
        return "forward" if self.pitch_steps != 0 else "left"

    def record(self, direction: str) -> None:
        self.looks.append(direction)
        if direction == "forward":
            self.pitch_steps = 0
        elif direction == "up":
            self.pitch_steps = min(MAX_PITCH_STEPS, self.pitch_steps + 1)
        elif direction == "down":
            self.pitch_steps = max(-MAX_PITCH_STEPS, self.pitch_steps - 1)

    def payload(self, phase: str, **extra: Any) -> dict[str, Any]:
        return {
            "phase": phase,
            "goal_id": self.goal_id,
            "purpose": list(self.purpose),
            "budget": self.budget,
            "looks": list(self.looks),
            "recalled": list(self.recalled),
            "place": self.place,
            "revisit": self.revisit,
            **extra,
        }
