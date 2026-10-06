"""Environment profiles, discovered as data (ADR 0025).

Person's core knows no environment by name. Each environment ships a manifest,
`environments/<kind>/environment.json`, naming the files that carry what it
owns: its observation payload schema, its configuration schema, its skill
library and vocabulary, its emergency vocabulary, and the module that supplies
its cognition-side profile. The core reads those manifests and nothing else,
so adding an environment never edits the core and the core cannot quietly
grow an environment's vocabulary.

The TypeScript runtime reads the same manifests (`packages/protocol/ts/environments.ts`).
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

#: Overrides where manifests are looked for: a path list, as PATH is.
ENVIRONMENTS_VARIABLE = "PERSON_ENVIRONMENTS"


class EnvironmentNotFound(LookupError):
    """No installed environment profile has this kind."""


@dataclass(frozen=True, slots=True)
class EnvironmentManifest:
    kind: str
    directory: Path
    document: Mapping[str, Any]

    @property
    def embodiments(self) -> tuple[str, ...]:
        return tuple(sorted(self.document["embodiments"]))

    def _json(self, relative: str) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads((self.directory / relative).read_text(encoding="utf-8"))
        return loaded

    @property
    def payload_schema(self) -> dict[str, Any]:
        return self._json(self.document["observationPayload"]["schema"])

    @property
    def config_schema(self) -> dict[str, Any]:
        return self._json(self.document["config"]["schema"])

    @property
    def skills_directory(self) -> Path:
        return self.directory / str(self.document["skills"]["directory"])

    @property
    def emergency_triggers(self) -> frozenset[str]:
        return frozenset(self.document["emergency"]["triggers"])

    @property
    def emergency_actions(self) -> frozenset[str]:
        return frozenset(self.document["emergency"]["actions"])

    @property
    def cognition_entry(self) -> str | None:
        entry = self.document.get("cognition", {}).get("python")
        return None if entry is None else str(entry)


def environment_roots() -> tuple[Path, ...]:
    configured = os.environ.get(ENVIRONMENTS_VARIABLE)
    if configured:
        return tuple(Path(part) for part in configured.split(os.pathsep) if part)
    # Source layout: packages/protocol/python/person_protocol/environments.py.
    return (Path(__file__).resolve().parents[4] / "environments",)


@lru_cache(maxsize=1)
def discovered() -> Mapping[str, EnvironmentManifest]:
    found: dict[str, EnvironmentManifest] = {}
    for root in environment_roots():
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*/environment.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            kind = str(document["kind"])
            if kind != path.parent.name:
                raise ValueError(f"{path} declares kind {kind!r} in directory {path.parent.name}")
            if kind in found:
                raise ValueError(f"environment {kind!r} is installed twice")
            found[kind] = EnvironmentManifest(kind=kind, directory=path.parent, document=document)
    return found


def environment(kind: str) -> EnvironmentManifest:
    try:
        return discovered()[kind]
    except KeyError:
        raise EnvironmentNotFound(
            f"no environment profile {kind!r} is installed "
            f"(found: {', '.join(sorted(discovered())) or 'none'})"
        ) from None


def sole_environment() -> EnvironmentManifest:
    """The one installed environment, for defaults that need one. Refuses ambiguity."""
    installed = discovered()
    if len(installed) != 1:
        raise EnvironmentNotFound(
            f"expected exactly one installed environment, found {sorted(installed)}; name one"
        )
    return next(iter(installed.values()))
