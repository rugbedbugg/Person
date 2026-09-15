"""Protocol contract tests, including Node/Python compatibility."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from person_protocol import (
    MESSAGE_TYPES,
    PROTOCOL_VERSION,
    FrameError,
    LineReader,
    ProtocolError,
    ProtocolValidator,
    SessionIdentity,
    decode_frame,
    encode_frame,
    envelope,
    schema_directory,
)

REPOSITORY = Path(__file__).resolve().parents[3]
CORPUS = REPOSITORY / "fixtures" / "protocol-corpus"
VALIDATOR = ProtocolValidator()


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _corpus(group: str) -> list[Path]:
    return sorted((CORPUS / group).glob("*.json"))


def test_one_schema_per_message_type() -> None:
    schemas = sorted(schema_directory().glob("*.schema.json"))
    assert len(schemas) == len(MESSAGE_TYPES) + 1


@pytest.mark.parametrize("path", _corpus("valid"), ids=lambda p: p.name)
def test_valid_corpus_accepted(path: Path) -> None:
    valid, diagnostics = VALIDATOR.validate(_load(path))
    assert valid, diagnostics


@pytest.mark.parametrize("path", _corpus("invalid"), ids=lambda p: p.name)
def test_invalid_corpus_rejected(path: Path) -> None:
    valid, diagnostics = VALIDATOR.validate(_load(path))
    assert not valid
    assert diagnostics


def test_unknown_protocol_version_is_named_in_the_diagnostic() -> None:
    message = _load(CORPUS / "invalid" / "unknown-protocol-version.json")
    valid, diagnostics = VALIDATOR.validate(message)
    assert not valid
    assert "unsupported protocol version" in " ".join(diagnostics)


def test_skill_invocation_rejects_free_form_command_fields() -> None:
    base = _load(CORPUS / "valid" / "skill-invocation.json")
    assert isinstance(base, dict)
    for field in ("command", "chat", "script", "code", "mineflayer"):
        assert not VALIDATOR.validate({**base, field: "anything"})[0], field
    nested = json.loads(json.dumps(base))
    nested["parameters"]["payload"] = {"run": "rm -rf"}
    assert not VALIDATOR.validate(nested)[0]


def test_assert_valid_raises_protocol_error() -> None:
    with pytest.raises(ProtocolError):
        VALIDATOR.assert_valid({"protocolVersion": PROTOCOL_VERSION})


def test_framing_round_trip_and_rejection() -> None:
    message = _load(CORPUS / "valid" / "observation.json")
    line = encode_frame(message)
    assert line.endswith("\n")
    assert decode_frame(line[:-1]) == message
    for bad in ("{not json", "[1,2,3]", "null"):
        with pytest.raises(FrameError):
            decode_frame(bad)


def test_line_reader_bounds_its_buffer() -> None:
    reader = LineReader(limit=64)
    lines, error = reader.push('{"a":1}\n{"b":2}\n')
    assert lines == ['{"a":1}', '{"b":2}']
    assert error is None
    assert reader.push('{"c":')[0] == []
    assert reader.push("3}\n")[0] == ['{"c":3}']
    _, error = reader.push("x" * 128)
    assert error is not None
    assert reader.pending == ""


def test_envelope_carries_replay_metadata() -> None:
    meta = envelope(
        SessionIdentity("ada", "8f6c1c0e-3d0a-4a1e-9f3a-2b6f1d9c4e11", "w"),
        "Observation",
        17,
    )
    for key in (
        "protocolVersion",
        "messageId",
        "personId",
        "sessionId",
        "worldId",
        "tick",
        "timestamp",
        "type",
    ):
        assert key in meta
    assert meta["protocolVersion"] == PROTOCOL_VERSION


def test_node_and_python_validators_agree_on_the_whole_corpus() -> None:
    node = os.environ.get("PERSON_NODE") or shutil.which("node")
    if not node:
        pytest.fail("node is required for the protocol compatibility test")
    result = subprocess.run(
        [node, str(REPOSITORY / "scripts" / "protocol-verdicts.ts")],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    node_verdicts = json.loads(result.stdout)
    assert node_verdicts, "the Node validator produced no verdicts"
    for group in ("valid", "invalid"):
        for path in _corpus(group):
            key = f"{group}/{path.name}"
            assert key in node_verdicts, f"{key} missing from the Node verdicts"
            python_valid, _ = VALIDATOR.validate(_load(path))
            assert python_valid == node_verdicts[key]["valid"], key
