"""A citation-only legacy basis must not hide new P1 discovery from the lead."""
from copy import deepcopy

from model_forge_codex.domain import MemberRole
from model_forge_codex.literature import build_library
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from test_direct_workflow import p1_documents
from test_draft_validation import draft_engine, run, write_outputs


def test_legacy_citation_library_does_not_hide_completed_current_discovery(draft_engine):
    engine = draft_engine
    record, stages, _ = run(engine, "P1", "p1.literature_update")
    discovery, reconciliation = stages
    directory = engine.run_dir(record.project_id, record.run_id)

    # Older publications can retain their exact collection separately from a
    # cumulative library that contains citations but no mathematical assessments.
    legacy = p1_documents(("citation.legacy",))["p1.lead_literature"]
    legacy["schema_version"] = "1.0.0"
    legacy_path = directory / "inputs/frozen-prior/lead_literature.json"
    write_json_atomic(legacy_path, legacy)
    previous = build_library(None, [legacy["papers"][0]["source"]], run_id="run.legacy")
    assert all(not source.get("assessments") for source in previous["sources"])
    basis = read_json(directory / "basis.json")
    basis["records"] = [{
        "phase": "P1", "branch": "trunk", "family": "lead_literature",
        "run_id": "run.legacy", "generation_id": "generation.legacy",
        "snapshot_path": str(legacy_path), "content_sha256": sha256_file(legacy_path),
    }]
    basis["cumulative_inputs"]["literature_library"] = {
        "document": previous, "sha256": engine._cumulative_digest(previous),
    }
    write_json_atomic(directory / "basis.json", basis)
    frozen_basis = deepcopy(basis)
    legacy_bytes = legacy_path.read_bytes()

    documents = p1_documents(("citation.current",))
    current = documents["p1.lead_literature"]["papers"][0]
    current["formulation_markdown"] = (
        r"$$C_\gamma(\pi)=\mathbb E_\pi\!\left[\sum_{t=0}^{\infty}"
        r"\gamma^t B_t\right],\qquad 0<\gamma<1.$$"
    )
    write_outputs(directory / "outputs" / discovery.stage_id,
                  {family: documents[family] for family in discovery.writes})
    assert not engine._validate_run_outputs(record, [discovery], [])
    record.stage_states[discovery.stage_id] = "succeeded"
    engine._save_run(record)

    workspace = engine.member_workspace(record, reconciliation.stage_id, MemberRole.RESEARCH_LEAD)
    workspace.mkdir(parents=True, exist_ok=True)
    brief = engine._render_brief(record, reconciliation, MemberRole.RESEARCH_LEAD, workspace)
    # This historical shape cannot supply the complete entry index. Its fallback
    # must expose both frozen prior material and every accepted current collection
    # through instructed file reads, rather than suppressing the current inputs.
    for family in discovery.writes:
        path = directory / "outputs" / discovery.stage_id / engine._output_filename(family)
        assert str(path) in brief
        assert read_json(path) == documents[family]
    current_path = directory / "outputs" / discovery.stage_id / "lead_literature.json"
    assert read_json(current_path)["papers"][0] == current
    assert str(legacy_path) in brief
    assert read_json(legacy_path) == legacy
    assert current["formulation_markdown"] not in brief
    assert legacy["papers"][0]["formulation_markdown"] not in brief
    assert read_json(directory / "basis.json") == frozen_basis
    assert legacy_path.read_bytes() == legacy_bytes
    assert engine.bridge.turns == []
