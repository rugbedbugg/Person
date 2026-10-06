"""Affective metareasoning, C6a: record-only (ADR 0023).

Person's pre-signal affect is read, in coarse bands, exactly where System-2
escalation is decided, and recorded; in record-only it changes nothing.
"""

from __future__ import annotations

from typing import Any

import pytest
from person_cognition.affect import AffectState, Temperament, decay
from person_cognition.deliberation.metareasoning import (
    TRIGGER_COUNT,
    Detectors,
    Trigger,
    affect_bands,
    affective_threshold,
)
from test_habits_active import Active, promoted_template
from test_metareasoning import ANSWER, Step, emergency

HIGH_UNEASE = affect_bands(0.7, 0.0)
LOW_CONTROL = affect_bands(0.1, -0.4)
CALM = affect_bands(0.3, 0.0)
CONFIDENT = affect_bands(0.0, 0.8)


def failure(count: int) -> Trigger:
    return Trigger(
        "repeated_failure",
        "SECURE_FOOD",
        {"consecutive_failures": count, "count": count},
    )


def arbitrating(step: Step, mode: str = "record_only") -> Step:
    step.arbiter.affect_arbitration = mode
    step.arbiter.detectors.early = mode != "off"
    return step


def shadows(step: Step) -> list[dict[str, Any]]:
    return [p for k, p in step.records if k == "affective_arbitration_shadow"]


# ------------------------------------------------------------------- rule


@pytest.mark.parametrize(
    ("bands", "threshold"),
    [(HIGH_UNEASE, 2), (LOW_CONTROL, 2), (CALM, 3), (CONFIDENT, 3)],
)
def test_only_high_unease_or_low_control_lower_the_threshold_and_nothing_raises_it(
    bands: dict[str, str], threshold: int
) -> None:
    assert affective_threshold(bands) == threshold <= TRIGGER_COUNT


def test_the_rule_sees_bands_never_values() -> None:
    assert affect_bands(0.5, -0.25) == {"unease_band": "high", "control_band": "low"}
    assert affect_bands(0.19, 0.25) == {"unease_band": "low", "control_band": "high"}
    assert set(affect_bands(0.3, 0.1).values()) == {"normal"}


def test_decay_returns_the_baseline() -> None:
    """F: high unease gives 2; experienced-time decay to normal gives 3 again."""
    state = AffectState(valence=0.0, unease=0.8, control=0.0)
    assert affective_threshold(affect_bands(state.unease, state.control)) == 2
    later = decay(state, Temperament(), 6_000.0)
    assert affective_threshold(affect_bands(later.unease, later.control)) == 3


def test_detectors_offer_an_early_candidate_only_when_arbitration_is_on() -> None:
    off = Detectors()
    assert off.goal_failed("SECURE_FOOD", "g", 2, 1.0) is None
    on = Detectors()
    on.early = True
    early = on.goal_failed("SECURE_FOOD", "g", 2, 1.0)
    assert early is not None and early.signal["count"] == 2
    assert on.planned("G", "g", False, 1.0) is None
    assert on.planned("G", "g", False, 1.0).signal["count"] == 2  # type: ignore[union-attr]
    assert on.planned("G", "g", False, 1.0).signal["count"] == 3, "no reset early"  # type: ignore[union-attr]
    assert on.emergency("suffocation", 1) is None
    assert on.emergency("suffocation", 2) is None, "emergencies keep their count"


# ---------------------------------------------------------- record-only


def test_record_only_records_what_affect_would_do_and_does_nothing() -> None:
    """C: high unease, two failures: the shadow says it would fire; nothing fires."""
    step = arbitrating(Step("active", [ANSWER]))
    step.arbiter.affect_snapshot = HIGH_UNEASE
    step.arbiter.raise_trigger(failure(2))
    step(10)
    assert step.kinds() == ["affective_arbitration_shadow"]
    shadow = shadows(step)[0]
    assert shadow["signal_count"] == 2 and shadow["shadow_threshold"] == 2
    assert shadow["affect_advanced_threshold"] is True
    assert shadow["baseline_threshold_crossed"] is False
    assert shadow["unease_band"] == "high" and "unease" not in shadow


def test_record_only_changes_no_request_and_no_payload() -> None:
    """Off against record-only: the same requests with the same payloads;
    only the affect evidence differs."""

    def run(mode: str) -> list[tuple[str, dict[str, Any]]]:
        step = arbitrating(Step("active", [ANSWER]), mode)
        step.arbiter.new_invocation_id = lambda: "x"
        step.arbiter.affect_snapshot = HIGH_UNEASE
        for count, at in ((2, 10), (3, 20)):
            step.arbiter.raise_trigger(failure(count) if mode != "off" or count == 3 else None)
            step(at)
        random = {"deliberation_id", "context_sha256", "latency_ms"}
        return [
            (k, {f: v for f, v in p.items() if f not in random})
            for k, p in step.records
            if k != "affective_arbitration_shadow"
        ]

    assert run("record_only") == run("off")


