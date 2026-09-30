"""Interoceptive affect: phasic events and tonic conditions (ADR 0014).

The body reaches affect as legitimate bodily state: health, food and breath as
the observation reports them. Events are appraised once, when they happen;
conditions weigh continuously, in Person's experienced time, and stop when
they end. A persisting threat is an onset and an exposure, never an appraisal
per observation. The idle placeholder means nothing. None of this changes
what affect may do.

Most of these tests drive `Interoception` and `Affect` together, which is
exactly the path the cognition loop takes, so that cadence and trajectory can
be varied with everything else held fixed. The loop-level tests cover what
only the loop does: one appraisal per causal event, provenance, idle, the
journal and the research switch.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_cognition.affect import Affect, AffectRecord, AffectState
from person_cognition.interoception import Interoception
from person_persistence import EvidenceJournal
from test_affect import outcome, with_home
from test_loop import Harness, envelope
from test_spatial import STILL, at

REPOSITORY = Path(__file__).resolve().parents[3]
COGNITION = REPOSITORY / "apps/cognition/python/person_cognition"


@pytest.fixture
def view() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["vitals"].update({"health": 20.0, "food": 20.0, "breath": 10})
    for key in ("resources", "passiveAnimals", "hostiles", "players", "containers", "hazards"):
        document["nearby"][key] = []
    document["selfMotion"] = dict(STILL)
    return document


def body(
    view: dict[str, Any],
    *,
    health: float = 20,
    food: float = 20,
    breath: int = 10,
    threat: float | None = None,
    name: str = "zombie",
) -> dict[str, Any]:
    observation = deepcopy(view)
    observation["vitals"].update({"health": health, "food": food, "breath": breath})
    if threat is not None:
        observation["nearby"]["hostiles"] = [
            {
                "name": name,
                "distance": threat,
                "bearing": "ahead",
                "elevation": "level",
                "rangeBand": "near",
                "detail": "central",
                "named": False,
                "tamed": False,
                "protectedTarget": True,
            }
        ]
    return observation


class Life:
    """Interoception and affect as the loop runs them, without the rest."""

    def __init__(self) -> None:
        self.sense = Interoception()
        self.affect = Affect(AffectRecord(), precise=True)
        self.phasic: list[str] = []
        self.tonic: list[dict[str, Any]] = []

    def live(self, observation: dict[str, Any], now: int) -> None:
        sensed = self.sense.sense(observation)
        record = self.affect.apply_tonic(sensed.pressures, now)
        if record is not None:
            self.tonic.append(record)
        for appraisal in sensed.events:
            self.affect.feel(appraisal, now)
            self.phasic.append(appraisal.trigger)

    def through(self, observation: dict[str, Any], start: int, end: int, every: int) -> None:
        for now in range(start, end + 1, every):
            self.live(observation, now)


def close(first: AffectState, second: AffectState) -> bool:
    return all(abs(first.get(d) - second.get(d)) < 1e-6 for d in ("valence", "unease", "control"))


# ------------------------------------------------------------------ hunger


def test_persistent_hunger_keeps_weighing_on_affect_without_new_events(
    view: dict[str, Any],
) -> None:
    life = Life()
    life.live(body(view, food=20), 0)
    life.through(body(view, food=5), 20, 6000, 20)
    assert life.affect.state.valence < -0.1, "a lasting hunger lowers valence and keeps it low"
    assert life.affect.state.control == 0.0, "hunger is not a failure of Person's own actions"
    assert life.phasic.count("hunger_starving") == 1, "entering starvation is one event"
    assert len(life.tonic) > 100, "the condition is integrated, not appraised once"


def test_hunger_pressure_depends_on_experienced_time_not_observations(view: dict[str, Any]) -> None:
    sparse, dense = Life(), Life()
    sparse.through(body(view, food=5), 0, 6000, 40)
    dense.through(body(view, food=5), 0, 6000, 10)
    assert close(sparse.affect.state, dense.affect.state), (sparse.affect.state, dense.affect.state)


def test_worsening_and_recovering_hunger_are_distinguishable(view: dict[str, Any]) -> None:
    worsening, recovering = Life(), Life()
    for step, food in enumerate(range(18, 3, -1)):
        worsening.live(body(view, food=food), step * 400)
    for step, food in enumerate(range(4, 19)):
        recovering.live(body(view, food=food), step * 400)
    assert worsening.affect.state.valence < recovering.affect.state.valence
    assert "hunger_relieved" in recovering.phasic and "hunger_relieved" not in worsening.phasic
    assert "hunger_starving" in worsening.phasic


# ------------------------------------------------------------------ health


def test_low_health_is_a_sustained_vulnerability(view: dict[str, Any]) -> None:
    life = Life()
    life.live(body(view, health=20), 0)
    life.through(body(view, health=6), 20, 5000, 20)
    assert life.affect.state.unease > 0.1, "still badly hurt, still uneasy"
    assert life.phasic.count("harm") == 1, "the damage itself is one event"


def test_one_damage_event_is_appraised_once(view: dict[str, Any]) -> None:
    life = Life()
    life.live(body(view, health=20), 0)
    life.through(body(view, health=12), 20, 2000, 20)
    assert life.phasic.count("harm") == 1
    assert life.affect.state.control == 0.0, "being hurt is not an action failing"


def test_recovering_health_lifts_valence_but_not_control(view: dict[str, Any]) -> None:
    life = Life()
    life.live(body(view, health=6), 0)
    life.through(body(view, health=6), 20, 3000, 20)
    low = life.affect.state
    for step, health in enumerate(range(7, 21)):
        life.live(body(view, health=health), 3000 + (step + 1) * 200)
    life.through(body(view, health=20), 6000, 9000, 20)
    assert life.affect.state.valence > low.valence
    assert life.affect.state.control == 0.0, "time healing is not Person's action working"


# ------------------------------------------------------------------ breath


def test_running_short_of_breath_is_felt(view: dict[str, Any]) -> None:
    life = Life()
    life.live(body(view), 0)
    for step, breath in enumerate(range(9, 1, -1)):
        life.live(body(view, breath=breath), (step + 1) * 30)
    assert life.affect.state.unease > 0.1
    assert "breath_short" in life.phasic and "breath_critical" in life.phasic
    life.live(body(view, breath=10), 400)
    assert "breath_recovered" in life.phasic
    before = life.affect.state.unease
    life.through(body(view, breath=10), 420, 4000, 20)
    assert life.affect.state.unease < before, "breathing again ends the pressure"


def test_only_what_the_body_reports_can_move_affect(view: dict[str, Any]) -> None:
    plain = body(view, food=12)
    padded = deepcopy(plain)
    padded["vitals"]["saturation"] = 20.0
    padded["vitals"]["exhaustion"] = 3.5
    first, second = Life(), Life()
    first.through(plain, 0, 2000, 20)
    second.through(padded, 0, 2000, 20)
    assert close(first.affect.state, second.affect.state)


# ------------------------------------------------------------------ threat


def test_a_visible_threat_is_one_onset_and_then_an_exposure(view: dict[str, Any]) -> None:
    life = Life()
    life.live(body(view), 0)
    life.through(body(view, threat=6.0), 20, 1200, 20)
    assert life.phasic.count("threat_onset") == 1
    assert life.phasic.count("perceived_threat") == 0, "no appraisal per observation"
    assert life.tonic[-1]["pressures"]["threat"] > 0
    assert life.affect.state.unease > 0.1


def test_doubling_the_observation_cadence_does_not_double_threat_affect(
    view: dict[str, Any],
) -> None:
    ordinary, doubled = Life(), Life()
    for life, every in ((ordinary, 20), (doubled, 10)):
        life.live(body(view), 0)
        life.through(body(view, threat=6.0), 20, 2020, every)
    assert close(ordinary.affect.state, doubled.affect.state), (
        ordinary.affect.state,
        doubled.affect.state,
    )


def test_a_threat_that_clears_stops_pressing_and_a_new_one_is_a_new_onset(
    view: dict[str, Any],
) -> None:
    life = Life()
    life.live(body(view), 0)
    life.through(body(view, threat=6.0), 20, 600, 20)
    life.through(body(view), 620, 5000, 20)
    assert life.tonic[-1]["pressures"]["threat"] == 0
    assert life.affect.state.unease < 0.05, "exposure over, unease settles"
    life.through(body(view, threat=6.0), 5020, 5200, 20)
    assert life.phasic.count("threat_onset") == 2


def test_a_threat_growing_closer_escalates_once_per_step(view: dict[str, Any]) -> None:
    life = Life()
    life.live(body(view), 0)
    for step, distance in enumerate((12.0, 12.0, 6.0, 6.0, 6.0, 2.0)):
        life.live(body(view, threat=distance), (step + 1) * 20)
    assert life.phasic.count("threat_onset") == 1
    assert life.phasic.count("threat_escalation") == 2


def test_no_hostile_needs_an_identity(view: dict[str, Any]) -> None:
    life = Life()
    life.live(body(view), 0)
    life.live(body(view, threat=6.0, name="zombie"), 20)
    life.live(body(view, threat=6.0, name="skeleton"), 40)
    life.live(body(view, threat=6.0, name="spider"), 60)
    assert life.phasic.count("threat_onset") == 1, "one exposure, whatever is in it"
    source = (COGNITION / "interoception.py").read_text(encoding="utf-8")
    assert '"name"' not in source and "entityId" not in source


# --------------------------------------------------------- one event, once


def records(evidence: Path, kind: str) -> list[dict[str, Any]]:
    return [
        dict(event.payload)
        for event in EvidenceJournal(evidence / "journal").read()
        if event.type == kind
    ]


@pytest.fixture
def two_goals(view: dict[str, Any]) -> dict[str, Any]:
    close_ = deepcopy(view)
    close_["home"]["shelterState"] = "complete"
    close_["inventory"]["items"].append({"name": "wooden_pickaxe", "count": 1})
    return close_


def test_one_act_that_completes_several_goals_is_one_appraisal(
    tmp_path: Path, two_goals: dict[str, Any]
) -> None:
    harness = with_home(tmp_path, two_goals)
    _, policy, invocation = harness.observe(at(two_goals, 120))
    harness.loop.handle(outcome(invocation, policy, "place_owned_chest"))
    stored = at(two_goals, 140)
    stored["home"]["ownedStorage"] = [{"storageId": "storage_a", "contents": []}]
    before = len(records(tmp_path, "affect_appraised"))
    harness.observe(stored)
    appraised = records(tmp_path, "affect_appraised")[before:]
    caused = [r for r in appraised if r.get("cause", "").startswith("action:")]
    assert len(caused) == 1, appraised
    consequences = caused[0]["consequences"]
    kinds = {c["kind"] for c in consequences}
    assert "goal_complete" in kinds and len(consequences) >= 2, consequences
    assert not any(r["trigger"].startswith("goal_complete") for r in appraised), (
        "no separate appraisal per goal"
    )
    single = {**caused[0]}
    assert single["delta"]["valence"] <= 0.05 + 0.15 + 1e-9, "not multiplied by goal count"


def test_the_idle_placeholder_is_never_appraised(tmp_path: Path, view: dict[str, Any]) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    harness.observe(at(view, 100))
    idle = harness.loop._idle_goal(110)
    state: dict[str, float] = {}
    harness.loop.goals.update([idle], state, 110)
    harness.loop.goals.block(idle.goal_id, "no_feasible_plan", 111)
    harness.observe(at(view, 140))
    for record in records(tmp_path, "affect_appraised"):
        assert "maintain_reserves" not in record["trigger"]
        for consequence in record.get("consequences", []):
            assert consequence.get("goal_id") != idle.goal_id


def test_tonic_updates_are_journalled_with_their_causes(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    harness.observe(body(view, food=5) | {"tick": 100})
    harness.observe(at(body(view, food=5), 400))
    tonic = records(tmp_path, "affect_tonic")
    assert tonic, "a lasting hunger leaves a record of what it did"
    last = tonic[-1]
    assert set(last) >= {"pressures", "offset", "before", "after", "elapsed", "experienced_tick"}
    assert last["pressures"]["hunger"] > 0 and last["offset"].get("control", 0) == 0


def test_a_restart_resumes_the_tonic_state(tmp_path: Path, view: dict[str, Any]) -> None:
    first = Harness(tmp_path)
    first.hello()
    first.observe(at(body(view, food=5), 100))
    first.observe(at(body(view, food=5), 3000))
    felt = first.loop.affect.state
    first.loop.handle(
        {
            **envelope("EpisodeEvent", 3020),
            "episodeId": "ep_1",
            "phase": "ended",
            "reasonCodes": ["test"],
            "rngSeed": 7,
            "trainingContext": "fixture",
        }
    )
    second = Harness(tmp_path)
    second.hello()
    assert close(second.loop.affect.state, felt)


# ---------------------------------------------------------- research switch


def test_the_switch_leaves_r1_5_appraisal_exactly_as_it_was(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    harness = Harness(tmp_path, interoception=False)
    harness.hello()
    threatened = body(view, food=5, threat=6.0)
    harness.observe(at(threatened, 100))
    harness.observe(at(threatened, 120))
    appraised = records(tmp_path, "affect_appraised")
    assert [r["trigger"] for r in appraised].count("perceived_threat") == 2, "R1.5: per observation"
    assert records(tmp_path, "affect_tonic") == [], "R1.5 had no tonic affect"
    for record in appraised:
        assert set(record) == {
            "trigger",
            "components",
            "before",
            "delta",
            "after",
            "experienced_tick",
        }


def test_the_switch_is_consulted_only_where_r2_contributes() -> None:
    loop = (COGNITION / "loop.py").read_text(encoding="utf-8")
    uses = [line.strip() for line in loop.splitlines() if "self.interoception_on" in line]
    assert 0 < len(uses) <= 10, uses
    affect = (COGNITION / "affect.py").read_text(encoding="utf-8")
    assert "interoception" not in affect, "affect's state and authority know nothing of the switch"
