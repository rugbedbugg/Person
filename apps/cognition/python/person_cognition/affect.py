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
made, so an observer can always answer "why did this change?".

An affect mode (ADR 0013) switches affect for experiments. `active` is the
behaviour above. `record_only` appraises and records exactly as `active` does,
and lets nothing reach a decision. `off` lets nothing evolve at all. The mode
is consulted in two places only: where the state evolves, and where it is
consumed. Activation
decays toward a baseline as Person's experienced time passes. A temperament
supplies the baseline, how strongly Person reacts and how fast it recovers;
the default is neutral, and nothing here depends on its values.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from person_persistence import CanonicalEvent
from person_skills import skill_registry

DIMENSIONS: tuple[str, ...] = ("valence", "unease", "control")

#: How far affect is switched on (ADR 0013). Unset means `active`.
AFFECT_MODES: tuple[str, ...] = ("off", "record_only", "active")
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

#: What a goal is like, for affect: `protective` goals keep Person close and
#: protected, `outgoing` goals go out and get things. Which goals are which is
#: the environment's to say, from the goal's completion condition
#: (`CognitiveEnvironment.goal_character`; Minecraft's is
#: `person_minecraft.goals.goal_character`, ADR 0025). Affect never reads a
#: fact name, so the bias is generic, never "state X means project Y".
type GoalCharacter = Literal["protective", "outgoing"]

#: How each dimension pulls on each character of goal.
SENSITIVITY: Mapping[str, Mapping[str, float]] = {
    "protective": {"unease": 1.0, "valence": 0.0, "control": -0.5},
    "outgoing": {"unease": -1.0, "valence": 0.5, "control": 0.5},
}


def _clamp(dimension: str, value: float, digits: int | None = 4) -> float:
    low, high = RANGES[dimension]
    bounded = max(low, min(high, value))
    return bounded if digits is None else round(bounded, digits)