def test_the_baseline_trigger_is_recorded_at_the_arbitration_point_too() -> None:
    step = arbitrating(Step("active", [ANSWER]))
    step.arbiter.affect_snapshot = CALM
    step.arbiter.raise_trigger(failure(3))
    step(10)
    assert step.kinds() == ["affective_arbitration_shadow", "deliberation_requested"]
    assert shadows(step)[0]["affect_advanced_threshold"] is False
    requested = step.records[-1][1]
    assert "affect_changed_outcome" not in requested, "record-only adds no counterfactual"


def test_no_shadow_while_a_remedy_is_live_or_for_emergencies() -> None:
    step = arbitrating(Step("active", [ANSWER]))
    step.arbiter.affect_snapshot = HIGH_UNEASE
    emergency(step)
    step(10)
    step(20)
    assert step.arbiter.adopted is not None
    step.arbiter.raise_trigger(failure(2))
    step(30)
    assert shadows(step) == [], "not at the arbitration point, and emergencies are outside C6"


def test_an_applicable_habit_leaves_no_affect_evidence() -> None:
    """D: a promoted applicable habit and high unease: no affect event and no
    model, early or at the baseline; the habit answers at its own count."""
    step = arbitrating(Active([ANSWER]))
    step.arbiter.affect_snapshot = HIGH_UNEASE
    promoted_template(step.book, trigger_kind="repeated_failure", semantic_key="SECURE_FOOD")
    step.arbiter.raise_trigger(failure(2))
    step(10)
    assert step.kinds() == [], "no affect event, no model, not yet the habit's turn"
    step.arbiter.raise_trigger(failure(3))
    step(20)
    assert step.kinds() == ["habit_invoked"]
    assert shadows(step) == []


def test_the_signal_is_judged_by_the_affect_before_its_own_appraisal() -> None:
    """H: the bands a signal carries are those of its skill's dispatch; the
    signal's own appraisal, arriving after, cannot lower its threshold."""
    step = arbitrating(Step("active", [ANSWER]))
    step.arbiter.affect_snapshot = CALM  # dispatched calm
    step.arbiter.raise_trigger(failure(2))
    step.arbiter.affect_snapshot = LOW_CONTROL  # this failure's appraisal
    step(10)
    assert shadows(step)[0]["control_band"] == "normal"
    assert shadows(step)[0]["shadow_threshold"] == 3
    step.arbiter.raise_trigger(failure(3))  # the next signal may use it
    step(20)
    assert shadows(step)[1]["control_band"] == "low"


def test_restart_reconstructs_the_same_affect_bands() -> None:
    """G: affect rebuilt from the journal gives the same bands, so the same
    affective threshold, as before the restart."""
    from person_cognition.affect import AffectRecord
    from test_metareasoning import event

    record = AffectRecord()
    record.apply(
        event(
            "affect_appraised",
            trigger="action_failed",
            components={},
            before={"valence": 0.0, "unease": 0.0, "control": 0.0},
            delta={"valence": 0.0, "unease": 0.6, "control": -0.3},
            after={"valence": 0.0, "unease": 0.6, "control": -0.3},
            experienced_tick=10,
        )
    )
    rebuilt = AffectRecord()
    rebuilt.load_json(record.to_json())
    before = affect_bands(record.state.unease, record.state.control)
    after = affect_bands(rebuilt.state.unease, rebuilt.state.control)
    assert before == after == {"unease_band": "high", "control_band": "low"}
    assert affective_threshold(after) == 2


def test_arbitration_needs_a_deliberation_path_and_active_affect() -> None:
    from person_config import ConfigError, validate_config_document
    from test_deliberation import _example_document

    base = _example_document()
    base.pop("affect", None)  # unset means active (ADR 0013)
    for mode in ("record_only", "active"):
        base["deliberation"] = {"mode": mode, "affectArbitration": "record_only"}
        validate_config_document(base)
    base["deliberation"] = {"mode": "active", "affectArbitration": "active"}
    validate_config_document(base)
    for bad in (
        {"mode": "off", "affectArbitration": "record_only"},
        {"affectArbitration": "record_only"},
        {"mode": "record_only", "affectArbitration": "active"},
    ):
        base["deliberation"] = bad
        with pytest.raises(ConfigError):
            validate_config_document(base)
    base["deliberation"] = {"mode": "active", "affectArbitration": "record_only"}
    for affect in ("off", "record_only"):
        base["affect"] = {"mode": affect}
        with pytest.raises(ConfigError):
            validate_config_document(base)


# --------------------------------------------------------------- active (C6b)


