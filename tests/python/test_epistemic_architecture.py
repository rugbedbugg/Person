"""The epistemic and environment boundaries, held mechanically (ADR 0025-0028).

These are the rules a contributor who never reads an agent instruction file
must still be unable to break without a red test:

    Person's core names no environment, and depends on none
    the core protocol, configuration and skill infrastructure own no
        Minecraft vocabulary; the Minecraft profile does
    nothing downstream of the epistemic boundary reads a raw observation
    beliefs carry provenance, freshness, evidence references and scope, and
        an environment-specific belief never widens by itself
    a memory is not a percept, recall is not evidence, imagined material is
        never lived experience, and a canonical event is not evidence
    a predictive model has no route to the body
"""

from __future__ import annotations

import ast
import io
import json
import re
import tokenize
from pathlib import Path
from typing import Any

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]

#: Person's core, Python side: every package that must stay environment-neutral.
CORE_ROOTS = [
    REPOSITORY / "packages/epistemics/python",
    REPOSITORY / "packages/protocol/python",
    REPOSITORY / "packages/skills/python",
    REPOSITORY / "packages/config/python",
    REPOSITORY / "packages/planner/python",
    REPOSITORY / "packages/policy/python",
    REPOSITORY / "packages/persistence/python",
    REPOSITORY / "apps/cognition/python",
]
MINECRAFT = REPOSITORY / "environments/minecraft"

#: Words that belong to Minecraft's ontology and to nothing in Person's core.
MINECRAFT_WORDS = (
    "minecraft",
    "mineflayer",
    "overworld",
    "nether",
    "biome",
    "villager",
    "zombie",
    "creeper",
    "skeleton",
    "furnace",
    "crafting_table",
    "pickaxe",
    "cobblestone",
    "sweet_berr",
    "oak_log",
    "peaceful",
    "coal",
    "plant_food",
)

#: Compatibility readers that must name what old records meant. Nothing new
#: is written by them; each says so in its docstring.
COMPATIBILITY_ONLY = {
    REPOSITORY / "packages/persistence/python/person_persistence/legacy.py",
}


def sources(roots: list[Path]) -> list[Path]:
    return [
        path for root in roots for path in root.rglob("*.py") if "__pycache__" not in path.parts
    ]


def imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append(node.module)
    return found


def code_words(path: Path) -> set[str]:
    """Identifiers and short string literals: where a field is named, not prose."""
    words: set[str] = set()
    for token in tokenize.generate_tokens(io.StringIO(path.read_text("utf-8")).readline):
        if token.type == tokenize.NAME:
            words.add(token.string)
        elif token.type == tokenize.STRING and len(token.string) < 60:
            words.update(re.findall(r"[A-Za-z_]+", token.string))
    return words


# ------------------------------------------------------- the environment boundary


def test_person_core_never_imports_an_environment() -> None:
    for path in sources(CORE_ROOTS):
        for name in imports(path):
            assert not name.startswith("person_minecraft"), (
                f"{path.relative_to(REPOSITORY)} imports {name}: the core finds an "
                "environment through its manifest, never by name"
            )


def test_person_core_code_names_no_minecraft_ontology() -> None:
    for path in sources(CORE_ROOTS):
        if path in COMPATIBILITY_ONLY:
            continue
        words = {word.lower() for word in code_words(path)}
        leaked = sorted(word for word in MINECRAFT_WORDS if any(word in item for item in words))
        assert not leaked, f"{path.relative_to(REPOSITORY)} names {leaked} in code"


def test_the_core_protocol_owns_no_minecraft_observation_vocabulary() -> None:
    for path in sorted((REPOSITORY / "packages/protocol/schemas").glob("*.json")):
        text = path.read_text(encoding="utf-8").lower()
        for word in (*MINECRAFT_WORDS, "dayphase", "weather", "hostiles", "passiveanimals"):
            assert word not in text, f"{path.name} names {word}"
    core = json.loads(
        (REPOSITORY / "packages/protocol/schemas/observation.schema.json").read_text()
    )
    assert set(core["properties"]) == {
        "type",
        "observationVersion",
        "experience",
        "selfMotion",
        "cognition",
        "previousOutcome",
        "payload",
    }, "the observation envelope is environment-neutral; its payload is the environment's"


