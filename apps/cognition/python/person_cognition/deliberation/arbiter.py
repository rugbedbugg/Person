"""The C3 path, as the cognition loop drives it (ADR 0021).

    Person-owned trigger
      -> bounded asynchronous deliberation
      -> untrusted proposal -> C1 grounding gate
      -> staleness and relevance -> goal-admission gate
      -> Person's planner -> a priority Person assigns
      -> one temporary, defeasible goal
      -> ordinary planner, skills and safety

The loop calls in at a few points; only the main thread ever touches
cognitive state or the journal. The worker runs the provider call and
nothing else. In `record_only`, everything runs except the goal itself, and
the outcome is a shadow disposition that can never be mistaken for lived
behaviour.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import Any, cast

from person_planner import RECOVERY_SKILLS, plan_for
from person_skills import Condition

from .context import DeliberationContext
from .deliberator import CallResult, Deliberator, Request
from .habits import Episode, HabitTracker, signature_sha, template_id
from .metareasoning import (
    ACTION_FACTS,
    GOAL_FAILURES,
    GOAL_LIFETIME,
    STALE_AFTER,
    ArbitrationRecord,
    Detectors,
    Trigger,
    admit_goal,
    band,
    full_key,
)

Record = Callable[[str, dict[str, Any]], Any]
#: Project statuses still being pursued (ADR 0009).
OPEN_PROJECTS = frozenset({"ACTIVE", "SUSPENDED"})


def _condition(fact: str, op: str, value: float) -> Condition:
    """A completion condition from the admitted (fact, op, value) triple."""
    return Condition(fact, cast(Any, op), value)


class Handle:
    """A provider call in flight. `done()` never blocks."""

    def __init__(self) -> None:
        self._result: CallResult | None = None
        self._finished = threading.Event()

    def set(self, result: CallResult) -> None:
        self._result = result
        self._finished.set()

    def done(self) -> bool:
        return self._finished.is_set()

    def result(self) -> CallResult:
        assert self._result is not None
        return self._result


def thread_runner(call: Callable[[], CallResult]) -> Handle:
    """Run the provider call on a daemon thread: the world does not wait."""
    handle = Handle()
    worker = threading.Thread(target=lambda: handle.set(call()), daemon=True)
    worker.start()
    return handle


def immediate_runner(call: Callable[[], CallResult]) -> Handle:
    """For tests: the call finishes at once, and is still consumed later."""
    handle = Handle()
    handle.set(call())
    return handle


@dataclass
class InFlight:
    request: Request
    handle: Handle
    trigger: Trigger
    snapshot: dict[str, Any]
    trigger_refs: frozenset[str]


#: Trigger classes that name a source goal whose blocking a remedy may lift.
RETRY_TRIGGERS: frozenset[str] = frozenset({"repeated_failure", "no_viable_plan"})
#: The blocks a satisfied remedy may lift once: Person gave up on the goal
#: because of the trouble the remedy was for.
RETRYABLE_BLOCKS: frozenset[str] = frozenset(
    {"repeated_routine_failure", "no_feasible_plan", "not_found_in_bounded_search"}
)


@dataclass
class Adopted:
    deliberation_id: str
    goal_id: str
    goal_type: str
    conditions: tuple[tuple[str, str, float], ...]
    priority: float
    adopted_at: int
    #: Its own routine succeeded and declared every action fact it asks for:
    #: for a goal of action facts, that is satisfaction.
    routine_succeeded: bool = False
    #: The goal whose trouble raised the trigger, as it was at adoption: its
    #: id, type, creation tick (which instance) and why it was blocked, if it
    #: was. A satisfied remedy may grant that goal one retry (C4.1).
    trigger_kind: str = ""
    source_goal_id: str | None = None
    source_goal_type: str | None = None
    source_created_at: int | None = None
    source_block_reason: str | None = None


@dataclass
class Arbiter:
    """What C3 holds between decisions. Rebuilt state lives in `record`."""

    record: ArbitrationRecord
    detectors: Detectors = field(default_factory=Detectors)
    runner: Callable[[Callable[[], CallResult]], Handle] = thread_runner
    pending: dict[str, Trigger] = field(default_factory=dict)
    in_flight: InFlight | None = None
    adopted: Adopted | None = None
    emergency_now: bool = False
    world_epoch: int = 0
    #: ADR 0022: `off`, or `record_only` (C4: shadow evidence only).
    habits_mode: str = "off"
    tracker: HabitTracker | None = None
    #: Builds a context signature for a trigger and desired facts (the loop's).
    signature_for: Callable[[Trigger, list[str]], dict[str, Any]] | None = None
    #: Adopted goals ended since the loop last looked, with why: the loop
    #: closes them in its goal stack, or a suspended goal nobody proposes any
    #: more would stay a candidate for ever, and grants a satisfied one's
    #: source goal its retry.
    ended: list[tuple[Adopted, str]] = field(default_factory=list)

    def routine_finished(
        self, goal_id: str, status: str, effects: frozenset[str], now: int
    ) -> None:
        """The loop says how a routine for a goal ended, and what its steps
        declared they bring about."""
        adopted = self.adopted
        if adopted is not None and adopted.goal_id == goal_id and status == "SUCCESS":
            asked = {f for f, _, _ in adopted.conditions if f in ACTION_FACTS}
            if asked <= effects:
                adopted.routine_succeeded = True
        if self.tracker is not None and status == "SUCCESS":
            self.tracker.source_progress(goal_id, now)

    def raw_signal(self, key: str, now: int, record: Record) -> None:
        """One qualifying raw signal of a problem, whether or not it triggers."""
        if self.tracker is not None:
            self.tracker.raw_signal(key, now, record)

    def raise_trigger(self, trigger: Trigger | None) -> None:
        if trigger is not None:
            self.pending[full_key(trigger)] = trigger

    # ------------------------------------------------------------ each step

    def step(
        self,
        *,
        mode: str,
        deliberator: Deliberator | None,
        record: Record,
        state: Mapping[str, float],
        now: int,
        session: str,
        life_epoch: int,
        alive: bool,
        world_available: bool,
        goals: Any,
        projects: Any,
        registry: Any,
        goal_types: tuple[str, ...],
        context_for: Callable[[Trigger], tuple[DeliberationContext, frozenset[str]]],
        decision: int,
        failures: Callable[[str], int],
    ) -> None:
        """Consume an answer, keep the adopted goal honest, maybe ask again."""
        if mode == "off" or deliberator is None:
            self.pending.clear()
            self.emergency_now = False
            return
        if self.in_flight is not None and self.in_flight.handle.done():
            flight, self.in_flight = self.in_flight, None
            outcome = deliberator.finish(flight.request, flight.handle.result())
            self._dispose(
                mode,
                flight,
                outcome,
                record,
                state,
                now,
                session,
                life_epoch,
                goals,
                projects,
                registry,
                goal_types,
            )
        self._keep_adopted(record, state, now, failures)
        if self.tracker is not None:
            self.tracker.step(
                now=now,
                life_epoch=life_epoch,
                world_epoch=self.world_epoch,
                session=session,
                record=record,
            )
        for key, trigger in list(self.pending.items()):
            if self.emergency_now:
                break  # an emergency is never interrupted to think; try next step
            del self.pending[key]
            reason = None
            if not alive or not world_available:
                reason = "ineligible"
            elif self.in_flight is not None:
                reason = "in_flight"
            else:
                reason = self.record.suppression(key, now, session, trigger.kind)
            if reason is not None:
                record(
                    "deliberation_suppressed",
                    {
                        "trigger_kind": trigger.kind,
                        "trigger_key": trigger.key,
                        "trigger_key_full": key,
                        "reason": reason,
                        "experienced_tick": now,
                    },
                )
                continue
            context, trigger_refs = context_for(trigger)
            snapshot = {
                "session_id": session,
                "life_epoch": life_epoch,
                "world_epoch": self.world_epoch,
                "request_decision": decision,
                "requested_at": now,
            }
            request = deliberator.request(
                context,
                experienced_tick=now,
                extra={
                    "trigger_kind": trigger.kind,
                    "trigger_key": trigger.key,
                    "trigger_key_full": key,
                    "signal": dict(trigger.signal),
                    "source_goal_id": trigger.source_goal_id,
                    "source_project": trigger.source_project,
                    "trigger_refs": sorted(trigger_refs),
                    **snapshot,
                },
            )
            if request is None:
                continue
            handle = self.runner(partial(deliberator.call, request))
            self.in_flight = InFlight(request, handle, trigger, snapshot, trigger_refs)
        self.emergency_now = False

    # --------------------------------------------------------- disposition

    def _dispose(
        self,
        mode: str,
        flight: InFlight,
        outcome: Any,
        record: Record,
        state: Mapping[str, float],
        now: int,
        session: str,
        life_epoch: int,
        goals: Any,
        projects: Any,
        registry: Any,
        goal_types: tuple[str, ...],
    ) -> None:
        trigger = flight.trigger
        base = {
            "deliberation_id": flight.request.deliberation_id,
            "trigger_kind": trigger.kind,
            "trigger_key": trigger.key,
            "trigger_key_full": full_key(trigger),
            "experienced_tick": now,
        }

        def end(reason: str, **detail: Any) -> None:
            if mode == "record_only":
                record(
                    "deliberation_shadow_disposition",
                    {**base, "disposition": "would_discard", "reason": reason, **detail},
                )
            else:
                record("deliberation_discarded", {**base, "reason": reason, **detail})

        if outcome.failure is not None:
            return end(outcome.failure)
        if outcome.verdict is None or not outcome.verdict.admitted:
            return end("rejected")
        snapshot = flight.snapshot
        if snapshot["session_id"] != session:
            return end("stale", why="session")
        if snapshot["life_epoch"] != life_epoch:
            return end("died")
        if snapshot["world_epoch"] != self.world_epoch:
            return end("world_lost")
        if now - int(snapshot["requested_at"]) > STALE_AFTER:
            return end("stale", why="age")
        if trigger.source_goal_id is not None and trigger.source_goal_id not in goals.entries:
            return end("irrelevant", why="source_goal_gone")
        if trigger.source_project is not None and not any(
            p.project_id == trigger.source_project and p.status in OPEN_PROJECTS
            for p in projects.projects()
        ):
            return end("irrelevant", why="source_project_gone")
        admitted, why = admit_goal(
            outcome.verdict.proposal,
            goal_types=goal_types,
            state=state,
            trigger_refs=flight.trigger_refs,
        )
        if admitted is None:
            return end("inadmissible", why=why)
        conditions = tuple(_condition(f, op, v) for f, op, v in admitted["conditions"])
        if all(condition.holds(state) for condition in conditions):
            return end("superseded")
        plans = [
            plan
            for plan in plan_for(
                state, conditions, registry=registry, limit=1, recovery=tuple(RECOVERY_SKILLS)
            )
            if plan.steps
        ]
        if not plans:
            return end("infeasible")
        priority, source = band(trigger)
        goal = {
            "goal_type": admitted["goal_type"],
            "conditions": [list(c) for c in admitted["conditions"]],
            "priority": priority,
            "priority_source": source,
        }
        if mode == "record_only":
            record(
                "deliberation_shadow_disposition",
                {
                    **base,
                    "disposition": "would_adopt",
                    "reason": "admitted",
                    "hypothetical_goal": goal,
                    "hypothetical_band": priority,
                },
            )
            return None
        goal_id = f"goal_deliberation_{flight.request.deliberation_id}"
        record("deliberation_adopted", {**base, "goal_id": goal_id, **goal, "plan_found": True})
        if self.tracker is not None and self.signature_for is not None:
            desired = [str(f) for f, _, _ in admitted["conditions"]]
            signature = self.signature_for(trigger, desired)
            directions = [
                [str(entry.get("fact")), str(entry.get("direction"))]
                for strategy in outcome.verdict.proposal.get("strategies", [])
                if strategy.get("id") == outcome.verdict.proposal.get("preferred")
                for entry in strategy.get("desired", [])
            ]
            self.tracker.open(
                Episode(
                    deliberation_id=flight.request.deliberation_id,
                    template={
                        "template_id": template_id(
                            trigger_kind=trigger.kind,
                            semantic_key=trigger.key,
                            signature=signature,
                            goal_type=str(admitted["goal_type"]),
                            desired=directions,
                        ),
                        "trigger_kind": trigger.kind,
                        "semantic_key": trigger.key,
                        "signature_sha": signature_sha(signature),
                        "signature": signature,
                        "goal_type": str(admitted["goal_type"]),
                        "desired": sorted(directions),
                    },
                    semantic_key_full=full_key(trigger),
                    life_epoch=life_epoch,
                    world_epoch=self.world_epoch,
                    session=session,
                    source_goal_id=trigger.source_goal_id,
                )
            )
        blocked = goals.entries.get(trigger.source_goal_id) if trigger.source_goal_id else None
        self.adopted = Adopted(
            deliberation_id=flight.request.deliberation_id,
            goal_id=goal_id,
            goal_type=str(admitted["goal_type"]),
            conditions=tuple((str(f), str(op), float(v)) for f, op, v in admitted["conditions"]),
            priority=priority,
            adopted_at=now,
            trigger_kind=trigger.kind,
            source_goal_id=trigger.source_goal_id if blocked is not None else None,
            source_goal_type=blocked.goal_type if blocked is not None else None,
            source_created_at=blocked.created_at_tick if blocked is not None else None,
            source_block_reason=(
                blocked.suspension_reason
                if blocked is not None and blocked.status == "BLOCKED"
                else None
            ),
        )
        return None

    # ------------------------------------------------------- adopted goals

    def _keep_adopted(
        self,
        record: Record,
        state: Mapping[str, float],
        now: int,
        failures: Callable[[str], int],
    ) -> None:
        adopted = self.adopted
        if adopted is None:
            return
        why = None
        conditions = [_condition(f, op, v) for f, op, v in adopted.conditions]
        only_actions = all(f in ACTION_FACTS for f, _, _ in adopted.conditions)
        if (only_actions and adopted.routine_succeeded) or (
            not only_actions and all(condition.holds(state) for condition in conditions)
        ):
            why = "satisfied"
        elif failures(adopted.goal_id) >= GOAL_FAILURES:
            why = "failed"
        elif now - adopted.adopted_at > GOAL_LIFETIME:
            why = "expired"
        if why is not None:
            if self.tracker is not None:
                self.tracker.goal_ended(adopted.deliberation_id, why, now, record)
            record(
                "deliberation_goal_ended",
                {
                    "deliberation_id": adopted.deliberation_id,
                    "goal_id": adopted.goal_id,
                    "why": why,
                    "experienced_tick": now,
                },
            )
            self.ended.append((adopted, why))
            self.adopted = None

    @staticmethod
    def source_retry(adopted: Adopted, goals: Any) -> str | None:
        """The block a satisfied remedy may lift once, or None (C4.1).

        Only for triggers raised by a goal's own trouble, only for the same
        goal instance, and only while it is still blocked for the reason it
        was blocked when the remedy was adopted. Never a general unblocking.
        """
        if adopted.trigger_kind not in RETRY_TRIGGERS or adopted.source_goal_id is None:
            return None
        reason = adopted.source_block_reason
        if reason not in RETRYABLE_BLOCKS:
            return None
        source = goals.entries.get(adopted.source_goal_id)
        if (
            source is None
            or source.created_at_tick != adopted.source_created_at
            or source.status != "BLOCKED"
            or source.suspension_reason != reason
        ):
            return None
        return reason

    def adopted_goal(self, tick: int) -> Any:
        """The adopted goal as a candidate, if one is live. Affect never biases it."""
        from ..goals import Goal

        adopted = self.adopted
        if adopted is None:
            return None
        return Goal(
            goal_id=adopted.goal_id,
            goal_type=adopted.goal_type,
            priority=adopted.priority,
            # The deliberation it came from is in its id and its evidence.
            source="deliberation",
            created_at_tick=tick,
            status="QUEUED",
            completion_condition=tuple(_condition(f, op, v) for f, op, v in adopted.conditions),
            reason_codes=("deliberation",),
            base_priority=adopted.priority,
        )

    def end_carried_over(self, record: Record, now: int) -> None:
        """An adopted goal never outlives its session."""
        for deliberation_id, adoption in list(self.record.adopted.items()):
            record(
                "deliberation_goal_ended",
                {
                    "deliberation_id": deliberation_id,
                    "goal_id": adoption.get("goal_id"),
                    "why": "session_ended",
                    "experienced_tick": now,
                },
            )
