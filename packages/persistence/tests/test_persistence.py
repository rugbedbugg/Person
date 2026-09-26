"""Evidence must survive crashes and refuse to be quietly corrupted."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from person_persistence import (
    EvidenceEvent,
    EvidenceJournal,
    EvidenceStore,
    JournalCorruption,
    SnapshotStore,
    new_event,
)
from person_persistence.demonstrations import DemonstrationError, file_digest, load_manifest
from person_persistence.events import EvidenceError


def make_event(index: int, previous: str | None = None, **payload: Any) -> EvidenceEvent:
    return new_event(
        person_id="ada",
        world_id="w",
        session_id="00000000-0000-4000-8000-000000000001",
        episode_id="ep_1",
        decision_id=None,
        tick=index,
        policy_revision=1,
        training_context="fixture",
        event_type="routine_outcome",
        payload={"routine_id": "r_a", "context_id": "c", "status": "SUCCESS", **payload},
        previous_event_id=previous,
    )


class Counter:
    """A minimal reducer, so the store's behaviour is tested without the policy."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def reset(self) -> None:
        self.seen.clear()

    def apply(self, event: EvidenceEvent) -> None:
        self.seen.append(event.event_id)

    def to_json(self) -> dict[str, Any]:
        return {"seen": list(self.seen)}

    def load_json(self, body: Any) -> None:
        self.seen = list(body["seen"])


def test_records_are_chained_and_readable(tmp_path: Path) -> None:
    journal = EvidenceJournal(tmp_path)
    previous = None
    for index in range(5):
        event = journal.append(make_event(index, previous))
        previous = event.event_id
    events = list(journal.read())
    assert len(events) == 5
    for earlier, later in zip(events, events[1:], strict=False):
        assert later.previous_event_id == earlier.event_id


def test_duplicate_records_are_detected_and_ignored(tmp_path: Path) -> None:
    journal = EvidenceJournal(tmp_path)
    event = journal.append(make_event(1))
    journal.append(event)
    assert len(list(journal.read())) == 1
    assert journal.duplicate_records == 1


def test_a_corrupt_record_is_an_error_not_a_silent_skip(tmp_path: Path) -> None:
    journal = EvidenceJournal(tmp_path)
    journal.append(make_event(1))
    segment = journal.segments()[0]
    with segment.open("a", encoding="utf-8") as handle:
        handle.write('{"event_id": "not-a-uuid", "type": "bogus"}\n')
    with pytest.raises(JournalCorruption):
        list(journal.read())


def test_a_truncated_tail_is_dropped_and_counted(tmp_path: Path) -> None:
    journal = EvidenceJournal(tmp_path)
    journal.append(make_event(1))
    journal.append(make_event(2))
    segment = journal.segments()[0]
    raw = segment.read_text(encoding="utf-8")
    segment.write_text(raw[: len(raw) - 12], encoding="utf-8")
    events = list(journal.read())
    assert len(events) == 1
    assert journal.truncated_records == 1


def test_unknown_schema_versions_are_refused(tmp_path: Path) -> None:
    journal = EvidenceJournal(tmp_path)
    journal.append(make_event(1))
    segment = journal.segments()[0]
    document = json.loads(segment.read_text(encoding="utf-8").splitlines()[0])
    document["schema_version"] = "person-evidence-v99"
    document["event_id"] = "00000000-0000-4000-8000-0000000000ff"
    with segment.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(document) + "\n")
    with pytest.raises(JournalCorruption):
        list(journal.read())
    with pytest.raises(EvidenceError):
        EvidenceEvent.from_json(document)


