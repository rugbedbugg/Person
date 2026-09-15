"""Shared fixtures for the cross-cutting Python tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def repository() -> Path:
    return REPOSITORY


@pytest.fixture(scope="session")
def sample_observation() -> dict:
    path = REPOSITORY / "fixtures" / "protocol-corpus" / "valid" / "observation.json"
    return json.loads(path.read_text(encoding="utf-8"))
