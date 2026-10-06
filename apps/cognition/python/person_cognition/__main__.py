"""Entry point for the cognition process.

The runtime spawns this, writes newline-delimited protocol messages to its
standard input and reads them back from its standard output. Diagnostics go to
standard error, which the runtime captures but never parses as protocol.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

from person_config import ConfigError, load_cognition_settings
from person_persistence import EventRecordError, IdentityError, JournalCorruption

from .affect import research_bounds
from .continuity import found, inspect_root
from .environment import load_environment
from .loop import CognitionLoop


def compare_effects(path: str) -> str:
    """The validation harness's effect comparison, by the observations' environment."""
    with open(path, encoding="utf8") as handle:
        request = json.load(handle)
    kind = str(request["before"]["experience"]["environmentKind"])
    return json.dumps(load_environment(kind).compare_effects(request))


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
        description="Person cognition process (speaks the person-v3 protocol over stdio)",
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
    parser.add_argument(
        "--found",
        action="store_true",
        help=(
            "Found the configured Person: write its founding event into an empty "
            "evidence directory and exit (ADR 0017). The only way a canonical "
            "Person (person-NNN) comes into existence. Starts no cognition."
        ),
    )
    parser.add_argument(
        "--inspect-root",
        metavar="EVIDENCE_DIRECTORY",
        help=(
            "Print what an operator may know of a continuity root, as JSON, and exit "
            "(ADR 0018): its state, founding, life status, last session, world and lock. "
            "Read-only: takes no lock and writes nothing. Starts no cognition."
        ),
    )
    parser.add_argument(
        "--affect-bounds",
        action="store_true",
        help=(
            "Print what affect could do at most under the current architecture, as JSON, "
            "for the experiment harness (ADR 0013). Starts no cognition loop."
        ),
    )
    arguments = parser.parse_args(argv)

    if arguments.affect_bounds:
        # A static property of the code, for research tooling. Nothing here
        # can become a decision, and Person never consults it.
        sys.stdout.write(json.dumps(research_bounds(), sort_keys=True) + "\n")
        return 0

    if arguments.inspect_root:
        try:
            report = inspect_root(Path(arguments.inspect_root))
        except (OSError, EventRecordError, JournalCorruption) as error:
            sys.stderr.write(f"person-cognition: {error}\n")
            return 2
        sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")
        return 0

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

    if arguments.found:
        if not arguments.config:
            sys.stderr.write("person-cognition: --found needs --config\n")
            return 2
        try:
            chosen = load_cognition_settings(arguments.config)
            founding = found(
                evidence_directory=chosen.evidence_directory,
                person_id=chosen.person_id,
                world_id=chosen.world_id,
                name=chosen.identity_name,
                designation=chosen.identity_designation,
                environment_kind=chosen.environment_kind,
                embodiment_kind=chosen.embodiment_kind,
            )
        except (ConfigError, IdentityError) as error:
            sys.stderr.write(f"person-cognition: {error}\n")
            return 2
        sys.stdout.write(json.dumps(founding.payload(), sort_keys=True) + "\n")
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
        affect_mode=settings.affect_mode if settings is not None else "active",
        interoception=settings.interoception if settings is not None else True,
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
