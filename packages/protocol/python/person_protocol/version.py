"""Wire contract identity shared by the Node runtime and the cognition process."""

from __future__ import annotations

from typing import Final

PROTOCOL_VERSION: Final = "shroud-learning-v2"

NODE_MESSAGE_TYPES: Final[tuple[str, ...]] = (
    "SessionHello",
    "Observation",
    "ValidationDecision",
    "SkillStarted",
    "SkillOutcome",
    "EmergencyEvent",
    "EpisodeEvent",
)

COGNITION_MESSAGE_TYPES: Final[tuple[str, ...]] = (
    "CognitionReady",
    "GoalDecision",
    "PolicyDecision",
    "SkillInvocation",
)

MESSAGE_TYPES: Final[tuple[str, ...]] = NODE_MESSAGE_TYPES + COGNITION_MESSAGE_TYPES

SCHEMA_FILES: Final[dict[str, str]] = {
    "SessionHello": "session-hello.schema.json",
    "Observation": "observation.schema.json",
    "ValidationDecision": "validation-decision.schema.json",
    "SkillStarted": "skill-started.schema.json",
    "SkillOutcome": "skill-outcome.schema.json",
    "EmergencyEvent": "emergency-event.schema.json",
    "EpisodeEvent": "episode-event.schema.json",
    "CognitionReady": "cognition-ready.schema.json",
    "GoalDecision": "goal-decision.schema.json",
    "PolicyDecision": "policy-decision.schema.json",
    "SkillInvocation": "skill-invocation.schema.json",
}

TERMINAL_STATUSES: Final[tuple[str, ...]] = (
    "SUCCESS",
    "FAILED",
    "INTERRUPTED",
    "PREEMPTED",
    "TIMED_OUT",
    "INVALIDATED",
    "UNREACHABLE",
    "DEATH",
    "DISCONNECTED",
)

LEARNING_MODES: Final[tuple[str, ...]] = ("off", "shadow", "supervised")
TRAINING_CONTEXTS: Final[tuple[str, ...]] = (
    "fixture",
    "minecraft_peaceful",
    "minecraft_normal",
    "replay",
)