@dataclass(frozen=True, slots=True)
class AffectState:
    valence: float = 0.0
    unease: float = 0.0
    control: float = 0.0

    def get(self, dimension: str) -> float:
        return float(getattr(self, dimension))

    def moved(self, deltas: Mapping[str, float], digits: int | None = 4) -> AffectState:
        return AffectState(
            **{
                dimension: _clamp(
                    dimension, self.get(dimension) + deltas.get(dimension, 0.0), digits
                )
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


def appraise_threat(threat: float) -> Appraisal | None:
    """A threat Person perceives, as one intensity from 0 to 1.

    The environment says how its percepts add up to that intensity (for
    Minecraft, `person_minecraft.body.threat_intensity`); affect never reads a
    percept itself.
    """
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


def appraise_outcome(
    outcome: Mapping[str, Any], unremarkable: frozenset[str] | None = None
) -> Appraisal | None:
    """Whether Person's own action worked, as the runtime reported it.

    `unremarkable` is the environment's skills whose plain success is no
    achievement (its skill vocabulary's `unremarkable`); the installed
    environment's by default.
    """
    routine = (
        skill_registry().vocabulary.unremarkable_skills if unremarkable is None else unremarkable
    )
    executed = str(outcome["executedSkill"])
    status = str(outcome["status"])
    if outcome["emergency"]:
        # Something else took over. Person's own intentions did not steer.
        return Appraisal("overridden", {"controllability": -1.0}, {"control": -0.1, "unease": 0.05})
    if executed in routine:
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


# ------------------------------------------------------------------ tonic
#
# ADR 0014. An ongoing condition shifts the level a dimension settles toward;
# it never touches control, which is about whether Person's own actions work.
# Coefficients and caps are implementation parameters.

#: How far each fully present condition shifts valence and unease.
TONIC_WEIGHTS: Mapping[str, Mapping[str, float]] = {
    "hunger": {"valence": -0.35, "unease": 0.15},
    "vulnerability": {"valence": -0.35, "unease": 0.35},
    "breathlessness": {"valence": -0.3, "unease": 0.5},
    "threat": {"valence": -0.1, "unease": 0.4},
}
#: The most all conditions together may shift each dimension.
TONIC_CAPS: Mapping[str, tuple[float, float]] = {
    "valence": (-0.6, 0.0),
    "unease": (0.0, 0.7),
}


def tonic_offset(pressures: Mapping[str, float]) -> dict[str, float]:
    """The shift of each dimension's settling level that `pressures` imply."""
    offset: dict[str, float] = {}
    for dimension, (low, high) in TONIC_CAPS.items():
        total = sum(
            TONIC_WEIGHTS[condition].get(dimension, 0.0) * max(0.0, min(1.0, level))
            for condition, level in pressures.items()
            if condition in TONIC_WEIGHTS
        )
        total = round(max(low, min(high, total)), 4)
        if total:
            offset[dimension] = total
    return offset


# ------------------------------------------------------------------ state


def decay(state: AffectState, temperament: Temperament, elapsed: float) -> AffectState:
    """The state after `elapsed` experienced ticks with nothing happening."""
    return settle(state, temperament, elapsed, {})


def settle(
    state: AffectState,
    temperament: Temperament,
    elapsed: float,
    offset: Mapping[str, float],
    digits: int | None = 4,
) -> AffectState:
    """The state after `elapsed` experienced ticks under a held tonic offset.

    Each dimension relaxes toward its baseline shifted by the offset, with its
    own half-life (ADR 0014). With no offset this is plain decay. Because the
    relaxation is solved exactly over the whole interval, the result depends on
    experienced time alone: splitting an interval into more observations under
    the same offset gives the same state, provided the state is not rounded
    between steps (`digits=None`), since rounding once per observation would
    itself depend on how many observations there were.
    """
    if elapsed <= 0:
        return state
    settled: dict[str, float] = {}
    for dimension in DIMENSIONS:
        target = temperament.baseline.get(dimension)
        if dimension in offset:
            target = _clamp(dimension, target + offset[dimension])
        half_life = HALF_LIVES[dimension] / max(temperament.recovery, 1e-6)
        settled[dimension] = _clamp(
            dimension,
            target + (state.get(dimension) - target) * 0.5 ** (elapsed / half_life),
            digits,
        )
    return AffectState(**settled)


class AffectRecord:
    """The last affect state Person recorded, rebuilt from its own records.

    Phasic appraisals set the state; tonic updates set the state and the
    offset held from then on (ADR 0014).
    """

    def __init__(self) -> None:
        self.state = AffectState()
        self.at = 0
        self.offset: dict[str, float] = {}

    def reset(self) -> None:
        self.state = AffectState()
        self.at = 0
        self.offset = {}

    def apply(self, event: CanonicalEvent) -> None:
        if event.type in {"affect_appraised", "affect_tonic"}:
            self.state = AffectState.from_json(event.payload["after"])
            self.at = int(event.payload["experienced_tick"])
        if event.type == "affect_tonic":
            self.offset = {k: float(v) for k, v in event.payload["offset"].items()}

    def to_json(self) -> dict[str, Any]:
        return {"state": self.state.to_json(), "at": self.at, "offset": dict(self.offset)}

    def load_json(self, body: Mapping[str, Any]) -> None:
        self.state = AffectState.from_json(body["state"])
        self.at = int(body["at"])
        self.offset = {k: float(v) for k, v in body.get("offset", {}).items()}


class Affect:
    """Person's affect, for the cognition loop: appraise, decay, bias."""

    def __init__(
        self,
        record: AffectRecord,
        temperament: Temperament | None = None,
        mode: str = "active",
        precise: bool = False,
    ) -> None:
        if mode not in AFFECT_MODES:
            raise ValueError(f"unknown affect mode {mode!r}; expected one of {AFFECT_MODES}")
        self.mode = mode
        #: Keep the state unrounded between steps, so that it depends on
        #: experienced time and not on the number of observations (ADR 0014).
        #: Rounded, as before, when reproducing earlier appraisal exactly.
        self._digits: int | None = None if precise else 4
        self.temperament = temperament or Temperament()
        # A restart resumes the recorded state: affect is part of continuity.
        # It decays from when it was recorded, in experienced time only.
        self.state = record.state
        self._at = record.at
        #: The tonic offset in force until the next update (ADR 0014).
        self.offset: dict[str, float] = dict(record.offset)

    def advance(self, now: int) -> None:
        """Let experienced time pass: activation settles toward baseline."""
        if self.mode == "off":
            return
        self.state = settle(self.state, self.temperament, now - self._at, self.offset, self._digits)
        self._at = max(self._at, now)

    def apply_tonic(self, pressures: Mapping[str, float], now: int) -> dict[str, Any] | None:
        """Let the conditions held so far act up to `now`, then hold new ones.

        `pressures` are the ongoing conditions Person perceives now; the
        offset they imply is held until the next update. Returns the
        engineering record of the change, or None when nothing is pressing
        and nothing was.
        """
        if self.mode == "off":
            return None
        start = self._at
        before = self.state
        held = dict(self.offset)
        self.advance(now)
        self.offset = tonic_offset(pressures)
        if not held and not self.offset:
            return None
        return {
            "pressures": {name: round(value, 4) for name, value in sorted(pressures.items())},
            "offset": dict(self.offset),
            "held": held,
            "elapsed": max(0, now - start),
            "before": before.to_json(),
            "after": self.state.to_json(),
            "experienced_tick": now,
        }

    def feel(
        self, appraisal: Appraisal, now: int, extra: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Apply one appraisal. Returns the engineering record of the change.

        `extra` adds to the record, never to the change: the causal event an
        appraisal answers and its consequences (ADR 0014). With affect off
        nothing is applied and there is nothing to record.
        """
        if self.mode == "off":
            return None
        self.advance(now)
        scaled = {
            dimension: round(delta * self.temperament.reactivity, 4)
            for dimension, delta in appraisal.deltas.items()
        }
        before = self.state
        self.state = before.moved(scaled, self._digits)
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
            **(dict(extra) if extra else {}),
        }

    # ----------------------------------------------------------------- bias

    def bias(self, character: GoalCharacter, source: str) -> float:
        """The affective adjustment to a goal's priority, within ±BIAS_LIMIT.

        Urgent survival goals are never adjusted: affect reorders near
        neighbours among the legitimate, non-urgent candidates, and nothing
        more.
        """
        if self.mode != "active" or source == "emergency":
            return 0.0
        pull = SENSITIVITY[character]
        raw = sum(weight * self.state.get(dimension) for dimension, weight in pull.items())
        return round(max(-BIAS_LIMIT, min(BIAS_LIMIT, BIAS_LIMIT * raw)), 3)

    def tolerance(self) -> float:
        """Willingness to explore the untried, as a factor on the exploration bonus.

        Unease and a sense of not being in control make Person prefer what it
        knows; a sense of control lets it tolerate a little more. This is a
        preference inside what the runtime already permits, never a change to
        what it permits.
        """
        if self.mode != "active":
            return 1.0
        low, high = TOLERANCE_RANGE
        raw = 1.0 - 0.5 * self.state.unease + 0.25 * self.state.control
        return round(max(low, min(high, raw)), 4)


def adjusted(state: AffectState) -> Affect:
    """An Affect holding `state`, for probes and tests."""
    affect = Affect(AffectRecord())
    affect.state = replace(state)
    return affect


# ---------------------------------------------------------- research bounds
#
# What affect could do at most under the current architecture (R1.5): a
# static property of the code above, for the experiment harness to judge
# whether a decision gave affect any opportunity. Person never consults it.

#: The characters a goal can have for affect. `fixed` goals (urgent survival,
#: experimental trials) receive no bias at all.
CHARACTERS: tuple[str, ...] = ("protective", "outgoing", "fixed")
#: How `bias_swings` probes each character: a goal of that character, and a
#: source. A `fixed` goal is any goal from an emergency. No environment's fact
#: names are needed: the bound is a property of affect alone.
_PROBE: Mapping[str, tuple[GoalCharacter, str]] = {
    "protective": ("protective", "homeostasis"),
    "outgoing": ("outgoing", "homeostasis"),
    "fixed": ("outgoing", "emergency"),
}


def bias_swings(steps: int = 20) -> dict[str, dict[str, float]]:
    """The largest `bias(a) - bias(b)` any reachable state can produce.

    Found by evaluating `Affect.bias` itself over a grid of the state space,
    which includes every vertex, so it follows the code rather than restating
    it. One state biases both goals, which is why two goals of the same
    character can never be reordered by affect.
    """
    affect = Affect(AffectRecord())

    def axis(dimension: str) -> list[float]:
        low, high = RANGES[dimension]
        return [low + (high - low) * index / steps for index in range(steps + 1)]

    swings = {a: dict.fromkeys(CHARACTERS, 0.0) for a in CHARACTERS}
    for valence in axis("valence"):
        for unease in axis("unease"):
            for control in axis("control"):
                affect.state = AffectState(valence, unease, control)
                bias = {
                    character: affect.bias(probe, source)
                    for character, (probe, source) in _PROBE.items()
                }
                for a in CHARACTERS:
                    for b in CHARACTERS:
                        swings[a][b] = max(swings[a][b], round(bias[a] - bias[b], 4))
    return swings


def research_bounds() -> dict[str, Any]:
    """Everything the harness needs to judge affect's opportunity."""
    return {
        "bias_limit": BIAS_LIMIT,
        "tolerance_range": list(TOLERANCE_RANGE),
        "half_lives": dict(HALF_LIVES),
        "ranges": {dimension: list(RANGES[dimension]) for dimension in DIMENSIONS},
        "swings": bias_swings(),
    }
