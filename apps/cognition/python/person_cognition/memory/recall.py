"""Recall: a typed cue in, a few labelled memories out.

A cue names subjects and kinds from closed vocabularies and says why Person is
trying to remember. It carries no text and no limit, so the question is always
one Person could ask itself and the answer is always small.

Ranking is two numbers multiplied (ADR 0007):

    relevance      the fraction of the cue's subjects the memory is about;
                   zero excludes the memory, so recall is always cued
    accessibility  0.5 ** (age / half_life), where half_life grows with
                   salience, so what mattered fades more slowly

A memory whose accessibility has fallen below the threshold is not recalled.
It is not deleted either; it is still in the store and in the journal.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .episodes import KINDS, SUBJECTS, Episode, MemoryRecordError

#: Why Person may try to remember. Closed, like everything else in a cue.
PURPOSES: frozenset[str] = frozenset({"search", "goal", "orient"})

#: The most a single recall ever returns.
RECALL_LIMIT = 3

#: The most subjects one cue may name: enough for every evidence fact a plan
#: can lack, and well short of the vocabulary. A cue about everything is a dump.
MAX_CUE_SUBJECTS = 6


@dataclass(frozen=True, slots=True)
class Cue:
    subjects: frozenset[str]
    purpose: str
    kinds: frozenset[str] = field(default=KINDS)

    def __post_init__(self) -> None:
        for name, values, vocabulary in (
            ("subjects", self.subjects, SUBJECTS),
            ("kinds", self.kinds, KINDS),
        ):
            if not isinstance(values, frozenset) or not all(isinstance(v, str) for v in values):
                raise TypeError(f"a cue's {name} are a frozenset of vocabulary words")
            unknown = values - vocabulary
            if unknown:
                raise MemoryRecordError(f"a cue cannot ask about {sorted(unknown)}")
        if not self.subjects:
            raise MemoryRecordError("a cue must be about something")
        if len(self.subjects) > MAX_CUE_SUBJECTS:
            raise MemoryRecordError(f"a cue names at most {MAX_CUE_SUBJECTS} subjects")
        if not self.kinds:
            raise MemoryRecordError("a cue must allow at least one kind of episode")
        if self.purpose not in PURPOSES:
            raise MemoryRecordError(f"unknown recall purpose {self.purpose!r}")

    @classmethod
    def about(cls, *subjects: str, purpose: str, kinds: Iterable[str] | None = None) -> Cue:
        return cls(
            subjects=frozenset(subjects),
            purpose=purpose,
            kinds=frozenset(kinds) if kinds is not None else KINDS,
        )

    def to_json(self) -> dict[str, object]:
        return {
            "subjects": sorted(self.subjects),
            "kinds": sorted(self.kinds),
            "purpose": self.purpose,
        }


@dataclass(frozen=True, slots=True)
class RecallRules:
    """The replaceable constants of retrieval. Engineering defaults, not psychology."""

    #: Experienced ticks for an unremarkable memory to halve in accessibility.
    #: One Minecraft day.
    base_half_life: float = 24_000.0
    #: How much salience stretches the half-life: salience 1 lasts ten times as long.
    salience_stretch: float = 9.0
    #: Below this accessibility a memory does not come back.
    threshold: float = 0.05
    limit: int = RECALL_LIMIT

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= RECALL_LIMIT:
            raise MemoryRecordError(f"recall returns between 1 and {RECALL_LIMIT} memories")

    def accessibility(self, episode: Episode, now: int) -> float:
        age = max(0, now - episode.experienced_tick)
        half_life = self.base_half_life * (1.0 + self.salience_stretch * episode.salience)
        return float(0.5 ** (age / half_life))

    @staticmethod
    def relevance(episode: Episode, cue: Cue) -> float:
        if episode.kind not in cue.kinds:
            return 0.0
        return len(cue.subjects.intersection(episode.subjects)) / len(cue.subjects)


@dataclass(frozen=True, slots=True)
class Recalled:
    """A memory as it came back: labelled as memory, never as perception."""

    episode: Episode
    #: Experienced ticks between encoding and this recall.
    age: int
    relevance: float
    accessibility: float
    source: str = "memory"

    @property
    def score(self) -> float:
        return self.relevance * self.accessibility


def rank(
    episodes: Iterable[Episode], cue: Cue, now: int, rules: RecallRules
) -> tuple[list[Recalled], int]:
    """The best few recallable memories for a cue, and how many were recallable."""
    recallable: list[Recalled] = []
    for episode in episodes:
        relevance = rules.relevance(episode, cue)
        if relevance <= 0.0:
            continue
        accessibility = rules.accessibility(episode, now)
        if accessibility < rules.threshold:
            continue
        recallable.append(
            Recalled(
                episode=episode,
                age=max(0, now - episode.experienced_tick),
                relevance=relevance,
                accessibility=accessibility,
            )
        )
    recallable.sort(
        key=lambda item: (-item.score, -item.episode.experienced_tick, item.episode.memory_id)
    )
    return recallable[: rules.limit], len(recallable)
