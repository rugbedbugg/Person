"""Causal hypotheses and controlled experiments: reasoning is not evidence.

The rules defended here are ADR 0012's. A hypothesis is typed, structured and
falsifiable, in a closed vocabulary of what Person perceives and can do. A
proposer, deterministic or a language model, only proposes: the grounding
gate refuses anything privileged, invented, ungrounded or self-certifying,
and admits the rest with no evidence at all. Evidence comes from trials after
the hypothesis existed, split by whether the condition held and by whether
Person intervened to test it; correlation alone never settles anything, and
later evidence can always reverse it. Experiments are ordinary goals,
bounded, preemptible and resumable, and the learning mode decides whether
any of it happens and whether any of it may act.

Cognition-level evidence. The TypeScript suite runs the same loop in a
fixture world with a hidden rule, shifted by 1000 blocks and with hidden
hazards.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import pytest
from person_cognition.hypotheses import (
    HYPOTHESIS_LIMIT,
    CausalHypothesis,
    ContrastProposer,
    HypothesisBook,
    ModelProposer,
    Perceived,
    ReasoningContext,
    Rejection,
    TrialRecord,
    admit,
    design,
    epistemic_value,
    hypothesis_term,
)
from person_cognition.hypotheses.experiments import (
    DAILY_TRIALS,
    INVESTIGATION_PRIORITY,
    MAX_ATTEMPTS,
    TRIALS_PER_ARM,
)
from person_cognition.hypotheses.hypothesis import (
    EVIDENCE_SOURCE,
    INFERENCE,
    INITIAL,
    PERSONAL_EXPERIMENT,
    PERSONAL_OBSERVATION,
    STANDINGS,
)
from person_cognition.memory.episodes import Episode
from person_cognition.prediction import PendingPrediction
from person_persistence import EvidenceJournal, new_event
from person_policy import EvidencePolicyProvider, RoutineCandidate, RoutineStatistics
from person_skills import skill_registry
from test_loop import Harness, envelope
from test_spatial import STILL

REPOSITORY = Path(__file__).resolve().parents[3]
BERRIES = (
    {"fact": "plant_food", "op": "+=", "value": 6},
    {"fact": "edible_food", "op": "+=", "value": 6},
)
RAIN = Perceived("rain", "day", "place_1")
CLEAR = Perceived("clear", "day", "place_1")


# ------------------------------------------------------------------ helpers


def record(ref: str, verdict: str, weather: str, place: str | None = "place_1") -> TrialRecord:
    return TrialRecord(
        ref=ref,
        skill="gather_plant_food",
        fact="plant_food",
        verdict=verdict,
        conditions={"weather": weather, "day_phase": "day", "place": place},
    )


def context(*trials: TrialRecord) -> ReasoningContext:
    registry = skill_registry()
    from person_cognition.hypotheses import evaluable_effects, vocabulary

    return ReasoningContext(
        skill="gather_plant_food",
        fact="plant_food",
        question="variation",
        trials=trials
        or (
            record("t1", "contradicts", "rain"),
            record("t2", "contradicts", "rain"),
            record("t3", "supports", "clear"),
        ),
        vocabulary=vocabulary(["place_1"]),
        interventions=evaluable_effects(registry, registry.ids),
        belief=None,
    )


def proposal(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "condition": {"variable": "weather", "value": "rain"},
        "intervention": "gather_plant_food",
        "outcome": {"fact": "plant_food", "direction": "less_likely"},
        "horizon": 1,
        "premises": ["t1", "t2", "t3"],
        "rationale": "berries seem to fail in the rain",
    }
    body.update(changes)
    return body


def admitted(**changes: Any) -> CausalHypothesis:
    outcome = admit(
        proposal(**changes), context(), hypothesis_id="hyp_1", proposer="deterministic", now=0
    )
    assert isinstance(outcome, CausalHypothesis), outcome
    return outcome


def with_trials(hypothesis: CausalHypothesis, *trials: tuple[str, str, str]) -> CausalHypothesis:
    for index, (arm, kind, verdict) in enumerate(trials):
        hypothesis = hypothesis.updated(arm, kind, verdict, f"e{index}")
    return hypothesis


def repeated(arm: str, kind: str, verdict: str, times: int) -> list[tuple[str, str, str]]:
    return [(arm, kind, verdict)] * times


def rain_breaks_it(kind: str = "interventional", times: int = TRIALS_PER_ARM) -> list[Any]:
    return [
        *repeated("held", kind, "contradicts", times),
        *repeated("absent", kind, "supports", times),
    ]


# ----------------------------------------------------- 1. from an anomaly


def settle(
    harness: Harness,
    verdict: str,
    now: Perceived,
    *,
    after: Perceived | None = None,
    experiment: str | None = None,
    goal_id: str = "g",
    status: str = "SUCCESS",
    reasons: tuple[str, ...] = (),
    executed: str = "gather_plant_food",
) -> None:
    """One settled prediction, through the loop's own settling path."""
    loop = harness.loop
    loop.pending_prediction = PendingPrediction(
        decision_id="33333333-3333-4333-8333-333333333333",
        context_id="c",
        routine_id="r",
        goal_id=goal_id,
        requested_skill="gather_plant_food",
        state_before={"plant_food": 0.0, "edible_food": 0.0},
        tick=1,
        executed_skill=executed,
        expected_effects=BERRIES,
        status=status,
        requested_status=status,
        reason_codes=reasons,
        emergency=executed != "gather_plant_food",
        settled=True,
        perceived=now.to_json(),
        experiment=experiment,
    )
    gained = 6.0 if verdict == "supports" else 0.0
    loop._now = after or now
    loop._settle_prediction({"plant_food": gained, "edible_food": gained}, 10)


