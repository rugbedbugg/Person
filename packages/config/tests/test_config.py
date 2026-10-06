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


# ------------------------------------------------------------ affect mode


def _with_affect(tmp_path: Path, affect: dict[str, object] | None) -> Path:
    document = tomllib.loads((REPOSITORY / "examples/fixture.toml").read_text(encoding="utf-8"))
    document.pop("affect", None)
    if affect is not None:
        document["affect"] = affect
    document["runtime"]["outputDirectory"] = str(tmp_path)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_the_affect_mode_is_read_from_the_configuration(tmp_path: Path) -> None:
    for mode in ("off", "record_only", "active"):
        settings = load_cognition_settings(_with_affect(tmp_path, {"mode": mode}))
        assert settings.affect_mode == mode


def test_an_unstated_affect_mode_keeps_the_behaviour_affect_has_had(tmp_path: Path) -> None:
    assert load_cognition_settings(_with_affect(tmp_path, None)).affect_mode == "active"


def test_an_unknown_affect_mode_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_cognition_settings(_with_affect(tmp_path, {"mode": "muted"}))
    with pytest.raises(ConfigError):
        load_cognition_settings(_with_affect(tmp_path, {"mode": "off", "gain": 2}))


def test_every_shipped_configuration_states_its_affect_mode() -> None:
    for path in sorted((REPOSITORY / "examples").glob("*.toml")):
        document = tomllib.loads(path.read_text(encoding="utf-8"))
        assert document.get("affect", {}).get("mode") == "active", path.name


# ------------------------------------------------- environments (ADR 0025)


def test_the_core_schema_names_no_environment_and_the_environment_owns_its_sections() -> None:
    core = json.loads(
        (REPOSITORY / "packages/config/schema/person-config.schema.json").read_text("utf-8")
    )
    text = json.dumps(core).lower()
    for word in ("minecraft", "mineflayer", "peaceful", "difficulty", "villager", "server"):
        assert word not in text, f"the core configuration schema names {word}"
    for owned in ("world", "permissions", "server", "bot", "authorization"):
        assert owned not in core["properties"], f"{owned} is an environment's section"


def test_an_unknown_environment_is_refused(tmp_path: Path) -> None:
    document = tomllib.loads((REPOSITORY / "examples/fixture.toml").read_text(encoding="utf-8"))
    document["environment"]["kind"] = "crafter"
    with pytest.raises(ConfigError, match="unknown environment"):
        validate_config_document(document)


def test_difficulty_belongs_to_the_mineflayer_body_only() -> None:
    document = tomllib.loads((REPOSITORY / "examples/fixture.toml").read_text(encoding="utf-8"))
    document["environment"]["difficulty"] = "normal"
    with pytest.raises(ConfigError):
        validate_config_document(document)
    lan = tomllib.loads((REPOSITORY / "examples/minecraft-lan.toml").read_text(encoding="utf-8"))
    validate_config_document(lan)
    del lan["environment"]["difficulty"]
    with pytest.raises(ConfigError):
        validate_config_document(lan)


def test_a_version_2_configuration_is_still_read_never_rewritten() -> None:
    legacy = REPOSITORY / "docs/evidence/dedicated-server/2026-09-29/person-dedicated.toml"
    before = legacy.read_bytes()
    settings = load_cognition_settings(legacy)
    assert settings.environment_kind is None, "version 2 did not separate the environment"
    assert legacy.read_bytes() == before


def test_cognition_fails_closed_on_another_environment_or_body() -> None:
    settings = load_cognition_settings(REPOSITORY / "examples/fixture.toml")
    with pytest.raises(ConfigError, match="embodiment"):
        settings.cross_check(
            learning_mode="off",
            evidence_directory=str(settings.evidence_directory),
            environment_kind="minecraft",
            embodiment_kind="mineflayer",
        )