def test_older_journals_still_read_and_new_events_cannot_backdate_themselves() -> None:
    document = make_event(1).to_json()
    for schema in ("person-evidence-v1", "person-evidence-v2"):
        assert EvidenceEvent.from_json({**document, "schema_version": schema}).tick == 1

    search = {**document, "type": "information_search", "payload": {"phase": "started"}}
    assert EvidenceEvent.from_json(search).schema_version == "person-evidence-v9"
    for schema in ("person-evidence-v3", "person-evidence-v4", "person-evidence-v5"):
        assert EvidenceEvent.from_json({**search, "schema_version": schema}).tick == 1
    for schema in ("person-evidence-v1", "person-evidence-v2"):
        with pytest.raises(EvidenceError):
            EvidenceEvent.from_json({**search, "schema_version": schema})

    for kind in ("memory_encoded", "memory_recalled"):
        memory = {**document, "type": kind, "payload": {}}
        assert EvidenceEvent.from_json(memory).schema_version == "person-evidence-v9"
        assert EvidenceEvent.from_json({**memory, "schema_version": "person-evidence-v4"})
        for schema in ("person-evidence-v1", "person-evidence-v2", "person-evidence-v3"):
            with pytest.raises(EvidenceError):
                EvidenceEvent.from_json({**memory, "schema_version": schema})

    learned = {**document, "type": "effect_evidence", "payload": {}}
    assert EvidenceEvent.from_json(learned).schema_version == "person-evidence-v9"
    with pytest.raises(EvidenceError):
        EvidenceEvent.from_json({**learned, "schema_version": "person-evidence-v7"})

    affect = {**document, "type": "affect_appraised", "payload": {}}
    assert EvidenceEvent.from_json(affect).schema_version == "person-evidence-v9"
    with pytest.raises(EvidenceError):
        EvidenceEvent.from_json({**affect, "schema_version": "person-evidence-v6"})

    for kind in ("project_started", "project_changed"):
        project = {**document, "type": kind, "payload": {}}
        assert EvidenceEvent.from_json(project).schema_version == "person-evidence-v9"
        for schema in ("person-evidence-v4", "person-evidence-v5"):
            with pytest.raises(EvidenceError):
                EvidenceEvent.from_json({**project, "schema_version": schema})

    for kind in (
        "causal_trial",
        "hypothesis_proposed",
        "hypothesis_rejected",
        "hypothesis_evidence",
        "investigation_changed",
    ):
        causal = {**document, "type": kind, "payload": {}}
        assert EvidenceEvent.from_json(causal).schema_version == "person-evidence-v9"
        with pytest.raises(EvidenceError):
            EvidenceEvent.from_json({**causal, "schema_version": "person-evidence-v8"})

    for kind in ("place_formed", "place_visited"):
        place = {**document, "type": kind, "payload": {}}
        assert EvidenceEvent.from_json(place).schema_version == "person-evidence-v9"
        for schema in ("person-evidence-v3", "person-evidence-v4"):
            with pytest.raises(EvidenceError):
                EvidenceEvent.from_json({**place, "schema_version": schema})


def test_snapshots_are_atomic_and_checksummed(tmp_path: Path) -> None:
    snapshots = SnapshotStore(tmp_path)
    path = snapshots.write(
        sequence=1, last_event_id=None, event_count=0, tick=10, policy_revision=1, body={"a": 1}
    )
    assert not list(tmp_path.glob("*.tmp")), "no temporary file may be left behind"
    assert snapshots.read(path)["body"] == {"a": 1}

    document = json.loads(path.read_text(encoding="utf-8"))
    document["body"] = {"a": 2}
    path.write_text(json.dumps(document), encoding="utf-8")
    assert snapshots.latest_valid() is None, "a tampered snapshot must be ignored"


def test_restart_replays_from_the_snapshot_and_rebuilds_without_one(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path, snapshot_every=3)
    reducer = Counter()
    previous = None
    for index in range(7):
        event = store.append(make_event(index, previous), reducer)
        previous = event.event_id
    assert store.snapshots.available(), "a snapshot should have been written"

    restarted = EvidenceStore(tmp_path, snapshot_every=3)
    rebuilt = Counter()
    report = restarted.restore(rebuilt)
    assert report.from_snapshot is True
    assert rebuilt.seen == reducer.seen

    # Remove every snapshot: the journal alone must rebuild the same state.
    for path in restarted.snapshots.available():
        path.unlink()
    cold = EvidenceStore(tmp_path, snapshot_every=3)
    from_journal = Counter()
    cold_report = cold.restore(from_journal)
    assert cold_report.from_snapshot is False
    assert from_journal.seen == reducer.seen


def test_a_snapshot_that_disagrees_with_the_journal_forces_a_full_rebuild(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path, snapshot_every=100)
    reducer = Counter()
    previous = None
    for index in range(4):
        event = store.append(make_event(index, previous), reducer)
        previous = event.event_id
    store.snapshots.write(
        sequence=9,
        last_event_id="00000000-0000-4000-8000-00000000dead",
        event_count=99,
        tick=1,
        policy_revision=1,
        body={"seen": ["ghost"]},
    )
    restarted = EvidenceStore(tmp_path)
    rebuilt = Counter()
    report = restarted.restore(rebuilt)
    assert report.from_snapshot is False
    assert rebuilt.seen == reducer.seen
    assert any("full rebuild" in note for note in report.notes)


def test_the_journal_exposes_no_way_to_change_history() -> None:
    forbidden = {"update", "delete", "remove", "rewrite", "truncate", "overwrite", "edit"}
    assert forbidden.isdisjoint(dir(EvidenceJournal))


def test_demonstration_manifests_require_review_and_a_matching_hash(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text('{"event": 1}\n', encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    body = {
        "version": "person-demonstration-v1",
        "trace": "trace.jsonl",
        "sha256": file_digest(trace),
        "approved": True,
        "reviewer": "operator",
        "purpose": "seed a survival prior",
        "included_events": ["skill_completed"],
        "excluded_events": ["death"],
    }
    manifest.write_text(json.dumps(body), encoding="utf-8")
    loaded = load_manifest(manifest)
    assert loaded.reviewer == "operator"
    assert loaded.evidential_weight < 1.0

    body["approved"] = False
    manifest.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(DemonstrationError, match="not approved"):
        load_manifest(manifest)

    body["approved"] = True
    body["sha256"] = "0" * 64
    manifest.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(DemonstrationError, match="hash mismatch"):
        load_manifest(manifest)
