"""How a supported hypothesis may bear on a choice: a little, and visibly.

Under `supervised` only, a supported hypothesis whose condition holds now
moves the score of routines that use its intervention, in the direction it
claims, by at most `HYPOTHESIS_LIMIT` either way. The term is recorded apart
from every other part of a routine's score. It adds no candidate, removes
none, and cannot make a routine the runtime would refuse win.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .hypothesis import CausalHypothesis
from .vocabulary import Perceived

#: The most supported hypotheses may add to or take from a routine's score.
HYPOTHESIS_LIMIT = 0.1


def hypothesis_term(
    hypotheses: Mapping[str, CausalHypothesis], now: Perceived
) -> Callable[[tuple[str, ...]], float]:
    applying = [
        hypothesis
        for hypothesis in hypotheses.values()
        if hypothesis.standing == "supported"
        and now.value(hypothesis.condition.variable) == hypothesis.condition.value
    ]

    def skill_term(skill: str) -> float:
        total = 0.0
        for hypothesis in applying:
            if hypothesis.intervention != skill or hypothesis.relation is None:
                continue
            sign = -1.0 if hypothesis.outcome.direction == "less_likely" else 1.0
            total += sign * hypothesis.relation * hypothesis.confidence
        return total

    def term(steps: tuple[str, ...]) -> float:
        if not steps or not applying:
            return 0.0
        mean = sum(skill_term(step) for step in steps) / len(steps)
        return round(max(-HYPOTHESIS_LIMIT, min(HYPOTHESIS_LIMIT, HYPOTHESIS_LIMIT * mean)), 4)

    return term
