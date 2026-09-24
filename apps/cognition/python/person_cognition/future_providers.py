"""Interfaces reserved for later milestones.

Nothing in this module is implemented. These are the seams the future systems
will attach to, written down now so that the cognition and execution boundary
does not have to be renegotiated when they arrive. Each one is intentionally
tiny: a speculative abstraction that guesses wrong is worse than no abstraction.

Any attempt to use one raises, rather than returning a plausible-looking empty
result that could be mistaken for a working implementation.

Memory used to be reserved here, as `MemoryProvider.retrieve(query, limit)`.
It is implemented now, in `person_cognition.memory`, and deliberately not with
that signature: an arbitrary query with a caller-chosen limit is the database
access ADR 0003 forbids. Recall takes a typed `Cue` (ADR 0007).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class NotYetImplemented(NotImplementedError):
    """Raised by the placeholder providers. Future scope, not current scope."""

    def __init__(self, provider: str, milestone: str) -> None:
        super().__init__(
            f"{provider} is a future interface; it is scheduled for {milestone} "
            "and has no implementation in this milestone."
        )


@runtime_checkable
class WorldModelProvider(Protocol):
    """Descriptive world state plus predictive and causal beliefs."""

    def observe(self, event: dict[str, Any]) -> None: ...

    def predict(
        self, state: dict[str, float], candidate_action: dict[str, Any]
    ) -> dict[str, Any]: ...

    def update(self, prediction: dict[str, Any], outcome: dict[str, Any]) -> None: ...

    def query(self, belief: str) -> dict[str, Any] | None: ...


@runtime_checkable
class AffectProvider(Protocol):
    """Appraisal and persistent computational affect."""

    def update(self, event: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class LanguageProvider(Protocol):
    """Advisory language services. Never authoritative over identity or action."""

    def interpret_message(self, message: str, speaker: str) -> dict[str, Any]: ...

    def generate_reply(self, intent: dict[str, Any]) -> str: ...


@runtime_checkable
class SocialProvider(Protocol):
    """Players, relationships, incidents and commitments."""

    def observe_interaction(self, event: dict[str, Any]) -> None: ...

    def relationship(self, player: str) -> dict[str, Any]: ...


@runtime_checkable
class ProjectProvider(Protocol):
    """Long-term projects with milestones and suspended state."""

    def active_projects(self) -> list[dict[str, Any]]: ...

    def advance(self, project_id: str, outcome: dict[str, Any]) -> None: ...


@runtime_checkable
class ExplorationProvider(Protocol):
    """Epistemic exploration: what is worth finding out, and how safely."""

    def propose_experiment(self, state: dict[str, float]) -> dict[str, Any] | None: ...


class UnimplementedWorldModelProvider:
    milestone = "Phase 6, persistent and predictive world"

    def observe(self, event: dict[str, Any]) -> None:
        raise NotYetImplemented("WorldModelProvider", self.milestone)

    def predict(self, state: dict[str, float], candidate_action: dict[str, Any]) -> dict[str, Any]:
        raise NotYetImplemented("WorldModelProvider", self.milestone)

    def update(self, prediction: dict[str, Any], outcome: dict[str, Any]) -> None:
        raise NotYetImplemented("WorldModelProvider", self.milestone)

    def query(self, belief: str) -> dict[str, Any] | None:
        raise NotYetImplemented("WorldModelProvider", self.milestone)


class UnimplementedAffectProvider:
    milestone = "Phase 10, affect"

    def update(self, event: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        raise NotYetImplemented("AffectProvider", self.milestone)


class UnimplementedLanguageProvider:
    milestone = "Phase 9, language"

    def interpret_message(self, message: str, speaker: str) -> dict[str, Any]:
        raise NotYetImplemented("LanguageProvider", self.milestone)

    def generate_reply(self, intent: dict[str, Any]) -> str:
        raise NotYetImplemented("LanguageProvider", self.milestone)


class UnimplementedSocialProvider:
    milestone = "Phase 8, social identity"

    def observe_interaction(self, event: dict[str, Any]) -> None:
        raise NotYetImplemented("SocialProvider", self.milestone)

    def relationship(self, player: str) -> dict[str, Any]:
        raise NotYetImplemented("SocialProvider", self.milestone)


class UnimplementedProjectProvider:
    milestone = "Phase 11, autonomous projects"

    def active_projects(self) -> list[dict[str, Any]]:
        raise NotYetImplemented("ProjectProvider", self.milestone)

    def advance(self, project_id: str, outcome: dict[str, Any]) -> None:
        raise NotYetImplemented("ProjectProvider", self.milestone)


class UnimplementedExplorationProvider:
    milestone = "Phase 6, active experimentation"

    def propose_experiment(self, state: dict[str, float]) -> dict[str, Any] | None:
        raise NotYetImplemented("ExplorationProvider", self.milestone)


FUTURE_PROVIDERS = {
    "WorldModelProvider": UnimplementedWorldModelProvider,
    "AffectProvider": UnimplementedAffectProvider,
    "LanguageProvider": UnimplementedLanguageProvider,
    "SocialProvider": UnimplementedSocialProvider,
    "ProjectProvider": UnimplementedProjectProvider,
    "ExplorationProvider": UnimplementedExplorationProvider,
}
