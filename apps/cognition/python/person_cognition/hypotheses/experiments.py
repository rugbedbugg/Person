"""Experiments: finding out, bounded, as ordinary commitments.

Curiosity here is a small epistemic motive, not a personality: an unresolved
hypothesis Person could test is worth something, in proportion to how
uncertain it is, how much the skill matters to Person's life and whether the
contrast can be made at all, less what the test would cost and risk and what
it would take from open projects.

An experiment varies one thing, the hypothesis's condition, and keeps the
intervention fixed. Each trial is an ordinary goal (`INVESTIGATE`) whose only
permitted method is the intervention: the planner plans it, the policy
scores it, the runtime validates it, the capability policy and the safety
kernel judge it, exactly as for any goal. Urgent needs preempt it, and a
preempted trial resumes like any suspended goal. A trial is proposed only
when the condition Person perceives now fills an arm that still needs
evidence, so an experiment on the weather waits for the weather.

Everything is bounded: one open investigation, a fixed number of trials per
arm and of attempts in all, a daily trial budget in experienced time, a risk
limit, and no intervention that uses anything up. Investigations start only
when Person is calm and it is not night, and their trials rank below
projects.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from person_skills import Condition as Requirement
from person_skills import SkillRegistry

from ..goals import Drive, Goal, GoalStack
from .hypothesis import CausalHypothesis
from .vocabulary import Perceived

#: Trials of the intervention wanted on each side of the contrast.
TRIALS_PER_ARM = 4
#: Attempts of any kind, conclusive or not, before an investigation is retired.
MAX_ATTEMPTS = 12
#: At most this many experimental trials in a Minecraft day of experience.
DAILY_TRIALS = 8
DAY = 24_000
#: An investigation that makes no progress for this long is retired.
PATIENCE = DAY
#: At most this many investigations open at once.
MAX_OPEN = 1
#: No experiment with an intervention riskier than this.
RISK_LIMIT = 0.25
#: An investigation starts only if its value exceeds this.
MIN_VALUE = 0.15
#: Below projects (300) and tool-making (260+), above storage and upkeep.
INVESTIGATION_PRIORITY = 240.0
#: Score weights. Parameters.
COST_WEIGHT = 0.1
RISK_WEIGHT = 1.0
DISRUPTION_WEIGHT = 0.15
#: No investigation while any pressing need is more urgent than this.
CALM = 0.3
PRESSING_DRIVES = ("health", "food", "safety")
OPEN = frozenset({"ACTIVE", "SUSPENDED"})
GOAL_TYPE = "INVESTIGATE"


@dataclass(frozen=True, slots=True)
class Design:
    """How a hypothesis would be tested."""

    hypothesis_id: str
    intervention: str
    variable: str
    value: str
    #: The observation expected to differ between the arms.
    fact: str
    direction: str
    trials_per_arm: int
    max_attempts: int
    #: Estimated from the skill contract: time (in tick budgets) and risk.
    cost: float
    risk: float

    def to_json(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "intervention": self.intervention,
            "variable": self.variable,
            "value": self.value,
            "fact": self.fact,
            "direction": self.direction,
            "trials_per_arm": self.trials_per_arm,
            "max_attempts": self.max_attempts,
            "cost": self.cost,
            "risk": self.risk,
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> Design:
        return cls(
            hypothesis_id=str(body["hypothesis_id"]),
            intervention=str(body["intervention"]),
            variable=str(body["variable"]),
            value=str(body["value"]),
            fact=str(body["fact"]),
            direction=str(body["direction"]),
            trials_per_arm=int(body["trials_per_arm"]),
            max_attempts=int(body["max_attempts"]),
            cost=float(body["cost"]),
            risk=float(body["risk"]),
        )


def design(hypothesis: CausalHypothesis, registry: SkillRegistry) -> Design | None:
    """A safe, cheap, single-factor test of `hypothesis`, or None if there is none."""
    if hypothesis.intervention not in registry.ids:
        return None
    spec = registry.get(hypothesis.intervention)
    if spec.emergency or spec.risk > RISK_LIMIT:
        return None
    if any(effect.op == "-=" for effect in spec.expected_effects):
        return None  # It would use something up to find out.
    return Design(
        hypothesis_id=hypothesis.hypothesis_id,
        intervention=hypothesis.intervention,
        variable=hypothesis.condition.variable,
        value=hypothesis.condition.value,
        fact=hypothesis.outcome.fact,
        direction=hypothesis.outcome.direction,
        trials_per_arm=TRIALS_PER_ARM,
        max_attempts=MAX_ATTEMPTS,
        cost=round(spec.max_ticks / 2400, 4),
        risk=spec.risk,
    )


@dataclass(frozen=True, slots=True)
class Value:
    """An experiment's worth, with every part visible."""

    value: float
    parts: Mapping[str, float]

    def to_json(self) -> dict[str, Any]:
        return {"value": round(self.value, 4), **{k: round(v, 4) for k, v in self.parts.items()}}


