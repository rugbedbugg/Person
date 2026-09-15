"""Compact snapshots of rebuilt statistics.

A snapshot is an optimisation, never a source of truth. It is written
atomically with a checksum; if anything about it looks wrong it is ignored and
the statistics are rebuilt from the journal, which is authoritative.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

SNAPSHOT_VERSION = 1


class SnapshotError(ValueError):
    """The snapshot cannot be trusted and must be ignored."""


def write_atomic_json(path: Path, document: Any, *, indent: int | None = None) -> Path:
    """Write JSON so a crash mid-write cannot leave a half-parsed file behind."""
    directory = Path(path).parent
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_name = tempfile.mkstemp(dir=directory, suffix=".tmp")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(document, handle, allow_nan=False, indent=indent)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return Path(path)


def _checksum(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SnapshotStore:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, sequence: int) -> Path:
        return self.directory / f"cognition-{sequence:06d}.json"

    def available(self) -> list[Path]:
        return sorted(self.directory.glob("cognition-[0-9]*.json"))

    def write(
        self,
        *,
        sequence: int,
        last_event_id: str | None,
        event_count: int,
        tick: int,
        policy_revision: int,
        body: dict[str, Any],
    ) -> Path:
        document = {
            "version": SNAPSHOT_VERSION,
            "sequence": sequence,
            "last_event_id": last_event_id,
            "event_count": event_count,
            "tick": tick,
            "policy_revision": policy_revision,
            "body": body,
        }
        document["checksum"] = _checksum(document)
        return write_atomic_json(self._path(sequence), document)

    def read(self, path: Path) -> dict[str, Any]:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SnapshotError(f"{path.name} is not readable JSON: {error}") from error
        if not isinstance(document, dict):
            raise SnapshotError(f"{path.name} is not a snapshot object")
        if document.get("version") != SNAPSHOT_VERSION:
            raise SnapshotError(f"{path.name} has unsupported snapshot version")
        stated = document.pop("checksum", None)
        if stated != _checksum(document):
            raise SnapshotError(f"{path.name} failed its checksum")
        document["checksum"] = stated
        return document

    def latest_valid(self) -> dict[str, Any] | None:
        """The newest snapshot that passes every check, or None."""
        for path in reversed(self.available()):
            try:
                return self.read(path)
            except SnapshotError:
                continue
        return None
