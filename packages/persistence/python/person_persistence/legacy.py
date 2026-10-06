"""Compatibility only: what a pre-v20 record's `training_context` meant (ADR 0025).

Before environment profiles existed every record was Minecraft by
construction, and one string folded the environment, the embodiment, the
server difficulty and replay together. This table maps each value to the
experience stream it always meant, so old journals are read without being
rewritten. It is the one place in Person's core that names an environment,
and only because the records it reads predate the distinction; nothing new
is ever written with it.
"""

from __future__ import annotations

from person_epistemics import ExperienceKey

LEGACY_TRAINING_CONTEXTS: dict[str, ExperienceKey] = {
    "fixture": ExperienceKey("minecraft", "fixture", None, "lived"),
    "minecraft_peaceful": ExperienceKey("minecraft", "mineflayer", "peaceful", "lived"),
    "minecraft_normal": ExperienceKey("minecraft", "mineflayer", "normal", "lived"),
    # Reserved before v20 and never produced; read as replay of an unknown body.
    "replay": ExperienceKey("minecraft", "unknown", None, "replay"),
}


def legacy_experience(training_context: str) -> ExperienceKey:
    return LEGACY_TRAINING_CONTEXTS[training_context]
