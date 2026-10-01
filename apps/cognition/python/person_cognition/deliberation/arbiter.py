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

from person_planner import plan_for
from person_skills import Condition

from .context import DeliberationContext
from .deliberator import CallResult, Deliberator, Request
from .metareasoning import (
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


@dataclass
class Adopted:
    deliberation_id: str
    goal_id: str
    goal_type: str
    conditions: tuple[tuple[str, str, float], ...]
    priority: float
    adopted_at: int


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
            plan for plan in plan_for(state, conditions, registry=registry, limit=1) if plan.steps
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
        self.adopted = Adopted(
            deliberation_id=flight.request.deliberation_id,
            goal_id=goal_id,
            goal_type=str(admitted["goal_type"]),
            conditions=tuple((str(f), str(op), float(v)) for f, op, v in admitted["conditions"]),
            priority=priority,
            adopted_at=now,
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
        if all(condition.holds(state) for condition in conditions):
            why = "satisfied"
        elif failures(adopted.goal_id) >= GOAL_FAILURES:
            why = "failed"
        elif now - adopted.adopted_at > GOAL_LIFETIME:
            why = "expired"
        if why is not None:
            record(
                "deliberation_goal_ended",
                {
                    "deliberation_id": adopted.deliberation_id,
                    "goal_id": adopted.goal_id,
                    "why": why,
                    "experienced_tick": now,
                },
            )
            self.adopted = None

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
