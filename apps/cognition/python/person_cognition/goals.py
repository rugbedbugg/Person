"""Goals, homeostasis and the goal stack.

A goal answers "what should Person accomplish"; a routine answers "how". They
are separate systems on purpose, so the same need can be met by different
strategies and the learner can compare them.

Needs produce urgency rather than commands: homeostasis raises the priority of
a goal, and the stack decides what that means for whatever Person was already
doing.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from person_skills import Condition

GoalStatus = str

GOAL_TYPES = (
    "SURVIVE_IMMEDIATE",
    "SECURE_FOOD",
    "SECURE_SHELTER",
    "ESTABLISH_TOOLS",
    "ESTABLISH_STORAGE",
    "RECOVER_HOME",
    "MAINTAIN_RESERVES",
)


@dataclass(frozen=True, slots=True)
class Goal:
    goal_id: str
    goal_type: str
    priority: float
    source: str
    created_at_tick: int
    status: GoalStatus
    completion_condition: tuple[Condition, ...]
    suspension_reason: str | None = None
    reason_codes: tuple[str, ...] = ()
    #: The priority the drive or project gave it, before affect (ADR 0010).
    base_priority: float | None = None
    #: What affect added or took away. `priority` = base + this.
    affect_bias: float = 0.0

    def as_message(self) -> dict[str, Any]:
        return {
            "goalId": self.goal_id,
            "goalType": self.goal_type,
            "priority": round(self.priority, 3),
            "source": self.source,
            "createdAtTick": self.created_at_tick,
            "status": self.status,
            "completionCondition": [
                {"fact": condition.fact, "op": condition.op, "value": condition.value}
                for condition in self.completion_condition
            ],
            "suspensionReason": self.suspension_reason,
        }

    def satisfied_by(self, state: dict[str, float]) -> bool:
        return all(condition.holds(state) for condition in self.completion_condition)


@dataclass(frozen=True, slots=True)
class Drive:
    """One homeostatic need and how badly it is unmet, from 0 to 1."""

    name: str
    urgency: float
    reason: str


def homeostasis(observation: dict[str, Any], state: dict[str, float]) -> list[Drive]:
    """Survival needs, expressed as urgency rather than as actions."""
    vitals = observation["vitals"]
    home = observation["home"]
    environment = observation["environment"]
    drives: list[Drive] = []

    drives.append(Drive("health", max(0.0, (20.0 - vitals["health"]) / 20.0), "health_below_full"))
    drives.append(Drive("food", max(0.0, (20.0 - vitals["food"]) / 20.0), "food_below_full"))

    threat = 0.0
    for hostile in observation["nearby"]["hostiles"]:
        threat = max(threat, max(0.0, 1.0 - hostile["distance"] / 16.0))
    for hazard in observation["nearby"]["hazards"]:
        threat = max(threat, max(0.0, 1.0 - hazard["distance"] / 4.0))
    drives.append(Drive("safety", threat, "threat_proximity"))

    night = environment["dayPhase"] in {"dusk", "night"}
    shelter_gap = 0.0 if state.get("shelter_complete", 0) >= 1 else (1.0 if night else 0.5)
    drives.append(Drive("shelter", shelter_gap, "shelter_incomplete"))

    tool_gap = max(0.0, (2.0 - state.get("tool_tier", 0)) / 2.0)
    drives.append(Drive("tool_readiness", tool_gap, "tool_tier_below_stone"))

    drives.append(Drive("fuel", 0.0 if state.get("fuel", 0) >= 4 else 0.5, "fuel_reserve_low"))
    drives.append(
        Drive(
            "food_reserve",
            0.0 if home["foodReserve"] >= 4 else 0.6,
            "stored_food_reserve_low",
        )
    )
    capacity = observation["inventory"]["freeSlots"]
    drives.append(
        Drive("inventory_capacity", 0.0 if capacity > 4 else 0.7, "inventory_nearly_full")
    )
    return drives


def _condition(fact: str, value: float) -> Condition:
    return Condition(fact, ">=", value)


class SurvivalGoalProvider:
    """Deterministic survival goals, ordered by homeostatic urgency."""

    name = "survival"

    def propose(
        self,
        observation: dict[str, Any],
        state: dict[str, float],
        tick: int,
        *,
        home: str = "unknown",
    ) -> list[Goal]:
        home_relation = home
        drives = {drive.name: drive for drive in homeostasis(observation, state)}
        environment = observation["environment"]
        home_record = observation["home"]
        night = environment["dayPhase"] in {"dusk", "night"}
        proposals: list[Goal] = []

        def add(
            goal_type: str,
            priority: float,
            conditions: Sequence[Condition],
            reasons: Sequence[str],
            source: str = "homeostasis",
        ) -> None:
            proposals.append(
                Goal(
                    goal_id=f"goal_{goal_type.lower()}",
                    goal_type=goal_type,
                    priority=round(min(1000.0, max(0.0, priority)), 3),
                    source=source,
                    created_at_tick=tick,
                    status="QUEUED",
                    completion_condition=tuple(conditions),
                    reason_codes=tuple(reasons),
                )
            )

        safety = drives["safety"].urgency
        health = drives["health"].urgency
        if safety > 0.4 or observation["vitals"]["health"] < 7:
            add(
                "SURVIVE_IMMEDIATE",
                900 + 100 * safety,
                [_condition("safe", 1)],
                ["threat_present" if safety > 0.4 else "health_critical"],
                source="emergency",
            )

        food_urgency = drives["food"].urgency
        if observation["vitals"]["food"] < 18:
            add(
                "SECURE_FOOD",
                400 + 400 * food_urgency + 100 * health,
                [_condition("food_level", 16)],
                ["food_band_below_full"],
            )

        if state.get("shelter_complete", 0) < 1:
            add(
                "SECURE_SHELTER",
                350 + (300 if night else 0) + 100 * drives["shelter"].urgency,
                [_condition("shelter_complete", 1)],
                ["night_approaching" if night else "shelter_incomplete"],
            )

        if state.get("tool_tier", 0) < 2:
            add(
                "ESTABLISH_TOOLS",
                260 + 60 * drives["tool_readiness"].urgency,
                [_condition("tool_tier", 2)],
                ["tool_tier_below_stone"],
            )

        # Storage serves basic reserves and inventory capacity, which are needs
        # (`PERSON_SPEC` section 17). The `improve_home` project also has it as
        # a milestone, at higher priority, when Person commits to its home.
        if state.get("owned_storage_available", 0) < 1:
            add(
                "ESTABLISH_STORAGE",
                220,
                [_condition("owned_storage_available", 1)],
                ["no_owned_storage"],
            )

        # Person's own belief that it is far from a home it remembers, never
        # a distance the runtime measured (C8).
        if home_relation == "far" and night:
            add(
                "RECOVER_HOME",
                600,
                [_condition("at_home", 1)],
                ["far_from_home_at_night"],
            )

        if home_record["foodReserve"] < 4 and state.get("owned_storage_available", 0) >= 1:
            add(
                "MAINTAIN_RESERVES",
                180,
                [_condition("stored_surplus", 1)],
                ["stored_food_reserve_low"],
            )

        proposals.sort(key=lambda goal: (-goal.priority, goal.goal_type))
        return proposals


@dataclass
class GoalStack:
    """Interruption and resumption.

    A goal is suspended rather than abandoned when something more urgent
    arrives, and the most important suspended goal resumes as soon as the
    interruption is over. Long-horizon work depends on this even though this
    milestone only has survival goals to run through it.
    """

    entries: dict[str, Goal] = field(default_factory=dict)
    active_id: str | None = None
    history: list[tuple[int, str, str]] = field(default_factory=list)
    #: Every event ever noted, so a reader can find the new ones although
    #: `history` is trimmed.
    noted: int = 0

    def _note(self, tick: int, goal_id: str, event: str) -> None:
        self.noted += 1
        self.history.append((tick, goal_id, event))
        if len(self.history) > 512:
            del self.history[:-512]

    @property
    def active(self) -> Goal | None:
        return self.entries.get(self.active_id) if self.active_id else None

    def suspended(self) -> list[Goal]:
        return [goal for goal in self.entries.values() if goal.status == "SUSPENDED"]

    def update(self, proposals: Iterable[Goal], state: dict[str, float], tick: int) -> Goal | None:
        proposed = {goal.goal_id: goal for goal in proposals}

        # Refresh priorities of goals that are still wanted, and retire goals
        # whose completion condition now holds.
        for goal_id, goal in list(self.entries.items()):
            if goal.status in {"COMPLETE", "FAILED", "ABANDONED"}:
                continue
            if goal.satisfied_by(state):
                self.entries[goal_id] = replace(goal, status="COMPLETE", suspension_reason=None)
                self._note(tick, goal_id, "complete")
                if self.active_id == goal_id:
                    self.active_id = None
                continue
            if goal_id in proposed:
                self.entries[goal_id] = replace(goal, priority=proposed[goal_id].priority)
            elif goal.status == "ACTIVE":
                self.entries[goal_id] = replace(
                    goal, status="SUSPENDED", suspension_reason="no_longer_proposed"
                )
                self._note(tick, goal_id, "suspend")
                self.active_id = None

        for goal_id, goal in proposed.items():
            existing = self.entries.get(goal_id)
            if existing is None or existing.status in {"COMPLETE", "FAILED", "ABANDONED"}:
                self.entries[goal_id] = goal
                self._note(tick, goal_id, "queued")

        candidates = [
            goal
            for goal in self.entries.values()
            if goal.status in {"QUEUED", "ACTIVE", "SUSPENDED"} and not goal.satisfied_by(state)
        ]
        if not candidates:
            self.active_id = None
            return None
        candidates.sort(key=lambda goal: (-goal.priority, goal.goal_type))
        best = candidates[0]

        if self.active_id and self.active_id != best.goal_id:
            current = self.entries[self.active_id]
            if current.status == "ACTIVE":
                self.entries[self.active_id] = replace(
                    current,
                    status="SUSPENDED",
                    suspension_reason=f"preempted_by_{best.goal_type.lower()}",
                )
                self._note(tick, self.active_id, "suspend")
        if best.status == "SUSPENDED":
            self._note(tick, best.goal_id, "resume")
        self.entries[best.goal_id] = replace(best, status="ACTIVE", suspension_reason=None)
        self.active_id = best.goal_id
        return self.entries[best.goal_id]

    def block(self, goal_id: str, reason: str, tick: int) -> None:
        goal = self.entries.get(goal_id)
        if goal is None:
            return
        self.entries[goal_id] = replace(goal, status="BLOCKED", suspension_reason=reason)
        self._note(tick, goal_id, "blocked")
        if self.active_id == goal_id:
            self.active_id = None

    def reopen(self, goal_id: str, tick: int) -> None:
        """A blocked goal becomes eligible again, because what blocked it changed."""
        goal = self.entries.get(goal_id)
        if goal is None or goal.status != "BLOCKED":
            return
        self.entries[goal_id] = replace(goal, status="QUEUED", suspension_reason=None)
        self._note(tick, goal_id, "reopened")

    def as_messages(self) -> list[dict[str, Any]]:
        return [
            goal.as_message()
            for goal in sorted(
                self.entries.values(), key=lambda goal: (-goal.priority, goal.goal_id)
            )
        ]

    def resume_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for _tick, goal_id, event in self.history:
            if event == "resume":
                counts[goal_id] = counts.get(goal_id, 0) + 1
        return counts