def requested(step: Step) -> list[dict[str, Any]]:
    return [p for k, p in step.records if k == "deliberation_requested"]


def test_normal_affect_deliberates_on_the_baseline_signal() -> None:
    """A: normal affect, three failures: deliberation on the third, and the
    journal says affect changed nothing."""
    step = arbitrating(Step("active", [ANSWER]), "active")
    step.arbiter.affect_snapshot = CALM
    step.arbiter.raise_trigger(failure(2))
    step(10)
    assert requested(step) == []
    step.arbiter.raise_trigger(failure(3))
    step(20)
    [request] = requested(step)
    assert request["baseline_would_fire"] is True
    assert request["affect_changed_outcome"] is False


@pytest.mark.parametrize("bands", [HIGH_UNEASE, LOW_CONTROL])
def test_high_unease_or_low_control_deliberates_one_signal_earlier(
    bands: dict[str, str],
) -> None:
    """B: two failures are enough, and the journal records that the
    baseline would not yet have asked."""
    step = arbitrating(Step("active", [ANSWER]), "active")
    step.arbiter.affect_snapshot = bands
    step.arbiter.raise_trigger(failure(2))
    step(10)
    [request] = requested(step)
    assert request["baseline_would_fire"] is False
    assert request["affect_changed_outcome"] is True
    assert request["signal"]["count"] == 2


def test_when_the_budgets_overrule_affect_that_is_kept_too() -> None:
    step = arbitrating(Step("active", [ANSWER]), "active")
    step.arbiter.affect_snapshot = HIGH_UNEASE
    for n in range(4):
        step.record(
            "deliberation_requested",
            {
                "deliberation_id": f"dlb_{n}",
                "trigger_key_full": f"repeated_failure:G{n}",
                "trigger_kind": "repeated_failure",
                "session_id": "s",
                "experienced_tick": 1,
            },
        )
    step.arbiter.raise_trigger(failure(2))
    step(10)
    suppressed = step.records[-1]
    assert suppressed[0] == "deliberation_suppressed"
    assert suppressed[1]["affect_advanced_threshold"] is True
    assert suppressed[1]["baseline_would_fire"] is False
    assert "affect_changed_outcome" not in suppressed[1], "no request, no outcome"


def test_an_advanced_request_spends_its_evidence() -> None:
    step = arbitrating(Step("active", [ANSWER]), "active")
    step.arbiter.affect_snapshot = HIGH_UNEASE
    detectors = step.arbiter.detectors
    assert detectors.planned("SECURE_FOOD", "g", False, 1.0) is None
    early = detectors.planned("SECURE_FOOD", "g", False, 1.0)
    step.arbiter.raise_trigger(early)
    step(10)
    assert requested(step)[0]["affect_changed_outcome"] is True
    assert detectors.planned("SECURE_FOOD", "g", False, 1.0) is None, "counting starts over"


def test_active_affect_never_bypasses_an_applicable_habit() -> None:
    """D, active: high unease and an applicable habit: the habit answers at
    its own count; no affect event, no model."""
    step = arbitrating(Active([ANSWER]), "active")
    step.arbiter.affect_snapshot = HIGH_UNEASE
    promoted_template(step.book, trigger_kind="repeated_failure", semantic_key="SECURE_FOOD")
    step.arbiter.raise_trigger(failure(2))
    step(10)
    assert step.kinds() == []
    step.arbiter.raise_trigger(failure(3))
    step(20)
    assert step.kinds() == ["habit_invoked"]


def test_active_affect_leaves_emergencies_alone() -> None:
    """E: high unease and two suffocations: no strategic deliberation; the
    third fires exactly as ADR 0021."""
    step = arbitrating(Step("active", [ANSWER]), "active")
    step.arbiter.affect_snapshot = HIGH_UNEASE
    detectors = step.arbiter.detectors
    for at in (1, 2):
        step.arbiter.raise_trigger(detectors.emergency("suffocation", at))
    step(10)
    assert requested(step) == []
    step.arbiter.raise_trigger(detectors.emergency("suffocation", 3))
    step(20)
    [request] = requested(step)
    assert "affect_changed_outcome" not in request


def test_active_judges_each_signal_by_the_affect_before_it() -> None:
    """H, active: a failure dispatched calm is not advanced by its own
    appraisal; the next signal may be."""
    step = arbitrating(Step("active", [ANSWER]), "active")
    step.arbiter.affect_snapshot = CALM
    step.arbiter.raise_trigger(failure(2))
    step.arbiter.affect_snapshot = LOW_CONTROL
    step(10)
    assert requested(step) == []
    step.arbiter.raise_trigger(
        Trigger("no_viable_plan", "SECURE_FOOD", {"decisions_without_plan": 2, "count": 2})
    )
    step(20)
    assert requested(step)[0]["affect_changed_outcome"] is True
