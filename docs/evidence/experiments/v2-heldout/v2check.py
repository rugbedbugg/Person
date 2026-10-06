"""Apply experiments/v2/PROTOCOL.md to a suite's output: validity, invariants, B criterion.

python3 v2check.py <out-directory> <expected-commit>
"""

import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

out, commit = Path(sys.argv[1]), sys.argv[2]
INVALID = {"runtime_livelock", "runtime_error", "disconnected"}
problems = []
cells = defaultdict(list)

for results in sorted(out.glob("*/results.json")):
    r = json.loads(results.read_text())
    plan = r["plan"]["name"]
    if not r["commit"].startswith(commit) or not r["treeClean"]:
        problems.append(f"{plan}: suite commit {r['commit'][:7]} clean={r['treeClean']}")
    for comparison in r["comparisons"]:
        if comparison["between"] == ["P0", "R2rec"] and comparison["divergentSeeds"]:
            problems.append(
                f"HARD {plan} {comparison['horizon']}: negative control diverged on "
                f"{comparison['divergentSeeds']} seeds"
            )
    for run_json in sorted(glob.glob(str(results.parent / "*/*/seed-*/run.json"))):
        run = json.loads(Path(run_json).read_text())
        meta, metrics = run["metadata"], run["metrics"]
        report = sorted(Path(run_json).parent.glob("output/reports/episode-*.json"))
        reason = json.loads(report[-1].read_text()).get("reason") if report else "no_report"
        status = "valid"
        if (
            reason in INVALID
            or not meta["commit"].startswith(commit)
            or not meta["treeClean"]
            or reason == "no_report"
        ):
            status = "INVALID"
        elif reason == "decision_budget_reached":
            status = "CENSORED_DECISION_LIMIT"
        for key in (
            "priority_changed_without_opportunity",
            "exploration_changed_without_opportunity",
        ):
            if metrics.get(key, 0):
                problems.append(
                    f"HARD {plan} {meta['condition']} {meta['horizon']} s{meta['seed']}: "
                    f"{key}={metrics[key]}"
                )
        cells[(plan, meta["condition"], meta["horizon"])].append(
            (meta["seed"], status, reason, metrics)
        )

counts = defaultdict(int)
for (plan, condition, horizon), runs in sorted(cells.items()):
    for seed, status, reason, _ in runs:
        counts[status] += 1
        if status != "valid":
            problems.append(f"{status} {plan} {condition} {horizon} seed {seed} ({reason})")
print("runs:", dict(counts), "cells:", len(cells))


def b_criterion(plan_prefix: str, divergences: dict) -> str:
    runs = {
        seed: m
        for (p, c, h), rs in cells.items()
        if p.startswith(plan_prefix) and c == "R2act" and h == "long"
        for seed, s, _, m in rs
        if s == "valid"
    }
    opportunity = [s for s, m in runs.items() if m.get("priority_opportunities", 0) >= 1]
    changed = [
        s
        for s, m in runs.items()
        if m.get("priority_changed", 0) >= 1
        and not m.get("priority_changed_without_opportunity", 0)
    ]
    divergent = divergences.get(plan_prefix, 0)
    if len(runs) < 5:
        return f"incomplete ({len(runs)} valid seeds)"
    if len(opportunity) < 3:
        verdict = "INSUFFICIENT OPPORTUNITY" + (" (channel untested)" if not opportunity else "")
    elif not changed:
        verdict = "NO REPLICATION OBSERVED"
    elif len(changed) >= 3 and set(changed) <= set(opportunity) and divergent >= 3:
        verdict = "REPLICATED"
    else:
        verdict = "MIXED / WEAK"
    return (
        f"{verdict}: opportunity seeds {len(opportunity)}/5, "
        f"changed {len(changed)}/5, divergent {divergent}/5"
    )


divergences = {}
for results in sorted(out.glob("*/results.json")):
    r = json.loads(results.read_text())
    for comparison in r["comparisons"]:
        if comparison["between"] == ["A15", "R2act"] and comparison["horizon"] == "long":
            divergences[r["plan"]["name"]] = comparison["divergentSeeds"]
for plan in sorted({p for p, _, _ in cells}):
    if "near-tie" in plan:
        print(plan, "B criterion (descriptive here):", b_criterion(plan, divergences))
    if "wide-margin" in plan:
        changes = sum(
            m.get("priority_changed", 0)
            for (p, c, h), rs in cells.items()
            if p == plan and c == "R2act"
            for _, s, _, m in rs
        )
        print(plan, "A control, R2act priority changes:", changes, "(protocol expects 0 on A2)")
print("problems:", len(problems))
for line in problems:
    print("  ", line)
