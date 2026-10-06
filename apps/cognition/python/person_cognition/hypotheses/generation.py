"""Proposing hypotheses: reasoning, which is not evidence.

A proposer is given a bounded reasoning context and suggests candidate
hypotheses. The context holds only what Person has: the anomaly, a few of its
own classified trials with the conditions it perceived at the time, the
vocabulary it may use, the skills it was offered and its current belief about
that effect. No observation, no journal, no world, no positions, no targets.

Whatever comes back is untrusted data. The grounding gate admits a proposal
only if every field is one a hypothesis has, every value is in Person's
vocabulary, the outcome is something Person can observe the intervention
failing to produce, and it cites premises from its context. It admits it with
no evidence at all: what motivated a hypothesis is not what confirms it, and
nothing a proposer says about its own confidence counts.

Two proposers exist. The contrast proposer, deterministic, suggests the
conditions that differed between trials that worked and trials that did not.
`ModelProposer` lets a language model reason for Person through the same
context and the same gate; none is wired in yet. Proposing and planning are
separate stages: a proposal is never a plan.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .hypothesis import DIRECTIONS, CausalHypothesis, Condition, Outcome, Provenance
from .quarantine import refusal
from .vocabulary import VARIABLES

#: Trials a reasoning context may hold.
CONTEXT_TRIALS = 8
#: Proposals considered from one context.
MAX_PROPOSALS = 3
#: Characters of rationale kept, for people to read.
RATIONALE_LIMIT = 240
#: The only fields a proposal may have.
FIELDS: frozenset[str] = frozenset(
    {"condition", "intervention", "outcome", "horizon", "premises", "rationale"}
)
#: The only horizon Person can judge: the observation after one action.
HORIZON = 1


@dataclass(frozen=True, slots=True)
class TrialRecord:
    """One of Person's own classified trials, with the conditions it perceived."""

    ref: str
    skill: str
    fact: str
    verdict: str
    conditions: Mapping[str, str | None]

    def to_json(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "skill": self.skill,
            "fact": self.fact,
            "verdict": self.verdict,
            "conditions": dict(self.conditions),
        }


@dataclass(frozen=True, slots=True)
class ReasoningContext:
    """Everything a proposer may know, and nothing more."""

    #: The skill and effect whose outcomes need explaining.
    skill: str
    fact: str
    #: `variation` (it sometimes followed and sometimes did not) or
    #: `repeated_error` (it kept not following).
    question: str
    trials: tuple[TrialRecord, ...]
    vocabulary: Mapping[str, tuple[str, ...]]
    #: Offered skills, and the effects of each Person can judge.
    interventions: Mapping[str, tuple[str, ...]]
    #: Person's current reliability belief for this effect (ADR 0011).
    belief: Mapping[str, Any] | None

    def premises(self) -> frozenset[str]:
        return frozenset(trial.ref for trial in self.trials)

    def to_json(self) -> dict[str, Any]:
        """Exactly what a language model would be shown."""
        return {
            "question": self.question,
            "skill": self.skill,
            "fact": self.fact,
            "trials": [trial.to_json() for trial in self.trials],
            "vocabulary": {name: list(values) for name, values in self.vocabulary.items()},
            "interventions": {name: list(facts) for name, facts in self.interventions.items()},
            "belief": dict(self.belief) if self.belief is not None else None,
            "form": {
                "condition": {"variable": "one of vocabulary", "value": "one of its values"},
                "intervention": "one of interventions",
                "outcome": {"fact": "one of that intervention's facts", "direction": DIRECTIONS},
                "horizon": HORIZON,
                "premises": "refs of the trials that motivated it",
                "rationale": "optional, for people",
            },
        }


@runtime_checkable
class Proposer(Protocol):
    #: `deterministic` or `language_model`.
    kind: str

    def propose(self, context: ReasoningContext) -> Sequence[Any]: ...


class ContrastProposer:
    """What was different when it did not work?

    For each perceived condition, the values more common among trials where
    the effect did not follow than among trials where it did are candidate
    causes, most lopsided first.
    """

    kind = "deterministic"

    def propose(self, context: ReasoningContext) -> list[dict[str, Any]]:
        failed = [trial for trial in context.trials if trial.verdict == "contradicts"]
        worked = [trial for trial in context.trials if trial.verdict == "supports"]
        if not failed:
            return []
        ranked: list[tuple[float, int, str, str]] = []
        for order, variable in enumerate(VARIABLES):
            values = {trial.conditions.get(variable) for trial in failed} - {None}
            for value in sorted(str(item) for item in values):
                share_failed = sum(t.conditions.get(variable) == value for t in failed) / len(
                    failed
                )
                share_worked = (
                    sum(t.conditions.get(variable) == value for t in worked) / len(worked)
                    if worked
                    else 0.0
                )
                if share_failed > share_worked:
                    ranked.append((share_failed - share_worked, -order, variable, value))
        ranked.sort(reverse=True)
        proposals: list[dict[str, Any]] = []
        for _gap, _order, variable, value in ranked[:MAX_PROPOSALS]:
            premises = [
                trial.ref
                for trial in context.trials
                if trial.verdict in {"contradicts", "supports"}
                and (trial.verdict == "supports" or trial.conditions.get(variable) == value)
            ]
            proposals.append(
                {
                    "condition": {"variable": variable, "value": value},
                    "intervention": context.skill,
                    "outcome": {"fact": context.fact, "direction": "less_likely"},
                    "horizon": HORIZON,
                    "premises": premises,
                    "rationale": (
                        f"{context.fact} did not follow {context.skill} in "
                        f"{sum(t.conditions.get(variable) == value for t in failed)} of "
                        f"{len(failed)} such trials with {variable} {value}"
                    ),
                }
            )
        return proposals


