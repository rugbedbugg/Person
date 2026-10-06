from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from person_protocol import EnvironmentNotFound, environment
from person_protocol.assets import package_asset_directory
from referencing import Registry, Resource

#: The configuration version written now. Version 2 is still read (ADR 0025).
CONFIG_VERSION = 3


class ConfigError(ValueError):
    def __init__(self, message: str, diagnostics: list[str] | None = None) -> None:
        self.diagnostics = diagnostics or []
        detail = "".join(f"\n  - {line}" for line in self.diagnostics)
        super().__init__(f"{message}{detail}")


def config_schema_path() -> Path:
    return package_asset_directory(__file__, "schema") / "person-config.schema.json"


def legacy_config_schema_path() -> Path:
    """The frozen configVersion 2 schema, kept only to read old documents."""
    return package_asset_directory(__file__, "schema") / "legacy" / "person-config-v2.schema.json"


@lru_cache(maxsize=4)
def _validator(kind: str) -> Draft202012Validator:
    """The core schema and the environment's own, together (ADR 0025)."""
    core = json.loads(config_schema_path().read_text(encoding="utf-8"))
    owned = environment(kind).config_schema
    registry = Registry().with_resources(
        [(core["$id"], Resource.from_contents(core)), (owned["$id"], Resource.from_contents(owned))]
    )
    composite = {
        "$schema": core["$schema"],
        "allOf": [{"$ref": core["$id"]}, {"$ref": owned["$id"]}],
        "unevaluatedProperties": False,
    }
    return Draft202012Validator(composite, registry=registry)


@lru_cache(maxsize=1)
def _legacy_validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(legacy_config_schema_path().read_text("utf-8")))


def validate_config_document(document: Any) -> dict[str, Any]:
    """Validate a version 3 document, or read a version 2 one against its frozen schema.

    Cognition needs nothing from a configuration that the version 2 format
    expressed differently: its experience stream arrives in SessionHello. So a
    version 2 document is checked against the schema it was written for, and
    read as it is; it is never rewritten.
    """
    if not isinstance(document, dict):
        raise ConfigError("Configuration must be a table")
    if document.get("configVersion") == 2:
        validator = _legacy_validator()
    else:
        kind = (
            document.get("environment", {}).get("kind")
            if isinstance(document.get("environment"), dict)
            else None
        )
        if not isinstance(kind, str):
            raise ConfigError(
                "Configuration does not match the schema", ["/environment/kind is required"]
            )
        try:
            validator = _validator(kind)
        except EnvironmentNotFound as error:
            raise ConfigError("Configuration names an unknown environment", [str(error)]) from error
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    if errors:
        raise ConfigError(
            "Configuration does not match the schema",
            ["/" + "/".join(str(p) for p in e.absolute_path) + " " + e.message for e in errors],
        )
    return document


@dataclass(frozen=True, slots=True)
class CognitionSettings:
    """The subset of configuration the cognition process legitimately owns."""

    person_id: str
    world_id: str
    learning_mode: str
    evidence_directory: Path
    output_directory: Path
    snapshot_every_events: int
    exploration_bonus: float
    minimum_support: int
    rng_seed: int | None
    #: How far affect is switched on (ADR 0013). Cognition's alone: the
    #: runtime neither reads nor receives it.
    affect_mode: str = "active"
    #: ADR 0014: interoceptive affect. Off is a frozen R1.5 research baseline.
    interoception: bool = True
    #: ADR 0017: the name and designation a new continuity root is founded with.
    identity_name: str | None = None
    identity_designation: str | None = None
    #: ADR 0025: which environment, and which of its embodiments. None when
    #: read from a version 2 document, which did not separate them; the
    #: runtime's SessionHello is authoritative either way.
    environment_kind: str | None = None
    embodiment_kind: str | None = None
    #: ADR 0020/0021: off (default), record_only or active. Cognition's alone.
    deliberation_mode: str = "off"
    #: Which model answers; only `scripted` exists before C7 chooses one.
    deliberation_backend: str | None = None
    deliberation_script: Path | None = None
    #: ADR 0022: off (default) or record_only.
    deliberation_habits: str = "off"
    #: ADR 0023: affective metareasoning, off, record_only or active.
    deliberation_affect_arbitration: str = "off"

    def cross_check(
        self,
        *,
        learning_mode: str,
        evidence_directory: str,
        environment_kind: str | None = None,
        embodiment_kind: str | None = None,
    ) -> None:
        """Fail closed when the runtime disagrees with the file we read."""
        for name, runtime_says, file_says in (
            ("environment", environment_kind, self.environment_kind),
            ("embodiment", embodiment_kind, self.embodiment_kind),
        ):
            if runtime_says is not None and file_says is not None and runtime_says != file_says:
                raise ConfigError(
                    f"Runtime and cognition disagree about the {name}",
                    [f"runtime says {runtime_says!r}, configuration says {file_says!r}"],
                )
        if learning_mode != self.learning_mode:
            raise ConfigError(
                "Runtime and cognition disagree about the learning mode",
                [f"runtime says {learning_mode!r}, configuration says {self.learning_mode!r}"],
            )
        if Path(evidence_directory).resolve() != self.evidence_directory.resolve():
            raise ConfigError(
                "Runtime and cognition disagree about the evidence directory",
                [
                    f"runtime says {evidence_directory!r}, "
                    f"configuration says {self.evidence_directory}"
                ],
            )


def load_cognition_settings(filename: str | Path) -> CognitionSettings:
    path = Path(filename).resolve()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"Cannot read configuration {path}: {error}") from error
    try:
        document = json.loads(text) if path.suffix == ".json" else tomllib.loads(text)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"{path} could not be parsed: {error}") from error
    validate_config_document(document)
    base = path.parent
    runtime = document["runtime"]
    learning = document["learning"]
    output_directory = (base / runtime["outputDirectory"]).resolve()
    evidence = learning.get("evidenceDirectory")
    evidence_directory = (base / evidence).resolve() if evidence else output_directory / "evidence"
    return CognitionSettings(
        person_id=document["personId"],
        world_id=document["worldId"],
        learning_mode=learning["mode"],
        evidence_directory=evidence_directory,
        output_directory=output_directory,
        snapshot_every_events=learning.get("snapshotEveryEvents", 50),
        exploration_bonus=learning.get("explorationBonus", 0.15),
        minimum_support=learning.get("minimumSupport", 3),
        rng_seed=runtime.get("rngSeed"),
        affect_mode=document.get("affect", {}).get("mode", "active"),
        interoception=document.get("affect", {}).get("interoception", "on") == "on",
        identity_name=document.get("identity", {}).get("name"),
        identity_designation=document.get("identity", {}).get("designation"),
        environment_kind=(
            str(document["environment"]["kind"]) if document["configVersion"] >= 3 else None
        ),
        embodiment_kind=str(runtime["embodiment"]) if document["configVersion"] >= 3 else None,
        deliberation_mode=document.get("deliberation", {}).get("mode", "off"),
        deliberation_backend=document.get("deliberation", {}).get("backend"),
        deliberation_habits=document.get("deliberation", {}).get("habits", "off"),
        deliberation_affect_arbitration=document.get("deliberation", {}).get(
            "affectArbitration", "off"
        ),
        deliberation_script=(
            (base / document["deliberation"]["scriptedAnswers"]).resolve()
            if document.get("deliberation", {}).get("scriptedAnswers")
            else None
        ),
    )
