"""Person's canonical history: immutable events, the append-only journal,
snapshots and restore. History is not evidence (ADR 0027)."""

from .demonstrations import (
    DemonstrationError,
    DemonstrationManifest,
    file_digest,
    load_manifest,
)
from .events import (
    EVENT_SCHEMA_VERSION,
    EVENT_TYPES,
    EVIDENCE_SCHEMA_VERSION,
    SUPPORTED_EVIDENCE_SCHEMAS,
    CanonicalEvent,
    EventRecordError,
    EvidenceError,
    EvidenceEvent,
    new_event,
)
from .identity import (
    ContinuityRecord,
    Founding,
    IdentityError,
    LifeRecord,
    RootLock,
    SelfKnowledge,
    founded_explicitly,
    gap_category,
    is_canonical,
    is_validation,
    lock_holder,
)
from .journal import EventJournal, EvidenceJournal, JournalCorruption
from .legacy import LEGACY_TRAINING_CONTEXTS, legacy_experience
from .snapshot import SnapshotError, SnapshotStore
from .store import EventReducer, EventStore, EvidenceReducer, EvidenceStore, RestoreReport

__all__ = [
    "EVENT_SCHEMA_VERSION",
    "LEGACY_TRAINING_CONTEXTS",
    "CanonicalEvent",
    "EventJournal",
    "EventRecordError",
    "EventReducer",
    "EventStore",
    "legacy_experience",
    "EVENT_TYPES",
    "EVIDENCE_SCHEMA_VERSION",
    "ContinuityRecord",
    "Founding",
    "IdentityError",
    "LifeRecord",
    "RootLock",
    "SelfKnowledge",
    "founded_explicitly",
    "gap_category",
    "is_canonical",
    "is_validation",
    "lock_holder",
    "SUPPORTED_EVIDENCE_SCHEMAS",
    "DemonstrationError",
    "DemonstrationManifest",
    "EvidenceError",
    "EvidenceEvent",
    "EvidenceJournal",
    "EvidenceReducer",
    "EvidenceStore",
    "JournalCorruption",
    "RestoreReport",
    "SnapshotError",
    "SnapshotStore",
    "file_digest",
    "load_manifest",
    "new_event",
]
