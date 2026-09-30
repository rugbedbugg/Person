"""Death, respawn and termination (ADR 0017, I3). Synthetic identities only.

Life status is its own axis: alive, awaiting a respawn (engineering-facing),
or terminated. Death comes only from the trusted runtime; a terminal death is
terminal by itself, so a crash cannot undo it; nothing privileged reaches
Person; and a respawned body is the body as it is now, not a recovery.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from person_persistence import EvidenceJournal, IdentityError
from test_identity_continuity import PERSON, Process, envelope, journal, legacy_root
from test_operational_state import world
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


def life(process: Process, event: str, *, terminal: bool = False, tick: int = 0) -> None:
    process.loop.handle(
        {
            **envelope("LifeEvent", person=process.person, at=T0, tick=tick),
            "event": event,
            "terminal": terminal,
            "reasonCodes": ["body_died" if event == "died" else "body_respawned"],
        }
    )


def observe(process: Process, document: dict[str, Any], tick: int, **vitals: float) -> None:
    observation = at(document, tick)
    observation["personId"] = process.person
    observation["vitals"].update(vitals)
    process.loop.handle(observation)


def types(evidence: Path) -> list[str]:
    return [e.type for e in journal(evidence)]


def alive_person(tmp_path: Path, view: dict[str, Any]) -> Process:
    process = Process(tmp_path)
    process.hello(T0)
    world(process, "available", T0)
    observe(process, view, 100, health=6.0, food=6.0)
    observe(process, view, 140, health=4.0, food=4.0)
    return process


# ----------------------------------------------------------------- respawn


def test_respawn_keeps_the_same_person_memory_time_and_projects(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = alive_person(tmp_path, view)
    memories = len(process.loop.memory_store)
    lived = process.loop.memory.now
    projects = [p.to_json() for p in process.loop.project_book.projects()]

    life(process, "died", tick=140)
    assert process.loop.life.status == "awaiting_respawn"
    life(process, "respawned", tick=900)
    assert process.loop.life.status == "alive"

    assert process.loop.self_knowledge.person_id == PERSON
    assert types(tmp_path).count("person_founded") == 1, "no new Person"
    assert len(process.loop.memory_store) == memories + 1, "memory kept, and the death added"
    assert process.loop.memory.now == lived, "experienced time does not reset"
    assert [p.to_json() for p in process.loop.project_book.projects()] == projects


def test_the_first_observation_after_respawn_invents_no_recovery_or_movement(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = alive_person(tmp_path, view)
    life(process, "died", tick=140)
    life(process, "respawned", tick=900)
    before = len(journal(tmp_path))
    lived = process.loop.memory.now
    observe(process, view, 900, health=20.0, food=20.0)
    fresh = journal(tmp_path)[before:]
    felt = [e.payload["trigger"] for e in fresh if e.type == "affect_appraised"]
    # Dying hungry and waking fed would read as hunger relieved, and any
    # comparison with the dead body as a transition: none may be felt.
    assert not {"harm", "hunger_relieved", "breath_recovered"} & set(felt), felt
    assert not [e for e in fresh if e.type == "memory_encoded" and e.payload["kind"] == "hurt"]
    assert process.loop.memory.now == lived, "the time dead was not experienced"
    observe(process, view, 920, health=20.0)
    assert process.loop.memory.now == lived + 20


def test_the_death_is_one_salient_memory_of_what_person_knew(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = alive_person(tmp_path, view)
    life(process, "died", tick=140)
    died = [
        e for e in journal(tmp_path) if e.type == "memory_encoded" and e.payload["kind"] == "died"
    ]
    assert len(died) == 1
    payload = died[0].payload
    assert payload["salience"] == 1.0
    assert set(payload["details"]) == {
        "outcome",
        "health_before",
        "food_before",
        "threat_in_view",
        "goal",
        "project",
    }
    assert payload["details"]["health_before"] == 4.0 and payload["details"]["outcome"] == "died"


def test_nothing_privileged_about_the_death_reaches_person(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = alive_person(tmp_path, view)
    life(process, "died", tick=140)
    record = next(e for e in journal(tmp_path) if e.type == "person_died")
    assert set(record.payload) == {"terminal", "experienced_tick", "affect"}
    said = json.dumps(
        [e.payload for e in journal(tmp_path) if e.type in {"person_died", "memory_encoded"}]
    )
    for forbidden in ('"x"', '"position"', "inventory", "cause", "entity", "coordinates"):
        assert forbidden not in said, forbidden
    assert "affect" not in json.dumps(
        [e.payload for e in journal(tmp_path) if e.type == "memory_encoded"]
    ), "affect never touches memory (ADR 0010)"


def test_a_repeated_death_or_respawn_changes_nothing(tmp_path: Path, view: dict[str, Any]) -> None:
    process = alive_person(tmp_path, view)
    life(process, "died", tick=140)
    life(process, "died", tick=141)
    life(process, "respawned", tick=900)
    life(process, "respawned", tick=901)
    assert types(tmp_path).count("person_died") == 1
    assert types(tmp_path).count("person_respawned") == 1
    assert process.loop.life.deaths == 1 and process.loop.life.respawns == 1


def test_a_crash_before_the_respawn_resumes_the_same_person_awaiting_it(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = alive_person(tmp_path, view)
    life(process, "died", tick=140)
    # The process dies here, before any respawn.
    again = Process(tmp_path)
    ready = again.hello("2026-09-30T09:00:00Z")
    assert ready["lifeStatus"] == "awaiting_respawn"
    assert again.loop.life.status == "awaiting_respawn"
    assert again.loop.self_knowledge.person_id == PERSON
    life(again, "respawned", tick=1000)
    assert again.loop.life.status == "alive"


# -------------------------------------------------------------- permadeath


def test_permadeath_is_irreversible_and_no_configuration_resurrects(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = alive_person(tmp_path, view)
    life(process, "died", terminal=True, tick=140)
    assert process.loop.life.status == "terminated"
    died = next(e for e in journal(tmp_path) if e.type == "person_died")
    assert died.payload["terminal"] is True
    assert "person_terminated" in types(tmp_path)
    life(process, "respawned", tick=900)
    assert process.loop.life.status == "terminated", "a terminated Person never comes back"
    # Whatever the runtime is configured with now, startup refuses.
    with pytest.raises(IdentityError, match="terminated"):
        Process(tmp_path).hello("2026-09-30T09:00:00Z")


def test_a_crash_right_after_a_terminal_death_still_reconstructs_termination(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = alive_person(tmp_path, view)
    life(process, "died", terminal=True, tick=140)
    # Simulate the crash: the terminal death was written, nothing after it.
    journal_ = EvidenceJournal(tmp_path / "journal")
    events = list(journal_.read())
    cut = next(i for i, e in enumerate(events) if e.type == "person_died") + 1
    segment = sorted((tmp_path / "journal").glob("*.jsonl"))[-1]
    lines = segment.read_text(encoding="utf-8").splitlines(keepends=True)
    keep = len(lines) - (len(events) - cut)
    segment.write_text("".join(lines[:keep]), encoding="utf-8")
    for snapshot in (tmp_path / "snapshots").glob("*.json"):
        snapshot.unlink()
    assert types(tmp_path)[-1] == "person_died"
    with pytest.raises(IdentityError, match="terminated"):
        Process(tmp_path).hello("2026-09-30T09:00:00Z")


def test_cognition_cannot_end_itself_or_die_by_its_own_conclusion() -> None:
    source = (REPOSITORY / "apps/cognition/python/person_cognition/loop.py").read_text(
        encoding="utf-8"
    )
    # Death and termination are recorded only in the handler for the
    # runtime's LifeEvent.
    handler = source[source.index("def on_life_event") : source.index("def _death_memory")]
    elsewhere = source.replace(handler, "")
    for record in ('"person_died"', '"person_terminated"', '"person_respawned"'):
        assert record in handler and record not in elsewhere


# ------------------------------------------------- separate axes, legacy


def test_world_availability_and_life_status_stay_separate(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = alive_person(tmp_path, view)
    world(process, "unavailable", T0, tick=140)
    life(process, "died", tick=140)
    assert process.loop.operational.world == "unavailable"
    assert process.loop.life.status == "awaiting_respawn"
    world(process, "available", T0, tick=500)
    assert process.loop.life.status == "awaiting_respawn", "the world coming back is no respawn"
    life(process, "respawned", tick=500)
    world(process, "unavailable", T0, tick=600)
    assert process.loop.life.status == "alive", "losing the world is no death"


def test_a_legacy_store_still_reads_and_records_a_real_death(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    legacy_root(tmp_path, person="ada")
    process = Process(tmp_path, person="ada")
    process.hello(T0)
    observe(process, view, 100)
    life(process, "died", tick=100)
    new = types(tmp_path)
    assert new[0] == "episode_started" and "person_founded" not in new
    assert "session_started" not in new, "still no session history"
    assert "person_died" in new, "a death is real new history, not silent"
