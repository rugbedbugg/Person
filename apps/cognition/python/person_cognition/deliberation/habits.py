"""Evidence-backed habits: identity, episodes and the book (ADR 0022).

What can become a habit is a trigger-conditioned goal policy, never an
action sequence: when this familiar problem occurs in this matching context,
this goal has repeatedly resolved it. A resolution counts only after a
stabilization window with no new raw signal of the same problem. Three
consecutive independent successes of the same response template make it
promotable.

C4 is shadow only. Its events are a separate stream that the active book,
from which C5 will invoke habits, never reads: running record-only cannot
change behaviour in this session or any later one.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from person_persistence import EvidenceEvent

from .context import breath_band, food_band, health_band

CONTEXT_SIGNATURE_SCHEMA = "context_signature_v1"
RESPONSE_TEMPLATE_SCHEMA = "response_template_v1"
#: Declared engineering priors (ADR 0022), in experienced ticks or counts.
STABILIZATION_WINDOW = 1_200
PROMOTION_STREAK = 3

#: Trigger classes whose source goal is blocked by the very failures that
#: raised them, so silence afterwards proves nothing. Their success also needs
#: positive resolution evidence: the source goal, retried, succeeding at least
#: once inside the window (ADR 0021/0022 amendment, C4.1).
NEEDS_RESOLUTION: frozenset[str] = frozenset({"repeated_failure", "no_viable_plan"})

#: Inventory categories a response's desired facts make relevant. A fact
#: with no declared mapping adds no inventory to the signature.
INVENTORY_FOR_FACT: Mapping[str, tuple[str, ...]] = {
    "wood": ("wood",),
    "planks": ("wood",),
    "stone": ("stone",),
    "coal": ("coal", "fuel"),
    "fuel": ("fuel",),
    "raw_food": ("raw_food",),
    "cooked_food": ("cooked_food", "raw_food", "fuel"),
    "plant_food": ("food",),
    "edible_food": ("food",),
    "food_level": ("food",),
    "building_materials": ("building_materials",),
    "shelter_complete": ("building_materials",),
    "wooden_pickaxe": ("tools",),
    "stone_pickaxe": ("tools",),
    "wooden_axe": ("tools",),
    "stone_axe": ("tools",),
    "tool_tier": ("tools",),
}

SHADOW_EVENTS: frozenset[str] = frozenset(
    {
        "habit_candidate_shadow",
        "habit_evidence_shadow",
        "habit_promotion_shadow",
        "habit_conflict_shadow",
    }
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def signature_sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _count_band(count: int) -> str:
    return "one" if count <= 1 else "few" if count <= 3 else "many"


def _confidence_band(confidence: float) -> str:
    return "high" if confidence >= 0.8 else "medium"


def context_signature(
    *,
    observation: Mapping[str, Any] | None,
    place: Mapping[str, Any] | None,
    desired_facts: Sequence[str],
    source_goal_type: str | None,
) -> dict[str, Any]:
    """`context_signature_v1`: coarse, Person-visible, deterministic."""
    vitals = (observation or {}).get("vitals", {})
    environment = (observation or {}).get("environment", {})
    nearby = (observation or {}).get("nearby", {})
    threats: dict[str, dict[str, Any]] = {}
    for hostile in nearby.get("hostiles", []):
        kind = str(hostile.get("name") or hostile.get("kind"))
        entry = threats.setdefault(kind, {"count": 0, "nearest": hostile.get("rangeBand")})
        entry["count"] += 1
    categories = (observation or {}).get("inventory", {}).get("categories", {})
    relevant = sorted({c for fact in desired_facts for c in INVENTORY_FOR_FACT.get(fact, ())})
    recognised = place is not None and float(place.get("confidence", 0.0)) >= 0.5
    return {
        "schema": CONTEXT_SIGNATURE_SCHEMA,
        "health": health_band(float(vitals.get("health", 20.0))),
        "food": food_band(float(vitals.get("food", 20.0))),
        "breath": breath_band(float(vitals.get("breath", 10.0))),
        "day_phase": str(environment.get("dayPhase", "unknown")),
        "weather": str(environment.get("weather", "unknown")),
        "place": (
            {
                "ref": str(place["place_id"]),
                "confidence": _confidence_band(float(place["confidence"])),
            }
            if recognised and place is not None
            else "unknown"
        ),
        "threats": [
            {"kind": kind, "count": _count_band(entry["count"]), "nearest": entry["nearest"]}
            for kind, entry in sorted(threats.items())
        ],
        "inventory": {
            category: "some" if categories.get(category) else "0" for category in relevant
        },
        "source_goal_type": source_goal_type or "none",
    }


def template_id(
    *,
    trigger_kind: str,
    semantic_key: str,
    signature: Mapping[str, Any],
    goal_type: str,
    desired: Sequence[Sequence[Any]],
) -> str:
    """A habit's identity, from what it means: never from deliberation ids."""
    return (
        "hab_"
        + signature_sha(
            {
                "schema": RESPONSE_TEMPLATE_SCHEMA,
                "scope": [trigger_kind, semantic_key],
                "signature": signature,
                "goal_type": goal_type,
                "desired": sorted([str(fact), str(direction)] for fact, direction in desired),
            }
        )[:24]
    )


