"""Names a proposal must never use, and why a proposal was refused.

This is the one module that has to spell out what is privileged, so that it
can recognise it: a proposer, and above all a language model, can write any
field name it likes. The grounding gate admits only the fields a hypothesis
has; these lists only make a refusal say what kind of mistake it was.
"""

from __future__ import annotations

#: The world as the runtime knows it, not as Person does.
PRIVILEGED: frozenset[str] = frozenset(
    {
        "x",
        "y",
        "z",
        "position",
        "coordinates",
        "coords",
        "yaw",
        "pitch",
        "heading",
        "entity",
        "entity_id",
        "entityid",
        "uuid",
        "target",
        "block",
        "block_state",
        "snapshot",
        "world",
        "path",
        "pathfinder",
        "home_distance",
        "homedistance",
        "debug",
        "journal",
        "query",
        "sql",
        "code",
        "expression",
        "predicate",
        "eval",
        "command",
    }
)

#: Claims of standing a proposal cannot make for itself.
AUTHORITY: frozenset[str] = frozenset(
    {
        "confidence",
        "certainty",
        "probability",
        "likelihood",
        "prior",
        "evidence",
        "known",
        "knowledge",
        "true",
        "proven",
        "fact",
        "verified",
        "status",
        "standing",
        "provenance",
        "source",
    }
)


def refusal(key: str) -> str:
    """The reason a field that is not part of a hypothesis was refused."""
    name = key.lower()
    if name in PRIVILEGED:
        return f"privileged_reference:{name}"
    if name in AUTHORITY:
        return f"claims_authority:{name}"
    return f"unknown_field:{name[:32]}"
