"""Prediction error is measured, reported, and kept out of the policy."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_cognition import CognitionLoop
from person_cognition.prediction import apply_effect, compare
from person_persistence import EvidenceJournal
from person_policy import RoutineStatistics
from person_protocol import PROTOCOL_VERSION, decode_frame

REPOSITORY = Path(__file__).resolve().parents[3]
SESSION = "8f6c1c0e-3d0a-4a1e-9f3a-2b6f1d9c4e11"


def envelope(message_type: str, tick: int) -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "messageId": str(uuid.uuid4()),
        "personId": "ada",
        "sessionId": SESSION,
        "worldId": "test-world",
        "tick": tick,
        "timestamp": "2026-09-15T08:30:00.000Z",
        "type": message_type,
    }


def test_effect_semantics_match_the_planner() -> None:
    assert apply_effect(2, "+=", 8) == 10
    assert apply_effect(2, "-=", 8) == 0
    assert apply_effect(2, "=", 1) == 1
    assert apply_effect(5, "max", 2) == 5
    with pytest.raises(ValueError):
        apply_effect(1, "??", 1)


def test_an_exact_outcome_has_no_error() -> None:
    errors, unexplained, worst = compare(
        [{"fact": "wood", "op": "+=", "value": 8}], {"wood": 0}, {"wood": 8}
    )
    assert worst == "none"
    assert errors[0].error == 0
    assert unexplained == []


def test_a_small_shortfall_is_minor_and_a_large_one_is_major() -> None:
    _, _, minor = compare([{"fact": "wood", "op": "+=", "value": 8}], {"wood": 0}, {"wood": 6})
    _, _, major = compare([{"fact": "wood", "op": "+=", "value": 32}], {"wood": 0}, {"wood": 4})
    assert minor == "minor"
    assert major == "major"


def test_a_fact_that_moves_the_wrong_way_is_inverted() -> None:
    _, _, worst = compare(
        [{"fact": "shelter_complete", "op": "=", "value": 1}],
        {"shelter_complete": 0},
        {"shelter_complete": 0},
    )
    assert worst == "inverted", "a promised flag that never arrived is the interesting case"

    _, _, lost = compare([{"fact": "wood", "op": "+=", "value": 8}], {"wood": 10}, {"wood": 4})
    assert lost == "inverted"


def test_changes_nobody_predicted_are_reported() -> None:
    _, unexplained, _ = compare(
        [{"fact": "wood", "op": "+=", "value": 8}],
        {"wood": 0, "stone": 0},
        {"wood": 8, "stone": 6},
    )
    assert unexplained == [{"fact": "stone", "before": 0.0, "observed": 6.0}]


def test_volatile_facts_do_not_become_noise() -> None:
    _, unexplained, _ = compare(
        [{"fact": "wood", "op": "+=", "value": 1}],
        {"wood": 0, "food_level": 20, "reachable_wood": 4},
        {"wood": 1, "food_level": 17, "reachable_wood": 1},
    )
    assert unexplained == [], "hunger and what is in view move for their own reasons"


class Harness:
    def __init__(self, evidence: Path) -> None:
        self.sent: list[dict[str, Any]] = []
        self.loop = CognitionLoop(
            evidence_directory=evidence,
            write=lambda line: self.sent.append(decode_frame(line.rstrip("\n"))),
            log=lambda _line: None,
        )
        self.evidence = evidence

    def hello(self) -> None:
        from person_skills import skill_registry

        self.loop.handle(
            {
                **envelope("SessionHello", 0),
                "learningMode": "off",
                "trainingContext": "fixture",
                "policyRevision": 0,
                "skillLibraryRevision": skill_registry().revision,
                "rngSeed": 7,
                "evidenceDirectory": str(self.evidence),
                "skillIds": skill_registry().ids,
            }
        )

    def observe(self, observation: dict[str, Any]) -> dict[str, Any]:
        before = len(self.sent)
        self.loop.handle(observation)
        produced = self.sent[before:]
        return next(m for m in produced if m["type"] == "SkillInvocation")

    def outcome(
        self,
        invocation: dict[str, Any],
        *,
        expected: list[dict[str, Any]],
        executed: str | None = None,
        status: str = "SUCCESS",
    ) -> None:
        self.loop.handle(
            {
                **envelope("SkillOutcome", invocation["tick"] + 10),
                "decisionId": invocation["decisionId"],
                "goalId": invocation["goalId"],
                "routineId": invocation["routineId"],
                "contextId": "h_healthy.f_low.d_day.t_none.hm_near.tt_none.fs_none",
                "requestedSkill": invocation["skillId"],
                "requestedParameters": invocation["parameters"],
                "requestedSkillStatus": status,
                "executedSkill": executed or invocation["skillId"],
                "executedParameters": invocation["parameters"],
                "status": status,
                "emergency": executed is not None and executed != invocation["skillId"],
                "reasonCodes": [],
                "effects": [],
                "expectedEffects": expected,
                "healthBefore": 20,
                "healthAfter": 20,
                "foodBefore": 10,
                "foodAfter": 10,
                "healthCost": 0,
                "resourceCost": [],
                "inventoryDelta": [],
                "elapsedTicks": 120,
                "interruptReason": None,
                "completionEvidence": {"kinds": ["elapsed_ticks"], "details": {}},
            }
        )


@pytest.fixture
def observation() -> dict[str, Any]:
    document = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["nearby"]["resources"].append(
        {
            "kind": "plant_food",
            "name": "sweet_berry_bush",
            "distance": 4.0,
            "bearing": "ahead",
            "elevation": "below",
            "rangeBand": "reach",
            "detail": "central",
            "harvestPermitted": True,
        }
    )
    return document


def test_a_prediction_is_settled_by_the_next_observation(
    tmp_path: Path, observation: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    invocation = harness.observe(observation)
    harness.outcome(invocation, expected=[{"fact": "plant_food", "op": "+=", "value": 6}])
    assert harness.loop.prediction_errors == [], "nothing is settled until the world is seen again"

    after = deepcopy(observation)
    after["inventory"]["items"].append({"name": "sweet_berries", "count": 6})
    after["inventory"]["categories"]["food"] = 6
    harness.observe(after)

    assert len(harness.loop.prediction_errors) == 1
    record = harness.loop.prediction_errors[0]
    assert record["severity"] == "none"
    assert record["executed_skill"] == "gather_plant_food"
    observed = {entry["fact"]: entry for entry in record["observed"]}
    assert observed["plant_food"]["predicted"] == 6
    assert observed["plant_food"]["observed"] == 6


def test_a_broken_promise_is_recorded_as_inverted(
    tmp_path: Path, observation: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    invocation = harness.observe(observation)
    harness.outcome(invocation, expected=[{"fact": "plant_food", "op": "+=", "value": 6}])
    harness.observe(deepcopy(observation))

    record = harness.loop.prediction_errors[0]
    assert record["severity"] == "inverted"
    assert record["observed"][0]["error"] == -6


def test_prediction_is_attributed_to_the_skill_that_ran(
    tmp_path: Path, observation: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    invocation = harness.observe(observation)
    harness.outcome(
        invocation,
        executed="flee",
        status="SUCCESS",
        expected=[{"fact": "safe", "op": "=", "value": 1}],
    )
    harness.observe(deepcopy(observation))

    record = harness.loop.prediction_errors[0]
    assert record["requested_skill"] == invocation["skillId"]
    assert record["executed_skill"] == "flee"
    assert record["emergency"] is True
    assert [entry["fact"] for entry in record["observed"]] == ["safe"]


def test_an_unsettled_prediction_is_recorded_as_unobserved(
    tmp_path: Path, observation: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    invocation = harness.observe(observation)
    harness.outcome(invocation, expected=[{"fact": "plant_food", "op": "+=", "value": 6}])
    harness.loop.handle(
        {
            **envelope("EpisodeEvent", 900),
            "episodeId": "ep_1",
            "phase": "ended",
            "trainingContext": "fixture",
            "rngSeed": 7,
            "reasonCodes": ["done"],
        }
    )
    record = harness.loop.prediction_errors[0]
    assert record["severity"] == "unobserved"
    assert record["observed"] == []


def test_prediction_errors_are_persisted_but_never_scored(
    tmp_path: Path, observation: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    invocation = harness.observe(observation)
    harness.outcome(invocation, expected=[{"fact": "plant_food", "op": "+=", "value": 6}])
    harness.observe(deepcopy(observation))

    events = list(EvidenceJournal(tmp_path / "journal").read())
    recorded = [event for event in events if event.type == "prediction_error"]
    assert len(recorded) == 1
    assert recorded[0].schema_version == "person-evidence-v4"
    assert recorded[0].payload["decision_id"] == invocation["decisionId"]

    # Replaying the whole journal must leave the policy statistics untouched by
    # the prediction records: instrumentation cannot become behaviour by accident.
    with_predictions = RoutineStatistics()
    without_predictions = RoutineStatistics()
    for event in events:
        with_predictions.apply(event)
        if event.type != "prediction_error":
            without_predictions.apply(event)
    assert with_predictions.routines == without_predictions.routines
    assert with_predictions.skills == without_predictions.skills


def test_the_learning_report_summarises_prediction_error(
    tmp_path: Path, observation: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    invocation = harness.observe(observation)
    harness.outcome(invocation, expected=[{"fact": "plant_food", "op": "+=", "value": 6}])
    harness.observe(deepcopy(observation))
    harness.loop.handle(
        {
            **envelope("EpisodeEvent", 900),
            "episodeId": "ep_report",
            "phase": "ended",
            "trainingContext": "fixture",
            "rngSeed": 7,
            "reasonCodes": ["done"],
        }
    )
    report = json.loads(
        (tmp_path / "reports" / "learning-ep_report.json").read_text(encoding="utf-8")
    )
    assert report["prediction_error"]["recorded"] >= 1
    assert "inverted" in report["prediction_error"]["severities"]
    assert report["prediction_error"]["worst"][0]["severity"] == "inverted"
