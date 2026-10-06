"""A Person's identity and the continuity of its sessions (ADR 0017, I1).

Synthetic identities only: no test creates the canonical Person-000.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from person_cognition.continuity import found
from person_cognition.loop import CognitionLoop
from person_config import CognitionSettings
from person_epistemics import ExperienceKey
from person_persistence import EventJournal, IdentityError, SelfKnowledge, new_event
from person_protocol import PROTOCOL_VERSION, decode_frame
from person_skills import skill_registry

PERSON = "test-person-000"


def envelope(kind: str, *, person: str, at: str, tick: int = 0) -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "messageId": str(uuid.uuid4()),
        "personId": person,
        "sessionId": str(uuid.uuid4()),
        "worldId": "test-world",
        "tick": tick,
        "timestamp": at,
        "type": kind,
    }


class Process:
    """One cognition process: a session from hello to (maybe) a clean end."""

    def __init__(self, evidence: Path, person: str = PERSON) -> None:
        self.sent: list[dict[str, Any]] = []
        self.evidence = evidence
        self.person = person
        self.loop = CognitionLoop(
            evidence_directory=evidence,
            write=lambda line: self.sent.append(decode_frame(line.rstrip("\n"))),
            log=lambda line: None,
        )

    def hello(self, at: str) -> dict[str, Any]:
        self.loop.handle(
            {
                **envelope("SessionHello", person=self.person, at=at),
                "learningMode": "off",
                "experience": {
                    "context": "lived",
                    "environmentKind": "minecraft",
                    "embodimentKind": "fixture",
                    "environmentVariant": None,
                },
                "policyRevision": 0,
                "skillLibraryRevision": skill_registry().revision,
                "rngSeed": 7,
                "evidenceDirectory": str(self.evidence),
                "skillIds": skill_registry().ids,
            }
        )
        return next(m for m in reversed(self.sent) if m["type"] == "CognitionReady")

    def end_cleanly(self, at: str) -> None:
        self.loop.handle(
            {
                **envelope("EpisodeEvent", person=self.person, at=at, tick=10),
                "episodeId": "ep",
                "phase": "ended",
                "experience": {
                    "context": "lived",
                    "environmentKind": "minecraft",
                    "embodimentKind": "fixture",
                    "environmentVariant": None,
                },
                "rngSeed": 7,
                "reasonCodes": ["done"],
            }
        )


def journal(evidence: Path) -> list[Any]:
    return list(EventJournal(evidence / "journal").read())


# ------------------------------------------------------------ a new Person


def test_a_new_root_begins_with_its_founding_then_its_first_session(tmp_path: Path) -> None:
    process = Process(tmp_path)
    ready = process.hello("2026-09-30T08:00:00Z")
    events = journal(tmp_path)
    assert [e.type for e in events] == ["person_founded", "session_started"]
    assert events[0].payload["person_id"] == PERSON
    assert events[0].payload["founded_at"] == "2026-09-30T08:00:00Z"
    assert events[1].payload["gap"] is None, "a first session has no gap to learn"
    assert events[1].payload["previous_session_id"] is None
    assert ready["restoredEvents"] == 0, "its own founding is not restored history"
    known = process.loop.self_knowledge
    assert known is not None and known.person_id == PERSON and known.last_gap is None


def test_a_restart_learns_the_gap_and_how_the_last_session_ended(tmp_path: Path) -> None:
    first = Process(tmp_path)
    first.hello("2026-09-30T08:00:00Z")
    first.end_cleanly("2026-09-30T08:05:00Z")
    before = journal(tmp_path)
    assert before[-1].type == "session_ended"
    now_before = first.loop.memory.now
    memories_before = len(first.loop.memory_store)

    second = Process(tmp_path)
    second.hello("2026-09-30T11:05:00Z")
    started = journal(tmp_path)[-1]
    assert started.type == "session_started"
    assert started.payload["gap"] == "hours"
    assert started.payload["previous_ended_cleanly"] is True
    assert started.payload["previous_session_id"] == before[1].payload["session_id"]
    # Learned, not remembered: no experienced time and no memory for the gap.
    assert second.loop.memory.now == now_before
    assert len(second.loop.memory_store) == memories_before
    assert second.loop.self_knowledge.last_gap == "hours"


def test_after_a_crash_nothing_is_invented_and_the_next_start_says_so(tmp_path: Path) -> None:
    crashed = Process(tmp_path)
    crashed.hello("2026-09-30T08:00:00Z")  # never ends: the process died
    Process(tmp_path).hello("2026-10-02T08:00:00Z")
    events = journal(tmp_path)
    assert "session_ended" not in [e.type for e in events]
    assert events[-1].payload["previous_ended_cleanly"] is False
    assert events[-1].payload["gap"] == "days"


def test_a_clock_that_went_backwards_is_unknown_not_continuous(tmp_path: Path) -> None:
    Process(tmp_path).hello("2026-09-30T08:00:00Z")
    Process(tmp_path).hello("2026-09-29T08:00:00Z")
    assert journal(tmp_path)[-1].payload["gap"] == "unknown"


# --------------------------------------------------------------- binding


def test_a_root_opens_only_as_its_own_person(tmp_path: Path) -> None:
    Process(tmp_path).hello("2026-09-30T08:00:00Z")
    with pytest.raises(IdentityError):
        Process(tmp_path, person="test-person-001").hello("2026-09-30T09:00:00Z")


def test_ordinary_startup_never_founds_a_canonical_person(tmp_path: Path) -> None:
    with pytest.raises(IdentityError):
        Process(tmp_path, person="person-999").hello("2026-09-30T08:00:00Z")
    assert journal(tmp_path) == [] if (tmp_path / "journal").exists() else True


def test_even_a_fully_configured_canonical_person_is_not_founded_by_startup(
    tmp_path: Path,
) -> None:
    # Name and designation configured: only the founding command may use them.
    settings = CognitionSettings(
        person_id="person-999",
        world_id="test-world",
        learning_mode="off",
        evidence_directory=tmp_path,
        output_directory=tmp_path,
        snapshot_every_events=50,
        exploration_bonus=0.15,
        minimum_support=3,
        rng_seed=7,
        identity_name="Probe",
        identity_designation="Person-999",
    )
    process = Process(tmp_path, person="person-999")
    process.loop.settings = settings
    with pytest.raises(IdentityError, match="founding command"):
        process.hello("2026-09-30T08:00:00Z")
    assert (
        not list((tmp_path / "journal").glob("*.jsonl"))
        if (tmp_path / "journal").exists()
        else True
    )


def test_the_founding_command_founds_once_and_startup_then_resumes(tmp_path: Path) -> None:
    # A canonical-form serial no real Person has; never person-000.
    made = found(
        evidence_directory=tmp_path,
        person_id="person-999",
        world_id="test-world",
        name="Probe",
        designation="Person-999",
        environment_kind="minecraft",
        embodiment_kind="fixture",
        now="2026-09-30T07:00:00Z",
    )
    assert made.designation == "Person-999"
    with pytest.raises(IdentityError):
        found(
            evidence_directory=tmp_path,
            person_id="person-999",
            world_id="test-world",
            name="Probe",
            designation="Person-999",
            environment_kind="minecraft",
            embodiment_kind="fixture",
        )
    process = Process(tmp_path, person="person-999")
    process.hello("2026-09-30T08:00:00Z")
    assert [e.type for e in journal(tmp_path)] == ["person_founded", "session_started"]
    assert process.loop.self_knowledge.designation == "Person-999"
    assert journal(tmp_path)[-1].payload["gap"] == "hours"


def test_a_canonical_founding_needs_a_name_and_a_designation(tmp_path: Path) -> None:
    with pytest.raises(IdentityError):
        found(
            evidence_directory=tmp_path,
            person_id="person-999",
            world_id="test-world",
            name=None,
            designation=None,
            environment_kind="minecraft",
            embodiment_kind="fixture",
        )


# ----------------------------------------------------------------- legacy


def legacy_root(evidence: Path, person: str = "ada") -> None:
    journal_ = EventJournal(evidence / "journal")
    journal_.append(
        new_event(
            person_id=person,
            world_id="test-world",
            session_id=str(uuid.uuid4()),
            episode_id="old",
            decision_id=None,
            tick=0,
            policy_revision=0,
            experience=ExperienceKey("minecraft", "fixture"),
            event_type="episode_started",
            payload={},
            previous_event_id=None,
        )
    )


def test_a_legacy_root_is_read_and_resumed_but_never_given_a_founding(tmp_path: Path) -> None:
    legacy_root(tmp_path)
    process = Process(tmp_path, person="ada")
    process.hello("2026-09-30T08:00:00Z")
    types = [e.type for e in journal(tmp_path)]
    assert types[0] == "episode_started" and "person_founded" not in types
    assert process.loop.continuity.legacy
    assert process.loop.self_knowledge.name is None
    with pytest.raises(IdentityError):
        found(
            evidence_directory=tmp_path,
            person_id="ada",
            world_id="test-world",
            name="Ada",
            designation=None,
            environment_kind="minecraft",
            embodiment_kind="fixture",
        )


def test_a_legacy_root_opens_only_as_the_person_who_wrote_it(tmp_path: Path) -> None:
    legacy_root(tmp_path, person="ada")
    with pytest.raises(IdentityError):
        Process(tmp_path, person="test-person-000").hello("2026-09-30T08:00:00Z")


# ---------------------------------------------------------------- firewall


def test_cognition_receives_a_bounded_projection_not_the_record(tmp_path: Path) -> None:
    process = Process(tmp_path)
    process.hello("2026-09-30T08:00:00Z")
    fields = {field.name for field in dataclasses.fields(SelfKnowledge)}
    assert fields == {
        "person_id",
        "name",
        "designation",
        "founded_at",
        "last_gap",
        "previous_ended_cleanly",
    }
    said = json.dumps(dataclasses.asdict(process.loop.self_knowledge))
    assert "event_id" not in said and "timestamp" not in said
    assert "started_at" not in said, "no raw session times reach cognition"
