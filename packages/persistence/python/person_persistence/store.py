"""Evidence store: append, snapshot, and rebuild after a restart.

Startup is always: load the latest valid snapshot, replay everything recorded
after it, and reconstruct state from the result. If the snapshot is unusable
the journal alone rebuilds the same state, more slowly. The journal is
authoritative; the snapshot only saves time.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Protocol

from .events import EvidenceEvent
from .journal import EvidenceJournal, JournalCorruption
from .snapshot import SnapshotError, SnapshotStore


class EvidenceReducer(Protocol):
    """Anything that can be rebuilt by replaying evidence."""

    def apply(self, event: EvidenceEvent) -> None: ...

    def to_json(self) -> dict[str, Any]: ...

    def load_json(self, body: Mapping[str, Any]) -> None: ...

    def reset(self) -> None: ...


class RestoreReport:
    __slots__ = (
        "from_snapshot",
        "snapshot_tick",
        "replayed_events",
        "truncated_records",
        "duplicate_records",
        "notes",
    )

    def __init__(self) -> None:
        self.from_snapshot = False
        self.snapshot_tick: int | None = None
        self.replayed_events = 0
        self.truncated_records = 0
        self.duplicate_records = 0
        self.notes: list[str] = []

    def as_dict(self) -> dict[str, Any]:
        return {
            "from_snapshot": self.from_snapshot,
            "snapshot_tick": self.snapshot_tick,
            "replayed_events": self.replayed_events,
            "truncated_records": self.truncated_records,
            "duplicate_records": self.duplicate_records,
            "notes": list(self.notes),
        }


class EvidenceStore:
    def __init__(self, directory: Path, *, snapshot_every: int = 50) -> None:
        self.directory = Path(directory)
        self.journal = EvidenceJournal(self.directory / "journal")
        self.snapshots = SnapshotStore(self.directory / "snapshots")
        self.snapshot_every = max(1, snapshot_every)
        self.last_event_id: str | None = None
        self.event_count = 0
        self._since_snapshot = 0
        self._snapshot_sequence = 0
        self._last_tick = 0
        self._policy_revision = 0

    # --------------------------------------------------------------- restore

    def restore(self, reducer: EvidenceReducer) -> RestoreReport:
        report = RestoreReport()
        reducer.reset()
        after: str | None = None
        snapshot = None
        try:
            snapshot = self.snapshots.latest_valid()
        except SnapshotError as error:  # pragma: no cover - latest_valid swallows these
            report.notes.append(f"snapshot ignored: {error}")
        if snapshot is not None:
            try:
                reducer.load_json(snapshot["body"])
                after = snapshot["last_event_id"]
                report.from_snapshot = True
                report.snapshot_tick = snapshot["tick"]
                self._snapshot_sequence = int(snapshot["sequence"])
                self.event_count = int(snapshot["event_count"])
                self._policy_revision = int(snapshot["policy_revision"])
            except (KeyError, TypeError, ValueError) as error:
                report.notes.append(f"snapshot body rejected, rebuilding from evidence: {error}")
                reducer.reset()
                after = None
                self.event_count = 0

        try:
            replayed = self._replay(reducer, after)
        except JournalCorruption as error:
            if after is None:
                raise
            # The snapshot pointed somewhere the journal does not go. Fall back
            # to a complete rebuild rather than trusting a mismatched pair.
            report.notes.append(f"snapshot and journal disagree, full rebuild: {error}")
            report.from_snapshot = False
            reducer.reset()
            self.event_count = 0
            replayed = self._replay(reducer, None)

        report.replayed_events = replayed
        report.truncated_records = self.journal.truncated_records
        report.duplicate_records = self.journal.duplicate_records
        if report.truncated_records:
            report.notes.append(
                f"dropped {report.truncated_records} truncated record(s) at the journal tail"
            )
        if report.duplicate_records:
            report.notes.append(f"ignored {report.duplicate_records} duplicate record(s)")
        return report

    def _replay(self, reducer: EvidenceReducer, after: str | None) -> int:
        replayed = 0
        for event in self.journal.read(after_event_id=after):
            reducer.apply(event)
            self.last_event_id = event.event_id
            self._last_tick = event.tick
            self._policy_revision = max(self._policy_revision, event.policy_revision)
            replayed += 1
        self.event_count += replayed
        return replayed

    # ---------------------------------------------------------------- append

    def append(self, event: EvidenceEvent, reducer: EvidenceReducer | None = None) -> EvidenceEvent:
        self.journal.append(event)
        self.last_event_id = event.event_id
        self._last_tick = event.tick
        self._policy_revision = max(self._policy_revision, event.policy_revision)
        self.event_count += 1
        self._since_snapshot += 1
        if reducer is not None:
            reducer.apply(event)
            if self._since_snapshot >= self.snapshot_every:
                self.write_snapshot(reducer)
        return event

    def append_all(
        self, events: Iterable[EvidenceEvent], reducer: EvidenceReducer | None = None
    ) -> int:
        appended = 0
        for event in events:
            self.append(event, reducer)
            appended += 1
        return appended

    def write_snapshot(self, reducer: EvidenceReducer) -> Path:
        self._snapshot_sequence += 1
        self._since_snapshot = 0
        return self.snapshots.write(
            sequence=self._snapshot_sequence,
            last_event_id=self.last_event_id,
            event_count=self.event_count,
            tick=self._last_tick,
            policy_revision=self._policy_revision,
            body=reducer.to_json(),
        )

    @property
    def policy_revision(self) -> int:
        return self._policy_revision
