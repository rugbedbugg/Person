"""Predictive models: zero, one or many, all advisory (ADR 0028).

A predictive model answers "if Person did this, what would follow?". It is a
cognitive component and nothing more. It never acts: it has no channel to the
runtime, it emits no `SkillInvocation`, and an architecture test holds every
implementation to that.

Person may have no model, one, or several that differ by domain, target,
representation, temporal scale and horizon. They need not share an internal
representation: the contract is the query and the prediction, not a state
format. A symbolic contract reader and a learned network would both fit.

A prediction is imagined (`Source.MODEL_ROLLOUT`). It is compared with what
actually followed, and the comparison is what is recorded and learned from;
the prediction itself is never evidence, never a belief and never a memory.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .provenance import Source

#: Temporal scales a prediction can be about. Only one has a producer.
TEMPORAL_SCALES: tuple[str, ...] = ("one_action", "episode", "lifetime")


@dataclass(frozen=True, slots=True)
class Intervention:
    """The action a prediction is conditional on."""

    skill_id: str
    parameters: Mapping[str, int | float | str | bool] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PredictionQuery:
    #: The facts the prediction starts from, in the environment's vocabulary.
    state: Mapping[str, float]
    intervention: Intervention
    #: The belief store's version when the query was made.
    belief_version: int
    horizon: str = "next_observation"


@dataclass(frozen=True, slots=True)
class PredictedOutcome:
    target: str
    op: str
    value: float


@dataclass(frozen=True, slots=True)
class Prediction:
    model_id: str
    model_version: str
    domain: str
    temporal_scale: str
    horizon: str
    intervention: Intervention
    belief_version: int
    outcomes: tuple[PredictedOutcome, ...]
    #: None when the model states no uncertainty; the declared-effect model
    #: does not, which is itself worth recording.
    confidence: float | None = None
    evidence_refs: tuple[str, ...] = ()
    #: Imagined. Always. The field exists so nothing can forget it.
    source: Source = Source.MODEL_ROLLOUT

    def __post_init__(self) -> None:
        if self.source is not Source.MODEL_ROLLOUT:
            raise ValueError("a prediction is a model's output and nothing else")

    @property
    def targets(self) -> tuple[str, ...]:
        return tuple(outcome.target for outcome in self.outcomes)

    def identity(self) -> dict[str, Any]:
        """Who predicted, under what: recorded with every settled prediction."""
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "domain": self.domain,
            "temporal_scale": self.temporal_scale,
            "horizon": self.horizon,
            "belief_version": self.belief_version,
            "intervention": {
                "skill": self.intervention.skill_id,
                "parameters": dict(self.intervention.parameters),
            },
            "confidence": self.confidence,
            "source": self.source.value,
        }

    def expected(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {"fact": outcome.target, "op": outcome.op, "value": outcome.value}
            for outcome in self.outcomes
        )


@runtime_checkable
class PredictiveModel(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def version(self) -> str: ...

    @property
    def domain(self) -> str: ...

    @property
    def temporal_scale(self) -> str: ...

    def predict(self, query: PredictionQuery) -> Prediction | None: ...


class Predictors:
    """The models Person has, in a fixed order. Possibly none."""

    def __init__(self, models: Iterable[PredictiveModel] = ()) -> None:
        self.models: tuple[PredictiveModel, ...] = tuple(models)
        ids = [model.model_id for model in self.models]
        if len(ids) != len(set(ids)):
            raise ValueError("predictive model ids must be unique")

    def __len__(self) -> int:
        return len(self.models)

    def predict(self, query: PredictionQuery) -> tuple[Prediction, ...]:
        """Every model's prediction for the query; models that abstain are skipped."""
        predictions: list[Prediction] = []
        for model in self.models:
            prediction = model.predict(query)
            if prediction is not None:
                predictions.append(prediction)
        return tuple(predictions)
