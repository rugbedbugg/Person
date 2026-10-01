"""When Person deliberates, and what an answer may change (ADR 0021, C3).

Person-owned throughout. Detectors notice that ordinary cognition may be
insufficient; eligibility and suppression decide whether a deliberation may
be requested now; the goal-admission gate, the planner and a priority Person
assigns decide what an admitted answer may change. The model chooses none of
it. Every timer runs on experienced time and is rebuilt from the journal, so
neither time away nor a restart replenishes anything.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from person_persistence import EvidenceEvent

#: Declared engineering priors (ADR 0021), in experienced ticks.
TRIGGER_COUNT = 3
RECURRENCE_WINDOW = 2_400
STALE_AFTER = 1_200
GOAL_LIFETIME = 2_400
GOAL_FAILURES = 3
COOLDOWNS: tuple[int, ...] = (6_000, 12_000, 24_000, 48_000, 72_000)
PER_HOUR = 4
#: Of those, the most that are not `emergency_recurrence`: one hourly slot
#: stays free, so ordinary failures cannot spend it all before a recurring
#: hazard appears.
PER_HOUR_ORDINARY = 3
PER_SESSION = 16
EXPERIENCED_HOUR = 72_000

#: Priority bands Person assigns by trigger. The model never sets one.
RECOVERY_BAND = 700.0
PROJECT_BAND = 300.0

#: Facts no observation carries: true only because the action that makes them
#: true just succeeded (`rested` after waiting). A goal made only of these is
#: satisfied by its routine's success, the only evidence there is.
ACTION_FACTS: frozenset[str] = frozenset({"rested", "stored_surplus", "withdrawn", "looted"})

#: ADR 0023 (C6): the trigger kinds affect may advance, by exactly one signal,
#: and the bands it is read in. Declared engineering priors.
AFFECTIVE_KINDS: frozenset[str] = frozenset(
    {"repeated_failure", "repeated_prediction_error", "no_viable_plan"}
)
AFFECT_ADVANCE = 1
UNEASE_HIGH = 0.5
UNEASE_LOW = 0.2
CONTROL_LOW = -0.25
CONTROL_HIGH = 0.25


def affect_bands(unease: float, control: float) -> dict[str, str]:
    """Coarse bands of Person's ADR 0010 affect: the arbitration rule never
    sees the values themselves."""
    return {
        "unease_band": "high"
        if unease >= UNEASE_HIGH
        else "low"
        if unease < UNEASE_LOW
        else "normal",
        "control_band": "low"
        if control <= CONTROL_LOW
        else "high"
        if control >= CONTROL_HIGH
        else "normal",
    }


def affective_threshold(bands: Mapping[str, str]) -> int:
    """Only earlier, never later: high unease or low control lowers the
    evidence Person needs by one signal; nothing raises it."""
    if bands.get("unease_band") == "high" or bands.get("control_band") == "low":
        return TRIGGER_COUNT - AFFECT_ADVANCE
    return TRIGGER_COUNT


#: Prediction-error severities that count as severe.
SEVERE: frozenset[str] = frozenset({"major", "inverted"})

#: Goal types a deliberation may not add: an experiment's trial exists only
#: through its investigation (ADR 0012).
NOT_ADOPTABLE: frozenset[str] = frozenset({"INVESTIGATE"})

#: What ends a request's life, and whether it earns a longer cooldown.
RESOLUTIONS: frozenset[str] = frozenset(
    {"deliberation_adopted", "deliberation_discarded", "deliberation_shadow_disposition"}
)
BACKOFF_REASONS: frozenset[str] = frozenset({"unavailable", "degraded"})


@dataclass(frozen=True, slots=True)
class Trigger:
    """Why ordinary cognition may be insufficient, keyed as one problem."""

    kind: str
    key: str
    signal: Mapping[str, Any]
    source_goal_id: str | None = None
    source_priority: float | None = None
    source_project: str | None = None


def origin(trigger: Trigger) -> Trigger:
    """The problem a trigger is about. A `habit_breakdown` (ADR 0022, C5) is
    about the problem its habit answered: its band, its budget class and the
    scope its fresh evidence counts toward are that problem's."""
    if trigger.kind != "habit_breakdown":
        return trigger
    return Trigger(
        str(trigger.signal["origin_kind"]),
        str(trigger.signal["origin_key"]),
        {},
        source_goal_id=trigger.source_goal_id,
        source_priority=trigger.source_priority,
        source_project=trigger.source_project,
    )


def band(trigger: Trigger) -> tuple[float, str]:
    """The priority an adopted goal gets, and where it came from."""
    trigger = origin(trigger)
    if trigger.kind == "emergency_recurrence":
        return RECOVERY_BAND, "recovery_band"
    if trigger.kind == "project_reconsideration":
        return PROJECT_BAND, "project_band"
    inherited = trigger.source_priority if trigger.source_priority is not None else 0.0
    return min(RECOVERY_BAND, inherited), "inherited_capped"


