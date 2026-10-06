"""Path integration: where Person thinks it is, from what it felt (ADR 0008).

Cognition keeps a position and a facing in a frame of its own. The frame's
origin is wherever Person began integrating and its first axis is the way
Person faced then; it has no relation to Minecraft's axes or origin, and
nothing here ever sees a coordinate. Each felt step moves the estimate and
widens its uncertainty, and nothing narrows it again: there is no correction
from hidden truth, so the estimate drifts the way a body's does.

Frame convention: `forward` is along the facing at the frame's origin, `left`
is ninety degrees anticlockwise from it, and `heading` counts eighths of a
turn to the left of that original facing.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

#: The eight felt directions, in eighths of a turn to the left of ahead.
SECTORS: Mapping[str, int] = {
    "ahead": 0,
    "ahead_left": 1,
    "left": 2,
    "behind_left": 3,
    "behind": 4,
    "behind_right": 5,
    "right": 6,
    "ahead_right": 7,
}

#: Felt rotations, in eighths of a turn, positive to the left.
ROTATIONS: Mapping[str, int] = {
    "none": 0,
    "slight_left": 1,
    "left": 2,
    "sharp_left": 3,
    "about_face": 4,
    "sharp_right": -3,
    "right": -2,
    "slight_right": -1,
}

#: Uncertainty added per block travelled: the distance estimate's grain and
#: half a direction sector. An implementation parameter.
TRANSLATION_ERROR = 0.4
#: Further uncertainty per block, per eighth of a turn of heading doubt.
HEADING_ERROR = 0.4
#: Eighths of heading doubt added by each felt turn, which is rounded.
TURN_ERROR = 0.5
#: Added on waking after a restart: Person cannot know it was not moved.
RESUME_UNCERTAINTY = 8.0
RESUME_HEADING_UNCERTAINTY = 1.0


@dataclass(frozen=True, slots=True)
class Estimate:
    """Where Person believes it is, in its own frame, and how sure it is."""

    forward: float = 0.0
    left: float = 0.0
    heading: int = 0
    #: Radius, in blocks, within which Person thinks it is.
    uncertainty: float = 0.0
    #: Eighths of a turn of doubt about its facing.
    heading_uncertainty: float = 0.0
    #: Which frame this is. A new one starts whenever Person is lost.
    frame: int = 1

    def distance_to(self, forward: float, left: float) -> float:
        return math.hypot(self.forward - forward, self.left - left)

    def to_json(self) -> dict[str, Any]:
        return {
            "forward": round(self.forward, 3),
            "left": round(self.left, 3),
            "heading": self.heading,
            "uncertainty": round(self.uncertainty, 3),
            "heading_uncertainty": round(self.heading_uncertainty, 3),
            "frame": self.frame,
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> Estimate:
        return cls(
            forward=float(body["forward"]),
            left=float(body["left"]),
            heading=int(body["heading"]),
            uncertainty=float(body["uncertainty"]),
            heading_uncertainty=float(body["heading_uncertainty"]),
            frame=int(body["frame"]),
        )


def integrate(estimate: Estimate, motion: Mapping[str, Any]) -> Estimate:
    """The estimate after one felt step."""
    continuity = motion["continuity"]
    if continuity == "start":
        # Nothing was felt: this is the first moment of a session.
        return estimate
    if continuity == "discontinuous":
        # The scene jumped and Person does not know how far. It is lost, and
        # starts again from nothing rather than pretend to know.
        return Estimate(frame=estimate.frame + 1)

    translation = motion["translation"]
    moved = float(translation["distance"] or 0.0)
    forward, left, uncertainty = estimate.forward, estimate.left, estimate.uncertainty
    if translation["band"] != "none" and moved > 0:
        # Felt relative to the facing at the previous observation, which is
        # the heading this estimate still holds.
        angle = (estimate.heading + SECTORS[translation["direction"]]) * math.pi / 4
        forward += moved * math.cos(angle)
        left += moved * math.sin(angle)
        uncertainty += moved * (TRANSLATION_ERROR + HEADING_ERROR * estimate.heading_uncertainty)

    turn = ROTATIONS[motion["rotation"]]
    heading_uncertainty = estimate.heading_uncertainty + (TURN_ERROR if turn else 0.0)
    return replace(
        estimate,
        forward=forward,
        left=left,
        heading=(estimate.heading + turn) % 8,
        uncertainty=uncertainty,
        heading_uncertainty=heading_uncertainty,
    )


def resumed(estimate: Estimate) -> Estimate:
    """The estimate on waking: the same place, believed less firmly."""
    return replace(
        estimate,
        uncertainty=estimate.uncertainty + RESUME_UNCERTAINTY,
        heading_uncertainty=estimate.heading_uncertainty + RESUME_HEADING_UNCERTAINTY,
    )