@dataclass
class Template:
    template_id: str
    trigger_kind: str
    semantic_key: str
    signature_sha: str
    goal_type: str
    desired: list[list[str]]
    successes: int = 0
    failures: int = 0
    inconclusive: int = 0
    streak: int = 0
    state: str = "candidate"
    founding: list[str] = field(default_factory=list)

    def scope(self) -> tuple[str, str, str]:
        return (self.trigger_kind, self.semantic_key, self.signature_sha)

    def to_json(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "trigger_kind": self.trigger_kind,
            "semantic_key": self.semantic_key,
            "signature_sha": self.signature_sha,
            "goal_type": self.goal_type,
            "desired": self.desired,
            "successes": self.successes,
            "failures": self.failures,
            "inconclusive": self.inconclusive,
            "streak": self.streak,
            "state": self.state,
            "founding": self.founding,
        }


class HabitBook:
    """Templates and their evidence, rebuilt from one event stream only.

    The shadow book reads only the record-only stream; the active book reads
    only the active stream. Neither ever sees the other's events.
    """

    STREAMS: Mapping[str, Mapping[str, str]] = {
        "shadow": {
            "candidate": "habit_candidate_shadow",
            "evidence": "habit_evidence_shadow",
            "promotion": "habit_promotion_shadow",
            "conflict": "habit_conflict_shadow",
        },
        "active": {
            "candidate": "habit_candidate_formed",
            "evidence": "habit_evidence",
            "promotion": "habit_promoted",
            "conflict": "habit_conflict",
        },
    }

    def __init__(self, stream: str) -> None:
        self.stream = stream
        self.events = self.STREAMS[stream]
        self.templates: dict[str, Template] = {}

    def reset(self) -> None:
        self.templates.clear()

    def promoted_for(self, scope: tuple[str, str, str]) -> Template | None:
        return next(
            (t for t in self.templates.values() if t.scope() == scope and t.state == "promoted"),
            None,
        )

    def apply(self, event: EvidenceEvent) -> None:
        payload = event.payload
        if event.type == self.events["candidate"]:
            body = payload["template"]
            self.templates[str(body["template_id"])] = Template(
                template_id=str(body["template_id"]),
                trigger_kind=str(body["trigger_kind"]),
                semantic_key=str(body["semantic_key"]),
                signature_sha=str(body["signature_sha"]),
                goal_type=str(body["goal_type"]),
                desired=[list(item) for item in body["desired"]],
            )
        elif event.type == self.events["evidence"]:
            template = self.templates.get(str(payload["template_id"]))
            if template is None:
                return
            verdict = str(payload["verdict"])
            if verdict == "success":
                template.successes += 1
                template.streak += 1
                template.founding.append(str(payload["deliberation_id"]))
            elif verdict == "failure":
                template.failures += 1
                template.streak = 0
            else:
                template.inconclusive += 1
        elif event.type == self.events["promotion"]:
            template = self.templates.get(str(payload["template_id"]))
            if template is not None:
                template.state = "promoted"

    def to_json(self) -> dict[str, Any]:
        return {"templates": [t.to_json() for _, t in sorted(self.templates.items())]}

    def load_json(self, body: Mapping[str, Any]) -> None:
        self.reset()
        for item in body["templates"]:
            template = Template(**{k: item[k] for k in Template.__dataclass_fields__ if k in item})
            self.templates[template.template_id] = template


