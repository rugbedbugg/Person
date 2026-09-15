"""Skill-dependency planning by means-ends regression.

Learning should choose between valid strategies, not rediscover that a furnace
needs stone and that stone needs a pickaxe. The planner derives feasible
sequences from SkillSpec preconditions and effects; the policy then picks among
them using evidence.

The algorithm is deliberately plain. To satisfy an unmet condition it looks for
skills whose declared effects move that fact, recursively arranges for their
preconditions, and then continues with whatever the goal still needs. Every
returned plan is replayed through the declared effects, so a plan that the
contracts do not actually support never reaches the policy.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from person_skills import Condition, SkillRegistry, SkillSpec, skill_registry

ParameterValue = int | float | str | bool

MAX_PLAN_LENGTH = 8
MAX_DEPTH = 8
MAX_NODES = 20000
BRANCH_LIMIT = 3
PLANS_PER_OPTION = 3
PLANS_PER_CALL = 24

#: Emergency reflexes belong to the runtime. Two of them are also ordinary
#: intentions ("go home", "eat"), so those stay available to the planner.
PLANNABLE_EMERGENCY_SKILLS = frozenset({"return_home", "eat_to_target"})


@dataclass(frozen=True, slots=True)
class PlanStep:
    skill_id: str
    parameters: tuple[tuple[str, ParameterValue], ...]

    @property
    def parameter_map(self) -> dict[str, ParameterValue]:
        return dict(self.parameters)

    def label(self) -> str:
        scalars = ",".join(f"{key}={value}" for key, value in self.parameters)
        return f"{self.skill_id}({scalars})" if scalars else self.skill_id


@dataclass(frozen=True, slots=True)
class Plan:
    steps: tuple[PlanStep, ...]
    cost: float
    risk: float
    ticks: int

    @property
    def skill_ids(self) -> tuple[str, ...]:
        return tuple(step.skill_id for step in self.steps)

    def labels(self) -> tuple[str, ...]:
        return tuple(step.label() for step in self.steps)


def satisfied(state: Mapping[str, float], conditions: Iterable[Condition]) -> bool:
    return all(condition.holds(state) for condition in conditions)


def parameter_variants(spec: SkillSpec) -> list[dict[str, ParameterValue]]:
    """Default parameters, plus one larger variant for scalable skills.

    Two variants keep branching low while still giving the learner a real
    choice: gather a little often, or a lot once.
    """
    base = spec.default_parameters()
    variants = [base]
    for name in sorted({e.scales_with for e in spec.expected_effects if e.scales_with}):
        parameter = next((p for p in spec.parameters if p.name == name), None)
        default = base.get(name)
        if parameter is None or parameter.type != "integer" or not isinstance(default, int):
            continue
        larger = default * 4
        if parameter.maximum is not None:
            larger = int(min(larger, parameter.maximum))
        if larger > default:
            variants.append({**base, name: larger})
    return variants


def _apply(
    spec: SkillSpec, state: Mapping[str, float], parameters: Mapping[str, ParameterValue]
) -> dict[str, float]:
    successor = dict(state)
    for effect in spec.expected_effects:
        effect.apply(successor, parameters)
    return successor


def step_cost(spec: SkillSpec) -> float:
    """Cheap, safe and quick first. Risk dominates convenience."""
    return 1.0 + spec.risk * 4.0 + spec.max_ticks / 4000.0


def relevant_skills(goal: Sequence[Condition], specs: Sequence[SkillSpec]) -> list[SkillSpec]:
    """Backward relevance closure from the goal facts."""
    facts = {condition.fact for condition in goal}
    chosen: dict[str, SkillSpec] = {}
    changed = True
    while changed:
        changed = False
        for spec in specs:
            if spec.id in chosen:
                continue
            if not any(effect.fact in facts for effect in spec.expected_effects):
                continue
            chosen[spec.id] = spec
            changed = True
            for condition in spec.preconditions:
                if condition.fact not in facts:
                    facts.add(condition.fact)
    return list(chosen.values())


def _helps(spec: SkillSpec, condition: Condition) -> bool:
    for effect in spec.expected_effects:
        if effect.fact != condition.fact:
            continue
        if condition.op in {">=", ">", "=="} and effect.op in {"+=", "=", "max"}:
            return True
        if condition.op in {"<=", "<", "=="} and effect.op in {"-=", "="}:
            return True
    return False


class _Budget:
    __slots__ = ("nodes",)

    def __init__(self) -> None:
        self.nodes = 0

    def spend(self) -> bool:
        self.nodes += 1
        return self.nodes < MAX_NODES


def simulate(
    state: Mapping[str, float],
    steps: Sequence[PlanStep],
    *,
    registry: SkillRegistry | None = None,
) -> dict[str, float]:
    """Apply a plan's declared effects; used to explain and to check a plan."""
    registry = registry or skill_registry()
    current = dict(state)
    for step in steps:
        current = _apply(registry.get(step.skill_id), current, step.parameter_map)
    return current


def _feasible(
    state: Mapping[str, float], steps: Sequence[PlanStep], registry: SkillRegistry
) -> dict[str, float] | None:
    """Replay a plan through the contracts; None if a precondition fails."""
    current = dict(state)
    for step in steps:
        spec = registry.get(step.skill_id)
        if not satisfied(current, spec.preconditions):
            return None
        current = _apply(spec, current, step.parameter_map)
    return current


def _plan_cost(steps: Sequence[PlanStep], registry: SkillRegistry) -> float:
    return sum(step_cost(registry.get(step.skill_id)) for step in steps)


