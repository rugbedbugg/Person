"""The projects Minecraft offers Person (ADR 0009, ADR 0025).

The project mechanism is Person's (`person_cognition.projects`); which
commitments make sense in Minecraft, and what their milestones are, is the
Minecraft profile's.
"""

from __future__ import annotations

from collections.abc import Mapping

from person_cognition.projects import Milestone, Template
from person_skills import Condition

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