class Detectors:
    """Signals cognition already has, turned into keyed triggers.

    With affective arbitration on (ADR 0023), the affective kinds also offer a
    candidate one signal before the baseline, without resetting: whether it
    fires is decided later, from Person's affect, at the arbitration point.
    Off, they behave exactly as ADR 0021.
    """

    def __init__(self) -> None:
        #: ADR 0023: offer candidates one signal early.
        self.early = False
        self._emergencies: dict[str, deque[int]] = defaultdict(deque)
        self._errors: dict[str, deque[int]] = defaultdict(deque)
        self._unplanned: dict[str, int] = {}
        self._projects: set[tuple[str, int]] = set()

    @staticmethod
    def _recent(times: deque[int], now: int) -> int:
        while times and now - times[0] > RECURRENCE_WINDOW:
            times.popleft()
        return len(times)

    def _floor(self) -> int:
        return TRIGGER_COUNT - AFFECT_ADVANCE if self.early else TRIGGER_COUNT

    def emergency(self, trigger: str, now: int) -> Trigger | None:
        times = self._emergencies[trigger]
        times.append(now)
        count = self._recent(times, now)
        if count < TRIGGER_COUNT:
            return None
        # Fired once: the next trigger for this problem needs three new signals.
        times.clear()
        return Trigger(
            "emergency_recurrence",
            trigger,
            {"recurrences": count, "window": RECURRENCE_WINDOW},
        )

    def goal_failed(
        self, goal_type: str, goal_id: str, failures: int, priority: float
    ) -> Trigger | None:
        if failures < self._floor():
            return None
        return Trigger(
            "repeated_failure",
            goal_type,
            {"consecutive_failures": failures, "count": failures},
            source_goal_id=goal_id,
            source_priority=priority,
        )

    def planned(self, goal_type: str, goal_id: str, found: bool, priority: float) -> Trigger | None:
        if found:
            self._unplanned.pop(goal_type, None)
            return None
        count = self._unplanned.get(goal_type, 0) + 1
        self._unplanned[goal_type] = count
        if count < self._floor():
            return None
        if count >= TRIGGER_COUNT:
            self._unplanned.pop(goal_type, None)
        return Trigger(
            "no_viable_plan",
            goal_type,
            {"decisions_without_plan": count, "count": count},
            source_goal_id=goal_id,
            source_priority=priority,
        )

    def prediction(
        self,
        skill: str | None,
        facts: Sequence[str],
        severity: str,
        now: int,
        goal_id: str | None,
        priority: float | None,
    ) -> Trigger | None:
        if severity not in SEVERE or not skill or not facts:
            return None
        # One failed invocation is one signal, however many of its expected
        # facts failed with it; the problem is the skill and that set of facts.
        key = prediction_key(skill, facts)
        times = self._errors[key]
        times.append(now)
        count = self._recent(times, now)
        if count < self._floor():
            return None
        if count >= TRIGGER_COUNT:
            times.clear()
        return Trigger(
            "repeated_prediction_error",
            key,
            {"severe_invocations": count, "window": RECURRENCE_WINDOW, "count": count},
            source_goal_id=goal_id,
            source_priority=priority,
        )

    def project(self, kind: str, project_id: str, blocks: int, near: int) -> Trigger | None:
        """Once per project and block count: a stuck project is one problem."""
        if blocks != near or (project_id, blocks) in self._projects:
            return None
        self._projects.add((project_id, blocks))
        return Trigger(
            "project_reconsideration",
            kind,
            {"blocks": blocks},
            source_project=project_id,
        )