def _cheapest_first(
    plans: list[tuple[PlanStep, ...]], registry: SkillRegistry
) -> list[tuple[PlanStep, ...]]:
    """Cheapest first, so callers that truncate keep the simplest routes."""
    return sorted(plans, key=lambda steps: (_plan_cost(steps, registry), len(steps)))


def _regress(
    state: Mapping[str, float],
    goal: Sequence[Condition],
    specs: Sequence[SkillSpec],
    registry: SkillRegistry,
    depth: int,
    active: frozenset[str],
    budget: _Budget,
) -> list[tuple[PlanStep, ...]]:
    if satisfied(state, goal):
        return [()]
    if depth <= 0 or not budget.spend():
        return []
    unmet = next(condition for condition in goal if not condition.holds(state))

    # Order by whether one application of this skill would settle the condition
    # outright, then by cost. Without this the search happily chains a skill
    # that nudges the fact by one unit and never reaches a target of twenty.
    options: list[tuple[int, float, str, str, SkillSpec, dict[str, ParameterValue]]] = []
    for spec in specs:
        if spec.id in active or not _helps(spec, unmet):
            continue
        for parameters in parameter_variants(spec):
            projected = _apply(spec, state, parameters)
            if projected.get(unmet.fact, 0) == state.get(unmet.fact, 0):
                continue
            settles = 0 if unmet.holds(projected) else 1
            options.append(
                (
                    settles,
                    step_cost(spec),
                    spec.id,
                    str(sorted(parameters.items())),
                    spec,
                    parameters,
                )
            )
    options.sort(key=lambda option: option[:4])

    plans: list[tuple[PlanStep, ...]] = []
    for _settles, _cost, _id, _key, spec, parameters in options:
        # Each option gets its own small quota so that one cheap but elaborate
        # branch cannot crowd out a simpler alternative found later.
        from_option = 0
        prefixes = _regress(
            state, spec.preconditions, specs, registry, depth - 1, active | {spec.id}, budget
        )
        for prefix in prefixes[:BRANCH_LIMIT]:
            if from_option >= PLANS_PER_OPTION:
                break
            middle = _feasible(state, prefix, registry)
            if middle is None or not satisfied(middle, spec.preconditions):
                continue
            if len(prefix) + 1 > MAX_PLAN_LENGTH:
                continue
            step = PlanStep(spec.id, tuple(sorted(parameters.items())))
            after = _apply(spec, middle, parameters)
            suffixes = _regress(after, goal, specs, registry, depth - 1, active, budget)
            for suffix in suffixes[:BRANCH_LIMIT]:
                combined = (*prefix, step, *suffix)
                if len(combined) > MAX_PLAN_LENGTH:
                    continue
                plans.append(combined)
                from_option += 1
                if len(plans) >= PLANS_PER_CALL:
                    return _cheapest_first(plans, registry)
                if from_option >= PLANS_PER_OPTION:
                    break
    return _cheapest_first(plans, registry)


def _is_minimal(
    steps: Sequence[PlanStep],
    state: Mapping[str, float],
    goal: Sequence[Condition],
    registry: SkillRegistry,
) -> bool:
    """True when no single step can be dropped and the goal still reached.

    Without this, a plan with a harmless extra step looks like an alternative
    strategy, and the learner would spend real episodes distinguishing plans
    that differ only by noise.
    """
    if len(steps) <= 1:
        return True
    for index in range(len(steps)):
        reduced = (*steps[:index], *steps[index + 1 :])
        result = _feasible(state, reduced, registry)
        if result is not None and satisfied(result, goal):
            return False
    return True


def plan_for(
    state: Mapping[str, float],
    goal: Sequence[Condition],
    *,
    registry: SkillRegistry | None = None,
    limit: int = 6,
    max_depth: int = MAX_DEPTH,
    allowed_skills: Sequence[str] | None = None,
) -> list[Plan]:
    """Candidate plans that reach the goal, cheapest first.

    Only minimal, contract-feasible plans are returned, and plans made of the
    same steps in a different order are treated as one strategy.
    """
    registry = registry or skill_registry()
    available = [
        registry.get(skill_id)
        for skill_id in (allowed_skills or registry.ids)
        if not registry.get(skill_id).emergency or skill_id in PLANNABLE_EMERGENCY_SKILLS
    ]
    specs = relevant_skills(goal, available) or available
    start = dict(state)
    if satisfied(start, goal):
        return [Plan(steps=(), cost=0.0, risk=0.0, ticks=0)]

    raw = _regress(start, goal, specs, registry, max_depth, frozenset(), _Budget())
    scored: list[Plan] = []
    for steps in raw:
        result = _feasible(start, steps, registry)
        if result is None or not satisfied(result, goal):
            continue
        if not _is_minimal(steps, start, goal, registry):
            continue
        cost = sum(step_cost(registry.get(step.skill_id)) for step in steps)
        risk = sum(registry.get(step.skill_id).risk for step in steps)
        ticks = sum(registry.get(step.skill_id).max_ticks for step in steps)
        scored.append(Plan(steps=steps, cost=cost, risk=risk, ticks=ticks))

    unique: dict[tuple[str, ...], Plan] = {}
    unordered: set[tuple[str, ...]] = set()
    for plan in sorted(
        scored, key=lambda plan: (round(plan.cost, 6), len(plan.steps), plan.labels())
    ):
        signature = plan.labels()
        multiset = tuple(sorted(signature))
        if multiset in unordered or signature in unique:
            continue
        unordered.add(multiset)
        unique[signature] = plan
    return list(itertools.islice(unique.values(), limit))
