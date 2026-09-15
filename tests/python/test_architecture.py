"""Architecture rules the cognition side must keep, enforced as tests."""

from __future__ import annotations

import ast
import importlib.metadata
import json
import re
import tomllib
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
COGNITION_ROOTS = [
    REPOSITORY / "packages/protocol/python",
    REPOSITORY / "packages/skills/python",
    REPOSITORY / "packages/config/python",
    REPOSITORY / "packages/planner/python",
    REPOSITORY / "packages/policy/python",
    REPOSITORY / "packages/persistence/python",
    REPOSITORY / "apps/cognition/python",
]

FORBIDDEN_DEPENDENCIES = {
    "torch",
    "tensorflow",
    "jax",
    "keras",
    "redis",
    "kafka",
    "kafka-python",
    "psycopg2",
    "sqlalchemy",
    "javascript",
    "mineflayer",
}


def python_sources() -> list[Path]:
    files: list[Path] = []
    for root in COGNITION_ROOTS:
        files.extend(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    return files


def test_cognition_declares_no_heavyweight_or_minecraft_dependencies() -> None:
    manifests = [REPOSITORY / "pyproject.toml"] + [
        path / "pyproject.toml" for path in (REPOSITORY / "packages").iterdir() if path.is_dir()
    ]
    manifests.append(REPOSITORY / "apps/cognition/pyproject.toml")
    for manifest in manifests:
        document = tomllib.loads(manifest.read_text(encoding="utf-8"))
        declared = document.get("project", {}).get("dependencies", [])
        groups = document.get("dependency-groups", {})
        for requirement in [*declared, *(item for group in groups.values() for item in group)]:
            name = re.split(r"[<>=!\[ ]", requirement, maxsplit=1)[0].strip().lower()
            assert name not in FORBIDDEN_DEPENDENCIES, f"{manifest} declares {name}"


def test_the_installed_environment_contains_no_learning_frameworks() -> None:
    installed = {dist.metadata["Name"].lower() for dist in importlib.metadata.distributions()}
    assert FORBIDDEN_DEPENDENCIES.isdisjoint(installed), sorted(FORBIDDEN_DEPENDENCIES & installed)


def test_cognition_never_imports_a_minecraft_client() -> None:
    for path in python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                root = name.split(".")[0]
                assert root not in {"mineflayer", "javascript", "socket", "socketserver"}, (
                    f"{path.relative_to(REPOSITORY)} imports {name}"
                )


def test_cognition_has_no_raw_movement_or_block_primitives() -> None:
    """Cognition may name skills. It may not name Minecraft mechanics."""
    forbidden = re.compile(
        r"\b(move_forward|turn_left|turn_right|set_block|break_block|place_block|"
        r"send_chat|bot\.chat|/tp |/give |/gamemode )",
    )
    for path in python_sources():
        source = path.read_text(encoding="utf-8")
        match = forbidden.search(source)
        assert match is None, f"{path.relative_to(REPOSITORY)} contains {match.group(0)!r}"


def test_cognition_never_evaluates_generated_code() -> None:
    for path in python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"eval", "exec", "compile"}, (
                    f"{path.relative_to(REPOSITORY)} calls {node.func.id}"
                )


def test_the_evidence_journal_is_append_only() -> None:
    from person_persistence import EvidenceJournal

    source = (REPOSITORY / "packages/persistence/python/person_persistence/journal.py").read_text(
        encoding="utf-8"
    )
    assert '"a"' in source, "the journal must open its segments in append mode"
    assert '"w"' not in source, "the journal must never open a segment for writing"
    for forbidden in ("update", "delete", "remove", "rewrite", "truncate"):
        assert forbidden not in dir(EvidenceJournal)


def test_learning_is_off_by_default_everywhere() -> None:
    for path in (REPOSITORY / "examples").glob("*.toml"):
        document = tomllib.loads(path.read_text(encoding="utf-8"))
        assert document["learning"]["mode"] == "off", path.name
    schema = json.loads(
        (REPOSITORY / "packages/config/schema/person-config.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["properties"]["learning"]["required"] == ["mode"], (
        "the learning mode must be stated explicitly rather than defaulted on"
    )


def test_future_providers_refuse_to_pretend_they_work() -> None:
    from person_cognition.future_providers import FUTURE_PROVIDERS, NotYetImplemented

    assert set(FUTURE_PROVIDERS) == {
        "MemoryProvider",
        "WorldModelProvider",
        "AffectProvider",
        "LanguageProvider",
        "SocialProvider",
        "ProjectProvider",
        "ExplorationProvider",
    }
    for _name, factory in FUTURE_PROVIDERS.items():
        provider = factory()
        method = next(
            attribute
            for attribute in dir(provider)
            if not attribute.startswith("_") and callable(getattr(provider, attribute))
        )
        with pytest.raises(NotYetImplemented):
            getattr(provider, method)(*[{}] * _arity(provider, method))


def _arity(provider: object, method: str) -> int:
    import inspect

    signature = inspect.signature(getattr(provider, method))
    return len(signature.parameters)


def test_the_protocol_forbids_a_free_form_command_field() -> None:
    schema = json.loads(
        (REPOSITORY / "packages/protocol/schemas/skill-invocation.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["unevaluatedProperties"] is False
    for forbidden in ("command", "chat", "script", "code", "packet"):
        assert forbidden not in schema["properties"]


def test_no_required_scope_placeholders_remain_in_cognition() -> None:
    allowed = {"future_providers.py"}
    marker = re.compile(r"TODO|FIXME|NotImplementedError")
    for path in python_sources():
        if path.name in allowed:
            continue
        source = path.read_text(encoding="utf-8")
        match = marker.search(source)
        assert match is None, f"{path.relative_to(REPOSITORY)} contains {match.group(0)}"
