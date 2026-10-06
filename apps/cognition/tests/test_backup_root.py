"""The verified backup of a continuity root (ADR 0018). Validation identities only."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from person_persistence import EventJournal
from test_identity_continuity import Process
from test_root_inspection import found_validation, tree

REPOSITORY = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "backup_root", REPOSITORY / "scripts/evidence/backup-root.py"
)
assert _spec and _spec.loader
backup_root = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backup_root)

MOMENT = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)


def lived_root(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    found_validation(root)
    process = Process(root, person="validation-000")
    process.hello("2026-09-30T08:00:00Z")
    process.end_cleanly("2026-09-30T08:10:00Z")
    return root


def test_a_backup_is_a_verified_byte_copy_and_leaves_the_root_untouched(tmp_path: Path) -> None:
    root = lived_root(tmp_path)
    destination = tmp_path / "backups"
    destination.mkdir()
    ended = subprocess.run(
        [sys.executable, "-c", "import os; print(os.getpid())"],
        capture_output=True,
        text=True,
        check=True,
    )
    (root / ".lock").write_text(ended.stdout.strip(), encoding="utf-8")  # stale
    before = tree(root)
    target = backup_root.backup(root, destination, MOMENT)
    assert tree(root) == before, "the root is only read"
    assert target.name == "validation-000-20260930T120000Z"
    for line in (target / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        assert backup_root.digest(root / name) == expected == backup_root.digest(target / name)
    assert not (target / ".lock").exists()
    copied = [e.type for e in EventJournal(target / "journal").read()]
    assert copied == [e.type for e in EventJournal(root / "journal").read()]


def test_a_backup_is_refused_while_the_root_is_being_lived(tmp_path: Path) -> None:
    root = lived_root(tmp_path)
    destination = tmp_path / "backups"
    destination.mkdir()
    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        (root / ".lock").write_text(str(holder.pid), encoding="utf-8")
        with pytest.raises(SystemExit, match="stop it before a backup"):
            backup_root.backup(root, destination, MOMENT)
    finally:
        holder.kill()
        holder.wait()
    assert list(destination.iterdir()) == []


def test_a_backup_inside_its_own_root_or_of_nothing_is_refused(tmp_path: Path) -> None:
    root = lived_root(tmp_path)
    (root / "inner").mkdir()
    with pytest.raises(SystemExit, match="no backup"):
        backup_root.backup(root, root / "inner", MOMENT)
    with pytest.raises(SystemExit, match="no continuity root"):
        backup_root.backup(tmp_path / "empty", tmp_path, MOMENT)
