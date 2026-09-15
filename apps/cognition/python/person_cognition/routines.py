"""Routines: reusable compositions of skills.

A routine is an ordered composition whose elements are either a skill
invocation or another routine. Nesting is part of the data model from the
start, because the goal architecture is meant to support long-horizon work
later even though this milestone only composes survival sequences.

Routine identity is stable and content-derived, so evidence gathered before a
restart still refers to the same routine after one.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from person_planner import Plan, PlanStep
from person_policy import RoutineCandidate
from person_skills import SkillRegistry, skill_registry

MAX_EXPANSION_DEPTH = 4
ParameterValue = int | float | str | bool


@dataclass(frozen=True, slots=True)
class SkillStep:
    skill_id: str
    parameters: tuple[tuple[str, ParameterValue], ...] = ()

    @property
    def parameter_map(self) -> dict[str, ParameterValue]:
        return dict(self.parameters)

    def label(self) -> str:
        scalars = ",".join(f"{key}={value}" for key, value in self.parameters)
        return f"{self.skill_id}({scalars})" if scalars else self.skill_id


@dataclass(frozen=True, slots=True)
class RoutineRef:
    routine_id: str

    def label(self) -> str:
        return f"@{self.routine_id}"


RoutineElement = SkillStep | RoutineRef


@dataclass(frozen=True, slots=True)
class Routine:
    routine_id: str
    name: str
    goal_type: str
    elements: tuple[RoutineElement, ...]
    risk: float = 0.0
    cost: float = 0.0
    ticks: int = 0

    def labels(self) -> tuple[str, ...]:
        return tuple(element.label() for element in self.elements)


class RoutineExpansionError(ValueError):
    """A routine references a routine that is missing or nested too deeply."""


def routine_identifier(goal_type: str, labels: Sequence[str]) -> str:
    digest = hashlib.sha256(
        json.dumps({"goal": goal_type, "steps": list(labels)}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"r_{digest[:16]}"


def routine_name(goal_type: str, skills: Sequence[str]) -> str:
    head = "_".join(skills[:2]) if skills else "noop"
    name = f"{goal_type.lower()}__{head}"
    return name[:63]


def routine_from_plan(goal_type: str, plan: Plan) -> Routine:
    elements = tuple(SkillStep(step.skill_id, step.parameters) for step in plan.steps)
    labels = tuple(element.label() for element in elements)
    return Routine(
        routine_id=routine_identifier(goal_type, labels),
        name=routine_name(goal_type, [element.skill_id for element in elements]),
        goal_type=goal_type,
        elements=elements,
        risk=plan.risk,
        cost=plan.cost,
        ticks=plan.ticks,
    )


class RoutineLibrary:
    """Known routines, addressable by their stable identifiers."""

    def __init__(self, routines: Iterable[Routine] = ()) -> None:
        self._routines: dict[str, Routine] = {}
        for routine in routines:
            self.add(routine)

    def add(self, routine: Routine) -> Routine:
        self._routines[routine.routine_id] = routine
        return routine

    def get(self, routine_id: str) -> Routine | None:
        return self._routines.get(routine_id)

    def __contains__(self, routine_id: object) -> bool:
        return routine_id in self._routines

    def __len__(self) -> int:
        return len(self._routines)

    def ids(self) -> list[str]:
        return sorted(self._routines)

    def expand(self, routine: Routine, depth: int = 0) -> list[SkillStep]:
        """Flatten nested routines into the skill sequence that will run."""
        if depth > MAX_EXPANSION_DEPTH:
            raise RoutineExpansionError(
                f"Routine {routine.routine_id} nests deeper than {MAX_EXPANSION_DEPTH}"
            )
        steps: list[SkillStep] = []
        for element in routine.elements:
            if isinstance(element, SkillStep):
                steps.append(element)
                continue
            nested = self.get(element.routine_id)
            if nested is None:
                raise RoutineExpansionError(
                    f"Routine {routine.routine_id} references unknown routine {element.routine_id}"
                )
            steps.extend(self.expand(nested, depth + 1))
        return steps

    def to_json(self) -> list[dict[str, Any]]:
        return [
            {
                "routine_id": routine.routine_id,
                "name": routine.name,
                "goal_type": routine.goal_type,
                "elements": [
                    {"skill": element.skill_id, "parameters": dict(element.parameters)}
                    if isinstance(element, SkillStep)
                    else {"routine": element.routine_id}
                    for element in routine.elements
                ],
            }
            for routine in sorted(self._routines.values(), key=lambda routine: routine.routine_id)
        ]


def candidate_from_routine(
    routine: Routine,
    library: RoutineLibrary,
    state: Mapping[str, float],
    registry: SkillRegistry | None = None,
) -> RoutineCandidate:
    """Describe a routine for the policy, including whether it can start now."""
    registry = registry or skill_registry()
    steps = library.expand(routine)
    first = steps[0] if steps else None
    applicable = True
    if first is not None:
        spec = registry.get(first.skill_id)
        applicable = all(condition.holds(state) for condition in spec.preconditions)
    return RoutineCandidate(
        routine_id=routine.routine_id,
        name=routine.name,
        steps=tuple(step.skill_id for step in steps),
        step_labels=tuple(step.label() for step in steps),
        risk=routine.risk,
        cost=routine.cost,
        ticks=routine.ticks,
        applicable=applicable,
    )


def plan_step_of(step: SkillStep) -> PlanStep:
    return PlanStep(step.skill_id, step.parameters)
