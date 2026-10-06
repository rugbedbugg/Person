"""A causal hypothesis: typed, structured, falsifiable, and never a fact.

    WHEN   condition C (one perceived variable, one value)
    IF     Person performs intervention A (a skill it has)
    THEN   observable outcome O is less, or more, likely than when C does not
           hold
    WITHIN one action: judged on the observation that follows it

Evidence is kept in four cells: whether the condition held (the arm), crossed
with how the trial came about (the kind). A trial Person made as the
experiment for this hypothesis is interventional; one from ordinary life that
happens to match is observational, because Person did not choose the
condition in order to test it. Observational evidence counts, and counts for
less.

Two numbers are kept apart. The relation is how much less (or more) often the
outcome followed when the condition held, in the direction claimed. The
confidence is how much evidence stands behind that, measured on the thinner
arm, because a contrast is only as good as its weaker side.

Standing is derived from evidence every time it is asked for, so it can move
either way for as long as evidence arrives. A hypothesis is never true,
proven or a fact; the most it can be is supported.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

DIRECTIONS: tuple[str, ...] = ("less_likely", "more_likely")
ARMS: tuple[str, ...] = ("held", "absent")
KINDS: tuple[str, ...] = ("interventional", "observational")
LIFECYCLES: tuple[str, ...] = ("proposed", "testable", "under_test", "retired")
STANDINGS: tuple[str, ...] = ("unresolved", "supported", "weakened", "contradicted")

#: Where the knowledge a hypothesis involves comes from. The names may change;
#: the distinctions may not (`PERSON_SPEC` 22.2, ADR 0012). A hypothesis is
#: Person's inference; its evidence is Person's observation or experiment;
#: skill contracts and the vocabulary are initial knowledge.
INITIAL = "INITIAL"
PERSONAL_OBSERVATION = "PERSONAL_OBSERVATION"
PERSONAL_EXPERIMENT = "PERSONAL_EXPERIMENT"
INFERENCE = "INFERENCE"
EVIDENCE_SOURCE: Mapping[str, str] = {
    "interventional": PERSONAL_EXPERIMENT,
    "observational": PERSONAL_OBSERVATION,
}

#: How much one trial of each kind counts. Parameters.
KIND_WEIGHT: Mapping[str, float] = {"interventional": 1.0, "observational": 0.5}
#: What a verdict says about the outcome, as (followed, did not follow).
VERDICT_WEIGHT: Mapping[str, tuple[float, float]] = {
    "supports": (1.0, 0.0),
    "partial": (0.5, 0.5),
    "contradicts": (0.0, 1.0),
}
#: Weighted evidence on the thinner arm at which confidence reaches a half.
HALF_CONFIDENCE = 4.0
#: Confidence below which no standing is claimed.
DECISIVE_CONFIDENCE = 0.5
#: Relation at or above which a decisive hypothesis is supported, and at or
#: below which it is contradicted. Between the two it is weakened.
SUPPORTED_RELATION = 0.3
CONTRADICTED_RELATION = 0.1
#: Evidence records kept on each side, for provenance.
REFS = 8


@dataclass(frozen=True, slots=True)
class Condition:
    variable: str
    value: str

    def to_json(self) -> dict[str, str]:
        return {"variable": self.variable, "value": self.value}


@dataclass(frozen=True, slots=True)
class Outcome:
    fact: str
    direction: str

    def to_json(self) -> dict[str, str]:
        return {"fact": self.fact, "direction": self.direction}


@dataclass(frozen=True, slots=True)
class Provenance:
    """Who proposed the hypothesis, from what, and when. Not evidence."""

    #: The kind of reasoner: `deterministic` or `language_model`.
    proposer: str
    #: The trials that motivated it. They are why it was proposed; they are
    #: never counted for it, because it was fitted to them.
    premises: tuple[str, ...]
    #: Person's experienced time when it was proposed.
    proposed_at: int
    source: str = INFERENCE

    def to_json(self) -> dict[str, Any]:
        return {
            "proposer": self.proposer,
            "premises": list(self.premises),
            "proposed_at": self.proposed_at,
            "source": self.source,
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> Provenance:
        return cls(
            proposer=str(body["proposer"]),
            premises=tuple(str(item) for item in body["premises"]),
            proposed_at=int(body["proposed_at"]),
            source=str(body["source"]),
        )


@dataclass(frozen=True, slots=True)
class Cell:
    """Weighted outcomes of one arm and one kind."""

    followed: float = 0.0
    absent: float = 0.0
    trials: int = 0

    def to_json(self) -> dict[str, Any]:
        return {"followed": self.followed, "absent": self.absent, "trials": self.trials}


def _cells() -> dict[str, Cell]:
    return {f"{arm}:{kind}": Cell() for arm in ARMS for kind in KINDS}


@dataclass(frozen=True, slots=True)
class CausalHypothesis:
    hypothesis_id: str
    condition: Condition
    intervention: str
    outcome: Outcome
    #: In actions: the outcome is judged on the observation after one action.
    horizon: int
    provenance: Provenance
    #: For people to read. Nothing parses it and nothing acts on it.
    rationale: str = ""
    lifecycle: str = "proposed"
    cells: Mapping[str, Cell] = field(default_factory=_cells)
    #: The latest trials that counted for it, and against it.
    supporting: tuple[str, ...] = ()
    contradicting: tuple[str, ...] = ()

    # ------------------------------------------------------------- identity

    @property
    def signature(self) -> tuple[str, str, str, str, str]:
        """What it claims, without who said it or why: duplicates share one."""
        return (
            self.condition.variable,
            self.condition.value,
            self.intervention,
            self.outcome.fact,
            self.outcome.direction,
        )

    # ------------------------------------------------------------- evidence

    def arm(self, arm: str) -> tuple[float, float]:
        """Weighted (followed, did not follow) on one arm, across both kinds."""
        followed = absent = 0.0
        for kind in KINDS:
            cell = self.cells[f"{arm}:{kind}"]
            followed += KIND_WEIGHT[kind] * cell.followed
            absent += KIND_WEIGHT[kind] * cell.absent
        return followed, absent

    def estimate(self, arm: str) -> float | None:
        """How often the outcome followed on this arm, or None with no evidence."""
        followed, absent = self.arm(arm)
        if followed + absent == 0:
            return None
        # A uniform prior: one trial moves it, none can make it certain.
        return (followed + 1.0) / (followed + absent + 2.0)

    @property
    def relation(self) -> float | None:
        """How far the evidence bears out the claimed difference, from -1 to 1."""
        held, absent = self.estimate("held"), self.estimate("absent")
        if held is None or absent is None:
            return None
        difference = absent - held
        return difference if self.outcome.direction == "less_likely" else -difference

    @property
    def confidence(self) -> float:
        """How much evidence stands behind the relation, from 0 towards 1."""
        thinnest = min(sum(self.arm(arm)) for arm in ARMS)
        return thinnest / (thinnest + HALF_CONFIDENCE)

    @property
    def controlled(self) -> bool:
        """Whether Person has intervened on both sides of the contrast."""
        return all(self.cells[f"{arm}:interventional"].trials > 0 for arm in ARMS)

    @property
    def standing(self) -> str:
        """What the evidence says now. Correlation alone never settles it."""
        relation = self.relation
        if relation is None or self.confidence < DECISIVE_CONFIDENCE or not self.controlled:
            return "unresolved"
        if relation >= SUPPORTED_RELATION:
            return "supported"
        if relation <= CONTRADICTED_RELATION:
            return "contradicted"
        return "weakened"

    @property
    def status(self) -> str:
        standing = self.standing
        return standing if standing != "unresolved" else self.lifecycle

    def updated(self, arm: str, kind: str, verdict: str, ref: str) -> CausalHypothesis:
        followed, absent = VERDICT_WEIGHT[verdict]
        key = f"{arm}:{kind}"
        cell = self.cells[key]
        cells = {
            **self.cells,
            key: Cell(cell.followed + followed, cell.absent + absent, cell.trials + 1),
        }
        # Which way this one trial pointed, for the provenance lists: for
        # "less likely when held", the outcome following without the
        # condition, or failing with it, agrees.
        agrees = (followed > absent) == (arm == "absent")
        if self.outcome.direction == "more_likely":
            agrees = not agrees
        supporting, contradicting = self.supporting, self.contradicting
        if followed != absent:
            if agrees:
                supporting = (*supporting, ref)[-REFS:]
            else:
                contradicting = (*contradicting, ref)[-REFS:]
        return replace(self, cells=cells, supporting=supporting, contradicting=contradicting)

    # ---------------------------------------------------------- persistence

    def to_json(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "condition": self.condition.to_json(),
            "intervention": self.intervention,
            "outcome": self.outcome.to_json(),
            "horizon": self.horizon,
            "provenance": self.provenance.to_json(),
            "rationale": self.rationale,
            "lifecycle": self.lifecycle,
            "cells": {key: cell.to_json() for key, cell in sorted(self.cells.items())},
            "supporting": list(self.supporting),
            "contradicting": list(self.contradicting),
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> CausalHypothesis:
        return cls(
            hypothesis_id=str(body["hypothesis_id"]),
            condition=Condition(
                str(body["condition"]["variable"]), str(body["condition"]["value"])
            ),
            intervention=str(body["intervention"]),
            outcome=Outcome(str(body["outcome"]["fact"]), str(body["outcome"]["direction"])),
            horizon=int(body["horizon"]),
            provenance=Provenance.from_json(body["provenance"]),
            rationale=str(body["rationale"]),
            lifecycle=str(body["lifecycle"]),
            cells={
                str(key): Cell(float(cell["followed"]), float(cell["absent"]), int(cell["trials"]))
                for key, cell in body["cells"].items()
            },
            supporting=tuple(str(item) for item in body["supporting"]),
            contradicting=tuple(str(item) for item in body["contradicting"]),
        )

    def summary(self) -> dict[str, Any]:
        """The epistemic state, for journals and operators."""
        relation = self.relation
        return {
            "hypothesis_id": self.hypothesis_id,
            "status": self.status,
            "standing": self.standing,
            "relation": None if relation is None else round(relation, 4),
            "confidence": round(self.confidence, 4),
            "controlled": self.controlled,
        }
