"""Configuration, legacy migration, and refusal of V1 learning checkpoints."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from person_config import (
    LEGACY_CHECKPOINT_DIAGNOSTIC,
    ConfigError,
    is_legacy_learning_checkpoint,
    load_cognition_settings,
    validate_config_document,
)
from person_config.migrate import LegacyCheckpointError, assert_not_legacy_checkpoint

REPOSITORY = Path(__file__).resolve().parents[3]


def test_the_example_configuration_loads_with_learning_off() -> None:
    settings = load_cognition_settings(REPOSITORY / "examples/fixture.toml")
    assert settings.person_id == "ada"
    assert settings.learning_mode == "off"
    assert settings.rng_seed is not None, "fixture runs record their seed"


def test_cognition_fails_closed_when_the_runtime_disagrees() -> None:
    settings = load_cognition_settings(REPOSITORY / "examples/fixture.toml")
    settings.cross_check(learning_mode="off", evidence_directory=str(settings.evidence_directory))
    with pytest.raises(ConfigError, match="learning mode"):
        settings.cross_check(
            learning_mode="supervised", evidence_directory=str(settings.evidence_directory)
        )
    with pytest.raises(ConfigError, match="evidence directory"):
        settings.cross_check(learning_mode="off", evidence_directory="/somewhere/else")


def test_schema_rejects_a_deposit_into_pre_existing_containers() -> None:
    document = tomllib.loads((REPOSITORY / "examples/fixture.toml").read_text(encoding="utf-8"))
    validate_config_document(document)
    document["permissions"]["containers"]["existing"]["deposit"] = True
    with pytest.raises(ConfigError, match="deposit"):
        validate_config_document(document)


def test_a_legacy_q_learning_checkpoint_is_recognised_and_refused() -> None:
    document = json.loads(
        (REPOSITORY / "examples/legacy-q-checkpoint.json").read_text(encoding="utf-8")
    )
    assert is_legacy_learning_checkpoint(document)
    with pytest.raises(LegacyCheckpointError) as error:
        assert_not_legacy_checkpoint(document)
    message = str(error.value)
    assert message == LEGACY_CHECKPOINT_DIAGNOSTIC
    assert "have not been modified" in message or "has not been modified" in message
    assert "demonstration" in message


def test_a_person_configuration_is_not_mistaken_for_a_checkpoint() -> None:
    document = tomllib.loads((REPOSITORY / "examples/fixture.toml").read_text(encoding="utf-8"))
    assert not is_legacy_learning_checkpoint(document)
