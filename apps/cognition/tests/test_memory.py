"""Person's memory: what can become one, and how much of it comes back.

The rules defended here are ADR 0007's. A memory is formed only from what
cognition was given or did, and only through a whitelist. It comes back only
when cued, a few at a time, labelled as memory. It fades by becoming
inaccessible, never by being erased, and it is never quietly corrected by the
world. It never claims that an action was done to a particular thing Person
saw, because nothing yet knows that.

Everything here drives the real cognition loop in process with hand-built
messages, or the memory package directly. It is cognition-level evidence.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_cognition.memory import (
    KINDS,
    RECALL_LIMIT,
    SUBJECTS,
    Cue,
    Episode,
    Memory,
    MemoryRecordError,
    MemoryStore,
    Provenance,
    Recalled,
    RecallRules,
)
from person_cognition.memory import encoding as remembering
from person_cognition.search import LOOK_BUDGET, NOT_FOUND
from person_persistence import EvidenceJournal, new_event
from person_planner import symbolic_state
from person_skills import skill_registry
from test_loop import Harness, envelope

REPOSITORY = Path(__file__).resolve().parents[3]
SESSION = "8f6c1c0e-3d0a-4a1e-9f3a-2b6f1d9c4e11"


# ----------------------------------------------------------------- helpers


@pytest.fixture
def view() -> dict[str, Any]:
    """Healthy, fed, no shelter, nothing in sight."""
    document: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["vitals"].update({"health": 20.0, "food": 20.0})
    for key in ("resources", "passiveAnimals", "hostiles", "players", "containers", "hazards"):
        document["nearby"][key] = []
    return document


def tree(detail: str = "central", distance: float = 7.0) -> dict[str, Any]:
    return {
        "kind": "wood",
        **({"name": "oak_log"} if detail == "central" else {}),
        "distance": distance,
        "bearing": "ahead",
        "elevation": "level",
        "rangeBand": "near",
        "detail": detail,
        "harvestPermitted": True,
    }


def seeing(view: dict[str, Any], *resources: dict[str, Any], tick: int = 100) -> dict[str, Any]:
    changed = deepcopy(view)
    changed["nearby"]["resources"] = list(resources)
    changed["tick"] = tick
    changed["messageId"] = envelope("Observation", tick)["messageId"]
    return changed


def event(kind: str, payload: dict[str, Any], *, tick: int = 1, context: str = "fixture") -> Any:
    return new_event(
        person_id="ada",
        world_id="w",
        session_id=SESSION,
        episode_id="ep_1",
        decision_id=None,
        tick=tick,
        policy_revision=0,
        training_context=context,
        event_type=kind,
        payload=payload,
        previous_event_id=None,
    )


def encoded(
    store: MemoryStore,
    *subjects: str,
    at: int = 0,
    salience: float = 0.2,
    kind: str = "perceived",
    context: str = "fixture",
) -> str:
    """Put one episode in the store the way the loop does: through an event."""
    record = event(
        "memory_encoded",
        {
            "kind": kind,
            "subjects": list(subjects),
            "experienced_tick": at,
            "salience": salience,
            "details": {"what": list(subjects)},
            "provenance": {"source": "perceived", "message_id": "m", "decision_id": None},
        },
        context=context,
    )
    store.apply(record)
    return str(record.event_id)


def memory_at(store: MemoryStore, now: int, context: str = "fixture") -> Memory:
    """A Memory whose experienced clock reads exactly `now`.

    A new Memory resumes from the latest experienced time in the store, as a
    restarted Person does, and then lives through the difference.
    """
    memory = Memory(store, training_context=context)
    assert now >= memory.now
    memory.observe_time(0)
    memory.observe_time(now - memory.now)
    assert memory.now == now
    return memory


def journal(evidence: Path, kind: str) -> list[Any]:
    return [
        record for record in EvidenceJournal(evidence / "journal").read() if record.type == kind
    ]


def episodes(harness: Harness) -> list[Episode]:
    return list(harness.loop.memory_store.inspect())


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


def exhaust(harness: Harness, view: dict[str, Any], start: int = 100) -> None:
    """Show Person the same empty view until the search it starts is over."""
    for step in range(LOOK_BUDGET + 3):
        _, policy, invocation = harness.observe(seeing(view, tick=start + step * 20))
        harness.complete(invocation, policy)


# ------------------------------------------------------ the retrieval firewall


def test_recall_takes_a_typed_cue_and_nothing_else() -> None:
    memory = memory_at(MemoryStore(), 0)
    for query in ("wood", {"subjects": ["wood"]}, ["wood"], None):
        with pytest.raises(TypeError):
            memory.recall(query)  # type: ignore[arg-type]

    parameters = list(inspect.signature(Memory.recall).parameters)
    assert parameters == ["self", "cue"], "no limit, no filter, no query string"
    # `place` is one of Person's own place identifiers (ADR 0008), never text.
    assert {field.name for field in dataclasses.fields(Cue)} == {
        "subjects",
        "purpose",
        "kinds",
        "place",
    }
    with pytest.raises(MemoryRecordError):
        Cue.about("wood", purpose="search", place="12,64,-3")

    with pytest.raises(MemoryRecordError):
        Cue.about("diamonds", purpose="search")
    with pytest.raises(MemoryRecordError):
        Cue.about("wood", purpose="dump_everything")
    with pytest.raises(MemoryRecordError):
        Cue.about(*sorted(SUBJECTS), purpose="search")
    with pytest.raises(TypeError):
        Cue(subjects={"wood"}, purpose="search")  # type: ignore[arg-type]


def test_no_method_reachable_from_cognition_returns_the_store() -> None:
    public = {
        name
        for name, value in inspect.getmembers(Memory)
        if not name.startswith("_") and callable(value)
    }
    assert public == {"recall", "experience", "payload", "encoded", "observe_time"}
    source = (REPOSITORY / "apps/cognition/python/person_cognition/loop.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (".inspect(", ".episodes_in(", "._store", "memory_store.get("):
        assert forbidden not in source, f"the loop must not reach past recall: {forbidden}"


def test_a_relevant_cue_retrieves_a_small_bounded_subset() -> None:
    store = MemoryStore()
    for index in range(20):
        encoded(store, "wood", at=index)
        encoded(store, "stone", at=index)
    recalled = memory_at(store, 30).recall(Cue.about("wood", purpose="search"))

    assert 0 < len(recalled) <= RECALL_LIMIT
    assert all("wood" in item.episode.subjects for item in recalled)
    assert len(store) == 40, "nothing was consumed by recalling"


def test_unrelated_memories_do_not_come_back() -> None:
    store = MemoryStore()
    for index in range(10):
        encoded(store, "stone", at=index)
        encoded(store, "animal", at=index)
    assert memory_at(store, 20).recall(Cue.about("coal", purpose="search")) == ()


def test_recent_and_salient_memories_outrank_weaker_ones_by_the_documented_rule() -> None:
    store = MemoryStore()
    old_weak = encoded(store, "wood", at=0, salience=0.1)
    old_strong = encoded(store, "wood", at=0, salience=0.9)
    recent_weak = encoded(store, "wood", at=20_000, salience=0.1)
    memory = memory_at(store, 24_000)

    order = [item.episode.memory_id for item in memory.recall(Cue.about("wood", purpose="goal"))]
    assert order == [recent_weak, old_strong, old_weak]

    # The numbers are the ADR's, and reproducible by hand.
    rules = RecallRules()
    for item in memory.recall(Cue.about("wood", purpose="goal")):
        half_life = rules.base_half_life * (1 + rules.salience_stretch * item.episode.salience)
        assert item.accessibility == pytest.approx(0.5 ** (item.age / half_life))
        assert item.relevance == 1.0


def test_relevance_gates_so_salience_cannot_drag_in_the_irrelevant() -> None:
    store = MemoryStore()
    encoded(store, "hostile", "danger", at=0, salience=1.0)
    faint = encoded(store, "wood", "coal", at=0, salience=0.0)
    recalled = memory_at(store, 10).recall(Cue.about("wood", purpose="search"))
    assert [item.episode.memory_id for item in recalled] == [faint]
    assert recalled[0].relevance == 1.0


def test_old_memories_become_inaccessible_without_being_erased() -> None:
    store = MemoryStore()
    weak = encoded(store, "wood", at=0, salience=0.0)
    cue = Cue.about("wood", purpose="search")

    assert [item.episode.memory_id for item in memory_at(store, 1_000).recall(cue)] == [weak]
    # Past about 4.3 half-lives the memory is below the threshold.
    assert memory_at(store, 24_000 * 5).recall(cue) == ()
    assert store.get(weak) is not None, "forgotten is not deleted"
    assert "delete" not in dir(store) and "forget" not in dir(store)


def test_salience_keeps_a_memory_accessible_for_longer() -> None:
    store = MemoryStore()
    weak = encoded(store, "wood", at=0, salience=0.0)
    strong = encoded(store, "wood", at=0, salience=1.0)
    recalled = memory_at(store, 24_000 * 5).recall(Cue.about("wood", purpose="search"))
    assert [item.episode.memory_id for item in recalled] == [strong]
    assert weak != strong


def test_fixture_memories_never_surface_in_a_live_world() -> None:
    store = MemoryStore()
    encoded(store, "wood", at=0, context="fixture")
    assert memory_at(store, 10, context="live").recall(Cue.about("wood", purpose="search")) == ()


def test_only_encoded_episodes_can_become_memories() -> None:
    # The journal holds decisions, outcomes and searches too. None of them is
    # a memory unless Person encoded one from it.
    store = MemoryStore()
    for kind, payload in (
        ("routine_outcome", {"routine_id": "r", "status": "SUCCESS", "context_id": "c"}),
        ("skill_completed", {"executed_skill": "gather_wood", "status": "SUCCESS"}),
        ("information_search", {"phase": "exhausted", "purpose": ["reachable_wood"]}),
        ("emergency_override", {"trigger": "immediate_threat"}),
        ("memory_recalled", {"cue": {}, "recalled": []}),
    ):
        store.apply(event(kind, payload))
    assert len(store) == 0


def test_memories_are_immutable_and_never_refreshed() -> None:
    store = MemoryStore()
    memory_id = encoded(store, "wood", at=0)
    episode = store.get(memory_id)
    assert episode is not None
    with pytest.raises(dataclasses.FrozenInstanceError):
        episode.salience = 1.0  # type: ignore[misc]
    for name in ("update", "refresh", "correct", "set", "replace", "delete"):
        assert not hasattr(store, name)


# ---------------------------------------------------------------- encoding


def test_a_glimpse_is_not_remembered_as_a_thing(view: dict[str, Any]) -> None:
    glimpse = remembering.noticed(seeing(view, tree("peripheral")))
    assert "wood" not in glimpse
    seen = remembering.noticed(seeing(view, tree("central")))
    assert [percept["detail"] for percept in seen["wood"]] == ["central"]


def test_encoding_copies_only_whitelisted_fields(view: dict[str, Any]) -> None:
    # Fields no observation may carry, injected anyway: memory must not keep
    # what it was not asked to keep, even if a bug upstream let it through.
    smuggled = tree("central") | {"position": {"x": 12, "y": 64, "z": -3}, "entityId": 991}
    observation = seeing(view, smuggled) | {"worldSnapshot": {"secret": True}}
    draft = remembering.perceived(observation, "wood", remembering.noticed(observation)["wood"])

    body = json.dumps({"details": draft.details, "provenance": draft.provenance.to_json()})
    for forbidden in ("position", "entityId", "991", "worldSnapshot", "secret", '"x"'):
        assert forbidden not in body
    assert set(draft.details) == {"what", "count", "recognised", "nearest_range", "day_phase"}


def outcome(skill: str, *, executed: str | None = None, status: str = "SUCCESS") -> dict[str, Any]:
    return {
        **envelope("SkillOutcome", 200),
        "decisionId": "33333333-3333-4333-8333-333333333333",
        "goalId": "goal_secure_shelter",
        "routineId": "r_1",
        "contextId": "c",
        "requestedSkill": skill,
        "requestedParameters": {},
        "requestedSkillStatus": "PREEMPTED" if executed else status,
        "executedSkill": executed or skill,
        "executedParameters": {},
        "status": status,
        "emergency": executed is not None,
        "reasonCodes": [],
        "effects": ["logs_collected"],
        "expectedEffects": [],
        "healthBefore": 20,
        "healthAfter": 20,
        "foodBefore": 20,
        "foodAfter": 20,
        "healthCost": 0,
        "resourceCost": [],
        "inventoryDelta": [{"name": "oak_log", "delta": 3}],
        "elapsedTicks": 80,
        "interruptReason": None,
        # What the motor knew about the tree it chose. Never Person's.
        "completionEvidence": {
            "kinds": ["blocks_broken"],
            "details": {"target_x": 5, "target_z": 11, "tree": "tree_b"},
        },
    }


def test_an_action_is_remembered_by_what_ran_and_what_was_felt() -> None:
    draft = remembering.acted(outcome("gather_wood"), skill_registry(), "e1")
    assert draft is not None
    assert draft.kind == "acted"
    assert draft.subjects == ("wood",)
    assert set(draft.details) == {
        "skill",
        "status",
        "emergency",
        "effects",
        "inventory",
        "health_cost",
    }
    assert draft.details["inventory"] == ["oak_log:+3"]
    body = json.dumps(dict(draft.details))
    assert "target" not in body and "tree_b" not in body and "11" not in body

    replaced = remembering.acted(outcome("gather_wood", executed="flee"), skill_registry(), "e2")
    assert replaced is not None
    assert replaced.details["skill"] == "flee"
    assert replaced.details["requested"] == "gather_wood"


# ------------------------------------------------------------ in the loop


def test_an_experienced_percept_can_later_be_recalled(tmp_path: Path, view: dict[str, Any]) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    harness.observe(seeing(view, tree("central"), tick=100))

    recalled = harness.loop.memory.recall(Cue.about("wood", purpose="goal"))
    assert [item.episode.kind for item in recalled] == ["perceived"]
    remembered = recalled[0]
    assert remembered.episode.detail("what") == ["oak_log"]
    assert remembered.episode.provenance.source == "perceived"


def test_recall_is_labelled_memory_and_never_becomes_perception(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    harness.observe(seeing(view, tree("central"), tick=100))
    empty = seeing(view, tick=200)

    recalled = harness.loop.memory.recall(Cue.about("wood", purpose="goal"))
    assert recalled and all(isinstance(item, Recalled) for item in recalled)
    assert {item.source for item in recalled} == {"memory"}
    # Remembering a tree does not put one in view.
    assert symbolic_state(empty)["reachable_wood"] == 0


def test_stale_memory_is_not_overwritten_by_what_is_true_now(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    harness.observe(seeing(view, tree("central"), tick=100))
    before = [episode.to_json() for episode in episodes(harness)]
    # The tree is gone, whatever the reason. Person sees nothing there.
    for step in range(3):
        _, policy, invocation = harness.observe(seeing(view, tick=200 + step * 50))
        harness.complete(invocation, policy)

    after = {episode.memory_id: episode.to_json() for episode in episodes(harness)}
    for record in before:
        assert after[record["memory_id"]] == record, "a memory is never edited"
    assert not any(
        "absent" in json.dumps(record) or "gone" in json.dumps(record) for record in after.values()
    )


def test_restart_keeps_memories_and_their_provenance_but_not_what_was_in_mind(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    first = Harness(tmp_path)
    first.hello()
    _, policy, invocation = first.observe(seeing(view, tree("central"), tick=100))
    first.complete(invocation, policy)
    finish(first, 300)
    stored = {episode.memory_id: episode.to_json() for episode in episodes(first)}
    assert stored and len(first.loop.memory.working) > 0

    second = Harness(tmp_path)
    second.hello()
    restored = {episode.memory_id: episode.to_json() for episode in episodes(second)}
    assert restored == stored, "the same episodes, with the same provenance"
    assert len(second.loop.memory.working) == 0, "nothing is in mind until something is recalled"
    assert second.loop.memory.now >= first.loop.memory.now, "experienced time resumes"


def test_restart_does_not_inject_the_store(tmp_path: Path, view: dict[str, Any]) -> None:
    first = Harness(tmp_path)
    first.hello()
    for index in range(12):
        # Twelve separate sightings, far enough apart to be separate episodes.
        tick = 100 + index * 1_000
        first.observe(seeing(view, tree("central"), tick=tick))
        first.observe(seeing(view, tick=tick + 10))
    finish(first, 20_000)
    assert len(first.loop.memory_store) >= 12

    earlier = len(journal(tmp_path, "memory_recalled"))
    second = Harness(tmp_path)
    second.hello()
    assert len(second.loop.memory.working) == 0, "waking up recalls nothing by itself"
    assert len(journal(tmp_path, "memory_recalled")) == earlier

    exhaust(second, view, start=100)
    recalls = journal(tmp_path, "memory_recalled")[earlier:]
    assert recalls, "the search cued recall"
    returned: set[str] = set()
    for record in recalls:
        assert len(record.payload["recalled"]) <= RECALL_LIMIT
        assert record.payload["considered"] >= len(record.payload["recalled"])
        returned.update(record.payload["recalled"])
    assert len(returned) < len(first.loop.memory_store), "the store never came back whole"


def test_a_search_that_found_nothing_is_remembered_as_exactly_that(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    first = Harness(tmp_path)
    first.hello()
    exhaust(first, view)
    searched = [episode for episode in episodes(first) if episode.kind == "searched"]
    assert searched, "the exhausted search was encoded"
    assert {episode.detail("conclusion") for episode in searched} == {NOT_FOUND}
    assert all(episode.provenance.source == "own_decision" for episode in searched)
    finish(first, 1_000)

    second = Harness(tmp_path)
    second.hello()
    _, policy, invocation = second.observe(seeing(view, tick=100))
    started = [
        record.payload
        for record in EvidenceJournal(tmp_path / "journal").read()
        if record.type == "information_search" and record.payload["phase"] == "started"
    ][-1]
    assert set(started["recalled"]) & {episode.memory_id for episode in searched}
    assert "recalls_unfound_search" in policy["reasonCodes"]
    # Remembering an earlier failure is not knowledge of absence, and without a
    # sense of place it does not change where Person looks.
    assert invocation["skillId"] == "look"
    assert all("absent" not in json.dumps(episode.to_json()) for episode in episodes(second))


def test_an_action_on_some_tree_is_not_remembered_as_one_on_the_tree_seen(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    # C4: Person sees tree A. The motor, choosing its own target from what the
    # body knows, fells tree B. Memory may say "I saw a tree" and "I cut wood";
    # it may not say "I cut the tree I saw".
    harness = Harness(tmp_path)
    harness.hello()
    _, policy, invocation = harness.observe(seeing(view, tree("central"), tick=100))
    assert invocation["skillId"] == "gather_wood", invocation["skillId"]
    harness.loop.handle(
        {
            **outcome("gather_wood"),
            "decisionId": invocation["decisionId"],
            "goalId": invocation["goalId"],
            "routineId": invocation["routineId"],
            "contextId": policy["contextId"],
        }
    )

    saw = [episode for episode in episodes(harness) if episode.kind == "perceived"]
    did = [episode for episode in episodes(harness) if episode.kind == "acted"]
    assert len(saw) == 1 and len(did) == 1
    action = json.dumps(did[0].to_json())
    assert saw[0].memory_id not in action
    assert saw[0].provenance.message_id is not None
    assert saw[0].provenance.message_id not in action
    for binding in ("target", "referent", "object", "tree_b", "what"):
        assert binding not in json.dumps(dict(did[0].details))


def test_every_memory_can_say_why_it_exists(tmp_path: Path, view: dict[str, Any]) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    _, policy, invocation = harness.observe(seeing(view, tree("central"), tick=100))
    harness.complete(invocation, policy, status="FAILED")
    hurt = seeing(view, tick=200)
    hurt["vitals"]["health"] = 14.0
    harness.observe(hurt)

    kinds = {episode.kind: episode for episode in episodes(harness)}
    assert {"perceived", "acted", "hurt"} <= set(kinds)
    assert kinds["perceived"].provenance.source == "perceived"
    assert kinds["acted"].provenance.source == "action_outcome"
    assert kinds["acted"].provenance.evidence_event_id is not None
    assert kinds["hurt"].provenance.source == "proprioceptive"
    assert set(KINDS) >= set(kinds)

    encodings = journal(tmp_path, "memory_encoded")
    assert {record.event_id for record in encodings} == {
        episode.memory_id for episode in episodes(harness)
    }


def test_provenance_is_a_closed_vocabulary() -> None:
    with pytest.raises(MemoryRecordError):
        Provenance("hunch")
    for later in ("inferred", "taught", "operator", "external"):
        with pytest.raises(MemoryRecordError):
            Provenance(later)
