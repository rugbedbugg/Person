"""Append-only canonical event journal.

Person's longitudinal history (ADR 0027). Called the evidence journal until
history and evidence were separated; `EvidenceJournal` remains as an alias.

The journal has no update and no delete. Records are appended and flushed to
disk, segments roll over by size, and reading is strict: a malformed record is
an error rather than something quietly skipped. The one exception is a
truncated final line, which is what a crash mid-append actually looks like.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

from .events import CanonicalEvent, EventRecordError

SEGMENT_LIMIT_BYTES = 8 * 1024 * 1024


class JournalCorruption(EventRecordError):
    """The journal on disk cannot be trusted."""


class EventJournal:
    """Append-only journal of immutable canonical events."""

    def __init__(self, directory: Path, *, segment_limit: int = SEGMENT_LIMIT_BYTES) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.segment_limit = segment_limit
        self.truncated_records = 0
        self.duplicate_records = 0

    # ------------------------------------------------------------------ files

    def segments(self) -> list[Path]:
        return sorted(self.directory.glob("[0-9]*.jsonl"))

    def _active_segment(self) -> Path:
        segments = self.segments()
        if not segments:
            return self.directory / "000001.jsonl"
        last = segments[-1]
        if last.stat().st_size >= self.segment_limit:
            return self.directory / f"{int(last.stem) + 1:06d}.jsonl"
        return last

    # ------------------------------------------------------------------ write

    def append(self, event: CanonicalEvent) -> CanonicalEvent:
        """Append one record and flush it to disk before returning."""
        line = json.dumps(event.to_json(), separators=(",", ":"), allow_nan=False)
        if "\n" in line:
            raise EventRecordError("Evidence record contains a newline")
        path = self._active_segment()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

    # ------------------------------------------------------------------- read

    def read(self, *, after_event_id: str | None = None) -> Iterator[CanonicalEvent]:
        """Yield every record, optionally only those after a known event.

        A final line without its newline is treated as a crash-truncated write
        and dropped, and counted. Anything else that fails to parse raises:
        silently accepting a damaged record would poison every statistic
        rebuilt from it.
        """
        started = after_event_id is None
        seen: set[str] = set()
        segments = self.segments()
        for index, path in enumerate(segments):
            raw = path.read_text(encoding="utf-8")
            if not raw:
                continue
            complete = raw.endswith("\n")
            lines = raw.split("\n")
            if lines and lines[-1] == "":
                lines.pop()
            for position, line in enumerate(lines):
                last_line = index == len(segments) - 1 and position == len(lines) - 1
                if not line.strip():
                    continue
                try:
                    event = CanonicalEvent.from_json(json.loads(line))
                except (json.JSONDecodeError, EventRecordError) as error:
                    if last_line and not complete:
                        self.truncated_records += 1
                        continue
                    raise JournalCorruption(
                        f"{path.name} line {position + 1} is not readable evidence: {error}"
                    ) from error
                if event.event_id in seen:
                    self.duplicate_records += 1
                    continue
                seen.add(event.event_id)
                if started:
                    yield event
                elif event.event_id == after_event_id:
                    started = True
        if not started and after_event_id is not None:
            # The snapshot points at a record this journal does not contain.
            raise JournalCorruption(
                f"Snapshot references event {after_event_id} which is not in the journal"
            )

    def last_event_id(self) -> str | None:
        last: str | None = None
        for event in self.read():
            last = event.event_id
        return last

    def count(self) -> int:
        return sum(1 for _ in self.read())


#: Compatibility name (ADR 0027).
EvidenceJournal = EventJournal