@dataclass
class ArbitrationRecord:
    """Cooldowns, budgets and adopted goals, rebuilt from the journal alone."""

    #: Experienced tick and trigger kind of every request.
    requested_at: list[tuple[int, str]] = field(default_factory=list)
    per_session: dict[str, int] = field(default_factory=dict)
    in_flight: dict[str, str] = field(default_factory=dict)
    resolved_at: dict[str, int] = field(default_factory=dict)
    backoff: dict[str, int] = field(default_factory=dict)
    #: Adopted goals not yet ended: deliberation id -> the adoption payload.
    adopted: dict[str, dict[str, Any]] = field(default_factory=dict)

    def reset(self) -> None:
        self.requested_at.clear()
        self.per_session.clear()
        self.in_flight.clear()
        self.resolved_at.clear()
        self.backoff.clear()
        self.adopted.clear()

    def apply(self, event: EvidenceEvent) -> None:
        payload = event.payload
        key = payload.get("trigger_key_full")
        if event.type == "deliberation_requested" and key:
            # A breakdown is budgeted as the problem it is about, so one
            # descended from an emergency may use the reserved slot.
            self.requested_at.append(
                (
                    int(payload["experienced_tick"]),
                    str(payload.get("budget_kind") or payload.get("trigger_kind")),
                )
            )
            session = str(payload.get("session_id"))
            self.per_session[session] = self.per_session.get(session, 0) + 1
            self.in_flight[str(payload["deliberation_id"])] = str(key)
        elif event.type in RESOLUTIONS and key:
            self.in_flight.pop(str(payload["deliberation_id"]), None)
            self.resolved_at[str(key)] = int(payload["experienced_tick"])
            # How many unavailable or degraded answers in a row: each doubles
            # the key's cooldown, up to the last one.
            if payload.get("reason") in BACKOFF_REASONS:
                self.backoff[str(key)] = min(len(COOLDOWNS) - 1, self.backoff.get(str(key), 0) + 1)
            else:
                self.backoff.pop(str(key), None)
            if event.type == "deliberation_adopted":
                self.adopted[str(payload["deliberation_id"])] = dict(payload)
        elif event.type == "deliberation_goal_ended":
            self.adopted.pop(str(payload["deliberation_id"]), None)

    def to_json(self) -> dict[str, Any]:
        return {
            "requested_at": [list(item) for item in self.requested_at],
            "per_session": dict(self.per_session),
            "in_flight": dict(self.in_flight),
            "resolved_at": dict(self.resolved_at),
            "backoff": dict(self.backoff),
            "adopted": dict(self.adopted),
        }

    def load_json(self, body: Mapping[str, Any]) -> None:
        self.reset()
        self.requested_at.extend((int(t), str(k)) for t, k in body["requested_at"])
        self.per_session.update({str(k): int(v) for k, v in body["per_session"].items()})
        self.in_flight.update({str(k): str(v) for k, v in body["in_flight"].items()})
        self.resolved_at.update({str(k): int(v) for k, v in body["resolved_at"].items()})
        self.backoff.update({str(k): int(v) for k, v in body["backoff"].items()})
        self.adopted.update({str(k): dict(v) for k, v in body["adopted"].items()})

    def suppression(self, key: str, now: int, session: str, kind: str = "") -> str | None:
        """Why a new request for `key` may not be made now, or `None`.

        Whether one is in flight is the live process's to say: a request a
        crash left unanswered stays unmatched evidence, and must not block the
        next session forever. It still counts against the budgets.
        """
        if self.per_session.get(session, 0) >= PER_SESSION:
            return "session_budget"
        recent = [k for tick, k in self.requested_at if now - tick < EXPERIENCED_HOUR]
        if len(recent) >= PER_HOUR:
            return "hourly_budget"
        ordinary = sum(1 for k in recent if k != "emergency_recurrence")
        if kind != "emergency_recurrence" and ordinary >= PER_HOUR_ORDINARY:
            return "hourly_budget_reserved"
        resolved = self.resolved_at.get(key)
        if resolved is not None:
            cooldown = COOLDOWNS[self.backoff.get(key, 0)]
            if now - resolved < cooldown:
                return "cooldown"
        return None


def prediction_key(skill: str, facts: Sequence[str]) -> str:
    """A prediction-error problem: the skill and its sorted set of failed facts."""
    return f"{skill}:{'+'.join(sorted(set(facts)))}"


def full_key(trigger: Trigger) -> str:
    return f"{trigger.kind}:{trigger.key}"


#: How a proposal's desired direction becomes a completion condition.
def condition_for(
    fact: str, direction: str, state: Mapping[str, float]
) -> tuple[str, str, float] | None:
    current = float(state.get(fact, 0.0))
    if direction == "achieve":
        return (fact, ">=", 1.0)
    if direction == "avoid":
        return (fact, "<=", 0.0)
    if direction == "increase":
        return (fact, ">=", current + 1.0)
    if direction == "decrease":
        return (fact, "<=", max(0.0, current - 1.0))
    return None


def admit_goal(
    proposal: Mapping[str, Any],
    *,
    goal_types: Sequence[str],
    state: Mapping[str, float],
    trigger_refs: frozenset[str],
) -> tuple[dict[str, Any] | None, str | None]:
    """The goal-admission gate: the preferred strategy as a Person goal, or why not.

    Returns the goal type and completion conditions, or the reason it is
    inadmissible. Nothing here asks whether the goal is wise; its authority
    is bounded by priority, lifetime, the planner and the safety kernel.
    """
    preferred = proposal.get("preferred")
    strategy = next((s for s in proposal.get("strategies", []) if s.get("id") == preferred), None)
    if strategy is None:
        return None, "no_preferred_strategy"
    goal_type = strategy.get("goal_type")
    if goal_type not in goal_types or goal_type in NOT_ADOPTABLE:
        return None, "unknown_goal"
    desired = strategy.get("desired") or []
    if not desired:
        return None, "no_desired_state"
    conditions = []
    for entry in desired:
        fact = entry.get("fact")
        if fact not in state:
            # Not a predicate Person can evaluate from what it perceives.
            return None, "unrepresentable_goal"
        condition = condition_for(str(fact), str(entry.get("direction")), state)
        if condition is None:
            return None, "unrepresentable_goal"
        conditions.append(condition)
    if trigger_refs and not trigger_refs & set(strategy.get("premises") or ()):
        return None, "does_not_cite_trigger"
    return {"goal_type": goal_type, "conditions": conditions}, None