def epistemic_value(
    hypothesis: CausalHypothesis,
    plan: Design,
    *,
    relevance: float,
    discrimination: float,
    tolerance: float,
    open_projects: int,
) -> Value:
    """uncertainty x relevance x discrimination, less cost, risk and disruption.

    Risk is weighed through the same tolerance factor the policy uses for
    exploration (ADR 0010): the one way affect reaches an experiment.
    """
    uncertainty = 1.0 - hypothesis.confidence
    worth = uncertainty * relevance * discrimination
    cost = COST_WEIGHT * plan.cost
    risk = RISK_WEIGHT * plan.risk * (1.0 + max(0.0, 1.0 - tolerance))
    disruption = DISRUPTION_WEIGHT * open_projects
    return Value(
        worth - cost - risk - disruption,
        {
            "uncertainty": uncertainty,
            "relevance": relevance,
            "discrimination": discrimination,
            "cost": cost,
            "risk": risk,
            "disruption": disruption,
        },
    )


@dataclass(frozen=True, slots=True)
class Investigation:
    investigation_id: str
    design: Design
    status: str
    started_at: int
    held_trials: int = 0
    absent_trials: int = 0
    attempts: int = 0
    #: Experienced times of recent experimental trials, for the daily budget.
    trial_times: tuple[int, ...] = ()
    interruptions: int = 0
    #: The trial goal in flight, if any.
    pending: str | None = None
    note: str | None = None
    #: Experienced time of the last trial, or of the start.
    progressed_at: int = 0

    @property
    def hypothesis_id(self) -> str:
        return self.design.hypothesis_id

    def needs(self, arm: str) -> bool:
        done = self.held_trials if arm == "held" else self.absent_trials
        return done < self.design.trials_per_arm

    def to_json(self) -> dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "design": self.design.to_json(),
            "status": self.status,
            "started_at": self.started_at,
            "held_trials": self.held_trials,
            "absent_trials": self.absent_trials,
            "attempts": self.attempts,
            "trial_times": list(self.trial_times),
            "interruptions": self.interruptions,
            "pending": self.pending,
            "note": self.note,
            "progressed_at": self.progressed_at,
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> Investigation:
        return cls(
            investigation_id=str(body["investigation_id"]),
            design=Design.from_json(body["design"]),
            status=str(body["status"]),
            started_at=int(body["started_at"]),
            held_trials=int(body["held_trials"]),
            absent_trials=int(body["absent_trials"]),
            attempts=int(body["attempts"]),
            trial_times=tuple(int(item) for item in body["trial_times"]),
            interruptions=int(body["interruptions"]),
            pending=body.get("pending"),
            note=body.get("note"),
            progressed_at=int(body["progressed_at"]),
        )


Change = tuple[str, dict[str, Any]]


def _change(investigation: Investigation, change: str, **extra: Any) -> Change:
    return "investigation_changed", {
        "change": change,
        "investigation": investigation.to_json(),
        **extra,
    }


def arm_of(design_: Design, now: Perceived) -> str | None:
    """Which side of the contrast Person is on now, or None if it cannot tell."""
    value = now.value(design_.variable)
    if value is None:
        return None
    return "held" if value == design_.value else "absent"


def calm(drives: Sequence[Drive], night: bool) -> bool:
    pressing = [drive.urgency for drive in drives if drive.name in PRESSING_DRIVES]
    return not night and all(urgency <= CALM for urgency in pressing)


