"""Evidence-derived statistics.

Nothing here stores a score. Scores are computed from counts that were
themselves rebuilt from immutable evidence, so a change to the scoring
algorithm re-reads history rather than invalidating it.

Two tables are kept:

* routines, keyed by context and routine, which the policy scores;
* skills, keyed by context and skill, which records what actually executed.

The skill table is where attribution lives. When the runtime replaces a
requested skill, the executed skill receives the attempt and the requested
skill receives a preemption, never an attempt.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from person_persistence import EvidenceEvent

SUCCESS_STATUSES = frozenset({"SUCCESS"})
FAILURE_STATUSES = frozenset(
    {"FAILED", "TIMED_OUT", "UNREACHABLE", "INVALIDATED", "DEATH", "DISCONNECTED"}
)
INCONCLUSIVE_STATUSES = frozenset({"INTERRUPTED", "PREEMPTED"})


@dataclass(slots=True)
class OutcomeCounts:
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    inconclusive: int = 0
    preemptions: int = 0
    health_cost: float = 0.0
    resource_cost: float = 0.0
    elapsed_ticks: int = 0
    recoveries: int = 0
    failure_modes: Counter[str] = field(default_factory=Counter)
    evidence_refs: list[str] = field(default_factory=list)

    @property
    def decisive(self) -> int:
        """Attempts that produced a verdict; interruptions are not evidence."""
        return self.successes + self.failures

    @property
    def posterior_mean(self) -> float:
        """Beta(1 + successes, 1 + failures) mean."""
        return (1.0 + self.successes) / (2.0 + self.decisive)

    @property
    def posterior_variance(self) -> float:
        alpha = 1.0 + self.successes
        beta = 1.0 + self.failures
        total = alpha + beta
        return (alpha * beta) / (total * total * (total + 1.0))

    def posterior_lower(self, z: float = 1.0) -> float:
        """A conservative success estimate.

        One success out of one must not look like a hundred out of a hundred:
        the same mean with far more spread scores lower.
        """
        return max(0.0, self.posterior_mean - z * math.sqrt(self.posterior_variance))

    @property
    def mean_health_cost(self) -> float:
        return self.health_cost / self.attempts if self.attempts else 0.0

    @property
    def mean_resource_cost(self) -> float:
        return self.resource_cost / self.attempts if self.attempts else 0.0

    @property
    def mean_ticks(self) -> float:
        return self.elapsed_ticks / self.attempts if self.attempts else 0.0

    @property
    def recovery_probability(self) -> float:
        troubled = self.failures + self.inconclusive
        return (1.0 + self.recoveries) / (2.0 + troubled)

    def to_json(self) -> dict[str, Any]:
        return {
            "attempts": self.attempts,
            "successes": self.successes,
            "failures": self.failures,
            "inconclusive": self.inconclusive,
            "preemptions": self.preemptions,
            "health_cost": self.health_cost,
            "resource_cost": self.resource_cost,
            "elapsed_ticks": self.elapsed_ticks,
            "recoveries": self.recoveries,
            "failure_modes": dict(self.failure_modes),
            "evidence_refs": self.evidence_refs[-32:],
        }

    @staticmethod
    def from_json(body: Mapping[str, Any]) -> OutcomeCounts:
        counts = OutcomeCounts(
            attempts=int(body.get("attempts", 0)),
            successes=int(body.get("successes", 0)),
            failures=int(body.get("failures", 0)),
            inconclusive=int(body.get("inconclusive", 0)),
            preemptions=int(body.get("preemptions", 0)),
            health_cost=float(body.get("health_cost", 0.0)),
            resource_cost=float(body.get("resource_cost", 0.0)),
            elapsed_ticks=int(body.get("elapsed_ticks", 0)),
            recoveries=int(body.get("recoveries", 0)),
        )
        counts.failure_modes.update(dict(body.get("failure_modes", {})))
        counts.evidence_refs = list(body.get("evidence_refs", []))
        return counts


Key = tuple[str, str, str]


def _key(training_context: str, context_id: str, identifier: str) -> Key:
    return (training_context, context_id, identifier)


class RoutineStatistics:
    """Replayable statistics over routines and executed skills."""

    def __init__(self) -> None:
        self.routines: dict[Key, OutcomeCounts] = {}
        self.skills: dict[Key, OutcomeCounts] = {}
        self.events_applied = 0

    def reset(self) -> None:
        self.routines.clear()
        self.skills.clear()
        self.events_applied = 0

    def apply(self, event: EvidenceEvent) -> None:
        self.events_applied += 1
        payload = event.payload
        if event.type == "routine_outcome":
            key = _key(
                event.training_context,
                str(payload.get("context_id", "")),
                str(payload.get("routine_id", "")),
            )
            self._record(self.routines.setdefault(key, OutcomeCounts()), payload, event.event_id)
        elif event.type in {"skill_completed", "skill_failed", "skill_interrupted"}:
            executed = payload.get("executed_skill")
            requested = payload.get("requested_skill")
            context_id = str(payload.get("context_id", ""))
            if executed:
                counts = self.skills.setdefault(
                    _key(event.training_context, context_id, str(executed)), OutcomeCounts()
                )
                self._record(counts, payload, event.event_id)
            if requested and requested != executed:
                # The requested skill never ran. It gets the preemption and no
                # attempt, so learning cannot credit it with the outcome.
                preempted = self.skills.setdefault(
                    _key(event.training_context, context_id, str(requested)), OutcomeCounts()
                )
                preempted.preemptions += 1

    @staticmethod
    def _record(counts: OutcomeCounts, payload: Mapping[str, Any], event_id: str) -> None:
        status = str(payload.get("status", "FAILED"))
        counts.attempts += 1
        if status in SUCCESS_STATUSES:
            counts.successes += 1
        elif status in FAILURE_STATUSES:
            counts.failures += 1
        else:
            counts.inconclusive += 1
        counts.health_cost += float(payload.get("health_cost", 0.0) or 0.0)
        counts.resource_cost += float(payload.get("resource_cost", 0.0) or 0.0)
        counts.elapsed_ticks += int(payload.get("elapsed_ticks", 0) or 0)
        if payload.get("recovered"):
            counts.recoveries += 1
        for mode in payload.get("failure_modes", []) or []:
            counts.failure_modes[str(mode)] += 1
        counts.evidence_refs.append(event_id)
        if len(counts.evidence_refs) > 64:
            del counts.evidence_refs[:-64]

    def to_json(self) -> dict[str, Any]:
        def pack(table: dict[Key, OutcomeCounts]) -> list[dict[str, Any]]:
            return [
                {
                    "training_context": key[0],
                    "context_id": key[1],
                    "id": key[2],
                    "counts": counts.to_json(),
                }
                for key, counts in sorted(table.items())
            ]

        return {
            "version": 1,
            "events_applied": self.events_applied,
            "routines": pack(self.routines),
            "skills": pack(self.skills),
        }

    def load_json(self, body: Mapping[str, Any]) -> None:
        if int(body.get("version", 0)) != 1:
            raise ValueError("Unsupported statistics snapshot version")
        self.reset()
        self.events_applied = int(body.get("events_applied", 0))
        for table_name, target in (("routines", self.routines), ("skills", self.skills)):
            for entry in list(body.get(table_name, [])):
                if not isinstance(entry, dict) or "id" not in entry:
                    raise ValueError(f"Malformed {table_name} entry in snapshot")
                key = _key(
                    str(entry.get("training_context", "")),
                    str(entry.get("context_id", "")),
                    str(entry["id"]),
                )
                target[key] = OutcomeCounts.from_json(entry.get("counts", {}))

    def routine(self, training_context: str, context_id: str, routine_id: str) -> OutcomeCounts:
        return self.routines.get(_key(training_context, context_id, routine_id), OutcomeCounts())

    def skill(self, training_context: str, context_id: str, skill_id: str) -> OutcomeCounts:
        return self.skills.get(_key(training_context, context_id, skill_id), OutcomeCounts())

    def supported_routines(self, minimum_support: int) -> list[Key]:
        return [
            key
            for key, counts in sorted(self.routines.items())
            if counts.decisive >= minimum_support
        ]
