"""Versioned cognition/runtime protocol: schemas, validation, framing, envelopes."""

from .envelope import SessionIdentity, envelope
from .framing import MAX_FRAME_BYTES, FrameError, LineReader, decode_frame, encode_frame
from .validator import ProtocolError, ProtocolValidator, protocol_validator, schema_directory
from .version import (
    COGNITION_MESSAGE_TYPES,
    LEARNING_MODES,
    MESSAGE_TYPES,
    NODE_MESSAGE_TYPES,
    PROTOCOL_VERSION,
    SCHEMA_FILES,
    TERMINAL_STATUSES,
    TRAINING_CONTEXTS,
)

__all__ = [
    "COGNITION_MESSAGE_TYPES",
    "LEARNING_MODES",
    "MAX_FRAME_BYTES",
    "MESSAGE_TYPES",
    "NODE_MESSAGE_TYPES",
    "PROTOCOL_VERSION",
    "SCHEMA_FILES",
    "TERMINAL_STATUSES",
    "TRAINING_CONTEXTS",
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