def test_the_environment_profile_owns_its_payload_skills_and_vocabulary() -> None:
    manifest = json.loads((MINECRAFT / "environment.json").read_text(encoding="utf-8"))
    assert manifest["kind"] == "minecraft"
    assert (MINECRAFT / manifest["observationPayload"]["schema"]).is_file()
    assert (MINECRAFT / manifest["config"]["schema"]).is_file()
    skills = MINECRAFT / manifest["skills"]["directory"]
    assert (skills / "vocabulary.json").is_file() and (skills / "facts.json").is_file()
    assert sorted(manifest["embodiments"]) == ["fixture", "mineflayer"], (
        "a fixture is another body of Minecraft, not another environment"
    )
    assert not (REPOSITORY / "packages/skills/specs").exists(), "no skill library in the core"


def test_generic_skill_infrastructure_enumerates_no_environment_vocabulary() -> None:
    schema = json.loads(
        (REPOSITORY / "packages/skills/schema/skill-spec.schema.json").read_text(encoding="utf-8")
    )
    properties = schema["properties"]
    assert "enum" not in properties["category"]
    assert "enum" not in properties["requiredPermissions"]["items"]
    assert "enum" not in properties["completionEvidence"]["items"]
    text = json.dumps(schema).lower()
    for word in ("harvest", "hunt", "shelter", "smelt", "emergency_dig", *MINECRAFT_WORDS):
        assert word not in text, f"the generic SkillSpec schema names {word}"


def test_the_core_configuration_enumerates_no_environment_modes() -> None:
    schema = json.loads(
        (REPOSITORY / "packages/config/schema/person-config.schema.json").read_text("utf-8")
    )
    text = json.dumps(schema).lower()
    for word in ("traininggcontext", "trainingcontext", "minecraft_", *MINECRAFT_WORDS):
        assert word not in text, f"the core configuration schema names {word}"


def test_a_second_environment_needs_no_core_change(tmp_path: Path) -> None:
    """A made-up environment with its own vocabulary loads through the same core."""
    from person_skills import SkillRegistry, SkillSpecError

    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "facts.json").write_text(
        json.dumps({"description": "toy", "facts": {"lamp_lit": "1 when lit", "seen_lamp": "n"}})
    )
    (skills / "vocabulary.json").write_text(
        json.dumps(
            {
                "description": "toy",
                "categories": ["light"],
                "permissions": ["touch"],
                "completionEvidence": ["lamp_state"],
                "limits": {"maxTicks": 100, "maxDistance": 3, "minHealth": 1},
                "factClasses": {
                    "evidence": ["seen_lamp"],
                    "tracked": ["lamp_lit"],
                    "evaluable": ["lamp_lit"],
                    "unobservable": [],
                    "action": [],
                },
                "failures": {"notAttempted": []},
            }
        )
    )
    spec = {
        "id": "light_lamp",
        "version": 1,
        "category": "light",
        "summary": "Light the lamp that is in view.",
        "parameters": {},
        "preconditions": [{"fact": "seen_lamp", "op": ">=", "value": 1}],
        "expectedEffects": [{"fact": "lamp_lit", "op": "=", "value": 1}],
        "possibleFailures": ["no_lamp"],
        "requiredPermissions": ["touch"],
        "costLimits": {"maxTicks": 50, "maxDistance": 2, "minHealth": 0},
        "interruptionPolicy": "preemptible",
        "completionEvidence": ["lamp_state"],
        "risk": 0.1,
        "emergency": False,
    }
    (skills / "light_lamp.json").write_text(json.dumps(spec))
    registry = SkillRegistry(skills)
    assert registry.ids == ["light_lamp"]
    assert registry.vocabulary.evidence_facts == frozenset({"seen_lamp"})

    from person_planner import evidence_needed, plan_for
    from person_skills import Condition

    goal = (Condition("lamp_lit", ">=", 1),)
    assert evidence_needed({}, goal, registry=registry) == ("seen_lamp",)
    assert plan_for({"seen_lamp": 1.0}, goal, registry=registry, limit=1)

    # And it cannot name what its own vocabulary does not allow.
    (skills / "light_lamp.json").write_text(json.dumps({**spec, "category": "crafting"}))
    with pytest.raises(SkillSpecError, match="does not allow"):
        SkillRegistry(skills)


