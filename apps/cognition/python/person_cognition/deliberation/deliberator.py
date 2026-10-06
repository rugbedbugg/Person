"""One deliberation, recorded (ADR 0020 C1; split for asynchrony in ADR 0021).

Mode `off` invokes and records nothing. Otherwise a deliberation has three
steps, and only the middle one may run off the main thread:

1. `request` (main thread): pin the effective input by hash and record the
   request;
2. `call` (worker): the provider call and nothing else, touching no cognitive
   state and no journal;
3. `finish` (main thread): gate the answer and record what happened.

The journal gets the request, the gated proposal or the rejections, and the
unavailability. The raw provider text goes only to an operator audit artifact
outside anything cognition reads, linked by hash.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .context import CONTEXT_SCHEMA, DeliberationContext
from .model import (
    CognitiveModel,
    ModelResponse,
    ProviderDegraded,
    SterilityFailure,
    canonical_json,
    sha256_text,
)
from .proposal import INSTRUCTION_TEMPLATE, PROPOSAL_SCHEMA, Verdict, gate

MODES: tuple[str, ...] = ("off", "record_only", "active")
#: Wall-clock bound on one call. Implementation parameter.
TIMEOUT_S = 120.0

Record = Callable[[str, dict[str, Any]], Any]


@dataclass(frozen=True, slots=True)
class Outcome:
    deliberation_id: str
    #: `completed` or `unavailable`.
    status: str
    verdict: Verdict | None
    #: Why an answer was not usable, when it was a sterility failure or a
    #: degraded or unavailable response; `None` for an ordinary gated answer.
    failure: str | None = None


@dataclass(frozen=True, slots=True)
class Request:
    """A recorded request: everything the worker and `finish` need."""

    deliberation_id: str
    context: DeliberationContext
    context_text: str
    pinned: dict[str, str]
    started: float


#: What the worker hands back: a response, or the exception the call raised.
CallResult = ModelResponse | BaseException


class Deliberator:
    def __init__(
        self,
        *,
        mode: str,
        model: CognitiveModel | None,
        record: Record,
        audit_directory: Path | None = None,
        new_id: Callable[[], str] = lambda: f"dlb_{uuid.uuid4().hex[:16]}",
    ) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown deliberation mode {mode!r}")
        self.mode = mode
        self.model = model
        self._record = record
        self._audit = audit_directory
        self._new_id = new_id

    def request(
        self,
        context: DeliberationContext,
        *,
        experienced_tick: int,
        extra: dict[str, Any] | None = None,
    ) -> Request | None:
        if self.mode == "off" or self.model is None:
            return None
        deliberation_id = self._new_id()
        context_text = canonical_json(context.document)
        pinned = {
            "context_schema": CONTEXT_SCHEMA,
            "context_sha256": sha256_text(context_text),
            "instruction_sha256": sha256_text(INSTRUCTION_TEMPLATE),
            "proposal_schema": PROPOSAL_SCHEMA,
        }
        self._record(
            "deliberation_requested",
            {
                "deliberation_id": deliberation_id,
                "mode": self.mode,
                "reason": context.reason(),
                "request_refs": list(context.document["request"]["refs"]),
                "experienced_tick": experienced_tick,
                "provider": self.model.provider,
                "model": self.model.model,
                **pinned,
                **(extra or {}),
            },
        )
        return Request(deliberation_id, context, context_text, pinned, time.monotonic())

    def call(self, request: Request) -> CallResult:
        """The provider call alone. Safe to run on a worker thread."""
        assert self.model is not None
        try:
            return self.model.deliberate(
                INSTRUCTION_TEMPLATE, request.context_text, timeout_s=TIMEOUT_S
            )
        except BaseException as error:  # handed back, judged on the main thread
            return error

    def finish(self, request: Request, result: CallResult) -> Outcome:
        """Gate and record one answer, on the main thread."""
        assert self.model is not None
        deliberation_id = request.deliberation_id
        latency = int((time.monotonic() - request.started) * 1000)
        if isinstance(result, SterilityFailure | ProviderDegraded):
            # An answer from a backend that was not sterile, or that carried
            # an event nobody recognises, is not an answer. Only the category
            # and, for a sterility failure, the hash are recorded; the raw
            # output is quarantined by the adapter, never here.
            sterility = isinstance(result, SterilityFailure)
            label = "sterility_failure" if sterility else "degraded"
            self._record(
                "deliberation_completed",
                {
                    "deliberation_id": deliberation_id,
                    "output_sha256": (
                        result.output_sha256 if isinstance(result, SterilityFailure) else None
                    ),
                    "latency_ms": latency,
                    "provider": result.provider,
                    "model": self.model.model,
                    "backend_version": "unverified",
                    "verdict": "rejected",
                    "rejections": [f"{label}:{result.category}"],
                    "proposal": None,
                    "stated_confidence": None,
                },
            )
            return Outcome(deliberation_id, "completed", None, failure=label)
        if isinstance(result, KeyboardInterrupt | SystemExit):
            raise result
        if isinstance(result, BaseException):
            # An adapter that raises is a backend that failed.
            result = ModelResponse(
                status="unavailable",
                provider=self.model.provider,
                model=self.model.model,
                backend_version="unknown",
                latency_ms=latency,
                reason="backend",
            )
        if result.status == "unavailable":
            self._audit_artifact(request, result, None)
            self._record(
                "deliberation_unavailable",
                {
                    "deliberation_id": deliberation_id,
                    "reason": result.reason,
                    "latency_ms": result.latency_ms,
                    **result.identity(),
                },
            )
            return Outcome(deliberation_id, "unavailable", None, failure="unavailable")
        text = result.text or ""
        verdict = gate(text, request.context)
        output_sha256 = sha256_text(text)
        self._audit_artifact(request, result, output_sha256)
        self._record(
            "deliberation_completed",
            {
                "deliberation_id": deliberation_id,
                "output_sha256": output_sha256,
                "latency_ms": result.latency_ms,
                **result.identity(),
                "verdict": "admitted" if verdict.admitted else "rejected",
                "rejections": list(verdict.rejections),
                "proposal": verdict.proposal,
                "stated_confidence": verdict.confidence,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                # Person's own share of the input, so a harness's overhead is
                # never read as what Person needed to think.
                "person_context_chars": len(request.context_text),
            },
        )
        return Outcome(deliberation_id, "completed", verdict)

    def deliberate(self, context: DeliberationContext, *, experienced_tick: int) -> Outcome | None:
        """All three steps in one, synchronously (C1 and offline evaluation)."""
        request = self.request(context, experienced_tick=experienced_tick)
        if request is None:
            return None
        return self.finish(request, self.call(request))

    def _audit_artifact(
        self, request: Request, response: ModelResponse, output_sha256: str | None
    ) -> None:
        """The exact input and raw answer, for operators and C7 audits only."""
        if self._audit is None:
            return
        self._audit.mkdir(parents=True, exist_ok=True, mode=0o700)
        artifact = {
            "deliberation_id": request.deliberation_id,
            **request.pinned,
            "instruction": INSTRUCTION_TEMPLATE,
            "context": request.context_text,
            "response": {
                "status": response.status,
                **response.identity(),
                "latency_ms": response.latency_ms,
                "reason": response.reason,
                "text": response.text,
                "output_sha256": output_sha256,
            },
        }
        (self._audit / f"{request.deliberation_id}.json").write_text(
            canonical_json(artifact) + "\n", encoding="utf-8"
        )
