"""Later specialist briefs receive scientific provenance without raw P2 directions."""
import json
from copy import deepcopy

import pytest

from model_forge_codex.domain import MemberRole
from model_forge_codex.methods import get_method
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import publish, record, workbench


@pytest.mark.parametrize("phase,mode", [("P3", "p3.theory_establishment"), ("P4", "p4.preliminary"), ("P5", "p5.review_revision")])
def test_actual_later_phase_briefs_keep_p2_directions_lead_only(workbench, phase, mode):
    engine, project, branch = workbench
    method = get_method(project, branch)["definition"]
    identity = method["identity"]
    proposal = {"proposal_id": "proposal.original", "method": method,
                "researcher_origin": {"specification_markdown": "RAW_P2_ORIGIN_LEAD_ONLY"},
                "motivation": "SCIENTIFIC_MOTIVATION_SHARED"}
    p2 = publish(project, "trunk", "P2", {
        "lead_proposal": proposal,
        "method_catalog": {"methods": [method], "method_sources": {identity["stable_id"]: {
            "run_id": "run.p2_origin", "family": "lead_proposal", "proposal_id": "proposal.original", "identity": identity}}}},
        "run.p2_origin")
    publish(project, "trunk", "P1", {
        "literature_synthesis": {"landscape": "SCIENTIFIC_LANDSCAPE_SHARED", "phase2_preparation": {"instructions_markdown": "RAW_PREPARATION_LEAD_ONLY"}},
        "phase2_handoff": {"directions": "RAW_OLD_HANDOFF_LEAD_ONLY"}}, "run.p1_origin")
    candidate = record(engine, branch, "run.later." + phase, phase, mode)
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    basis = engine.compute_basis(candidate.project_id, phase, branch, mode)
    write_json_atomic(directory / "basis.json", basis)
    original_basis = deepcopy(basis)
    if phase == "P5":
        from model_forge_codex.p5_review_packet import prepare_review_packet
        from test_p5_review_packet import packet_basis
        prepare_review_packet(directory, basis=packet_basis(directory / "packet-fixture"),
                              instructions="Review the supplied fixture.", run_id=candidate.run_id)
    stages = engine.stage_plan(candidate.project_id, phase, mode)
    for role in (MemberRole.THEORIST, MemberRole.DATA_ANALYST, MemberRole.RESEARCH_LEAD):
        stage = next(stage for stage in stages if role in stage.roles)
        brief = engine._render_brief(candidate, stage, role, engine.member_workspace(candidate, stage.stage_id, role))
        if role == MemberRole.RESEARCH_LEAD:
            assert "phase2_handoff" in brief
            path = directory / "inputs/method-sources" / (identity["stable_id"] + ".json")
            assert "RAW_P2_ORIGIN_LEAD_ONLY" in path.read_text(encoding="utf-8")
        else:
            assert "phase2_handoff" not in brief
            assert "RAW_P2_ORIGIN_LEAD_ONLY" not in brief
            scientific = list((directory / "inputs/specialist-views" / role.value).rglob("*.json"))
            assert len(scientific) == 2
            joined = "\n".join(path.read_text(encoding="utf-8") for path in scientific)
            assert "SCIENTIFIC_MOTIVATION_SHARED" in joined and "SCIENTIFIC_LANDSCAPE_SHARED" in joined
            assert "RAW_PREPARATION_LEAD_ONLY" not in joined and "RAW_P2_ORIGIN_LEAD_ONLY" not in joined
            source = read_json(directory / "inputs/method-sources/specialist-views" / role.value / (identity["stable_id"] + ".json"))
            assert source["materials"]["proposal"]["document"]["method"] == method
            assert "researcher_origin" not in source["materials"]["proposal"]["document"]
            assert source["materials"]["proposal"]["ref"]["generation_id"] == p2["records"]["lead_proposal"]["generation_id"]
    assert read_json(directory / "basis.json") == original_basis
    assert "RAW_P2_ORIGIN_LEAD_ONLY" in json.dumps(original_basis)
