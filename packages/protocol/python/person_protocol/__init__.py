"""Versioned cognition/runtime protocol: schemas, validation, framing, envelopes.

The core contract is environment-neutral. An Observation's payload, and the
emergency vocabulary, belong to environment profiles found by manifest
(`environments.py`, ADR 0025).
"""

from .envelope import SessionIdentity, envelope
from .environments import (
    EnvironmentManifest,
    EnvironmentNotFound,
    discovered,
    environment,
    sole_environment,
)
from .framing import MAX_FRAME_BYTES, FrameError, LineReader, decode_frame, encode_frame
from .validator import ProtocolError, ProtocolValidator, protocol_validator, schema_directory
from .version import (
    COGNITION_MESSAGE_TYPES,
    EXPERIENCE_CONTEXTS,
    LEARNING_MODES,
    MESSAGE_TYPES,
    NODE_MESSAGE_TYPES,
    PROTOCOL_VERSION,
    SCHEMA_FILES,
    TERMINAL_STATUSES,
)

__all__ = [
    "EXPERIENCE_CONTEXTS",
    "EnvironmentManifest",
    "EnvironmentNotFound",
    "discovered",
    "environment",
    "sole_environment",
    "COGNITION_MESSAGE_TYPES",
    "LEARNING_MODES",
    "MAX_FRAME_BYTES",
    "MESSAGE_TYPES",
    "NODE_MESSAGE_TYPES",
    "PROTOCOL_VERSION",
    "SCHEMA_FILES",
    "TERMINAL_STATUSES",
    "FrameError",
    "LineReader",
    "ProtocolError",
    "ProtocolValidator",
    "SessionIdentity",
    "decode_frame",
    "encode_frame",
    "envelope",
    "protocol_validator",
    "schema_directory",
]
