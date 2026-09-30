"""One deliberation, recorded (ADR 0020, C1).

Mode `off` invokes and records nothing. Mode `record_only` builds nothing
itself: it is handed a context, pins the effective input by hash, calls the
model, gates the answer and records what happened. It returns the verdict to
its caller and changes nothing else; in C1 nothing acts on it.

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
from .model import CognitiveModel, ModelResponse, canonical_json, sha256_text
from .proposal import INSTRUCTION_TEMPLATE, PROPOSAL_SCHEMA, Verdict, gate

MODES: tuple[str, ...] = ("off", "record_only")
#: Wall-clock bound on one call. Implementation parameter.
TIMEOUT_S = 120.0

Record = Callable[[str, dict[str, Any]], Any]


@dataclass(frozen=True, slots=True)
class Outcome:
    deliberation_id: str
    #: `completed` or `unavailable`.
    status: str
    verdict: Verdict | None


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

    def deliberate(self, context: DeliberationContext, *, experienced_tick: int) -> Outcome | None:
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
            },
        )
        started = time.monotonic()
        try:
            response = self.model.deliberate(
                INSTRUCTION_TEMPLATE, context_text, timeout_s=TIMEOUT_S
            )
        except Exception:  # an adapter that raises is a backend that failed
            response = ModelResponse(
                status="unavailable",
                provider=self.model.provider,
                model=self.model.model,
                backend_version="unknown",
                latency_ms=int((time.monotonic() - started) * 1000),
                reason="backend",
            )
        if response.status == "unavailable":
            self._audit_artifact(deliberation_id, pinned, context_text, response, None)
            self._record(
                "deliberation_unavailable",
                {
                    "deliberation_id": deliberation_id,
                    "reason": response.reason,
                    "latency_ms": response.latency_ms,
                    **response.identity(),
                },
            )
            return Outcome(deliberation_id, "unavailable", None)
        text = response.text or ""
        verdict = gate(text, context)
        output_sha256 = sha256_text(text)
        self._audit_artifact(deliberation_id, pinned, context_text, response, output_sha256)
        self._record(
            "deliberation_completed",
            {
                "deliberation_id": deliberation_id,
                "output_sha256": output_sha256,
                "latency_ms": response.latency_ms,
                **response.identity(),
                "verdict": "admitted" if verdict.admitted else "rejected",
                "rejections": list(verdict.rejections),
                "proposal": verdict.proposal,
                "stated_confidence": verdict.confidence,
            },
        )
        return Outcome(deliberation_id, "completed", verdict)

    def _audit_artifact(
        self,
        deliberation_id: str,
        pinned: dict[str, str],
        context_text: str,
        response: ModelResponse,
        output_sha256: str | None,
    ) -> None:
        """The exact input and raw answer, for operators and C7 audits only."""
        if self._audit is None:
            return
        self._audit.mkdir(parents=True, exist_ok=True, mode=0o700)
        artifact = {
            "deliberation_id": deliberation_id,
            **pinned,
            "instruction": INSTRUCTION_TEMPLATE,
            "context": context_text,
            "response": {
                "status": response.status,
                **response.identity(),
                "latency_ms": response.latency_ms,
                "reason": response.reason,
                "text": response.text,
                "output_sha256": output_sha256,
            },
        }
        (self._audit / f"{deliberation_id}.json").write_text(
            canonical_json(artifact) + "\n", encoding="utf-8"
        )
