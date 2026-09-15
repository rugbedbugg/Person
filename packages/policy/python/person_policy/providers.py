"""Policy providers.

A provider answers one question: given the observation, the active goal and the
candidate routines the planner produced, which routine should Person run, and
on what grounds?

Two providers exist. The deterministic one is the survival-first fallback and
never needs evidence, so Person works with learning switched off. The evidence
provider scores routines from their recorded history and is the only one that
learning mode can put in control.

There is deliberately no neural provider. The interface is here for one, but
inventing one now would add a dependency and a failure mode with nothing to
show for it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .envelope import EnvelopeThresholds, safe_envelope
from .statistics import OutcomeCounts, RoutineStatistics


@dataclass(frozen=True, slots=True)
class RoutineCandidate:
    """What a provider needs to know about one option."""

    routine_id: str
    name: str
    steps: tuple[str, ...]
    step_labels: tuple[str, ...]
    risk: float
    cost: float
    ticks: int
    applicable: bool = True


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: RoutineCandidate
    score: float
    counts: OutcomeCounts
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PolicyChoice:
    routine_id: str
    routine_name: str
    steps: tuple[str, ...]
    confidence: float
    reason_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    policy_revision: int
    learned_or_fallback: str
    candidates: tuple[ScoredCandidate, ...]
    shadow_routine_id: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class PolicyProvider(Protocol):
    name: str

    def propose(
        self,
        observation: dict[str, Any],
        goal: Any,
        candidates: Sequence[RoutineCandidate],
        context_id: str,
    ) -> PolicyChoice: ...


class NoCandidatesError(RuntimeError):
    """The planner produced nothing for this goal."""


def _deterministic_order(candidate: RoutineCandidate) -> tuple[Any, ...]:
    """Safety first, then brevity, then a stable tie-break on identity."""
    return (
        0 if candidate.applicable else 1,
        round(candidate.risk, 6),
        round(candidate.cost, 6),
        len(candidate.steps),
        candidate.routine_id,
    )


class DeterministicPolicyProvider:
    """Survival-first fallback. Requires no evidence and never explores."""

    name = "deterministic"

    def __init__(self, policy_revision: int = 0) -> None:
        self.policy_revision = policy_revision

    def propose(
        self,
        observation: dict[str, Any],
        goal: Any,
        candidates: Sequence[RoutineCandidate],
        context_id: str,
    ) -> PolicyChoice:
        if not candidates:
            raise NoCandidatesError("No candidate routine for the active goal")
        ordered = sorted(candidates, key=_deterministic_order)
        chosen = ordered[0]
        scored = tuple(
            ScoredCandidate(
                candidate=candidate,
                score=-_deterministic_order(candidate)[1] - _deterministic_order(candidate)[2],
                counts=OutcomeCounts(),
                reasons=("deterministic_ranking",),
            )
            for candidate in ordered
        )
        return PolicyChoice(
            routine_id=chosen.routine_id,
            routine_name=chosen.name,
            steps=chosen.steps,
            confidence=0.5,
            reason_codes=("fallback_policy", "lowest_risk_feasible_plan"),
            evidence_refs=(),
            policy_revision=self.policy_revision,
            learned_or_fallback="fallback",
            candidates=scored,
        )


@dataclass(frozen=True, slots=True)
class ScoringWeights:
    """Risk and safety dominate convenience, deliberately."""

    success: float = 1.0
    health: float = 0.9
    risk: float = 0.7
    resource: float = 0.15
    time: float = 0.2
    recovery: float = 0.25


class EvidencePolicyProvider:
    """Uncertainty-aware routine selection from recorded evidence."""

    name = "evidence"

    def __init__(
        self,
        statistics: RoutineStatistics,
        *,
        training_context: str,
        learning_mode: str = "off",
        minimum_support: int = 3,
        exploration_bonus: float = 0.15,
        weights: ScoringWeights | None = None,
        thresholds: EnvelopeThresholds | None = None,
        policy_revision: int = 0,
    ) -> None:
        self.statistics = statistics
        self.training_context = training_context
        self.learning_mode = learning_mode
        self.minimum_support = minimum_support
        self.exploration_bonus = exploration_bonus
        self.weights = weights or ScoringWeights()
        self.thresholds = thresholds
        self.policy_revision = policy_revision
        self.fallback = DeterministicPolicyProvider(policy_revision)

    def score(
        self,
        candidate: RoutineCandidate,
        counts: OutcomeCounts,
        *,
        envelope_open: bool,
    ) -> tuple[float, tuple[str, ...]]:
        weights = self.weights
        reasons: list[str] = []
        estimate = counts.posterior_lower()
        score = weights.success * estimate
        reasons.append("beta_posterior_lower_bound")

        score -= weights.health * min(1.0, counts.mean_health_cost / 20.0)
        score -= weights.risk * candidate.risk
        score -= weights.resource * min(1.0, counts.mean_resource_cost / 32.0)
        score -= weights.time * min(1.0, candidate.ticks / 20000.0)
        score += weights.recovery * (counts.recovery_probability - 0.5)
        if not candidate.applicable:
            score -= 1.0
            reasons.append("preconditions_not_currently_met")

        if envelope_open and counts.decisive < self.minimum_support:
            score += self.exploration_bonus
            reasons.append("exploration_bonus")
        elif counts.decisive < self.minimum_support:
            reasons.append("exploration_suppressed_outside_envelope")
        return score, tuple(reasons)

    def propose(
        self,
        observation: dict[str, Any],
        goal: Any,
        candidates: Sequence[RoutineCandidate],
        context_id: str,
    ) -> PolicyChoice:
        if not candidates:
            raise NoCandidatesError("No candidate routine for the active goal")
        envelope = safe_envelope(observation, self.thresholds)
        scored: list[ScoredCandidate] = []
        for candidate in candidates:
            counts = self.statistics.routine(
                self.training_context, context_id, candidate.routine_id
            )
            value, reasons = self.score(candidate, counts, envelope_open=bool(envelope))
            scored.append(ScoredCandidate(candidate, value, counts, reasons))
        scored.sort(
            key=lambda entry: (
                -entry.score,
                _deterministic_order(entry.candidate),
            )
        )
        best = scored[0]
        fallback = self.fallback.propose(observation, goal, candidates, context_id)

        supported = best.counts.decisive >= self.minimum_support
        reason_codes: list[str] = [*best.reasons]
        reason_codes.append("safe_envelope_open" if envelope else "safe_envelope_closed")
        for reason in envelope.reasons[:4]:
            reason_codes.append(reason)

        if self.learning_mode == "off":
            return PolicyChoice(
                routine_id=fallback.routine_id,
                routine_name=fallback.routine_name,
                steps=fallback.steps,
                confidence=fallback.confidence,
                reason_codes=("learning_off", *fallback.reason_codes),
                evidence_refs=(),
                policy_revision=self.policy_revision,
                learned_or_fallback="fallback",
                candidates=tuple(scored),
            )

        if self.learning_mode == "shadow":
            # The learner proposes and the proposal is recorded, but the
            # fallback is what actually executes.
            return PolicyChoice(
                routine_id=fallback.routine_id,
                routine_name=fallback.routine_name,
                steps=fallback.steps,
                confidence=fallback.confidence,
                reason_codes=("shadow_mode", *fallback.reason_codes, *reason_codes[:4]),
                evidence_refs=tuple(best.counts.evidence_refs[-8:]),
                policy_revision=self.policy_revision,
                learned_or_fallback="fallback",
                candidates=tuple(scored),
                shadow_routine_id=best.candidate.routine_id,
            )

        if not supported and not envelope:
            # Nothing is well supported and it is not safe to find out.
            return PolicyChoice(
                routine_id=fallback.routine_id,
                routine_name=fallback.routine_name,
                steps=fallback.steps,
                confidence=fallback.confidence,
                reason_codes=("insufficient_support_outside_envelope", *fallback.reason_codes),
                evidence_refs=(),
                policy_revision=self.policy_revision,
                learned_or_fallback="fallback",
                candidates=tuple(scored),
                shadow_routine_id=best.candidate.routine_id,
            )

        confidence = min(1.0, max(0.0, best.counts.posterior_lower()))
        return PolicyChoice(
            routine_id=best.candidate.routine_id,
            routine_name=best.candidate.name,
            steps=best.candidate.steps,
            confidence=confidence if supported else min(confidence, 0.4),
            reason_codes=tuple(
                dict.fromkeys(["learned_selection" if supported else "exploring", *reason_codes])
            ),
            evidence_refs=tuple(best.counts.evidence_refs[-8:]),
            policy_revision=self.policy_revision,
            learned_or_fallback="learned" if supported else "fallback",
            candidates=tuple(scored),
            shadow_routine_id=None,
        )
