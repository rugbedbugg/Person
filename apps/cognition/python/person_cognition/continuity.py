"""Opening a continuity root as one Person, and what that Person learns of its gaps.

ADR 0017. The trusted part: it reads the root's first record to decide whose
root this is, and fails closed on anything else. What cognition is given is a
`SelfKnowledge` projection, never a record or the journal.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from person_persistence import (
    ContinuityRecord,
    EvidenceEvent,
    EvidenceStore,
    Founding,
    IdentityError,
    RootLock,
    SelfKnowledge,
    gap_category,
    is_canonical,
    new_event,
)


@dataclass(frozen=True, slots=True)
class RootPlan:
    """What opening a root requires: a founding to write, or nothing."""

    #: Write this as the first event of an empty root.
    found: Founding | None
    #: The root has events but no founding: read and resume as before.
    legacy: bool


def plan_root(
    first: EvidenceEvent | None,
    *,
    person_id: str,
    name: str | None,
    designation: str | None,
    now: str,
    founding_command: bool = False,
) -> RootPlan:
    """Decide how to open a root as `person_id`, or refuse."""
    if first is None:
        if is_canonical(person_id) and not founding_command:
            raise IdentityError(
                f"{person_id} is a canonical Person; its continuity root is founded only "
                "by the operator's founding command, never by ordinary startup"
            )
        if is_canonical(person_id) and (not name or not designation):
            raise IdentityError(f"founding {person_id} needs a name and a designation")
        return RootPlan(
            found=Founding(
                person_id=person_id,
                name=name or person_id,
                designation=designation,
                founded_at=now,
            ),
            legacy=False,
        )
    if first.type == "person_founded":
        founding = Founding.from_payload(first.payload)
        if founding.person_id != person_id:
            raise IdentityError(
                f"this continuity root belongs to {founding.person_id}, not {person_id}"
            )
        if founding_command:
            raise IdentityError(f"{person_id} is already founded; founding happens once")
        return RootPlan(found=None, legacy=False)
    if first.person_id != person_id:
        raise IdentityError(f"this legacy root belongs to {first.person_id}, not {person_id}")
    if founding_command:
        raise IdentityError(
            "a legacy root is never given a founding event after the fact; "
            "binding it to a canonical Person needs an explicit, recorded migration"
        )
    return RootPlan(found=None, legacy=True)


def session_payload(record: ContinuityRecord, session_id: str, now: str) -> dict[str, object]:
    """What a new session records about the one before it and the gap between."""
    previous = record.last_session
    return {
        "session_id": session_id,
        "previous_session_id": previous["session_id"] if previous else None,
        "previous_ended_cleanly": previous["ended"] if previous else None,
        "gap": gap_category(record.last_timestamp, now),
        # Suspension is known only now, from how the last session ended and
        # this one begins (I2): the process was not running in between.
        "suspension": (
            {
                "after": "clean_end" if previous["ended"] else "crash",
                "world_at_end": record.world,
            }
            if previous
            else None
        ),
    }


@dataclass(frozen=True, slots=True)
class OperationalView:
    """What Person may know of its operational state (ADR 0017, I2).

    Only whether the world is available to its body now: not why, not for how
    long, and nothing of the runtime's connection machinery.
    """

    world: str | None


def self_knowledge(
    record: ContinuityRecord, person_id: str, session: dict[str, object]
) -> SelfKnowledge:
    founding = record.founding
    return SelfKnowledge(
        person_id=person_id,
        name=founding.name if founding else None,
        designation=founding.designation if founding else None,
        founded_at=founding.founded_at if founding else None,
        last_gap=session["gap"],  # type: ignore[arg-type]
        previous_ended_cleanly=session["previous_ended_cleanly"],  # type: ignore[arg-type]
    )


def found(
    *,
    evidence_directory: Path,
    person_id: str,
    world_id: str,
    name: str | None,
    designation: str | None,
    training_context: str,
    now: str | None = None,
) -> Founding:
    """The operator's founding command: write a founding into an empty root.

    The only way a canonical Person comes into existence (ADR 0017). It
    writes exactly one event and starts no cognition.
    """
    moment = now or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    lock = RootLock(evidence_directory).acquire()
    try:
        store = EvidenceStore(evidence_directory)
        plan = plan_root(
            store.first_event(),
            person_id=person_id,
            name=name,
            designation=designation,
            now=moment,
            founding_command=True,
        )
        assert plan.found is not None
        made = new_event(
            person_id=person_id,
            world_id=world_id,
            session_id=str(uuid.uuid4()),
            # Founding happens outside any episode, as the loop's own pre-episode events do.
            episode_id="ep_unstarted",
            decision_id=None,
            tick=0,
            policy_revision=0,
            training_context=training_context,
            event_type="person_founded",
            payload=plan.found.payload(),
            previous_event_id=None,
        )
        # The founding's recorded time is its founding moment, by definition.
        store.append(EvidenceEvent.from_json({**made.to_json(), "timestamp": moment}))
        return plan.found
    finally:
        lock.release()
