"""Hypotheses, trials and investigations, rebuilt from Person's own records.

Two tables that never mix, as for effect beliefs (ADR 0011): what a record
went to was decided when it was written, by the learning mode then in force.
`active` is what Person reasons and acts with under `supervised`; `shadow` is
for engineering evaluation under `shadow`, and no decision reads it.
Investigations change behaviour, so they exist only in the active table.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from person_persistence import EvidenceEvent

from .experiments import Investigation
from .generation import TrialRecord
from .hypothesis import VERDICT_WEIGHT, CausalHypothesis

TABLES: tuple[str, ...] = ("active", "shadow")
#: Trials remembered per skill and effect, for reasoning over.
RECENT_TRIALS = 16
#: What an investigation's status makes of its hypothesis's lifecycle.
LIFECYCLE_OF: Mapping[str, str] = {
    "ACTIVE": "under_test",
    "SUSPENDED": "under_test",
    "COMPLETE": "testable",
    "RETIRED": "retired",
}


class HypothesisBook:
    def __init__(self) -> None:
        self.hypotheses: dict[str, dict[str, CausalHypothesis]] = {name: {} for name in TABLES}
        self.trials: dict[str, dict[tuple[str, str], list[TrialRecord]]] = {
            name: {} for name in TABLES
        }
        self.rejected: dict[str, int] = dict.fromkeys(TABLES, 0)
        self.investigations: dict[str, Investigation] = {}

    def reset(self) -> None:
        for name in TABLES:
            self.hypotheses[name].clear()
            self.trials[name].clear()
            self.rejected[name] = 0
        self.investigations.clear()

    def apply(self, event: EvidenceEvent) -> None:
        payload = event.payload
        table = str(payload.get("admitted_to", ""))
        if event.type == "causal_trial" and table in TABLES:
            key = (str(payload["skill"]), str(payload["fact"]))
            recent = self.trials[table].setdefault(key, [])
            recent.append(
                TrialRecord(
                    ref=event.event_id,
                    skill=key[0],
                    fact=key[1],
                    verdict=str(payload["verdict"]),
                    conditions=dict(payload["conditions"]),
                )
            )
            del recent[:-RECENT_TRIALS]
        elif event.type == "hypothesis_proposed" and table in TABLES:
            proposed = CausalHypothesis.from_json(payload["hypothesis"])
            self.hypotheses[table][proposed.hypothesis_id] = proposed
        elif event.type == "hypothesis_rejected" and table in TABLES:
            self.rejected[table] += 1
        elif event.type == "hypothesis_evidence" and table in TABLES:
            evidenced = self.hypotheses[table].get(str(payload["hypothesis_id"]))
            verdict = str(payload["verdict"])
            if evidenced is not None and verdict in VERDICT_WEIGHT:
                self.hypotheses[table][evidenced.hypothesis_id] = evidenced.updated(
                    str(payload["arm"]), str(payload["kind"]), verdict, event.event_id
                )
        elif event.type == "investigation_changed":
            investigation = Investigation.from_json(payload["investigation"])
            self.investigations[investigation.investigation_id] = investigation
            tested = self.hypotheses["active"].get(investigation.hypothesis_id)
            if tested is not None:
                self.hypotheses["active"][tested.hypothesis_id] = replace(
                    tested, lifecycle=LIFECYCLE_OF.get(investigation.status, "testable")
                )

    def all_ids(self) -> int:
        return sum(len(table) for table in self.hypotheses.values())

    def to_json(self) -> dict[str, Any]:
        return {
            "hypotheses": {
                name: [h.to_json() for _, h in sorted(table.items())]
                for name, table in self.hypotheses.items()
            },
            "trials": {
                name: [
                    [trial.to_json() for trial in records] for _, records in sorted(table.items())
                ]
                for name, table in self.trials.items()
            },
            "rejected": dict(self.rejected),
            "investigations": [inv.to_json() for _, inv in sorted(self.investigations.items())],
        }

    def load_json(self, body: Mapping[str, Any]) -> None:
        self.reset()
        for name, records in body["hypotheses"].items():
            for record in records:
                hypothesis = CausalHypothesis.from_json(record)
                self.hypotheses[name][hypothesis.hypothesis_id] = hypothesis
        for name, groups in body["trials"].items():
            for group in groups:
                trials = [
                    TrialRecord(
                        ref=str(item["ref"]),
                        skill=str(item["skill"]),
                        fact=str(item["fact"]),
                        verdict=str(item["verdict"]),
                        conditions=dict(item["conditions"]),
                    )
                    for item in group
                ]
                if trials:
                    self.trials[name][(trials[0].skill, trials[0].fact)] = trials
        self.rejected = {name: int(body["rejected"].get(name, 0)) for name in TABLES}
        for record in body["investigations"]:
            investigation = Investigation.from_json(record)
            self.investigations[investigation.investigation_id] = investigation
