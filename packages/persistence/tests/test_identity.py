"""Identity and continuity records (ADR 0017). Synthetic identities only."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from person_persistence import (
    ContinuityRecord,
    EvidenceEvent,
    EvidenceStore,
    Founding,
    IdentityError,
    RootLock,
    gap_category,
    is_canonical,
    new_event,
)


def event(kind: str, payload: dict, *, at: str, person: str = "test-person-000") -> EvidenceEvent:
    made = new_event(
        person_id=person,
        world_id="w",
        session_id="00000000-0000-4000-8000-000000000000",
        episode_id=None,
        decision_id=None,
        tick=0,
        policy_revision=0,
        training_context="fixture",
        event_type=kind,
        payload=payload,
        previous_event_id=None,
    )
    return EvidenceEvent.from_json({**made.to_json(), "timestamp": at})


def founding(person: str = "test-person-000") -> Founding:
    return Founding(
        person_id=person, name="Test", designation=None, founded_at="2026-09-30T00:00:00Z"
    )


# ------------------------------------------------------------------ the gap


@pytest.mark.parametrize(
    ("later", "category"),
    [
        ("2026-09-30T00:59:59Z", "minutes"),
        ("2026-09-30T01:00:00Z", "hours"),
        ("2026-09-30T23:59:59Z", "hours"),
        ("2026-10-01T00:00:00Z", "days"),
        ("2026-10-06T23:59:59Z", "days"),
        ("2026-10-07T00:00:00Z", "longer"),
    ],
)
def test_the_gap_is_a_coarse_category_with_fixed_bounds(later: str, category: str) -> None:
    assert gap_category("2026-09-30T00:00:00Z", later) == category


def test_no_earlier_event_means_no_gap_and_a_bad_clock_means_unknown() -> None:
    assert gap_category(None, "2026-09-30T00:00:00Z") is None
    assert gap_category("2026-09-30T00:00:00Z", "2026-09-29T00:00:00Z") == "unknown"
    assert gap_category("not a time", "2026-09-30T00:00:00Z") == "unknown"
    assert gap_category("", "2026-09-30T00:00:00Z") == "unknown", "missing, not absent"


# ------------------------------------------------------------ the record


def test_the_founding_is_recognised_only_as_the_first_event() -> None:
    record = ContinuityRecord()
    record.apply(event("person_founded", founding().payload(), at="2026-09-30T00:00:00Z"))
    assert record.founding == founding() and not record.legacy
    later = ContinuityRecord()
    later.apply(event("episode_started", {}, at="2026-09-30T00:00:00Z"))
    later.apply(event("person_founded", founding().payload(), at="2026-09-30T00:00:01Z"))
    assert later.founding is None and later.legacy
    assert later.violations, "a founding after any other event is a violation"


def test_sessions_pair_by_id_and_a_crash_leaves_no_end() -> None:
    record = ContinuityRecord()
    record.apply(event("session_started", {"session_id": "a"}, at="2026-09-30T00:00:00Z"))
    assert record.last_session == {
        "session_id": "a",
        "started_at": "2026-09-30T00:00:00Z",
        "ended": False,
    }
    record.apply(event("session_ended", {"session_id": "other"}, at="2026-09-30T00:00:01Z"))
    assert record.last_session["ended"] is False, "only its own end closes a session"
    record.apply(event("session_ended", {"session_id": "a"}, at="2026-09-30T00:00:02Z"))
    assert record.last_session["ended"] is True
    record.apply(event("session_started", {"session_id": "b"}, at="2026-09-30T01:00:00Z"))
    assert record.last_session["ended"] is False
    assert record.last_timestamp == "2026-09-30T01:00:00Z"


def test_the_record_survives_its_own_serialisation() -> None:
    record = ContinuityRecord()
    record.apply(event("person_founded", founding().payload(), at="2026-09-30T00:00:00Z"))
    record.apply(event("session_started", {"session_id": "a"}, at="2026-09-30T00:00:00Z"))
    copy = ContinuityRecord()
    copy.load_json(record.to_json())
    assert copy.to_json() == record.to_json()


def test_canonical_identifiers_are_person_and_three_digits() -> None:
    assert is_canonical("person-000") and is_canonical("person-123")
    for other in ("ada", "test-person-000", "person-0000", "person-00", "Person-000"):
        assert not is_canonical(other)


def test_a_founding_has_a_stable_fingerprint() -> None:
    assert founding().fingerprint() == founding().fingerprint()
    assert founding("test-person-001").fingerprint() != founding().fingerprint()


# --------------------------------------------------------------- binding


def test_a_snapshot_of_another_person_is_refused_before_it_is_loaded(tmp_path: Path) -> None:
    class Reducer:
        loaded = False

        def apply(self, event: EvidenceEvent) -> None: ...
        def to_json(self) -> dict:
            return {}

        def load_json(self, body: dict) -> None:
            Reducer.loaded = True

        def reset(self) -> None: ...

    store = EvidenceStore(tmp_path)
    store.identity = {"person_id": "test-person-a", "founding": "a"}
    store.append(event("episode_started", {}, at="2026-09-30T00:00:00Z"))
    store.write_snapshot(Reducer())
    other = EvidenceStore(tmp_path)
    other.identity = {"person_id": "test-person-b", "founding": "b"}
    with pytest.raises(IdentityError):
        other.restore(Reducer())
    assert not Reducer.loaded

    same = EvidenceStore(tmp_path)
    same.identity = {"person_id": "test-person-a", "founding": "a"}
    assert same.restore(Reducer()).from_snapshot is True


def test_a_legacy_snapshot_without_identity_still_loads_for_a_legacy_root(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    store.append(event("episode_started", {}, at="2026-09-30T00:00:00Z"))

    class Reducer:
        def apply(self, event: EvidenceEvent) -> None: ...
        def to_json(self) -> dict:
            return {}

        def load_json(self, body: dict) -> None: ...
        def reset(self) -> None: ...

    path = store.write_snapshot(Reducer())
    assert "identity" not in path.read_text(encoding="utf-8")
    assert EvidenceStore(tmp_path).restore(Reducer()).from_snapshot is True


# ------------------------------------------------------------------ lock


def test_one_live_process_holds_a_root_and_a_dead_ones_lock_is_taken_over(
    tmp_path: Path,
) -> None:
    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        (tmp_path / ".lock").write_text(str(holder.pid), encoding="utf-8")
        with pytest.raises(IdentityError):
            RootLock(tmp_path).acquire()
    finally:
        holder.kill()
        holder.wait()
    lock = RootLock(tmp_path).acquire()
    assert (tmp_path / ".lock").read_text(encoding="utf-8") == str(os.getpid())
    again = RootLock(tmp_path).acquire()
    assert again.held, "reentrant within one process"
    lock.release()
    assert not (tmp_path / ".lock").exists()
