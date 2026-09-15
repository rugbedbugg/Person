"""Legacy Shroud V1 artefact detection on the cognition side."""

from __future__ import annotations

from typing import Any

LEGACY_CHECKPOINT_DIAGNOSTIC = "\n".join(
    [
        "Legacy Shroud V1 learning checkpoint detected.",
        "",
        "V1 Q-learning checkpoints are incompatible with the",
        "Person hierarchical skill policy.",
        "",
        "The checkpoint has not been modified.",
        "",
        "Start a new Person evidence store or import reviewed",
        "historical traces through the demonstration mechanism.",
    ]
)


class LegacyCheckpointError(ValueError):
    def __init__(self) -> None:
        super().__init__(LEGACY_CHECKPOINT_DIAGNOSTIC)


def is_legacy_learning_checkpoint(document: Any) -> bool:
    """Recognise a Shroud V1 tabular Q-learning checkpoint.

    There is no conversion. The V1 table is indexed by seven integer action ids
    over a bucketed vector; Person scores routines built from typed skills in a
    coarse semantic context. Any mapping between the two would be invented.
    """
    if not isinstance(document, dict):
        return False
    schema = document.get("schema")
    has_table = isinstance(document.get("entries"), list) and isinstance(
        document.get("actions"), list
    )
    return (isinstance(schema, str) and schema.startswith("shroud-rl-v")) or has_table


def assert_not_legacy_checkpoint(document: Any) -> None:
    if is_legacy_learning_checkpoint(document):
        raise LegacyCheckpointError()
