"""The epistemic boundary as the running loop holds it (ADR 0026, ADR 0027).

The architecture tests check the boundary statically. These drive a real
`CognitionLoop` and check what it does with an observation: what it believes
carries provenance, scope and evidence references and is journalled once per
change; what it remembers never stands in for what it perceives.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_persistence import EventJournal
from test_loop import REPOSITORY, Harness


@pytest.fixture
def observation() -> dict[str, Any]:
    corpus = REPOSITORY / "fixtures/protocol-corpus/valid/observation.json"
    document: dict[str, Any] = json.loads(corpus.read_text(encoding="utf-8"))
    return document


def belief_events(evidence: Path) -> list[dict[str, Any]]:
    return [
        dict(event.payload)
        for event in EventJournal(evidence / "journal").read()
        if event.type == "belief_revised"
    ]


def test_a_reported_belief_is_journalled_with_its_provenance_and_scope(
    tmp_path: Path, observation: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    harness.observe(observation)
    revised = belief_events(tmp_path)
    assert revised, "the runtime's reports become beliefs, through the journal"
    for belief in revised:
        assert belief["basis"] == "runtime_report"
        assert belief["evidence_refs"] == [observation["messageId"]]
        # Learned in this world, by this body: nothing here is general.
        assert belief["scope"]["level"] == "world"
        assert belief["scope"]["environment"] == "minecraft"
        assert belief["scope"]["world"] == observation["worldId"]

    # The same report again confirms; it does not revise.
    again = deepcopy(observation)
    again["messageId"] = "0b1c7a52-6f0e-4b8e-9d55-7f1e2a3c4d5e"
    again["tick"] += 20
    harness.observe(again)
    assert len(belief_events(tmp_path)) == len(revised)


def test_a_remembered_resource_is_not_a_perceived_one(
    tmp_path: Path, observation: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    seen = deepcopy(observation)
    seen["payload"]["nearby"]["resources"].append(
        {
            "kind": "coal",
            "name": "coal_ore",
            "distance": 6.0,
            "bearing": "left",
            "elevation": "level",
            "rangeBand": "near",
            "detail": "central",
            "harvestPermitted": True,
        }
    )
    harness.observe(seen)
    environment = harness.loop.environment
    assert environment is not None and harness.loop.decision is not None
    assert environment.planning_facts(harness.loop.decision)["reachable_coal"] == 1.0

    gone = deepcopy(observation)
    gone["messageId"] = "5d2e8f1a-0c3b-4e6d-8a7f-9b1c2d3e4f50"
    gone["tick"] += 20
    harness.observe(gone)
    # Person may well remember the coal; the planner is told only what is
    # perceived now (ADR 0003, ADR 0026).
    assert environment.planning_facts(harness.loop.decision)["reachable_coal"] == 0.0
