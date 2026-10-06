"""The Minecraft environment profile, cognition side (ADR 0025).

Person's cognition is environment-neutral; this object is everything it needs
to know about Minecraft, behind the `CognitiveEnvironment` contract
(`person_cognition.environment`). The loop finds it through the manifest
(`environment.json`, `cognition.python`) when the runtime's SessionHello names
the environment, so no core module imports this package.

Every method reads a view on the epistemic side of the boundary: a
`PerceptualState` of `MinecraftPercepts`, or a `DecisionState`. None reads a
raw observation, and none can see a `WorldSnapshot`, which never crosses to
cognition at all (ADR 0002).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from person_cognition.affect import GoalCharacter
from person_cognition.goals import Drive, Goal
from person_cognition.interoception import BodyReading
from person_cognition.memory.episodes import EpisodeDraft
from person_cognition.projects import Template
from person_epistemics import (
    DecisionState,
    EpistemicEvidence,
    PerceptualState,
)
from person_policy import EnvelopeVerdict
from person_skills import SkillRegistry, skill_registry

from . import body, causal, context, facts, goals, memory, situation
from .beliefs import belief_evidence
from .envelope import safe_envelope
from .perception import MinecraftPercepts, perceive
from .projects import TEMPLATES

Percepts = PerceptualState[MinecraftPercepts]
Decision = DecisionState[MinecraftPercepts, BodyReading]


class MinecraftProfile:
    kind = "minecraft"
    #: Every goal type a Minecraft Person may hold, the core's included.
    goal_types: tuple[str, ...] = goals.GOAL_TYPES
    project_templates: tuple[Template, ...] = TEMPLATES
    context_signature = staticmethod(situation.context_signature)

    def __init__(self) -> None:
        self.goal_provider = goals.SurvivalGoalProvider()

    # --------------------------------------------------------------- the boundary

    def perceive(self, observation: Mapping[str, Any]) -> Percepts:
        return perceive(observation)

    def belief_evidence(self, state: Percepts, now: int) -> tuple[EpistemicEvidence, ...]:
        return belief_evidence(state, now)

    def body(self, state: Percepts) -> BodyReading:
        return body.body_reading(state.percepts)

    def skills(self) -> SkillRegistry:
        return skill_registry(self.kind)

    # ------------------------------------------------------------------ deciding

    def planning_facts(self, decision: Decision) -> dict[str, float]:
        return facts.planning_facts(decision)

    def decision_context(self, decision: Decision) -> context.DecisionContext:
        return context.decision_context(decision)

    def drives(self, decision: Decision, state: dict[str, float]) -> list[Drive]:
        return goals.homeostasis(decision, state)

    def goal_character(self, completion_facts: frozenset[str]) -> GoalCharacter:
        return goals.goal_character(completion_facts)

    def propose_goals(self, decision: Decision, state: dict[str, float], tick: int) -> list[Goal]:
        return self.goal_provider.propose(decision, state, tick)

    def idle_goal(self, tick: int) -> Goal:
        return goals.idle_goal(tick)

    def envelope(self, decision: Decision) -> EnvelopeVerdict:
        return safe_envelope(decision)

    def night(self, state: Percepts) -> bool:
        return state.percepts.night

    def threat(self, state: Percepts) -> float:
        return body.threat_intensity(state.percepts)

    def evidence_percepts(self, state: Percepts) -> dict[str, list[dict[str, Any]]]:
        return facts.evidence_percepts(state.percepts)

    def recognised_evidence(self, state: Percepts) -> dict[str, float]:
        return facts.evidence_facts(state)

    # -------------------------------------------------------------------- memory

    def noticed(self, state: Percepts) -> dict[str, list[Mapping[str, Any]]]:
        return memory.noticed(state.percepts)

    def seen(self, state: Percepts) -> dict[str, EpisodeDraft]:
        """For each subject in view, the episode of having seen it."""
        return {
            subject: memory.perceived(state.percepts, subject, percepts)
            for subject, percepts in memory.noticed(state.percepts).items()
        }

    def skill_subjects(self, skill_id: str, registry: SkillRegistry) -> tuple[str, ...]:
        return memory.skill_subjects(skill_id, registry)

    def evidence_subjects(self, facts_: Iterable[str]) -> frozenset[str]:
        return memory.evidence_subjects(facts_)

    def emergency_subjects(self, trigger: str) -> tuple[str, ...]:
        return memory.emergency_subjects(trigger)

    def health(self, state: Percepts) -> float:
        return float(state.percepts.vitals["health"])

    def last_felt(self, state: Percepts | None) -> tuple[float | None, float | None, bool]:
        """Health, food, and whether a threat was in view, as last perceived."""
        if state is None:
            return None, None, False
        percepts = state.percepts
        threat = bool(percepts.nearby["hostiles"])
        return float(percepts.vitals["health"]), float(percepts.vitals["food"]), threat

    # -------------------------------------------------------------------- causes

    def conditions(self, state: Percepts) -> dict[str, str]:
        return causal.conditions(state.percepts)

    # -------------------------------------------------------------- deliberation

    def situation(self, state: Percepts | None) -> list[dict[str, Any]]:
        return situation.situation_facts(None if state is None else state.percepts)

    def signature_basis(self, state: Percepts | None) -> MinecraftPercepts | None:
        return None if state is None else state.percepts

    # ------------------------------------------------------------------ offline

    def compare_effects(self, request: Mapping[str, Any]) -> dict[str, Any]:
        from .effects import run

        return run(request)


profile = MinecraftProfile()
