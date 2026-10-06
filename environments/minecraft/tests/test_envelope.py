"""Whether Person can afford to explore, judged by Minecraft from the decision state."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_minecraft.envelope import safe_envelope
from person_minecraft.offline import snapshot_decision

REPOSITORY = Path(__file__).resolve().parents[3]


@pytest.fixture
def observation() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["payload"]["vitals"]["health"] = 20
    document["payload"]["vitals"]["food"] = 20
    return document


def verdict(observation: dict[str, Any], home: str = "unknown") -> Any:
    return safe_envelope(snapshot_decision(observation, home=home))


def test_a_nearby_hostile_closes_the_envelope(observation: dict[str, Any]) -> None:
    dangerous = deepcopy(observation)
    dangerous["payload"]["nearby"]["hostiles"] = [
        {
            "name": "zombie",
            "distance": 2.0,
            "bearing": "ahead",
            "elevation": "level",
            "rangeBand": "reach",
            "detail": "central",
            "named": False,
            "tamed": False,
            "protectedTarget": True,
        }
    ]
    closed = verdict(dangerous)
    assert not closed
    assert "hostile_nearby" in closed.reasons


def test_the_envelope_closes_in_darkness_without_shelter(observation: dict[str, Any]) -> None:
    night = deepcopy(observation)
    night["payload"]["environment"]["dayPhase"] = "night"
    night["payload"]["environment"]["lightLevel"] = 2
    assert "darkness_without_shelter" in verdict(night).reasons
    night["payload"]["home"]["shelterState"] = "complete"
    # Sheltered means a shelter Person believes complete and Person believing
    # it is home (C8).
    assert "darkness_without_shelter" in verdict(night, home="near").reasons
    assert verdict(night, home="at_home")
