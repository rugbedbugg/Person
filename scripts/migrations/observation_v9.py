"""Rewrite protocol fixtures and captures from the v2 wire (`shroud-learning-v2`,
flat Observation, `trainingContext`) to `person-v3` (ADR 0025).

A development aid for test fixtures and corpora only. Recorded evidence is
never rewritten: the readers understand old records instead.

    uv run python scripts/migrations/observation_v9.py FILE [FILE ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

#: Every v2 training context was Minecraft by construction.
LEGACY_EXPERIENCE: dict[str, dict[str, Any]] = {
    "fixture": {"embodimentKind": "fixture", "environmentVariant": None, "context": "lived"},
    "minecraft_peaceful": {
        "embodimentKind": "mineflayer",
        "environmentVariant": "peaceful",
        "context": "lived",
    },
    "minecraft_normal": {
        "embodimentKind": "mineflayer",
        "environmentVariant": "normal",
        "context": "lived",
    },
    "replay": {"embodimentKind": "unknown", "environmentVariant": None, "context": "replay"},
}
PAYLOAD_KEYS = (
    "vitals",
    "environment",
    "inventory",
    "permissions",
    "affordances",
    "nearby",
    "home",
    "navigation",
)


def experience(training_context: str) -> dict[str, Any]:
    legacy = LEGACY_EXPERIENCE[training_context]
    return {
        "context": legacy["context"],
        "environmentKind": "minecraft",
        "embodimentKind": legacy["embodimentKind"],
        "environmentVariant": legacy["environmentVariant"],
    }


def upgrade(message: Any) -> Any:
    if not isinstance(message, dict):
        return message
    out: dict[str, Any] = {}
    for key, value in message.items():
        if key == "protocolVersion" and value == "shroud-learning-v2":
            out[key] = "person-v3"
        elif key == "trainingContext" and value in LEGACY_EXPERIENCE:
            out["experience"] = experience(value)
        elif message.get("type") == "Observation" and key in PAYLOAD_KEYS:
            out.setdefault("payload", {})[key] = value
        elif message.get("type") == "Observation" and key == "observationVersion":
            out[key] = 9
        else:
            out[key] = value
    if out.get("type") == "Observation" and "payload" in out:
        # The payload follows the envelope, after everything core.
        payload = out.pop("payload")
        out["payload"] = payload
    return out


def main(paths: list[str]) -> None:
    for name in paths:
        path = Path(name)
        document = json.loads(path.read_text(encoding="utf-8"))
        upgraded = upgrade(document)
        if (
            isinstance(document, dict)
            and "protocolVersion" in document
            and document.get("type") is None
        ):
            upgraded = {**document, "protocolVersion": "person-v3"}
        path.write_text(json.dumps(upgraded, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
