"""Which experience stream a record belongs to (ADR 0025).

`trainingContext` used to fold four different things into one value:
the environment (Minecraft), the embodiment (fixture or Mineflayer), the
environment's own configuration (peaceful or normal difficulty), and whether
the experience was lived or replayed. They are separate here:

    environment_kind     which environment profile: "minecraft"
    embodiment_kind      which implementation of that environment's body
    environment_variant  an environment-owned token for configuration that
                         changes its dynamics, or None
    context              "lived" or "replay"

A fixture is not another environment: it is another embodiment of the same
one. The world a record happened in is a fourth thing again, the `worldId`
every record already carries.

Statistics, effect beliefs and episodic memory are partitioned by
`ExperienceKey.key`, so evidence from one stream never silently stands in for
another, and replayed records never mix with lived ones.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

#: The epistemic standing of an experience stream. Core vocabulary: every
#: environment has lived experience, and any of them may be replayed.
EXPERIENCE_CONTEXTS: tuple[str, ...] = ("lived", "replay")

#: Environment, embodiment and variant tokens are owned by environment
#: profiles. The core checks only their shape, never their values.
TOKEN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


class ExperienceError(ValueError):
    """An experience description is malformed."""


@dataclass(frozen=True, slots=True)
class ExperienceKey:
    environment_kind: str
    embodiment_kind: str
    environment_variant: str | None = None
    context: str = "lived"

    def __post_init__(self) -> None:
        if self.context not in EXPERIENCE_CONTEXTS:
            raise ExperienceError(f"unknown experience context {self.context!r}")
        for name, value in (
            ("environment_kind", self.environment_kind),
            ("embodiment_kind", self.embodiment_kind),
        ):
            if not TOKEN.fullmatch(value):
                raise ExperienceError(f"{name} {value!r} is not a token")
        if self.environment_variant is not None and not TOKEN.fullmatch(self.environment_variant):
            raise ExperienceError(f"environment_variant {self.environment_variant!r}")

    @property
    def key(self) -> str:
        """The partition key: `lived:minecraft/fixture`, `lived:minecraft/mineflayer/normal`."""
        stream = f"{self.environment_kind}/{self.embodiment_kind}"
        if self.environment_variant is not None:
            stream += f"/{self.environment_variant}"
        return f"{self.context}:{stream}"

    @property
    def lived(self) -> bool:
        return self.context == "lived"

    def replayed(self) -> ExperienceKey:
        """The same stream, as it is when processed again rather than lived."""
        return ExperienceKey(
            self.environment_kind, self.embodiment_kind, self.environment_variant, "replay"
        )

    def to_json(self) -> dict[str, Any]:
        """The persisted form, as journal records carry it."""
        return {
            "context": self.context,
            "environment": self.environment_kind,
            "embodiment": self.embodiment_kind,
            "variant": self.environment_variant,
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> ExperienceKey:
        variant = body.get("variant")
        return cls(
            environment_kind=str(body["environment"]),
            embodiment_kind=str(body["embodiment"]),
            environment_variant=None if variant is None else str(variant),
            context=str(body.get("context", "lived")),
        )

    def to_message(self) -> dict[str, Any]:
        """The wire form, as `SessionHello`, `Observation` and `EpisodeEvent` carry it."""
        return {
            "context": self.context,
            "environmentKind": self.environment_kind,
            "embodimentKind": self.embodiment_kind,
            "environmentVariant": self.environment_variant,
        }

    @classmethod
    def from_message(cls, body: Mapping[str, Any]) -> ExperienceKey:
        variant = body.get("environmentVariant")
        return cls(
            environment_kind=str(body["environmentKind"]),
            embodiment_kind=str(body["embodimentKind"]),
            environment_variant=None if variant is None else str(variant),
            context=str(body.get("context", "lived")),
        )

    @classmethod
    def parse(cls, key: str) -> ExperienceKey:
        """Invert `key`."""
        context, _, stream = key.partition(":")
        parts = stream.split("/")
        if len(parts) not in (2, 3):
            raise ExperienceError(f"not an experience key: {key!r}")
        return cls(parts[0], parts[1], parts[2] if len(parts) == 3 else None, context)
