"""The provider-neutral deliberation boundary (ADR 0020, C1).

Scripted models only; synthetic identities only. What is shown to a model,
what the gate admits, what is recorded and where, and that recording changes
nothing about what Person does.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from person_cognition.deliberation import (
    CAPS,
    INSTRUCTION_TEMPLATE,
    Capability,
    ModelResponse,
    ScriptedModel,
    build_context,
    canonical_json,
    gate,
    sha256_text,
)
from person_cognition.deliberation.metrics import deliberation_rate
from person_config import ConfigError, validate_config_document
from test_identity_continuity import Process, journal
from test_life_status import observe
from test_operational_state import world
from test_spatial import STILL

#: The experience stream every fixture test lives in (ADR 0025).
FIXTURE = "lived:minecraft/fixture"

REPOSITORY = Path(__file__).resolve().parents[3]
T0 = "2026-09-30T08:00:00Z"


@pytest.fixture
def view() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["payload"]["vitals"].update({"health": 20.0, "food": 20.0, "breath": 10})
    for key in ("resources", "passiveAnimals", "hostiles", "players", "containers", "hazards"):
        document["payload"]["nearby"][key] = []
    document["selfMotion"] = dict(STILL)
    return document


def lived(tmp_path: Path, view: dict[str, Any], *, mode: str = "record_only") -> Process:
    process = Process(tmp_path)
    process.hello(T0)
    world(process, "available", T0)
    observe(process, view, 100, health=14.0, food=9.0)
    observe(process, view, 140, health=12.0, food=9.0)
    process.loop.deliberation_mode = mode
    process.loop.deliberation_audit = tmp_path.parent / f"{tmp_path.name}-audit"
    return process


def capability_ref(context: Any, effect: str) -> str:
    return next(
        ref
        for ref, (section, item) in context.refs.items()
        if section == "capabilities" and effect in item["effects"]
    )


def valid(context: Any) -> dict[str, Any]:
    wood = capability_ref(context, "wood")
    return {
        "assessment": {"summary": "Health is falling and food is low.", "premises": ["s1", "s2"]},
        "uncertainties": [{"about": "Whether food is reachable here.", "premises": ["s2"]}],
        "strategies": [
            {
                "id": "s1",
                "goal_type": "SECURE_FOOD",
                "desired": [{"fact": "edible_food", "direction": "increase"}],
                "expected": [{"fact": "wood", "direction": "increase", "support": [wood]}],
                "capability_refs": [wood],
                "premises": ["s2"],
            }
        ],
        "preferred": "s1",
        "evidence_needed": [{"kind": "observe", "about": "What food is in view."}],
        "confidence": 0.6,
    }


# ----------------------------------------------------------------- context


def test_the_context_is_projections_only_with_no_affect_positions_or_evidence(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = lived(tmp_path, view)
    before = len(journal(tmp_path))
    held = len(process.loop.memory.working)
    context = process.loop.deliberation_context("reflection")
    text = canonical_json(context.document)
    assert len(journal(tmp_path)) == before, "building a context records nothing"
    assert len(process.loop.memory.working) == held, "and recalls nothing"
    for forbidden in ('"valence"', '"unease"', '"control"', '"distance"', '"x"', "event_id"):
        assert forbidden not in text, forbidden
    assert context.document["self"]["name"] == "test-person-000"
    facts = {item["fact"]: item["value"] for item in context.document["situation"]}
    assert facts["health"] == "low" and facts["food"] == "low"
    assert all(ref in context.refs for ref in ("s1", "c1"))


def test_every_collection_is_capped() -> None:
    many = [{"i": n} for n in range(100)]
    context = build_context(
        reason="reflection",
        request_refs=[f"x{n}" for n in range(100)],
        self_knowledge=None,
        world_available=True,
        situation=(),
        place=None,
        working_memory=[{"kind": "acted", "subjects": ["a"] * 50} for _ in range(20)],
        beliefs=many,
        hypotheses=many,
        goals=many,
        projects=many,
        recent=many,
        capabilities=[Capability(f"k{n}", "s" * 500, ("wood",)) for n in range(100)],
        vocabulary={"facts": ("wood",)},
    )
    document = context.document
    assert len(document["request"]["refs"]) == CAPS["request_refs"]
    for section in ("memories", "beliefs", "hypotheses", "goals", "projects", "recent"):
        assert len(document[section]) == CAPS[section], section
    assert len(document["capabilities"]) == CAPS["capabilities"]
    assert all(len(c["summary"]) <= 160 for c in document["capabilities"])
    assert all(len(m["subjects"]) <= CAPS["list_items"] for m in document["memories"])


def test_serialisation_is_canonical_for_hashing() -> None:
    assert canonical_json({"b": 1, "a": [2, {"d": 3, "c": 4}]}) == canonical_json(
        {"a": [2, {"c": 4, "d": 3}], "b": 1}
    )
    assert canonical_json({"a": 1}) == '{"a":1}'


# -------------------------------------------------------------------- gate


def test_a_grounded_proposal_is_admitted(tmp_path: Path, view: dict[str, Any]) -> None:
    context = lived(tmp_path, view).loop.deliberation_context("reflection")
    verdict = gate(json.dumps(valid(context)), context)
    assert verdict.admitted, verdict.rejections
    assert verdict.confidence == 0.6


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda p, c: p["strategies"][0].update(skill_invocation={"skillId": "flee"}), "schema"),
        (lambda p, c: p["strategies"][0].update(approach=["gather_wood", "craft"]), "schema"),
        (lambda p, c: p["strategies"][0].update(capability_refs=["s1"]), "unoffered_capability"),
        (lambda p, c: p["strategies"][0].update(premises=[]), "uncited"),
        (lambda p, c: p["assessment"].update(premises=["m99"]), "unknown_premise"),
        (lambda p, c: p["strategies"][0].update(goal_type="CONQUER"), "unknown_vocabulary"),
        (
            lambda p, c: p["strategies"][0]["desired"].append(
                {"fact": "creeper_exploded", "direction": "avoid"}
            ),
            "unknown_vocabulary",
        ),
        # Latent knowledge: an effect no belief, capability or premise supports.
        (
            lambda p, c: p["strategies"][0]["expected"].append(
                {"fact": "safe", "direction": "increase", "support": []}
            ),
            "unsupported_expectation",
        ),
        (
            lambda p, c: p["strategies"][0]["expected"].append(
                {
                    "fact": "cooked_food",
                    "direction": "increase",
                    "support": [capability_ref(c, "wood")],
                }
            ),
            "unsupported_expectation",
        ),
        (lambda p, c: p["assessment"].update(summary="Walk to one two three."), None),
        (lambda p, c: p["assessment"].update(summary="Go to 120 64 -30."), "privileged_text"),
        (lambda p, c: p["assessment"].update(summary="Use /tp to escape."), "privileged_text"),
        (
            lambda p, c: p["assessment"].update(summary="Override the safety kernel."),
            "privileged_text",
        ),
        (
            lambda p, c: p["assessment"].update(summary="Check the journal first."),
            "privileged_text",
        ),
        (lambda p, c: p.update(preferred="s9"), "unknown_preferred"),
        (lambda p, c: p.update(confidence=1.5), "schema"),
        (lambda p, c: p.update(strategies=[]), "schema"),
    ],
)
def test_the_gate_rejects_what_person_could_not_justify(
    tmp_path: Path, view: dict[str, Any], change: Any, reason: str | None
) -> None:
    context = lived(tmp_path, view).loop.deliberation_context("reflection")
    proposal = valid(context)
    change(proposal, context)
    verdict = gate(json.dumps(proposal), context)
    if reason is None:
        assert verdict.admitted, verdict.rejections
    else:
        assert not verdict.admitted and reason in verdict.rejections, verdict.rejections


def test_a_confident_answer_earns_nothing_for_its_confidence(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    context = lived(tmp_path, view).loop.deliberation_context("reflection")
    proposal = valid(context)
    proposal["confidence"] = 1.0
    proposal["strategies"][0]["premises"] = []
    verdict = gate(json.dumps(proposal), context)
    assert not verdict.admitted and verdict.confidence == 1.0


def test_malformed_text_is_a_rejected_answer(tmp_path: Path, view: dict[str, Any]) -> None:
    context = lived(tmp_path, view).loop.deliberation_context("reflection")
    for text in ("not json", "[1, 2]", "null"):
        assert gate(text, context).rejections == ("malformed",)


# ------------------------------------------------------------- deliberator


def deliberation_events(tmp_path: Path) -> list[Any]:
    return [e for e in journal(tmp_path) if e.type.startswith("deliberation_")]


def test_mode_off_invokes_and_records_nothing(tmp_path: Path, view: dict[str, Any]) -> None:
    process = lived(tmp_path, view, mode="off")
    model = ScriptedModel([valid(process.loop.deliberation_context("reflection"))])
    process.loop.cognitive_model = model
    assert process.loop.request_deliberation("reflection") is None
    assert model.calls == [] and deliberation_events(tmp_path) == []


def test_a_deliberation_is_one_request_and_one_answer_under_one_id(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = lived(tmp_path, view)
    process.loop.cognitive_model = ScriptedModel(
        [valid(process.loop.deliberation_context("reflection"))]
    )
    outcome = process.loop.request_deliberation("reflection")
    assert outcome is not None and outcome.status == "completed" and outcome.verdict.admitted
    requested, completed = deliberation_events(tmp_path)
    assert requested.type == "deliberation_requested"
    assert completed.type == "deliberation_completed"
    assert requested.payload["deliberation_id"] == completed.payload["deliberation_id"]
    instruction, context_text = process.loop.cognitive_model.calls[0]
    assert requested.payload["context_sha256"] == sha256_text(context_text)
    assert requested.payload["instruction_sha256"] == sha256_text(INSTRUCTION_TEMPLATE)
    assert instruction == INSTRUCTION_TEMPLATE
    assert requested.payload["context_schema"] == "person-deliberation-context-v2"
    assert requested.payload["proposal_schema"] == "person-deliberation-proposal-v1"
    assert (
        completed.payload["provider"] == "scripted" and completed.payload["verdict"] == "admitted"
    )
    assert completed.payload["proposal"]["preferred"] == "s1"


def test_raw_text_goes_only_to_the_audit_artifact(tmp_path: Path, view: dict[str, Any]) -> None:
    process = lived(tmp_path, view)
    marker = "UNGROUNDED-MARKER creepers explode, so dig down"
    process.loop.cognitive_model = ScriptedModel([marker])
    outcome = process.loop.request_deliberation("emergency_recurrence")
    assert outcome is not None and outcome.status == "completed"
    assert not outcome.verdict.admitted, "malformed is a rejected answer, not unavailability"
    for segment in (tmp_path / "journal").glob("*.jsonl"):
        assert marker not in segment.read_text(encoding="utf-8")
    artifact = json.loads(
        (process.loop.deliberation_audit / f"{outcome.deliberation_id}.json").read_text()
    )
    assert artifact["response"]["text"] == marker
    assert artifact["response"]["output_sha256"] == sha256_text(marker)
    assert not process.loop.deliberation_audit.is_relative_to(tmp_path), "outside the root"


def test_a_provider_with_no_answer_is_unavailable_and_person_carries_on(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    process = lived(tmp_path, view)
    process.loop.cognitive_model = ScriptedModel([None])
    outcome = process.loop.request_deliberation("no_viable_plan")
    assert outcome is not None and outcome.status == "unavailable"
    kinds = [e.type for e in deliberation_events(tmp_path)]
    assert kinds == ["deliberation_requested", "deliberation_unavailable"]
    assert deliberation_events(tmp_path)[1].payload["reason"] == "timeout"
    observe(process, view, 180, health=12.0, food=9.0)
    assert process.loop.running


def test_an_adapter_that_raises_is_an_unavailable_backend(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    class Broken:
        provider = "broken"
        model = "broken-v0"

        def deliberate(self, instruction: str, context: str, *, timeout_s: float) -> ModelResponse:
            raise RuntimeError("quota exceeded, perhaps")

    process = lived(tmp_path, view)
    process.loop.cognitive_model = Broken()
    outcome = process.loop.request_deliberation("reflection")
    assert outcome is not None and outcome.status == "unavailable"
    assert deliberation_events(tmp_path)[-1].payload["reason"] == "backend"


def test_a_request_left_unanswered_by_a_crash_stays_unanswered(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    class Crashing:
        provider = "crashing"
        model = "crashing-v0"

        def deliberate(self, instruction: str, context: str, *, timeout_s: float) -> ModelResponse:
            raise KeyboardInterrupt  # the process dies mid-call

    process = lived(tmp_path, view)
    process.loop.cognitive_model = Crashing()
    with pytest.raises(KeyboardInterrupt):
        process.loop.request_deliberation("reflection")
    Process(tmp_path).hello("2026-09-30T09:00:00Z")
    kinds = [e.type for e in deliberation_events(tmp_path)]
    assert kinds == ["deliberation_requested"], "no completion is synthesised on restart"


# --------------------------------------------------------------- isolation


def scrub(message: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in message.items() if k not in ("messageId", "timestamp")}


def run(
    tmp_path: Path, view: dict[str, Any], *, deliberate: bool, monkeypatch: pytest.MonkeyPatch
) -> Process:
    # The same message and session ids in both runs, so decision ids match too.
    import test_identity_continuity
    import test_loop

    counter = iter(range(1, 10_000))
    ids = SimpleNamespace(uuid4=lambda: uuid.UUID(int=next(counter)))
    for helper in (test_identity_continuity, test_loop):
        monkeypatch.setattr(helper, "uuid", ids)
    process = Process(tmp_path)
    process.hello(T0)
    world(process, "available", T0)
    if deliberate:
        process.loop.deliberation_mode = "record_only"
        process.loop.deliberation_audit = tmp_path.parent / f"{tmp_path.name}-audit"
    script = [
        (100, 20.0, 18.0),
        (140, 16.0, 14.0),
        (180, 11.0, 9.0),
        (220, 6.0, 5.0),
        (260, 6.0, 4.0),
    ]
    for tick, health, food in script:
        if deliberate:
            process.loop.cognitive_model = ScriptedModel(
                [valid(process.loop.deliberation_context("reflection"))]
            )
            process.loop.request_deliberation("reflection")
        observe(process, view, tick, health=health, food=food)
    return process


def test_record_only_changes_nothing_but_its_own_evidence(
    tmp_path: Path, view: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = run(tmp_path / "plain", view, deliberate=False, monkeypatch=monkeypatch)
    recorded = run(tmp_path / "recorded", view, deliberate=True, monkeypatch=monkeypatch)
    assert [scrub(m) for m in plain.sent] == [scrub(m) for m in recorded.sent], (
        "the same decisions, message for message"
    )

    def cognitive(root: Path) -> list[tuple[str, Any]]:
        return [
            (e.type, e.payload)
            for e in journal(root)
            if not e.type.startswith("deliberation_")
            and e.type not in ("person_founded", "session_started")
        ]

    assert cognitive(tmp_path / "plain") == cognitive(tmp_path / "recorded")
    assert len(deliberation_events(tmp_path / "recorded")) == 10
    assert plain.loop.memory.now == recorded.loop.memory.now


def test_nothing_in_the_decision_loop_calls_for_deliberation() -> None:
    source = (REPOSITORY / "apps/cognition/python/person_cognition/loop.py").read_text()
    assert source.count("request_deliberation(") == 1, "defined, never called, in C1"
    audit_readers = [
        path
        for path in (REPOSITORY / "apps/cognition/python/person_cognition").rglob("*.py")
        if "deliberation-audit" in path.read_text() or "_audit" in path.read_text()
    ]
    names = sorted(path.name for path in audit_readers)
    assert names == ["deliberator.py", "loop.py"], names
    deliberator = (
        REPOSITORY / "apps/cognition/python/person_cognition/deliberation/deliberator.py"
    ).read_text()
    assert "read_text" not in deliberator and "open(" not in deliberator, "write-only"


# ------------------------------------------------------------ config, metric


def test_deliberation_mode_is_off_by_default_and_only_the_known_modes_exist() -> None:
    from person_config import load_cognition_settings

    settings = load_cognition_settings(str(REPOSITORY / "examples/fixture.toml"))
    assert settings.deliberation_mode == "off"
    base = json.loads(json.dumps(_example_document()))
    base["deliberation"] = {"mode": "record_only"}
    validate_config_document(base)
    base["deliberation"] = {"mode": "active"}  # ADR 0021
    validate_config_document(base)
    base["deliberation"] = {"mode": "always"}
    with pytest.raises(ConfigError):
        validate_config_document(base)


def _example_document() -> dict[str, Any]:
    import tomllib

    return tomllib.loads((REPOSITORY / "examples/fixture.toml").read_text(encoding="utf-8"))


def test_the_rate_of_deliberation_is_per_experienced_hour_and_by_reason() -> None:
    class Event:
        def __init__(self, type_: str, reason: str) -> None:
            self.type = type_
            self.payload = {"reason": reason}

    events = [
        Event("deliberation_requested", "no_viable_plan"),
        Event("deliberation_requested", "emergency_recurrence"),
        Event("deliberation_requested", "emergency_recurrence"),
        Event("deliberation_completed", "x"),
    ]
    rate = deliberation_rate(events, experienced_ticks=36_000)
    assert rate["deliberations"] == 3 and rate["per_experienced_hour"] == 6.0
    assert rate["by_reason"] == {"emergency_recurrence": 2, "no_viable_plan": 1}
    assert deliberation_rate([], 0)["per_experienced_hour"] is None


def test_the_deliberator_itself_refuses_to_run_when_off(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    from person_cognition.deliberation import Deliberator

    context = lived(tmp_path, view).loop.deliberation_context("reflection")
    model = ScriptedModel([valid(context)])
    recorded: list[Any] = []
    off = Deliberator(mode="off", model=model, record=lambda t, p: recorded.append(t))
    assert off.deliberate(context, experienced_tick=0) is None
    assert model.calls == [] and recorded == []
    with pytest.raises(ValueError):
        Deliberator(mode="bogus", model=model, record=lambda t, p: None)


def test_a_belief_person_holds_is_shown_with_its_uncertainty_and_can_support(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    from person_cognition.effect_learning import EffectBelief

    process = lived(tmp_path, view)
    beliefs = process.loop.effect_beliefs.tables["active"]
    beliefs[(FIXTURE, "gather_wood", "wood")] = EffectBelief(
        "gather_wood", "wood", supporting=3.0, contradicting=1.0
    )
    context = process.loop.deliberation_context("reflection")
    (shown,) = context.document["beliefs"]
    assert shown["skill"] == "gather_wood" and shown["fact"] == "wood"
    assert 0 < shown["estimate"] < 1 and 0 < shown["strength"] < 1
    proposal = valid(context)
    proposal["strategies"][0]["expected"] = [
        {"fact": "wood", "direction": "increase", "support": [shown["ref"]]}
    ]
    assert gate(json.dumps(proposal), context).admitted
    proposal["strategies"][0]["expected"][0]["fact"] = "stone"
    assert "unsupported_expectation" in gate(json.dumps(proposal), context).rejections


def test_a_template_answer_names_a_recent_outcome_by_its_skill() -> None:
    from person_cognition.deliberation.model import TemplateModel

    context = {
        "recent": [
            {"ref": "r1", "skill": "gather_wood", "emergency": False},
            {"ref": "r2", "skill": "look", "emergency": False},
        ]
    }
    model = TemplateModel([{"premises": ["$recent:gather_wood", "$recent:mine_stone"]}])
    answer = json.loads(model.deliberate("", json.dumps(context), timeout_s=1).text or "")
    assert answer["premises"] == ["r1", "$recent:mine_stone"], (
        "a placeholder with nothing to stand for is left for the gate to see"
    )


# ---------------------------------- request-local recall (ADR 0020, as amended)


def berries_remembered(process: Any) -> str:
    from test_memory import encoded

    held = {held.episode.memory_id for held in process.loop.memory.working.items()}
    memory_id = encoded(process.loop.memory_store, "plant_food", at=50, salience=0.6)
    assert memory_id not in held
    return memory_id


def test_a_request_recalls_for_itself_and_working_memory_is_untouched(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    from person_cognition.deliberation.metareasoning import Trigger

    process = lived(tmp_path, view)
    memory_id = berries_remembered(process)
    before = [h.episode.memory_id for h in process.loop.memory.working.items()]
    events = len(journal(tmp_path))
    trigger = Trigger("repeated_prediction_error", "gather_plant_food:plant_food", {})
    context, _ = process.loop._trigger_context(trigger)
    assert context.retrieval is not None
    assert memory_id in context.retrieval.memory_ids
    assert context.retrieval.cue_subjects == ("plant_food",)
    assert any("plant_food" in m["subjects"] for m in context.document["memories"])
    assert [h.episode.memory_id for h in process.loop.memory.working.items()] == before
    assert len(journal(tmp_path)) == events, "preparing the context records nothing"
    plain = process.loop.deliberation_context(trigger.kind)
    assert not any("plant_food" in m["subjects"] for m in plain.document["memories"]), (
        "passive context construction recalls nothing"
    )


def test_record_only_and_active_requests_recall_the_same_slice(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    from person_cognition.deliberation.metareasoning import Trigger

    process = lived(tmp_path, view)
    berries_remembered(process)
    trigger = Trigger("repeated_prediction_error", "gather_plant_food:plant_food", {})
    slices = []
    for mode in ("record_only", "active"):
        process.loop.deliberation_mode = mode
        context, _ = process.loop._trigger_context(trigger)
        slices.append((context.retrieval, context.document["memories"]))
    assert slices[0] == slices[1]
