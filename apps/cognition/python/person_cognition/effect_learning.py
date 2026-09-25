"""Learned reliability of skill effects, from prediction error (ADR 0011).

A skill's contract says what the skill is meant to do. That is a prediction,
not proof. This module lets Person learn, from its own experience, how far to
trust it: "when I gather wood, my wood goes up", or "this has been unreliable
for me". It is the first generalised belief Person holds, and deliberately the
only kind: one per (skill, effect fact), nothing else.

The chain is:

    the executed skill's declared effect  (the prediction target)
        -> was the skill genuinely attempted?
        -> can Person evaluate the effect from its own experience?
        -> supports / partial / contradicts / inconclusive
        -> a bounded evidence update to an uncertain belief
        -> under an active learning mode, a bounded term in routine scoring

Only a genuine attempt teaches anything. A proposal the runtime refused, a
takeover by the safety kernel, a preemption, a missing prerequisite found
before anything physical happened, an unreachable target: none of these is
evidence about what the action does, and each is recorded as inconclusive
with the reason.

Only a fact Person can evaluate counts. Inventory and body state are felt;
the planner's `at_home` and `sheltered` are Person's own beliefs, made true by
the same outcome report they would be judged against; facts that no
observation carries are unobservable; facts the observation takes from the
runtime's placement ledger are bookkeeping, not experience. None of those
teaches reliability.

Beliefs are keyed by skill and fact, never by target. Under C4 the motor
chooses its own target, and nothing here pretends to know which thing an
action was done to.

Uncertainty is first-class. A belief keeps its supporting and contradicting
evidence separately; its estimate and its strength are separate numbers; with
no evidence it has no estimate at all, and a belief with no strength
contributes nothing to any decision.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from person_persistence import EvidenceEvent
from person_skills import SkillRegistry

from .prediction import compare

#: Facts a trial can teach reliability about: inventory, which Person holds and
#: feels, body state, and threat it perceives. Implementation parameter, and
#: the reason every other fact is excluded is in the module docstring.
EVALUABLE_FACTS: frozenset[str] = frozenset(
    {
        "wood",
        "planks",
        "stone",
        "coal",
        "fuel",
        "raw_food",
        "cooked_food",
        "plant_food",
        "edible_food",
        "building_materials",
        "chest_item",
        "wooden_pickaxe",
        "stone_pickaxe",
        "wooden_axe",
        "stone_axe",
        "tool_tier",
        "food_level",
        "health_level",
        "inventory_space",
        "safe",
    }
)

#: Failure reasons that mean a prerequisite was missing or a target could not
#: be found before anything physical was attempted.
NOT_ATTEMPTED_REASONS: frozenset[str] = frozenset(
    {
        "missing_materials",
        "missing_tool",
        "no_placement_site",
        "obstructed_site",
        "empty_container",
        "inventory_full",
        "container_full",
        "no_diggable_ground",
        "no_safe_route",
        "nothing_to_deposit",
        "no_permitted_target",
        "no_permitted_container",
        "no_owned_storage",
        "no_furnace",
        "protected_area",
        "unreachable_resource",
        "unreachable_home",
        "unreachable_target",
        "no_route",
        "invalid_parameter",
        "invalid_direction",
    }
)

#: Statuses that are never a genuine attempt of the requested skill.
NOT_ATTEMPTED_STATUSES: frozenset[str] = frozenset(
    {"INVALIDATED", "UNREACHABLE", "INTERRUPTED", "PREEMPTED", "DISCONNECTED", "DEATH"}
)

#: Evidence weights for each verdict, as (supporting, contradicting).
WEIGHTS: Mapping[str, tuple[float, float]] = {
    "supports": (1.0, 0.0),
    "partial": (0.5, 0.5),
    "contradicts": (0.0, 1.0),
}

#: Evidence at which a belief's strength reaches one half. Parameter.
HALF_STRENGTH = 4.0
#: The most a learned belief may add to or take from a routine's score, on a
#: scale where the exploration bonus is 0.15. Parameter.
RELIABILITY_LIMIT = 0.1
#: Provenance kept per belief: the latest evidence records that shaped it.
PROVENANCE = 8


@dataclass(frozen=True, slots=True)
class Trial:
    """One settled prediction, classified: what it can and cannot teach."""

    skill: str
    fact: str
    verdict: str
    reason: str

    def to_json(self) -> dict[str, str]:
        return {
            "skill": self.skill,
            "fact": self.fact,
            "verdict": self.verdict,
            "reason": self.reason,
        }


def attempt_reason(
    *,
    requested: str,
    executed: str | None,
    status: str | None,
    requested_status: str | None,
    emergency: bool,
    reason_codes: Iterable[str],
) -> str | None:
    """Why this was not a genuine attempt of the requested skill, or None if it was."""
    if emergency or executed != requested:
        return "overridden_by_runtime"
    if status is None:
        return "no_outcome"
    if requested_status in NOT_ATTEMPTED_STATUSES or status in NOT_ATTEMPTED_STATUSES:
        return f"not_attempted_{(status or '').lower()}"
    blocking = set(reason_codes) & NOT_ATTEMPTED_REASONS
    if blocking:
        return f"not_attempted_{sorted(blocking)[0]}"
    return None


def classify(
    *,
    requested: str,
    executed: str | None,
    status: str | None,
    requested_status: str | None,
    emergency: bool,
    reason_codes: Iterable[str],
    expected_effects: Iterable[Mapping[str, Any]],
    state_before: Mapping[str, float],
    state_after: Mapping[str, float] | None,
) -> list[Trial]:
    """What one settled prediction says about each declared effect."""
    effects = list(expected_effects)
    skill = executed or requested
    if not effects:
        return []
    why_not = attempt_reason(
        requested=requested,
        executed=executed,
        status=status,
        requested_status=requested_status,
        emergency=emergency,
        reason_codes=reason_codes,
    )
    if why_not is not None:
        return [Trial(skill, str(effect["fact"]), "inconclusive", why_not) for effect in effects]
    if state_after is None:
        return [
            Trial(skill, str(effect["fact"]), "inconclusive", "no_observation_after")
            for effect in effects
        ]
    errors, _, _ = compare(effects, state_before, state_after)
    trials: list[Trial] = []
    for entry in errors:
        if entry.fact not in EVALUABLE_FACTS:
            trials.append(Trial(skill, entry.fact, "inconclusive", "not_evaluable_by_person"))
        elif entry.severity in {"none", "minor"}:
            trials.append(Trial(skill, entry.fact, "supports", "effect_observed"))
        elif entry.severity == "major":
            trials.append(Trial(skill, entry.fact, "partial", "effect_partly_observed"))
        else:
            trials.append(Trial(skill, entry.fact, "contradicts", "effect_absent"))
    return trials


@dataclass(frozen=True, slots=True)
class EffectBelief:
    """How much Person trusts one declared effect of one skill, and why."""

    skill: str
    fact: str
    supporting: float = 0.0
    contradicting: float = 0.0
    #: The latest evidence records behind it: engineering provenance.
    provenance: tuple[str, ...] = ()

    @property
    def evidence(self) -> float:
        return self.supporting + self.contradicting

    @property
    def estimate(self) -> float | None:
        """Expected reliability, or None: with no experience, no estimate."""
        if self.evidence == 0:
            return None
        # A Beta(1, 1) prior, so one outcome moves the estimate but cannot
        # make it 0 or 1.
        return (self.supporting + 1.0) / (self.evidence + 2.0)

    @property
    def strength(self) -> float:
        """How much experience stands behind the estimate, from 0 towards 1."""
        return self.evidence / (self.evidence + HALF_STRENGTH)

    def updated(self, verdict: str, record: str) -> EffectBelief:
        supporting, contradicting = WEIGHTS[verdict]
        return replace(
            self,
            supporting=self.supporting + supporting,
            contradicting=self.contradicting + contradicting,
            provenance=(*self.provenance, record)[-PROVENANCE:],
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "fact": self.fact,
            "supporting": self.supporting,
            "contradicting": self.contradicting,
            "provenance": list(self.provenance),
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> EffectBelief:
        return cls(
            skill=str(body["skill"]),
            fact=str(body["fact"]),
            supporting=float(body["supporting"]),
            contradicting=float(body["contradicting"]),
            provenance=tuple(str(item) for item in body["provenance"]),
        )


Key = tuple[str, str, str]


class EffectBeliefs:
    """Active and shadow beliefs, rebuilt from `effect_evidence` records alone.

    The two tables never mix. What a record was admitted to is decided when it
    is written, by the learning mode then in force: nothing (`off`), the
    shadow table (`shadow`), or the active table (`supervised`).
    """

    def __init__(self) -> None:
        self.tables: dict[str, dict[Key, EffectBelief]] = {"active": {}, "shadow": {}}

    def reset(self) -> None:
        for table in self.tables.values():
            table.clear()

    def apply(self, event: EvidenceEvent) -> None:
        if event.type != "effect_evidence":
            return
        table = self.tables.get(str(event.payload["admitted_to"]))
        verdict = str(event.payload["verdict"])
        if table is None or verdict not in WEIGHTS:
            return
        key = (event.training_context, str(event.payload["skill"]), str(event.payload["fact"]))
        belief = table.get(key) or EffectBelief(skill=key[1], fact=key[2])
        table[key] = belief.updated(verdict, event.event_id)

    def to_json(self) -> dict[str, Any]:
        return {
            name: [
                {"training_context": key[0], **belief.to_json()}
                for key, belief in sorted(table.items())
            ]
            for name, table in self.tables.items()
        }

    def load_json(self, body: Mapping[str, Any]) -> None:
        self.reset()
        for name, records in body.items():
            for record in records:
                belief = EffectBelief.from_json(record)
                self.tables[name][(str(record["training_context"]), belief.skill, belief.fact)] = (
                    belief
                )

    def belief(
        self, table: str, training_context: str, skill: str, fact: str
    ) -> EffectBelief | None:
        return self.tables[table].get((training_context, skill, fact))


def admitted_to(learning_mode: str) -> str:
    """Where a new trial's evidence goes under a learning mode."""
    return {"off": "none", "shadow": "shadow", "supervised": "active"}.get(learning_mode, "none")


