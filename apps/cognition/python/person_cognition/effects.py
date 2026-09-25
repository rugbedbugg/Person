"""Compare a skill's declared effects with what two observations actually show.

This is the prediction-error comparison that already exists, asked a different
question. During a run, ``prediction`` settles a prediction against the next
observation the loop receives. During an operator's single-skill validation
run there is no loop, but there are two observations taken either side of one
skill, and the same question is worth asking about them.

Nothing here decides anything. It reads two observations and a list of declared
effects, and returns a verdict per fact. It never touches the evidence store,
never scores a routine, and never reaches the runtime: the Node harness spawns
it, reads the JSON it prints, and writes the result into a validation report.

Both sides of the comparison come from :func:`person_planner.symbolic_state`
and :func:`person_cognition.prediction.compare`, so a validation report and a
live prediction error mean the same thing by construction.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from person_planner import symbolic_state

from .prediction import compare

Verdict = Literal["match", "mismatch", "not_observable", "inconclusive"]

#: Facts an Observation cannot carry.
#:
#: ``symbolic_state`` returns a constant zero for each of these, because they
#: record that a transient action completed rather than anything about the
#: world. A skill that promises one of them is not making a checkable claim, and
#: reporting that as a failed prediction would be wrong.
#: `at_home` and `sheltered` are Person's belief about where it is (C8), which
#: an observation alone cannot establish.
UNOBSERVABLE_FACTS: frozenset[str] = frozenset(
    {"rested", "stored_surplus", "withdrawn", "looted", "at_home", "sheltered"}
)


def _verdict(fact: str, severity: str) -> Verdict:
    if fact in UNOBSERVABLE_FACTS:
        return "not_observable"
    if severity == "none":
        return "match"
    if severity == "unobserved":
        return "inconclusive"
    return "mismatch"


def compare_observations(
    expected_effects: Sequence[Mapping[str, Any]],
    before: Mapping[str, Any],
    after: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """One report section: expected against observed, fact by fact."""
    state_before = symbolic_state(dict(before))
    if after is None:
        # A skill that ran but could not be observed afterwards proves nothing
        # either way, and saying so is more useful than calling it a failure.
        return {
            "available": True,
            "reason": "post_observation_unavailable",
            "facts": [
                {
                    "fact": str(effect["fact"]),
                    "op": str(effect["op"]),
                    "predictedValue": float(effect["value"]),
                    "before": float(state_before.get(str(effect["fact"]), 0.0)),
                    "predicted": None,
                    "observed": None,
                    "severity": "unobserved",
                    "verdict": "inconclusive",
                }
                for effect in expected_effects
            ],
            "unexplained": [],
            "worstSeverity": "unobserved",
            "matched": 0,
            "mismatched": 0,
            "notObservable": 0,
            "inconclusive": len(expected_effects),
        }

    state_after = symbolic_state(dict(after))
    errors, unexplained, worst = compare(expected_effects, state_before, state_after)

    facts: list[dict[str, Any]] = []
    for effect, entry in zip(expected_effects, errors, strict=True):
        verdict = _verdict(entry.fact, entry.severity)
        facts.append(
            {
                "fact": entry.fact,
                "op": str(effect["op"]),
                "predictedValue": float(effect["value"]),
                "before": entry.before,
                "predicted": entry.predicted,
                "observed": entry.observed,
                "severity": entry.severity,
                "verdict": verdict,
            }
        )

    def count(name: Verdict) -> int:
        return sum(1 for fact in facts if fact["verdict"] == name)

    return {
        "available": True,
        "reason": None,
        "facts": facts,
        "unexplained": unexplained,
        "worstSeverity": worst,
        "matched": count("match"),
        "mismatched": count("mismatch"),
        "notObservable": count("not_observable"),
        "inconclusive": count("inconclusive"),
    }


def run(request: Mapping[str, Any]) -> dict[str, Any]:
    """Entry point for the one-shot comparison the Node harness asks for."""
    after = request.get("after")
    return compare_observations(
        request.get("expectedEffects") or [],
        request["before"],
        after if isinstance(after, Mapping) else None,
    )


def main(path: str) -> str:
    with open(path, encoding="utf8") as handle:
        request: dict[str, Any] = json.load(handle)
    return json.dumps(run(request))