class ModelProposer:
    """A language model reasoning for Person, through the same gate.

    `complete` receives the reasoning context as JSON text and returns JSON
    text: a list of proposals. That is the whole interface. Text that is not
    a list of objects is passed on as a malformed proposal, so the gate
    records it rather than it vanishing.
    """

    kind = "language_model"

    def __init__(self, complete: Callable[[str], str]) -> None:
        self._complete = complete

    def propose(self, context: ReasoningContext) -> list[Any]:
        text = self._complete(json.dumps(context.to_json(), sort_keys=True))
        try:
            parsed = json.loads(text)
        except ValueError:
            return [None]
        if not isinstance(parsed, list):
            return [None]
        return parsed[:MAX_PROPOSALS]


@dataclass(frozen=True, slots=True)
class Rejection:
    """A quarantined proposal: why, and the names it used. Never its values."""

    reasons: tuple[str, ...]
    fields: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {"reasons": list(self.reasons), "fields": list(self.fields)}


def _names(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        return [str(key) for key in value]
    return []


def admit(
    proposal: Any,
    context: ReasoningContext,
    *,
    hypothesis_id: str,
    proposer: str,
    now: int,
    known: frozenset[tuple[str, str, str, str, str]] = frozenset(),
) -> CausalHypothesis | Rejection:
    """The grounding gate. A hypothesis with no evidence, or the reasons why not."""
    if not isinstance(proposal, Mapping):
        return Rejection(("malformed",), ())
    fields = tuple(sorted(str(key) for key in proposal)[:16])
    reasons: list[str] = [refusal(key) for key in fields if key not in FIELDS]

    condition = proposal.get("condition")
    outcome = proposal.get("outcome")
    for part, allowed in ((condition, {"variable", "value"}), (outcome, {"fact", "direction"})):
        reasons.extend(refusal(key) for key in _names(part) if key not in allowed)

    variable = condition.get("variable") if isinstance(condition, Mapping) else None
    value = condition.get("value") if isinstance(condition, Mapping) else None
    if not isinstance(variable, str) or not isinstance(value, str):
        reasons.append("no_condition")
    elif variable not in context.vocabulary:
        reasons.append("unknown_variable")
    elif value not in context.vocabulary[variable]:
        reasons.append("unavailable_value")

    intervention = proposal.get("intervention")
    if not isinstance(intervention, str) or intervention not in context.interventions:
        reasons.append("unavailable_capability")

    fact = outcome.get("fact") if isinstance(outcome, Mapping) else None
    direction = outcome.get("direction") if isinstance(outcome, Mapping) else None
    if not isinstance(fact, str):
        reasons.append("no_observable_outcome")
    elif isinstance(intervention, str) and fact not in context.interventions.get(intervention, ()):
        reasons.append("unfalsifiable")
    if direction not in DIRECTIONS:
        reasons.append("invalid_direction")

    if proposal.get("horizon", HORIZON) != HORIZON:
        reasons.append("unsupported_horizon")

    premises = proposal.get("premises")
    available = context.premises()
    if (
        not isinstance(premises, list)
        or not premises
        or not all(isinstance(item, str) and item in available for item in premises)
    ):
        reasons.append("ungrounded")

    rationale = proposal.get("rationale", "")
    if not isinstance(rationale, str):
        reasons.append("malformed_rationale")

    if reasons:
        return Rejection(tuple(dict.fromkeys(reasons)), fields)
    assert isinstance(variable, str) and isinstance(value, str)
    assert isinstance(intervention, str) and isinstance(fact, str)
    assert isinstance(direction, str) and isinstance(premises, list)
    hypothesis = CausalHypothesis(
        hypothesis_id=hypothesis_id,
        condition=Condition(variable, value),
        intervention=intervention,
        outcome=Outcome(fact, direction),
        horizon=HORIZON,
        provenance=Provenance(
            proposer=proposer,
            premises=tuple(dict.fromkeys(premises)),
            proposed_at=now,
        ),
        rationale=str(rationale)[:RATIONALE_LIMIT],
    )
    if hypothesis.signature in known:
        return Rejection(("duplicate",), fields)
    return hypothesis
