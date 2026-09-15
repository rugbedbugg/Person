"""Locate the canonical schema files in both source and installed layouts."""

from __future__ import annotations

from pathlib import Path


def package_asset_directory(module_file: str, name: str, source_depth: int = 2) -> Path:
    """Return a data directory shipped with a package.

    Wheels place the directory inside the package (``person_protocol/schemas``).
    A source checkout keeps it next to the language bindings so the TypeScript
    runtime reads exactly the same files (``packages/protocol/schemas``).
    """
    installed = Path(module_file).resolve().parent / name
    if installed.is_dir():
        return installed
    source = Path(module_file).resolve().parents[source_depth] / name
    if source.is_dir():
        return source
    raise FileNotFoundError(f"Cannot locate the {name!r} asset directory for {module_file}")
