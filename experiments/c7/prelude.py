"""Synthetic prior experience for C7 scenarios (ADR 0024, synthetic-history validity).

A scenario may begin from fixture-authored memories, beliefs and place
knowledge, but only as history Person could have lived: this module drives a
real `CognitionLoop` with synthetic observations and skill outcomes, so every
journal record is written by Person's own handlers, through the same schemas,
reducers and firewalls as ordinary cognition. Nothing is written into a store
directly, and no evaluator-only fact is ever installed as knowledge.

    uv run python experiments/c7/prelude.py <root> <person-id> home-and-away <away> <seen>

The root it leaves is the scenario's frozen initial cognitive state.
"""

from __future__ import annotations

import json
import sys
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from person_cognition import CognitionLoop
from person_protocol import PROTOCOL_VERSION, decode_frame
from person_skills import skill_registry

REPOSITORY = Path(__file__).resolve().parents[2]
SESSION = "c7000000-0000-4000-8000-000000000001"
#: What Person can be shown seeing: (resource kind, block name).
RESOURCES: dict[str, tuple[str, str]] = {
    "wood": ("wood", "oak_log"),
    "plant_food": ("plant_food", "sweet_berry_bush"),
}
STILL: dict[str, Any] = {
    "continuity": "continuous",
    "translation": {"direction": "none", "band": "none", "distance": 0},
    "rotation": "none",
    "vertical": "level",
}


def _moved(direction: str, distance: float) -> dict[str, Any]:
    band = "tiny" if distance < 2 else "short" if distance < 8 else "moderate"
    return {
        "continuity": "continuous",
        "translation": {
            "direction": direction,
            "band": "far" if distance >= 24 else band,
            "distance": distance,
        },
        "rotation": "none",
        "vertical": "level",
    }


class Life:
    """One synthetic session of a Person, through its real cognition."""

    def __init__(self, root: Path, person_id: str) -> None:
        self.person_id = person_id
        self.sent: list[dict[str, Any]] = []
        self.loop = CognitionLoop(
            evidence_directory=root,
            write=lambda line: self.sent.append(decode_frame(line.rstrip("\n"))),
            log=lambda _: None,
        )
        self.root = root
        self.view: dict[str, Any] = json.loads(
            (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text("utf-8")
        )
        self.view["vitals"].update({"health": 20.0, "food": 20.0, "breath": 10})
        for key in ("resources", "passiveAnimals", "hostiles", "players", "containers", "hazards"):
            self.view["nearby"][key] = []
        self.tick = 0

    def envelope(self, kind: str) -> dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "messageId": str(uuid.uuid4()),
            "personId": self.person_id,
            "sessionId": SESSION,
            "worldId": "test-world",
            "tick": self.tick,
            "timestamp": "2026-10-01T08:00:00.000Z",
            "type": kind,
        }

    def hello(self) -> None:
        self.loop.handle(
            {
                **self.envelope("SessionHello"),
                "learningMode": "off",
                "trainingContext": "fixture",
                "policyRevision": 0,
                "skillLibraryRevision": skill_registry().revision,
                "rngSeed": 7,
                "evidenceDirectory": str(self.root),
                "skillIds": skill_registry().ids,
            }
        )

    def observe(
        self, *, motion: dict[str, Any] | None = None, seen: str | None = None
    ) -> dict[str, Any] | None:
        """One observation; returns the skill Person asked for, if any."""
        self.tick += 20
        view = deepcopy(self.view)
        view.update(self.envelope("Observation"))
        view["selfMotion"] = motion or dict(STILL)
        if seen is not None:
            kind, name = RESOURCES[seen]
            view["nearby"]["resources"] = [
                {
                    "kind": kind,
                    "name": name,
                    "distance": 4.0,
                    "harvestPermitted": True,
                    "bearing": "ahead",
                    "elevation": "level",
                    "rangeBand": "near",
                    "detail": "central",
                }
            ]
        before = len(self.sent)
        self.loop.handle(view)
        asked = [m for m in self.sent[before:] if m["type"] == "SkillInvocation"]
        return asked[-1] if asked else None

    def outcome(self, invocation: dict[str, Any], executed: str) -> None:
        """The runtime reports a skill's outcome; `executed` may differ from
        what was asked, as when the kernel replaces it."""
        self.tick += 10
        self.loop.handle(
            {
                **self.envelope("SkillOutcome"),
                "decisionId": invocation["decisionId"],
                "goalId": invocation["goalId"],
                "routineId": invocation["routineId"],
                "contextId": "c7-prelude",
                "requestedSkill": invocation["skillId"],
                "requestedParameters": invocation["parameters"],
                "requestedSkillStatus": "SUCCESS",
                "executedSkill": executed,
                "executedParameters": {},
                "status": "SUCCESS",
                "emergency": False,
                "reasonCodes": [],
                "effects": [],
                "expectedEffects": [],
                "healthBefore": 20,
                "healthAfter": 20,
                "foodBefore": 20,
                "foodAfter": 20,
                "healthCost": 0,
                "resourceCost": [],
                "inventoryDelta": [],
                "elapsedTicks": 10,
                "interruptReason": None,
                "completionEvidence": {"kinds": ["elapsed_ticks"], "details": {}},
            }
        )

    def end(self) -> None:
        self.loop.handle(
            {
                **self.envelope("EpisodeEvent"),
                "episodeId": "ep_c7_prelude",
                "phase": "ended",
                "reasonCodes": ["prelude_complete"],
                "rngSeed": 7,
                "trainingContext": "fixture",
            }
        )


def home_and_away(root: Path, person_id: str, away: float = 72.0, seen: str = "wood") -> None:
    """Person was home, saw `seen` there, and walked `away` blocks ahead.

    It learns home from its own successful return home (C8), perceives wood
    while there, then walks ahead and settles at a new place.
    """
    life = Life(root, person_id)
    life.hello()
    asked = life.observe()
    assert asked is not None, "Person acts at home"
    life.outcome(asked, "return_home")
    life.observe()
    life.observe(seen=seen)
    life.observe(seen=seen)
    walked = 0.0
    while walked < away:
        step = min(8.0, away - walked)
        life.observe(motion=_moved("ahead", step))
        walked += step
    # Person acts where it now is, so its outcome settles that place.
    for _ in range(12):
        asked = life.observe()
        if asked is not None:
            life.outcome(asked, "eat_to_target")
            break
    else:
        raise RuntimeError("Person never acted at the far place")
    life.end()


PRELUDES = {"home-and-away": home_and_away}

if __name__ == "__main__":
    root, person, name, *rest = sys.argv[1:]
    PRELUDES[name](Path(root), person, float(rest[0]), *rest[1:])
