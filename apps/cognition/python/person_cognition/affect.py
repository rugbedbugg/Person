"""Affect: a small continuous internal state that biases cognition (ADR 0010).

The causal direction is fixed:

    experienced event -> deterministic appraisal -> continuous affect state
        -> bounded bias -> the ordinary goal, project and policy machinery

Affect never chooses a goal, never runs a skill, and never touches what the
runtime permits. It reads only what cognition legitimately has: percepts, the
body's felt state, outcomes the runtime reported, Person's own goal, project
and search outcomes. It is not belief: feeling uneasy is not knowing there is
danger, and feeling calm proves nothing is safe.

The state has three dimensions, each with a plain meaning:

    valence   [-1, 1]  how things are going: goals met or thwarted
    unease    [ 0, 1]  threat and harm activation
    control   [-1, 1]  whether Person's own actions seem to work

Every appraisal records what triggered it, its components, and the change it
made, so an observer can always answer "why did this change?". Activation
decays toward a baseline as Person's experienced time passes. A temperament
supplies the baseline, how strongly Person reacts and how fast it recovers;
the default is neutral, and nothing here depends on its values.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from person_persistence import EvidenceEvent

DIMENSIONS: tuple[str, ...] = ("valence", "unease", "control")
RANGES: Mapping[str, tuple[float, float]] = {
    "valence": (-1.0, 1.0),
    "unease": (0.0, 1.0),
    "control": (-1.0, 1.0),
}

#: Experienced ticks for activation to halve toward baseline. Unease settles
#: in about a minute of game time; mood and a sense of control take longer.
#: Implementation parameters.
HALF_LIVES: Mapping[str, float] = {"valence": 6_000.0, "unease": 1_200.0, "control": 12_000.0}

#: The most affect may add to or take from a goal's priority. Well inside the
#: gaps between the tiers of need (danger 900+, hunger 400+, projects 300), so
#: it can reorder near neighbours and never replace the drive system.
BIAS_LIMIT = 25.0

#: How much exploration Person will tolerate, as a factor on the policy's
#: exploration bonus: never below half, never above a quarter more.
TOLERANCE_RANGE = (0.5, 1.25)

#: Facts whose pursuit keeps Person close and protected, as opposed to going
#: out and getting things. A goal's character is read from its completion
#: condition, so the bias is generic, never "state X means project Y".
PROTECTIVE_FACTS: frozenset[str] = frozenset(
    {
        "shelter_complete",
        "sheltered",
        "at_home",
        "owned_storage_available",
        "stored_surplus",
        "safe",
    }
)

#: How each dimension pulls on each character of goal.
SENSITIVITY: Mapping[str, Mapping[str, float]] = {
    "protective": {"unease": 1.0, "valence": 0.0, "control": -0.5},
    "outgoing": {"unease": -1.0, "valence": 0.5, "control": 0.5},
}


def _clamp(dimension: str, value: float) -> float:
    low, high = RANGES[dimension]
    return round(max(low, min(high, value)), 4)


@dataclass(frozen=True, slots=True)
class AffectState:
    valence: float = 0.0
    unease: float = 0.0
    control: float = 0.0

    def get(self, dimension: str) -> float:
        return float(getattr(self, dimension))

    def moved(self, deltas: Mapping[str, float]) -> AffectState:
        return AffectState(
            **{
                dimension: _clamp(dimension, self.get(dimension) + deltas.get(dimension, 0.0))
                for dimension in DIMENSIONS
            }
        )

    def to_json(self) -> dict[str, float]:
        return {dimension: self.get(dimension) for dimension in DIMENSIONS}

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> AffectState:
        return cls(**{dimension: float(body[dimension]) for dimension in DIMENSIONS})


@dataclass(frozen=True, slots=True)
class Temperament:
    """Where Person settles, how strongly it reacts, how fast it recovers."""

    baseline: AffectState = field(default_factory=AffectState)
    reactivity: float = 1.0
    recovery: float = 1.0


@dataclass(frozen=True, slots=True)
class Appraisal:
    """One experienced event, judged: what it was, and what it means."""

    trigger: str
    #: Named appraisal components, each in its own plain units.
    components: Mapping[str, float]
    #: The change to each dimension these components imply.
    deltas: Mapping[str, float]


# ---------------------------------------------------------------- appraisal


def appraise_threat(observation: Mapping[str, Any]) -> Appraisal | None:
    """A threat Person perceives: a hostile or a hazard in the observation."""
    nearby = observation["nearby"]
    threat = 0.0
    for hostile in nearby["hostiles"]:
        threat = max(threat, 1.0 - float(hostile["distance"]) / 16.0)
    for hazard in nearby["hazards"]:
        threat = max(threat, 1.0 - float(hazard["distance"]) / 4.0)
    if threat <= 0.0:
        return None
    threat = round(threat, 4)
    return Appraisal("perceived_threat", {"threat": threat}, {"unease": 0.3 * threat})


def appraise_harm(health_lost: float) -> Appraisal | None:
    """Harm felt through the body: health lost between two observations."""
    if health_lost < 1.0:
        return None
    lost = round(health_lost, 2)
    return Appraisal(
        "harm",
        {"health_lost": lost},
        {"unease": 0.08 * lost, "valence": -0.05 * lost, "control": -0.03 * lost},
    )


def appraise_outcome(outcome: Mapping[str, Any]) -> Appraisal | None:
    """Whether Person's own action worked, as the runtime reported it."""
    executed = str(outcome["executedSkill"])
    status = str(outcome["status"])
    if outcome["emergency"]:
        # Something else took over. Person's own intentions did not steer.
        return Appraisal("overridden", {"controllability": -1.0}, {"control": -0.1, "unease": 0.05})
    if executed in {"look", "look_around", "wait_safely"}:
        return None
    if status == "SUCCESS":
        return Appraisal("action_succeeded", {"success": 1.0}, {"valence": 0.05, "control": 0.05})
    if status in {"INTERRUPTED", "PREEMPTED"}:
        return None
    return Appraisal("action_failed", {"success": -1.0}, {"valence": -0.08, "control": -0.08})


