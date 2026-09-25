"""Projects: persistent commitments that outlast the goal of the moment.

A goal is what Person is trying to accomplish now. A project is something it
has decided to see through: "make this home livable", "keep food in hand". It
is a cognitive record with an identity, a purpose, milestones, a status, the
reason it was taken up, the interruptions it has suffered and the failures it
has met, anchored to a place in Person's own map. It is not a skill and not a
routine, and it holds no coordinate or runtime target.

The causal chain it sits in:

    bodily and world signals -> drives (homeostasis) -> candidate goals
        -> bounded priority selection (the goal stack) -> a project's next
        milestone as a goal -> planning and action -> interruption by a more
        urgent need -> resumption when that need passes

Selection is deliberately plain. A project starts only when Person's pressing
needs are calm; templates are tried in a fixed order and the first that fits
is taken (satisficing, not optimising); at most two are open; only the oldest
open one pursues its next milestone, at a fixed priority below urgent needs.
A milestone that keeps being blocked makes the project impossible, and it is
abandoned. After a restart a project resumes only if it still applies.

Projects are rebuilt from `project_started` and `project_changed` journal
events, and from nothing else.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from person_persistence import EvidenceEvent
from person_skills import Condition

from .goals import Drive, Goal, GoalStack

#: Below the urgent needs (food 400+, shelter at night 650+, danger 900+) and
#: above the maintenance ones. A parameter.
PROJECT_PRIORITY = 300.0
#: At most this many projects are open at once.
MAX_OPEN = 2
#: A milestone blocked this many times makes its project impossible.
BLOCKS_TO_ABANDON = 2
#: No new project while any pressing need is more urgent than this.
CALM = 0.3
#: An abandoned kind is not taken up again for a Minecraft day of experience.
ABANDON_COOLDOWN = 24_000

PRESSING_DRIVES = ("health", "food", "safety")
OPEN = frozenset({"ACTIVE", "SUSPENDED"})


@dataclass(frozen=True, slots=True)
class Milestone:
    name: str
    goal_type: str
    condition: Condition


@dataclass(frozen=True, slots=True)
class Template:
    kind: str
    purpose: str
    milestones: tuple[Milestone, ...]
    #: Memory subjects for recalling how this kind of work has gone.
    subjects: tuple[str, ...]
    reason: str


TEMPLATES: tuple[Template, ...] = (
    Template(
        kind="improve_home",
        purpose="make_home_livable",
        milestones=(
            Milestone("shelter", "SECURE_SHELTER", Condition("shelter_complete", ">=", 1)),
            Milestone(
                "storage", "ESTABLISH_STORAGE", Condition("owned_storage_available", ">=", 1)
            ),
        ),
        subjects=("shelter", "storage"),
        reason="home_attachment",
    ),
    Template(
        kind="secure_food_supply",
        purpose="keep_food_in_hand",
        milestones=(Milestone("cooked_food", "SECURE_FOOD", Condition("cooked_food", ">=", 4)),),
        subjects=("food",),
        reason="food_security",
    ),
)
BY_KIND: Mapping[str, Template] = {template.kind: template for template in TEMPLATES}


@dataclass(frozen=True, slots=True)
class Project:
    project_id: str
    kind: str
    purpose: str
    status: str
    reasons: tuple[str, ...]
    #: The cognitive place it is anchored to: Person's home, by its own map.
    anchor: str | None
    started_at: int
    completed: tuple[str, ...] = ()
    interruptions: tuple[dict[str, Any], ...] = ()
    blocks: tuple[tuple[str, int], ...] = ()
    note: str | None = None

    @property
    def template(self) -> Template:
        return BY_KIND[self.kind]

    @property
    def goal_id(self) -> str:
        return f"goal_{self.project_id}"

    def next_milestone(self, state: Mapping[str, float]) -> Milestone | None:
        """The first milestone not met now. Satisficing: the world decides."""
        for milestone in self.template.milestones:
            if not milestone.condition.holds(dict(state)):
                return milestone
        return None

    def blocked(self, milestone: str) -> int:
        return dict(self.blocks).get(milestone, 0)

    def to_json(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "kind": self.kind,
            "purpose": self.purpose,
            "status": self.status,
            "reasons": list(self.reasons),
            "anchor": self.anchor,
            "started_at": self.started_at,
            "completed": list(self.completed),
            "interruptions": [dict(item) for item in self.interruptions],
            "blocks": [list(item) for item in self.blocks],
            "note": self.note,
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> Project:
        return cls(
            project_id=str(body["project_id"]),
            kind=str(body["kind"]),
            purpose=str(body["purpose"]),
            status=str(body["status"]),
            reasons=tuple(str(reason) for reason in body["reasons"]),
            anchor=body.get("anchor"),
            started_at=int(body["started_at"]),
            completed=tuple(str(name) for name in body["completed"]),
            interruptions=tuple(dict(item) for item in body["interruptions"]),
            blocks=tuple((str(name), int(count)) for name, count in body["blocks"]),
            note=body.get("note"),
        )


class ProjectBook:
    """Every project Person has taken up, rebuilt from its own records."""

    def __init__(self) -> None:
        self._projects: dict[str, Project] = {}

    def reset(self) -> None:
        self._projects.clear()

    def apply(self, event: EvidenceEvent) -> None:
        if event.type in {"project_started", "project_changed"}:
            project = Project.from_json(event.payload["project"])
            self._projects[project.project_id] = project

    def to_json(self) -> dict[str, Any]:
        return {"projects": [project.to_json() for project in self._projects.values()]}

    def load_json(self, body: Mapping[str, Any]) -> None:
        self.reset()
        for record in body["projects"]:
            project = Project.from_json(record)
            self._projects[project.project_id] = project

    def projects(self) -> tuple[Project, ...]:
        return tuple(self._projects.values())

    def __len__(self) -> int:
        return len(self._projects)


Change = tuple[str, dict[str, Any]]


def _change(kind: str, project: Project, change: str) -> Change:
    return kind, {"change": change, "project": project.to_json()}


@dataclass
class ProjectManager:
    """Takes up, pursues, interrupts, resumes and gives up projects."""

    book: ProjectBook
    #: The project whose goal was active on the last update, if any.
    _pursuing: str | None = None
    #: Projects already re-examined since this process started.
    _examined: set[str] = field(default_factory=set)

    def unfinished(self) -> list[Project]:
        return [project for project in self.book.projects() if project.status in OPEN]

    def current(self) -> Project | None:
        """The one project that pursues a milestone: the oldest open one."""
        candidates = [project for project in self.unfinished() if project.note != "home_unknown"]
        return candidates[0] if candidates else None

    # ------------------------------------------------------------- choosing

    def consider(
        self,
        *,
        state: Mapping[str, float],
        drives: list[Drive],
        home_place: str | None,
        night: bool,
        now: int,
    ) -> list[Change]:
        """Perhaps take up a new project. Only when calm, and only one at a time."""
        pressing = {drive.name: drive.urgency for drive in drives if drive.name in PRESSING_DRIVES}
        calm = all(urgency <= CALM for urgency in pressing.values()) and not night
        if not calm or home_place is None or len(self.unfinished()) >= MAX_OPEN:
            return []
        busy = {project.kind for project in self.unfinished()}
        for template in TEMPLATES:
            if template.kind in busy or self._cooling(template.kind, now):
                continue
            candidate = Project(
                project_id=f"project_{len(self.book) + 1}",
                kind=template.kind,
                purpose=template.purpose,
                status="SUSPENDED",
                reasons=(template.reason, "needs_calm"),
                anchor=home_place,
                started_at=now,
            )
            if candidate.next_milestone(state) is None:
                continue  # Already true of the world: nothing to commit to.
            self._examined.add(candidate.project_id)
            return [_change("project_started", candidate, "started")]
        return []

    def _cooling(self, kind: str, now: int) -> bool:
        return any(
            project.kind == kind
            and project.status == "ABANDONED"
            and now - project.started_at < ABANDON_COOLDOWN
            for project in self.book.projects()
        )

    # ------------------------------------------------------------ pursuing

    def goal(self, state: Mapping[str, float], tick: int) -> Goal | None:
        """The current project's next milestone, as a goal to compete."""
        project = self.current()
        if project is None:
            return None
        milestone = project.next_milestone(state)
        if milestone is None:
            return None
        return Goal(
            goal_id=project.goal_id,
            goal_type=milestone.goal_type,
            priority=PROJECT_PRIORITY,
            source="self_generated",
            created_at_tick=tick,
            status="QUEUED",
            completion_condition=(milestone.condition,),
            reason_codes=(f"project_{project.kind}", f"milestone_{milestone.name}"),
        )

    def reexamine(
        self, *, state: Mapping[str, float], home_place: str | None, failures: int
    ) -> list[Change]:
        """Before pursuing a project this process did not start, check it still applies.

        A project survives a restart, and the world may have moved on: its
        milestones may all be met, or Person may not know where its home is.
        """
        changes: list[Change] = []
        for project in self.unfinished():
            waiting = project.note == "home_unknown"
            if project.project_id in self._examined and not waiting:
                continue
            self._examined.add(project.project_id)
            if waiting and home_place is None:
                continue
            if project.next_milestone(state) is None:
                done = replace(project, status="COMPLETE", note="already_done")
                changes.append(_change("project_changed", done, "completed"))
            elif home_place is None:
                parked = replace(project, status="SUSPENDED", note="home_unknown")
                changes.append(_change("project_changed", parked, "suspended"))
            else:
                reasons = project.reasons
                if failures:
                    reasons = tuple(dict.fromkeys((*reasons, "recalls_earlier_failure")))
                resumed = replace(project, note="resumed_after_restart", reasons=reasons)
                changes.append(_change("project_changed", resumed, "resumed"))
        return changes

    def unexamined(self) -> list[Project]:
        """Open projects this process has not yet checked, or that wait on home."""
        return [
            project
            for project in self.unfinished()
            if project.project_id not in self._examined or project.note == "home_unknown"
        ]

    def track(self, goals: GoalStack, state: Mapping[str, float], now: int) -> list[Change]:
        """Follow the current project's goal through the stack, and record what happened."""
        project = self.current()
        if project is None:
            self._pursuing = None
            return []
        entry = goals.entries.get(project.goal_id)
        changes: list[Change] = []

        completed = tuple(
            milestone.name
            for milestone in project.template.milestones
            if milestone.condition.holds(dict(state))
        )
        if completed != project.completed:
            project = replace(project, completed=completed)
            if project.next_milestone(state) is None:
                done = replace(project, status="COMPLETE", note="milestones_met")
                self._pursuing = None
                return [_change("project_changed", done, "completed")]
            changes.append(_change("project_changed", project, "progressed"))

        if entry is None:
            return changes
        if entry.status == "ACTIVE" and project.status != "ACTIVE":
            resumed = project.status == "SUSPENDED" and bool(project.interruptions)
            project = replace(project, status="ACTIVE", note=None)
            changes.append(_change("project_changed", project, "resumed" if resumed else "active"))
            self._pursuing = project.project_id
        elif (
            entry.status == "SUSPENDED"
            and project.status == "ACTIVE"
            and (entry.suspension_reason or "").startswith("preempted_by_")
        ):
            interruption = {
                "by": (entry.suspension_reason or "").removeprefix("preempted_by_"),
                "at": now,
            }
            project = replace(
                project,
                status="SUSPENDED",
                interruptions=(*project.interruptions[-7:], interruption),
                note="interrupted",
            )
            changes.append(_change("project_changed", project, "interrupted"))
            self._pursuing = None
        elif entry.status == "BLOCKED":
            milestone = project.next_milestone(state)
            name = milestone.name if milestone else "unknown"
            count = project.blocked(name) + 1
            blocks = tuple((key, value) for key, value in project.blocks if key != name)
            project = replace(project, blocks=(*blocks, (name, count)))
            if count >= BLOCKS_TO_ABANDON:
                given_up = replace(project, status="ABANDONED", note=f"blocked_{name}")
                changes.append(_change("project_changed", given_up, "abandoned"))
            else:
                # One more chance: queue the milestone again.
                goals.reopen(project.goal_id, now)
                changes.append(_change("project_changed", project, "blocked"))
        return changes
