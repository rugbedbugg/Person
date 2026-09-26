"""Architecture rules the cognition side must keep, enforced as tests."""

from __future__ import annotations

import ast
import importlib.metadata
import io
import json
import re
import tokenize
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

    # Memory left this list when it was built (ADR 0007); the rest remain.
    assert set(FUTURE_PROVIDERS) == {
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


def test_memory_cannot_read_the_journal_for_itself() -> None:
    # The memory store is fed events by the evidence store's replay, and reads
    # only the ones Person encoded. If the memory package could open the
    # journal it could recall anything in it (ADR 0003 rule 1, ADR 0007).
    forbidden = {"EvidenceJournal", "EvidenceStore", "SnapshotStore", "open", "read_text"}
    package = REPOSITORY / "apps/cognition/python/person_cognition/memory"
    for path in package.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            name = (
                node.id
                if isinstance(node, ast.Name)
                else node.attr
                if isinstance(node, ast.Attribute)
                else node.name
                if isinstance(node, ast.alias)
                else None
            )
            assert name not in forbidden, f"{path.relative_to(REPOSITORY)} uses {name}"


def test_no_arbitrary_query_interface_to_memory_exists() -> None:
    for path in python_sources():
        source = path.read_text(encoding="utf-8")
        assert "def retrieve(" not in source, f"{path.relative_to(REPOSITORY)} defines retrieve"


def test_the_spatial_model_reads_no_absolute_or_ledger_state() -> None:
    # Person's sense of place is integrated from felt motion (ADR 0008). The
    # package must not be able to see a coordinate, a heading, the runtime's
    # home distance, or the journal, whatever the observation happens to hold.
    cognition = REPOSITORY / "apps/cognition/python/person_cognition"
    # Projects are anchored to places in the same model and are held to the
    # same rule (Phase D).
    sources = [
        *(cognition / "spatial").rglob("*.py"),
        cognition / "projects.py",
        cognition / "affect.py",
        # Learned effect beliefs come from felt outcomes only (ADR 0011).
        cognition / "effect_learning.py",
        # Hypotheses and experiments speak only Person's vocabulary (ADR
        # 0012). The quarantine module is the one place that names what is
        # privileged, so that the gate can recognise it.
        *(
            path
            for path in (cognition / "hypotheses").rglob("*.py")
            if path.name != "quarantine.py"
        ),
    ]
    forbidden = {
        "homeDistance",
        "yaw",
        "pitch",
        "position",
        "WorldSnapshot",
        "EvidenceJournal",
        "EvidenceStore",
        "SnapshotStore",
        "open",
        "read_text",
    }
    for path in sources:
        source = path.read_text(encoding="utf-8")
        # Identifiers and string literals, which is where a field would be
        # read; prose in comments and docstrings may name what is excluded.
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.NAME:
                words = {token.string}
            elif token.type == tokenize.STRING and len(token.string) < 40:
                words = set(re.findall(r"\w+", token.string))
            else:
                continue
            leaked = words & forbidden
            assert not leaked, f"{path.relative_to(REPOSITORY)} uses {sorted(leaked)}"


def test_the_loop_reaches_places_only_through_its_spatial_sense() -> None:
    source = (REPOSITORY / "apps/cognition/python/person_cognition/loop.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("spatial_map.places(", "spatial_map._places", ".estimate = "):
        assert forbidden not in source, f"the loop must not edit the map: {forbidden}"


def test_no_cognition_code_reads_a_home_distance() -> None:
    # C8: the observation carries no distance to home, and nothing on the
    # cognition side may look for one. Whether Person is home is its belief.
    for path in python_sources():
        source = path.read_text(encoding="utf-8")
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            # A field lookup is a short literal; prose may name what is gone.
            short = token.type == tokenize.STRING and len(token.string) < 40
            if short and "homeDistance" in token.string:
                raise AssertionError(f"{path.relative_to(REPOSITORY)} reads homeDistance")


HYPOTHESES = REPOSITORY / "apps/cognition/python/person_cognition/hypotheses"


def _code(path: Path) -> str:
    """Source without comments and docstrings: prose may name what is excluded."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(body, list)
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body[0] = ast.Pass()
    return ast.unparse(tree)


def test_experiments_act_only_through_the_ordinary_goal_boundary() -> None:
    # An experiment is a goal. Nothing in the package can emit a message,
    # touch a body or reach the runtime; the loop sends what the planner and
    # policy chose, as for any goal.
    for path in HYPOTHESES.rglob("*.py"):
        code = _code(path)
        for forbidden in (
            "_send",
            "encode_frame",
            "SkillInvocation",
            "embodiment",
            "Embodiment",
            "mineflayer",
            "subprocess",
            "socket",
        ):
            assert forbidden not in code, f"{path.name} uses {forbidden}"


def test_a_hypothesis_holds_no_executable_predicate() -> None:
    tree = ast.parse((HYPOTHESES / "hypothesis.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        assert not isinstance(node, ast.Lambda), "no predicate hides in a hypothesis"
        if isinstance(node, ast.AnnAssign):
            assert "Callable" not in ast.unparse(node.annotation)


def test_a_proposer_sees_only_the_bounded_reasoning_context() -> None:
    generation = _code(HYPOTHESES / "generation.py")
    # The language model's whole input is the context, serialised.
    calls = re.findall(r"self\._complete\((.*)\)", generation)
    assert calls == ["json.dumps(context.to_json(), sort_keys=True)"], calls
    assert re.search(r"def propose\(self, context: ReasoningContext\)", generation)


def test_proposal_text_cannot_move_a_belief() -> None:
    # The gate builds a hypothesis with empty evidence; only journalled
    # trials, through the book, ever update one.
    generation = _code(HYPOTHESES / "generation.py")
    for forbidden in (".updated(", "Cell(", "cells=", "followed", "lifecycle="):
        assert forbidden not in generation, forbidden
    book = _code(HYPOTHESES / "book.py")
    assert book.count(".updated(") == 1


def test_no_hypothesis_is_ever_declared_knowledge() -> None:
    pattern = re.compile(r"\bknowledge\w*\s*=|\bknown\s*=\s*True|standing\s*=\s*['\"]true")
    sources = [
        *HYPOTHESES.rglob("*.py"),
        REPOSITORY / "apps/cognition/python/person_cognition/loop.py",
    ]
    for path in sources:
        match = pattern.search(_code(path))
        assert match is None, f"{path.name}: {match.group(0) if match else ''}"