#: Person's own words that an environment's vocabulary happens to reuse. The
#: core owns these: they are protocol fields, role names or core concepts.
CORE_OWNED_WORDS = {
    "danger",  # core memory subject (memory/episodes.py CORE_SUBJECTS)
    "self",  # core memory subject
    "emergency",  # SkillSpec and SkillOutcome field, goal source
    "elapsed_ticks",  # SkillOutcome field, routine statistics
    "inventory_delta",  # SkillOutcome field, journalled as reported
    "look",  # a skill role every environment fills (vocabulary.json roles)
    "at_home",  # Person's own home relation (spatial, ADR 0008)
    "shelter",  # the place reason for the home Person built (spatial)
}

#: Known leaks of the same kind, each recorded in docs/CURRENT_STATE.md. This
#: list may only shrink: a test below fails if an entry stops being needed.
KNOWN_VOCABULARY_LEAKS = {
    # C9: interoception's body reading is on Minecraft's food scale.
    "apps/cognition/python/person_cognition/interoception.py": {"food"},
}


def environment_vocabulary() -> set[str]:
    """Every word an installed environment owns: its memory, spatial and
    emergency vocabulary, its skills, facts and skill vocabulary, and the names
    of the drives its homeostasis produces."""
    from person_minecraft.goals import homeostasis
    from person_minecraft.offline import facts_from_observation, snapshot_decision
    from person_protocol import discovered
    from person_skills import skill_registry

    words: set[str] = set()
    for kind, manifest in discovered().items():
        document = manifest.document
        words |= set(document.get("memory", {}).get("subjects", ()))
        words |= set(document.get("spatial", {}).get("signatureSubjects", ()))
        words |= set(document["emergency"]["triggers"]) | set(document["emergency"]["actions"])
        registry = skill_registry(kind)
        vocabulary = registry.vocabulary
        words |= set(registry.ids) | set(registry.facts)
        words |= set(vocabulary.categories) | set(vocabulary.permissions)
        words |= set(vocabulary.completion_evidence)
    observation = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text("utf-8")
    )
    decision = snapshot_decision(observation)
    words |= {drive.name for drive in homeostasis(decision, facts_from_observation(observation))}
    return words


def string_literals(path: Path) -> set[str]:
    found: set[str] = set()
    for token in tokenize.generate_tokens(io.StringIO(path.read_text("utf-8")).readline):
        if token.type == tokenize.STRING:
            try:
                value = ast.literal_eval(token.string)
            except (ValueError, SyntaxError):
                continue
            if isinstance(value, str):
                found.add(value)
    return found


def test_environment_vocabulary_never_leaks_into_core_cognition() -> None:
    """No core module branches on, or names, a word an environment owns: a
    drive, a memory subject, an emergency, a skill, a fact. Each is the
    environment's to say through its profile (ADR 0025)."""
    vocabulary = environment_vocabulary() - CORE_OWNED_WORDS
    assert {"food", "safety", "hostile", "hostile_swarm", "coal"} <= vocabulary
    leaks: dict[str, set[str]] = {}
    for path in sources(CORE_ROOTS):
        if path in COMPATIBILITY_ONLY:
            continue
        named = string_literals(path) & vocabulary
        if named:
            leaks[str(path.relative_to(REPOSITORY))] = named
    for file, words in leaks.items():
        unexpected = words - KNOWN_VOCABULARY_LEAKS.get(file, set())
        assert not unexpected, f"{file} names environment vocabulary {sorted(unexpected)}"
    for file, words in KNOWN_VOCABULARY_LEAKS.items():
        assert leaks.get(file, set()) == words, f"{file}: a known leak was fixed; shrink the list"


def test_affect_reads_a_goals_character_never_its_facts() -> None:
    """Which goals are protective is the environment's to say; affect biases
    by that character alone, so a second environment with its own facts gets
    the same affect, not one where every goal is outgoing."""
    import inspect

    from person_cognition.affect import Affect, AffectRecord, AffectState, GoalCharacter

    affect_py = REPOSITORY / "apps/cognition/python/person_cognition/affect.py"
    assert not any(name.startswith("person_minecraft") for name in imports(affect_py))
    assert string_literals(affect_py) & (environment_vocabulary() - CORE_OWNED_WORDS) == set()
    assert inspect.signature(Affect.bias).parameters["character"].annotation in (
        GoalCharacter,
        "GoalCharacter",
    )

    def toy_character(completion_facts: frozenset[str]) -> GoalCharacter:
        return "protective" if completion_facts & {"lamp_lit", "door_shut"} else "outgoing"

    uneasy = Affect(AffectRecord())
    uneasy.state = AffectState(valence=0.0, unease=1.0, control=0.0)
    toy_protective = uneasy.bias(toy_character(frozenset({"door_shut"})), "homeostasis")
    toy_outgoing = uneasy.bias(toy_character(frozenset({"lamp_oil"})), "homeostasis")
    assert toy_protective > toy_outgoing, "unease draws a toy world's protective goal forward"

    from person_minecraft.goals import goal_character

    assert toy_protective == uneasy.bias(goal_character(frozenset({"safe"})), "homeostasis")
    assert toy_outgoing == uneasy.bias(goal_character(frozenset({"tool_tier"})), "homeostasis")


