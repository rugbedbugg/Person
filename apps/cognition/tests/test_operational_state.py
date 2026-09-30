"""Operational state: the world's availability, across sessions (ADR 0017, I2).

Adversarial cases, each with a synthetic identity. Losing the world is a
state, not the end of Person; suspension is known only afterwards; time
without the world is external time, never experienced; nothing is invented.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
from person_persistence import EvidenceJournal
from test_identity_continuity import PERSON, Process, envelope, journal, legacy_root
from test_spatial import STILL, at

REPOSITORY = Path(__file__).resolve().parents[3]

T0 = "2026-09-30T08:00:00Z"


@pytest.fixture
def view() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["vitals"].update({"health": 20.0, "food": 20.0, "breath": 10})
    for key in ("resources", "passiveAnimals", "hostiles", "players", "containers", "hazards"):
        document["nearby"][key] = []
    document["selfMotion"] = dict(STILL)
    return document


def world(process: Process, state: str, at_: str, tick: int = 0) -> None:
    process.loop.handle(
        {
            **envelope("WorldAvailability", person=process.person, at=at_, tick=tick),
            "state": state,
            "reasonCodes": ["connected" if state == "available" else "connection_lost"],
        }
    )


def observe(process: Process, document: dict[str, Any], tick: int, **vitals: float) -> None:
    observation = at(document, tick)
    observation["personId"] = process.person
    observation["vitals"].update(vitals)
    process.loop.handle(observation)


def lifecycle(evidence: Path) -> list[tuple[str, Any]]:
    kinds = {"session_started", "session_ended", "world_availability_changed", "person_founded"}
    return [
        (e.type, e.payload.get("state") or e.payload.get("suspension"))
        for e in journal(evidence)
        if e.type in kinds
    ]


# ------------------------------------------------------ sessions and suspension


def test_crash_while_embodied_is_a_suspension_after_a_crash_with_nothing_invented(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    first = Process(tmp_path)
    first.hello(T0)
    world(first, "available", T0)
    observe(first, view, 100)
    # The process dies here: no session_ended, no world_unavailable.
    second = Process(tmp_path)
    second.hello("2026-09-30T09:00:00Z")
    types = [e.type for e in journal(tmp_path)]
    assert types.count("session_ended") == 0
    assert types.count("world_availability_changed") == 1, "no absence was invented"
    started = journal(tmp_path)[-1].payload
    assert started["suspension"] == {"after": "crash", "world_at_end": "available"}
    assert started["previous_ended_cleanly"] is False


def test_clean_shutdown_while_embodied_is_a_suspension_after_a_clean_end(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    first = Process(tmp_path)
    first.hello(T0)
    world(first, "available", T0)
    observe(first, view, 100)
    first.end_cleanly("2026-09-30T08:10:00Z")
    second = Process(tmp_path)
    second.hello("2026-09-30T08:30:00Z")
    started = journal(tmp_path)[-1].payload
    assert started["suspension"] == {"after": "clean_end", "world_at_end": "available"}
    assert started["gap"] == "minutes"


def test_a_first_session_has_no_suspension_before_it(tmp_path: Path) -> None:
    Process(tmp_path).hello(T0)
    assert journal(tmp_path)[-1].payload["suspension"] is None


# ------------------------------------------------------- the world goes away


def test_minecraft_disappearing_while_cognition_lives_is_a_state_not_an_end(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = Process(tmp_path)
    process.hello(T0)
    world(process, "available", T0)
    observe(process, view, 100, health=20.0)
    observe(process, view, 140, health=20.0)
    lived = process.loop.memory.now
    harm_before = sum(
        1
        for e in journal(tmp_path)
        if e.type == "affect_appraised" and e.payload["trigger"] == "harm"
    )

    world(process, "unavailable", "2026-09-30T08:01:00Z", tick=140)
    assert process.loop.operational.world == "unavailable"
    assert process.loop.running, "cognition lives on without the world"

    # The world comes back far later, and the body was hurt meanwhile.
    world(process, "available", "2026-09-30T09:00:00Z", tick=50_000)
    observe(process, view, 50_000, health=12.0)
    assert process.loop.memory.now == lived, "the absence was not experienced"
    harm_after = sum(
        1
        for e in journal(tmp_path)
        if e.type == "affect_appraised" and e.payload["trigger"] == "harm"
    )
    assert harm_after == harm_before, "no harm event invented across the absence"
    observe(process, view, 50_040, health=12.0)
    assert process.loop.memory.now == lived + 40, "experience resumes with the world"
    # Reconnection is not rebirth: one founding, one session, same identity.
    types = [e.type for e in journal(tmp_path)]
    assert types.count("person_founded") == 1 and types.count("session_started") == 1
    assert process.loop.self_knowledge.person_id == PERSON


def test_restart_after_a_long_world_absence(tmp_path: Path, view: dict[str, Any]) -> None:
    first = Process(tmp_path)
    first.hello(T0)
    world(first, "available", T0)
    observe(first, view, 100)
    lived = first.loop.memory.now
    world(first, "unavailable", "2026-09-30T08:05:00Z", tick=100)
    first.end_cleanly("2026-09-30T08:06:00Z")
    assert journal(tmp_path)[-1].payload["reasons"] == ["done"]

    second = Process(tmp_path)
    second.hello("2026-10-10T08:00:00Z")
    started = journal(tmp_path)[-1].payload
    assert started["gap"] == "longer"
    assert started["suspension"] == {"after": "clean_end", "world_at_end": "unavailable"}
    assert second.loop.memory.now == lived, "ten days away is not ten days lived"
    assert second.loop.operational.world is None, "unknown until the runtime says"


def test_repeated_connect_and_disconnect_cycles_record_only_real_changes(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = Process(tmp_path)
    process.hello(T0)
    tick = 100
    lived_spans = 0
    for _cycle in range(3):
        world(process, "available", T0, tick=tick)
        world(process, "available", T0, tick=tick)  # a repeat changes nothing
        observe(process, view, tick)
        observe(process, view, tick + 20)
        lived_spans += 20
        world(process, "unavailable", T0, tick=tick + 20)
        world(process, "unavailable", T0, tick=tick + 20)
        tick += 10_000  # the world ran on without Person
    changes = [
        e.payload["state"] for e in journal(tmp_path) if e.type == "world_availability_changed"
    ]
    assert changes == ["available", "unavailable"] * 3
    assert process.loop.memory.now == lived_spans


# ----------------------------------------------------------------- legacy


def test_a_legacy_store_acquires_no_lifecycle_history(tmp_path: Path, view: dict[str, Any]) -> None:
    legacy_root(tmp_path, person="ada")
    before = [e.type for e in journal(tmp_path)]
    process = Process(tmp_path, person="ada")
    process.hello(T0)
    world(process, "available", T0)
    world(process, "unavailable", T0, tick=5)
    process.end_cleanly("2026-09-30T08:10:00Z")
    after = [e.type for e in journal(tmp_path)]
    new = after[len(before) :]
    lifecycle_types = {
        "person_founded",
        "session_started",
        "session_ended",
        "world_availability_changed",
    }
    assert not lifecycle_types & set(new), new
    assert process.loop.operational.world == "unavailable", "still known in memory"


# ---------------------------------------------------------------- firewall


def test_person_knows_only_whether_the_world_is_available(tmp_path: Path) -> None:
    process = Process(tmp_path)
    process.hello(T0)
    world(process, "unavailable", T0)
    assert dataclasses.asdict(process.loop.operational) == {"world": "unavailable"}


def test_the_evidence_stays_a_valid_chain(tmp_path: Path, view: dict[str, Any]) -> None:
    process = Process(tmp_path)
    process.hello(T0)
    world(process, "available", T0)
    world(process, "unavailable", T0, tick=3)
    events = list(EvidenceJournal(tmp_path / "journal").read())
    for before, after in zip(events, events[1:], strict=False):
        assert after.previous_event_id == before.event_id


@pytest.mark.parametrize("state", ["available", "unavailable"])
def test_world_state_is_journalled_with_its_reason(tmp_path: Path, state: str) -> None:
    process = Process(tmp_path)
    process.hello(T0)
    world(process, state, T0)
    last = journal(tmp_path)[-1]
    assert last.type == "world_availability_changed"
    assert last.payload["state"] == state and last.payload["reasons"]
