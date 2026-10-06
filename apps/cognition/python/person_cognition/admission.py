"""Which canonical events are epistemic evidence, and for what (ADR 0027).

The journal is Person's history. Almost all of it is history and nothing
else: an affect appraisal, a deliberation, a recall, a session starting.
Exactly three kinds of record may move a belief, each by the reducer that
owns that belief, and each only as the provenance class named here:

    belief_revised        a fact belief, from the runtime's reports or from
                          what Person sensed (ADR 0026); its own payload
                          names its basis, and the store refuses any basis
                          that is not world evidence
    effect_evidence       the reliability of a skill's declared effect, from
                          the outcome of Person's own action (ADR 0011)
    hypothesis_evidence   a causal hypothesis, from an intervention or an
                          observation Person made (ADR 0012)

Every other event type is history only. An architecture test feeds every
other type to every belief-holding reducer and checks that nothing moves.
Recalling a memory, replaying a journal, imagining an outcome or a model's
prediction are canonical events at most; none is on this list, so none can
become evidence by being recorded.
"""

from __future__ import annotations

from collections.abc import Mapping

from person_epistemics import EventAdmission, Source, admissions

EVIDENCE_ADMISSIONS: Mapping[str, EventAdmission] = admissions(
    {
        "belief_revised": EventAdmission(
            "belief_revised", Source.RUNTIME_REPORT, "fact belief (basis stated per record)"
        ),
        "effect_evidence": EventAdmission(
            "effect_evidence", Source.INTERVENTION_OUTCOME, "effect reliability"
        ),
        "hypothesis_evidence": EventAdmission(
            "hypothesis_evidence", Source.INTERVENTION_OUTCOME, "causal hypothesis"
        ),
    }
)
