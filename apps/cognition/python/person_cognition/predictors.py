"""Person's predictive models (ADR 0028).

One exists, and it is not new: the declared-effect model has always been how
Person predicted, because the planner reasons with every skill's declared
effects as if they were true and `prediction.py` has always measured how true
they are. What is new is that it is now a `PredictiveModel` with an identity,
a version, a domain and a temporal scale, and every settled prediction records
which model made it and under which belief-store version.

It is advisory only. It reads a skill contract; it cannot act, emit a
message, or reach the runtime. Learned effect reliability (ADR 0011) is
learned about this model's predictions, not a second model.
"""

from __future__ import annotations

from person_epistemics import (
    Intervention,
    PredictedOutcome,
    Prediction,
    PredictionQuery,
)
from person_skills import SkillRegistry


class DeclaredEffectModel:
    """Predicts a skill's effects to be exactly what its contract declares."""

    model_id = "declared_effects"
    version = "1"
    temporal_scale = "one_action"

    def __init__(self, registry: SkillRegistry, domain: str) -> None:
        self.registry = registry
        #: The environment whose skill contracts it reads.
        self.domain = domain

    def predict(self, query: PredictionQuery) -> Prediction | None:
        skill = query.intervention.skill_id
        if skill not in self.registry:
            return None
        spec = self.registry.get(skill)
        parameters = dict(query.intervention.parameters)
        return Prediction(
            model_id=self.model_id,
            model_version=f"{self.version}+{self.registry.revision}",
            domain=self.domain,
            temporal_scale=self.temporal_scale,
            horizon=query.horizon,
            intervention=Intervention(skill, parameters),
            belief_version=query.belief_version,
            outcomes=tuple(
                PredictedOutcome(effect.fact, effect.op, effect.magnitude(parameters))
                for effect in spec.expected_effects
            ),
            # A contract states no uncertainty. Learned reliability does.
            confidence=None,
        )
