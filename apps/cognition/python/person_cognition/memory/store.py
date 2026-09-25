"""The memory store, and the one narrow door cognition uses to reach it.

`MemoryStore` is an evidence reducer. It is rebuilt after a restart by
replaying the journal, and it reads exactly one kind of event,
`memory_encoded`, so nothing Person did not encode as an episode can become a
memory, however much of it the journal holds (ADR 0003, ADR 0007). It also
reads the experienced time `episode_ended` recorded, so a restarted Person's
clock resumes where it stopped.

`Memory` is what the cognition loop holds. It decides what in an observation
is worth encoding, stamps drafts with experienced time and salience, keeps a
small working memory, and answers typed cues with a few labelled memories. It
has no method that returns the store.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from person_persistence import EvidenceEvent

from . import encoding
from .episodes import Episode, EpisodeDraft, Provenance
from .recall import Cue, Recalled, RecallRules, rank
from .salience import with_novelty

#: Experienced ticks a subject must be out of sight before seeing it again is
#: a new episode. Thirty seconds of game time.
REFRACTORY_TICKS = 600

#: Items working memory holds. It is not persisted.
WORKING_CAPACITY = 7


class MemoryStore:
    """Every episode Person has encoded. Operators and tests read it; cognition does not."""

    def __init__(self) -> None:
        self._episodes: dict[str, Episode] = {}
        self._familiar: set[tuple[str, str]] = set()
        self.experienced = 0

    def reset(self) -> None:
        self._episodes.clear()
        self._familiar.clear()
        self.experienced = 0

    def apply(self, event: EvidenceEvent) -> None:
        payload = event.payload
        if event.type == "memory_encoded":
            episode = Episode(
                memory_id=event.event_id,
                kind=str(payload["kind"]),
                subjects=tuple(str(subject) for subject in payload["subjects"]),
                experienced_tick=int(payload["experienced_tick"]),
                world_tick=event.tick,
                episode_id=event.episode_id,
                training_context=event.training_context,
                salience=float(payload["salience"]),
                details=dict(payload["details"]),
                provenance=Provenance.from_json(payload["provenance"]),
                place_id=(payload.get("place") or {}).get("place_id"),
                place_confidence=float((payload.get("place") or {}).get("confidence", 0.0)),
            )
            self._add(episode)
        elif event.type == "episode_ended" and "experienced_ticks" in payload:
            self.experienced = max(self.experienced, int(payload["experienced_ticks"]))

    def _add(self, episode: Episode) -> None:
        self._episodes[episode.memory_id] = episode
        self.experienced = max(self.experienced, episode.experienced_tick)
        for subject in episode.subjects:
            self._familiar.add((episode.training_context, subject))

    def to_json(self) -> dict[str, Any]:
        return {
            "experienced": self.experienced,
            "episodes": [episode.to_json() for episode in self._episodes.values()],
        }

    def load_json(self, body: Mapping[str, Any]) -> None:
        self.reset()
        for record in body["episodes"]:
            self._add(Episode.from_json(record))
        self.experienced = max(self.experienced, int(body["experienced"]))

    def __len__(self) -> int:
        return len(self._episodes)

    def get(self, memory_id: str) -> Episode | None:
        return self._episodes.get(memory_id)

    def familiar(self, training_context: str, subjects: tuple[str, ...]) -> bool:
        """Whether Person has encoded anything about every one of these before."""
        return all((training_context, subject) in self._familiar for subject in subjects)

    def episodes_in(self, training_context: str) -> Iterator[Episode]:
        """Candidates for recall. Fixture and live memories never mix."""
        return (
            episode
            for episode in self._episodes.values()
            if episode.training_context == training_context
        )

    def inspect(self) -> tuple[Episode, ...]:
        """Everything, in encoding order. For operators and tests, never cognition."""
        return tuple(self._episodes.values())


@dataclass(frozen=True, slots=True)
class Held:
    """One item in working memory, and how it got there."""

    how: str
    episode: Episode
    recalled: Recalled | None = None


class WorkingMemory:
    """What Person has in mind: the last few things encoded or recalled."""

    def __init__(self, capacity: int = WORKING_CAPACITY) -> None:
        self._items: deque[Held] = deque(maxlen=capacity)

    def hold(self, item: Held) -> None:
        self._items.append(item)

    def items(self) -> tuple[Held, ...]:
        return tuple(self._items)

    def __len__(self) -> int:
        return len(self._items)


class Memory:
    """Person's access to its own past: encode experience, recall by cue."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        training_context: str,
        rules: RecallRules | None = None,
    ) -> None:
        self._store = store
        self.training_context = training_context
        self.rules = rules or RecallRules()
        self.working = WorkingMemory()
        self._now = store.experienced
        self._last_tick: int | None = None
        self._last_health: float | None = None
        self._in_view: frozenset[str] = frozenset()
        self._last_noticed: dict[str, int] = {}
        #: How many memories the last cue could have returned, for the journal.
        self.last_considered = 0

    # ------------------------------------------------------------------ time

    @property
    def now(self) -> int:
        """Person's experienced time: ticks it was present for, across restarts."""
        return self._now

    def observe_time(self, tick: int) -> None:
        # Only time Person was receiving observations for is experienced. A
        # restart resumes from the stored clock rather than the world's, and a
        # world tick that went backwards (a fresh fixture) adds nothing.
        if self._last_tick is not None and tick > self._last_tick:
            self._now += tick - self._last_tick
        self._last_tick = tick

    # -------------------------------------------------------------- encoding

    def experience(self, observation: Mapping[str, Any]) -> list[EpisodeDraft]:
        """What in this observation is worth encoding: harm felt, and things newly seen."""
        self.observe_time(int(observation["tick"]))
        drafts: list[EpisodeDraft] = []
        if self._last_health is not None:
            harm = encoding.hurt(self._last_health, observation)
            if harm is not None:
                drafts.append(harm)
        self._last_health = float(observation["vitals"]["health"])

        found = encoding.noticed(observation)
        for subject in sorted(found):
            last = self._last_noticed.get(subject)
            fresh = subject not in self._in_view and (
                last is None or self._now - last >= REFRACTORY_TICKS
            )
            if fresh:
                drafts.append(encoding.perceived(observation, subject, found[subject]))
            self._last_noticed[subject] = self._now
        self._in_view = frozenset(found)
        return drafts

    def payload(
        self, draft: EpisodeDraft, place: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """The journal payload for a draft, stamped with time, salience and place."""
        novel = not self._store.familiar(self.training_context, draft.subjects)
        return {
            "place": dict(place) if place else None,
            "kind": draft.kind,
            "subjects": list(draft.subjects),
            "experienced_tick": self._now,
            "salience": with_novelty(draft.salience, novel),
            "details": dict(draft.details),
            "provenance": draft.provenance.to_json(),
        }

    def encoded(self, memory_id: str) -> None:
        """An episode just reached the store; it is what Person has in mind."""
        episode = self._store.get(memory_id)
        if episode is not None:
            self.working.hold(Held("encoded", episode))

    # ---------------------------------------------------------------- recall

    def recall(self, cue: Cue) -> tuple[Recalled, ...]:
        """At most `RECALL_LIMIT` memories relevant to the cue, labelled as memory."""
        if not isinstance(cue, Cue):
            raise TypeError("recall takes a Cue; there is no free-form query")
        recalled, considered = rank(
            self._store.episodes_in(self.training_context), cue, self._now, self.rules
        )
        self.last_considered = considered
        for item in recalled:
            self.working.hold(Held("recalled", item.episode, item))
        return tuple(recalled)
