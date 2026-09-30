"""Archive raw experiment journals as one deterministic tar.gz per evidence group.

    python scripts/evidence/archive-journals.py <group-id> <commit> <out.tar.gz> <dir> [<dir> ...]

Every file under the given run directories goes into the archive byte for
byte; nothing is rewritten. Beside them sits `MANIFEST.json`, generated
metadata: for each run its condition, seed and horizon, and for each journal
its size, SHA-256 and event count. Paths are stored relative to the
repository's `runs/` directory, in sorted order, with fixed timestamps and
owners, so the same inputs give the same archive.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

ARCHIVE_SCHEMA_VERSION = "person-journal-archive-v1"
ROOT = Path(__file__).resolve().parents[2] / "runs"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def terminal(run: Path) -> str | None:
    reports = sorted((run / "output" / "reports").glob("episode-*.json"))
    if reports:
        report = json.loads(reports[-1].read_text(encoding="utf-8"))
        return f"{report.get('outcome')}:{report.get('reason')}"
    return None


def describe(run: Path) -> dict[str, object]:
    metadata = {}
    if (run / "run.json").exists():
        metadata = json.loads((run / "run.json").read_text(encoding="utf-8")).get("metadata", {})
    journals = []
    for journal in sorted((run / "evidence" / "journal").glob("*.jsonl")):
        data = journal.read_bytes()
        journals.append(
            {
                "path": str(journal.relative_to(ROOT)),
                "bytes": len(data),
                "sha256": digest(data),
                "events": sum(1 for line in data.splitlines() if line.strip()),
            }
        )
    return {
        "run": str(run.relative_to(ROOT)),
        "condition": metadata.get("condition"),
        "seed": metadata.get("seed"),
        "horizon": metadata.get("horizon"),
        "commit": metadata.get("commit"),
        "terminal": terminal(run),
        "journals": journals,
        "events": sum(int(j["events"]) for j in journals),
    }


def main() -> None:
    group, commit, out, *directories = sys.argv[1:]
    runs = sorted(
        {
            journal.parent.parent
            for d in directories
            for journal in Path(d).resolve().rglob("evidence/journal")
        },
        key=str,
    )
    files = sorted(
        (path for d in directories for path in Path(d).resolve().rglob("*") if path.is_file()),
        key=lambda p: str(p.relative_to(ROOT)),
    )
    described = [describe(run) for run in runs]
    manifest = {
        "archive_schema_version": ARCHIVE_SCHEMA_VERSION,
        "group": group,
        "originating_commit": commit,
        "run_count": len(described),
        "event_count": sum(int(run["events"]) for run in described),
        "file_count": len(files),
        "uncompressed_bytes": sum(path.stat().st_size for path in files),
        "runs": described,
    }
    body = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")

    def add(archive: tarfile.TarFile, name: str, data: bytes) -> None:
        info = tarfile.TarInfo(name)
        info.size = len(data)
        info.mtime = 0
        info.mode = 0o644
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        archive.addfile(info, io.BytesIO(data))

    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
        add(archive, f"{group}/MANIFEST.json", body)
        for path in files:
            add(archive, f"{group}/{path.relative_to(ROOT)}", path.read_bytes())
    with (
        open(out, "wb") as handle,
        gzip.GzipFile(fileobj=handle, mode="wb", mtime=0, filename="") as zipped,
    ):
        zipped.write(raw.getvalue())
    print(
        json.dumps(
            {
                key: manifest[key]
                for key in ("group", "run_count", "event_count", "file_count", "uncompressed_bytes")
            }
        )
    )


if __name__ == "__main__":
    main()
