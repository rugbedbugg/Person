"""The single-skill validation comparison reuses the prediction-error code.

These tests are about reuse as much as about arithmetic. The Node validation
harness asks this module a question and writes the answer into a report, and
the whole point of routing it here is that a validation report and a live
prediction-error record are produced by the same comparison.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_cognition import effects
from person_cognition.__main__ import main
from person_planner import symbolic_state

REPOSITORY = Path(__file__).resolve().parents[3]


@pytest.fixture
def observation() -> dict[str, Any]:
    return json.loads(  # type: ignore[no-any-return]
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )


def test_an_effect_the_world_confirms_is_a_match(observation: dict[str, Any]) -> None:
    before = deepcopy(observation)
    before["home"]["shelterState"] = "partial"
    after = deepcopy(observation)
    after["home"]["shelterState"] = "complete"

    result = effects.compare_observations(
        [{"fact": "shelter_complete", "op": "=", "value": 1}], before, after
    )

    assert result["available"] is True
    assert result["matched"] == 1
    assert result["mismatched"] == 0
    fact = result["facts"][0]
    assert fact["fact"] == "shelter_complete"
    assert fact["before"] == 0.0
    assert fact["observed"] == 1.0
    assert fact["verdict"] == "match"


def test_an_effect_the_world_denies_is_a_mismatch(observation: dict[str, Any]) -> None:
    before = deepcopy(observation)
    before["home"]["shelterState"] = "partial"
    after = deepcopy(observation)
    after["home"]["shelterState"] = "breached"

    result = effects.compare_observations(
        [{"fact": "shelter_complete", "op": "=", "value": 1}], before, after
    )

    assert result["mismatched"] == 1
    assert result["facts"][0]["verdict"] == "mismatch"
    assert result["facts"][0]["severity"] == "inverted"


def test_being_home_is_a_belief_an_observation_cannot_settle(
    observation: dict[str, Any],
) -> None:
    # C8: the observation carries no distance to home, so whether Person got
    # home is Person's own belief, not something a before/after pair proves.
    result = effects.compare_observations(
        [{"fact": "at_home", "op": "=", "value": 1}], observation, deepcopy(observation)
    )
    assert result["facts"][0]["verdict"] == "not_observable"


def test_facts_an_observation_cannot_carry_are_not_failures(
    observation: dict[str, Any],
) -> None:
    result = effects.compare_observations(
        [{"fact": "rested", "op": "=", "value": 1}], observation, deepcopy(observation)
    )
    assert result["notObservable"] == 1
    assert result["mismatched"] == 0
    assert result["facts"][0]["verdict"] == "not_observable"


def test_the_unobservable_facts_really_are_unobservable(
    observation: dict[str, Any],
) -> None:
    # The list is explicit, so this is what keeps it honest: every fact on it
    # must be one `symbolic_state` cannot derive from any observation.
    state = symbolic_state(observation)
    for fact in effects.UNOBSERVABLE_FACTS:
        assert state[fact] == 0.0


def test_a_missing_post_observation_is_inconclusive(observation: dict[str, Any]) -> None:
    result = effects.compare_observations(
        [{"fact": "at_home", "op": "=", "value": 1}], observation, None
    )
    assert result["inconclusive"] == 1
    assert result["mismatched"] == 0
    assert result["reason"] == "post_observation_unavailable"
    assert result["facts"][0]["verdict"] == "inconclusive"


def test_the_entry_point_is_analysis_and_never_a_decision(
    observation: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "expectedEffects": [{"fact": "at_home", "op": "=", "value": 1}],
                "before": observation,
                "after": observation,
            }
        ),
        encoding="utf-8",
    )

    assert main(["--compare-effects", str(request)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["facts"][0]["fact"] == "at_home"
    # Nothing that could become a physical request may come back out of here.
    for forbidden in ("SkillInvocation", "skillId", "parameters", "decisionId"):
        assert forbidden not in printed


def test_an_unreadable_request_fails_without_starting_anything(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    assert main(["--compare-effects", str(missing)]) == 2
