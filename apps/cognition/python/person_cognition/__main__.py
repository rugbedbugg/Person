"""Entry point for the cognition process.

The runtime spawns this, writes newline-delimited protocol messages to its
standard input and reads them back from its standard output. Diagnostics go to
standard error, which the runtime captures but never parses as protocol.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

from person_config import ConfigError, load_cognition_settings

from .effects import main as compare_effects
from .loop import CognitionLoop


def _lines(stream: TextIO) -> Iterator[str]:
    """Yield one line at a time.

    ``read(n)`` on a pipe blocks until the buffer fills or the peer closes,
    which would stall the whole loop while the runtime waits for a decision.
    ``readline`` returns as soon as a framed message arrives.
    """
    readline = stream.readline
    while True:
        line = readline()
        if not line:
            return
        yield line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="person-cognition",
        description="Person cognition process (speaks the shroud-learning-v2 protocol over stdio)",
    )
    parser.add_argument("--config", help="Person configuration file, for the cognition settings")
    parser.add_argument(
        "--evidence-directory",
        help="Override the evidence directory the runtime announces (tests and replay)",
    )
    parser.add_argument(
        "--compare-effects",
        metavar="REQUEST",
        help=(
            "Compare a skill's declared effects against two observations and print the "
            "result. A one-shot analysis for the single-skill validation harness: it "
            "starts no cognition loop, reads no evidence, and proposes nothing."
        ),
    )
    arguments = parser.parse_args(argv)

    if arguments.compare_effects:
        # Deliberately before anything else is constructed. This path must not
        # be able to become a decision: no loop, no policy, no evidence.
        try:
            sys.stdout.write(compare_effects(arguments.compare_effects))
            sys.stdout.flush()
        except (OSError, ValueError, KeyError) as error:
            sys.stderr.write(f"person-cognition: {error}\n")
            return 2
        return 0

    settings = None
    if arguments.config:
        try:
            settings = load_cognition_settings(arguments.config)
        except ConfigError as error:
            sys.stderr.write(f"person-cognition: {error}\n")
            return 2

    def write(line: str) -> None:
        # The runtime blocks waiting for each decision, so every frame is
        # flushed as soon as it is written.
        sys.stdout.write(line)
        sys.stdout.flush()

    loop = CognitionLoop(
        settings=settings,
        evidence_directory=Path(arguments.evidence_directory)
        if arguments.evidence_directory
        else None,
        write=write,
    )
    try:
        loop.run(_lines(sys.stdin))
    except KeyboardInterrupt:  # pragma: no cover - operator interrupt
        return 130
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
