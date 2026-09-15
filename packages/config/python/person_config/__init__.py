"""Cognition-side view of the Person configuration.

The Node runtime is authoritative for every safety-relevant field. Cognition
loads the same file, validated against the same schema, only to learn its own
settings, and it cross-checks them against the authoritative values the runtime
sends in SessionHello.
"""

from .load import (
    CognitionSettings,
    ConfigError,
    config_schema_path,
    load_cognition_settings,
    validate_config_document,
)
from .migrate import (
    LEGACY_CHECKPOINT_DIAGNOSTIC,
    LegacyCheckpointError,
    is_legacy_learning_checkpoint,
)

__all__ = [
    "LEGACY_CHECKPOINT_DIAGNOSTIC",
    "CognitionSettings",
    "ConfigError",
    "LegacyCheckpointError",
    "config_schema_path",
    "is_legacy_learning_checkpoint",
    "load_cognition_settings",
    "validate_config_document",
]