def journal(harness: Harness, kind: str) -> list[dict[str, Any]]:
    return [
        dict(event.payload)
        for event in EvidenceJournal(harness.evidence / "journal").read()
        if event.type == kind
    ]


def anomalous(harness: Harness) -> None:
    settle(harness, "contradicts", RAIN)
    settle(harness, "contradicts", RAIN)
    settle(harness, "supports", CLEAR)


def about_rain(harness: Harness, table: str = "active") -> CausalHypothesis:
    """The hypothesis that it is the rain."""
    (found,) = [
        hypothesis
        for hypothesis in harness.loop.hypothesis_book.hypotheses[table].values()
        if hypothesis.condition.variable == "weather"
    ]
    return found


def test_a_prediction_anomaly_produces_a_proposed_structured_hypothesis(tmp_path: Path) -> None:
    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    anomalous(harness)
    proposed = journal(harness, "hypothesis_proposed")
    assert proposed, journal(harness, "hypothesis_rejected")
    # Two failures in the rain are already a repeated error, and every
    # condition they shared is a guess; nothing yet tells them apart.
    assert proposed[0]["question"] == "repeated_error"
    guesses = {
        (entry["hypothesis"]["condition"]["variable"], entry["hypothesis"]["condition"]["value"])
        for entry in proposed
    }
    assert ("weather", "rain") in guesses and len(guesses) <= 3
    first = next(
        e["hypothesis"] for e in proposed if e["hypothesis"]["condition"]["value"] == "rain"
    )
    assert first["intervention"] == "gather_plant_food"
    assert first["outcome"] == {"fact": "plant_food", "direction": "less_likely"}
    assert first["provenance"]["proposer"] == "deterministic"
    assert first["provenance"]["premises"], "it says what motivated it"


# ------------------------------------------- 2-3. representation and words


def test_a_hypothesis_has_no_executable_or_free_text_semantics() -> None:
    hypothesis = admitted()
    types = {field.name: field.type for field in fields(CausalHypothesis)}
    assert "Callable" not in json.dumps(types)
    # The only free text is the rationale, and it changes nothing.
    other = admitted(rationale="an entirely different story about lava")
    evidence = rain_breaks_it()
    first, second = with_trials(hypothesis, *evidence), with_trials(other, *evidence)
    assert first.summary() == second.summary()
    assert hypothesis_term({"h": first}, RAIN)(("gather_plant_food",)) == hypothesis_term(
        {"h": second}, RAIN
    )(("gather_plant_food",))


def test_every_concept_a_hypothesis_names_is_one_person_has() -> None:
    hypothesis = admitted()
    ctx = context()
    assert hypothesis.condition.value in ctx.vocabulary[hypothesis.condition.variable]
    assert hypothesis.intervention in ctx.interventions
    assert hypothesis.outcome.fact in ctx.interventions[hypothesis.intervention]
    # A place Person never formed cannot be named.
    unformed = admit(
        proposal(condition={"variable": "place", "value": "place_99"}),
        ctx,
        hypothesis_id="h",
        proposer="deterministic",
        now=0,
    )
    assert isinstance(unformed, Rejection) and "unavailable_value" in unformed.reasons


# ------------------------------------------ 4-5. reasoning and quarantine


