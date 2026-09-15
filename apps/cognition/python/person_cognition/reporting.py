"""Learning-side summary of an episode.

The runtime writes the authoritative episode report. This is the cognition
half: what was selected, what it was selected on, how often the runtime had to
step in, and what the evidence looks like afterwards.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from person_persistence.snapshot import write_atomic_json

if TYPE_CHECKING:  # pragma: no cover - typing only
    from person_policy import PolicyChoice, RoutineStatistics

    from .goals import GoalStack


class LearningSummary:
    def __init__(self) -> None:
        self.selections: list[dict[str, Any]] = []
        self.overrides: Counter[str] = Counter()
        self.emergencies: Counter[str] = Counter()
        self.outcomes: list[dict[str, Any]] = []
        self.predictions: list[dict[str, Any]] = []

    def note_selection(self, choice: PolicyChoice) -> None:
        self.selections.append(
            {
                "routine_id": choice.routine_id,
                "routine_name": choice.routine_name,
                "learned_or_fallback": choice.learned_or_fallback,
                "confidence": round(choice.confidence, 6),
                "reason_codes": list(choice.reason_codes),
                "shadow_routine_id": choice.shadow_routine_id,
            }
        )

    def note_override(self, decision: str, reason_codes: list[str]) -> None:
        self.overrides[decision] += 1
        for code in reason_codes[:4]:
            self.overrides[f"{decision}:{code}"] += 1

    def note_emergency(self, trigger: str) -> None:
        self.emergencies[trigger] += 1

    def note_outcome(self, message: dict[str, Any]) -> None:
        self.outcomes.append(
            {
                "requested_skill": message["requestedSkill"],
                "executed_skill": message["executedSkill"],
                "status": message["status"],
                "requested_status": message["requestedSkillStatus"],
                "emergency": message["emergency"],
                "health_cost": message["healthCost"],
                "elapsed_ticks": message["elapsedTicks"],
                "expected_effects": message["expectedEffects"],
                "effects": message["effects"],
            }
        )

    def note_prediction(self, payload: dict[str, Any]) -> None:
        self.predictions.append(payload)

    @property
    def prediction_severities(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for record in self.predictions:
            counts[str(record.get("severity", "unobserved"))] += 1
        return dict(counts)

    @property
    def worst_predictions(self) -> list[dict[str, Any]]:
        """The misses a reader should look at first."""
        ranked = sorted(
            self.predictions,
            key=lambda record: {"inverted": 0, "major": 1, "unobserved": 2, "minor": 3}.get(
                str(record.get("severity")), 4
            ),
        )
        return ranked[:10]

    @property
    def fallback_rate(self) -> float:
        if not self.selections:
            return 0.0
        fallbacks = sum(1 for item in self.selections if item["learned_or_fallback"] == "fallback")
        return fallbacks / len(self.selections)

    def write(
        self,
        directory: Path,
        *,
        statistics: RoutineStatistics,
        episode_id: str,
        learning_mode: str,
        training_context: str,
        policy_revision: int,
        goals: GoalStack,
        restore_notes: list[str],
    ) -> Path:
        body = {
            "schema_version": 1,
            "episode_id": episode_id,
            "learning_mode": learning_mode,
            "training_context": training_context,
            "policy_revision": policy_revision,
            "restore_notes": restore_notes,
            "selections": self.selections,
            "fallback_rate": round(self.fallback_rate, 6),
            "safety_overrides": dict(self.overrides),
            "prediction_error": {
                "recorded": len(self.predictions),
                "severities": self.prediction_severities,
                "worst": self.worst_predictions,
            },
            "emergencies": dict(self.emergencies),
            "outcomes": self.outcomes,
            "goal_history": [
                {"tick": tick, "goal_id": goal_id, "event": event}
                for tick, goal_id, event in goals.history
            ],
            "goal_resumptions": goals.resume_counts(),
            "routine_statistics": [
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
                for key, counts in sorted(statistics.routines.items())
            ],
            "skill_statistics": [
                {
                    "training_context": key[0],
                    "context_id": key[1],
                    "skill_id": key[2],
                    "attempts": counts.attempts,
                    "successes": counts.successes,
                    "failures": counts.failures,
                    "preemptions": counts.preemptions,
                }
                for key, counts in sorted(statistics.skills.items())
            ],
        }
        target = Path(directory) / "reports"
        return write_atomic_json(target / f"learning-{episode_id}.json", body, indent=2)
