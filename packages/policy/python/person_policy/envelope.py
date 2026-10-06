"""The safe exploration envelope: the verdict the policy acts on.

Exploration of an uncertain routine is only allowed when Person can afford to
be wrong. Outside the envelope the exploration bonus is exactly zero and the
best-supported safe behaviour wins.

Whether Person can afford to be wrong is judged by the environment profile
from the decision state (Minecraft's: `person_minecraft.envelope`, ADR 0025);
the policy sees only the verdict. It mirrors, on the cognition side, the
safety hierarchy the runtime enforces, and is not a substitute for it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EnvelopeVerdict:
    open: bool
    reasons: tuple[str, ...]

    def __bool__(self) -> bool:
        return self.open


#: The verdict when nothing says exploring is safe.
CLOSED = EnvelopeVerdict(open=False, reasons=("no_envelope",))