def test_a_language_model_reasons_for_person_but_testifies_to_nothing(tmp_path: Path) -> None:
    seen: list[dict[str, Any]] = []

    def model(text: str) -> str:
        seen.append(json.loads(text))
        # The model says it is sure. That is worth nothing.
        body = proposal(premises=[seen[-1]["trials"][0]["ref"]])
        return json.dumps([body])

    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    harness.loop.proposer = ModelProposer(model)
    anomalous(harness)
    held = about_rain(harness)
    assert held.provenance.proposer == "language_model"
    assert held.provenance.source == INFERENCE
    assert held.confidence == 0 and held.relation is None and held.standing == "unresolved"
    assert held.status in {"proposed", "testable"}
    # What the model was shown: the bounded reasoning context, and only that.
    assert set(seen[0]) == {
        "question",
        "skill",
        "fact",
        "trials",
        "vocabulary",
        "interventions",
        "belief",
        "form",
    }
    shown = json.dumps(seen)
    for private in ('"x"', "position", "yaw", "entityId", "homeDistance", "snapshot"):
        assert private not in shown, private


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"position": {"x": 10, "y": 64, "z": -3}}, "privileged_reference:position"),
        ({"condition": {"variable": "x", "value": "10"}}, "unknown_variable"),
        ({"entity_id": 1234}, "privileged_reference:entity_id"),
        ({"target": "that tree"}, "privileged_reference:target"),
        ({"condition": {"variable": "soil_moisture", "value": "wet"}}, "unknown_variable"),
        ({"confidence": 0.9}, "claims_authority:confidence"),
        ({"known": True, "source": "common knowledge"}, "claims_authority:known"),
        ({"outcome": {"direction": "less_likely"}}, "no_observable_outcome"),
        ({"outcome": {"fact": "rested", "direction": "less_likely"}}, "unfalsifiable"),
        ({"outcome": {"fact": "shelter_complete", "direction": "less_likely"}}, "unfalsifiable"),
        ({"intervention": "teleport_home"}, "unavailable_capability"),
        ({"intervention": "flee"}, "unavailable_capability"),
        ({"premises": []}, "ungrounded"),
        ({"premises": ["something the model imagined"]}, "ungrounded"),
        ({"horizon": 40}, "unsupported_horizon"),
        ({"code": "lambda state: state['wood'] > 3"}, "privileged_reference:code"),
    ],
)
def test_malformed_privileged_and_self_certifying_proposals_are_quarantined(
    changes: dict[str, Any], reason: str
) -> None:
    outcome = admit(
        proposal(**changes), context(), hypothesis_id="h", proposer="language_model", now=0
    )
    assert isinstance(outcome, Rejection), outcome
    assert reason in outcome.reasons, outcome.reasons


def test_quarantined_proposals_are_journalled_without_their_contents(tmp_path: Path) -> None:
    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    harness.loop.proposer = ModelProposer(
        lambda _: json.dumps([proposal(position={"x": 777}), "not an object"])
    )
    anomalous(harness)
    rejected = journal(harness, "hypothesis_rejected")
    assert rejected and all(entry["proposer"] == "language_model" for entry in rejected)
    assert "777" not in json.dumps(rejected), "the values it tried are not kept"
    assert not harness.loop.hypothesis_book.hypotheses["active"]
    unparsable = Harness(tmp_path / "prose", learning_mode="supervised")
    unparsable.hello()
    unparsable.loop.proposer = ModelProposer(lambda _: "Berries hate rain, trust me.")
    anomalous(unparsable)
    assert journal(unparsable, "hypothesis_rejected")[0]["reasons"] == ["malformed"]


# ---------------------------------------------------------- 6. persistence


def test_hypotheses_and_their_evidence_survive_restart(tmp_path: Path) -> None:
    first = Harness(tmp_path, learning_mode="supervised")
    first.hello()
    anomalous(first)
    settle(first, "contradicts", RAIN)
    before = first.loop.hypothesis_book.to_json()
    assert before["hypotheses"]["active"]

    second = Harness(tmp_path, learning_mode="supervised")
    second.hello()
    assert second.loop.hypothesis_book.to_json() == before
    assert len(second.loop.memory.working) == 0


# ------------------------------------------------- 7-11. evidence and standing


def test_one_supporting_trial_is_not_certainty() -> None:
    once = with_trials(
        admitted(),
        ("held", "interventional", "contradicts"),
        ("absent", "interventional", "supports"),
    )
    assert once.standing == "unresolved"
    assert once.confidence < 0.5
    assert once.relation is not None and 0 < once.relation < 1


def test_repeated_controlled_support_raises_confidence_until_it_is_supported() -> None:
    confidences = []
    hypothesis = admitted()
    for _ in range(TRIALS_PER_ARM):
        hypothesis = with_trials(
            hypothesis,
            ("held", "interventional", "contradicts"),
            ("absent", "interventional", "supports"),
        )
        confidences.append(hypothesis.confidence)
    assert confidences == sorted(confidences) and confidences[0] < confidences[-1]
    assert hypothesis.standing == "supported"
    assert hypothesis.status == "supported"


def test_repeated_contradiction_lowers_it_to_contradicted() -> None:
    hypothesis = with_trials(
        admitted(),
        *repeated("held", "interventional", "supports", TRIALS_PER_ARM),
        *repeated("absent", "interventional", "supports", TRIALS_PER_ARM),
    )
    assert hypothesis.relation is not None and hypothesis.relation <= 0.1
    assert hypothesis.standing == "contradicted"
    assert len(hypothesis.contradicting) == TRIALS_PER_ARM, "the successes in the rain"
    assert len(hypothesis.supporting) == TRIALS_PER_ARM, "the successes without it"


def test_later_evidence_reverses_the_conclusion() -> None:
    supported = with_trials(admitted(), *rain_breaks_it())
    assert supported.standing == "supported"
    # The world changes: now berries come in the rain too.
    later = with_trials(supported, *repeated("held", "interventional", "supports", 12))
    assert later.standing in {"weakened", "contradicted"}
    assert later.relation is not None and supported.relation is not None
    assert later.relation < supported.relation


