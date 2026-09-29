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

Affect and projects left for the same reason: they are implemented, in
`person_cognition.affect` (ADR 0010) and `person_cognition.projects` (ADR
0009), and neither took the shape reserved for it. A placeholder that outlives
its implementation is a false claim that the capability does not exist.
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


class UnimplementedExplorationProvider:
    milestone = "Phase 6, active experimentation"

    def propose_experiment(self, state: dict[str, float]) -> dict[str, Any] | None:
        raise NotYetImplemented("ExplorationProvider", self.milestone)


FUTURE_PROVIDERS = {
    "WorldModelProvider": UnimplementedWorldModelProvider,
    "LanguageProvider": UnimplementedLanguageProvider,
    "SocialProvider": UnimplementedSocialProvider,
    "ExplorationProvider": UnimplementedExplorationProvider,
}
