"""Copy a continuity root to a backup destination, verified (ADR 0018).

    uv run python scripts/evidence/backup-root.py <root> <backup-directory>

Backups exist for storage and integrity recovery, never to undo a lived event.
The copy is refused while any process holds the root's lock, so it is never
taken of a root mid-write. Every file is copied byte for byte into
`<backup-directory>/<person>-<UTC time>/`, a `SHA256SUMS` is written beside
them, and the copy is read back and verified against the originals before this
reports success. The root itself is only read.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from person_cognition.continuity import inspect_root


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def backup(root: Path, destination: Path, now: datetime | None = None) -> Path:
    report = inspect_root(root)
    if report["state"] == "absent":
        raise SystemExit(f"{root} holds no continuity root")
    if report["lock"]["live"]:
        raise SystemExit(
            f"{root} is held by process {report['lock']['pid']}; stop it before a backup"
        )
    if not destination.is_dir():
        raise SystemExit(f"{destination} is not a directory")
    if destination.resolve().is_relative_to(root.resolve()):
        raise SystemExit("a backup inside the root it copies is no backup")
    person = report["founding"]["person_id"] if report["founding"] else report["persons"][0]
    moment = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    target = destination / f"{person}-{moment}"
    target.mkdir()
    sums: dict[str, str] = {}
    for source in sorted(root.rglob("*")):
        relative = source.relative_to(root)
        if source.is_dir() or relative.name == ".lock":
            continue
        copy = target / relative
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, copy)
        sums[relative.as_posix()] = digest(source)
    for relative, expected in sums.items():
        if digest(target / relative) != expected:
            raise SystemExit(f"verification failed for {relative}; the backup is not usable")
    (target / "SHA256SUMS").write_text(
        "".join(f"{sums[name]}  {name}\n" for name in sorted(sums)), encoding="utf-8"
    )
    (target / "BACKUP.json").write_text(
        json.dumps(
            {
                "root": str(root.resolve()),
                "person": person,
                "taken_at": moment,
                "events": report["journal"]["events"],
                "life": report["life"],
                "files": len(sums),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write(__doc__ or "")
        return 2
    target = backup(Path(argv[0]), Path(argv[1]))
    sys.stdout.write(f"{target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
