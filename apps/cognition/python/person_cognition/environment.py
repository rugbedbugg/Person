"""What cognition needs from an environment, and how it finds one (ADR 0025).

Person's cognition is environment-neutral. Everything it must know about the
world it lives in arrives through this contract, implemented by an
environment profile (Minecraft's: `person_minecraft.profile`). The loop finds
the profile through the environment's manifest when the runtime's
SessionHello names the environment; no module in this package imports any
environment, and an architecture test holds it to that.

Every method takes a view from the epistemic side of the boundary
(`PerceptualState`, `DecisionState`), never a raw observation (ADR 0026).
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from person_epistemics import DecisionState, EpistemicEvidence, PerceptualState
from person_policy import EnvelopeVerdict
from person_protocol import environment
from person_skills import SkillRegistry

from .affect import GoalCharacter
from .goals import Drive, Goal
from .interoception import BodyReading
from .memory.episodes import EpisodeDraft
from .projects import Template

Percepts = PerceptualState[Any]
Decision = DecisionState[Any, BodyReading]


class DecisionContextLike(Protocol):
    def identifier(self) -> str: ...

    def as_dict(self) -> dict[str, str]: ...


class CognitiveEnvironment(Protocol):
    kind: str
    goal_types: tuple[str, ...]
    project_templates: tuple[Template, ...]

    # The epistemic boundary.
    def perceive(self, observation: Mapping[str, Any]) -> Percepts: ...
    def belief_evidence(self, state: Percepts, now: int) -> tuple[EpistemicEvidence, ...]: ...
    def body(self, state: Percepts) -> BodyReading: ...
    def skills(self) -> SkillRegistry: ...

    # Deciding.
    def planning_facts(self, decision: Decision) -> dict[str, float]: ...
    def decision_context(self, decision: Decision) -> DecisionContextLike: ...
    def drives(self, decision: Decision, state: dict[str, float]) -> list[Drive]: ...
    #: Whether a goal with this completion condition is protective or outgoing,
    #: for affect's bias (ADR 0010). The environment owns its facts' meaning.
    def goal_character(self, completion_facts: frozenset[str]) -> GoalCharacter: ...
    def propose_goals(
        self, decision: Decision, state: dict[str, float], tick: int
    ) -> list[Goal]: ...
    def idle_goal(self, tick: int) -> Goal: ...
    def envelope(self, decision: Decision) -> EnvelopeVerdict: ...
    def night(self, state: Percepts) -> bool: ...
    def threat(self, state: Percepts) -> float: ...
    def evidence_percepts(self, state: Percepts) -> dict[str, list[dict[str, Any]]]: ...
    def recognised_evidence(self, state: Percepts) -> dict[str, float]: ...

    # Memory.
    def noticed(self, state: Percepts) -> dict[str, list[Mapping[str, Any]]]: ...
    def seen(self, state: Percepts) -> dict[str, EpisodeDraft]: ...
    def skill_subjects(self, skill_id: str, registry: SkillRegistry) -> tuple[str, ...]: ...
    def evidence_subjects(self, facts: Iterable[str]) -> frozenset[str]: ...
    #: What an emergency is about beyond `danger`, which every emergency is.
    def emergency_subjects(self, trigger: str) -> tuple[str, ...]: ...
    def health(self, state: Percepts) -> float: ...
    def last_felt(self, state: Percepts | None) -> tuple[float | None, float | None, bool]: ...

    # Causes, and deliberation.
    def conditions(self, state: Percepts) -> dict[str, str]: ...
    def situation(self, state: Percepts | None) -> list[dict[str, Any]]: ...
    def signature_basis(self, state: Percepts | None) -> Any: ...
    def context_signature(self, **basis: Any) -> dict[str, Any]: ...

    # Offline: the validation harness's effect comparison (no loop, no store).
    def compare_effects(self, request: Mapping[str, Any]) -> dict[str, Any]: ...


class EnvironmentUnavailable(LookupError):
    """No cognition profile is installed for this environment."""


def load_environment(kind: str) -> CognitiveEnvironment:
    """The cognition profile an installed environment declares in its manifest."""
    manifest = environment(kind)
    entry = manifest.cognition_entry
    if entry is None:
        raise EnvironmentUnavailable(f"environment {kind!r} declares no cognition profile")
    module_name, _, attribute = entry.partition(":")
    profile: CognitiveEnvironment = getattr(importlib.import_module(module_name), attribute)
    if profile.kind != kind:
        raise EnvironmentUnavailable(f"{entry} implements {profile.kind!r}, not {kind!r}")
    return profile
