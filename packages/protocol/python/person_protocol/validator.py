"""Validate protocol messages against the canonical JSON Schema files.

The Node runtime compiles the same files. Keeping one schema set and two thin
bindings is what stops the TypeScript and Python views of the contract from
drifting apart.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

from .assets import package_asset_directory
from .version import MESSAGE_TYPES, PROTOCOL_VERSION, SCHEMA_FILES


class ProtocolError(ValueError):
    """A message did not satisfy the versioned protocol contract."""

    def __init__(self, message: str, diagnostics: Iterable[str] = ()) -> None:
        self.diagnostics = list(diagnostics)
        detail = "; ".join(self.diagnostics)
        super().__init__(f"{message}: {detail}" if detail else message)


def schema_directory() -> Path:
    return package_asset_directory(__file__, "schemas")


def _describe(error: ValidationError) -> str:
    location = "/" + "/".join(str(part) for part in error.absolute_path)
    return f"{location} {error.message}"


class ProtocolValidator:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or schema_directory()
        resources = []
        for path in sorted(self.directory.glob("*.schema.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            resources.append((path.name, Resource.from_contents(schema)))
        registry = Registry().with_resources(resources)
        self._validators: dict[str, Draft202012Validator] = {}
        for message_type in MESSAGE_TYPES:
            filename = SCHEMA_FILES[message_type]
            schema = json.loads((self.directory / filename).read_text(encoding="utf-8"))
            self._validators[message_type] = Draft202012Validator(
                schema,
                registry=registry,
                format_checker=Draft202012Validator.FORMAT_CHECKER,
            )

    @property
    def message_types(self) -> tuple[str, ...]:
        return MESSAGE_TYPES

    def validate(self, message: Any) -> tuple[bool, list[str]]:
        if not isinstance(message, dict):
            return False, ["/ message must be a JSON object"]
        version = message.get("protocolVersion")
        if version != PROTOCOL_VERSION:
            return False, [
                f"/protocolVersion unsupported protocol version {json.dumps(version)}; "
                f"this runtime speaks {PROTOCOL_VERSION}"
            ]
        message_type = message.get("type")
        if not isinstance(message_type, str) or message_type not in self._validators:
            return False, [f"/type unknown message type {json.dumps(message_type)}"]
        errors = sorted(
            self._validators[message_type].iter_errors(message),
            key=lambda error: list(error.absolute_path),
        )
        if errors:
            return False, [_describe(error) for error in errors]
        return True, []

    def assert_valid(self, message: Any) -> dict[str, Any]:
        valid, diagnostics = self.validate(message)
        if not valid:
            raise ProtocolError("Invalid protocol message", diagnostics)
        assert isinstance(message, dict)
        return message


@lru_cache(maxsize=1)
def protocol_validator() -> ProtocolValidator:
    """Process-wide validator; compiling the schema set once is much cheaper."""
    return ProtocolValidator()
