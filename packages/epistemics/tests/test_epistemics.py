"""The epistemic distinctions, held structurally (ADR 0026, 0027, 0028)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import pytest
from person_epistemics import (
    IMAGINED,
    LIVED,
    NEVER_EVIDENCE,
    WORLD_EVIDENCE,
    BeliefState,
    EvidenceRefused,
    ExperienceKey,
    Freshness,
    Intervention,
    PredictedOutcome,
    Prediction,
    PredictionQuery,
    Predictors,
    Scope,
    ScopeError,
    ScopeLevel,
    Situation,
    Source,
    Widening,
    admit,
    check_widening,
)

LIVED_FIXTURE = ExperienceKey("env_a", "body_a")
HERE = Situation(environment_kind="env_a", world_id="world-1", embodiment_kind="body_a")


def evidence(value: Any, *, source: Source = Source.REAL_OBSERVATION, at: int = 10, **kw: Any):
    return admit(
        bears_on=kw.get("key", "door_open"),
        value=value,
        source=source,
        scope=kw.get("scope", Scope.world("env_a", "world-1")),
        observed_at=at,
        confidence=kw.get("confidence", 1.0),
        refs=kw.get("refs", ("message-1",)),
        experience=kw.get("experience", LIVED_FIXTURE),
    )


@dataclass(frozen=True)
class Event:
    type: str
    payload: dict[str, Any]


def journal(state: BeliefState, revisions: list[Any]) -> None:
    for revision in revisions:
        state.apply(Event("belief_revised", revision.payload()))


# ---------------------------------------------------------------- provenance


def test_the_provenance_classes_partition_every_source() -> None:
    assert set(Source) == WORLD_EVIDENCE | NEVER_EVIDENCE | {
        Source.TESTIMONY,
        Source.RESEARCH,
        Source.OPERATOR_INTERVENTION,
    }
    assert LIVED <= WORLD_EVIDENCE
    assert IMAGINED <= NEVER_EVIDENCE
    assert Source.REPLAY not in LIVED and Source.MEMORY_RECALL not in LIVED


@pytest.mark.parametrize(
    "source",
    [
        Source.MEMORY_RECALL,
        Source.REPLAY,
        Source.COUNTERFACTUAL,
        Source.MODEL_ROLLOUT,
        Source.INFERENCE,
        Source.INITIAL_KNOWLEDGE,
        Source.TESTIMONY,
        Source.RESEARCH,
        Source.OPERATOR_INTERVENTION,
    ],
)
def test_only_world_evidence_is_admitted(source: Source) -> None:
    with pytest.raises(EvidenceRefused):
        evidence(True, source=source)


def test_replayed_experience_is_never_new_evidence() -> None:
    with pytest.raises(EvidenceRefused, match="replayed"):
        evidence(True, experience=LIVED_FIXTURE.replayed())


def test_evidence_must_cite_what_it_rests_on() -> None:
    with pytest.raises(EvidenceRefused, match="reference"):
        evidence(True, refs=())


# ------------------------------------------------------------------- beliefs


def test_a_belief_carries_provenance_freshness_scope_and_references() -> None:
    state = BeliefState()
    journal(state, state.revise([evidence("open", at=12, refs=("message-7",))]))
    belief = state.get("door_open", HERE)
    assert belief is not None
    assert belief.value == "open"
    assert belief.basis is Source.REAL_OBSERVATION
    assert belief.evidence_refs == ("message-7",)
    assert belief.updated_at == 12 and belief.last_observed_at == 12
    assert belief.scope == Scope.world("env_a", "world-1")
    assert state.version == 1


def test_a_confirmation_refreshes_without_a_revision() -> None:
    state, fresh = BeliefState(), Freshness()
    journal(state, state.revise([evidence("open", at=12)], fresh))
    assert state.revise([evidence("open", at=40)], fresh) == []
    belief = state.view(HERE, fresh)["door_open"]
    assert belief.updated_at == 12 and belief.last_observed_at == 40
    # The overlay is never persisted: a rebuild knows only the revision time.
    rebuilt = BeliefState()
    rebuilt.load_json(state.to_json())
    assert rebuilt.view(HERE)["door_open"].last_observed_at == 12


def test_beliefs_are_revised_by_admitted_evidence_only() -> None:
    state = BeliefState()
    with pytest.raises(TypeError):
        state.revise([{"bears_on": "door_open", "value": True}])  # type: ignore[list-item]


def test_a_revision_with_a_non_evidential_basis_is_refused_on_replay() -> None:
    state = BeliefState()
    revision = state.revise([evidence("open")])[0]
    forged = revision.payload() | {"basis": Source.MODEL_ROLLOUT.value}
    state.apply(Event("belief_revised", forged))
    assert state.refused == 1 and state.get("door_open", HERE) is None


def test_a_world_belief_does_not_hold_in_another_world_or_environment() -> None:
    state = BeliefState()
    journal(state, state.revise([evidence("open")]))
    assert state.get("door_open", replace(HERE, world_id="world-2")) is None
    assert state.get("door_open", replace(HERE, environment_kind="env_b")) is None


def test_revising_never_changes_scope() -> None:
    state = BeliefState()
    local = Scope.world("env_a", "world-1")
    journal(state, state.revise([evidence("open", scope=local)]))
    revisions = state.revise([evidence("closed", scope=local, at=20)])
    assert [revision.belief.scope for revision in revisions] == [local]


# --------------------------------------------------------------------- scope


def test_environment_specific_knowledge_never_becomes_general_implicitly() -> None:
    embodied = Scope.embodiment("env_a", "body_a")
    with pytest.raises(ScopeError):
        check_widening(embodied, Widening(Scope.general(), "transfer", ("e1",)))
    with pytest.raises(ScopeError):
        check_widening(embodied, Widening(Scope.environment("env_a"), "", ()))
    with pytest.raises(ScopeError):
        check_widening(embodied, Widening(Scope.environment("env_b"), "transfer", ("e1",)))
    widened = check_widening(
        embodied, Widening(Scope.environment("env_a"), "seen in both", ("e1",))
    )
    assert widened.level is ScopeLevel.ENVIRONMENT
    env = Scope.environment("env_a")
    assert check_widening(env, Widening(Scope.general(), "tested elsewhere", ("e2",))).level is (
        ScopeLevel.GENERAL
    )


def test_a_scope_states_exactly_what_its_level_needs() -> None:
    with pytest.raises(ScopeError):
        Scope(ScopeLevel.GENERAL, environment_kind="env_a")
    with pytest.raises(ScopeError):
        Scope(ScopeLevel.WORLD, environment_kind="env_a")


# ---------------------------------------------------------------- experience


def test_experience_separates_environment_embodiment_variant_and_context() -> None:
    live = ExperienceKey("env_a", "body_b", "hard")
    assert live.key == "lived:env_a/body_b/hard"
    assert ExperienceKey.parse(live.key) == live
    assert live.replayed().key == "replay:env_a/body_b/hard"
    assert ExperienceKey.from_message(live.to_message()) == live
    assert ExperienceKey.from_json(live.to_json()) == live


# ---------------------------------------------------------------- prediction


class Constant:
    model_id = "constant"
    version = "1"
    domain = "env_a"
    temporal_scale = "one_action"

    def predict(self, query: PredictionQuery) -> Prediction | None:
        return Prediction(
            model_id=self.model_id,
            model_version=self.version,
            domain=self.domain,
            temporal_scale=self.temporal_scale,
            horizon=query.horizon,
            intervention=query.intervention,
            belief_version=query.belief_version,
            outcomes=(PredictedOutcome("door_open", "=", 1.0),),
        )


def test_zero_one_or_many_predictive_models() -> None:
    query = PredictionQuery({}, Intervention("open_door"), belief_version=3)
    assert Predictors().predict(query) == ()
    (only,) = Predictors([Constant()]).predict(query)
    assert only.identity()["belief_version"] == 3
    assert only.source is Source.MODEL_ROLLOUT


def test_a_prediction_is_always_imagined() -> None:
    query = PredictionQuery({}, Intervention("open_door"), belief_version=0)
    prediction = Constant().predict(query)
    assert prediction is not None
    with pytest.raises(ValueError):
        replace(prediction, source=Source.REAL_OBSERVATION)
    with pytest.raises(EvidenceRefused):
        evidence(1.0, source=prediction.source)
