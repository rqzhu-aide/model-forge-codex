"""Implementation authorship follows retained production, including historical ownership."""
from model_forge_codex.research_sources import implementation_projection
from model_forge_codex.storage import write_json_atomic


def test_implementation_author_uses_its_frozen_stage_not_current_ownership(tmp_path):
    for run_id, stage_id, role in (("run.old", "p4.lead", "research_lead"),
                                  ("run.new", "p4.analyst", "data_analyst")):
        write_json_atomic(tmp_path / "runs" / run_id / "stage-plan.json",
                          [{"stage_id": stage_id, "roles": [role]}])
        ref = {"run_id": run_id, "stage_id": stage_id}
        projected = implementation_projection(tmp_path, {"implementation_summary": {"rule": "Saved calculation."}},
                                               {"generation_ref": ref})
        assert projected["producer_role"] == role
    unknown = implementation_projection(tmp_path, {}, {"generation_ref": {"run_id": "run.old"}})
    assert unknown["producer_role"] is None
