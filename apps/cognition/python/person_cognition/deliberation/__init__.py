"""Deliberation by a replaceable model, behind Person's boundary (ADR 0020).

C1: the context, the proposal and its gate, the model interface, and the
record. Nothing here changes what Person does.
"""

from .context import CAPS, CONTEXT_SCHEMA, REASONS, Capability, DeliberationContext, build_context
from .deliberator import MODES, Deliberator, Outcome
from .model import (
    UNAVAILABLE_REASONS,
    CognitiveModel,
    ModelResponse,
    ProviderDegraded,
    ScriptedModel,
    SterilityFailure,
    canonical_json,
    sha256_text,
)
from .proposal import INSTRUCTION_TEMPLATE, PROPOSAL_SCHEMA, Verdict, gate

__all__ = [
    "CAPS",
    "CONTEXT_SCHEMA",
    "INSTRUCTION_TEMPLATE",
    "MODES",
    "PROPOSAL_SCHEMA",
    "REASONS",
    "UNAVAILABLE_REASONS",
    "Capability",
    "CognitiveModel",
    "DeliberationContext",
    "Deliberator",
    "ModelResponse",
    "ProviderDegraded",
    "Outcome",
    "ScriptedModel",
    "SterilityFailure",
    "Verdict",
    "build_context",
    "canonical_json",
    "gate",
    "sha256_text",
]