def test_every_emergency_says_what_it_is_about() -> None:
    """The environment classifies each of its emergencies for memory; none is
    left to a guess from its name, and each subject is one memory accepts."""
    from person_cognition.memory import SUBJECTS
    from person_minecraft.memory import EMERGENCY_SUBJECTS
    from person_protocol import discovered

    triggers = discovered()["minecraft"].document["emergency"]["triggers"]
    assert set(EMERGENCY_SUBJECTS) == set(triggers)
    assert all(set(about) <= SUBJECTS for about in EMERGENCY_SUBJECTS.values())


def test_whether_a_drive_is_pressing_is_typed_not_named() -> None:
    """The core reads a drive's `pressing` flag, never its name, so another
    environment's drives work unchanged."""
    from person_cognition.goals import Drive
    from person_cognition.hypotheses.experiments import calm
    from person_cognition.projects import ProjectBook, ProjectManager

    urgent = [Drive("lamp_oil", 0.9, "oil_low", pressing=True)]
    leisure = [Drive("lamp_polish", 0.9, "lamp_dull", pressing=False)]
    assert not calm(urgent, night=False)
    assert calm(leisure, night=False)
    from person_minecraft.projects import TEMPLATES

    def considered(drives: list[Drive]) -> list[Any]:
        manager = ProjectManager(ProjectBook(), TEMPLATES)
        return manager.consider(state={}, drives=drives, home_place="p", night=False, now=0)

    assert considered(urgent) == []
    assert considered(leisure), "a need that is not pressing leaves Person free to take one up"


# ------------------------------------------------------- the epistemic boundary


#: The core-cognition modules that read the observation payload for themselves:
#: none. The loop hands the message to the environment profile, once.
PAYLOAD_KEYS = {
    "payload",
    "vitals",
    "nearby",
    "inventory",
    "affordances",
    "navigation",
    "dayPhase",
    "hostiles",
    "passiveAnimals",
}


def test_nothing_downstream_of_the_boundary_reads_a_raw_observation() -> None:
    for path in sources(
        [
            REPOSITORY / "apps/cognition/python",
            REPOSITORY / "packages/planner/python",
            REPOSITORY / "packages/policy/python",
            REPOSITORY / "packages/epistemics/python",
        ]
    ):
        for token in tokenize.generate_tokens(io.StringIO(path.read_text("utf-8")).readline):
            if token.type == tokenize.STRING and len(token.string) < 40:
                leaked = set(re.findall(r"\w+", token.string)) & PAYLOAD_KEYS
                # An `acted` episode keeps the inventory changes the runtime
                # reported in its outcome, under that name: memory, not a percept.
                if path.parent.name == "memory":
                    leaked -= {"inventory"}
                assert not leaked, f"{path.relative_to(REPOSITORY)} reads {sorted(leaked)}"


def test_the_loop_crosses_the_boundary_once_per_observation() -> None:
    loop = (REPOSITORY / "apps/cognition/python/person_cognition/loop.py").read_text("utf-8")
    assert loop.count("environment.perceive(message)") == 1
    for forbidden in ("symbolic_state", "_last_observation", 'message["selfMotion"]'):
        assert forbidden not in loop, forbidden


