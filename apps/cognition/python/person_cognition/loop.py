"""The cognition process.

Reads normalised observations, decides what Person should be trying to do and
which known strategy to try, and proposes one bounded skill at a time. It never
touches Minecraft: the only thing it can emit that has physical consequences is
a SkillInvocation, which the runtime is free to reject or replace.

Everything the process learns from is the outcome the runtime reports, and the
outcome says what actually ran.

Each observation crosses the epistemic boundary once (ADR 0026): the
environment profile turns it into a `PerceptualState`, the runtime's reports
in it are admitted as evidence and revise persistent beliefs, and a
`DecisionState` (percepts, beliefs, self-state, knowledge) is what goals,
planning, policy and appraisal read. Nothing below that point reads the raw
message, and nothing in this module knows which environment it is living in.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from person_config import CognitionSettings, ConfigError
from person_epistemics import (
    BeliefState,
    DecisionState,
    EvidenceRefused,
    ExperienceKey,
    Freshness,
    Intervention,
    Knowledge,
    PerceptualState,
    PlaceEstimate,
    PredictionQuery,
    Predictors,
    SelfState,
)
from person_persistence import (
    CanonicalEvent,
    ContinuityRecord,
    EventStore,
    Founding,
    IdentityError,
    LifeRecord,
    RootLock,
    SelfKnowledge,
    new_event,
)
from person_planner import evidence_needed, plan_for, relevant_skills
from person_policy import (
    CLOSED,
    DeterministicPolicyProvider,
    EnvelopeVerdict,
    EvidencePolicyProvider,
    NoCandidatesError,
    PolicyChoice,
    RoutineStatistics,
)
from person_protocol import (
    ProtocolValidator,
    SessionIdentity,
    encode_frame,
    envelope,
    protocol_validator,
)
from person_skills import SkillRegistry, skill_registry

from .affect import (
    TOLERANCE_RANGE,
    Affect,
    AffectRecord,
    Appraisal,
    appraise_goal,
    appraise_harm,
    appraise_outcome,
    appraise_project,
    appraise_search,
    appraise_threat,
)
from .continuity import OperationalView, plan_root, self_knowledge, session_payload
from .deliberation import (
    Capability,
    CognitiveModel,
    DeliberationContext,
    Deliberator,
    Outcome,
    Retrieval,
    build_context,
)
from .deliberation.arbiter import Arbiter
from .deliberation.habits import HabitTracker
from .deliberation.metareasoning import (
    ArbitrationRecord,
    Trigger,
    affect_bands,
    origin,
    prediction_key,
)
from .deliberation.model import TemplateModel
from .deliberation.proposal import DIRECTIONS as DELIBERATION_DIRECTIONS
from .effect_learning import (
    EffectBeliefs,
    Trial,
    admitted_to,
    classify,
    reliability_term,
)
from .environment import CognitiveEnvironment, load_environment
from .goals import CORE_GOAL_TYPES, Goal, GoalStack
from .hypotheses import (
    CausalHypothesis,
    ContrastProposer,
    HypothesisBook,
    InvestigationManager,
    Perceived,
    Proposer,
    ReasoningContext,
    admit,
    calm,
    design,
    evaluable_effects,
    hypothesis_term,
    perceived,
    vocabulary,
)
from .hypotheses.experiments import GOAL_TYPE as INVESTIGATE
from .hypotheses.generation import CONTEXT_TRIALS
from .interoception import BodyReading, Interoception, combined
from .memory import Cue, Memory, MemoryStore, Recalled
from .memory import encoding as remembering
from .memory.episodes import SUBJECTS, EpisodeDraft
from .memory.recall import MAX_CUE_SUBJECTS
from .prediction import PendingPrediction, build_payload
from .predictors import DeclaredEffectModel
from .projects import ProjectBook, ProjectManager
from .reducers import CognitiveReducers
from .reporting import LearningSummary
from .routines import (
    Routine,
    RoutineLibrary,
    SkillStep,
    candidate_from_routine,
    routine_from_plan,
)
from .search import NOT_FOUND, SEARCH_ROUTINE_ID, InformationSearch, revisit_budget
from .spatial import Spatial, SpatialMap

COGNITION_VERSION = "0.1.0"
MAX_CANDIDATES = 6
#: Unresolved hypotheses held at once about one skill's effect.
MAX_LIVE_HYPOTHESES = 3

#: Routines that are not strategies, so they are never scored as one.
UNSCORED_ROUTINES = frozenset({"r_idle_wait", SEARCH_ROUTINE_ID})

FAILURE_STATUSES = {"FAILED", "TIMED_OUT", "UNREACHABLE", "INVALIDATED", "DEATH", "DISCONNECTED"}
INTERRUPT_STATUSES = {"INTERRUPTED", "PREEMPTED"}


@dataclass
class ActiveRoutine:
    routine: Routine
    goal_id: str
    context_id: str
    steps: tuple[SkillStep, ...]
    index: int = 0
    started_tick: int = 0
    health_cost: float = 0.0
    resource_cost: float = 0.0
    elapsed_ticks: int = 0
    failure_modes: list[str] = field(default_factory=list)
    recovered: bool = False

    @property
    def finished(self) -> bool:
        return self.index >= len(self.steps)

    def current(self) -> SkillStep | None:
        return self.steps[self.index] if not self.finished else None


def _span(scores: tuple[float, float, float] | None) -> dict[str, float] | None:
    """A routine's score at the low, neutral and high tolerance, for the record."""
    if scores is None:
        return None
    low, neutral, high = scores
    return {"low": round(low, 6), "neutral": round(neutral, 6), "high": round(high, 6)}


