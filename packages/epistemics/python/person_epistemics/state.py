"""The epistemic views a decision is made from (ADR 0026).

    PHYSICAL TRUTH    WorldSnapshot, runtime-only; never reaches this package
    PERCEPTUAL TRUTH  PerceptualState: what this observation says Person sensed
    BELIEF            BeliefView: what Person currently takes to be true
    MEMORY            recalled episodes, labelled as memory
    KNOWLEDGE         Knowledge: what Person started with, and room for what an
                      explicit, evidence-backed promotion may add later
    SELF              SelfState: Person's view of itself, distinct from the world

`DecisionState` bundles them for one decision without merging them. Nothing
downstream of the epistemic boundary reads a raw protocol `Observation`: it
reads whichever of these views it needs. The planning facts in particular
(what is true now) come from current percepts for what is in reach and
beliefs for what persists, never from memories. Planning may consult
`recalled`, the memories a bounded recall supplied, as memory; it never
queries the memory store itself. Remembering that coal was seen somewhere is
a recalled episode; it is not a percept, and it does not make coal
reachable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .beliefs import BeliefView
from .evidence import BeliefValue
from .experience import ExperienceKey
from .provenance import NEVER_EVIDENCE, Source
from .scope import Scope, Situation


@dataclass(frozen=True, slots=True)
class PerceptualState[P]:
    """One observation, as perception: current, bounded, and nothing more.

    `percepts` is the environment's own typed view of the observation payload;
    the core never looks inside it. Everything here is about now.
    """

    message_id: str
    tick: int
    world_id: str
    experience: ExperienceKey
    #: The core, environment-neutral sense of Person's own motion (ADR 0008).
    self_motion: Mapping[str, Any]
    #: What the runtime reported of the previous skill, when there was one.
    previous_outcome: Mapping[str, Any] | None
    percepts: P
    source: Source = Source.REAL_OBSERVATION

    @property
    def situation(self) -> Situation:
        return Situation(
            environment_kind=self.experience.environment_kind,
            world_id=self.world_id,
            embodiment_kind=self.experience.embodiment_kind,
        )


@dataclass(frozen=True, slots=True)
class PlaceEstimate:
    """Where Person believes it is, in its own map (ADR 0008)."""

    place_id: str
    confidence: float


@dataclass(frozen=True, slots=True)
class SelfState[B]:
    """Person's view of itself, composed from the mechanisms that own each part.

    Nothing here is stored: each field is read from its owner when the state
    is built, so there is exactly one source for each.

        body           the environment's reading of the body this observation
                       reported (interoception's input)
        life           LifeRecord (ADR 0017): alive, awaiting_respawn
        world          OperationalView: whether the world is available
        place, home    the spatial model's self-estimate (ADR 0008, C8)
        affect         the affect state, when affect is on (ADR 0010)
        capabilities   the skills the runtime offered this session
        identity       self-knowledge from the continuity record (ADR 0017)
    """

    body: B
    life: str
    world_available: bool | None
    place: PlaceEstimate | None
    home_relation: str
    affect: Mapping[str, float] | None
    capabilities: tuple[str, ...]
    identity: Any | None = None


class KnowledgeRefused(ValueError):
    """An item that cannot be knowledge: no evidence, or the wrong kind of source."""


@dataclass(frozen=True, slots=True)
class KnownFact:
    """One item of learned knowledge: a belief an explicit gate promoted.

    The shape a future promotion writes, so promotion needs no redesign of
    `Knowledge`. Promotion keeps everything the belief had: its value and
    confidence, its basis (the provenance class it rests on), its evidence
    references and its scope, which a promotion never widens (widening is
    `check_widening`'s alone). It also names the canonical event that
    recorded the promotion, so knowledge can be traced and audited.

    No promotion gate exists yet: nothing outside this package constructs a
    `KnownFact` (architecture test), and the gate, when it comes, is its own
    decision. What may never become knowledge is settled now: anything whose
    class is never evidence (inference, recall, replay, counterfactuals,
    model rollouts, initial knowledge restated) and anything without evidence.
    """

    key: str
    value: BeliefValue
    confidence: float
    basis: Source
    evidence_refs: tuple[str, ...]
    scope: Scope
    #: The canonical event that recorded the promotion.
    promoted_by: str

    def __post_init__(self) -> None:
        if Source(self.basis) in NEVER_EVIDENCE:
            raise KnowledgeRefused(f"{self.basis.value} can never become knowledge")
        if not self.evidence_refs:
            raise KnowledgeRefused("knowledge must reference the evidence it rests on")
        if not self.promoted_by:
            raise KnowledgeRefused("knowledge must name the promotion that recorded it")
        if not 0.0 <= self.confidence <= 1.0:
            raise KnowledgeRefused("confidence must lie in [0, 1]")


@dataclass(frozen=True, slots=True)
class Knowledge:
    """What Person knows, as opposed to what it believes or remembers.

    Two parts, never merged. `skills` and `facts` are initial knowledge
    (`PERSON_SPEC` section 45.1), with `source` `INITIAL_KNOWLEDGE`. `learned`
    is knowledge Person acquired: each item a `KnownFact` an explicit,
    evidence-backed promotion produced from a belief, keeping its provenance
    and scope. Learned material is belief until such a promotion; none exists
    yet, so `learned` is always empty today. Inference or recall never
    reaches it silently: `KnownFact` refuses those classes outright.
    """

    skills: Any
    facts: Mapping[str, str]
    source: Source = Source.INITIAL_KNOWLEDGE
    learned: tuple[KnownFact, ...] = ()


@dataclass(frozen=True, slots=True)
class DecisionState[P, B]:
    percepts: PerceptualState[P]
    beliefs: BeliefView
    self_state: SelfState[B]
    knowledge: Knowledge
    #: Memories recalled for this decision, labelled as memory. Never percepts,
    #: never beliefs: they are what Person remembers, not what it sees.
    recalled: tuple[Any, ...] = field(default=())

    @property
    def situation(self) -> Situation:
        return self.percepts.situation