def appraise_goal(event: str, goal_type: str) -> Appraisal | None:
    """A goal reached, or found to be out of reach."""
    if event == "complete":
        return Appraisal(
            f"goal_complete_{goal_type.lower()}",
            {"goal_congruence": 1.0},
            {"valence": 0.1, "control": 0.05},
        )
    if event == "blocked":
        return Appraisal(
            f"goal_blocked_{goal_type.lower()}",
            {"goal_congruence": -1.0},
            {"valence": -0.1, "control": -0.05},
        )
    return None


def appraise_project(change: str, kind: str) -> Appraisal | None:
    """A commitment advancing, finished, or given up."""
    table = {
        "progressed": ({"goal_congruence": 0.5}, {"valence": 0.05, "control": 0.03}),
        "completed": ({"goal_congruence": 1.0}, {"valence": 0.15, "control": 0.05}),
        "abandoned": ({"goal_congruence": -1.0}, {"valence": -0.12, "control": -0.08}),
    }
    if change not in table:
        return None
    components, deltas = table[change]
    return Appraisal(f"project_{change}_{kind}", components, deltas)


def appraise_search(conclusion: str) -> Appraisal:
    """Finding what was looked for, or not."""
    if conclusion == "found":
        return Appraisal("search_found", {"goal_congruence": 0.5}, {"valence": 0.03})
    return Appraisal("search_unfound", {"goal_congruence": -0.5}, {"valence": -0.05})


# ------------------------------------------------------------------ state