#: Where Person plans: choosing goals, projects and investigations, deriving the
#: planning facts, and searching for plans. Planning may use what memory
#: supplies through the epistemic pipeline (`DecisionState.recalled`, or a
#: bounded recall the loop makes and hands over); it may never reach the
#: memory store, the journal, or recall for itself.
#:
#:     MemoryStore -> bounded recall (loop, typed Cue) -> DecisionState.recalled -> planning
#:     planner -> MemoryStore                                              forbidden
PLANNING_SOURCES = [
    REPOSITORY / "packages/planner/python",
    REPOSITORY / "apps/cognition/python/person_cognition/goals.py",
    REPOSITORY / "apps/cognition/python/person_cognition/projects.py",
    REPOSITORY / "apps/cognition/python/person_cognition/search.py",
    REPOSITORY / "apps/cognition/python/person_cognition/hypotheses",
    MINECRAFT / "python/person_minecraft/facts.py",
    MINECRAFT / "python/person_minecraft/goals.py",
    MINECRAFT / "python/person_minecraft/projects.py",
    MINECRAFT / "python/person_minecraft/context.py",
    MINECRAFT / "python/person_minecraft/situation.py",
    MINECRAFT / "python/person_minecraft/envelope.py",
]

#: What would let planning query memory for itself. The `Recalled` and
#: `Episode` types are allowed: they are what a bounded recall hands over.
MEMORY_ACCESS = {
    "Memory",
    "MemoryStore",
    "WorkingMemory",
    "Cue",
    "recall",
    "recall_for_deliberation",
    "episodes_in",
    "EventJournal",
    "EventStore",
    "SnapshotStore",
}


def test_planning_never_queries_the_memory_store() -> None:
    paths = [
        path
        for root in PLANNING_SOURCES
        for path in ([root] if root.suffix == ".py" else sources([root]))
    ]
    assert len(paths) > len(PLANNING_SOURCES), "every planning source is checked"
    for path in paths:
        for name in imports(path):
            assert not name.startswith(
                ("person_cognition.memory.store", "person_persistence.journal")
            ), f"{path.relative_to(REPOSITORY)} imports {name}"
        names = {
            node.id if isinstance(node, ast.Name) else node.attr
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.Name | ast.Attribute)
        }
        imported = {
            alias.asname or alias.name
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        reached = sorted((names | imported) & MEMORY_ACCESS)
        assert not reached, f"{path.relative_to(REPOSITORY)} reaches memory directly: {reached}"


def test_recalled_memory_reaches_planning_but_never_as_a_current_fact() -> None:
    """A recalled episode is in the decision state, labelled as memory, and the
    planning facts (what is true now) are exactly what they are without it."""
    from person_cognition.memory import Episode, Provenance, Recalled
    from person_minecraft.facts import planning_facts
    from person_minecraft.offline import snapshot_decision

    observation = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text("utf-8")
    )
    assert not any(r["kind"] == "coal" for r in observation["payload"]["nearby"]["resources"])
    coal = Recalled(
        episode=Episode(
            memory_id="mem_coal",
            kind="perceived",
            subjects=("coal",),
            experienced_tick=10,
            world_tick=10,
            episode_id="ep",
            experience="lived:minecraft/fixture",
            salience=0.6,
            details={"count": 3},
            provenance=Provenance("perceived", message_id="m-earlier"),
        ),
        age=5,
        relevance=1.0,
        accessibility=1.0,
    )
    remembering = snapshot_decision(observation, recalled=(coal,))
    assert remembering.recalled == (coal,) and remembering.recalled[0].source == "memory"
    assert planning_facts(remembering) == planning_facts(snapshot_decision(observation))
    assert planning_facts(remembering)["reachable_coal"] == 0.0


def test_privileged_world_truth_has_no_way_into_cognition() -> None:
    forbidden = {"WorldSnapshot", "homeDistance", "yaw", "pitch", "position", "entityId"}
    for path in sources([REPOSITORY / "apps/cognition/python", MINECRAFT / "python"]):
        if path.name in {"quarantine.py", "proposal.py"}:
            continue  # The gates name what is privileged so that they can refuse it.
        leaked = code_words(path) & forbidden
        assert not leaked, f"{path.relative_to(REPOSITORY)} names {sorted(leaked)}"


# ---------------------------------------------------------------- provenance


def test_every_episode_source_is_lived() -> None:
    from person_cognition.memory.episodes import SOURCE_CLASSES, Provenance
    from person_epistemics import IMAGINED, LIVED, Source

    assert set(SOURCE_CLASSES.values()) <= LIVED
    for source in Source:
        assert source.value not in SOURCE_CLASSES, "a provenance class is not an episode source"
    with pytest.raises(ValueError):
        Provenance("model_rollout")
    assert IMAGINED.isdisjoint(set(SOURCE_CLASSES.values()))


