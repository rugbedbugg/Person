"""What a failed plan was missing: capability, or only evidence.

The planner used to treat every failure the same way. A shelter needs wood,
wood needs a tree in view, no tree is in view, so no plan exists and the goal
was blocked. That conflates two very different situations: Person cannot build
a shelter, and Person cannot see a tree from where it is standing and which way
it is facing.

This module separates them with a counterfactual that never touches the real
state: had the missing percepts been there, would a plan exist? If so, the
failure is for want of evidence, and the evidence is named. Whether to go and
look, and how hard, is decided by the caller.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from person_skills import Condition, SkillRegistry, skill_registry

from .search import plan_for

#: Facts only current perception establishes. No skill produces them, a test
#: asserts that, and a zero means "not seen" rather than "not there".
EVIDENCE_FACTS: frozenset[str] = frozenset(
    {
        "reachable_wood",
        "reachable_stone",
        "reachable_coal",
        "reachable_plant_food",
        "reachable_animal",
        "permitted_container_nearby",
    }
)

#: How many hypothetical plans to read the missing evidence from.
HYPOTHESIS_PLANS = 4


def evidence_needed(
    state: Mapping[str, float],
    goal: Sequence[Condition],
    *,
    registry: SkillRegistry | None = None,
) -> tuple[str, ...]:
    """The evidence facts whose absence from view is all that stands in the way.

    Empty when a plan already exists, and empty when no amount of seeing would
    help, because then looking is not the answer.
    """
    registry = registry or skill_registry()
    if plan_for(state, goal, registry=registry, limit=1):
        return ()
    unseen = sorted(fact for fact in EVIDENCE_FACTS if state.get(fact, 0.0) < 1)
    if not unseen:
        return ()
    imagined = {**state, **{fact: 1.0 for fact in unseen}}
    needed: set[str] = set()
    for plan in plan_for(imagined, goal, registry=registry, limit=HYPOTHESIS_PLANS):
        for step in plan.steps:
            for condition in registry.get(step.skill_id).preconditions:
                if condition.fact in unseen:
                    needed.add(condition.fact)
    return tuple(sorted(needed))