def reliability_term(
    beliefs: EffectBeliefs,
    registry: SkillRegistry,
    training_context: str,
) -> Callable[[tuple[str, ...]], float]:
    """A scorer for routines from the active beliefs: bounded and generic.

    Each step contributes the mean, over its skill's evaluable declared
    effects, of (estimate - 0.5) weighted by strength: a skill Person has
    found reliable adds, one it has found unreliable subtracts, and one it
    knows nothing about adds nothing. The routine's term is the mean over its
    steps, scaled to at most `RELIABILITY_LIMIT` either way.
    """

    def skill_term(skill: str) -> float:
        if skill not in registry.ids:
            return 0.0
        terms: list[float] = []
        for effect in registry.get(skill).expected_effects:
            if effect.fact not in EVALUABLE_FACTS:
                continue
            belief = beliefs.belief("active", training_context, skill, effect.fact)
            if belief is None or belief.estimate is None:
                terms.append(0.0)
            else:
                terms.append((belief.estimate - 0.5) * belief.strength)
        return sum(terms) / len(terms) if terms else 0.0

    def term(steps: tuple[str, ...]) -> float:
        if not steps:
            return 0.0
        mean = sum(skill_term(step) for step in steps) / len(steps)
        return round(
            max(-RELIABILITY_LIMIT, min(RELIABILITY_LIMIT, 2 * RELIABILITY_LIMIT * mean)), 4
        )

    return term
