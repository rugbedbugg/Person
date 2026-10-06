"""Goals, drives and the goal stack: the environment-neutral mechanism.

Which needs exist and which goals they raise belong to the environment
profile (Minecraft's are `person_minecraft.goals`, ADR 0025).

A goal answers "what should Person accomplish"; a routine answers "how". They
are separate systems on purpose, so the same need can be met by different
strategies and the learner can compare them.

Needs produce urgency rather than commands: homeostasis raises the priority of
a goal, and the stack decides what that means for whatever Person was already
doing.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from person_skills import Condition

GoalStatus = str

#: Goal types Person's core owns, whatever the environment: one trial of an
#: experiment (ADR 0012). An environment profile adds its own (its needs and
#: projects), and the loop's vocabulary is the union.
CORE_GOAL_TYPES: tuple[str, ...] = ("INVESTIGATE",)


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
    #: How the planner may pursue it (ADR 0021/0022): `ordinary`, or
    #: `recovery` for a temporary remedy goal from a deliberation or a habit,
    #: which may also use the planner's recovery operators (`wait_safely`).
    planning_profile: str = "ordinary"

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
    """One homeostatic need and how badly it is unmet, from 0 to 1.

    `name` and `reason` are the environment's own words, and Person's core
    never branches on them. What the core needs to know about a drive is
    typed here: whether it is `pressing`, a need that keeps Person from
    taking up anything voluntary (a project, an investigation) while it is
    urgent. The environment's homeostasis decides which of its drives those
    are (Minecraft's: `person_minecraft.goals`, ADR 0025).
    """

    name: str
    urgency: float
    reason: str
    pressing: bool


class GoalProvider(Protocol):
    """Proposes goals from the decision state, ordered by urgency."""

    name: str

    def propose(self, decision: Any, state: dict[str, float], tick: int) -> list[Goal]: ...


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
    #: The candidates the last update ranked, best first (research record).
    ranked: tuple[Goal, ...] = ()

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
                fresh = proposed[goal_id]
                # Priority, and what it is made of, move together: a record
                # carrying a stale base or affect bias would misstate why.
                self.entries[goal_id] = replace(
                    goal,
                    priority=fresh.priority,
                    base_priority=fresh.base_priority,
                    affect_bias=fresh.affect_bias,
                )
            elif goal.status == "ACTIVE":
                self.entries[goal_id] = replace(
                    goal, status="SUSPENDED", suspension_reason="no_longer_proposed"
                )
                self._note(tick, goal_id, "suspend")
                self.active_id = None

        for goal_id, goal in proposed.items():
            # A goal already met is not wanted. Queuing it would only complete
            # it again at the next update: a success nothing achieved.
            if goal.satisfied_by(state):
                continue
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
            self.ranked = ()
            return None
        candidates.sort(key=lambda goal: (-goal.priority, goal.goal_type))
        # What this choice was made from, for the engineering record.
        self.ranked = tuple(candidates)
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
        # A finished or abandoned goal is not revived by being blocked.
        if goal is None or goal.status in {"COMPLETE", "FAILED", "ABANDONED"}:
            return
        already = goal.status == "BLOCKED"
        self.entries[goal_id] = replace(goal, status="BLOCKED", suspension_reason=reason)
        # A goal stays blocked until something reopens it. Blocking it again
        # is not a new event, and recording it as one would let a single
        # blockage be counted, and appraised, once per observation.
        if not already:
            self._note(tick, goal_id, "blocked")
        if self.active_id == goal_id:
            self.active_id = None

    def conclude(self, goal_id: str, tick: int, reason: str) -> None:
        """A goal that was only ever about one attempt is over, however it went.

        An experiment's trial is for observing, not for getting its outcome:
        once observed, it is done. Recorded as `concluded`: neither achieved
        nor blocked.
        """
        goal = self.entries.get(goal_id)
        if goal is None or goal.status in {"COMPLETE", "FAILED", "ABANDONED"}:
            return
        self.entries[goal_id] = replace(goal, status="COMPLETE", suspension_reason=reason)
        self._note(tick, goal_id, "concluded")
        if self.active_id == goal_id:
            self.active_id = None

    def abandon(self, goal_id: str, tick: int, reason: str) -> None:
        """A goal Person has given up on. It is never a candidate again."""
        goal = self.entries.get(goal_id)
        if goal is None or goal.status in {"COMPLETE", "FAILED", "ABANDONED"}:
            return
        self.entries[goal_id] = replace(goal, status="ABANDONED", suspension_reason=reason)
        self._note(tick, goal_id, "abandoned")
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