class InvestigationManager:
    """Takes up, runs, interrupts, resumes, concludes and retires investigations."""

    def __init__(self, investigations: Mapping[str, Investigation]) -> None:
        self._investigations = investigations

    def current(self) -> Investigation | None:
        for investigation in self._investigations.values():
            if investigation.status in OPEN:
                return investigation
        return None

    def consider(
        self,
        *,
        hypotheses: Mapping[str, CausalHypothesis],
        registry: SkillRegistry,
        experience: Mapping[str, Any],
        tolerance: float,
        open_projects: int,
        is_calm: bool,
        now: int,
    ) -> list[Change]:
        """Perhaps start investigating the most valuable testable hypothesis.

        `experience` says how often Person has tried each skill and which
        values of each condition it has lived through; it is how relevance
        and discrimination are judged.
        """
        if not is_calm or self.current() is not None:
            return []
        tried = {inv.hypothesis_id for inv in self._investigations.values()}
        attempts: Mapping[str, int] = experience["attempts"]
        seen: Mapping[str, set[str]] = experience["seen"]
        best: tuple[float, str, Design, Value] | None = None
        # Oldest first, so that of equally valuable questions the one Person
        # has wondered about longest is taken up.
        ordered = sorted(
            hypotheses.values(),
            key=lambda h: (h.provenance.proposed_at, h.hypothesis_id),
        )
        for hypothesis in ordered:
            if hypothesis.hypothesis_id in tried or hypothesis.standing != "unresolved":
                continue
            plan = design(hypothesis, registry)
            if plan is None:
                continue
            values = seen.get(plan.variable, set())
            # A contrast needs both sides: the condition, and anything else.
            # One Person has never lived through cannot be expected to
            # discriminate, so it is worth nothing yet.
            both = plan.value in values and bool(values - {plan.value})
            worth = epistemic_value(
                hypothesis,
                plan,
                relevance=min(1.0, attempts.get(plan.intervention, 0) / 4),
                discrimination=1.0 if both else 0.0,
                tolerance=tolerance,
                open_projects=open_projects,
            )
            if worth.value > MIN_VALUE and (best is None or worth.value > best[0]):
                best = (worth.value, hypothesis.hypothesis_id, plan, worth)
        if best is None:
            return []
        _, _, plan, worth = best
        started = Investigation(
            investigation_id=f"investigation_{len(self._investigations) + 1}",
            design=plan,
            status="SUSPENDED",
            started_at=now,
            progressed_at=now,
        )
        return [_change(started, "started", value=worth.to_json())]

    def review(self, experienced: int) -> list[Change]:
        """Retire an investigation whose condition has not come round for a day.

        An experiment on the weather waits for the weather; it does not wait
        for ever, holding the one place an investigation may occupy.
        """
        investigation = self.current()
        if investigation is None or investigation.pending is not None:
            return []
        if experienced - investigation.progressed_at < PATIENCE:
            return []
        retired = replace(investigation, status="RETIRED", note="condition_not_encountered")
        return [_change(retired, "retired")]

    def goal(
        self, now: Perceived, state: Mapping[str, float], experienced: int, tick: int
    ) -> Goal | None:
        """The next trial, if the condition Person perceives now fills an arm."""
        investigation = self.current()
        if investigation is None:
            return None
        plan = investigation.design
        if investigation.pending is not None:
            trial = investigation.pending
        else:
            arm = arm_of(plan, now)
            if arm is None or not investigation.needs(arm):
                return None
            recent = [t for t in investigation.trial_times if experienced - t < DAY]
            if len(recent) >= DAILY_TRIALS:
                return None
            trial = f"goal_{investigation.investigation_id}_t{investigation.attempts + 1}"
        return Goal(
            goal_id=trial,
            goal_type=GOAL_TYPE,
            priority=INVESTIGATION_PRIORITY,
            source="self_generated",
            created_at_tick=tick,
            status="QUEUED",
            completion_condition=(Requirement(plan.fact, ">=", state.get(plan.fact, 0.0) + 1),),
            reason_codes=(
                f"investigate_{plan.hypothesis_id}",
                f"vary_{plan.variable}",
                f"attempt_{investigation.attempts + 1}",
            ),
        )

    def method(self, goal_id: str) -> str | None:
        """The only skill a trial goal may be pursued with."""
        investigation = self._for_goal(goal_id)
        return investigation.design.intervention if investigation else None

    def _for_goal(self, goal_id: str) -> Investigation | None:
        for investigation in self._investigations.values():
            if goal_id.startswith(f"goal_{investigation.investigation_id}_t"):
                return investigation
        return None

    def hypothesis_for(self, goal_id: str) -> str | None:
        investigation = self._for_goal(goal_id)
        return investigation.hypothesis_id if investigation else None

    def track(self, goals: GoalStack, trial_goal: Goal | None) -> list[Change]:
        """Follow the trial goal through the stack: taken up, interrupted, resumed."""
        investigation = self.current()
        if investigation is None:
            return []
        goal_id = investigation.pending or (trial_goal.goal_id if trial_goal else None)
        entry = goals.entries.get(goal_id) if goal_id else None
        if entry is None:
            return []
        if entry.status == "ACTIVE" and investigation.status != "ACTIVE":
            resumed = investigation.pending is not None and investigation.interruptions > 0
            updated = replace(investigation, status="ACTIVE", pending=entry.goal_id, note=None)
            return [_change(updated, "resumed" if resumed else "trial_begun")]
        if (
            entry.status == "SUSPENDED"
            and investigation.status == "ACTIVE"
            and (entry.suspension_reason or "").startswith("preempted_by_")
        ):
            updated = replace(
                investigation,
                status="SUSPENDED",
                interruptions=investigation.interruptions + 1,
                note="interrupted",
            )
            by = (entry.suspension_reason or "").removeprefix("preempted_by_")
            return [_change(updated, "interrupted", by=by)]
        if entry.status == "BLOCKED":
            # The trial could not even be started: no plan, or nothing found.
            updated = replace(
                investigation,
                status="SUSPENDED",
                attempts=investigation.attempts + 1,
                pending=None,
                note=entry.suspension_reason,
            )
            return [*[_change(updated, "trial_blocked")], *self._stop_if_spent(updated)]
        return []

    def trial(
        self,
        goal_id: str,
        *,
        arm: str | None,
        conclusive: bool,
        resumable: bool,
        experienced: int,
        hypothesis: CausalHypothesis | None,
    ) -> tuple[list[Change], bool]:
        """Account for one settled trial. Returns changes, and whether the goal is done."""
        investigation = self._for_goal(goal_id)
        if investigation is None or investigation.status not in OPEN:
            return [], False
        attempts = investigation.attempts + 1
        if not conclusive and resumable and attempts < investigation.design.max_attempts:
            # Interrupted before it could show anything: the same trial resumes.
            updated = replace(investigation, attempts=attempts)
            return [_change(updated, "trial_inconclusive")], False
        held = investigation.held_trials + (1 if conclusive and arm == "held" else 0)
        absent = investigation.absent_trials + (1 if conclusive and arm == "absent" else 0)
        updated = replace(
            investigation,
            status="SUSPENDED",
            held_trials=held,
            absent_trials=absent,
            attempts=attempts,
            trial_times=(*investigation.trial_times, experienced)[-16:]
            if conclusive
            else investigation.trial_times,
            pending=None,
            note=None,
            progressed_at=experienced if conclusive else investigation.progressed_at,
        )
        changes = [_change(updated, "trial" if conclusive else "trial_inconclusive")]
        if hypothesis is not None and hypothesis.standing != "unresolved":
            done = replace(updated, status="COMPLETE", note=hypothesis.standing)
            return [*changes, _change(done, "concluded", standing=hypothesis.summary())], True
        return [*changes, *self._stop_if_spent(updated)], True

    def _stop_if_spent(self, investigation: Investigation) -> list[Change]:
        full = not investigation.needs("held") and not investigation.needs("absent")
        if full or investigation.attempts >= investigation.design.max_attempts:
            note = "unresolved_after_budget" if full else "attempts_exhausted"
            retired = replace(investigation, status="RETIRED", pending=None, note=note)
            return [_change(retired, "retired")]
        return []
