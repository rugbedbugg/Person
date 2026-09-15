"""The cognition process.

Reads normalised observations, decides what Person should be trying to do and
which known strategy to try, and proposes one bounded skill at a time. It never
touches Minecraft: the only thing it can emit that has physical consequences is
a SkillInvocation, which the runtime is free to reject or replace.

Everything the process learns from is the outcome the runtime reports, and the
outcome says what actually ran.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from person_config import CognitionSettings
from person_persistence import EvidenceEvent, EvidenceStore, new_event
from person_planner import plan_for, symbolic_state
from person_policy import (
    DeterministicPolicyProvider,
    EvidencePolicyProvider,
    NoCandidatesError,
    PolicyChoice,
    RoutineStatistics,
)
from person_protocol import (
    ProtocolValidator,
    SessionIdentity,
    encode_frame,
    envelope,
    protocol_validator,
)
from person_skills import SkillRegistry, skill_registry

from .context import decision_context
from .goals import Goal, GoalStack, SurvivalGoalProvider
from .prediction import PendingPrediction, build_payload
from .reporting import LearningSummary
from .routines import (
    Routine,
    RoutineLibrary,
    SkillStep,
    candidate_from_routine,
    routine_from_plan,
)

COGNITION_VERSION = "0.1.0"
MAX_CANDIDATES = 6

FAILURE_STATUSES = {"FAILED", "TIMED_OUT", "UNREACHABLE", "INVALIDATED", "DEATH", "DISCONNECTED"}
INTERRUPT_STATUSES = {"INTERRUPTED", "PREEMPTED"}


@dataclass
class ActiveRoutine:
    routine: Routine
    goal_id: str
    context_id: str
    steps: tuple[SkillStep, ...]
    index: int = 0
    started_tick: int = 0
    health_cost: float = 0.0
    resource_cost: float = 0.0
    elapsed_ticks: int = 0
    failure_modes: list[str] = field(default_factory=list)
    recovered: bool = False

    @property
    def finished(self) -> bool:
        return self.index >= len(self.steps)

    def current(self) -> SkillStep | None:
        return self.steps[self.index] if not self.finished else None


class CognitionLoop:
    def __init__(
        self,
        *,
        settings: CognitionSettings | None = None,
        registry: SkillRegistry | None = None,
        write: Callable[[str], None] | None = None,
        log: Callable[[str], None] | None = None,
        evidence_directory: Path | None = None,
        validator: ProtocolValidator | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry or skill_registry()
        self.validator = validator or protocol_validator()
        self._write = write or (lambda line: sys.stdout.write(line))
        self._log = log or (lambda line: sys.stderr.write(line + "\n"))
        self.statistics = RoutineStatistics()
        self.goal_provider = SurvivalGoalProvider()
        self.goals = GoalStack()
        self.library = RoutineLibrary()
        self.summary = LearningSummary()
        self.identity: SessionIdentity | None = None
        self.episode_id = "ep_unstarted"
        self.learning_mode = "off"
        self.training_context = "fixture"
        self.policy_revision = 0
        self.rng_seed: int | None = None
        self.store: EvidenceStore | None = None
        self.evidence_directory = evidence_directory
        self.active: ActiveRoutine | None = None
        self.previous_event_id: str | None = None
        self.decision_counter = 0
        self.pending_decision_id: str | None = None
        self.running = True
        self.restore_notes: list[str] = []
        self.consecutive_failures: dict[str, int] = {}
        self._pending_choice: PolicyChoice | None = None
        #: One prediction at a time: the runtime runs one skill at a time.
        self.pending_prediction: PendingPrediction | None = None
        self.prediction_errors: list[dict[str, Any]] = []
        self._last_state: dict[str, float] = {}

    # ------------------------------------------------------------------ utils

    def _send(self, message: dict[str, Any]) -> None:
        valid, diagnostics = self.validator.validate(message)
        if not valid:
            # Refusing to emit an invalid message is the cognition-side half of
            # the contract; the runtime would drop it anyway.
            self._log(f"cognition refused to send invalid {message.get('type')}: {diagnostics}")
            return
        self._write(encode_frame(message))

    def _envelope(self, message_type: str, tick: int) -> dict[str, Any]:
        identity = self.identity or SessionIdentity("unknown", "0" * 8, "unknown")
        return envelope(identity, message_type, tick)

    def _record(
        self,
        event_type: str,
        tick: int,
        payload: dict[str, Any],
        decision_id: str | None = None,
    ) -> EvidenceEvent | None:
        if self.store is None or self.identity is None:
            return None
        event = new_event(
            person_id=self.identity.person_id,
            world_id=self.identity.world_id,
            session_id=self.identity.session_id,
            episode_id=self.episode_id,
            decision_id=decision_id,
            tick=tick,
            policy_revision=self.policy_revision,
            training_context=self.training_context,
            event_type=event_type,
            payload=payload,
            previous_event_id=self.previous_event_id,
        )
        self.store.append(event, self.statistics)
        self.previous_event_id = event.event_id
        return event

    def _policy(self) -> DeterministicPolicyProvider | EvidencePolicyProvider:
        if self.learning_mode == "off" and self.settings is None:
            return DeterministicPolicyProvider(self.policy_revision)
        return EvidencePolicyProvider(
            self.statistics,
            training_context=self.training_context,
            learning_mode=self.learning_mode,
            minimum_support=self.settings.minimum_support if self.settings else 3,
            exploration_bonus=self.settings.exploration_bonus if self.settings else 0.15,
            policy_revision=self.policy_revision,
        )

    # -------------------------------------------------------------- dispatch

    def handle(self, message: dict[str, Any]) -> None:
        handler = {
            "SessionHello": self.on_session_hello,
            "Observation": self.on_observation,
            "ValidationDecision": self.on_validation,
            "SkillStarted": self.on_skill_started,
            "SkillOutcome": self.on_skill_outcome,
            "EmergencyEvent": self.on_emergency,
            "EpisodeEvent": self.on_episode_event,
        }.get(str(message.get("type")))
        if handler is None:
            self._log(f"cognition ignored unexpected message type {message.get('type')}")
            return
        handler(message)

    # ---------------------------------------------------------------- session

    def on_session_hello(self, message: dict[str, Any]) -> None:
        self.identity = SessionIdentity(
            person_id=message["personId"],
            session_id=message["sessionId"],
            world_id=message["worldId"],
        )
        self.learning_mode = message["learningMode"]
        self.training_context = message["trainingContext"]
        self.policy_revision = message["policyRevision"]
        self.rng_seed = message["rngSeed"]
        directory = self.evidence_directory or Path(message["evidenceDirectory"])
        if self.settings is not None:
            self.settings.cross_check(
                learning_mode=self.learning_mode,
                evidence_directory=message["evidenceDirectory"],
            )
        if message["skillLibraryRevision"] != self.registry.revision:
            self._log(
                "skill library revision mismatch: runtime "
                f"{message['skillLibraryRevision']} vs cognition {self.registry.revision}"
            )
        self.store = EvidenceStore(
            directory,
            snapshot_every=self.settings.snapshot_every_events if self.settings else 50,
        )
        report = self.store.restore(self.statistics)
        self.restore_notes = list(report.notes)
        self.previous_event_id = self.store.last_event_id
        self.policy_revision = max(self.policy_revision, self.store.policy_revision)
        for note in report.notes:
            self._log(f"evidence restore: {note}")
        self._send(
            {
                **self._envelope("CognitionReady", message["tick"]),
                "type": "CognitionReady",
                "cognitionVersion": COGNITION_VERSION,
                "policyRevision": self.policy_revision,
                "learningMode": self.learning_mode,
                "restoredEvents": report.replayed_events,
                "restoredRoutines": len(self.statistics.routines),
                "snapshotTick": report.snapshot_tick,
            }
        )

    def on_episode_event(self, message: dict[str, Any]) -> None:
        self.episode_id = message["episodeId"]
        self._record(
            "episode_started" if message["phase"] == "started" else "episode_ended",
            message["tick"],
            {
                "reason_codes": message["reasonCodes"],
                "rng_seed": message["rngSeed"],
                "training_context": message["trainingContext"],
                "learning_mode": self.learning_mode,
            },
        )
        if message["phase"] == "ended":
            self._settle_prediction(None, message["tick"])
            self._finish_routine("INTERRUPTED", message["tick"], reason="episode_ended")
            if self.store is not None:
                self.store.write_snapshot(self.statistics)
                self.summary.write(
                    self.store.directory,
                    statistics=self.statistics,
                    episode_id=self.episode_id,
                    learning_mode=self.learning_mode,
                    training_context=self.training_context,
                    policy_revision=self.policy_revision,
                    goals=self.goals,
                    restore_notes=self.restore_notes,
                )
            self.running = False

    # ------------------------------------------------------------ observation

    def on_observation(self, message: dict[str, Any]) -> None:
        tick = message["tick"]
        state = symbolic_state(message)
        context = decision_context(message)
        context_id = context.identifier()
        # The first thing a new observation is good for is settling whatever
        # the last skill claimed it would do.
        self._settle_prediction(state, tick)
        self._last_state = dict(state)

        proposals = self.goal_provider.propose(message, state, tick)
        goal = self.goals.update(proposals, state, tick)
        if goal is None:
            goal = self._idle_goal(tick)
            self.goals.update([goal], state, tick)
            goal = self.goals.active or goal

        if self.active is not None and (
            self.active.goal_id != goal.goal_id or self.active.finished
        ):
            self._finish_routine(
                "SUCCESS" if self.active.finished else "INTERRUPTED",
                tick,
                reason="goal_changed" if not self.active.finished else "routine_complete",
            )

        if self.active is None and not self._start_routine(message, state, context_id, goal, tick):
            return
        assert self.active is not None

        step = self.active.current()
        if step is None:
            self._finish_routine("SUCCESS", tick, reason="routine_complete")
            if not self._start_routine(message, state, context_id, goal, tick):
                return
            step = self.active.current() if self.active else None
        if step is None:
            self._emit_idle(message, goal, context_id, tick)
            return

        spec = self.registry.get(step.skill_id)
        if not spec.applicable(state):
            # The world moved on. Abandon the routine rather than sending a
            # proposal the runtime would only reject.
            self.active.failure_modes.append("preconditions_changed")
            self._finish_routine("INVALIDATED", tick, reason="preconditions_changed")
            if not self._start_routine(message, state, context_id, goal, tick):
                return
            step = self.active.current() if self.active else None
            if step is None:
                self._emit_idle(message, goal, context_id, tick)
                return
            spec = self.registry.get(step.skill_id)

        self._emit_decision(message, goal, context_id, step, spec, tick)

    def _idle_goal(self, tick: int) -> Goal:
        from person_skills import Condition

        return Goal(
            goal_id="goal_maintain_reserves",
            goal_type="MAINTAIN_RESERVES",
            priority=10.0,
            source="maintenance",
            created_at_tick=tick,
            status="QUEUED",
            completion_condition=(Condition("rested", ">=", 1),),
            reason_codes=("nothing_urgent",),
        )

    def _start_routine(
        self,
        observation: dict[str, Any],
        state: dict[str, float],
        context_id: str,
        goal: Goal,
        tick: int,
    ) -> bool:
        plans = plan_for(
            state, goal.completion_condition, registry=self.registry, limit=MAX_CANDIDATES
        )
        plans = [plan for plan in plans if plan.steps]
        if not plans:
            self.goals.block(goal.goal_id, "no_feasible_plan", tick)
            self._emit_idle(observation, goal, context_id, tick)
            return False
        routines = [self.library.add(routine_from_plan(goal.goal_type, plan)) for plan in plans]
        candidates = [
            candidate_from_routine(routine, self.library, state, self.registry)
            for routine in routines
        ]
        try:
            choice = self._policy().propose(observation, goal, candidates, context_id)
        except NoCandidatesError:
            self.goals.block(goal.goal_id, "no_candidate_routine", tick)
            self._emit_idle(observation, goal, context_id, tick)
            return False
        chosen = next(
            (routine for routine in routines if routine.routine_id == choice.routine_id),
            routines[0],
        )
        self.active = ActiveRoutine(
            routine=chosen,
            goal_id=goal.goal_id,
            context_id=context_id,
            steps=tuple(self.library.expand(chosen)),
            started_tick=tick,
        )
        self._pending_choice = choice
        self._record(
            "routine_selected",
            tick,
            {
                "routine_id": chosen.routine_id,
                "routine_name": chosen.name,
                "goal_id": goal.goal_id,
                "goal_type": goal.goal_type,
                "context_id": context_id,
                "steps": [step.label() for step in self.active.steps],
                "learned_or_fallback": choice.learned_or_fallback,
                "confidence": choice.confidence,
                "reason_codes": list(choice.reason_codes),
                "shadow_routine_id": choice.shadow_routine_id,
                "candidates": [
                    {
                        "routine_id": scored.candidate.routine_id,
                        "score": round(scored.score, 6),
                        "attempts": scored.counts.attempts,
                        "successes": scored.counts.successes,
                    }
                    for scored in choice.candidates
                ],
            },
        )
        self.summary.note_selection(choice)
        return True

    def _emit_decision(
        self,
        observation: dict[str, Any],
        goal: Goal,
        context_id: str,
        step: SkillStep,
        spec: Any,
        tick: int,
    ) -> None:
        assert self.active is not None
        self.decision_counter += 1
        decision_id = _decision_uuid(self.decision_counter, self.identity)
        self.pending_decision_id = decision_id
        choice: PolicyChoice = self._pending_choice or self._policy().propose(
            observation,
            goal,
            [candidate_from_routine(self.active.routine, self.library, {}, self.registry)],
            context_id,
        )

        self._record(
            "goal_selected",
            tick,
            {
                "goal_id": goal.goal_id,
                "goal_type": goal.goal_type,
                "priority": goal.priority,
                "context_id": context_id,
                "reason_codes": list(goal.reason_codes),
                "stack": [entry["goalId"] for entry in self.goals.as_messages()],
            },
            decision_id,
        )

        self._send(
            {
                **self._envelope("GoalDecision", tick),
                "type": "GoalDecision",
                "decisionId": decision_id,
                "goal": (self.goals.active or goal).as_message(),
                "reasonCodes": list(goal.reason_codes)[:32],
                "stack": self.goals.as_messages()[:32],
            }
        )
        self._send(
            {
                **self._envelope("PolicyDecision", tick),
                "type": "PolicyDecision",
                "decisionId": decision_id,
                "goalId": goal.goal_id,
                "contextId": context_id,
                "routineId": self.active.routine.routine_id,
                "routineName": self.active.routine.name,
                "steps": [item.skill_id for item in self.active.steps][:32],
                "confidence": round(min(1.0, max(0.0, choice.confidence)), 6),
                "reasonCodes": list(choice.reason_codes)[:32],
                "evidenceRefs": list(choice.evidence_refs)[:64],
                "policyRevision": self.policy_revision,
                "learnedOrFallback": choice.learned_or_fallback,
                "candidates": [
                    {
                        "routineId": scored.candidate.routine_id,
                        "routineName": scored.candidate.name,
                        "score": round(scored.score, 6),
                        "attempts": scored.counts.attempts,
                        "successes": scored.counts.successes,
                        "meanSuccess": round(scored.counts.posterior_mean, 6),
                    }
                    for scored in choice.candidates[:32]
                ],
                "shadowRoutineId": choice.shadow_routine_id,
            }
        )
        # The state a prediction is measured against is the one the planner
        # reasoned over, captured before anything physical happens.
        self.pending_prediction = PendingPrediction(
            decision_id=decision_id,
            context_id=context_id,
            routine_id=self.active.routine.routine_id,
            goal_id=goal.goal_id,
            requested_skill=step.skill_id,
            state_before=dict(self._last_state),
            tick=tick,
        )
        self._send(
            {
                **self._envelope("SkillInvocation", tick),
                "type": "SkillInvocation",
                "decisionId": decision_id,
                "goalId": goal.goal_id,
                "routineId": self.active.routine.routine_id,
                "routineStepIndex": min(self.active.index, 63),
                "skillId": step.skill_id,
                "skillVersion": spec.version,
                "parameters": step.parameter_map or spec.default_parameters(),
                "limits": {
                    "maxTicks": spec.max_ticks,
                    "maxDistance": spec.max_distance,
                    "minHealth": spec.min_health,
                },
            }
        )

    def _emit_idle(
        self, observation: dict[str, Any], goal: Goal, context_id: str, tick: int
    ) -> None:
        """Nothing is planned, so wait safely rather than stall the runtime."""
        spec = self.registry.get("wait_safely")
        self.active = ActiveRoutine(
            routine=Routine(
                routine_id="r_idle_wait",
                name="idle__wait_safely",
                goal_type=goal.goal_type,
                elements=(SkillStep("wait_safely"),),
                risk=spec.risk,
                cost=1.0,
                ticks=spec.max_ticks,
            ),
            goal_id=goal.goal_id,
            context_id=context_id,
            steps=(SkillStep("wait_safely"),),
            started_tick=tick,
        )
        self.library.add(self.active.routine)
        self._pending_choice = DeterministicPolicyProvider(self.policy_revision).propose(
            observation,
            goal,
            [candidate_from_routine(self.active.routine, self.library, {}, self.registry)],
            context_id,
        )
        self._emit_decision(observation, goal, context_id, self.active.steps[0], spec, tick)

    # -------------------------------------------------------------- feedback

    def on_validation(self, message: dict[str, Any]) -> None:
        if message["decision"] in {"REJECT", "REPLACE"}:
            self.summary.note_override(message["decision"], message["reasonCodes"])

    def on_skill_started(self, message: dict[str, Any]) -> None:
        self._record(
            "skill_started",
            message["tick"],
            {
                "requested_skill": message["requestedSkill"],
                "executed_skill": message["executedSkill"],
                "parameters": dict(message["parameters"]),
                "limits": dict(message["limits"]),
                "context_id": self.active.context_id if self.active else "",
                "routine_id": self.active.routine.routine_id if self.active else "",
                "start_health": message["startHealth"],
                "start_food": message["startFood"],
            },
            message["decisionId"],
        )

    def on_emergency(self, message: dict[str, Any]) -> None:
        self._record(
            "emergency_override",
            message["tick"],
            {
                "level": message["level"],
                "trigger": message["trigger"],
                "action": message["action"],
                "preempted_skill": message["preemptedSkill"],
                "reason_codes": message["reasonCodes"],
                "context_id": self.active.context_id if self.active else "",
                "routine_id": self.active.routine.routine_id if self.active else "",
            },
            message["decisionId"],
        )
        self.summary.note_emergency(message["trigger"])

    def on_skill_outcome(self, message: dict[str, Any]) -> None:
        status = message["status"]
        # An emergency replacement is recorded as an interruption even when the
        # substituted skill succeeded: the routine did not run as planned, and
        # the executed skill still gets its own SUCCESS in the statistics.
        interrupted = (
            status in INTERRUPT_STATUSES
            or message["requestedSkillStatus"] in INTERRUPT_STATUSES
            or message["emergency"]
        )
        event_type = (
            "skill_interrupted"
            if interrupted
            else "skill_completed"
            if status == "SUCCESS"
            else "skill_failed"
        )
        resource_cost = sum(abs(item["delta"]) for item in message["resourceCost"])
        payload = {
            "requested_skill": message["requestedSkill"],
            "executed_skill": message["executedSkill"],
            "requested_status": message["requestedSkillStatus"],
            "status": status,
            "emergency": message["emergency"],
            "context_id": message["contextId"],
            "routine_id": message["routineId"],
            "goal_id": message["goalId"],
            "health_cost": message["healthCost"],
            "resource_cost": resource_cost,
            "elapsed_ticks": message["elapsedTicks"],
            "effects": message["effects"],
            "expected_effects": message["expectedEffects"],
            "inventory_delta": message["inventoryDelta"],
            "failure_modes": [] if status == "SUCCESS" else message["reasonCodes"][:8],
            "completion_evidence": message["completionEvidence"],
            "interrupt_reason": message["interruptReason"],
        }
        event = self._record(event_type, message["tick"], payload, message["decisionId"])
        self.summary.note_outcome(message)

        pending = self.pending_prediction
        if pending is not None and pending.decision_id == message["decisionId"]:
            pending.executed_skill = message["executedSkill"]
            # The effects belong to the skill that actually ran, which is the
            # only thing there is any point predicting.
            pending.expected_effects = tuple(message["expectedEffects"])
            pending.status = status
            pending.emergency = bool(message["emergency"])
            pending.elapsed_ticks = int(message["elapsedTicks"])
            pending.health_cost = float(message["healthCost"])
            pending.settled = True
            if event is not None:
                pending.evidence_refs.append(event.event_id)

        active = self.active
        if active is None:
            return
        active.health_cost += message["healthCost"]
        active.resource_cost += resource_cost
        active.elapsed_ticks += message["elapsedTicks"]

        expected = active.current()
        executed_as_planned = (
            expected is not None
            and message["executedSkill"] == expected.skill_id
            and message["requestedSkill"] == expected.skill_id
        )

        if status == "SUCCESS" and executed_as_planned:
            active.index += 1
            if active.finished:
                self._finish_routine("SUCCESS", message["tick"], reason="all_steps_completed")
            return

        if message["emergency"] or message["requestedSkillStatus"] in INTERRUPT_STATUSES:
            # The runtime took over. The routine is interrupted, not failed, and
            # it recovered if the substituted emergency skill succeeded.
            active.recovered = status == "SUCCESS"
            active.failure_modes.append(message["interruptReason"] or "preempted")
            self._finish_routine("INTERRUPTED", message["tick"], reason="emergency_override")
            return

        if status in FAILURE_STATUSES:
            active.failure_modes.extend(message["reasonCodes"][:4])
            self._finish_routine(status, message["tick"], reason="skill_failed")
            return

        active.failure_modes.append(status.lower())
        self._finish_routine("INTERRUPTED", message["tick"], reason="skill_interrupted")

    def _settle_prediction(self, state: dict[str, float] | None, tick: int) -> None:
        """Record how far the skill contract was from what actually happened.

        This is measurement only. The record never reaches the policy, which is
        why prediction error cannot change behaviour in this milestone even by
        accident: the statistics reducer has no case for it.
        """
        pending = self.pending_prediction
        if pending is None or not pending.settled:
            return
        self.pending_prediction = None
        payload = build_payload(pending, state)
        self.prediction_errors.append(payload)
        self.summary.note_prediction(payload)
        self._record("prediction_error", tick, payload, pending.decision_id)

    def _finish_routine(self, status: str, tick: int, *, reason: str) -> None:
        active = self.active
        self.active = None
        self._pending_choice = None
        if active is None or active.routine.routine_id == "r_idle_wait":
            return
        if status == "SUCCESS":
            self.consecutive_failures.pop(active.goal_id, None)
        elif status != "INTERRUPTED":
            # A goal whose strategies keep failing is blocked rather than
            # retried forever; BLOCKED is a real goal state, and spinning would
            # burn the episode without producing usable evidence.
            failures = self.consecutive_failures.get(active.goal_id, 0) + 1
            self.consecutive_failures[active.goal_id] = failures
            if failures >= 3:
                self.goals.block(active.goal_id, "repeated_routine_failure", tick)
        self._record(
            "routine_outcome",
            tick,
            {
                "routine_id": active.routine.routine_id,
                "routine_name": active.routine.name,
                "goal_id": active.goal_id,
                "context_id": active.context_id,
                "status": status,
                "reason": reason,
                "steps_completed": active.index,
                "steps_total": len(active.steps),
                "health_cost": active.health_cost,
                "resource_cost": active.resource_cost,
                "elapsed_ticks": active.elapsed_ticks,
                "failure_modes": active.failure_modes[:8],
                "recovered": active.recovered,
            },
        )

    # ------------------------------------------------------------------- run

    def run(self, lines: Any) -> None:
        from person_protocol import LineReader, decode_frame
        from person_protocol.framing import FrameError

        reader = LineReader()
        for chunk in lines:
            frames, error = reader.push(chunk)
            if error:
                self._log(f"cognition dropped a frame: {error}")
                continue
            for line in frames:
                try:
                    message = decode_frame(line)
                except FrameError as failure:
                    self._log(f"cognition dropped a malformed frame: {failure}")
                    continue
                valid, diagnostics = self.validator.validate(message)
                if not valid:
                    self._log(f"cognition rejected an invalid message: {diagnostics}")
                    continue
                self.handle(message)
                if not self.running:
                    return


def _decision_uuid(counter: int, identity: SessionIdentity | None) -> str:
    import uuid

    seed = f"{identity.session_id if identity else 'session'}:{counter}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))
