from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from person_protocol.assets import package_asset_directory


class ConfigError(ValueError):
    def __init__(self, message: str, diagnostics: list[str] | None = None) -> None:
        self.diagnostics = diagnostics or []
        detail = "".join(f"\n  - {line}" for line in self.diagnostics)
        super().__init__(f"{message}{detail}")


def config_schema_path() -> Path:
    return package_asset_directory(__file__, "schema") / "person-config.schema.json"


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(config_schema_path().read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_config_document(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ConfigError("Configuration must be a table")
    errors = sorted(_validator().iter_errors(document), key=lambda e: list(e.absolute_path))
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

    def cross_check(self, *, learning_mode: str, evidence_directory: str) -> None:
        """Fail closed when the runtime disagrees with the file we read."""
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
    )
