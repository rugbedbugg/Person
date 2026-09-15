"""Newline-delimited JSON framing with a hard size ceiling."""

from __future__ import annotations

import json
from typing import Any

MAX_FRAME_BYTES = 1024 * 1024


class FrameError(ValueError):
    """A frame could not be encoded or decoded."""


def encode_frame(message: Any) -> str:
    line = json.dumps(message, separators=(",", ":"), allow_nan=False)
    if "\n" in line:
        raise FrameError("Encoded message contains a newline")
    if len(line.encode("utf-8")) > MAX_FRAME_BYTES:
        raise FrameError("Encoded message exceeds the frame size limit")
    return line + "\n"


def decode_frame(line: str) -> dict[str, Any]:
    if len(line.encode("utf-8")) > MAX_FRAME_BYTES:
        raise FrameError("frame exceeds the size limit")
    try:
        value = json.loads(line)
    except json.JSONDecodeError as error:
        raise FrameError(f"frame is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise FrameError("frame is not a JSON object")
    return value


class LineReader:
    """Incremental splitter that refuses to grow past the frame limit."""

    def __init__(self, limit: int = MAX_FRAME_BYTES) -> None:
        self._buffer = ""
        self._limit = limit

    def push(self, chunk: str) -> tuple[list[str], str | None]:
        self._buffer += chunk
        lines: list[str] = []
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                lines.append(line)
        if len(self._buffer.encode("utf-8")) > self._limit:
            self._buffer = ""
            return lines, "unterminated frame exceeded the size limit"
        return lines, None

    @property
    def pending(self) -> str:
        return self._buffer
