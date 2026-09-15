"""Load and validate the canonical SkillSpec files.

Nothing in this module executes anything. A SkillSpec is the contract the
planner reasons over and the Node runtime enforces; the executable half lives
behind the trust boundary in the Node runtime.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, NoReturn

from jsonschema import Draft202012Validator
from person_protocol.assets import package_asset_directory

ConditionOp = Literal[">=", "<=", "==", ">", "<"]
EffectOp = Literal["+=", "-=", "=", "max"]
ParameterValue = int | float | str | bool


class SkillSpecError(ValueError):
    """A skill spec is missing, malformed, or used with invalid parameters."""


def spec_directory() -> Path:
    return package_asset_directory(__file__, "specs")


@dataclass(frozen=True, slots=True)
class Condition:
    fact: str
    op: ConditionOp
    value: float

    def holds(self, state: Mapping[str, float]) -> bool:
        current = state.get(self.fact, 0)
        match self.op:
            case ">=":
                return current >= self.value
            case "<=":
                return current <= self.value
            case "==":
                return current == self.value
            case ">":
                return current > self.value
            case "<":
                return current < self.value
        raise SkillSpecError(f"Unknown condition operator {self.op}")


@dataclass(frozen=True, slots=True)
class Effect:
    fact: str
    op: EffectOp
    value: float
    scales_with: str | None = None

    def magnitude(self, parameters: Mapping[str, ParameterValue]) -> float:
        if self.scales_with is not None:
            supplied = parameters.get(self.scales_with)
            if isinstance(supplied, int | float) and not isinstance(supplied, bool):
                return float(supplied)
        return self.value

    def apply(self, state: dict[str, float], parameters: Mapping[str, ParameterValue]) -> None:
        magnitude = self.magnitude(parameters)
        current = state.get(self.fact, 0)
        match self.op:
            case "+=":
                state[self.fact] = current + magnitude
            case "-=":
                state[self.fact] = max(0, current - magnitude)
            case "=":
                state[self.fact] = magnitude
            case "max":
                state[self.fact] = max(current, magnitude)
            case _:
                raise SkillSpecError(f"Unknown effect operator {self.op}")


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    name: str
    type: str
    default: ParameterValue
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] | None = None

    def check(self, skill_id: str, value: ParameterValue) -> ParameterValue:
        def fail(reason: str) -> NoReturn:
            raise SkillSpecError(f"{skill_id}.{self.name} {reason}")

        if self.type == "boolean":
            if not isinstance(value, bool):
                fail("must be a boolean")
            return value
        if self.type == "string":
            if not isinstance(value, str):
                fail("must be a string")
            if self.choices is not None and value not in self.choices:
                fail(f"must be one of {', '.join(self.choices)}")
            return value
        if isinstance(value, bool) or not isinstance(value, int | float):
            fail("must be a number")
        if self.type == "integer" and not isinstance(value, int):
            fail("must be an integer")
        if self.minimum is not None and value < self.minimum:
            fail(f"must be at least {self.minimum:g}")
        if self.maximum is not None and value > self.maximum:
            fail(f"must be at most {self.maximum:g}")
        return value


@dataclass(frozen=True, slots=True)
class SkillSpec:
    id: str
    version: int
    category: str
    summary: str
    parameters: tuple[ParameterSpec, ...]
    preconditions: tuple[Condition, ...]
    expected_effects: tuple[Effect, ...]
    possible_failures: tuple[str, ...]
    required_permissions: tuple[str, ...]
    max_ticks: int
    max_distance: int
    min_health: float
    interruption_policy: str
    completion_evidence: tuple[str, ...]
    risk: float
    emergency: bool

    def applicable(self, state: Mapping[str, float]) -> bool:
        return all(condition.holds(state) for condition in self.preconditions)

    def default_parameters(self) -> dict[str, ParameterValue]:
        return {parameter.name: parameter.default for parameter in self.parameters}

    def resolve_parameters(
        self, supplied: Mapping[str, ParameterValue]
    ) -> dict[str, ParameterValue]:
        known = {parameter.name: parameter for parameter in self.parameters}
        for key in supplied:
            if key not in known:
                raise SkillSpecError(f"{self.id} does not accept the parameter {key}")
        return {
            name: parameter.check(self.id, supplied.get(name, parameter.default))
            for name, parameter in known.items()
        }

    def limits(self) -> dict[str, float]:
        return {
            "maxTicks": self.max_ticks,
            "maxDistance": self.max_distance,
            "minHealth": self.min_health,
        }


def _spec_from_json(document: dict[str, Any]) -> SkillSpec:
    parameters = tuple(
        ParameterSpec(
            name=name,
            type=body["type"],
            default=body["default"],
            minimum=body.get("minimum"),
            maximum=body.get("maximum"),
            choices=tuple(body["enum"]) if "enum" in body else None,
        )
        for name, body in sorted(document["parameters"].items())
    )
    return SkillSpec(
        id=document["id"],
        version=document["version"],
        category=document["category"],
        summary=document["summary"],
        parameters=parameters,
        preconditions=tuple(
            Condition(c["fact"], c["op"], c["value"]) for c in document["preconditions"]
        ),
        expected_effects=tuple(
            Effect(e["fact"], e["op"], e["value"], e.get("scalesWith"))
            for e in document["expectedEffects"]
        ),
        possible_failures=tuple(document["possibleFailures"]),
        required_permissions=tuple(document["requiredPermissions"]),
        max_ticks=document["costLimits"]["maxTicks"],
        max_distance=document["costLimits"]["maxDistance"],
        min_health=document["costLimits"]["minHealth"],
        interruption_policy=document["interruptionPolicy"],
        completion_evidence=tuple(document["completionEvidence"]),
        risk=document["risk"],
        emergency=document["emergency"],
    )


class SkillRegistry:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or spec_directory()
        schema = json.loads((self.directory / "skill-spec.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        self.facts: dict[str, str] = json.loads(
            (self.directory / "facts.json").read_text(encoding="utf-8")
        )["facts"]
        specs: dict[str, SkillSpec] = {}
        digest = hashlib.sha256()
        for path in sorted(self.directory.glob("*.json")):
            if path.name in {"facts.json", "skill-spec.schema.json"}:
                continue
            raw = path.read_text(encoding="utf-8")
            document = json.loads(raw)
            errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
            if errors:
                detail = "; ".join(f"{list(e.absolute_path)} {e.message}" for e in errors)
                raise SkillSpecError(f"{path.name} is not a valid SkillSpec: {detail}")
            if document["id"] != path.stem:
                raise SkillSpecError(f"{path.name} declares mismatched skill id {document['id']}")
            spec = _spec_from_json(document)
            for condition in spec.preconditions:
                if condition.fact not in self.facts:
                    raise SkillSpecError(
                        f"{spec.id} precondition uses unknown fact {condition.fact}"
                    )
            parameter_names = {parameter.name for parameter in spec.parameters}
            for effect in spec.expected_effects:
                if effect.fact not in self.facts:
                    raise SkillSpecError(f"{spec.id} effect uses unknown fact {effect.fact}")
                if effect.scales_with is not None and effect.scales_with not in parameter_names:
                    raise SkillSpecError(
                        f"{spec.id} effect scales with unknown parameter {effect.scales_with}"
                    )
            specs[spec.id] = spec
            digest.update(f"{path.name}:{raw}".encode())
        if not specs:
            raise SkillSpecError(f"No skill specs found in {self.directory}")
        self._specs = specs
        self.revision = digest.hexdigest()[:16]

    @property
    def ids(self) -> list[str]:
        return sorted(self._specs)

    def __contains__(self, skill_id: object) -> bool:
        return skill_id in self._specs

    def __iter__(self) -> Any:
        return iter(self._specs.values())

    def get(self, skill_id: str) -> SkillSpec:
        try:
            return self._specs[skill_id]
        except KeyError as error:
            raise SkillSpecError(f"Unknown skill {skill_id}") from error

    def by_category(self, category: str) -> list[SkillSpec]:
        return [spec for spec in self._specs.values() if spec.category == category]


@lru_cache(maxsize=1)
def skill_registry() -> SkillRegistry:
    return SkillRegistry()
