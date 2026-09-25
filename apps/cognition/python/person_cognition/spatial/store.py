"""Person's spatial model: a reducer over its own records, and the loop's view of it.

`SpatialMap` is rebuilt after a restart from `place_formed` and
`place_visited` events and from the estimate `episode_ended` recorded, and
from nothing else in the journal. `Spatial` is what the cognition loop holds:
it integrates felt motion, says which place Person believes it is at, and
produces the payloads for forming or revisiting a place. It never reads a
coordinate, the placement ledger, or `homeDistance` (ADR 0008).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from person_persistence import EvidenceEvent

from .integration import Estimate, integrate, resumed
from .places import REASONS, Place, Whereabouts, recognise

#: Beyond this many blocks of believed distance, home is far. A parameter,
#: and a believed distance, never a measured one.
NEAR_HOME = 32.0

#: Person's relation to home, in the decision context's own words.
HOME_RELATIONS: frozenset[str] = frozenset({"at_home", "near", "far", "unknown"})

#: Coarse scene subjects that may make up a place's signature. Kinds, never
#: particular objects.
SIGNATURE_SUBJECTS: frozenset[str] = frozenset(
    {"wood", "stone", "coal", "plant_food", "animal", "container", "hazard"}
)


class SpatialMap:
    """Places, routes between them, and the last estimate Person recorded."""

    def __init__(self) -> None:
        self._places: dict[str, Place] = {}
        self.labels: dict[str, str] = {}
        self.routes: list[dict[str, Any]] = []
        self.estimate: Estimate | None = None

    def reset(self) -> None:
        self._places.clear()
        self.labels.clear()
        self.routes.clear()
        self.estimate = None

    def apply(self, event: EvidenceEvent) -> None:
        payload = event.payload
        if event.type == "place_formed":
            place = Place.from_json(payload["place"])
            self._places[place.place_id] = place
            self._settle(payload)
        elif event.type == "place_visited":
            self._settle(payload)
        elif event.type == "episode_ended" and "self_estimate" in payload:
            self.estimate = Estimate.from_json(payload["self_estimate"])

    def _settle(self, payload: Mapping[str, Any]) -> None:
        self.estimate = Estimate.from_json(payload["estimate"])
        if payload.get("label"):
            self.labels[str(payload["place_id"])] = str(payload["label"])
        if payload.get("route"):
            self.routes.append(dict(payload["route"]))

    def to_json(self) -> dict[str, Any]:
        return {
            "places": [place.to_json() for place in self._places.values()],
            "labels": dict(self.labels),
            "routes": list(self.routes),
            "estimate": self.estimate.to_json() if self.estimate else None,
        }

    def load_json(self, body: Mapping[str, Any]) -> None:
        self.reset()
        for record in body["places"]:
            place = Place.from_json(record)
            self._places[place.place_id] = place
        self.labels.update(body["labels"])
        self.routes.extend(body["routes"])
        if body["estimate"] is not None:
            self.estimate = Estimate.from_json(body["estimate"])

    def places(self) -> tuple[Place, ...]:
        return tuple(self._places.values())

    def __len__(self) -> int:
        return len(self._places)


class Spatial:
    """Person's sense of where it is, for the cognition loop."""

    def __init__(self, spatial_map: SpatialMap) -> None:
        self._map = spatial_map
        # Waking up: the last recorded estimate, believed less firmly, or a
        # fresh frame if Person has never recorded one.
        self.estimate = resumed(spatial_map.estimate) if spatial_map.estimate else Estimate()
        self._scene: tuple[str, ...] = ()
        self._last_place: str | None = None
        self._last_at: Estimate | None = None

    def feel(self, self_motion: Mapping[str, Any], scene: frozenset[str]) -> None:
        """Integrate one felt step, and remember what is in view here."""
        self.estimate = integrate(self.estimate, self_motion)
        self._scene = tuple(sorted(scene & SIGNATURE_SUBJECTS))

    def here(self) -> Whereabouts | None:
        """The place Person believes it is at, if it recognises one."""
        return recognise(self._map.places(), self.estimate, self._scene)

    def label_of(self, place_id: str) -> str | None:
        return self._map.labels.get(place_id)

    def home_relation(self) -> tuple[str, float]:
        """Where Person believes it is relative to home, and how firmly (C8).

        `at_home` when Person recognises a place it labelled home. `near` or
        `far` only when that holds whichever way the drift since forming home
        has gone; otherwise `unknown`, as it is when Person has no home place
        or is lost in a frame its home is not in. Derived only from Person's
        own estimate and uncertainty.
        """
        homes = [
            place
            for place in self._map.places()
            if self._map.labels.get(place.place_id) == "home" and place.frame == self.estimate.frame
        ]
        if not homes:
            return "unknown", 0.0
        here = self.here()
        if here is not None and self._map.labels.get(here.place_id) == "home":
            return "at_home", here.confidence
        nearest = min(homes, key=lambda place: self.estimate.distance_to(place.forward, place.left))
        believed = self.estimate.distance_to(nearest.forward, nearest.left)
        drift = max(0.0, self.estimate.uncertainty - nearest.uncertainty)
        if believed + drift <= NEAR_HOME:
            return "near", 1.0 - drift / NEAR_HOME
        if believed - drift > NEAR_HOME:
            return "far", min(1.0, (believed - drift) / believed)
        return "unknown", 0.0

    def settle(
        self, reason: str, experienced: int, label: str | None = None
    ) -> tuple[str, dict[str, Any]]:
        """The journal record for being somewhere that mattered.

        Revisiting a recognised place, or forming a new one. Either way the
        record carries the estimate, so a restart resumes from it, and the
        route from the last place Person settled at, if it can relate the two.
        """
        if reason not in REASONS:
            raise ValueError(f"unknown reason for a place {reason!r}")
        whereabouts = self.here()
        payload: dict[str, Any] = {"reason": reason, "estimate": self.estimate.to_json()}
        if label:
            payload["label"] = label
        if whereabouts is not None:
            kind = "place_visited"
            place_id = whereabouts.place_id
            payload.update(place_id=place_id, confidence=round(whereabouts.confidence, 3))
        else:
            kind = "place_formed"
            place_id = f"place_{len(self._map) + 1}"
            place = Place(
                place_id=place_id,
                frame=self.estimate.frame,
                forward=self.estimate.forward,
                left=self.estimate.left,
                uncertainty=self.estimate.uncertainty,
                reason=reason,
                formed_at=experienced,
                signature=self._scene,
            )
            payload.update(place_id=place_id, confidence=1.0, place=place.to_json())
        previous, at = self._last_place, self._last_at
        if (
            previous is not None
            and previous != place_id
            and at is not None
            and at.frame == self.estimate.frame
        ):
            payload["route"] = {
                "from": previous,
                "to": place_id,
                "forward": round(self.estimate.forward - at.forward, 3),
                "left": round(self.estimate.left - at.left, 3),
                "uncertainty": round(self.estimate.uncertainty - at.uncertainty, 3),
            }
        self._last_place, self._last_at = place_id, self.estimate
        return kind, payload
