"""Envelope construction for cognition-side messages."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .version import PROTOCOL_VERSION


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    person_id: str
    session_id: str
    world_id: str


def envelope(
    identity: SessionIdentity,
    message_type: str,
    tick: int,
    *,
    message_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    moment = now or datetime.now(UTC)
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "messageId": message_id or str(uuid.uuid4()),
        "personId": identity.person_id,
        "sessionId": identity.session_id,
        "worldId": identity.world_id,
        "tick": tick,
        "timestamp": moment.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "type": message_type,
    }
