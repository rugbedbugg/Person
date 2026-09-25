"""Person's sense of place: integrated from felt motion, never from coordinates.

The rules defended here are ADR 0008's. Cognition integrates coarse, relative
self-motion into an estimate in a frame of its own, and the estimate drifts:
uncertainty only grows, and nothing hidden corrects it. Places are Person's
own records, recognised with a confidence. A search Person remembers making at
a place it believes it has returned to makes the next search there shorter,
and it never becomes knowledge that nothing is there.

Everything here drives the real cognition loop in process, or the spatial
package directly, with hand-built messages. It is cognition-level evidence.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_cognition.search import LOOK_BUDGET, NOT_FOUND, REVISIT_MIN_LOOKS
from person_cognition.spatial import Estimate, Spatial, SpatialMap, integrate, recognise
from person_cognition.spatial.places import Place
from person_persistence import EvidenceJournal
from test_loop import Harness, envelope

REPOSITORY = Path(__file__).resolve().parents[3]

STILL: dict[str, Any] = {
    "continuity": "continuous",
    "translation": {"direction": "none", "band": "none", "distance": 0},
    "rotation": "none",
    "vertical": "level",
}


def moved(direction: str, distance: float, rotation: str = "none") -> dict[str, Any]:
    band = "tiny" if distance < 2 else "short" if distance < 8 else "moderate"
    band = "far" if distance >= 24 else band
    return {
        "continuity": "continuous",
        "translation": {"direction": direction, "band": band, "distance": distance},
        "rotation": rotation,
        "vertical": "level",
    }


def turned(rotation: str) -> dict[str, Any]:
    return {**STILL, "rotation": rotation}


# ------------------------------------------------------------ integration


def test_standing_still_moves_nothing_and_adds_no_doubt() -> None:
    start = Estimate()
    after = integrate(integrate(start, STILL), STILL)
    assert after == start


def test_walking_ahead_moves_the_estimate_ahead() -> None:
    after = integrate(Estimate(), moved("ahead", 6))
    assert after.forward == pytest.approx(6) and after.left == pytest.approx(0)
    assert after.uncertainty > 0


def test_sideways_and_diagonal_steps_go_where_they_were_felt() -> None:
    left = integrate(Estimate(), moved("left", 4))
    assert left.left == pytest.approx(4) and left.forward == pytest.approx(0, abs=1e-9)
    diagonal = integrate(Estimate(), moved("ahead_right", 4))
    assert diagonal.forward > 0 and diagonal.left < 0


def test_turning_on_the_spot_changes_facing_not_position() -> None:
    after = integrate(Estimate(), turned("left"))
    assert (after.forward, after.left, after.uncertainty) == (0, 0, 0)
    assert after.heading == 2
    assert after.heading_uncertainty > 0, "a felt turn is rounded, so it adds doubt"


def test_turning_then_walking_is_coherent() -> None:
    # Turn left a quarter, then walk "ahead": that is the original left.
    after = integrate(integrate(Estimate(), turned("left")), moved("ahead", 5))
    assert after.left == pytest.approx(5) and after.forward == pytest.approx(0, abs=1e-9)
    # A step felt with a turn in it is felt relative to the facing before it.
    combined = integrate(Estimate(), moved("ahead", 5, rotation="left"))
    assert combined.forward == pytest.approx(5)
    assert combined.heading == 2


def test_a_square_walk_comes_back_near_the_start_and_less_sure() -> None:
    estimate = Estimate()
    doubts = []
    for _ in range(4):
        estimate = integrate(estimate, moved("ahead", 10, rotation="left"))
        doubts.append(estimate.uncertainty)
    assert math.hypot(estimate.forward, estimate.left) == pytest.approx(0, abs=1e-6)
    assert doubts == sorted(doubts) and doubts[0] < doubts[-1]
    assert estimate.uncertainty > 10, "four legs of travel are never exact"


def test_being_lost_starts_a_new_frame_rather_than_guessing() -> None:
    estimate = integrate(Estimate(), moved("ahead", 10))
    lost = integrate(
        estimate,
        {
            "continuity": "discontinuous",
            "translation": {"direction": "unknown", "band": "unknown", "distance": None},
            "rotation": "unknown",
            "vertical": "unknown",
        },
    )
    assert lost.frame == estimate.frame + 1
    place = Place("place_1", estimate.frame, 10, 0, 0, "search", 0)
    assert recognise([place], lost, ()) is None, "old places cannot be related to"


def test_recognition_is_a_confidence_and_falls_with_doubt() -> None:
    place = Place("place_1", 1, 0, 0, 0.0, "search", 0, ("wood",))
    sure = recognise([place], Estimate(), ("wood",))
    unsure = recognise([place], Estimate(uncertainty=12), ("wood",))
    assert sure is not None and unsure is not None
    assert 0 < unsure.confidence < sure.confidence < 1
    assert recognise([place], Estimate(forward=30), ()) is None


# ------------------------------------------------------------- in the loop


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


def at(view: dict[str, Any], tick: int, motion: dict[str, Any] | None = None) -> dict[str, Any]:
    changed = deepcopy(view)
    changed["tick"] = tick
    changed["messageId"] = envelope("Observation", tick)["messageId"]
    changed["selfMotion"] = motion or dict(STILL)
    return changed


def records(evidence: Path, kind: str) -> list[dict[str, Any]]:
    return [
        dict(event.payload)
        for event in EvidenceJournal(evidence / "journal").read()
        if event.type == kind
    ]


def search_here(harness: Harness, view: dict[str, Any], start: int) -> tuple[int, int]:
    """Let Person search from where it stands until it stops looking."""
    looks = 0
    tick = start
    for _ in range(LOOK_BUDGET + 4):
        _, policy, invocation = harness.observe(at(view, tick))
        tick += 20
        harness.complete(invocation, policy)
        if invocation["skillId"] == "look":
            looks += 1
        elif looks:
            break
    return looks, tick


def finish(harness: Harness, tick: int) -> None:
    harness.loop.handle(
        {
            **envelope("EpisodeEvent", tick),
            "episodeId": "ep_1",
            "phase": "ended",
            "reasonCodes": ["test"],
            "rngSeed": 7,
            "trainingContext": "fixture",
        }
    )


def test_a_search_is_made_at_a_place_and_remembered_there(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    looks, _ = search_here(harness, view, 100)
    assert looks == LOOK_BUDGET, "the first search at a place is a full one"

    formed = records(tmp_path, "place_formed")
    assert formed and formed[0]["reason"] == "search"
    place = formed[0]["place_id"]
    searched = [
        episode
        for episode in harness.loop.memory_store.inspect()
        if episode.kind == "searched" and episode.detail("conclusion") == NOT_FOUND
    ]
    assert searched and all(episode.place_id == place for episode in searched)


def drive(
    harness: Harness, view: dict[str, Any], steps: int, moves: dict[int, dict[str, Any]]
) -> None:
    """Run the loop for some decisions, with felt motion at chosen steps."""
    for step in range(steps):
        _, policy, invocation = harness.observe(at(view, 100 + step * 20, moves.get(step)))
        harness.complete(invocation, policy)


def starts(evidence: Path) -> list[dict[str, Any]]:
    return [
        record for record in records(evidence, "information_search") if record["phase"] == "started"
    ]


def test_somewhere_else_is_searched_in_full(tmp_path: Path, view: dict[str, Any]) -> None:
    # "Not found" was about one place. Walking to another reopens the goal,
    # and a place Person has not searched gets the whole budget.
    harness = Harness(tmp_path)
    harness.hello()
    drive(harness, view, 30, {14: moved("ahead", 12)})
    searches = starts(tmp_path)
    places = [record["place"]["place_id"] for record in searches]
    assert places[0] == "place_1" and "place_2" in places
    first_elsewhere = searches[places.index("place_2")]
    assert first_elsewhere["budget"] == LOOK_BUDGET
    assert first_elsewhere["revisit"] == 0.0


def test_returning_to_a_searched_place_makes_the_search_shorter_not_skipped(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    # Search here, walk twelve blocks and search there, walk back and search.
    drive(harness, view, 48, {14: moved("ahead", 12), 30: moved("behind", 12)})
    searches = starts(tmp_path)
    places = [record["place"]["place_id"] for record in searches]
    back = next(
        record
        for index, record in enumerate(searches)
        if record["place"]["place_id"] == "place_1" and "place_2" in places[:index]
    )
    assert back["revisit"] > 0, "Person believes it is back where it searched"
    assert REVISIT_MIN_LOOKS <= back["budget"] < LOOK_BUDGET
    assert set(back["recalled"]), "the earlier search came back, cued by the place"

    concluded = [r for r in records(tmp_path, "information_search") if r["phase"] == "exhausted"]
    assert {record["conclusion"] for record in concluded} == {NOT_FOUND}
    for episode in harness.loop.memory_store.inspect():
        assert "absent" not in json.dumps(episode.to_json())


def test_the_same_place_searched_again_for_the_same_things_is_short(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    # Two goals need the same unseen wood. The second, from the same place,
    # remembers the first searched here and found nothing.
    harness = Harness(tmp_path)
    harness.hello()
    drive(harness, view, 14, {})
    first, second = starts(tmp_path)[:2]
    assert first["budget"] == LOOK_BUDGET
    assert second["place"]["place_id"] == first["place"]["place_id"]
    assert second["budget"] < LOOK_BUDGET


def test_seeing_wood_still_reopens_a_goal_at_a_place_searched_before(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    _, tick = search_here(harness, view, 100)
    wood = at(view, tick)
    wood["nearby"]["resources"] = [
        {
            "kind": "wood",
            "name": "oak_log",
            "distance": 5.0,
            "bearing": "ahead",
            "elevation": "level",
            "rangeBand": "near",
            "detail": "central",
            "harvestPermitted": True,
        }
    ]
    _, _, invocation = harness.observe(wood)
    assert invocation["skillId"] == "gather_wood", "the earlier search never meant absence"


def test_the_map_changes_only_through_felt_motion(tmp_path: Path, view: dict[str, Any]) -> None:
    # Everything else the observation says, including the runtime's own home
    # distance, is not a sense of place, and must not correct the estimate.
    harness = Harness(tmp_path)
    harness.hello()
    harness.observe(at(view, 100))
    before = harness.loop.spatial.estimate
    changed = at(view, 120)
    changed["home"]["homeDistance"] = 0.0
    changed["nearby"]["workstations"] = []
    harness.observe(changed)
    assert harness.loop.spatial.estimate == before


def test_places_persist_and_a_restart_resumes_less_sure_without_revealing_anything(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    first = Harness(tmp_path)
    first.hello()
    _, tick = search_here(first, view, 100)
    _, policy, invocation = first.observe(at(view, tick, moved("ahead", 12)))
    first.complete(invocation, policy)
    finish(first, tick + 40)
    places = [place.to_json() for place in first.loop.spatial_map.places()]
    last = first.loop.spatial.estimate

    second = Harness(tmp_path)
    second.hello()
    assert [place.to_json() for place in second.loop.spatial_map.places()] == places
    woke = second.loop.spatial.estimate
    assert (woke.forward, woke.left, woke.heading) == (last.forward, last.left, last.heading)
    assert woke.uncertainty > last.uncertainty, "Person cannot know it was not moved"

    # The first observation after waking says nothing about where the body is.
    start = at(view, 5, {**STILL, "continuity": "start"})
    start["home"]["homeDistance"] = 250.0
    second.observe(start)
    assert second.loop.spatial.estimate == woke


def test_home_is_where_person_built_its_shelter() -> None:
    spatial = Spatial(SpatialMap())
    kind, payload = spatial.settle("shelter", 10, label="home")
    assert kind == "place_formed" and payload["label"] == "home"
    with pytest.raises(ValueError):
        spatial.settle("teleported", 10)


def test_nothing_absolute_is_in_the_spatial_model(tmp_path: Path, view: dict[str, Any]) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    search_here(harness, view, 100)
    body = json.dumps(harness.loop.spatial_map.to_json())
    for forbidden in ('"x"', '"y"', '"z"', "yaw", "pitch", "homeDistance", "position"):
        assert forbidden not in body
