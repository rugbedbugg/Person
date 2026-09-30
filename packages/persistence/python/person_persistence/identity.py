"""Who a continuity root belongs to, and where its sessions begin and end (ADR 0017).

Engineering truth, rebuilt from the journal like everything else. Cognition
never reads this module's records directly; it receives a bounded projection
(name, designation, founding, and the last gap as a coarse category), so the
memory firewall (ADR 0003) holds.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .events import EvidenceEvent

IDENTITY_SCHEMA_VERSION = "person-identity-v1"
#: A canonical Person's identifier: `person-000`, `person-001`, ... A
#: canonical Person is founded only by the operator, never by startup.
CANONICAL = re.compile(r"^person-\d{3}$")
#: Upper bounds, in seconds, of each gap category; beyond the last is `longer`.
GAP_CATEGORIES: tuple[tuple[float, str], ...] = (
    (3600.0, "minutes"),
    (86400.0, "hours"),
    (7 * 86400.0, "days"),
)
LOCK_NAME = ".lock"


class IdentityError(RuntimeError):
    """A continuity root cannot be opened as this Person. Fail closed."""


def is_canonical(person_id: str) -> bool:
    return CANONICAL.fullmatch(person_id) is not None


@dataclass(frozen=True, slots=True)
class Founding:
    person_id: str
    name: str
    designation: str | None
    founded_at: str
    identity_schema_version: str = IDENTITY_SCHEMA_VERSION
    founding_experienced_tick: int = 0

    def payload(self) -> dict[str, Any]:
        return asdict(self)

    def fingerprint(self) -> str:
        canonical = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> Founding:
        return cls(
            person_id=str(payload["person_id"]),
            name=str(payload["name"]),
            designation=payload.get("designation"),
            founded_at=str(payload["founded_at"]),
            identity_schema_version=str(payload["identity_schema_version"]),
            founding_experienced_tick=int(payload.get("founding_experienced_tick", 0)),
        )


def _instant(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def gap_category(previous: str | None, now: str) -> str | None:
    """The coarse external gap between two recorded instants, or None if no gap.

    `unknown` when either instant is missing or unreadable, or the clock went
    backwards: continuity is never invented.
    """
    if previous is None:
        return None
    before, after = _instant(previous), _instant(now)
    if before is None or after is None or after < before:
        return "unknown"
    seconds = (after - before).total_seconds()
    for bound, category in GAP_CATEGORIES:
        if seconds < bound:
            return category
    return "longer"


class ContinuityRecord:
    """Identity and session continuity, rebuilt from the journal alone."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.founding: Founding | None = None
        #: The journal began with something other than a founding event.
        self.legacy = False
        self.events_seen = 0
        self.last_session: dict[str, Any] | None = None
        self.last_timestamp: str | None = None
        #: Events that break the founding rule; nonzero means a corrupt root.
        self.violations: list[str] = []

    def apply(self, event: EvidenceEvent) -> None:
        if event.type == "person_founded":
            if self.events_seen:
                self.violations.append(f"person_founded at position {self.events_seen}")
            elif self.founding is None:
                self.founding = Founding.from_payload(event.payload)
        elif self.events_seen == 0:
            self.legacy = True
        if event.type == "session_started":
            self.last_session = {
                "session_id": event.payload.get("session_id"),
                "started_at": event.timestamp,
                "ended": False,
            }
        elif (
            event.type == "session_ended"
            and self.last_session is not None
            and self.last_session["session_id"] == event.payload.get("session_id")
        ):
            self.last_session = {**self.last_session, "ended": True}
        self.events_seen += 1
        self.last_timestamp = event.timestamp

    def to_json(self) -> dict[str, Any]:
        return {
            "founding": self.founding.payload() if self.founding else None,
            "legacy": self.legacy,
            "events_seen": self.events_seen,
            "last_session": self.last_session,
            "last_timestamp": self.last_timestamp,
            "violations": list(self.violations),
        }

    def load_json(self, body: Mapping[str, Any]) -> None:
        self.reset()
        founding = body.get("founding")
        self.founding = Founding.from_payload(founding) if founding else None
        self.legacy = bool(body.get("legacy", False))
        self.events_seen = int(body.get("events_seen", 0))
        self.last_session = body.get("last_session")
        self.last_timestamp = body.get("last_timestamp")
        self.violations = list(body.get("violations", []))


@dataclass(frozen=True, slots=True)
class SelfKnowledge:
    """What cognition may know about its own identity and continuity.

    A projection, never the journal: no raw durations, no records.
    """

    person_id: str
    name: str | None
    designation: str | None
    founded_at: str | None
    #: The coarse external gap before this session: minutes, hours, days,
    #: longer or unknown; None on a Person's very first session.
    last_gap: str | None
    #: Whether the previous session ended cleanly; None when there was none.
    previous_ended_cleanly: bool | None


class RootLock:
    """One process at a time per continuity root (ADR 0017).

    Reentrant within one process, so a restart simulated in-process still
    works; a lock left by a process that no longer exists is taken over.
    """

    def __init__(self, directory: Path) -> None:
        self.path = Path(directory) / LOCK_NAME
        self.held = False

    def acquire(self) -> RootLock:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            holder = self._holder()
            if holder is not None and holder != os.getpid() and _alive(holder):
                raise IdentityError(
                    f"{self.path.parent} is in use by process {holder}; "
                    "a continuity root is lived by one process at a time"
                ) from None
            self.path.write_text(str(os.getpid()), encoding="utf-8")
        else:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
        self.held = True
        return self

    def release(self) -> None:
        if self.held and self._holder() == os.getpid():
            self.path.unlink(missing_ok=True)
        self.held = False

    def _holder(self) -> int | None:
        try:
            return int(self.path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
