"""What each decision was chosen from, for research only (R1.5, ADR 0013).

The journal records every legitimate goal candidate with its base priority,
affect bias and affect character, and every routine candidate with its score
at the neutral tolerance and at both ends of the tolerance range. The
experiment harness derives from these whether affect had any opportunity to
change a decision. Nothing in cognition reads them back: they describe a
decision, they do not make one.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_cognition.affect import TOLERANCE_RANGE, Affect, AffectRecord, AffectState
from person_persistence import EvidenceJournal
from person_policy import EvidencePolicyProvider, RoutineStatistics
from test_affect import experienced, known_success, option, skill_outcome, with_home
from test_loop import Harness
from test_spatial import STILL, at

REPOSITORY = Path(__file__).resolve().parents[3]
COGNITION = REPOSITORY / "apps/cognition/python/person_cognition"


@pytest.fixture
def view() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["vitals"].update({"health": 20.0, "food": 20.0})
    for key in ("resources", "passiveAnimals", "hostiles", "players", "containers", "hazards"):
        document["nearby"][key] = []
    document["selfMotion"] = dict(STILL)
    return document


@pytest.fixture
def two_goals(view: dict[str, Any]) -> dict[str, Any]:
    close = deepcopy(view)
    close["home"]["shelterState"] = "complete"
    close["inventory"]["items"].append({"name": "wooden_pickaxe", "count": 1})
    return close


def records(evidence: Path, event_type: str) -> list[dict[str, Any]]:
    return [
        dict(event.payload)
        for event in EvidenceJournal(evidence / "journal").read()
        if event.type == event_type
    ]


def test_every_goal_decision_records_the_candidates_it_was_chosen_from(
    tmp_path: Path, two_goals: dict[str, Any]
) -> None:
    harness = with_home(tmp_path, two_goals)
    harness.loop.affect.state = experienced([skill_outcome("gather_wood", "SUCCESS")] * 10, 0)
    harness.observe(at(two_goals, 200))
    selected = records(tmp_path, "goal_selected")[-1]
    candidates = selected["candidates"]
    assert len(candidates) >= 2
    for candidate in candidates:
        assert set(candidate) == {
            "goal_id",
            "goal_type",
            "source",
            "character",
            "base_priority",
            "affect_bias",
            "priority",
        }
        assert candidate["priority"] == pytest.approx(
            candidate["base_priority"] + candidate["affect_bias"], abs=1e-3
        )
    top = min(candidates, key=lambda c: (-c["priority"], c["goal_type"]))
    assert selected["goal_id"] == top["goal_id"], "the choice is the top candidate"
    characters = {c["goal_type"]: c["character"] for c in candidates}
    assert characters["ESTABLISH_TOOLS"] == "outgoing"
    assert characters["ESTABLISH_STORAGE"] == "protective"


def test_urgent_goals_are_recorded_as_beyond_affect(tmp_path: Path, view: dict[str, Any]) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    threatened = at(view, 100)
    threatened["nearby"]["hostiles"] = [
        {
            "name": "zombie",
            "distance": 3.0,
            "bearing": "ahead",
            "elevation": "level",
            "rangeBand": "near",
            "detail": "central",
            "named": False,
            "tamed": False,
            "protectedTarget": True,
        }
    ]
    harness.observe(threatened)
    candidates = records(tmp_path, "goal_selected")[-1]["candidates"]
    urgent = [c for c in candidates if c["source"] == "emergency"]
    assert urgent and all(c["character"] == "fixed" for c in urgent)
    assert all(c["affect_bias"] == 0.0 for c in urgent)


def test_routine_candidates_carry_their_scores_across_the_tolerance_range(
    view: dict[str, Any],
) -> None:
    statistics = RoutineStatistics()
    for _ in range(6):
        statistics.apply(known_success("r_known"))
    provider = EvidencePolicyProvider(
        statistics,
        training_context="fixture",
        learning_mode="supervised",
        minimum_support=3,
        exploration_bonus=0.9,
    )
    options = [option("known"), option("untried")]
    uneasy = Affect(AffectRecord())
    uneasy.state = AffectState(unease=1.0, control=-1.0)
    choice = provider.propose(
        view,
        None,
        options,
        "c",
        tolerance=uneasy.tolerance(),
        tolerance_bounds=TOLERANCE_RANGE,
    )
    assert choice.scored_choice, "the ranking decided"
    for scored in choice.candidates:
        assert scored.tolerance_scores is not None
        low, neutral, high = scored.tolerance_scores
        at_neutral, _ = provider.score(
            scored.candidate, scored.counts, envelope_open=True, tolerance=1.0
        )
        assert neutral == pytest.approx(at_neutral)
        assert low <= neutral <= high, "less tolerance never makes a routine more attractive"
    by_id = {s.candidate.routine_id: s for s in choice.candidates}
    assert by_id["r_untried"].tolerance_scores[1] > by_id["r_known"].tolerance_scores[1]  # type: ignore[index]
    assert choice.routine_id == "r_known", "at this tolerance the familiar routine wins"


def test_a_fallback_choice_is_not_a_scored_choice(view: dict[str, Any]) -> None:
    provider = EvidencePolicyProvider(
        RoutineStatistics(), training_context="fixture", learning_mode="off"
    )
    choice = provider.propose(
        view,
        None,
        [option("a"), option("b")],
        "c",
        tolerance=0.5,
        tolerance_bounds=TOLERANCE_RANGE,
    )
    assert not choice.scored_choice, "with learning off the fallback decides, whatever the scores"


def test_routine_decisions_record_the_tolerance_and_whether_scores_decided(
    tmp_path: Path,
) -> None:
    hungry: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    hungry["nearby"]["resources"].append(
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
    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    harness.observe(hungry)
    selected = records(tmp_path, "routine_selected")[-1]
    assert selected["tolerance"] == 1.0
    assert isinstance(selected["scored_choice"], bool)
    for candidate in selected["candidates"]:
        assert set(candidate["score_at_tolerance"]) == {"low", "neutral", "high"}


def test_nothing_in_cognition_reads_the_decision_basis_back() -> None:
    for path in COGNITION.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for field in ("score_at_tolerance", "tolerance_scores", "scored_choice"):
            if path.name == "loop.py":
                # The loop writes them into the journal (a key and its value)
                # and uses them nowhere else.
                assert text.count(field) <= 2, (path.name, field)
            else:
                assert field not in text, (path.name, field)
