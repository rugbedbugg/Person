"""Cognitive places: somewhere Person was, as Person understands it (ADR 0008).

A place is a record Person makes at a moment that mattered: it looked for
something there, did something there, built its shelter there. It holds the
estimated position and uncertainty at that moment, in Person's own frame, and
a coarse scene signature: which kinds of thing were in view. Its identifier is
a counter, so it says nothing about where the place is.

Recognition is a belief with a confidence, never a confirmation. Person is
probably at place P when its estimate falls within P's radius once the doubt
it has accumulated since forming P is allowed for; the more doubt, the less
confident, and a familiar-looking scene helps a little. A signature is a set of kinds, never
the identity of a particular object (C4).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .integration import Estimate

#: How far, in blocks, still counts as the same place. A parameter.
PLACE_RADIUS = 6.0
#: The least confidence that counts as recognising a place.
RECOGNITION_THRESHOLD = 0.3
#: How much a matching scene can add to confidence.
SIGNATURE_WEIGHT = 0.2
#: Recognition is never certain.
MAX_CONFIDENCE = 0.95

REASONS: frozenset[str] = frozenset({"search", "action", "shelter"})


@dataclass(frozen=True, slots=True)
class Place:
    place_id: str
    frame: int
    forward: float
    left: float
    #: Person's positional doubt when it formed the place.
    uncertainty: float
    reason: str
    formed_at: int
    signature: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "place_id": self.place_id,
            "frame": self.frame,
            "forward": round(self.forward, 3),
            "left": round(self.left, 3),
            "uncertainty": round(self.uncertainty, 3),
            "reason": self.reason,
            "formed_at": self.formed_at,
            "signature": list(self.signature),
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> Place:
        return cls(
            place_id=str(body["place_id"]),
            frame=int(body["frame"]),
            forward=float(body["forward"]),
            left=float(body["left"]),
            uncertainty=float(body["uncertainty"]),
            reason=str(body["reason"]),
            formed_at=int(body["formed_at"]),
            signature=tuple(str(item) for item in body["signature"]),
        )


@dataclass(frozen=True, slots=True)
class Whereabouts:
    """Which place Person believes it is at, and how strongly."""

    place_id: str
    confidence: float

    def to_json(self) -> dict[str, Any]:
        return {"place_id": self.place_id, "confidence": round(self.confidence, 3)}


def confidence(place: Place, estimate: Estimate, scene: Iterable[str]) -> float:
    """How strongly Person could believe it is at `place`. Zero if it cannot."""
    if place.frame != estimate.frame:
        # A place from before Person was lost is in a frame it cannot relate
        # to where it is now. Only landmarks could bridge that, later.
        return 0.0
    # Within one frame, error accumulates along a single path, so what can
    # separate Person from a place is the doubt it has gathered since forming
    # it, not the doubt it already had then and still has.
    drift = max(0.0, estimate.uncertainty - place.uncertainty)
    tolerance = PLACE_RADIUS + drift
    gap = estimate.distance_to(place.forward, place.left)
    if gap > tolerance:
        return 0.0
    closeness = 1.0 - gap / tolerance
    sharpness = PLACE_RADIUS / tolerance
    seen = set(scene)
    shared = set(place.signature)
    union = seen | shared
    likeness = len(seen & shared) / len(union) if union else 0.0
    return min(MAX_CONFIDENCE, closeness * sharpness + SIGNATURE_WEIGHT * likeness)


def recognise(
    places: Iterable[Place], estimate: Estimate, scene: Iterable[str]
) -> Whereabouts | None:
    scene = tuple(scene)
    best: Whereabouts | None = None
    for place in places:
        belief = confidence(place, estimate, scene)
        if belief >= RECOGNITION_THRESHOLD and (best is None or belief > best.confidence):
            best = Whereabouts(place.place_id, belief)
    return best