def test_a_canonical_event_is_not_evidence_unless_admitted() -> None:
    from person_cognition.admission import EVIDENCE_ADMISSIONS
    from person_cognition.effect_learning import EffectBeliefs
    from person_epistemics import BeliefState, ExperienceKey
    from person_persistence import EVENT_TYPES, new_event

    assert set(EVIDENCE_ADMISSIONS) == {"belief_revised", "effect_evidence", "hypothesis_evidence"}
    for never in ("memory_recalled", "memory_encoded", "deliberation_completed", "episode_started"):
        assert never not in EVIDENCE_ADMISSIONS
    for event_type in sorted(set(EVENT_TYPES) - set(EVIDENCE_ADMISSIONS)):
        event = new_event(
            person_id="ada",
            world_id="w",
            session_id="00000000-0000-4000-8000-000000000001",
            episode_id="ep",
            decision_id=None,
            tick=1,
            policy_revision=0,
            experience=ExperienceKey("minecraft", "fixture"),
            event_type=event_type,
            payload={},
            previous_event_id=None,
        )
        for reducer in (EffectBeliefs(), BeliefState()):
            before = json.dumps(reducer.to_json(), sort_keys=True)
            try:
                reducer.apply(event)
            except (KeyError, TypeError):
                pytest.fail(f"{type(reducer).__name__} read a {event_type} as evidence")
            after = json.dumps(reducer.to_json(), sort_keys=True)
            assert before == after, f"{event_type} moved {type(reducer).__name__}"


def test_a_predictive_model_has_no_route_to_the_body() -> None:
    for path in (
        REPOSITORY / "apps/cognition/python/person_cognition/predictors.py",
        REPOSITORY / "packages/epistemics/python/person_epistemics/prediction.py",
    ):
        modules = imports(path)
        assert "person_protocol" not in modules and not any(
            name.startswith(("subprocess", "socket")) for name in modules
        ), path.name
        words = code_words(path)
        for forbidden in ("_send", "encode_frame", "SkillInvocation", "embodiment", "write"):
            assert forbidden not in words, f"{path.name} uses {forbidden}"


def test_prediction_is_plural_and_a_prediction_is_never_evidence() -> None:
    from person_cognition import future_providers
    from person_cognition.predictors import DeclaredEffectModel
    from person_epistemics import (
        EvidenceRefused,
        ExperienceKey,
        Intervention,
        PredictionQuery,
        PredictiveModel,
        Predictors,
        Scope,
        Source,
        admit,
    )
    from person_skills import skill_registry

    # No singleton world model is reserved any more (ADR 0028); the first
    # predictive model is the declared-effect model Person always had.
    assert not hasattr(future_providers, "WorldModelProvider")
    registry = skill_registry("minecraft")
    model = DeclaredEffectModel(registry, "minecraft")
    assert isinstance(model, PredictiveModel)
    skill = next(
        spec.id
        for spec in map(registry.get, registry.ids)
        if spec.expected_effects and not spec.parameters
    )
    [prediction] = Predictors([model]).predict(
        PredictionQuery(state={}, intervention=Intervention(skill), belief_version=3)
    )
    assert prediction.source is Source.MODEL_ROLLOUT
    assert prediction.identity()["model_id"] == "declared_effects"
    assert prediction.belief_version == 3
    with pytest.raises(EvidenceRefused):
        admit(
            bears_on=prediction.outcomes[0].target,
            value=prediction.outcomes[0].value,
            source=prediction.source,
            scope=Scope.world("minecraft", "w"),
            observed_at=0,
            confidence=1.0,
            refs=("prediction",),
            experience=ExperienceKey("minecraft", "fixture"),
        )


def test_only_the_loop_proposes_a_physical_action() -> None:
    for path in sources([REPOSITORY / "apps/cognition/python", MINECRAFT / "python"]):
        if path.name == "loop.py":
            continue
        assert '"SkillInvocation"' not in path.read_text(encoding="utf-8"), path.name


