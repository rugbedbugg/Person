"""D2's opportunity gates, as PROTOCOL.md amendment 2 defines them.

    python3 d2gates.py <suite-out-directory>

Per seed and horizon, on the R2rec run: threat exposures (runs of consecutive
affect_tonic records with pressures.threat > 0), threat onsets and escalations
within each exposure, and harm appraisals inside the encounter window (world
ticks 3000 to 3800, plus 600). Then the same threat accounting on R2act.
"""

import glob
import json
import sys
from pathlib import Path

WINDOW = (3000, 3800 + 600)


def events(run: Path) -> list[dict]:
    return [
        json.loads(line)
        for f in sorted(glob.glob(str(run / "evidence/journal/*.jsonl")))
        for line in open(f)
        if line.strip()
    ]


def kinds(event: dict) -> list[str]:
    payload = event["payload"]
    found = [payload.get("trigger", "")]
    found += [c.get("kind", "") for c in payload.get("consequences", []) or []]
    found += [c.get("trigger", "") for c in payload.get("consequences", []) or []]
    return found


def gates(run: Path) -> dict:
    journal = events(run)
    tonic = [e for e in journal if e["type"] == "affect_tonic"]
    exposures, current = [], None
    for event in tonic:
        threat = (event["payload"].get("pressures") or {}).get("threat", 0)
        if threat and threat > 0:
            if current is None:
                current = [event["tick"], event["tick"]]
            current[1] = event["tick"]
        elif current is not None:
            exposures.append(current)
            current = None
    if current is not None:
        exposures.append(current)
    appraised = [e for e in journal if e["type"] == "affect_appraised"]
    per_exposure = []
    for start, end in exposures:
        inside = [e for e in appraised if start <= e["tick"] <= end]
        per_exposure.append(
            {
                "ticks": [start, end],
                "onsets": sum("threat_onset" in kinds(e) for e in inside),
                "escalations": sum("threat_escalation" in kinds(e) for e in inside),
            }
        )
    harm = [
        e["tick"] for e in appraised if "harm" in kinds(e) and WINDOW[0] <= e["tick"] <= WINDOW[1]
    ]
    return {"exposures": per_exposure, "harm_in_window": harm}


out = Path(sys.argv[1])
for plan in sorted(out.glob(sys.argv[2] if len(sys.argv) > 2 else "*d2*")):
    for horizon in ("short", "medium", "long"):
        for seed_dir in sorted(plan.glob(f"R2rec/{horizon}/seed-*")):
            seed = seed_dir.name
            g = gates(seed_dir)
            act = gates(plan / "R2act" / horizon / seed)
            threat = "TESTED" if g["exposures"] else "UNTESTED"
            setback = "TESTED" if g["harm_in_window"] else "UNTESTED"
            one_onset = (
                all(x["onsets"] == 1 for x in act["exposures"]) if act["exposures"] else None
            )
            print(
                f"{horizon:6} {seed}: threat {threat} ({len(g['exposures'])} exposures), "
                f"setback {setback} ({len(g['harm_in_window'])} harm in window), "
                f"recovery {setback}; R2act one onset per exposure: {one_onset} "
                f"{[(x['onsets'], x['escalations']) for x in act['exposures']]}"
            )