class CognitionLoop:
    def __init__(
        self,
        *,
        settings: CognitionSettings | None = None,
        registry: SkillRegistry | None = None,
        write: Callable[[str], None] | None = None,
        log: Callable[[str], None] | None = None,
        evidence_directory: Path | None = None,
        validator: ProtocolValidator | None = None,
        affect_mode: str = "active",
        interoception: bool = True,
        environment: CognitiveEnvironment | None = None,
    ) -> None:
        self.settings = settings
        #: The environment profile Person lives in (ADR 0025): given, or found
        #: from the manifest of the environment SessionHello names.
        self.environment: CognitiveEnvironment | None = environment
        self._registry_given = registry is not None
        #: How far affect is switched on (ADR 0013); from Person's own
        #: configuration, never from the runtime.
        self.affect_mode = affect_mode
        self.registry = registry or skill_registry()
        self.validator = validator or protocol_validator()
        self._write = write or (lambda line: sys.stdout.write(line))
        self._log = log or (lambda line: sys.stderr.write(line + "\n"))
        self.statistics = RoutineStatistics()
        #: Every episode Person has encoded, rebuilt from the journal. The loop
        #: reaches it only through `self.memory`, never directly.
        self.memory_store = MemoryStore()
        #: Person's places and its last estimate of where it is, rebuilt from
        #: its own records. Reached through `self.spatial` only.
        self.spatial_map = SpatialMap()
        #: Who this Person is and how its sessions have run (ADR 0017),
        #: rebuilt from the journal. Cognition sees only `self_knowledge`.
        self.continuity = ContinuityRecord()
        #: Alive, awaiting a respawn, or terminated (ADR 0017, I3): its own
        #: axis, rebuilt from the journal alone.
        self.life = LifeRecord()
        #: ADR 0021: cooldowns, budgets and adopted goals, rebuilt from the
        #: journal; and what C3 holds between decisions.
        self.arbitration = ArbitrationRecord()
        self.arbiter = Arbiter(record=self.arbitration)
        #: The last observation Person perceived, as perception (ADR 0026):
        #: what it knew at a death, and what a deliberation is shown.
        self._last_percepts: PerceptualState[Any] | None = None
        #: The decision state of the current observation.
        self.decision: DecisionState[Any, BodyReading] | None = None
        #: Whether Person may afford to explore now, as the environment judges.
        self._verdict: EnvelopeVerdict = CLOSED
        #: Persistent fact beliefs (ADR 0026), rebuilt from `belief_revised`,
        #: and the ephemeral record of when each was last confirmed.
        self.belief_state = BeliefState()
        self.freshness = Freshness()
        #: The experience stream this session lives in (ADR 0025).
        self.experience: ExperienceKey | None = None
        #: Person's predictive models (ADR 0028): the declared-effect model
        #: once the environment is known.
        self.predictors = Predictors()
        self.self_knowledge: SelfKnowledge | None = None
        #: Whether the world is available to the body now (I2); all Person
        #: may know of its operational state.
        self.operational = OperationalView(world=None)
        #: Lifecycle events are written only for a founded root; a legacy
        #: root acquires no lifecycle history it never had (I2).
        self._lifecycle = False
        self._lock: RootLock | None = None
        #: Projects Person has taken up, rebuilt from its own records.
        self.project_book = ProjectBook()
        self.projects = ProjectManager(self.project_book)
        #: Person's affect, rebuilt from its own appraisals (ADR 0010).
        self.affect_record = AffectRecord()
        #: ADR 0014: the body as affect feels it, phasic and tonic. Off is a
        #: frozen R1.5 baseline for research, never Person's ordinary life.
        self.interoception_on = interoception
        self.affect = Affect(self.affect_record, mode=affect_mode, precise=interoception)
        self._felt_health: float | None = None
        self.interoception = Interoception()
        #: One observation step's causal events, appraised once at its end.
        self._pending_actions: list[tuple[str, Appraisal | None]] = []
        self._step_searches: list[tuple[str, str, Appraisal]] = []
        self._step_changes: list[tuple[str, dict[str, Any]]] = []
        self._goal_events_seen = 0
        #: Learned reliability of skill effects, active and shadow (ADR 0011).
        self.effect_beliefs = EffectBeliefs()
        #: Causal hypotheses, their evidence and investigations (ADR 0012).
        self.hypothesis_book = HypothesisBook()
        self.investigations = InvestigationManager(self.hypothesis_book.investigations)
        #: Who reasons about anomalies. Deterministic unless one is supplied;
        #: whatever it is, it only proposes, through the grounding gate.
        self.proposer: Proposer = ContrastProposer()
        #: The skills the runtime offered this session.
        self.offered: tuple[str, ...] = ()
        #: ADR 0020, C1: off unless configured; a model only if one is given.
        #: Nothing in this loop calls `request_deliberation` itself.
        self.deliberation_mode = settings.deliberation_mode if settings else "off"
        self.cognitive_model: CognitiveModel | None = None
        if settings and settings.deliberation_backend == "scripted":
            if settings.deliberation_script is None:
                raise ConfigError("deliberation backend 'scripted' needs scriptedAnswers")
            self.cognitive_model = TemplateModel.from_file(settings.deliberation_script)
        self.deliberation_audit: Path | None = (
            settings.output_directory / "deliberation-audit" if settings else None
        )
        #: What Person perceives now: weather, day phase, and the place it is sure of.
        self._now: Perceived | None = None
        self.reducers = CognitiveReducers(
            self.statistics,
            self.memory_store,
            self.spatial_map,
            self.project_book,
            self.affect_record,
            self.effect_beliefs,
            self.hypothesis_book,
            self.continuity,
            self.life,
            self.arbitration,
            beliefs=self.belief_state,
        )
        # ADR 0022: habit learning. record_only writes the shadow stream and
        # never acts (C4); active writes the active stream, whose promoted
        # habits answer their problems without a model (C5).
        self.arbiter.habits_mode = settings.deliberation_habits if settings else "off"
        if self.arbiter.habits_mode == "record_only":
            self.arbiter.tracker = HabitTracker(self.reducers.habits_shadow)
        elif self.arbiter.habits_mode == "active":
            self.arbiter.tracker = HabitTracker(self.reducers.habits_active)
            self.arbiter.active_book = self.reducers.habits_active
        if self.arbiter.tracker is not None:
            self.arbiter.tracker.on_breakdown = self.arbiter.habit_broke
        # ADR 0023: affect may advance System-2 escalation by one signal.
        self.arbiter.affect_arbitration = (
            settings.deliberation_affect_arbitration if settings else "off"
        )
        self.arbiter.detectors.early = self.arbiter.affect_arbitration != "off"
        self.arbiter.basis_for = self._habit_basis
        self.memory = Memory(self.memory_store, experience="unstarted")
        self.spatial = Spatial(self.spatial_map)
        #: Person's belief about where it is relative to home (C8).
        self.home = "unknown"
        self.goals = GoalStack()
        self.library = RoutineLibrary()
        self.summary = LearningSummary()
        self.identity: SessionIdentity | None = None
        self.episode_id = "ep_unstarted"
        self.learning_mode = "off"
        self.policy_revision = 0
        self.rng_seed: int | None = None
        self.store: EventStore | None = None
        self.evidence_directory = evidence_directory
        self.active: ActiveRoutine | None = None
        self.previous_event_id: str | None = None
        self.decision_counter = 0
        self.pending_decision_id: str | None = None
        self.running = True
        self.restore_notes: list[str] = []
        self.consecutive_failures: dict[str, int] = {}
        self._pending_choice: PolicyChoice | None = None
        #: One prediction at a time: the runtime runs one skill at a time.
        self.pending_prediction: PendingPrediction | None = None
        self.prediction_errors: list[dict[str, Any]] = []
        self._last_state: dict[str, float] = {}
        #: The one search in progress, if any. Ephemeral: never persisted.
        self.search: InformationSearch | None = None
        #: Goals blocked by a search that found nothing, the evidence that
        #: would reopen them, and the cognitive place the search was made from.
        #: Not a record of absence: the moment any of it is seen, or Person
        #: believes it is somewhere else, the goal is live again.
        self.unfound: dict[str, tuple[tuple[str, ...], str | None]] = {}

    # ------------------------------------------------------------------ utils

    def _send(self, message: dict[str, Any]) -> None:
        valid, diagnostics = self.validator.validate(message)
        if not valid:
            # Refusing to emit an invalid message is the cognition-side half of
            # the contract; the runtime would drop it anyway.
            self._log(f"cognition refused to send invalid {message.get('type')}: {diagnostics}")
            return
        self._write(encode_frame(message))

    def _envelope(self, message_type: str, tick: int) -> dict[str, Any]:
        identity = self.identity or SessionIdentity("unknown", "0" * 8, "unknown")
        return envelope(identity, message_type, tick)

    def _record(
        self,
        event_type: str,
        tick: int,
        payload: dict[str, Any],
        decision_id: str | None = None,
        timestamp: str | None = None,
    ) -> CanonicalEvent | None:
        if self.store is None or self.identity is None or self.experience is None:
            return None
        event = new_event(
            person_id=self.identity.person_id,
            world_id=self.identity.world_id,
            session_id=self.identity.session_id,
            episode_id=self.episode_id,
            decision_id=decision_id,
            tick=tick,
            policy_revision=self.policy_revision,
            experience=self.experience,
            event_type=event_type,
            payload=payload,
            previous_event_id=self.previous_event_id,
            timestamp=timestamp,
        )
        self.store.append(event, self.reducers)
        self.previous_event_id = event.event_id
        return event

    # ------------------------------------------------------------ deliberation

    def deliberation_context(
        self,
        reason: str,
        refs: tuple[str, ...] = (),
        recalled: tuple[Recalled, ...] = (),
    ) -> DeliberationContext:
        """The bounded context a model would be shown now (ADR 0020).

        Reads projections only: it recalls nothing, records nothing and
        changes nothing, so building it has no effect on Person. A request
        may pass in `recalled`, its own request-local recall, which joins
        working memory in this context and nowhere else.
        """
        known = self.self_knowledge
        here = self.spatial.here()
        working = [
            {
                "kind": held.episode.kind,
                "subjects": list(held.episode.subjects),
                "details": dict(held.episode.details),
                "place": held.episode.place_id,
                "source": held.episode.provenance.source,
            }
            for held in self.memory.working.items()
        ]
        held_ids = {held.episode.memory_id for held in self.memory.working.items()}
        working += [
            {
                "kind": item.episode.kind,
                "subjects": list(item.episode.subjects),
                "details": dict(item.episode.details),
                "place": item.episode.place_id,
                "source": item.episode.provenance.source,
            }
            for item in recalled
            if item.episode.memory_id not in held_ids
        ]
        beliefs = [
            {
                "skill": skill,
                "fact": fact,
                "estimate": round(belief.estimate or 0.0, 2),
                "strength": round(belief.strength, 2),
            }
            for (context, skill, fact), belief in sorted(
                self.effect_beliefs.tables["active"].items()
            )
            if context == self.experience_key and belief.estimate is not None
        ]
        hypotheses = [
            {
                key: value
                for key, value in hypothesis.to_json().items()
                if key in ("condition", "intervention", "outcome", "lifecycle")
            }
            for _, hypothesis in sorted(self.hypothesis_book.hypotheses["active"].items())
        ]
        goals = [
            {
                "goal_type": goal.goal_type,
                "priority": round(goal.priority, 1),
                "active": goal.goal_id == self.goals.active_id,
            }
            for goal in self.goals.ranked
        ]
        projects = [
            {
                "kind": project.kind,
                "status": project.status,
                "interruptions": project.interruptions,
                "blocks": project.blocks,
            }
            for project in self.project_book.projects()
        ]
        recent = [
            {
                "skill": error.get("executed_skill"),
                "requested": error.get("requested_skill"),
                "status": error.get("status"),
                "emergency": bool(error.get("emergency")),
                "severity": error.get("severity"),
                "expected": [effect.get("fact") for effect in error.get("expected", [])][:4],
                "unexplained": list(error.get("unexplained", []))[:4],
            }
            for error in self.prediction_errors[-8:]
        ]
        capabilities = [
            Capability(
                skill=spec.id,
                summary=spec.summary,
                effects=tuple(effect.fact for effect in spec.expected_effects),
            )
            for spec in (self.registry.get(skill) for skill in sorted(self.offered))
            if not spec.emergency
        ]
        return build_context(
            reason=reason,
            request_refs=refs,
            self_knowledge=(
                {"name": known.name, "designation": known.designation, "last_gap": known.last_gap}
                if known is not None
                else None
            ),
            world_available=(
                None if self.operational.world is None else self.operational.world == "available"
            ),
            situation=(
                self.environment.situation(self._last_percepts)
                if self.environment is not None
                else []
            ),
            place=({"place_id": here.place_id, "confidence": here.confidence} if here else None),
            working_memory=working,
            home_relation=self.spatial.home_relation()[0],
            # Person's own labels, for exactly the places this context cites.
            place_labels={
                str(place_id): label
                for place_id in {here.place_id if here else None}
                | {str(item["place"]) for item in working if item["place"] is not None}
                if place_id is not None
                and (label := self.spatial.label_of(str(place_id))) is not None
            },
            beliefs=beliefs,
            hypotheses=hypotheses,
            goals=goals,
            projects=projects,
            recent=recent,
            capabilities=capabilities,
            vocabulary={
                "goal_types": self.goal_types,
                "project_kinds": tuple(sorted(self.projects.by_kind)),
                "facts": tuple(sorted(self.registry.facts)),
                "directions": DELIBERATION_DIRECTIONS,
            },
        )

    def _metareasoning(self) -> bool:
        return self.deliberation_mode != "off" and self.cognitive_model is not None

    def _metareason(self, state: dict[str, float], tick: int) -> None:
        """One C3 step (ADR 0021): consume, keep, maybe ask. Never waits."""
        if not self._metareasoning() or self.identity is None:
            self.arbiter.pending.clear()
            return
        # `project_reconsideration` keeps its vocabulary but has no detector
        # yet: "one block short of abandonment" has not shown that System 2 is
        # warranted, and it overlaps repeated_failure and no_viable_plan.

        def record(event_type: str, payload: dict[str, Any]) -> None:
            self._record(event_type, tick, payload)

        self.arbiter.step(
            mode=self.deliberation_mode,
            deliberator=Deliberator(
                mode=self.deliberation_mode,
                model=self.cognitive_model,
                record=record,
                audit_directory=self.deliberation_audit,
            ),
            record=record,
            state=state,
            now=self.memory.now,
            session=self.identity.session_id,
            life_epoch=self.life.deaths + self.life.respawns,
            alive=self.life.status == "alive",
            world_available=self.operational.world != "unavailable",
            goals=self.goals,
            projects=self.project_book,
            registry=self.registry,
            goal_types=self.goal_types,
            context_for=self._trigger_context,
            decision=self.decision_counter,
            failures=lambda goal_id: self.consecutive_failures.get(goal_id, 0),
        )
        for adopted, why in self.arbiter.ended:
            if why != "satisfied":
                self.goals.abandon(adopted.goal_id, tick, reason=f"deliberation_{why}")
                continue
            self.goals.conclude(adopted.goal_id, tick, reason="deliberation_satisfied")
            prior = self.arbiter.source_retry(adopted, self.goals)
            if prior is None or adopted.source_goal_id is None:
                continue
            # One retry, granted once: the remedy is satisfied, so the goal
            # Person gave up on is tried again. A failure blocks it again.
            source = adopted.source_goal_id
            self.goals.reopen(source, tick)
            self.unfound.pop(source, None)
            if prior == "repeated_routine_failure":
                self.consecutive_failures[source] = 2
            if adopted.via == "habit":
                # The same bounded retry, granted by Person's recovery
                # machinery, never by the habit or a model (C5).
                record(
                    "habit_source_retry",
                    {
                        "template_id": adopted.template_id,
                        "habit_invocation_id": adopted.deliberation_id,
                        "source_goal_id": source,
                        "source_goal_type": adopted.source_goal_type,
                        "source_goal_epoch": adopted.source_created_at,
                        "prior_block_reason": prior,
                        "experienced_tick": self.memory.now,
                    },
                )
            else:
                record(
                    "deliberation_source_retry",
                    {
                        "deliberation_id": adopted.deliberation_id,
                        "source_goal_id": source,
                        "source_goal_type": adopted.source_goal_type,
                        "prior_block_reason": prior,
                        "experienced_tick": self.memory.now,
                    },
                )
        self.arbiter.ended.clear()

    def _recorder(self, tick: int) -> Callable[[str, dict[str, Any]], None]:
        def record(event_type: str, payload: dict[str, Any]) -> None:
            self._record(event_type, tick, payload)

        return record

    def _habit_basis(self, trigger: Trigger) -> dict[str, Any]:
        """What a habit's context signature is built from, as Person perceives
        it when the trigger fires."""
        trigger = origin(trigger)
        here = self.spatial.here()
        source = self.goals.entries.get(trigger.source_goal_id or "")
        source_type = (
            trigger.key
            if trigger.kind in ("repeated_failure", "no_viable_plan")
            else source.goal_type
            if source is not None
            else None
        )
        return {
            "observation": (
                self.environment.signature_basis(self._last_percepts)
                if self.environment is not None
                else None
            ),
            "place": {"place_id": here.place_id, "confidence": here.confidence} if here else None,
            "source_goal_type": source_type,
        }

    #: The memory kinds a deliberative recall may consult: the episodic
    #: evidence problem solving uses, and harm for emergencies.
    DELIBERATIVE_KINDS: tuple[str, ...] = ("perceived", "searched", "acted")
    EMERGENCY_KINDS: tuple[str, ...] = ("perceived", "searched", "acted", "endangered", "hurt")

    def _deliberative_cue(self, trigger: Trigger) -> tuple[frozenset[str], tuple[str, ...]]:
        """What Person recalls when it thinks about this problem: derived from
        the problem alone, never chosen by a model."""
        habit_facts: list[str] = []
        if trigger.kind == "habit_breakdown":
            template = (
                self.reducers.habits_active.templates.get(trigger.key)
                if self.reducers.habits_active
                else None
            )
            habit_facts = [str(fact) for fact, _ in template.desired] if template else []
        problem = origin(trigger)
        facts: list[str] = list(habit_facts)
        kinds = self.DELIBERATIVE_KINDS
        if problem.kind in ("repeated_failure", "no_viable_plan"):
            goal = self.goals.entries.get(problem.source_goal_id or "")
            if goal is not None:
                # The resources any relevant way of achieving this goal
                # depends on, whether or not a plan exists right now: what
                # Person knows about the problem, not just what it lacks.
                specs = [self.registry.get(skill) for skill in self.registry.ids]
                facts += [
                    condition.fact
                    for spec in relevant_skills(goal.completion_condition, specs)
                    for condition in spec.preconditions
                    if condition.fact in self.registry.vocabulary.evidence_facts
                ]
        elif problem.kind == "repeated_prediction_error":
            facts += problem.key.split(":", 1)[1].split("+") if ":" in problem.key else []
        elif problem.kind == "emergency_recurrence":
            # As the endangerment was encoded (memory encoding, ADR 0007).
            about = self._environment().emergency_subjects(problem.key)
            return frozenset({"danger", *about}), self.EMERGENCY_KINDS
        subjects = sorted(self._evidence_subjects(facts) & SUBJECTS)
        return frozenset(subjects[:MAX_CUE_SUBJECTS]), kinds

    def _trigger_context(self, trigger: Trigger) -> tuple[DeliberationContext, frozenset[str]]:
        """The context for a trigger, and the references that are its problem.

        Preparing a request recalls once, for this thought only: one bounded,
        deterministic cue derived from the problem, through the ordinary
        ranking and limit, never into working memory (ADR 0020, as amended).
        """
        subjects, kinds = self._deliberative_cue(trigger)
        recalled = (
            self.memory.recall_for_deliberation(Cue.about(*subjects, purpose="goal", kinds=kinds))
            if subjects
            else ()
        )
        context = replace(
            self.deliberation_context(trigger.kind, recalled=recalled),
            retrieval=Retrieval(
                cue_subjects=tuple(sorted(subjects)),
                cue_kinds=tuple(sorted(kinds)),
                memory_ids=tuple(item.episode.memory_id for item in recalled),
            ),
        )
        # A habit breakdown cites the problem its habit answered.
        trigger = origin(trigger)
        refs: set[str] = set()
        for ref, (section, item) in context.refs.items():
            if trigger.kind == "emergency_recurrence":
                if section == "memories" and item.get("details", {}).get("trigger") == trigger.key:
                    refs.add(ref)
                if section == "recent" and item.get("emergency"):
                    refs.add(ref)
            elif trigger.kind in ("repeated_failure", "no_viable_plan"):
                if section == "goals" and item.get("goal_type") == trigger.key:
                    refs.add(ref)
            elif trigger.kind == "repeated_prediction_error":
                if section == "recent" and item.get("skill") == trigger.key.split(":")[0]:
                    refs.add(ref)
            elif trigger.kind == "project_reconsideration":
                if section == "projects" and item.get("kind") == trigger.key:
                    refs.add(ref)
        return context, frozenset(refs)

    def request_deliberation(self, reason: str, refs: tuple[str, ...] = ()) -> Outcome | None:
        """Deliberate now and record it, reaching nothing (ADR 0020, C1).

        For tests and offline evaluation only: in C1 nothing in the decision
        loop calls this, because even a call that changes nothing spends the
        world's time. With the mode off, or no model, nothing happens at all.
        """
        if self.deliberation_mode == "off" or self.cognitive_model is None:
            return None
        tick = self._last_percepts.tick if self._last_percepts else 0
        deliberator = Deliberator(
            mode=self.deliberation_mode,
            model=self.cognitive_model,
            record=lambda event_type, payload: self._record(event_type, tick, payload),
            audit_directory=self.deliberation_audit,
        )
        return deliberator.deliberate(
            self.deliberation_context(reason, refs), experienced_tick=self.memory.now
        )

    def _policy(self) -> DeterministicPolicyProvider | EvidencePolicyProvider:
        if self.learning_mode == "off" and self.settings is None:
            return DeterministicPolicyProvider(self.policy_revision)
        return EvidencePolicyProvider(
            self.statistics,
            experience=self.experience_key,
            learning_mode=self.learning_mode,
            minimum_support=self.settings.minimum_support if self.settings else 3,
            exploration_bonus=self.settings.exploration_bonus if self.settings else 0.15,
            policy_revision=self.policy_revision,
        )

    # -------------------------------------------------------------- dispatch

    def handle(self, message: dict[str, Any]) -> None:
        handler = {
            "SessionHello": self.on_session_hello,
            "WorldAvailability": self.on_world_availability,
            "LifeEvent": self.on_life_event,
            "Observation": self.on_observation,
            "ValidationDecision": self.on_validation,
            "SkillStarted": self.on_skill_started,
            "SkillOutcome": self.on_skill_outcome,
            "EmergencyEvent": self.on_emergency,
            "EpisodeEvent": self.on_episode_event,
        }.get(str(message.get("type")))
        if handler is None:
            self._log(f"cognition ignored unexpected message type {message.get('type')}")
            return
        handler(message)

    # ---------------------------------------------------------------- session

    def on_session_hello(self, message: dict[str, Any]) -> None:
        self.identity = SessionIdentity(
            person_id=message["personId"],
            session_id=message["sessionId"],
            world_id=message["worldId"],
        )
        self.learning_mode = message["learningMode"]
        self.experience = ExperienceKey.from_message(message["experience"])
        self.policy_revision = message["policyRevision"]
        self.rng_seed = message["rngSeed"]
        directory = self.evidence_directory or Path(message["evidenceDirectory"])
        if self.settings is not None:
            self.settings.cross_check(
                learning_mode=self.learning_mode,
                evidence_directory=message["evidenceDirectory"],
                environment_kind=self.experience.environment_kind,
                embodiment_kind=self.experience.embodiment_kind,
            )
        self._enter_environment(self.experience.environment_kind)
        if message["skillLibraryRevision"] != self.registry.revision:
            self._log(
                "skill library revision mismatch: runtime "
                f"{message['skillLibraryRevision']} vs cognition {self.registry.revision}"
            )
        self.store = EventStore(
            directory,
            snapshot_every=self.settings.snapshot_every_events if self.settings else 50,
        )
        # Whose root is this (ADR 0017)? One process at a time; a founded root
        # opens only as its own Person; an empty one is founded first.
        self._lock = RootLock(directory).acquire()
        plan = plan_root(
            self.store.first_event(),
            person_id=self.identity.person_id,
            name=self.settings.identity_name if self.settings else None,
            designation=self.settings.identity_designation if self.settings else None,
            now=message["timestamp"],
        )
        existing = self.store.first_event()
        founded = (
            Founding.from_payload(existing.payload)
            if existing is not None and existing.type == "person_founded"
            else None
        )
        self.store.identity = self._identity_binding(founded)
        report = self.store.restore(self.reducers)
        if self.life.status == "terminated":
            # A terminated Person is never resumed, whatever the configuration
            # now says (ADR 0017, I3). Its evidence stays readable.
            self.close()
            raise IdentityError(
                f"{self.identity.person_id} is terminated; its evidence is read-only and "
                "it cannot be resumed"
            )
        # What this session learns of the gap, before it writes anything: a
        # Person's very first session has no gap to learn.
        session = session_payload(self.continuity, self.identity.session_id, message["timestamp"])
        if plan.found is not None:
            # An empty root: the founding is its first event, before any other.
            self._record(
                "person_founded",
                message["tick"],
                plan.found.payload(),
                timestamp=message["timestamp"],
            )
            self.store.identity = self._identity_binding(plan.found)
        self.self_knowledge = self_knowledge(self.continuity, self.identity.person_id, session)
        self._lifecycle = not plan.legacy
        self.operational = OperationalView(world=None)
        # Working memory starts empty: the past comes back only when cued.
        self.memory = Memory(self.memory_store, experience=self.experience_key)
        # Waking where it last knew it was, less sure of it: nothing about the
        # body's actual location is available, or used.
        self.spatial = Spatial(self.spatial_map)
        # Projects persist; which of them still apply is checked when Person
        # next observes the world, not assumed.
        self.projects = ProjectManager(self.project_book, self._templates())
        # Affect persists too, and settles only as experienced time passes.
        self.affect = Affect(
            self.affect_record, mode=self.affect_mode, precise=self.interoception_on
        )
        # So do hypotheses and investigations; an open investigation resumes.
        self.investigations = InvestigationManager(self.hypothesis_book.investigations)
        self.offered = tuple(str(skill) for skill in message["skillIds"])
        self.restore_notes = list(report.notes)
        self.previous_event_id = self.store.last_event_id
        if self._lifecycle:
            self._record(
                "session_started", message["tick"], session, timestamp=message["timestamp"]
            )
        # A goal a deliberation led to never outlives its session (ADR 0021).
        self.arbiter.end_carried_over(
            lambda event_type, payload: self._record(event_type, message["tick"], payload),
            self.memory.now,
        )
        self.policy_revision = max(self.policy_revision, self.store.policy_revision)
        for note in report.notes:
            self._log(f"evidence restore: {note}")
        self._send(
            {
                **self._envelope("CognitionReady", message["tick"]),
                "type": "CognitionReady",
                "cognitionVersion": COGNITION_VERSION,
                "policyRevision": self.policy_revision,
                "learningMode": self.learning_mode,
                "restoredEvents": report.replayed_events,
                "restoredRoutines": len(self.statistics.routines),
                "snapshotTick": report.snapshot_tick,
                "lifeStatus": self.life.status,
            }
        )

    def on_episode_event(self, message: dict[str, Any]) -> None:
        self.episode_id = message["episodeId"]
        self._record(
            "episode_started" if message["phase"] == "started" else "episode_ended",
            message["tick"],
            {
                "reason_codes": message["reasonCodes"],
                "rng_seed": message["rngSeed"],
                "experience": dict(message["experience"]),
                "learning_mode": self.learning_mode,
                "affect_mode": self.affect_mode,
                "interoception": "on" if self.interoception_on else "off",
                "experienced_ticks": self.memory.now,
                "self_estimate": self.spatial.estimate.to_json(),
            },
        )
        if message["phase"] == "ended":
            self._settle_prediction(None, message["tick"])
            self._conclude_search("abandoned", message["tick"], reason="episode_ended")
            self._finish_routine("INTERRUPTED", message["tick"], reason="episode_ended")
            if self.interoception_on:
                self._appraise_step(message["tick"])
            if self.store is not None and self._lifecycle:
                self._record(
                    "session_ended",
                    message["tick"],
                    {
                        "session_id": self.identity.session_id if self.identity else None,
                        "reason": "episode_ended",
                        "reasons": list(message["reasonCodes"])[:8],
                    },
                    timestamp=message["timestamp"],
                )
            if self.store is not None:
                self.store.write_snapshot(self.reducers)
                self.summary.write(
                    self.store.directory,
                    statistics=self.statistics,
                    episode_id=self.episode_id,
                    learning_mode=self.learning_mode,
                    experience=self.experience_key,
                    policy_revision=self.policy_revision,
                    goals=self.goals,
                    restore_notes=self.restore_notes,
                )
            self.close()
            self.running = False

    # ------------------------------------------------------------ observation

    def on_observation(self, message: dict[str, Any]) -> None:
        self._observe(message)
        if self.interoception_on:
            # Everything this observation brought about, appraised once per
            # causal event (ADR 0014).
            self._appraise_step(message["tick"])

    def _observe(self, message: dict[str, Any]) -> None:
        tick = message["tick"]
        environment = self._environment()
        # The epistemic boundary (ADR 0026): the message is read here, once,
        # as perception, and nothing below reads it again.
        percepts = environment.perceive(message)
        self._last_percepts = percepts
        # Where Person is comes first: its sense of place decides whether it
        # believes it is home, and what it notices is remembered there.
        self.spatial.feel(percepts.self_motion, frozenset(environment.noticed(percepts)))
        self.home, _ = self.spatial.home_relation()
        self._now = perceived(environment.conditions(percepts), self.spatial.here())
        self._revise_beliefs(percepts, tick)
        decision = self._decision_state(percepts)
        self.decision = decision
        self._verdict = environment.envelope(decision)
        state = environment.planning_facts(decision)
        context_id = environment.decision_context(decision).identifier()
        # The first thing a new observation is good for is settling whatever
        # the last skill claimed it would do.
        self._settle_prediction(state, tick)
        self._last_state = dict(state)
        self._remember(
            self.memory.experience(
                tick, environment.health(percepts), percepts.message_id, environment.seen(percepts)
            ),
            tick,
        )
        if self.interoception_on:
            self._sense_body(decision.self_state.body, tick)
        else:
            self._appraise_body(percepts, tick)

        self._reopen_unfound(state, tick)
        self._deliberate_projects(decision, state, tick)
        self._deliberate_investigations(decision, state, tick)
        self._metareason(state, tick)
        proposals = environment.propose_goals(decision, state, tick)
        project_goal = self.projects.goal(state, tick)
        if project_goal is not None:
            proposals.append(project_goal)
        trial_goal = self._trial_goal(state, tick)
        if trial_goal is not None:
            proposals.append(trial_goal)
        self._retire_stale_trials(trial_goal, tick)
        # Affect adjusts the candidates that already exist, within a tight
        # bound, and records how much; it adds none and removes none.
        proposals = [self._biased(proposal) for proposal in proposals]
        # A goal a deliberation led to comes after affect: its priority is the
        # one Person assigned it (ADR 0021), and affect adjusts none of it.
        adopted = self.arbiter.adopted_goal(tick)
        if adopted is not None:
            proposals.append(adopted)
        goal = self.goals.update(proposals, state, tick)
        changes = self.projects.track(self.goals, state, self.memory.now)
        self._record_changes(changes, tick)
        if self.interoception_on:
            self._step_changes.extend(changes)
        else:
            self._appraise_progress(changes, tick)
        self._record_changes(self.investigations.track(self.goals, trial_goal), tick)
        if goal is None:
            goal = self._idle_goal(tick)
            self.goals.update([goal], state, tick)
            goal = self.goals.active or goal
        if self.search is not None and self.search.goal_id != goal.goal_id:
            self._conclude_search("abandoned", tick, reason="goal_changed")

        if self.active is not None and (
            self.active.goal_id != goal.goal_id or self.active.finished
        ):
            self._finish_routine(
                "SUCCESS" if self.active.finished else "INTERRUPTED",
                tick,
                reason="goal_changed" if not self.active.finished else "routine_complete",
            )

        if self.active is None and not self._start_routine(decision, state, context_id, goal, tick):
            return
        assert self.active is not None

        step = self.active.current()
        if step is None:
            self._finish_routine("SUCCESS", tick, reason="routine_complete")
            if not self._start_routine(decision, state, context_id, goal, tick):
                return
            step = self.active.current() if self.active else None
        if step is None:
            self._emit_idle(decision, goal, context_id, tick)
            return

        spec = self.registry.get(step.skill_id)
        if not spec.applicable(state):
            # The world moved on. Abandon the routine rather than sending a
            # proposal the runtime would only reject.
            self.active.failure_modes.append("preconditions_changed")
            self._finish_routine("INVALIDATED", tick, reason="preconditions_changed")
            if not self._start_routine(decision, state, context_id, goal, tick):
                return
            step = self.active.current() if self.active else None
            if step is None:
                self._emit_idle(decision, goal, context_id, tick)
                return
            spec = self.registry.get(step.skill_id)

        self._emit_decision(decision, goal, context_id, step, spec, tick)

    def _idle_goal(self, tick: int) -> Goal:
        return self._environment().idle_goal(tick)

    # ----------------------------------------------------- epistemic state

    def _revise_beliefs(self, percepts: PerceptualState[Any], tick: int) -> None:
        """Admit what the observation reports as evidence, and revise beliefs.

        Only the environment's admissible reports become evidence; a replayed
        stream admits none. Each revision is journalled and the store is
        rebuilt from the journal; a belief confirmed unchanged is refreshed in
        the ephemeral overlay and journals nothing.
        """
        environment = self._environment()
        now = self.memory.time_at(percepts.tick)
        try:
            evidence = environment.belief_evidence(percepts, now)
        except EvidenceRefused:
            return
        for revision in self.belief_state.revise(evidence, self.freshness):
            event = self._record("belief_revised", tick, revision.payload())
            if event is None:
                # No continuity root to journal to: the belief is still held.
                self.belief_state.admit_revision(revision)

    def _decision_state(self, percepts: PerceptualState[Any]) -> DecisionState[Any, BodyReading]:
        """The views one decision is made from (ADR 0026). Composed, not stored:
        each part of the self-state is read from the mechanism that owns it."""
        environment = self._environment()
        here = self.spatial.here()
        affect = self.affect.state
        return DecisionState(
            percepts=percepts,
            beliefs=self.belief_state.view(percepts.situation, self.freshness),
            self_state=SelfState(
                body=environment.body(percepts),
                life=self.life.status,
                world_available=(
                    None
                    if self.operational.world is None
                    else self.operational.world == "available"
                ),
                place=PlaceEstimate(here.place_id, here.confidence) if here is not None else None,
                home_relation=self.home,
                affect=(
                    None
                    if self.affect_mode == "off"
                    else {
                        "valence": affect.valence,
                        "unease": affect.unease,
                        "control": affect.control,
                    }
                ),
                capabilities=self.offered,
                identity=self.self_knowledge,
            ),
            knowledge=Knowledge(skills=self.registry, facts=self.registry.facts),
        )

    def _environment(self) -> CognitiveEnvironment:
        if self.environment is None:
            raise RuntimeError("no environment profile: SessionHello has not named one")
        return self.environment

    def _enter_environment(self, kind: str) -> None:
        """Take up the environment SessionHello names, through its manifest."""
        if self.environment is None or self.environment.kind != kind:
            self.environment = load_environment(kind)
        if not self._registry_given:
            self.registry = self.environment.skills()
        self.arbiter.signature = self.environment.context_signature
        self.predictors = Predictors([DeclaredEffectModel(self.registry, kind)])

    def _templates(self) -> tuple[Any, ...]:
        return self.environment.project_templates if self.environment is not None else ()

    @property
    def experience_key(self) -> str:
        return self.experience.key if self.experience is not None else "unstarted"

    @property
    def goal_types(self) -> tuple[str, ...]:
        if self.environment is None:
            return CORE_GOAL_TYPES
        return self.environment.goal_types

    def _evidence_subjects(self, facts: Any) -> frozenset[str]:
        if self.environment is None:
            return frozenset()
        return self.environment.evidence_subjects(tuple(facts))

    def _start_routine(
        self,
        decision: DecisionState[Any, BodyReading],
        state: dict[str, float],
        context_id: str,
        goal: Goal,
        tick: int,
    ) -> bool:
        # An experiment's trial may be pursued only by the intervention it
        # tests; anything else would not be the experiment.
        method = self.investigations.method(goal.goal_id)
        plans = plan_for(
            state,
            goal.completion_condition,
            registry=self.registry,
            limit=MAX_CANDIDATES,
            allowed_skills=(method,) if method else None,
            recovery=(
                tuple(self.registry.vocabulary.recovery_skills)
                if goal.planning_profile == "recovery"
                else ()
            ),
        )
        plans = [plan for plan in plans if plan.steps]
        if self._metareasoning() and goal.source != "maintenance":
            # No plan is ordinary while information search can still find what
            # is missing; it is a reason to think only once search has given
            # up on this goal (ADR 0021).
            exhausted = not plans and goal.goal_id in self.unfound
            if exhausted:
                self.arbiter.raw_signal(
                    f"no_viable_plan:{goal.goal_type}", self.memory.now, self._recorder(tick)
                )
            self.arbiter.raise_trigger(
                self.arbiter.detectors.planned(
                    goal.goal_type, goal.goal_id, not exhausted, goal.priority
                )
            )
        if not plans:
            return self._seek(decision, state, context_id, goal, tick)
        if self.search is not None:
            # The planner found a way from what Person now perceives. That is
            # the whole test of whether the looking was enough.
            self._conclude_search("satisfied", tick)
        routines = [self.library.add(routine_from_plan(goal.goal_type, plan)) for plan in plans]
        candidates = [
            candidate_from_routine(routine, self.library, state, self.registry)
            for routine in routines
        ]
        try:
            choice = self._policy().propose(
                self._verdict,
                goal,
                candidates,
                context_id,
                tolerance=self.affect.tolerance(),
                reliability=self._reliability(),
                hypotheses=self._hypotheses(),
                tolerance_bounds=TOLERANCE_RANGE,
            )
        except NoCandidatesError:
            self.goals.block(goal.goal_id, "no_candidate_routine", tick)
            self._emit_idle(decision, goal, context_id, tick)
            return False
        chosen = next(
            (routine for routine in routines if routine.routine_id == choice.routine_id),
            routines[0],
        )
        self.active = ActiveRoutine(
            routine=chosen,
            goal_id=goal.goal_id,
            context_id=context_id,
            steps=tuple(self.library.expand(chosen)),
            started_tick=tick,
        )
        self._pending_choice = choice
        self._record(
            "routine_selected",
            tick,
            {
                "routine_id": chosen.routine_id,
                "routine_name": chosen.name,
                "goal_id": goal.goal_id,
                "goal_type": goal.goal_type,
                "context_id": context_id,
                "steps": [step.label() for step in self.active.steps],
                "learned_or_fallback": choice.learned_or_fallback,
                "confidence": choice.confidence,
                "reason_codes": list(choice.reason_codes),
                "shadow_routine_id": choice.shadow_routine_id,
                # For research (ADR 0013): the tolerance affect supplied,
                # whether the ranking decided, and each score across the
                # tolerance range. Nothing reads them back.
                "tolerance": self.affect.tolerance(),
                "scored_choice": choice.scored_choice,
                "candidates": [
                    {
                        "routine_id": scored.candidate.routine_id,
                        "score": round(scored.score, 6),
                        "learned_effect": scored.learned_effect,
                        "hypothesis_effect": scored.hypothesis_effect,
                        "attempts": scored.counts.attempts,
                        "successes": scored.counts.successes,
                        "score_at_tolerance": _span(scored.tolerance_scores),
                    }
                    for scored in choice.candidates
                ],
            },
        )
        self.summary.note_selection(choice)
        return True

    def _emit_decision(
        self,
        decision: DecisionState[Any, BodyReading],
        goal: Goal,
        context_id: str,
        step: SkillStep,
        spec: Any,
        tick: int,
    ) -> None:
        assert self.active is not None
        self.decision_counter += 1
        decision_id = _decision_uuid(self.decision_counter, self.identity)
        self.pending_decision_id = decision_id
        choice: PolicyChoice = self._pending_choice or self._policy().propose(
            self._verdict,
            goal,
            [candidate_from_routine(self.active.routine, self.library, {}, self.registry)],
            context_id,
        )

        self._record(
            "goal_selected",
            tick,
            {
                "goal_id": goal.goal_id,
                "goal_type": goal.goal_type,
                "priority": goal.priority,
                "base_priority": goal.base_priority
                if goal.base_priority is not None
                else goal.priority,
                "affect_bias": goal.affect_bias,
                # Every legitimate candidate this choice was made from, for
                # research (ADR 0013). Nothing reads it back.
                "candidates": [self._basis(entry) for entry in self.goals.ranked],
                "context_id": context_id,
                "reason_codes": list(goal.reason_codes),
                "stack": [entry["goalId"] for entry in self.goals.as_messages()],
            },
            decision_id,
        )

        self._send(
            {
                **self._envelope("GoalDecision", tick),
                "type": "GoalDecision",
                "decisionId": decision_id,
                "goal": (self.goals.active or goal).as_message(),
                "reasonCodes": list(goal.reason_codes)[:32],
                "stack": self.goals.as_messages()[:32],
            }
        )
        self._send(
            {
                **self._envelope("PolicyDecision", tick),
                "type": "PolicyDecision",
                "decisionId": decision_id,
                "goalId": goal.goal_id,
                "contextId": context_id,
                "routineId": self.active.routine.routine_id,
                "routineName": self.active.routine.name,
                "steps": [item.skill_id for item in self.active.steps][:32],
                "confidence": round(min(1.0, max(0.0, choice.confidence)), 6),
                "reasonCodes": list(choice.reason_codes)[:32],
                "evidenceRefs": list(choice.evidence_refs)[:64],
                "policyRevision": self.policy_revision,
                "learnedOrFallback": choice.learned_or_fallback,
                "candidates": [
                    {
                        "routineId": scored.candidate.routine_id,
                        "routineName": scored.candidate.name,
                        "score": round(scored.score, 6),
                        "attempts": scored.counts.attempts,
                        "successes": scored.counts.successes,
                        "meanSuccess": round(scored.counts.posterior_mean, 6),
                    }
                    for scored in choice.candidates[:32]
                ],
                "shadowRoutineId": choice.shadow_routine_id,
            }
        )
        # The state a prediction is measured against is the one the planner
        # reasoned over, captured before anything physical happens.
        experiment = self.investigations.hypothesis_for(goal.goal_id)
        parameters = step.parameter_map or spec.default_parameters()
        predictions = self.predictors.predict(
            PredictionQuery(
                state=dict(self._last_state),
                intervention=Intervention(step.skill_id, parameters),
                belief_version=self.belief_state.version,
            )
        )
        self.pending_prediction = PendingPrediction(
            decision_id=decision_id,
            context_id=context_id,
            routine_id=self.active.routine.routine_id,
            goal_id=goal.goal_id,
            requested_skill=step.skill_id,
            state_before=dict(self._last_state),
            tick=tick,
            perceived=self._now.to_json() if self._now is not None else None,
            experiment=experiment
            if step.skill_id == self.investigations.method(goal.goal_id)
            else None,
            predictions=predictions,
        )
        # ADR 0023: the affect this skill's outcome will be judged against is
        # the affect before that outcome is appraised.
        state = self.affect.state
        self.arbiter.affect_snapshot = affect_bands(state.unease, state.control)
        self._send(
            {
                **self._envelope("SkillInvocation", tick),
                "type": "SkillInvocation",
                "decisionId": decision_id,
                "goalId": goal.goal_id,
                "routineId": self.active.routine.routine_id,
                "routineStepIndex": min(self.active.index, 63),
                "skillId": step.skill_id,
                "skillVersion": spec.version,
                "parameters": step.parameter_map or spec.default_parameters(),
                "limits": {
                    "maxTicks": spec.max_ticks,
                    "maxDistance": spec.max_distance,
                    "minHealth": spec.min_health,
                },
            }
        )

    def _emit_idle(
        self, decision: DecisionState[Any, BodyReading], goal: Goal, context_id: str, tick: int
    ) -> None:
        """Nothing is planned, so wait safely rather than stall the runtime."""
        idle = self.registry.vocabulary.roles["idle"]
        spec = self.registry.get(idle)
        self.active = ActiveRoutine(
            routine=Routine(
                routine_id="r_idle_wait",
                name=f"idle__{idle}",
                goal_type=goal.goal_type,
                elements=(SkillStep(idle),),
                risk=spec.risk,
                cost=1.0,
                ticks=spec.max_ticks,
            ),
            goal_id=goal.goal_id,
            context_id=context_id,
            steps=(SkillStep(idle),),
            started_tick=tick,
        )
        self.library.add(self.active.routine)
        self._pending_choice = DeterministicPolicyProvider(self.policy_revision).propose(
            self._verdict,
            goal,
            [candidate_from_routine(self.active.routine, self.library, {}, self.registry)],
            context_id,
        )
        self._emit_decision(decision, goal, context_id, self.active.steps[0], spec, tick)

    # ------------------------------------------------------ information seeking

    def _seek(
        self,
        decision: DecisionState[Any, BodyReading],
        state: dict[str, float],
        context_id: str,
        goal: Goal,
        tick: int,
    ) -> bool:
        """No plan exists. Look for what is missing, or stop honestly.

        Returns False, like a routine that could not start: this decision is
        already made, either as a glance or as a safe wait.
        """
        search = self.search
        if search is None:
            purpose = evidence_needed(state, goal.completion_condition, registry=self.registry)
            if not purpose:
                # Seeing more would not help. This is the old, real "no plan".
                self.goals.block(goal.goal_id, "no_feasible_plan", tick)
                self._emit_idle(decision, goal, context_id, tick)
                return False
            # A search happens somewhere. Person settles where it believes it
            # is, and tries to remember searching for the same things here.
            where = self._settle("search", tick)
            sought = self._evidence_subjects(purpose)
            recalled = self._recall(
                Cue.about(
                    *sought,
                    purpose="search",
                    kinds=("searched", "perceived"),
                    place=where["place_id"],
                ),
                tick,
            )
            unfound = [
                item
                for item in recalled
                if item.episode.kind == "searched"
                and item.episode.detail("conclusion") == NOT_FOUND
            ]
            # An earlier search that sought all of this, at what Person
            # believes is this same place, and found none of it, is evidence
            # that another full sweep from here will find nothing new. It is
            # not evidence that nothing is here: the search is shorter, never
            # skipped, and still concludes only "not found".
            here_before = [
                item
                for item in unfound
                if item.episode.place_id == where["place_id"]
                and sought <= set(item.episode.detail("sought") or ())
            ]
            revisit = max(
                (min(where["confidence"], item.episode.place_confidence) for item in here_before),
                default=0.0,
            )
            search = InformationSearch(
                goal_id=goal.goal_id,
                purpose=purpose,
                budget=revisit_budget(revisit),
                recalled=tuple(item.episode.memory_id for item in recalled),
                recalls_unfound=bool(unfound),
                place=where,
                revisit=round(revisit, 3),
            )
            self.search = search
            self._record("information_search", tick, search.payload("started"))

        if search.remaining <= 0:
            self._conclude_search("exhausted", tick, conclusion=NOT_FOUND)
            self.goals.block(goal.goal_id, NOT_FOUND, tick)
            self.unfound[goal.goal_id] = (
                search.purpose,
                search.place["place_id"] if search.place else None,
            )
            self._emit_idle(decision, goal, context_id, tick)
            return False

        direction = search.next_direction(self._environment().evidence_percepts(decision.percepts))
        search.record(direction)
        self._emit_look(decision, goal, context_id, search, direction, tick)
        return False

    def _emit_look(
        self,
        decision: DecisionState[Any, BodyReading],
        goal: Goal,
        context_id: str,
        search: InformationSearch,
        direction: str,
        tick: int,
    ) -> None:
        look = self.registry.vocabulary.roles["look"]
        spec = self.registry.get(look)
        step = SkillStep(look, (("direction", direction),))
        self.active = ActiveRoutine(
            routine=Routine(
                routine_id=SEARCH_ROUTINE_ID,
                name=f"seek_evidence__{look}",
                goal_type=goal.goal_type,
                elements=(step,),
                risk=spec.risk,
                cost=1.0,
                ticks=spec.max_ticks,
            ),
            goal_id=goal.goal_id,
            context_id=context_id,
            steps=(step,),
            started_tick=tick,
        )
        self.library.add(self.active.routine)
        choice = DeterministicPolicyProvider(self.policy_revision).propose(
            self._verdict,
            goal,
            [candidate_from_routine(self.active.routine, self.library, {}, self.registry)],
            context_id,
        )
        self._pending_choice = replace(
            choice,
            reason_codes=(
                "seeking_evidence",
                *(f"wants_{fact}" for fact in search.purpose),
                f"looks_remaining_{search.remaining}",
                *(("recalls_unfound_search",) if search.recalls_unfound else ()),
                *(("searched_here_before",) if search.revisit > 0 else ()),
            ),
        )
        self._emit_decision(decision, goal, context_id, step, spec, tick)

    def _conclude_search(self, phase: str, tick: int, **extra: Any) -> None:
        search = self.search
        if search is None:
            return
        self.search = None
        self._record("information_search", tick, search.payload(phase, **extra))
        if phase in {"exhausted", "satisfied"}:
            conclusion = NOT_FOUND if phase == "exhausted" else "found"
            if self.interoception_on:
                cause = f"search:{search.goal_id}@{self.memory.now}"
                self._step_searches.append((cause, search.goal_id, appraise_search(conclusion)))
            else:
                self._feel(appraise_search(conclusion), tick)
            self._remember(
                [
                    remembering.searched(
                        tuple(self._evidence_subjects(search.purpose)),
                        conclusion,
                        len(search.looks),
                        None,
                    )
                ],
                tick,
                place=search.place,
            )

    def _reopen_unfound(self, state: dict[str, float], tick: int) -> None:
        # "Not found" was a fact about one search from one place. Seeing what
        # was sought reopens the goal; so does no longer believing Person is
        # at the place it searched from, because somewhere else was not
        # searched. Returning to that place reopens nothing by itself.
        here = self.spatial.here()
        for goal_id, (purpose, searched_from) in list(self.unfound.items()):
            seen = any(state.get(fact, 0.0) >= 1 for fact in purpose)
            elsewhere = here is None or here.place_id != searched_from
            if seen or elsewhere:
                del self.unfound[goal_id]
                self.goals.reopen(goal_id, tick)

    # -------------------------------------------------------------- feedback

    def on_validation(self, message: dict[str, Any]) -> None:
        if message["decision"] in {"REJECT", "REPLACE"}:
            self.summary.note_override(message["decision"], message["reasonCodes"])

    def on_skill_started(self, message: dict[str, Any]) -> None:
        self._record(
            "skill_started",
            message["tick"],
            {
                "requested_skill": message["requestedSkill"],
                "executed_skill": message["executedSkill"],
                "parameters": dict(message["parameters"]),
                "limits": dict(message["limits"]),
                "context_id": self.active.context_id if self.active else "",
                "routine_id": self.active.routine.routine_id if self.active else "",
                "start_health": message["startHealth"],
                "start_food": message["startFood"],
            },
            message["decisionId"],
        )

    def on_emergency(self, message: dict[str, Any]) -> None:
        event = self._record(
            "emergency_override",
            message["tick"],
            {
                "level": message["level"],
                "trigger": message["trigger"],
                "action": message["action"],
                "preempted_skill": message["preemptedSkill"],
                "reason_codes": message["reasonCodes"],
                "context_id": self.active.context_id if self.active else "",
                "routine_id": self.active.routine.routine_id if self.active else "",
            },
            message["decisionId"],
        )
        self.summary.note_emergency(message["trigger"])
        if self._metareasoning():
            # The emergency is handled by the kernel now; whether its
            # recurrence deserves thought is asked at a later decision.
            self.arbiter.emergency_now = True
            self.arbiter.raw_signal(
                f"emergency_recurrence:{message['trigger']}",
                self.memory.now,
                self._recorder(message["tick"]),
            )
            self.arbiter.raise_trigger(
                self.arbiter.detectors.emergency(message["trigger"], self.memory.now)
            )
        self._remember(
            [
                remembering.endangered(
                    message,
                    event.event_id if event else None,
                    self._environment().emergency_subjects(str(message["trigger"])),
                )
            ],
            message["tick"],
            message["decisionId"],
        )

    def on_skill_outcome(self, message: dict[str, Any]) -> None:
        status = message["status"]
        # An emergency replacement is recorded as an interruption even when the
        # substituted skill succeeded: the routine did not run as planned, and
        # the executed skill still gets its own SUCCESS in the statistics.
        interrupted = (
            status in INTERRUPT_STATUSES
            or message["requestedSkillStatus"] in INTERRUPT_STATUSES
            or message["emergency"]
        )
        event_type = (
            "skill_interrupted"
            if interrupted
            else "skill_completed"
            if status == "SUCCESS"
            else "skill_failed"
        )
        resource_cost = sum(abs(item["delta"]) for item in message["resourceCost"])
        payload = {
            "requested_skill": message["requestedSkill"],
            "executed_skill": message["executedSkill"],
            "requested_status": message["requestedSkillStatus"],
            "status": status,
            "emergency": message["emergency"],
            "context_id": message["contextId"],
            "routine_id": message["routineId"],
            "goal_id": message["goalId"],
            "health_cost": message["healthCost"],
            "resource_cost": resource_cost,
            "elapsed_ticks": message["elapsedTicks"],
            "effects": message["effects"],
            "expected_effects": message["expectedEffects"],
            "inventory_delta": message["inventoryDelta"],
            "failure_modes": [] if status == "SUCCESS" else message["reasonCodes"][:8],
            "completion_evidence": message["completionEvidence"],
            "interrupt_reason": message["interruptReason"],
        }
        event = self._record(event_type, message["tick"], payload, message["decisionId"])
        self.summary.note_outcome(message)
        if self.interoception_on:
            # Appraised with what it brought about, once Person has seen that.
            self._pending_actions.append((message["decisionId"], self._appraise_outcome(message)))
        else:
            self._feel(self._appraise_outcome(message), message["tick"])
        executed = str(message["executedSkill"])
        experience = remembering.acted(
            message,
            self._environment().skill_subjects(executed, self.registry)
            if executed in self.registry
            else ("self",),
            event.event_id if event else None,
            unremarkable=self.registry.vocabulary.unremarkable_skills,
        )
        if experience is not None:
            succeeded = message["status"] == "SUCCESS"
            roles = self.registry.vocabulary.roles
            built_home = executed == roles.get("buildsHome") and succeeded
            # Having gone home, Person believes it is home: a belief from its
            # own action's outcome, which labels the place it is at and moves
            # no estimate. The runtime's home position never comes up.
            went_home = executed == roles.get("goesHome") and succeeded
            where = self._settle(
                "shelter" if built_home else "action",
                message["tick"],
                label="home" if (built_home or went_home) else None,
            )
            self._remember([experience], message["tick"], message["decisionId"], place=where)

        pending = self.pending_prediction
        if pending is not None and pending.decision_id == message["decisionId"]:
            pending.executed_skill = message["executedSkill"]
            # The effects belong to the skill that actually ran, which is the
            # only thing there is any point predicting.
            pending.expected_effects = tuple(message["expectedEffects"])
            pending.status = status
            pending.requested_status = str(message["requestedSkillStatus"])
            pending.reason_codes = tuple(str(code) for code in message["reasonCodes"])
            pending.emergency = bool(message["emergency"])
            pending.elapsed_ticks = int(message["elapsedTicks"])
            pending.health_cost = float(message["healthCost"])
            pending.settled = True
            if event is not None:
                pending.evidence_refs.append(event.event_id)

        active = self.active
        if active is None:
            return
        active.health_cost += message["healthCost"]
        active.resource_cost += resource_cost
        active.elapsed_ticks += message["elapsedTicks"]

        expected = active.current()
        executed_as_planned = (
            expected is not None
            and message["executedSkill"] == expected.skill_id
            and message["requestedSkill"] == expected.skill_id
        )

        if status == "SUCCESS" and executed_as_planned:
            active.index += 1
            if active.finished:
                self._finish_routine("SUCCESS", message["tick"], reason="all_steps_completed")
            return

        if message["emergency"] or message["requestedSkillStatus"] in INTERRUPT_STATUSES:
            # The runtime took over. The routine is interrupted, not failed, and
            # it recovered if the substituted emergency skill succeeded.
            active.recovered = status == "SUCCESS"
            active.failure_modes.append(message["interruptReason"] or "preempted")
            self._finish_routine("INTERRUPTED", message["tick"], reason="emergency_override")
            return

        if status in FAILURE_STATUSES:
            active.failure_modes.extend(message["reasonCodes"][:4])
            self._finish_routine(status, message["tick"], reason="skill_failed")
            return

        active.failure_modes.append(status.lower())
        self._finish_routine("INTERRUPTED", message["tick"], reason="skill_interrupted")

    # --------------------------------------------------------- effect beliefs

    def _learn_effects(
        self,
        pending: PendingPrediction,
        state: dict[str, float] | None,
        prediction_event: str | None,
        tick: int,
    ) -> list[tuple[Trial, str | None]]:
        """Classify a settled prediction per declared effect, and journal it.

        Every trial is recorded, informative or not, with its reason. What the
        learning mode admits it to is fixed at the moment of writing: nothing
        under `off`, the shadow table under `shadow`, the active table under
        `supervised`.
        """
        trials = classify(
            requested=pending.requested_skill,
            executed=pending.executed_skill,
            status=pending.status,
            requested_status=pending.requested_status,
            emergency=pending.emergency,
            reason_codes=pending.reason_codes,
            expected_effects=pending.expected_effects,
            state_before=pending.state_before,
            state_after=state,
            evaluable=self.registry.vocabulary.evaluable_facts,
            not_attempted=self.registry.vocabulary.not_attempted,
            tracked=self.registry.vocabulary.tracked_facts,
        )
        destination = admitted_to(self.learning_mode)
        judged: list[tuple[Trial, str | None]] = []
        for trial in trials:
            event = self._record(
                "effect_evidence",
                tick,
                {
                    **trial.to_json(),
                    "admitted_to": destination if trial.verdict != "inconclusive" else "none",
                    "prediction_event_id": prediction_event,
                },
                pending.decision_id,
            )
            judged.append((trial, event.event_id if event else None))
        return judged

    def _appraise_outcome(self, message: dict[str, Any]) -> Appraisal | None:
        return appraise_outcome(message, self.registry.vocabulary.unremarkable_skills)

    def _reliability(self) -> Any:
        """The learned term for routine scoring, only when beliefs may act."""
        if self.learning_mode != "supervised":
            return None
        return reliability_term(self.effect_beliefs, self.registry, self.experience_key)

    # ---------------------------------------------------- causal hypotheses

    def _hypotheses(self) -> Any:
        """The supported-hypothesis term for routine scoring, only when beliefs may act."""
        if self.learning_mode != "supervised" or self._now is None:
            return None
        return hypothesis_term(self.hypothesis_book.hypotheses["active"], self._now)

    def _learn_causes(
        self,
        pending: PendingPrediction,
        judged: list[tuple[Trial, str | None]],
        tick: int,
    ) -> None:
        """Count one settled prediction for or against each hypothesis it bears on.

        A trial falls on one side of a hypothesis's contrast by the condition
        Person perceived when it decided. It is interventional evidence only
        for the hypothesis it was run to test; for any other it is
        observational. It is inconclusive if the condition changed while it
        ran, or Person could not tell which side it was on.
        """
        table = {"shadow": "shadow", "active": "active"}.get(admitted_to(self.learning_mode))
        before = Perceived.from_json(pending.perceived) if pending.perceived else None
        after = self._now
        tested = pending.experiment
        tested_arm: str | None = None
        tested_reason: str | None = None
        puzzle: tuple[str, str] | None = None
        for trial, ref in judged:
            if table is None or before is None:
                break
            if trial.verdict == "inconclusive":
                tested_reason = tested_reason or trial.reason
                continue
            self._record(
                "causal_trial",
                tick,
                {
                    **trial.to_json(),
                    "conditions": before.to_json(),
                    "experiment": tested,
                    "effect_evidence_id": ref,
                    "admitted_to": table,
                },
                pending.decision_id,
            )
            for hypothesis in list(self.hypothesis_book.hypotheses[table].values()):
                if hypothesis.intervention != trial.skill or hypothesis.outcome.fact != trial.fact:
                    continue
                variable = hypothesis.condition.variable
                reason = None
                if before.value(variable) is None:
                    reason = "condition_not_known"
                elif after is None or after.value(variable) != before.value(variable):
                    reason = "condition_changed_during_trial"
                arm = "held" if before.value(variable) == hypothesis.condition.value else "absent"
                verdict = trial.verdict if reason is None else "inconclusive"
                self._record(
                    "hypothesis_evidence",
                    tick,
                    {
                        "hypothesis_id": hypothesis.hypothesis_id,
                        "arm": arm,
                        "kind": "interventional"
                        if hypothesis.hypothesis_id == tested
                        else "observational",
                        "verdict": verdict,
                        "reason": reason or trial.reason,
                        "trial_ref": ref,
                        "admitted_to": table if verdict != "inconclusive" else "none",
                    },
                    pending.decision_id,
                )
                if hypothesis.hypothesis_id == tested:
                    if verdict == "inconclusive":
                        tested_reason = tested_reason or reason
                    else:
                        tested_arm = arm
            if puzzle is None:
                # One settled prediction, one question at most: about its
                # first declared effect Person could judge. Whether there is
                # anything to explain depends on the history, not on this
                # outcome alone: a success after failures is variation too.
                puzzle = (trial.skill, trial.fact)
        if puzzle is not None and table is not None:
            self._wonder(table, *puzzle, tick)

        if tested is not None and table == "active":
            if tested_arm is None:
                # A refusal, a takeover or a missing observation says nothing
                # about the world, and is recorded as saying nothing.
                self._record(
                    "hypothesis_evidence",
                    tick,
                    {
                        "hypothesis_id": tested,
                        "arm": None,
                        "kind": "interventional",
                        "verdict": "inconclusive",
                        "reason": tested_reason or "not_evaluated",
                        "trial_ref": None,
                        "admitted_to": "none",
                    },
                    pending.decision_id,
                )
            resumable = (tested_reason or "") in {
                "overridden_by_runtime",
                "not_attempted_interrupted",
                "not_attempted_preempted",
            }
            changes, done = self.investigations.trial(
                pending.goal_id,
                arm=tested_arm,
                conclusive=tested_arm is not None,
                resumable=resumable,
                experienced=self.memory.now,
                hypothesis=self.hypothesis_book.hypotheses["active"].get(tested),
            )
            self._record_changes(changes, tick)
            if done:
                self.goals.conclude(pending.goal_id, tick, "trial_observed")

    def _wonder(self, table: str, skill: str, fact: str, tick: int) -> None:
        """Is there something here to explain: variation, or repeated failure? A guess?"""
        recent = self.hypothesis_book.trials[table].get((skill, fact), [])
        failed = sum(trial.verdict == "contradicts" for trial in recent)
        worked = sum(trial.verdict == "supports" for trial in recent)
        question = "variation" if failed and worked else "repeated_error" if failed >= 2 else None
        if question is None:
            return
        held = self.hypothesis_book.hypotheses[table]
        live = [
            h
            for h in held.values()
            if h.intervention == skill
            and h.outcome.fact == fact
            and h.standing == "unresolved"
            and h.lifecycle != "retired"
        ]
        if len(live) >= MAX_LIVE_HYPOTHESES:
            return
        belief = self.effect_beliefs.belief(table, self.experience_key, skill, fact)
        context = ReasoningContext(
            skill=skill,
            fact=fact,
            question=question,
            trials=tuple(recent[-CONTEXT_TRIALS:]),
            vocabulary=vocabulary(self.spatial.known_places()),
            interventions=evaluable_effects(self.registry, self.offered),
            belief=None
            if belief is None
            else {
                "estimate": None if belief.estimate is None else round(belief.estimate, 4),
                "strength": round(belief.strength, 4),
            },
        )
        known = frozenset(h.signature for h in held.values())
        for proposal in self.proposer.propose(context):
            outcome = admit(
                proposal,
                context,
                hypothesis_id=f"hyp_{self.hypothesis_book.all_ids() + 1}",
                proposer=self.proposer.kind,
                now=self.memory.now,
                known=known,
            )
            if isinstance(outcome, CausalHypothesis):
                testable = design(outcome, self.registry) is not None
                hypothesis = replace(outcome, lifecycle="testable" if testable else "proposed")
                known = known | {hypothesis.signature}
                self._record(
                    "hypothesis_proposed",
                    tick,
                    {
                        "hypothesis": hypothesis.to_json(),
                        "question": question,
                        "admitted_to": table,
                    },
                )
            elif outcome.reasons != ("duplicate",):
                self._record(
                    "hypothesis_rejected",
                    tick,
                    {
                        **outcome.to_json(),
                        "proposer": self.proposer.kind,
                        "question": question,
                        "admitted_to": table,
                    },
                )

    def _deliberate_investigations(
        self, decision: DecisionState[Any, BodyReading], state: dict[str, float], tick: int
    ) -> None:
        """Perhaps start finding something out. Experiments change behaviour,
        so they run only when learned beliefs may act."""
        if self.learning_mode != "supervised":
            return
        trials = [
            trial for records in self.hypothesis_book.trials["active"].values() for trial in records
        ]
        attempts: dict[str, int] = {}
        seen: dict[str, set[str]] = {}
        for trial in trials:
            attempts[trial.skill] = attempts.get(trial.skill, 0) + 1
            for variable, value in trial.conditions.items():
                if value is not None:
                    seen.setdefault(variable, set()).add(str(value))
        environment = self._environment()
        night = environment.night(decision.percepts)
        self._record_changes(
            self.investigations.consider(
                hypotheses=self.hypothesis_book.hypotheses["active"],
                registry=self.registry,
                experience={"attempts": attempts, "seen": seen},
                tolerance=self.affect.tolerance(),
                open_projects=len(self.projects.unfinished()),
                is_calm=calm(environment.drives(decision, state), night),
                now=self.memory.now,
            ),
            tick,
        )

    def _trial_goal(self, state: dict[str, float], tick: int) -> Goal | None:
        if self.learning_mode != "supervised" or self._now is None:
            return None
        self._record_changes(self.investigations.review(self.memory.now), tick)
        return self.investigations.goal(self._now, state, self.memory.now, tick)

    def _retire_stale_trials(self, trial: Goal | None, tick: int) -> None:
        """A trial goal lives only while its investigation proposes it."""
        for goal_id, goal in list(self.goals.entries.items()):
            stale = trial is None or goal_id != trial.goal_id
            if goal.goal_type == INVESTIGATE and stale:
                self.goals.conclude(goal_id, tick, "no_longer_proposed")

    # ---------------------------------------------------------------- affect

    def _feel(
        self, appraisal: Appraisal | None, tick: int, extra: dict[str, Any] | None = None
    ) -> None:
        """Apply one appraisal and journal its full causal record."""
        if appraisal is None:
            return
        record = self.affect.feel(appraisal, self.memory.now, extra)
        if record is not None:
            self._record("affect_appraised", tick, record)

    def _sense_body(self, reading: BodyReading, tick: int) -> None:
        """The body's conditions press on, and its events are felt once (ADR 0014).

        `reading` is the body view of the self-state (ADR 0026): interoception
        reads the self, never the world."""
        sensed = self.interoception.sense(reading)
        record = self.affect.apply_tonic(sensed.pressures, self.memory.now)
        if record is not None:
            self._record("affect_tonic", tick, record)
        for appraisal in sensed.events:
            self._feel(appraisal, tick, {"cause": f"{appraisal.trigger}@{self.memory.now}"})

    def _appraise_step(self, tick: int) -> None:
        """One appraisal per causal event of this step, with its consequences.

        The causal events are an action whose outcome was reported, a search
        that concluded, and, for consequences with neither behind them, the
        observation itself. Goals and projects an event brought about are
        listed with it and weigh once. The idle placeholder is not a goal of
        Person's and is never appraised.
        """
        new = min(self.goals.noted - self._goal_events_seen, len(self.goals.history))
        self._goal_events_seen = self.goals.noted
        goal_events = self.goals.history[len(self.goals.history) - new :] if new else []
        actions, self._pending_actions = self._pending_actions, []
        searches, self._step_searches = self._step_searches, []
        changes, self._step_changes = self._step_changes, []

        now = self.memory.now
        events: dict[str, tuple[Appraisal | None, list[tuple[dict[str, Any], Appraisal]]]] = {}
        # Earlier outcomes with no observation of their own stand alone.
        for decision_id, appraisal in actions[:-1]:
            events[f"action:{decision_id}"] = (appraisal, [])
        action = f"action:{actions[-1][0]}" if actions else None
        if actions:
            events[action] = (actions[-1][1], [])  # type: ignore[index]
        for cause, _goal_id, appraisal in searches:
            events[cause] = (appraisal, [])
        observed = f"observation@{now}"

        def attach(cause: str, consequence: dict[str, Any], appraisal: Appraisal) -> None:
            base, listed = events.get(cause, (None, []))
            listed.append((consequence, appraisal))
            events[cause] = (base, listed)

        for _when, goal_id, event in goal_events:
            goal = self.goals.entries.get(goal_id)
            if goal is None or goal.source == "maintenance":
                continue
            appraisal = appraise_goal(event, goal.goal_type)
            if appraisal is None:
                continue
            consequence = {"kind": f"goal_{event}", "goal_id": goal_id, "goal_type": goal.goal_type}
            by_search = next(
                (cause for cause, searched, _ in searches if searched == goal_id), None
            )
            if event == "blocked" and goal.suspension_reason == NOT_FOUND and by_search:
                attach(by_search, consequence, appraisal)
            else:
                attach(action or observed, consequence, appraisal)
        for _kind, payload in changes:
            project = payload["project"]
            appraisal = appraise_project(payload["change"], project["kind"])
            if appraisal is None:
                continue
            consequence = {
                "kind": f"project_{payload['change']}",
                "project_id": project["project_id"],
                "project_kind": project["kind"],
            }
            attach(action or observed, consequence, appraisal)

        for cause, (base, consequences) in events.items():
            if base is None and not consequences:
                continue
            self._feel(
                combined(base, consequences),
                tick,
                {"cause": cause, "consequences": [item for item, _ in consequences]},
            )

    def _appraise_body(self, percepts: PerceptualState[Any], tick: int) -> None:
        """What the world and the body feel like now: threat perceived, harm felt."""
        environment = self._environment()
        self.affect.advance(self.memory.now)
        self._feel(appraise_threat(environment.threat(percepts)), tick)
        health = environment.health(percepts)
        if self._felt_health is not None:
            self._feel(appraise_harm(self._felt_health - health), tick)
        self._felt_health = health

    def _appraise_progress(self, changes: list[tuple[str, dict[str, Any]]], tick: int) -> None:
        """Goals reached or blocked, and projects advanced or given up."""
        new = min(self.goals.noted - self._goal_events_seen, len(self.goals.history))
        self._goal_events_seen = self.goals.noted
        for _when, goal_id, event in self.goals.history[len(self.goals.history) - new :]:
            goal = self.goals.entries.get(goal_id)
            if goal is not None:
                self._feel(appraise_goal(event, goal.goal_type), tick)
        for _kind, payload in changes:
            project = payload["project"]
            self._feel(appraise_project(payload["change"], project["kind"]), tick)

    def _basis(self, goal: Goal) -> dict[str, Any]:
        """One goal candidate as the engineering record describes it."""
        fixed = goal.goal_type == INVESTIGATE or goal.source == "emergency"
        facts = frozenset(condition.fact for condition in goal.completion_condition)
        return {
            "goal_id": goal.goal_id,
            "goal_type": goal.goal_type,
            "source": goal.source,
            "character": "fixed" if fixed else self._environment().goal_character(facts),
            "base_priority": goal.base_priority
            if goal.base_priority is not None
            else goal.priority,
            "affect_bias": goal.affect_bias,
            "priority": goal.priority,
        }

    def _biased(self, goal: Goal) -> Goal:
        if goal.goal_type == INVESTIGATE:
            # Affect reaches experiments only through the tolerance factor on
            # risk, as it reaches exploration (ADR 0012): no priority bias.
            return replace(goal, base_priority=goal.priority, affect_bias=0.0)
        facts = frozenset(condition.fact for condition in goal.completion_condition)
        bias = self.affect.bias(self._environment().goal_character(facts), goal.source)
        return replace(
            goal,
            base_priority=goal.priority,
            affect_bias=bias,
            priority=round(min(1000.0, max(0.0, goal.priority + bias)), 3),
        )

    # -------------------------------------------------------------- projects

    def _deliberate_projects(
        self, decision: DecisionState[Any, BodyReading], state: dict[str, float], tick: int
    ) -> None:
        """Check restored projects still apply, then perhaps take up a new one."""
        home_place = self.spatial.home_place()
        waiting = self.projects.unexamined()
        if waiting:
            subjects = sorted(
                {s for project in waiting for s in self.projects.template(project).subjects}
            )
            # How has this kind of work gone before? Bounded, cued recall.
            recalled = self._recall(
                Cue.about(*subjects, purpose="goal", kinds=("acted",)),
                tick,
            )
            failures = sum(item.episode.detail("status") != "SUCCESS" for item in recalled)
            self._record_changes(
                self.projects.reexamine(state=state, home_place=home_place, failures=failures),
                tick,
            )
        environment = self._environment()
        night = environment.night(decision.percepts)
        self._record_changes(
            self.projects.consider(
                state=state,
                drives=environment.drives(decision, state),
                home_place=home_place,
                night=night,
                now=self.memory.now,
            ),
            tick,
        )

    def _record_changes(self, changes: list[tuple[str, dict[str, Any]]], tick: int) -> None:
        for kind, payload in changes:
            self._record(kind, tick, payload)

    # ---------------------------------------------------------------- memory

    def _remember(
        self,
        drafts: list[EpisodeDraft],
        tick: int,
        decision_id: str | None = None,
        *,
        place: dict[str, Any] | None = None,
    ) -> None:
        """Encode experience. The journal records it; the store is rebuilt from that.

        Each episode is placed where Person believes it happened: the place it
        settled at for this experience, or else whichever it recognises.
        """
        if drafts and place is None:
            here = self.spatial.here()
            place = here.to_json() if here is not None else None
        for draft in drafts:
            payload = self.memory.payload(draft, place)
            event = self._record("memory_encoded", tick, payload, decision_id)
            if event is not None:
                self.memory.encoded(event.event_id)

    def _settle(self, reason: str, tick: int, label: str | None = None) -> dict[str, Any]:
        """Be somewhere that mattered: revisit a recognised place or form one."""
        kind, payload = self.spatial.settle(reason, self.memory.now, label)
        self._record(kind, tick, payload)
        return {"place_id": payload["place_id"], "confidence": payload["confidence"]}

    def _recall(self, cue: Cue, tick: int) -> tuple[Recalled, ...]:
        recalled = self.memory.recall(cue)
        self._record(
            "memory_recalled",
            tick,
            {
                "cue": cue.to_json(),
                "recalled": [item.episode.memory_id for item in recalled],
                "considered": self.memory.last_considered,
            },
        )
        return recalled

    def _settle_prediction(self, state: dict[str, float] | None, tick: int) -> None:
        """Record how far the skill contract was from what actually happened.

        This is measurement only. The record never reaches the policy, which is
        why prediction error cannot change behaviour in this milestone even by
        accident: the statistics reducer has no case for it.
        """
        pending = self.pending_prediction
        if pending is None or not pending.settled:
            return
        self.pending_prediction = None
        payload = build_payload(pending, state, tracked=self.registry.vocabulary.tracked_facts)
        if self._metareasoning():
            erred = self.goals.entries.get(str(payload.get("goal_id")))
            evaluable = self.registry.vocabulary.evaluable_facts
            failed_facts = [
                str(entry.get("fact"))
                for entry in payload.get("observed", [])
                if entry.get("fact") in evaluable
            ]
            if str(payload.get("severity")) in ("major", "inverted") and failed_facts:
                self.arbiter.raw_signal(
                    "repeated_prediction_error:"
                    + prediction_key(str(payload.get("executed_skill")), failed_facts),
                    self.memory.now,
                    self._recorder(tick),
                )
            self.arbiter.raise_trigger(
                self.arbiter.detectors.prediction(
                    payload.get("executed_skill"),
                    # Only facts Person can actually evaluate (ADR 0011): an
                    # unobservable expectation is not a surprise.
                    [
                        str(entry.get("fact"))
                        for entry in payload.get("observed", [])
                        if entry.get("fact") in evaluable
                    ],
                    str(payload.get("severity")),
                    self.memory.now,
                    erred.goal_id if erred else None,
                    erred.priority if erred else None,
                )
            )
        self.prediction_errors.append(payload)
        self.summary.note_prediction(payload)
        record = self._record("prediction_error", tick, payload, pending.decision_id)
        judged = self._learn_effects(pending, state, record.event_id if record else None, tick)
        self._learn_causes(pending, judged, tick)

    def _finish_routine(self, status: str, tick: int, *, reason: str) -> None:
        active = self.active
        self.active = None
        self._pending_choice = None
        if active is None or active.routine.routine_id in UNSCORED_ROUTINES:
            return
        self.arbiter.routine_finished(
            active.goal_id,
            status,
            frozenset(
                effect.fact
                for step in active.steps
                for effect in self.registry.get(step.skill_id).expected_effects
            ),
            self.memory.now,
        )
        if status == "SUCCESS":
            self.consecutive_failures.pop(active.goal_id, None)
        elif status != "INTERRUPTED":
            # A goal whose strategies keep failing is blocked rather than
            # retried forever; BLOCKED is a real goal state, and spinning would
            # burn the episode without producing usable evidence.
            failures = self.consecutive_failures.get(active.goal_id, 0) + 1
            self.consecutive_failures[active.goal_id] = failures
            failed_goal = self.goals.entries.get(active.goal_id)
            if self._metareasoning() and failed_goal is not None:
                self.arbiter.raw_signal(
                    f"repeated_failure:{failed_goal.goal_type}",
                    self.memory.now,
                    self._recorder(tick),
                )
                self.arbiter.raise_trigger(
                    self.arbiter.detectors.goal_failed(
                        failed_goal.goal_type, failed_goal.goal_id, failures, failed_goal.priority
                    )
                )
            if failures >= 3:
                self.goals.block(active.goal_id, "repeated_routine_failure", tick)
        self._record(
            "routine_outcome",
            tick,
            {
                "routine_id": active.routine.routine_id,
                "routine_name": active.routine.name,
                "goal_id": active.goal_id,
                "context_id": active.context_id,
                "status": status,
                "reason": reason,
                "steps_completed": active.index,
                "steps_total": len(active.steps),
                "health_cost": active.health_cost,
                "resource_cost": active.resource_cost,
                "elapsed_ticks": active.elapsed_ticks,
                "failure_modes": active.failure_modes[:8],
                "recovered": active.recovered,
            },
        )

    @staticmethod
    def _identity_binding(founding: Founding | None) -> dict[str, str] | None:
        """What this root's snapshots must carry to be loaded (ADR 0017)."""
        if founding is None:
            return None
        return {"person_id": founding.person_id, "founding": founding.fingerprint()}

    def on_world_availability(self, message: dict[str, Any]) -> None:
        """The world became available to the body, or stopped being (I2).

        An operational state, not a verdict on the run. While it is
        unavailable no observation arrives, so nothing is experienced, and
        nothing is invented for the absence: the baselines that compare one
        observation with the last are dropped, so the time away is not
        counted as lived and a change of body across it is not felt as an
        event.
        """
        state = message["state"]
        if state == self.operational.world:
            return
        self.operational = OperationalView(world=state)
        self.arbiter.world_epoch += 1
        if state == "unavailable":
            self._drop_body_continuity()
        if self._lifecycle:
            self._record(
                "world_availability_changed",
                message["tick"],
                {"state": state, "reasons": list(message["reasonCodes"])[:8]},
                timestamp=message["timestamp"],
            )

    def on_life_event(self, message: dict[str, Any]) -> None:
        """The trusted runtime observed a death, or brought the body back (I3).

        Never cognition's own conclusion. A repeated message changes nothing.
        A death is recorded with its `terminal` flag first, so a crash right
        after it still reconstructs the right state; it is remembered as an
        episode from what Person knew; and continuity with the body before it
        is dropped, so the next observation is the body as it is now, not a
        recovery. Projects are kept: whether they still matter is for later
        deliberation, not for death to decide.
        """
        tick = message["tick"]
        if message["event"] == "died":
            if self.life.status != "alive":
                return
            terminal = bool(message["terminal"])
            state = self.affect.state
            self._record(
                "person_died",
                tick,
                {
                    "terminal": terminal,
                    "experienced_tick": self.memory.now,
                    # Engineering evidence: how Person felt as it died. Kept
                    # out of the death memory, since affect never touches
                    # memory (ADR 0010).
                    "affect": {
                        "valence": round(state.valence, 4),
                        "unease": round(state.unease, 4),
                        "control": round(state.control, 4),
                    },
                },
                timestamp=message["timestamp"],
            )
            self._remember([self._death_memory(message)], tick)
            if terminal:
                self._record(
                    "person_terminated",
                    tick,
                    {"after": "terminal_death"},
                    timestamp=message["timestamp"],
                )
            if self.active is not None:
                self._finish_routine("INTERRUPTED", tick, reason="died")
            self._drop_body_continuity()
        elif message["event"] == "respawned":
            if self.life.status != "awaiting_respawn":
                return
            self._record(
                "person_respawned",
                tick,
                {"experienced_tick": self.memory.now},
                timestamp=message["timestamp"],
            )
            self._drop_body_continuity()

    def _death_memory(self, message: dict[str, Any]) -> EpisodeDraft:
        health, food, threat = (
            self.environment.last_felt(self._last_percepts)
            if self.environment is not None
            else (None, None, False)
        )
        active = self.goals.active
        project = self.projects.current()
        return remembering.died(
            health=health,
            food=food,
            threat_in_view=threat,
            goal_type=active.goal_type if active is not None else None,
            project_kind=project.kind if project is not None else None,
            message_id=str(message["messageId"]),
        )

    def _drop_body_continuity(self) -> None:
        """What compares one observation with the last starts again (I2, I3)."""
        self.memory.lose_continuity()
        self.interoception.lose_continuity()
        self._felt_health = None

    def close(self) -> None:
        """Let go of the continuity root. A process that ends without this
        simply leaves its lock to be taken over, and no session_ended."""
        if self._lock is not None:
            self._lock.release()
            self._lock = None

    # ------------------------------------------------------------------- run

    def run(self, lines: Any) -> None:
        from person_protocol import LineReader, decode_frame
        from person_protocol.framing import FrameError

        reader = LineReader()
        for chunk in lines:
            frames, error = reader.push(chunk)
            if error:
                self._log(f"cognition dropped a frame: {error}")
                continue
            for line in frames:
                try:
                    message = decode_frame(line)
                except FrameError as failure:
                    self._log(f"cognition dropped a malformed frame: {failure}")
                    continue
                valid, diagnostics = self.validator.validate(message)
                if not valid:
                    self._log(f"cognition rejected an invalid message: {diagnostics}")
                    continue
                self.handle(message)
                if not self.running:
                    return


def _decision_uuid(counter: int, identity: SessionIdentity | None) -> str:
    import uuid

    seed = f"{identity.session_id if identity else 'session'}:{counter}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))
