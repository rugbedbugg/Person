"""What a deliberation may answer, and the gate every answer passes (ADR 0020).

A proposal says what and why, never how: goals, project kinds, desired and
expected facts in Person's vocabulary, premises cited from its context, and
at most unordered references to offered capabilities as evidence that a
strategy is feasible. It cannot request, bind, sequence or parameterize a
skill. Everything the model returns is untrusted; the gate admits only a
proposal that is justified entirely by what Person could give it. Its stated
confidence is kept and has no weight.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .context import DeliberationContext

PROPOSAL_SCHEMA = "person-deliberation-proposal-v1"

INSTRUCTION_TEMPLATE = """\
You are a deliberative reasoning service consulted by Person, an artificial
inhabitant. You are not Person, and you have no memory of earlier calls.

The JSON context below is the complete factual basis of this deliberation.
Reason over its premises; do not import facts about Minecraft, its creatures,
items or mechanics, or about any world, from what you already know. If
something you would need is not in the context, name it under
evidence_needed instead of assuming it.

Answer with one JSON object and nothing else, of this form:
{
  "assessment": {"summary": text, "premises": [refs]},
  "uncertainties": [{"about": text, "premises": [refs]}],
  "strategies": [{
      "id": "s1" | "s2" | "s3",
      "goal_type": one of vocabulary.goal_types,
      "project_kind": one of vocabulary.project_kinds, or omitted,
      "desired": [{"fact": one of vocabulary.facts, "direction": one of vocabulary.directions}],
      "expected": [{"fact": ..., "direction": ..., "support": [refs]}],
      "capability_refs": [capability refs, unordered, only as evidence of feasibility],
      "premises": [refs]
  }],
  "preferred": a strategy id, or null,
  "evidence_needed": [{"kind": "observe" | "recall" | "test", "about": text}],
  "confidence": a number from 0 to 1
}

Rules: cite at least one premise for the assessment and for each strategy;
support every expected fact with a belief, a capability declaring that
effect, or a premise; name no skill to run and no order to run anything in;
write text without digits, positions or commands; at most 3 strategies,
4 uncertainties and 3 evidence requests; text under 280 characters.
"""

DIRECTIONS: tuple[str, ...] = ("increase", "decrease", "achieve", "avoid")


def _object(properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(properties),
        "properties": properties,
    }


_REFS: dict[str, object] = {"type": "array", "items": {"type": "string"}}
_EFFECT = _object({"fact": {"type": "string"}, "direction": {"type": "string"}})

#: The answer's shape, as the providers' structured-output modes take it: the
#: strict subset both accept (every key required, optional ones nullable, no
#: bounds). It shapes the answer; the gate, not the schema, decides it.
PROPOSAL_JSON_SCHEMA: dict[str, object] = _object(
    {
        "assessment": _object({"summary": {"type": "string"}, "premises": _REFS}),
        "uncertainties": {
            "type": "array",
            "items": _object({"about": {"type": "string"}, "premises": _REFS}),
        },
        "strategies": {
            "type": "array",
            "items": _object(
                {
                    "id": {"type": "string"},
                    "goal_type": {"type": "string"},
                    "project_kind": {"type": ["string", "null"]},
                    "desired": {"type": "array", "items": _EFFECT},
                    "expected": {
                        "type": "array",
                        "items": _object(
                            {
                                "fact": {"type": "string"},
                                "direction": {"type": "string"},
                                "support": _REFS,
                            }
                        ),
                    },
                    "capability_refs": _REFS,
                    "premises": _REFS,
                }
            ),
        },
        "preferred": {"type": ["string", "null"]},
        "evidence_needed": {
            "type": "array",
            "items": _object({"kind": {"type": "string"}, "about": {"type": "string"}}),
        },
        "confidence": {"type": "number"},
    }
)
EVIDENCE_KINDS: tuple[str, ...] = ("observe", "recall", "test")
STRATEGY_IDS: tuple[str, ...] = ("s1", "s2", "s3")

#: Words a proposal's text may not contain: privileged state, the machinery
#: behind Person, and claims of authority. Implementation parameter.
FORBIDDEN_WORDS: tuple[str, ...] = (
    "coordinate",
    "position",
    "journal",
    "snapshot",
    "pathfinder",
    "console",
    "operator",
    "command",
    "override",
    "bypass",
    "ignore safety",
    "seed",
)
_DIGIT = re.compile(r"\d")

TOP_KEYS = frozenset(
    {"assessment", "uncertainties", "strategies", "preferred", "evidence_needed", "confidence"}
)
STRATEGY_KEYS = frozenset(
    {"id", "goal_type", "project_kind", "desired", "expected", "capability_refs", "premises"}
)


@dataclass(frozen=True, slots=True)
class Verdict:
    """The gate's answer: the admitted proposal, or why there is none."""

    admitted: bool
    proposal: dict[str, Any] | None
    rejections: tuple[str, ...]
    #: The model's stated confidence, recorded with no weight.
    confidence: float | None


def _text(value: Any, limit: int, problems: set[str]) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        problems.add("schema")
        return None
    lowered = value.lower()
    if _DIGIT.search(value) or "/" in value:
        problems.add("privileged_text")
    if any(word in lowered for word in FORBIDDEN_WORDS):
        problems.add("privileged_text")
    return value


