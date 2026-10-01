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
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import Any, cast

from person_planner import RECOVERY_SKILLS, plan_for
from person_skills import Condition

from .context import DeliberationContext
from .deliberator import CallResult, Deliberator, Request
from .habits import (
    Episode,
    HabitBook,
    HabitTracker,
    Template,
    context_signature,
    signature_sha,
    template_id,
)
from .metareasoning import (
    ACTION_FACTS,
    AFFECTIVE_KINDS,
    GOAL_FAILURES,
    GOAL_LIFETIME,
    STALE_AFTER,
    TRIGGER_COUNT,
    ArbitrationRecord,
    Detectors,
    Trigger,
    admit_goal,
    affective_threshold,
    band,
    condition_for,
    full_key,
    origin,
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
    #: What Person perceived when the trigger fired: a habit's context
    #: signature is of the moment the problem arose, not of the answer.
    basis: dict[str, Any] | None = None


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
    #: `deliberation`, or `habit` for a promoted habit's remedy (C5); then
    #: `deliberation_id` holds the habit invocation's id.
    via: str = "deliberation"
    template_id: str | None = None


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
    #: What a context signature is built from when a trigger fires: the
    #: observation, the recognised place and the source goal type (the loop's).
    basis_for: Callable[[Trigger], dict[str, Any]] | None = None
    #: C5: the active book promoted habits are invoked from (habits `active`).
    active_book: HabitBook | None = None
    new_invocation_id: Callable[[], str] = lambda: f"hinv_{uuid.uuid4().hex[:16]}"
    #: The problem each habit last answered, for the breakdown that follows a
    #: definite failure of its own episode.
    invoked_for: dict[str, Trigger] = field(default_factory=dict)
    #: ADR 0023 (C6): `off`, `record_only` (shadow evidence only) or `active`.
    affect_arbitration: str = "off"
    #: Person's affect bands when it dispatched its latest skill: the state
    #: before any outcome that skill's signals carry was appraised.
    affect_snapshot: dict[str, str] | None = None
    #: The pre-signal bands each pending affective trigger is judged by.
    affect_at_signal: dict[str, dict[str, str]] = field(default_factory=dict)
    #: The session and life epoch of the current step, for habit episodes.
    tracker_session: str = ""
    tracker_life_epoch: int = 0
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
            key = full_key(trigger)
            self.pending[key] = trigger
            if (
                self.affect_arbitration != "off"
                and trigger.kind in AFFECTIVE_KINDS
                and self.affect_snapshot is not None
            ):
                # Never the state this very signal's appraisal produced.
                self.affect_at_signal[key] = dict(self.affect_snapshot)

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
        self.tracker_session = session
        self.tracker_life_epoch = life_epoch
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
        # A learned habit answers first, for every problem pending, before any
        # model is asked about any of them (ADR 0022, C5).
        bases: dict[str, dict[str, Any] | None] = {}
        for key, trigger in list(self.pending.items()):
            if self.emergency_now:
                break
            bases[key] = self.basis_for(trigger) if self.basis_for is not None else None
            if (
                alive
                and world_available
                and trigger.kind != "habit_breakdown"
                and not self._early(trigger)
                and self._habit(
                    trigger, bases[key], record, state, now, goals, projects, registry, goal_types
                )
            ):
                del self.pending[key]  # answered: no model, whatever its budgets
        for key, trigger in list(self.pending.items()):
            if self.emergency_now:
                break  # an emergency is never interrupted to think; try next step
            del self.pending[key]
            basis = bases.get(key)
            if basis is None and self.basis_for is not None:
                basis = self.basis_for(trigger)
            bands = self.affect_at_signal.pop(key, None)
            counterfactual: dict[str, Any] = {}
            if self.affect_arbitration != "off" and trigger.kind in AFFECTIVE_KINDS:
                early = self._early(trigger)
                if early and (
                    not alive
                    or not world_available
                    or self.adopted is not None
                    or self._matching_habit(trigger, basis) is not None
                ):
                    # Not at the arbitration point: a candidate the baseline
                    # would not act on leaves no trace (ADR 0023).
                    continue
                if alive and world_available and self.adopted is None:
                    counterfactual = self._arbitrate(trigger, key, bands, record, now)
                    if not counterfactual["fires"]:
                        continue
                if self.affect_arbitration != "active":
                    counterfactual = {}
                else:
                    counterfactual.pop("fires", None)
            reason = None
            if not alive or not world_available:
                reason = "ineligible"
            elif self.in_flight is not None:
                reason = "in_flight"
            elif self.adopted is not None:
                # One temporary remedy at a time (ADR 0021): while one is being
                # pursued, a problem it may well be resolving is not new.
                reason = "remedy_in_progress"
            else:
                reason = self.record.suppression(key, now, session, origin(trigger).kind)
            if reason is not None:
                record(
                    "deliberation_suppressed",
                    {
                        "trigger_kind": trigger.kind,
                        "trigger_key": trigger.key,
                        "trigger_key_full": key,
                        "reason": reason,
                        "experienced_tick": now,
                        # Affect may have wanted this earlier and C3 said no:
                        # that is evidence too (ADR 0023).
                        **{
                            k: v for k, v in counterfactual.items() if k != "affect_changed_outcome"
                        },
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
                    "budget_kind": origin(trigger).kind,
                    **snapshot,
                    **counterfactual,
                },
            )
            if request is None:
                continue
            handle = self.runner(partial(deliberator.call, request))
            self.in_flight = InFlight(request, handle, trigger, snapshot, trigger_refs, basis)
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
        if self.adopted is not None:
            # Another remedy (a habit's, or an earlier answer's) is live: one
            # at a time, and a live one is never silently replaced.
            return end("superseded", why="remedy_in_progress")
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
        problem = origin(trigger)
        if self.tracker is not None and flight.basis is not None:
            desired = [str(f) for f, _, _ in admitted["conditions"]]
            signature = context_signature(**flight.basis, desired_facts=desired)
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
                            trigger_kind=problem.kind,
                            semantic_key=problem.key,
                            signature=signature,
                            goal_type=str(admitted["goal_type"]),
                            desired=directions,
                        ),
                        "trigger_kind": problem.kind,
                        "semantic_key": problem.key,
                        "signature_sha": signature_sha(signature),
                        "signature": signature,
                        "goal_type": str(admitted["goal_type"]),
                        "desired": sorted(directions),
                    },
                    semantic_key_full=full_key(problem),
                    life_epoch=life_epoch,
                    world_epoch=self.world_epoch,
                    session=session,
                    source_goal_id=trigger.source_goal_id,
                )
            )
        self.adopted = self._adoption(
            flight.request.deliberation_id,
            goal_id,
            str(admitted["goal_type"]),
            tuple((str(f), str(op), float(v)) for f, op, v in admitted["conditions"]),
            priority,
            now,
            problem,
            goals,
        )
        return None

    @staticmethod
    def _adoption(
        adoption_id: str,
        goal_id: str,
        goal_type: str,
        conditions: tuple[tuple[str, str, float], ...],
        priority: float,
        now: int,
        problem: Trigger,
        goals: Any,
        **habit: Any,
    ) -> Adopted:
        blocked = goals.entries.get(problem.source_goal_id) if problem.source_goal_id else None
        return Adopted(
            deliberation_id=adoption_id,
            goal_id=goal_id,
            goal_type=goal_type,
            conditions=conditions,
            priority=priority,
            adopted_at=now,
            trigger_kind=problem.kind,
            source_goal_id=problem.source_goal_id if blocked is not None else None,
            source_goal_type=blocked.goal_type if blocked is not None else None,
            source_created_at=blocked.created_at_tick if blocked is not None else None,
            source_block_reason=(
                blocked.suspension_reason
                if blocked is not None and blocked.status == "BLOCKED"
                else None
            ),
            **habit,
        )

    # ------------------------------------------- affective arbitration (C6)

    @staticmethod
    def _early(trigger: Trigger) -> bool:
        """A candidate one signal before the ADR 0021 baseline."""
        return (
            trigger.kind in AFFECTIVE_KINDS
            and int(trigger.signal.get("count", TRIGGER_COUNT)) < TRIGGER_COUNT
        )

    def _arbitrate(
        self,
        trigger: Trigger,
        key: str,
        bands: dict[str, str] | None,
        record: Record,
        now: int,
    ) -> dict[str, Any]:
        """ADR 0023 at the arbitration point: record the detector-level facts,
        and say whether this signal fires under the mode in force."""
        count = int(trigger.signal.get("count", TRIGGER_COUNT))
        bands = bands or {"unease_band": "unknown", "control_band": "unknown"}
        shadow = affective_threshold(bands)
        baseline_crossed = count >= TRIGGER_COUNT
        shadow_crossed = count >= shadow
        advanced = shadow_crossed and not baseline_crossed
        record(
            "affective_arbitration_shadow",
            {
                "trigger_kind": trigger.kind,
                "trigger_key": trigger.key,
                "trigger_key_full": key,
                "signal_count": count,
                "baseline_threshold": TRIGGER_COUNT,
                "shadow_threshold": shadow,
                **bands,
                "baseline_threshold_crossed": baseline_crossed,
                "shadow_threshold_crossed": shadow_crossed,
                "affect_advanced_threshold": advanced,
                "mode": self.affect_arbitration,
                "experienced_tick": now,
            },
        )
        fires = shadow_crossed if self.affect_arbitration == "active" else baseline_crossed
        return {
            "fires": fires,
            "baseline_would_fire": baseline_crossed,
            "affect_advanced_threshold": advanced,
            "affect_changed_outcome": advanced,
        }

    # ------------------------------------------------------- habits (C5)

    def _matching_habit(self, trigger: Trigger, basis: dict[str, Any] | None) -> Template | None:
        """The promoted habit with this scope and this exact signature, if any."""
        book = self.active_book
        if book is None or self.habits_mode != "active" or basis is None:
            return None
        for t in book.templates.values():
            if (t.trigger_kind, t.semantic_key) != (trigger.kind, trigger.key):
                continue
            if t.state != "promoted":
                continue
            observed = signature_sha(
                context_signature(**basis, desired_facts=[str(f) for f, _ in t.desired])
            )
            if observed == t.signature_sha:
                return t
        return None

    def _habit(
        self,
        trigger: Trigger,
        basis: dict[str, Any] | None,
        record: Record,
        state: Mapping[str, float],
        now: int,
        goals: Any,
        projects: Any,
        registry: Any,
        goal_types: tuple[str, ...],
    ) -> bool:
        """Answer a firing trigger from a promoted habit, if one applies.

        Before any model suppression: a learned habit runs whatever the
        provider's cooldown, quota or availability. True when the habit
        answered, or was found contradicted and demoted (its breakdown then
        brings the problem back to System 2).
        """
        book = self.active_book
        if book is None or self.habits_mode != "active" or self.tracker is None or basis is None:
            return False
        scoped = [
            t
            for t in book.templates.values()
            if (t.trigger_kind, t.semantic_key) == (trigger.kind, trigger.key)
            and t.state == "promoted"
        ]
        if not scoped:
            return False
        signatures = {
            t.template_id: signature_sha(
                context_signature(**basis, desired_facts=[str(f) for f, _ in t.desired])
            )
            for t in scoped
        }
        habit = next((t for t in scoped if signatures[t.template_id] == t.signature_sha), None)
        if habit is None:
            # The habit does not apply here: no penalty, System 2 stays open.
            record(
                "habit_not_applicable",
                {
                    "template_ids": sorted(signatures),
                    "trigger_key_full": full_key(trigger),
                    "observed": {tid: sha for tid, sha in sorted(signatures.items())},
                    "experienced_tick": now,
                },
            )
            return False
        if self.adopted is not None:
            return False  # one temporary goal at a time; the ordinary path decides
        # The same relevance a deliberation's answer must pass.
        if trigger.source_goal_id is not None and trigger.source_goal_id not in goals.entries:
            return False
        if trigger.source_project is not None and not any(
            p.project_id == trigger.source_project and p.status in OPEN_PROJECTS
            for p in projects.projects()
        ):
            return False
        if habit.goal_type not in goal_types:
            return False
        triples = []
        for fact, direction in habit.desired:
            if fact not in state:
                return False
            triple = condition_for(str(fact), str(direction), state)
            if triple is None:
                return False
            triples.append(triple)
        conditions = tuple(_condition(f, op, v) for f, op, v in triples)
        visible = [c for c in conditions if c.fact not in ACTION_FACTS]
        self.invoked_for[habit.template_id] = trigger
        if visible and len(visible) == len(conditions) and all(c.holds(state) for c in visible):
            # The problem is here and what the habit aims at already holds:
            # the habit's account of this problem is wrong.
            self.tracker.demote(habit, "satisfied_at_invocation", now, record)
            return True
        plans = [
            plan
            for plan in plan_for(
                state, conditions, registry=registry, limit=1, recovery=tuple(RECOVERY_SKILLS)
            )
            if plan.steps
        ]
        if not plans:
            self.tracker.demote(habit, "infeasible_at_invocation", now, record)
            return True
        invocation = self.new_invocation_id()
        goal_id = f"goal_habit_{invocation}"
        priority, priority_source = band(trigger)
        record(
            "habit_invoked",
            {
                "template_id": habit.template_id,
                "habit_invocation_id": invocation,
                "trigger_kind": trigger.kind,
                "trigger_key": trigger.key,
                "trigger_key_full": full_key(trigger),
                "goal_id": goal_id,
                "goal_type": habit.goal_type,
                "conditions": [list(t) for t in triples],
                "priority": priority,
                "priority_source": priority_source,
                "experienced_tick": now,
            },
        )
        self.tracker.open(
            Episode(
                deliberation_id=invocation,
                template=habit.body(),
                semantic_key_full=full_key(trigger),
                life_epoch=self.tracker_life_epoch,
                world_epoch=self.world_epoch,
                session=self.tracker_session,
                source_goal_id=trigger.source_goal_id,
                via="habit",
            )
        )
        self.adopted = self._adoption(
            invocation,
            goal_id,
            habit.goal_type,
            tuple(triples),
            priority,
            now,
            trigger,
            goals,
            via="habit",
            template_id=habit.template_id,
        )
        return True

    def habit_broke(self, template: Template, reason: str, now: int) -> None:
        """A habit was demoted: its problem goes back to System 2 at once,
        bypassing the original trigger's threshold and cooldown, though not
        the budgets, the in-flight limit or any emergency (ADR 0022, C5)."""
        problem = self.invoked_for.pop(template.template_id, None)
        breakdown = Trigger(
            "habit_breakdown",
            template.template_id,
            {
                "origin_kind": template.trigger_kind,
                "origin_key": template.semantic_key,
                "reason": reason,
            },
            source_goal_id=problem.source_goal_id if problem is not None else None,
            source_priority=problem.source_priority if problem is not None else None,
            source_project=problem.source_project if problem is not None else None,
        )
        self.pending[full_key(breakdown)] = breakdown

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
            if adopted.via == "habit":
                record(
                    "habit_goal_ended",
                    {
                        "template_id": adopted.template_id,
                        "habit_invocation_id": adopted.deliberation_id,
                        "goal_id": adopted.goal_id,
                        "why": why,
                        "experienced_tick": now,
                    },
                )
            else:
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
            if self.tracker is not None:
                self.tracker.goal_ended(adopted.deliberation_id, why, now, record)
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
            source=adopted.via,
            created_at_tick=tick,
            status="QUEUED",
            completion_condition=tuple(_condition(f, op, v) for f, op, v in adopted.conditions),
            reason_codes=(adopted.via,),
            base_priority=adopted.priority,
            planning_profile="recovery",
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
