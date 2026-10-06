"""Validation identities and read-only root inspection (ADR 0018, E2a).

Synthetic and validation identities only: nothing here founds a person-NNN
serial except the reserved test serial person-999, never person-000.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from person_cognition.__main__ import main
from person_cognition.continuity import found, inspect_root
from person_persistence import IdentityError, is_canonical, is_validation
from test_identity_continuity import Process, journal, legacy_root
from test_life_status import alive_person, life, view  # noqa: F401 (fixture)
from test_operational_state import world

T0 = "2026-09-30T08:00:00Z"


def tree(directory: Path) -> dict[str, tuple[int, int]]:
    """Every path under a directory, with its size and modification time."""
    if not directory.exists():
        return {}
    return {
        str(path.relative_to(directory)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(directory.rglob("*"))
    }


def found_validation(evidence: Path, person: str = "validation-000") -> None:
    found(
        evidence_directory=evidence,
        person_id=person,
        world_id="test-world",
        name="Rehearsal",
        designation="Validation-000",
        environment_kind="minecraft",
        embodiment_kind="fixture",
        now="2026-09-30T07:00:00Z",
    )


# ------------------------------------------------------ validation identities


def test_a_validation_identity_is_its_own_namespace() -> None:
    assert is_validation("validation-000") and not is_canonical("validation-000")
    assert is_canonical("person-000") and not is_validation("person-000")
    for other in ("validation-0", "validation-0000", "Validation-000", "test-person-000"):
        assert not is_validation(other), other


def test_ordinary_startup_never_founds_a_validation_identity(tmp_path: Path) -> None:
    with pytest.raises(IdentityError, match="founding command"):
        Process(tmp_path, person="validation-000").hello(T0)
    assert not list(tmp_path.rglob("*.jsonl"))


def test_a_validation_founding_needs_a_name_and_a_designation(tmp_path: Path) -> None:
    with pytest.raises(IdentityError, match="name and a designation"):
        found(
            evidence_directory=tmp_path,
            person_id="validation-000",
            world_id="test-world",
            name=None,
            designation=None,
            environment_kind="minecraft",
            embodiment_kind="fixture",
        )


def test_a_founded_validation_identity_resumes_like_a_canonical_person(tmp_path: Path) -> None:
    found_validation(tmp_path)
    process = Process(tmp_path, person="validation-000")
    process.hello(T0)
    assert process.loop.self_knowledge.designation == "Validation-000"
    with pytest.raises(IdentityError, match="already founded"):
        found_validation(tmp_path)


# --------------------------------------------------------------- inspection


def test_inspecting_an_absent_root_creates_nothing(tmp_path: Path) -> None:
    root = tmp_path / "never"
    report = inspect_root(root)
    assert report["state"] == "absent"
    assert report["lock"] == {"pid": None, "live": False}
    assert not root.exists(), "inspection is read-only"


def test_inspecting_a_live_root_changes_nothing_in_it(tmp_path: Path) -> None:
    process = Process(tmp_path)
    process.hello(T0)
    world(process, "available", T0)
    process.end_cleanly("2026-09-30T08:10:00Z")
    before = tree(tmp_path)
    report = inspect_root(tmp_path)
    assert tree(tmp_path) == before, "no file created, written or touched"
    assert report["state"] == "founded"
    assert report["founding"]["person_id"] == "test-person-000"
    assert report["persons"] == ["test-person-000"]
    assert report["life"] == {"status": "alive", "deaths": 0, "respawns": 0}
    assert report["last_session"]["ended"] is True
    assert report["world"] == "available", "as the runtime last reported it"
    assert report["journal"]["events"] == len(journal(tmp_path))
    assert report["journal"]["truncated"] == 0 and report["journal"]["duplicates"] == 0


def test_inspection_reports_a_death_awaiting_respawn_and_a_termination(
    tmp_path: Path,
    view: dict[str, Any],  # noqa: F811 (the imported fixture)
) -> None:
    awaiting = alive_person(tmp_path / "a", view)
    life(awaiting, "died", tick=140)
    assert inspect_root(tmp_path / "a")["life"]["status"] == "awaiting_respawn"

    ended = alive_person(tmp_path / "b", view)
    life(ended, "died", terminal=True, tick=140)
    assert inspect_root(tmp_path / "b")["life"] == {
        "status": "terminated",
        "deaths": 1,
        "respawns": 0,
    }


def test_inspection_tells_a_legacy_root_from_a_founded_one(tmp_path: Path) -> None:
    legacy_root(tmp_path, person="ada")
    report = inspect_root(tmp_path)
    assert report["state"] == "legacy"
    assert report["founding"] is None
    assert report["persons"] == ["ada"]


def test_inspection_reports_who_holds_the_lock_and_whether_they_live(tmp_path: Path) -> None:
    found_validation(tmp_path)
    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        (tmp_path / ".lock").write_text(str(holder.pid), encoding="utf-8")
        assert inspect_root(tmp_path)["lock"] == {"pid": holder.pid, "live": True}
    finally:
        holder.kill()
        holder.wait()
    assert inspect_root(tmp_path)["lock"] == {"pid": holder.pid, "live": False}
    assert (tmp_path / ".lock").read_text(encoding="utf-8") == str(holder.pid), (
        "a stale lock is reported, never taken over"
    )


def test_the_inspect_command_prints_the_report_and_starts_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    found_validation(tmp_path)
    before = tree(tmp_path)
    assert main(["--inspect-root", str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["state"] == "founded"
    assert report["founding"]["designation"] == "Validation-000"
    assert tree(tmp_path) == before
    assert report["lock"]["pid"] != os.getpid(), "the command took no lock"
