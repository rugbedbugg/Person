"""Causal hypotheses and controlled experiments (ADR 0012).

"Maybe X causes Y. How could I test that?" A hypothesis is typed, structured
and falsifiable, proposed by reasoning that is never evidence, tested by
bounded experiments that run as ordinary goals, and held with a confidence
that later evidence can always reverse. It is a belief under test, never a
memory and never knowledge: promotion to knowledge is a later phase.
"""

from .book import HypothesisBook
from .experiments import Investigation, InvestigationManager, calm, design, epistemic_value
from .generation import (
    ContrastProposer,
    ModelProposer,
    Proposer,
    ReasoningContext,
    Rejection,
    TrialRecord,
    admit,
)
from .hypothesis import CausalHypothesis, Condition, Outcome, Provenance
from .influence import HYPOTHESIS_LIMIT, hypothesis_term
from .vocabulary import Perceived, evaluable_effects, perceived, vocabulary

__all__ = [
    "HYPOTHESIS_LIMIT",
    "CausalHypothesis",
    "Condition",
    "ContrastProposer",
    "HypothesisBook",
    "Investigation",
    "InvestigationManager",
    "ModelProposer",
    "Outcome",
    "Perceived",
    "Proposer",
    "Provenance",
    "ReasoningContext",
    "Rejection",
    "TrialRecord",
    "admit",
    "calm",
    "design",
    "epistemic_value",
    "evaluable_effects",
    "hypothesis_term",
    "perceived",
    "vocabulary",
]
