"""Small authoring references read from the producing run's frozen catalog."""
from __future__ import annotations

import json

from .catalog import Catalog, CatalogError
from .domain import MemberRole


CAPABILITY = "research_presentation_v1"
PRESENTATION_V2 = "research_presentation_v2"
NOTATION_CAPABILITY = "project_notation_v1"
SCIENTIFIC = ("scientific-explanation", "claims-and-evidence", "summary", "tables-and-figures")
INQUIRY = "user-inquiry"
EXPLANATION = ("scientific-explanation", "claims-and-evidence")


def presentation_reference_names(catalog: Catalog, phase: str, role: MemberRole, *,
                                 assessment_purpose: str | None = None,
                                 target_kind: str | None = None,
                                 stage_id: str | None = None) -> tuple[str, ...]:
    path = catalog.root / "contracts" / "phases" / f"{phase}.json"
    contract = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    capabilities = contract.get("capabilities", [])
    if PRESENTATION_V2 in capabilities:
        if target_kind == "report_section":
            return EXPLANATION
        if role == MemberRole.OUTSIDE_REVIEWER:
            return SCIENTIFIC if phase == "P5" else EXPLANATION
        if assessment_purpose is not None:
            return (*EXPLANATION, INQUIRY) if assessment_purpose in {
                "issue_explanation", "issue_suggestions", "model_dialogue", "project_context",
            } else EXPLANATION
        # The immutable P5 packet supplies the four neutral references once
        # to every reviewer and the revision Lead. Only the Lead retains its
        # existing narrowly editorial inquiry reference outside that packet.
        if phase == "P5" and stage_id == "p5.parallel_reviews":
            return ()
        if phase == "P5" and stage_id == "p5.revision_lead":
            return (INQUIRY,)
        names = list(EXPLANATION)
        # Summary belongs to synthesis, not the Lead's independent discovery
        # or proposal. A caller without a stage still receives neutral guidance.
        if role == MemberRole.RESEARCH_LEAD and stage_id not in {
            "p1.discovery", "p2.independent_proposals", "p2.supplied_method_proposals",
        }:
            names.append("summary")
        if phase in {"P2", "P3", "P4", "P5"}:
            names.append("tables-and-figures")
        if phase != "P5" or role == MemberRole.RESEARCH_LEAD:
            names.append(INQUIRY)
        return tuple(names)
    if CAPABILITY not in capabilities:
        return ()
    # The outside reviewer keeps its independent report packet and review duties.
    if role == MemberRole.OUTSIDE_REVIEWER or target_kind == "report_section":
        return ()
    if assessment_purpose is not None:
        return ((INQUIRY,) if assessment_purpose in {
            "issue_explanation", "issue_suggestions", "model_dialogue", "project_context",
        } else ())
    if phase == "P4":
        scientific = SCIENTIFIC if role == MemberRole.RESEARCH_LEAD else (
            "scientific-explanation", "claims-and-evidence", "tables-and-figures",
        )
        return (*scientific, INQUIRY)
    return (INQUIRY,)


def presentation_reference_brief(catalog: Catalog, phase: str, role: MemberRole, **context) -> str:
    names = presentation_reference_names(catalog, phase, role, **context)
    if not names:
        return ""
    sections = []
    for name in names:
        path = catalog.root / "references" / "research-presentation" / f"{name}.md"
        if not path.is_file():
            raise CatalogError(f"The frozen catalog is missing its presentation reference: {name}")
        sections.append(path.read_text(encoding="utf-8").strip())
    return ("## Researcher-facing presentation references\n\n"
            "Use these references for the outputs you already own. They do not change scientific "
            "scope, source authority, pause permissions or the selected method.\n\n"
            + "\n\n".join(sections) + "\n\n")