def test_knowledge_is_initial_until_an_explicit_promotion_exists() -> None:
    from person_epistemics import (
        NEVER_EVIDENCE,
        Knowledge,
        KnowledgeRefused,
        KnownFact,
        Scope,
        Source,
    )

    initial = Knowledge(skills=None, facts={})
    assert initial.source is Source.INITIAL_KNOWLEDGE and initial.learned == ()

    # The core has room for learned knowledge: a promoted belief keeps its
    # value, confidence, basis, evidence and scope, and names its promotion.
    world = Scope.world("minecraft", "w")
    promoted = KnownFact(
        key="shelter_state",
        value="complete",
        confidence=0.9,
        basis=Source.RUNTIME_REPORT,
        evidence_refs=("m-1", "m-2"),
        scope=world,
        promoted_by="evt-promotion",
    )
    assert Knowledge(skills=None, facts={}, learned=(promoted,)).learned[0].scope == world

    # Nothing that is not evidence becomes knowledge, and nothing without it.
    for source in NEVER_EVIDENCE:
        with pytest.raises(KnowledgeRefused):
            KnownFact("k", 1, 0.5, source, ("m",), world, "evt")
    with pytest.raises(KnowledgeRefused):
        KnownFact("k", 1, 0.5, Source.REAL_OBSERVATION, (), world, "evt")
    with pytest.raises(KnowledgeRefused):
        KnownFact("k", 1, 0.5, Source.REAL_OBSERVATION, ("m",), world, "")

    # No promotion gate exists yet, so no production code makes learned
    # knowledge, and only the loop's decision state (and the offline tools'
    # copy of it) builds Knowledge at all. A gate arrives by its own decision.
    roots = [*CORE_ROOTS, MINECRAFT / "python"]
    promoters = [
        str(path.relative_to(REPOSITORY))
        for path in sources(roots)
        if path.parent.name != "person_epistemics"
        and re.search(r"(?<![A-Za-z])KnownFact\(|learned=", path.read_text(encoding="utf-8"))
    ]
    assert promoters == [], f"nothing promotes to knowledge yet: {promoters}"
    builders = [
        path.relative_to(REPOSITORY)
        for path in sources([REPOSITORY / "apps/cognition/python", MINECRAFT / "python"])
        if re.search(r"(?<![A-Za-z])Knowledge\(", path.read_text(encoding="utf-8"))
    ]
    assert sorted(map(str, builders)) == sorted(
        [
            "apps/cognition/python/person_cognition/loop.py",
            "environments/minecraft/python/person_minecraft/offline.py",
        ]
    )


def test_no_code_widens_a_belief_but_the_explicit_gate() -> None:
    callers = []
    for path in sources([*CORE_ROOTS, MINECRAFT / "python"]):
        text = path.read_text(encoding="utf-8")
        if path.name == "scope.py":
            continue
        if "check_widening(" in text or "Scope.general(" in text or "Scope.environment(" in text:
            callers.append(path.relative_to(REPOSITORY))
    assert callers == [], f"only an explicit widening may broaden a belief: {callers}"


# ----------------------------------------------------------------- lifecycle


def life_event(event_type: str, **payload: Any) -> Any:
    from person_epistemics import ExperienceKey
    from person_persistence import new_event

    return new_event(
        person_id="person-000",
        world_id="w",
        session_id="00000000-0000-4000-8000-000000000001",
        episode_id="ep",
        decision_id=None,
        tick=1,
        policy_revision=0,
        experience=ExperienceKey("minecraft", "fixture"),
        event_type=event_type,
        payload=payload,
        previous_event_id=None,
    )


def test_respawn_continues_the_same_person_and_terminal_death_is_final() -> None:
    from person_persistence import LifeRecord

    life = LifeRecord()
    life.apply(life_event("person_died", terminal=False))
    assert life.status == "awaiting_respawn"
    life.apply(life_event("person_respawned"))
    assert life.status == "alive" and life.deaths == 1 and life.respawns == 1

    life.apply(life_event("person_died", terminal=True))
    assert life.status == "terminated"
    life.apply(life_event("person_respawned"))
    assert life.status == "terminated", "nothing brings a terminated Person back"


def test_respawn_is_the_default_and_permadeath_is_an_explicit_choice() -> None:
    schema = json.loads(
        (REPOSITORY / "packages/config/schema/person-config.schema.json").read_text("utf-8")
    )
    lifecycle = schema["properties"]["lifecycle"]
    assert "required" not in lifecycle and lifecycle["properties"]["death"]["enum"] == [
        "respawn",
        "permadeath",
    ]
    for path in sorted((REPOSITORY / "examples").glob("*.toml")):
        assert "permadeath" not in path.read_text(encoding="utf-8"), path.name
