"""Reviewed demonstration manifests.

Historical logs are never training evidence by default. Importing a trace
requires a manifest naming the file, its hash, who reviewed it and why, and
which events were included and excluded. Unreviewed imports are refused.

This milestone implements the schema, the validation and the provenance. It
does not implement a demonstration learner.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANIFEST_VERSION = "person-demonstration-v1"

REQUIRED = (
    "version",
    "trace",
    "sha256",
    "approved",
    "reviewer",
    "purpose",
    "included_events",
    "excluded_events",
)


class DemonstrationError(ValueError):
    """A demonstration manifest is missing, malformed, or unapproved."""


@dataclass(frozen=True, slots=True)
class DemonstrationManifest:
    trace: str
    sha256: str
    approved: bool
    reviewer: str
    purpose: str
    included_events: tuple[str, ...]
    excluded_events: tuple[str, ...]

    @property
    def evidential_weight(self) -> float:
        """Demonstrations count for less than fully instrumented live episodes."""
        return 0.25


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(Path(path).read_bytes())
    return digest.hexdigest()


def load_manifest(path: Path, *, base: Path | None = None) -> DemonstrationManifest:
    document: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise DemonstrationError("Manifest is not an object")
    missing = [name for name in REQUIRED if name not in document]
    if missing:
        raise DemonstrationError(f"Manifest is missing {', '.join(missing)}")
    if document["version"] != MANIFEST_VERSION:
        raise DemonstrationError(f"Unsupported manifest version {document['version']!r}")
    if document["approved"] is not True:
        raise DemonstrationError(
            "Manifest is not approved; unreviewed traces are never imported as evidence"
        )
    if not str(document["reviewer"]).strip():
        raise DemonstrationError("Manifest has no reviewer")
    trace = (base or Path(path).parent) / document["trace"]
    if not trace.is_file():
        raise DemonstrationError(f"Manifest trace {document['trace']} is missing")
    actual = file_digest(trace)
    if actual != document["sha256"]:
        raise DemonstrationError(
            f"Manifest hash mismatch for {document['trace']}: "
            f"expected {document['sha256']}, found {actual}"
        )
    return DemonstrationManifest(
        trace=str(trace),
        sha256=actual,
        approved=True,
        reviewer=str(document["reviewer"]),
        purpose=str(document["purpose"]),
        included_events=tuple(document["included_events"]),
        excluded_events=tuple(document["excluded_events"]),
    )
