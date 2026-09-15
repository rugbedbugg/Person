"""The cognition loop: protocol handling, routine progress, and restart reuse."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_cognition import CognitionLoop
from person_persistence import EvidenceJournal
from person_protocol import PROTOCOL_VERSION, decode_frame, protocol_validator

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


class Harness:
    """Drives a CognitionLoop in-process and captures what it says."""

    def __init__(self, evidence: Path, learning_mode: str = "off") -> None:
        self.sent: list[dict[str, Any]] = []
        self.logs: list[str] = []
        self.loop = CognitionLoop(
            evidence_directory=evidence,
            write=lambda line: self.sent.append(decode_frame(line.rstrip("\n"))),
            log=self.logs.append,
        )
        self.learning_mode = learning_mode
        self.evidence = evidence

    def hello(self) -> dict[str, Any]:
        from person_skills import skill_registry

        self.loop.handle(
            {
                **envelope("SessionHello", 0),
                "learningMode": self.learning_mode,
                "trainingContext": "fixture",
                "policyRevision": 0,
                "skillLibraryRevision": skill_registry().revision,
                "rngSeed": 7,
                "evidenceDirectory": str(self.evidence),
                "skillIds": skill_registry().ids,
            }
        )
        return self.of_type("CognitionReady")[-1]

    def of_type(self, message_type: str) -> list[dict[str, Any]]:
        return [message for message in self.sent if message["type"] == message_type]

    def observe(
        self, observation: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        before = len(self.sent)
        self.loop.handle(observation)
        produced = self.sent[before:]
        kinds = {message["type"]: message for message in produced}
        assert set(kinds) == {"GoalDecision", "PolicyDecision", "SkillInvocation"}, kinds
        return kinds["GoalDecision"], kinds["PolicyDecision"], kinds["SkillInvocation"]

    def complete(
        self, invocation: dict[str, Any], policy: dict[str, Any], status: str = "SUCCESS"
    ) -> None:
        self.loop.handle(
            {
                **envelope("SkillOutcome", invocation["tick"] + 10),
                "decisionId": invocation["decisionId"],
                "goalId": invocation["goalId"],
                "routineId": invocation["routineId"],
                "contextId": policy["contextId"],
                "requestedSkill": invocation["skillId"],
                "requestedParameters": invocation["parameters"],
                "requestedSkillStatus": status,
                "executedSkill": invocation["skillId"],
                "executedParameters": invocation["parameters"],
                "status": status,
                "emergency": False,
                "reasonCodes": [],
                "effects": ["done"],
                "expectedEffects": [],
                "healthBefore": 20,
                "healthAfter": 20,
                "foodBefore": 10,
                "foodAfter": 10,
                "healthCost": 0,
                "resourceCost": [],
                "inventoryDelta": [],
                "elapsedTicks": 10,
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
            "position": {"x": 14, "y": 64, "z": 2},
            "distance": 4.0,
            "harvestPermitted": True,
        }
    )
    return document


def test_the_loop_reports_readiness_and_then_decides(
    tmp_path: Path, observation: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    ready = harness.hello()
    assert ready["cognitionVersion"]
    assert ready["restoredEvents"] == 0

    goal, policy, invocation = harness.observe(observation)
    assert goal["goal"]["status"] == "ACTIVE"
    assert policy["learnedOrFallback"] == "fallback"
    assert invocation["skillId"] in {step for step in policy["steps"]}
    validator = protocol_validator()
    for message in (goal, policy, invocation):
        valid, diagnostics = validator.validate(message)
        assert valid, diagnostics


def test_the_loop_walks_a_routine_step_by_step(tmp_path: Path, observation: dict[str, Any]) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    _, policy, first = harness.observe(observation)
    assert first["routineStepIndex"] == 0
    assert first["skillId"] == "gather_plant_food"
    harness.complete(first, policy)

    # The world moved on the way the skill said it would, so the next step of
    # the same routine becomes applicable.
    after = deepcopy(observation)
    after["inventory"]["items"].append({"name": "sweet_berries", "count": 6})
    after["inventory"]["categories"]["food"] = 6
    _, _, second = harness.observe(after)
    assert second["routineId"] == first["routineId"]
    assert second["routineStepIndex"] == 1
    assert second["skillId"] == "eat_to_target"


def test_a_completed_routine_is_recorded_as_evidence(
    tmp_path: Path, observation: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    document = deepcopy(observation)
    for _ in range(4):
        _, policy, invocation = harness.observe(document)
        harness.complete(invocation, policy)
        if invocation["skillId"] == "gather_plant_food":
            document["inventory"]["items"].append({"name": "sweet_berries", "count": 6})
            document["inventory"]["categories"]["food"] = 6
        if invocation["skillId"] == "eat_to_target":
            document["vitals"]["food"] = 20
    events = [event.type for event in EvidenceJournal(tmp_path / "journal").read()]
    assert "routine_selected" in events
    assert "skill_completed" in events
    assert "routine_outcome" in events


def test_an_emergency_override_is_recorded_and_interrupts_the_routine(
    tmp_path: Path, observation: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    _, policy, invocation = harness.observe(observation)
    harness.loop.handle(
        {
            **envelope("EmergencyEvent", invocation["tick"] + 1),
            "decisionId": invocation["decisionId"],
            "level": "L1",
            "trigger": "immediate_threat",
            "reasonCodes": ["hostile_zombie"],
            "action": "flee",
            "preemptedSkill": invocation["skillId"],
        }
    )
    harness.loop.handle(
        {
            **envelope("SkillOutcome", invocation["tick"] + 20),
            "decisionId": invocation["decisionId"],
            "goalId": invocation["goalId"],
            "routineId": invocation["routineId"],
            "contextId": policy["contextId"],
            "requestedSkill": invocation["skillId"],
            "requestedParameters": invocation["parameters"],
            "requestedSkillStatus": "PREEMPTED",
            "executedSkill": "flee",
            "executedParameters": {"min_clearance": 16},
            "status": "SUCCESS",
            "emergency": True,
            "reasonCodes": ["immediate_threat"],
            "effects": ["threat_cleared"],
            "expectedEffects": [{"fact": "safe", "op": "=", "value": 1}],
            "healthBefore": 20,
            "healthAfter": 18,
            "foodBefore": 10,
            "foodAfter": 10,
            "healthCost": 2,
            "resourceCost": [],
            "inventoryDelta": [],
            "elapsedTicks": 40,
            "interruptReason": "immediate_threat",
            "completionEvidence": {"kinds": ["threat_clearance"], "details": {}},
        }
    )
    events = list(EvidenceJournal(tmp_path / "journal").read())
    kinds = [event.type for event in events]
    assert "emergency_override" in kinds
    interrupted = next(event for event in events if event.type == "skill_interrupted")
    assert interrupted.payload["executed_skill"] == "flee"
    assert interrupted.payload["requested_skill"] == invocation["skillId"]
    outcome = next(event for event in events if event.type == "routine_outcome")
    assert outcome.payload["status"] == "INTERRUPTED"
    assert outcome.payload["recovered"] is True

    statistics = harness.loop.statistics
    assert statistics.skill("fixture", policy["contextId"], "flee").successes == 1
    assert statistics.skill("fixture", policy["contextId"], invocation["skillId"]).attempts == 0
    assert statistics.skill("fixture", policy["contextId"], invocation["skillId"]).preemptions == 1


def test_learning_survives_a_restart_of_the_process(
    tmp_path: Path, observation: dict[str, Any]
) -> None:
    first = Harness(tmp_path, learning_mode="supervised")
    first.hello()
    document = deepcopy(observation)
    for _ in range(12):
        _, policy, invocation = first.observe(document)
        first.complete(invocation, policy)
    routines_before = len(first.loop.statistics.routines)
    assert routines_before > 0
    first.loop.handle(
        {
            **envelope("EpisodeEvent", 500),
            "episodeId": "ep_1",
            "phase": "ended",
            "trainingContext": "fixture",
            "rngSeed": 7,
            "reasonCodes": ["done"],
        }
    )
    known = {key: counts.successes for key, counts in first.loop.statistics.routines.items()}

    # A completely new process object, same evidence directory.
    second = Harness(tmp_path, learning_mode="supervised")
    ready = second.hello()
    assert ready["restoredRoutines"] == routines_before
    assert ready["snapshotTick"] is not None
    restored = {key: counts.successes for key, counts in second.loop.statistics.routines.items()}
    assert restored == known

    _, policy, _ = second.observe(document)
    assert policy["candidates"], "restored evidence must reach the policy"
    assert any(candidate["attempts"] > 0 for candidate in policy["candidates"])


def test_malformed_input_is_dropped_without_stopping_the_loop(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    harness.loop.run(iter(["{not json}\n", '{"type":"Nope"}\n', "[]\n"]))
    assert harness.sent == []
    assert len(harness.logs) >= 2