@dataclass
class Episode:
    """One adopted deliberation's journey toward evidence about its template."""

    deliberation_id: str
    template: dict[str, Any]
    semantic_key_full: str
    life_epoch: int
    world_epoch: int
    session: str
    stabilizing_since: int | None = None
    #: The goal whose trouble raised the trigger, when its class needs one.
    source_goal_id: str | None = None
    #: That source goal succeeded at something after the remedy was satisfied.
    resolved: bool = False

    @property
    def needs_resolution(self) -> bool:
        return str(self.template["trigger_kind"]) in NEEDS_RESOLUTION


class HabitTracker:
    """Turns adopted deliberations into success, failure or inconclusive evidence.

    C4 writes the shadow stream only. It never adds, removes or changes a
    goal; it only watches how adopted ones end and what follows.
    """

    def __init__(self, book: HabitBook) -> None:
        self.book = book
        self.episodes: dict[str, Episode] = {}

    def open(self, episode: Episode) -> None:
        self.episodes[episode.deliberation_id] = episode

    def goal_ended(self, deliberation_id: str, why: str, now: int, record: Any) -> None:
        episode = self.episodes.get(deliberation_id)
        if episode is None:
            return
        if why == "satisfied":
            episode.stabilizing_since = now
            return
        verdict = "inconclusive" if why == "session_ended" else "failure"
        self._conclude(episode, verdict, f"goal_{why}", now, record)

    def source_progress(self, goal_id: str, now: int) -> None:
        """A routine of `goal_id` succeeded: for an episode stabilizing after
        that goal's trouble, positive evidence the trouble was resolved."""
        for episode in self.episodes.values():
            if episode.source_goal_id == goal_id and episode.stabilizing_since is not None:
                episode.resolved = True

    def raw_signal(self, semantic_key_full: str, now: int, record: Any) -> None:
        """Any new qualifying raw signal of the same problem after the goal
        was satisfied, inside the window: it did not resolve it."""
        for episode in list(self.episodes.values()):
            if (
                episode.semantic_key_full == semantic_key_full
                and episode.stabilizing_since is not None
            ):
                self._conclude(episode, "failure", "recurred", now, record)

    def step(
        self, *, now: int, life_epoch: int, world_epoch: int, session: str, record: Any
    ) -> None:
        for episode in list(self.episodes.values()):
            if episode.life_epoch != life_epoch:
                self._conclude(episode, "failure", "died", now, record)
            elif episode.world_epoch != world_epoch or episode.session != session:
                self._conclude(episode, "inconclusive", "world_or_session", now, record)
            elif (
                episode.stabilizing_since is not None
                and now - episode.stabilizing_since >= STABILIZATION_WINDOW
            ):
                if episode.needs_resolution and not episode.resolved:
                    # Quiet because the goal was never tried again is not
                    # resolution: it may only have been given up on.
                    self._conclude(episode, "inconclusive", "no_retry", now, record)
                else:
                    self._conclude(episode, "success", "stable", now, record)

    def _conclude(self, episode: Episode, verdict: str, reason: str, now: int, record: Any) -> None:
        del self.episodes[episode.deliberation_id]
        events = self.book.events
        body = episode.template
        if body["template_id"] not in self.book.templates:
            record(events["candidate"], {"template": body, "experienced_tick": now})
        record(
            events["evidence"],
            {
                "template_id": body["template_id"],
                "deliberation_id": episode.deliberation_id,
                "verdict": verdict,
                "reason": reason,
                "experienced_tick": now,
            },
        )
        template = self.book.templates.get(body["template_id"])
        if template is None:
            return  # the book learns from the journal; nothing to promote yet
        if template.state == "candidate" and template.streak >= PROMOTION_STREAK:
            rival = self.book.promoted_for(template.scope())
            if rival is not None and rival.template_id != template.template_id:
                record(
                    events["conflict"],
                    {
                        "template_id": template.template_id,
                        "promoted_template_id": rival.template_id,
                        "experienced_tick": now,
                    },
                )
            else:
                record(
                    events["promotion"],
                    {
                        "template_id": template.template_id,
                        "founding": list(template.founding[-PROMOTION_STREAK:]),
                        "experienced_tick": now,
                    },
                )