def decay(state: AffectState, temperament: Temperament, elapsed: float) -> AffectState:
    """The state after `elapsed` experienced ticks with nothing happening."""
    if elapsed <= 0:
        return state
    settled: dict[str, float] = {}
    for dimension in DIMENSIONS:
        base = temperament.baseline.get(dimension)
        half_life = HALF_LIVES[dimension] / max(temperament.recovery, 1e-6)
        settled[dimension] = _clamp(
            dimension, base + (state.get(dimension) - base) * 0.5 ** (elapsed / half_life)
        )
    return AffectState(**settled)


class AffectRecord:
    """The last affect state Person recorded, rebuilt from its own appraisals."""

    def __init__(self) -> None:
        self.state = AffectState()
        self.at = 0

    def reset(self) -> None:
        self.state = AffectState()
        self.at = 0

    def apply(self, event: EvidenceEvent) -> None:
        if event.type == "affect_appraised":
            self.state = AffectState.from_json(event.payload["after"])
            self.at = int(event.payload["experienced_tick"])

    def to_json(self) -> dict[str, Any]:
        return {"state": self.state.to_json(), "at": self.at}

    def load_json(self, body: Mapping[str, Any]) -> None:
        self.state = AffectState.from_json(body["state"])
        self.at = int(body["at"])


class Affect:
    """Person's affect, for the cognition loop: appraise, decay, bias."""

    def __init__(self, record: AffectRecord, temperament: Temperament | None = None) -> None:
        self.temperament = temperament or Temperament()
        # A restart resumes the recorded state: affect is part of continuity.
        # It decays from when it was recorded, in experienced time only.
        self.state = record.state
        self._at = record.at

    def advance(self, now: int) -> None:
        """Let experienced time pass: activation settles toward baseline."""
        self.state = decay(self.state, self.temperament, now - self._at)
        self._at = max(self._at, now)

    def feel(self, appraisal: Appraisal, now: int) -> dict[str, Any]:
        """Apply one appraisal. Returns the engineering record of the change."""
        self.advance(now)
        scaled = {
            dimension: round(delta * self.temperament.reactivity, 4)
            for dimension, delta in appraisal.deltas.items()
        }
        before = self.state
        self.state = before.moved(scaled)
        return {
            "trigger": appraisal.trigger,
            "components": dict(appraisal.components),
            "before": before.to_json(),
            "delta": {
                dimension: round(self.state.get(dimension) - before.get(dimension), 4)
                for dimension in DIMENSIONS
            },
            "after": self.state.to_json(),
            "experienced_tick": now,
        }

    # ----------------------------------------------------------------- bias

    @staticmethod
    def character(completion_facts: frozenset[str]) -> str:
        return "protective" if completion_facts & PROTECTIVE_FACTS else "outgoing"

    def bias(self, completion_facts: frozenset[str], source: str) -> float:
        """The affective adjustment to a goal's priority, within ±BIAS_LIMIT.

        Urgent survival goals are never adjusted: affect reorders near
        neighbours among the legitimate, non-urgent candidates, and nothing
        more.
        """
        if source == "emergency":
            return 0.0
        pull = SENSITIVITY[self.character(completion_facts)]
        raw = sum(weight * self.state.get(dimension) for dimension, weight in pull.items())
        return round(max(-BIAS_LIMIT, min(BIAS_LIMIT, BIAS_LIMIT * raw)), 3)

    def tolerance(self) -> float:
        """Willingness to explore the untried, as a factor on the exploration bonus.

        Unease and a sense of not being in control make Person prefer what it
        knows; a sense of control lets it tolerate a little more. This is a
        preference inside what the runtime already permits, never a change to
        what it permits.
        """
        low, high = TOLERANCE_RANGE
        raw = 1.0 - 0.5 * self.state.unease + 0.25 * self.state.control
        return round(max(low, min(high, raw)), 4)


def adjusted(state: AffectState) -> Affect:
    """An Affect holding `state`, for probes and tests."""
    affect = Affect(AffectRecord())
    affect.state = replace(state)
    return affect
