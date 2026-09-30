"""Rebuild a pruned run from its journal alone and compare with what it recorded.

    uv run python scripts/evidence/rebuild-from-journal.py <run-directory>

Run it from a worktree at the commit that wrote the run, with that commit's
environment. It copies the run's evidence directory, restores cognition from
the journal with no snapshot, and prints JSON saying whether routine and skill
statistics, final affect and experienced time match what the run recorded, or
"unavailable" where that commit did not record them. The run directory itself
is never written.
"""

from __future__ import annotations

import inspect
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from person_cognition.affect import decay
from person_cognition.loop import CognitionLoop
from person_protocol import decode_frame
from person_skills import skill_registry

DIMENSIONS = ("valence", "unease", "control")


def events(journal: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for segment in sorted(journal.glob("*.jsonl"))
        for line in segment.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def restore(evidence: Path, metadata: dict[str, Any]) -> tuple[CognitionLoop, dict[str, Any]]:
    sent: list[dict[str, Any]] = []
    # Older commits take fewer settings; pass only the ones this one has.
    accepted = inspect.signature(CognitionLoop.__init__).parameters
    settings: dict[str, Any] = {}
    if "affect_mode" in accepted:
        settings["affect_mode"] = metadata.get("affectMode", "off")
    if "interoception" in accepted:
        settings["interoception"] = metadata.get("interoception", "on") == "on"
    loop = CognitionLoop(
        evidence_directory=evidence,
        write=lambda line: sent.append(decode_frame(line.rstrip("\n"))),
        log=lambda message: print(message, file=sys.stderr),
        **settings,
    )
    registry = skill_registry()
    loop.handle(
        {
            "protocolVersion": "shroud-learning-v2",
            "messageId": str(uuid.uuid4()),
            "personId": "ada",
            "sessionId": str(uuid.uuid4()),
            "worldId": "rebuild",
            "tick": 0,
            "timestamp": "2026-09-30T00:00:00Z",
            "type": "SessionHello",
            "learningMode": "off",
            "trainingContext": "fixture",
            "policyRevision": 0,
            "skillLibraryRevision": registry.revision,
            "rngSeed": 1,
            "evidenceDirectory": str(evidence),
            "skillIds": registry.ids,
        }
    )
    ready = [message for message in sent if message["type"] == "CognitionReady"][-1]
    return loop, ready


def statistics(loop: CognitionLoop) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The two tables exactly as the learning report writes them."""
    routines = [
        {
            "training_context": key[0],
            "context_id": key[1],
            "routine_id": key[2],
            "attempts": counts.attempts,
            "successes": counts.successes,
            "failures": counts.failures,
            "posterior_mean": round(counts.posterior_mean, 6),
            "posterior_lower": round(counts.posterior_lower(), 6),
        }
        for key, counts in sorted(loop.statistics.routines.items())
    ]
    skills = [
        {
            "training_context": key[0],
            "context_id": key[1],
            "skill_id": key[2],
            "attempts": counts.attempts,
            "successes": counts.successes,
            "failures": counts.failures,
            "preemptions": counts.preemptions,
        }
        for key, counts in sorted(loop.statistics.skills.items())
    ]
    return routines, skills


def final_affect(
    loop: CognitionLoop, journal: list[dict[str, Any]], metrics: dict[str, Any]
) -> tuple[Any, Any]:
    record = getattr(loop, "affect_record", None)
    if record is None or "affect_valence_final" not in metrics:
        return "unavailable", "unavailable"
    # The recorded metric is the last appraised state settled to the episode's
    # end (affect-analysis.ts), so settle the rebuilt state the same way, with
    # this commit's own decay and the loop's own temperament.
    appraised = [e for e in journal if e["type"] in ("affect_appraised", "affect_tonic")]
    at = float(appraised[-1]["payload"].get("experienced_tick", 0)) if appraised else 0.0
    end = max(float(metrics.get("experienced_ticks", at)), at)
    settled = decay(record.state, loop.affect.temperament, end - at)
    rebuilt = {d: round(getattr(settled, d), 4) for d in DIMENSIONS}
    recorded = {d: metrics[f"affect_{d}_final"] for d in DIMENSIONS}
    return rebuilt, recorded


def main() -> None:
    run = Path(sys.argv[1])
    recorded_run = json.loads((run / "run.json").read_text(encoding="utf-8"))
    metrics = recorded_run["metrics"]
    reports = sorted((run / "evidence" / "reports").glob("learning-*.json"))
    report = json.loads(reports[0].read_text(encoding="utf-8")) if reports else None

    evidence = Path(tempfile.mkdtemp()) / "evidence"
    shutil.copytree(run / "evidence", evidence)
    snapshots = evidence / "snapshots"
    if snapshots.exists():
        shutil.rmtree(snapshots)

    loop, ready = restore(evidence, recorded_run["metadata"])
    journal = events(evidence / "journal")
    routines, skills = statistics(loop)
    rebuilt, recorded = final_affect(loop, journal, metrics)
    memory = getattr(loop, "memory", None)

    def compare(ours: list[dict[str, Any]], key: str) -> Any:
        return "unavailable" if report is None else ours == report[key]

    print(
        json.dumps(
            {
                "run": str(run),
                "from_snapshot": ready.get("snapshotTick") is not None,
                "events_replayed": loop.store.event_count,
                "journal_events_on_disk": len(journal),
                "routines": len(routines),
                "routine_statistics_match": compare(routines, "routine_statistics"),
                "skills": len(skills),
                "skill_statistics_match": compare(skills, "skill_statistics"),
                "affect_rebuilt": rebuilt,
                "affect_recorded": recorded,
                "affect_match": "unavailable"
                if rebuilt == "unavailable"
                else all(abs(rebuilt[d] - recorded[d]) <= 5e-5 for d in DIMENSIONS),
                "experienced_ticks": {
                    "rebuilt": getattr(memory, "now", None),
                    "recorded": metrics.get("experienced_ticks", "unavailable"),
                },
                "chain": {
                    "truncated": loop.store.journal.truncated_records,
                    "duplicates": loop.store.journal.duplicate_records,
                    "last_event_id": loop.store.last_event_id,
                },
                "restore_notes": loop.restore_notes,
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