def test_correlation_counts_for_less_than_intervention_and_settles_nothing() -> None:
    observed = with_trials(admitted(), *rain_breaks_it("observational"))
    tested = with_trials(admitted(), *rain_breaks_it("interventional"))
    assert observed.confidence < tested.confidence
    assert observed.standing == "unresolved", "correlation alone never settles it"
    assert tested.standing == "supported"
    # However much of it there is.
    plenty = with_trials(admitted(), *rain_breaks_it("observational", times=40))
    assert plenty.confidence > tested.confidence and plenty.standing == "unresolved"
    assert EVIDENCE_SOURCE == {
        "interventional": PERSONAL_EXPERIMENT,
        "observational": PERSONAL_OBSERVATION,
    }


def test_the_motivating_trials_are_premises_not_evidence(tmp_path: Path) -> None:
    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    anomalous(harness)
    hypothesis = about_rain(harness)
    assert hypothesis.provenance.premises
    # The success in clear weather came after it was proposed: it counts.
    assert hypothesis.cells["absent:observational"].trials == 1
    assert hypothesis.cells["held:observational"].trials == 0, "its premises do not"
    settle(harness, "contradicts", RAIN)
    after = about_rain(harness)
    assert after.cells["held:observational"].trials == 1


# --------------------------------------------------- 12-17. experiments


def test_an_experiment_uses_only_a_capability_person_has_and_spends_nothing() -> None:
    registry = skill_registry()
    plan = design(admitted(), registry)
    assert plan is not None
    assert plan.intervention == "gather_plant_food" and plan.variable == "weather"
    assert plan.trials_per_arm == TRIALS_PER_ARM and plan.max_attempts == MAX_ATTEMPTS
    # Nothing that uses materials up, nothing risky, nothing an emergency.
    eating = replace(admitted(), intervention="eat_to_target")
    assert design(eating, registry) is None
    hunting = replace(admitted(), intervention="hunt_safe_passive_animals")
    assert design(hunting, registry) is None, "riskier than the limit"
    fleeing = replace(admitted(), intervention="flee")
    assert design(fleeing, registry) is None


def test_the_value_of_finding_out_is_inspectable_and_discounted() -> None:
    hypothesis = admitted()
    plan = design(hypothesis, skill_registry())
    assert plan is not None
    calm = epistemic_value(
        hypothesis, plan, relevance=1.0, discrimination=1.0, tolerance=1.0, open_projects=0
    )
    uneasy = epistemic_value(
        hypothesis, plan, relevance=1.0, discrimination=1.0, tolerance=0.5, open_projects=0
    )
    busy = epistemic_value(
        hypothesis, plan, relevance=1.0, discrimination=1.0, tolerance=1.0, open_projects=2
    )
    assert set(calm.parts) == {
        "uncertainty",
        "relevance",
        "discrimination",
        "cost",
        "risk",
        "disruption",
    }
    assert uneasy.value < calm.value and busy.value < calm.value
    certain = with_trials(hypothesis, *rain_breaks_it(times=12))
    settled = epistemic_value(
        certain, plan, relevance=1.0, discrimination=1.0, tolerance=1.0, open_projects=0
    )
    assert settled.value < calm.value, "less to find out"


def calm_view() -> dict[str, Any]:
    """A fed, sheltered, equipped Person beside berry bushes: nothing presses."""
    document: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["vitals"].update({"health": 20.0, "food": 20.0})
    for key in ("resources", "passiveAnimals", "hostiles", "players", "containers", "hazards"):
        document["nearby"][key] = []
    document["nearby"]["resources"] = [
        {
            "kind": "plant_food",
            "name": "sweet_berry_bush",
            "distance": 4.0,
            "bearing": "ahead",
            "elevation": "level",
            "rangeBand": "reach",
            "detail": "central",
            "harvestPermitted": True,
        }
    ]
    document["home"].update(
        {
            "shelterState": "complete",
            "foodReserve": 0,
        }
    )
    document["inventory"]["items"] = [{"name": "stone_pickaxe", "count": 1}]
    document["inventory"]["categories"].update({"wood": 0, "tools": 1})
    document["selfMotion"] = dict(STILL)
    return document