def _refs(value: Any, cap: int, problems: set[str]) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > cap
        or not all(isinstance(r, str) for r in value)
    ):
        problems.add("schema")
        return []
    return list(value)


def gate(text: str, context: DeliberationContext) -> Verdict:
    """Parse and ground one model answer against its context."""
    try:
        body = json.loads(text)
    except ValueError:
        return Verdict(False, None, ("malformed",), None)
    if not isinstance(body, dict):
        return Verdict(False, None, ("malformed",), None)
    problems: set[str] = set()
    vocabulary: Mapping[str, Any] = context.document["vocabulary"]
    goal_types = set(vocabulary.get("goal_types", ()))
    project_kinds = set(vocabulary.get("project_kinds", ()))
    facts = set(vocabulary.get("facts", ()))
    refs = context.refs

    def known(cited: list[str]) -> None:
        if any(ref not in refs for ref in cited):
            problems.add("unknown_premise")

    if set(body) - TOP_KEYS or not {"assessment", "strategies"} <= set(body):
        problems.add("schema")

    confidence = body.get("confidence")
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, int | float)
        or not 0 <= confidence <= 1
    ):
        problems.add("schema")
        confidence = None

    assessment = body.get("assessment")
    if not isinstance(assessment, dict) or set(assessment) - {"summary", "premises"}:
        problems.add("schema")
        assessment = {}
    _text(assessment.get("summary"), 280, problems)
    premises = _refs(assessment.get("premises", []), 8, problems)
    if not premises:
        problems.add("uncited")
    known(premises)

    uncertainties = body.get("uncertainties", [])
    if not isinstance(uncertainties, list) or len(uncertainties) > 4:
        problems.add("schema")
        uncertainties = []
    for item in uncertainties:
        if not isinstance(item, dict) or set(item) - {"about", "premises"}:
            problems.add("schema")
            continue
        _text(item.get("about"), 280, problems)
        known(_refs(item.get("premises", []), 8, problems))

    strategies = body.get("strategies")
    if not isinstance(strategies, list) or not 1 <= len(strategies) <= 3:
        problems.add("schema")
        strategies = []
    ids: list[str] = []
    for strategy in strategies:
        if not isinstance(strategy, dict) or set(strategy) - STRATEGY_KEYS:
            problems.add("schema")
            continue
        if strategy.get("id") not in STRATEGY_IDS or strategy.get("id") in ids:
            problems.add("schema")
        ids.append(str(strategy.get("id")))
        if strategy.get("goal_type") not in goal_types:
            problems.add("unknown_vocabulary")
        if (
            strategy.get("project_kind") is not None
            and strategy["project_kind"] not in project_kinds
        ):
            problems.add("unknown_vocabulary")
        cited = _refs(strategy.get("premises", []), 8, problems)
        if not cited:
            problems.add("uncited")
        known(cited)
        capability_refs = _refs(strategy.get("capability_refs", []), 4, problems)
        if any(refs.get(ref, ("", {}))[0] != "capabilities" for ref in capability_refs):
            problems.add("unoffered_capability")
        for key in ("desired", "expected"):
            entries = strategy.get(key, [])
            if not isinstance(entries, list) or len(entries) > 4:
                problems.add("schema")
                continue
            for entry in entries:
                allowed = {"fact", "direction"} | ({"support"} if key == "expected" else set())
                if not isinstance(entry, dict) or set(entry) - allowed:
                    problems.add("schema")
                    continue
                if entry.get("fact") not in facts or entry.get("direction") not in DIRECTIONS:
                    problems.add("unknown_vocabulary")
                if key == "expected" and not _supported(entry, refs, problems):
                    problems.add("unsupported_expectation")

    preferred = body.get("preferred")
    if preferred is not None and preferred not in ids:
        problems.add("unknown_preferred")

    evidence = body.get("evidence_needed", [])
    if not isinstance(evidence, list) or len(evidence) > 3:
        problems.add("schema")
        evidence = []
    for item in evidence:
        if not isinstance(item, dict) or set(item) - {"kind", "about"}:
            problems.add("schema")
            continue
        if item.get("kind") not in EVIDENCE_KINDS:
            problems.add("unknown_vocabulary")
        _text(item.get("about"), 280, problems)

    stated = float(confidence) if confidence is not None else None
    if problems:
        return Verdict(False, None, tuple(sorted(problems)), stated)
    return Verdict(True, body, (), stated)


def _supported(
    entry: Mapping[str, Any],
    refs: Mapping[str, tuple[str, dict[str, Any]]],
    problems: set[str],
) -> bool:
    """An expected world effect needs a Person-accessible justification.

    A belief about that fact, a capability that declares that effect, or a
    directly cited current premise. A confident prediction with none of these
    is an unsupported world claim.
    """
    support = _refs(entry.get("support", []), 4, problems)
    fact = entry.get("fact")
    for ref in support:
        section, item = refs.get(ref, ("", {}))
        if section == "beliefs" and item.get("fact") == fact:
            return True
        if section == "capabilities" and fact in item.get("effects", ()):
            return True
        if section == "hypotheses" and item.get("outcome", {}).get("fact") == fact:
            return True
        if section in ("situation", "memories", "recent"):
            return True
    return False
