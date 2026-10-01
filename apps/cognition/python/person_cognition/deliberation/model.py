"""The provider-neutral cognitive model interface (ADR 0020, C1).

A model is a stateless service: it receives the instruction and one bounded
context as text and returns text. The adapter, never the model's text, says
which provider, model and backend answered, how long it took, and whether
there was an answer at all. What the text means is decided afterwards, by
Person's parse and grounding gate.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

#: Why a provider produced no response. A malformed response is a response.
UNAVAILABLE_REASONS: tuple[str, ...] = ("timeout", "quota", "authentication", "backend")


def canonical_json(value: Any) -> str:
    """The one serialisation hashed and sent: sorted keys, no spacing."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SterilityFailure(RuntimeError):
    """A backend showed or used a capability it must not have (ADR 0020 rule 6).

    Carries only the violation category and the hash of the quarantined raw
    output: never the output itself.
    """

    def __init__(self, provider: str, category: str, output_sha256: str | None) -> None:
        super().__init__(f"{provider}: sterility failure ({category})")
        self.provider = provider
        self.category = category
        self.output_sha256 = output_sha256


class ProviderDegraded(RuntimeError):
    """A response carried an event the backend does not recognise.

    Not evidence of a capability: this one answer is rejected, and the
    backend stays enabled. Carries only the category.
    """

    def __init__(self, provider: str, category: str) -> None:
        super().__init__(f"{provider}: degraded response ({category})")
        self.provider = provider
        self.category = category


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """What an adapter reports for one call."""

    #: `answered` or `unavailable`.
    status: str
    provider: str
    model: str
    backend_version: str
    latency_ms: int
    #: The raw text, when answered. Never journalled; audited only.
    text: str | None = None
    #: One of `UNAVAILABLE_REASONS`, when unavailable.
    reason: str | None = None
    #: What kind of backend answered, e.g. `codex_exec`; whether it carries a
    #: provider-owned harness prompt, and whether that prompt is opaque to us.
    harness: str = "direct"
    provider_owned_harness: bool = False
    opaque_harness: bool = False
    #: Token counts the provider reports, when it does.
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.status not in ("answered", "unavailable"):
            raise ValueError(f"unknown model response status {self.status!r}")
        if self.status == "answered" and self.text is None:
            raise ValueError("an answered response carries its text")
        if self.status == "unavailable" and self.reason not in UNAVAILABLE_REASONS:
            raise ValueError(f"unknown unavailability reason {self.reason!r}")

    def identity(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "backend_version": self.backend_version,
            "harness": self.harness,
            "provider_owned_harness": self.provider_owned_harness,
            "opaque_harness": self.opaque_harness,
        }


@runtime_checkable
class CognitiveModel(Protocol):
    """A replaceable deliberative service. It is not Person (ADR 0020)."""

    provider: str
    model: str

    def deliberate(self, instruction: str, context: str, *, timeout_s: float) -> ModelResponse: ...


class ScriptedModel:
    """A model whose answers are written in advance: for tests and offline runs.

    Each entry is the text it answers with, or a mapping serialised as JSON,
    or `None` for a call the provider could not answer (`timeout`).
    """

    provider = "scripted"
    model = "scripted-v1"

    def __init__(self, answers: Iterable[str | Mapping[str, Any] | None]) -> None:
        self._answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def deliberate(self, instruction: str, context: str, *, timeout_s: float) -> ModelResponse:
        self.calls.append((instruction, context))
        answer = self._answers.pop(0) if self._answers else None
        if answer is None:
            return ModelResponse(
                status="unavailable",
                provider=self.provider,
                model=self.model,
                backend_version="scripted",
                latency_ms=0,
                reason="timeout",
            )
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return ModelResponse(
            status="answered",
            provider=self.provider,
            model=self.model,
            backend_version="scripted",
            latency_ms=0,
            text=text,
        )


class TemplateModel:
    """A scripted backend whose answers name context items by what they are.

    For offline tests and fixture runs, configured as `backend = "scripted"`:
    it makes no network call. Each answer in the file is `null` (no answer)
    or a proposal in which a placeholder string stands for a context
    reference: `$cap:<fact>` (a capability declaring that effect),
    `$mem:<kind>` (a memory of that kind), `$recent:emergency` (an emergency
    outcome), `$goal:<type>` and `$situation`. A placeholder with nothing to
    stand for is left as it is, so the gate sees exactly what was written.
    """

    provider = "scripted"
    model = "template-v1"

    def __init__(self, answers: list[Any]) -> None:
        self._answers = list(answers)

    @classmethod
    def from_file(cls, path: Any) -> TemplateModel:
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @staticmethod
    def _resolve(placeholder: str, context: dict[str, Any]) -> str:
        kind, _, what = placeholder[1:].partition(":")
        sections = {
            "cap": "capabilities",
            "mem": "memories",
            "recent": "recent",
            "goal": "goals",
            "situation": "situation",
        }
        if kind not in sections:
            return placeholder

        def matches(item: dict[str, Any]) -> bool:
            if kind == "cap":
                return what in item.get("effects", ())
            if kind == "mem":
                return bool(item.get("kind") == what)
            if kind == "recent":
                return bool(item.get(what))
            if kind == "goal":
                return bool(item.get("goal_type") == what)
            return True

        found = [item["ref"] for item in context.get(sections[kind], []) if matches(item)]
        return str(found[-1]) if found else placeholder

    def _expand(self, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, str) and value.startswith("$"):
            return self._resolve(value, context)
        if isinstance(value, list):
            return [self._expand(item, context) for item in value]
        if isinstance(value, dict):
            return {key: self._expand(item, context) for key, item in value.items()}
        return value

    def deliberate(self, instruction: str, context: str, *, timeout_s: float) -> ModelResponse:
        answer = self._answers.pop(0) if self._answers else None
        if answer is None:
            return ModelResponse(
                status="unavailable",
                provider=self.provider,
                model=self.model,
                backend_version="scripted",
                latency_ms=0,
                reason="timeout",
            )
        return ModelResponse(
            status="answered",
            provider=self.provider,
            model=self.model,
            backend_version="scripted",
            latency_ms=0,
            text=json.dumps(self._expand(answer, json.loads(context))),
        )