class HiddenWorld:
    """A deterministic world whose rule Person is never told.

    While `barren` holds of the weather, harvesting berries yields nothing.
    The loop sees only observations and outcomes.
    """

    def __init__(self, harness: Harness, barren: set[str]) -> None:
        self.harness = harness
        self.barren = barren
        self.berries = 0
        self.food = 20.0
        self.tick = 100
        self.hostile = False
        #: Answer the next experimental trial as preempted.
        self.preempt_next_trial = False

    def observation(self, weather: str) -> dict[str, Any]:
        document = calm_view()
        document["tick"] = self.tick
        document["messageId"] = envelope("Observation", self.tick)["messageId"]
        document["environment"]["weather"] = weather
        document["vitals"]["food"] = self.food
        if self.berries:
            document["inventory"]["items"].append({"name": "sweet_berries", "count": self.berries})
            document["inventory"]["categories"]["food"] = self.berries
        if self.hostile:
            document["nearby"]["hostiles"] = [
                {
                    "kind": "hostile",
                    "name": "zombie",
                    "distance": 3.0,
                    "bearing": "ahead",
                    "elevation": "level",
                    "rangeBand": "close",
                    "detail": "central",
                }
            ]
        return document

    def step(
        self, weather: str, *, preempted: bool = False
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Person observes, decides and acts once; the world answers by its rule."""
        goal, policy, invocation = self.harness.observe(self.observation(weather))
        skill = invocation["skillId"]
        status, reasons, effects = "SUCCESS", [], []
        if self.preempt_next_trial and goal["goal"]["goalType"] == "INVESTIGATE":
            self.preempt_next_trial = False
            preempted = True
        if preempted:
            # Something more urgent took over before the skill could act.
            status, reasons = "PREEMPTED", ["preempted_by_threat"]
            effects = list(BERRIES) if skill == "gather_plant_food" else []
        elif skill == "gather_plant_food":
            effects = list(BERRIES)
            if weather in self.barren:
                status, reasons = "FAILED", ["no_yield"]
            else:
                self.berries += 6
        elif skill == "eat_to_target":
            eaten = min(self.berries, 4)
            self.berries -= eaten
            self.food = min(20.0, self.food + 2 * eaten)
            effects = [{"fact": "food_level", "op": "max", "value": 16}]
        self.tick += 50
        self.harness.loop.handle(
            {
                **envelope("SkillOutcome", self.tick),
                "decisionId": invocation["decisionId"],
                "goalId": invocation["goalId"],
                "routineId": invocation["routineId"],
                "contextId": policy["contextId"],
                "requestedSkill": skill,
                "requestedParameters": invocation["parameters"],
                "requestedSkillStatus": status,
                "executedSkill": skill,
                "executedParameters": invocation["parameters"],
                "status": status,
                "emergency": False,
                "reasonCodes": reasons,
                "effects": [],
                "expectedEffects": effects,
                "healthBefore": 20,
                "healthAfter": 20,
                "foodBefore": self.food,
                "foodAfter": self.food,
                "healthCost": 0,
                "resourceCost": [],
                "inventoryDelta": [],
                "elapsedTicks": 50,
                "interruptReason": None,
                "completionEvidence": {"kinds": ["elapsed_ticks"], "details": {}},
            }
        )
        self.tick += 10
        return goal, invocation


def hungry_start(world: HiddenWorld) -> None:
    """Ordinary life: hungry, Person gathers berries, and it goes differently."""
    for weather in ("rain", "rain", "clear"):
        world.food = 15.0
        world.berries = 0
        goal, invocation = world.step(weather)
        assert goal["goal"]["goalType"] == "SECURE_FOOD", goal
        assert invocation["skillId"] == "gather_plant_food"
    world.food, world.berries = 20.0, 0


def weather_at(step: int) -> str:
    """Spells of weather, each longer than a few actions, as in any world."""
    return "rain" if (step // 5) % 2 == 0 else "clear"


def investigate(world: HiddenWorld, steps: int) -> list[tuple[str, str, str]]:
    seen = []
    for step in range(steps):
        weather = weather_at(step)
        goal, invocation = world.step(weather)
        seen.append((weather, goal["goal"]["goalType"], invocation["skillId"]))
    return seen


def test_the_flagship_a_hidden_rule_is_noticed_tested_and_believed(tmp_path: Path) -> None:
    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    world = HiddenWorld(harness, barren={"rain"})
    hungry_start(world)
    book = harness.loop.hypothesis_book
    hypothesis = about_rain(harness)
    assert hypothesis.standing == "unresolved"

    seen = investigate(world, 40)
    trials = [entry for entry in seen if entry[1] == "INVESTIGATE"]
    assert trials, seen
    # Every trial was the intervention, through the ordinary goal path.
    assert {skill for _, _, skill in trials} == {"gather_plant_food"}
    after = about_rain(harness)
    assert after.standing == "supported", after.summary()
    assert after.controlled
    investigation = next(
        inv for inv in book.investigations.values() if inv.hypothesis_id == after.hypothesis_id
    )
    assert investigation.status == "COMPLETE"
    assert investigation.attempts <= MAX_ATTEMPTS
    goals = [
        entry for entry in journal(harness, "goal_selected") if entry["goal_type"] == "INVESTIGATE"
    ]
    assert all(entry["priority"] == INVESTIGATION_PRIORITY for entry in goals)
    assert all(entry["affect_bias"] == 0 for entry in goals), "no affect on curiosity's priority"

    # Believing it now bears on choice, when it rains, and only then.
    term = harness.loop._hypotheses
    harness.loop._now = RAIN
    assert term()(("gather_plant_food",)) < 0
    harness.loop._now = CLEAR
    assert term()(("gather_plant_food",)) == 0


def test_experiment_trials_pass_the_ordinary_decision_path(tmp_path: Path) -> None:
    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    world = HiddenWorld(harness, barren={"rain"})
    hungry_start(world)
    before = len(harness.sent)
    investigate(world, 12)
    produced = {message["type"] for message in harness.sent[before:]}
    assert produced == {"GoalDecision", "PolicyDecision", "SkillInvocation"}
    trial = next(
        message
        for message in harness.sent[before:]
        if message["type"] == "GoalDecision" and message["goal"]["goalType"] == "INVESTIGATE"
    )
    assert harness.loop.validator.validate(trial)[0], "a valid protocol message"


def test_a_refused_trial_is_not_evidence_about_the_world(tmp_path: Path) -> None:
    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    anomalous(harness)
    hypothesis = about_rain(harness)
    already = len(journal(harness, "hypothesis_evidence"))
    for status, reasons, executed in (
        ("INVALIDATED", ("protected_area",), "gather_plant_food"),
        ("SUCCESS", (), "flee"),
        ("FAILED", ("missing_tool",), "gather_plant_food"),
    ):
        settle(
            harness,
            "contradicts",
            RAIN,
            experiment=hypothesis.hypothesis_id,
            status=status,
            reasons=reasons,
            executed=executed,
        )
    after = about_rain(harness)
    assert after.cells == hypothesis.cells, "nothing was counted"
    recorded = [
        entry
        for entry in journal(harness, "hypothesis_evidence")[already:]
        if entry["hypothesis_id"] == hypothesis.hypothesis_id
    ]
    assert recorded and all(entry["verdict"] == "inconclusive" for entry in recorded)
    assert all(entry["admitted_to"] == "none" for entry in recorded)


def test_a_condition_that_changes_mid_trial_makes_it_inconclusive(tmp_path: Path) -> None:
    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    anomalous(harness)
    before = about_rain(harness)
    settle(harness, "contradicts", RAIN, after=CLEAR)
    assert about_rain(harness).cells == before.cells, "the weather changed while it ran"
    reasons = {entry["reason"] for entry in journal(harness, "hypothesis_evidence")}
    assert "condition_changed_during_trial" in reasons
    # And Person unsure where it is cannot say whether a place held.
    from person_cognition.hypotheses import vocabulary

    here = replace(context(), vocabulary=vocabulary(["place_1"]))
    about_here = admit(
        proposal(condition={"variable": "place", "value": "place_1"}),
        here,
        hypothesis_id="hyp_here",
        proposer="deterministic",
        now=0,
    )
    assert isinstance(about_here, CausalHypothesis)
    harness.loop._record(
        "hypothesis_proposed",
        1,
        {"hypothesis": about_here.to_json(), "question": "variation", "admitted_to": "active"},
    )
    settle(harness, "contradicts", Perceived("rain", "day", None))
    unsure = [
        entry
        for entry in journal(harness, "hypothesis_evidence")
        if entry["hypothesis_id"] == "hyp_here"
    ]
    assert [entry["reason"] for entry in unsure] == ["condition_not_known"]


def test_the_experiment_budget_terminates(tmp_path: Path) -> None:
    # A world where no trial can ever be evaluated: every one is refused.
    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    world = HiddenWorld(harness, barren={"rain"})
    hungry_start(world)

    def refused(weather: str) -> tuple[dict[str, Any], dict[str, Any]]:
        goal, _, invocation = world.harness.observe(world.observation(weather))
        world.tick += 50
        world.harness.loop.handle(
            {
                **envelope("SkillOutcome", world.tick),
                "decisionId": invocation["decisionId"],
                "goalId": invocation["goalId"],
                "routineId": invocation["routineId"],
                "contextId": "c",
                "requestedSkill": invocation["skillId"],
                "requestedParameters": invocation["parameters"],
                "requestedSkillStatus": "INVALIDATED",
                "executedSkill": invocation["skillId"],
                "executedParameters": invocation["parameters"],
                "status": "INVALIDATED",
                "emergency": False,
                "reasonCodes": ["protected_area"],
                "effects": [],
                "expectedEffects": list(BERRIES),
                "healthBefore": 20,
                "healthAfter": 20,
                "foodBefore": 20,
                "foodAfter": 20,
                "healthCost": 0,
                "resourceCost": [],
                "inventoryDelta": [],
                "elapsedTicks": 50,
                "interruptReason": None,
                "completionEvidence": {"kinds": ["elapsed_ticks"], "details": {}},
            }
        )
        world.tick += 10
        return goal, invocation

    kinds = [refused(weather_at(step))[0]["goal"]["goalType"] for step in range(60)]
    investigations = list(harness.loop.hypothesis_book.investigations.values())
    assert investigations and all(inv.status == "RETIRED" for inv in investigations)
    assert all(inv.attempts <= MAX_ATTEMPTS for inv in investigations)
    assert kinds.count("INVESTIGATE") <= MAX_ATTEMPTS * len(investigations)
    assert kinds[-10:].count("INVESTIGATE") == 0, "it stopped"


def test_the_daily_budget_limits_experimental_trials() -> None:
    from person_cognition.hypotheses import Investigation, InvestigationManager

    plan = design(admitted(), skill_registry())
    assert plan is not None
    busy = Investigation(
        investigation_id="investigation_1",
        design=plan,
        status="SUSPENDED",
        started_at=0,
        trial_times=tuple(range(100, 100 + DAILY_TRIALS)),
    )
    manager = InvestigationManager({"investigation_1": busy})
    assert manager.goal(RAIN, {"plant_food": 0}, 1000, 1) is None, "a day's trials are spent"
    assert manager.goal(RAIN, {"plant_food": 0}, 100 + 24_000, 1) is not None, "a day later"


def test_urgent_needs_interrupt_an_experiment_and_it_resumes(tmp_path: Path) -> None:
    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    world = HiddenWorld(harness, barren={"rain"})
    hungry_start(world)
    # The next trial begins, and something more urgent cuts it short before
    # the skill can act.
    world.preempt_next_trial = True
    for step in range(20):
        goal, _ = world.step(weather_at(step))
        if goal["goal"]["goalType"] == "INVESTIGATE":
            break
    else:
        pytest.fail("no experiment began")
    trial_goal = goal["goal"]["goalId"]

    world.hostile = True
    threatened, _ = world.step("rain")
    assert threatened["goal"]["goalType"] == "SURVIVE_IMMEDIATE"
    changes = [entry["change"] for entry in journal(harness, "investigation_changed")]
    assert "interrupted" in changes, changes
    assert "trial_inconclusive" in changes, "the cut-short trial taught nothing"

    # The threat passes; the same trial is taken up again, not a new one.
    world.hostile = False
    goal, invocation = world.step("rain")
    assert goal["goal"]["goalId"] == trial_goal
    assert invocation["skillId"] == "gather_plant_food"
    changes = [entry["change"] for entry in journal(harness, "investigation_changed")]
    assert "resumed" in changes
    before = about_rain(harness).cells["held:interventional"].trials
    world.step("rain")
    assert about_rain(harness).cells["held:interventional"].trials == before + 1


# ----------------------------------------------------- 21-23. learning modes


def test_off_learns_nothing_and_shadow_learns_only_into_its_own_table(tmp_path: Path) -> None:
    for mode, active, shadow in (
        ("off", False, False),
        ("shadow", False, True),
        ("supervised", True, False),
    ):
        harness = Harness(tmp_path / mode, learning_mode=mode)
        harness.hello()
        anomalous(harness)
        book = harness.loop.hypothesis_book
        assert bool(book.hypotheses["active"]) == active, mode
        assert bool(book.hypotheses["shadow"]) == shadow, mode
        if mode == "off":
            assert not journal(harness, "causal_trial")


def test_shadow_hypotheses_change_no_decision(tmp_path: Path) -> None:
    runs = {}
    for mode in ("off", "shadow"):
        harness = Harness(tmp_path / mode, learning_mode=mode)
        harness.hello()
        world = HiddenWorld(harness, barren={"rain"})
        hungry_start(world)
        seen = investigate(world, 16)
        runs[mode] = seen
        assert not harness.loop.hypothesis_book.investigations
        for entry in journal(harness, "routine_selected"):
            assert all(c["hypothesis_effect"] == 0 for c in entry["candidates"])
        if mode == "shadow":
            assert harness.loop.hypothesis_book.hypotheses["shadow"], "it did learn, in shadow"
    assert runs["off"] == runs["shadow"]
    assert all(kind != "INVESTIGATE" for _, kind, _ in runs["shadow"])


def supported_book(direction: str = "less_likely") -> dict[str, CausalHypothesis]:
    hypothesis = with_trials(
        replace(admitted(), outcome=replace(admitted().outcome, direction=direction)),
        *(
            rain_breaks_it()
            if direction == "less_likely"
            else [
                *repeated("held", "interventional", "supports", 4),
                *repeated("absent", "interventional", "contradicts", 4),
            ]
        ),
    )
    assert hypothesis.standing == "supported"
    return {hypothesis.hypothesis_id: hypothesis}


def option(
    name: str, steps: tuple[str, ...], applicable: bool = True, risk: float = 0.2
) -> RoutineCandidate:
    return RoutineCandidate(
        routine_id=f"r_{name}",
        name=name,
        steps=steps,
        step_labels=steps,
        risk=risk,
        cost=3.0,
        ticks=2400,
        applicable=applicable,
    )


def provider() -> EvidencePolicyProvider:
    statistics = RoutineStatistics()
    for routine in ("r_plants", "r_hunt"):
        for _ in range(6):
            statistics.apply(
                new_event(
                    person_id="ada",
                    world_id="w",
                    session_id="00000000-0000-4000-8000-000000000001",
                    episode_id="ep",
                    decision_id=None,
                    tick=1,
                    policy_revision=0,
                    training_context="fixture",
                    event_type="routine_outcome",
                    payload={"routine_id": routine, "context_id": "c", "status": "SUCCESS"},
                    previous_event_id=None,
                )
            )
    return EvidencePolicyProvider(
        statistics, training_context="fixture", learning_mode="supervised", minimum_support=3
    )


def test_a_supported_hypothesis_can_change_a_close_choice_when_its_condition_holds() -> None:
    policy = provider()
    view = calm_view()
    # A close choice: berries ahead by a hair.
    plants = option("plants", ("gather_plant_food",), risk=0.19)
    hunt = option("hunt", ("hunt_safe_passive_animals",))
    book = supported_book()
    neutral = policy.propose(view, None, [plants, hunt], "c")
    assert neutral.routine_id == "r_plants", "without the belief, berries win the tie"
    raining = policy.propose(
        view, None, [plants, hunt], "c", hypotheses=hypothesis_term(book, RAIN)
    )
    clear = policy.propose(view, None, [plants, hunt], "c", hypotheses=hypothesis_term(book, CLEAR))
    effects = {c.candidate.routine_id: c.hypothesis_effect for c in raining.candidates}
    assert effects["r_plants"] < 0 and effects["r_hunt"] == 0
    assert all(abs(value) <= HYPOTHESIS_LIMIT for value in effects.values())
    assert raining.routine_id == "r_hunt"
    assert all(c.hypothesis_effect == 0 for c in clear.candidates)
    assert clear.routine_id == neutral.routine_id
    # It cannot make a refused option win, nor create one.
    refused = option("hunt", ("hunt_safe_passive_animals",), applicable=False)
    chosen = policy.propose(
        view, None, [plants, refused], "c", hypotheses=hypothesis_term(book, RAIN)
    )
    assert chosen.routine_id == "r_plants"
    assert len(chosen.candidates) == 2


# ------------------------------------------- 24-27. memory, knowledge, C4


def test_episodic_memory_and_causal_belief_are_different_objects(tmp_path: Path) -> None:
    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    stored = len(harness.loop.memory_store)
    anomalous(harness)
    assert len(harness.loop.memory_store) == stored, "no hypothesis became an episode"
    names = {field.name for field in fields(Episode)}
    assert not {"hypothesis_id", "cells", "standing"} & names
    reducers = harness.loop.reducers.to_json()
    assert "hypotheses" in reducers and "memory" in reducers
    assert "hyp_" not in json.dumps(reducers["memory"])


def test_nothing_becomes_knowledge_however_well_supported() -> None:
    supported = next(iter(supported_book().values()))
    assert supported.standing == "supported"
    assert set(STANDINGS) == {"unresolved", "supported", "weakened", "contradicted"}
    for word in ("true", "proven", "fact", "known", "knowledge"):
        assert word not in STANDINGS and supported.status != word
    assert not hasattr(supported, "knowledge")


def test_initial_knowledge_and_learned_belief_are_told_apart_by_provenance() -> None:
    # The skill contract is initial knowledge: Person was built with it.
    contract = skill_registry().get("gather_plant_food").expected_effects
    assert contract, "the contract says berries follow"
    hypothesis = admitted()
    assert hypothesis.provenance.source == INFERENCE != INITIAL
    assert INITIAL not in EVIDENCE_SOURCE.values()
    # A proposal cannot claim to be initial, or anything else, for itself.
    refused = admit(
        proposal(provenance={"source": "INITIAL"}),
        context(),
        hypothesis_id="h",
        proposer="language_model",
        now=0,
    )
    assert isinstance(refused, Rejection)
    assert "claims_authority:provenance" in refused.reasons


def test_no_hypothesis_is_about_one_particular_thing() -> None:
    names = {field.name for field in fields(CausalHypothesis)}
    assert not {"target", "entity", "block", "object", "instance"} & names
    refused = admit(
        proposal(condition={"variable": "tree", "value": "that one"}),
        context(),
        hypothesis_id="h",
        proposer="deterministic",
        now=0,
    )
    assert isinstance(refused, Rejection)


def test_the_contrast_proposer_suggests_what_differed() -> None:
    proposals = ContrastProposer().propose(context())
    assert proposals[0]["condition"] == {"variable": "weather", "value": "rain"}
    # Nothing that did not differ is suggested.
    assert all(p["condition"]["variable"] != "day_phase" for p in proposals)
    assert len(proposals) <= 3


def test_the_book_is_rebuilt_from_its_events_alone(tmp_path: Path) -> None:
    harness = Harness(tmp_path, learning_mode="supervised")
    harness.hello()
    anomalous(harness)
    settle(harness, "contradicts", RAIN)
    rebuilt = HypothesisBook()
    for event in EvidenceJournal(tmp_path / "journal").read():
        rebuilt.apply(event)
    assert rebuilt.to_json() == harness.loop.hypothesis_book.to_json()
    assert deepcopy(rebuilt.to_json()) == rebuilt.to_json()
