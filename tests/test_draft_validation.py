"""The member checker uses publication rules without reading live peer work."""
import copy
import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import pytest

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole, RunRecord, RunState
from model_forge_codex.literature import build_library
from model_forge_codex.runs import RunEngine, owned_writes
from model_forge_codex.storage import read_json, write_json_atomic
from test_direct_workflow import p1_documents, p2_documents, SEED
from test_researcher_workbench_engine import scientific_output_documents
from test_p5_review_packet import packet_basis, prepare_engine_review_packet
from conftest import use_legacy_p5_catalog


REPO = Path(__file__).resolve().parents[1]
PID = "project.draft"


@pytest.fixture
def draft_engine(tmp_path):
    project = tmp_path / "data/projects" / PID
    project.mkdir(parents=True)
    shutil.copytree(REPO / "contracts", project / "contracts")
    write_json_atomic(project / "project.json", {"project_id": PID, "research_instructions": "Recorded setting"})
    return RunEngine(tmp_path / "data", FakeCodexBridge())


def run(engine, phase, mode):
    record = RunRecord("run.draft." + phase, PID, phase, mode, "trunk", state=RunState.RUNNING)
    stages = engine.stage_plan(PID, phase, mode)
    record.stage_states = {stage.stage_id: "pending" for stage in stages}
    engine._save_run(record)
    directory = engine.run_dir(PID, record.run_id)
    write_json_atomic(directory / "stage-plan.json", [asdict(stage) for stage in stages])
    method = read_json(REPO / "contracts/examples/method.example.json")
    cumulative = {"literature_library": build_library(None, [], run_id="run.seed"), "method_catalog": {"methods": []},
                  "review_issue_ledger": {"issues": []}}
    write_json_atomic(directory / "basis.json", {
        "method": method, "records": [],
        "cumulative_inputs": {family: {"document": document, "sha256": engine._cumulative_digest(document)}
                              for family, document in cumulative.items()},
    })
    return record, engine._stages(record), method["identity"]


def write_outputs(root, documents, files=None):
    root.mkdir(parents=True, exist_ok=True)
    for family, document in documents.items():
        content = ("\n".join(json.dumps(row) for row in document)
                   if family.endswith(".metrics_long") else json.dumps(document))
        (root / RunEngine._output_filename(family)).write_bytes(content.encode("utf-8"))
    for name, content in (files or {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))


def check(engine, record, stage, role):
    return engine.validate_member_artifacts(record, stage, role,
        engine.member_workspace(record, stage.stage_id, role))


def codes(result):
    return {finding["code"] for finding in result["findings"]}


def snapshot(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def test_p1_draft_is_read_only_and_excludes_peers_and_future_outputs(draft_engine):
    engine = draft_engine
    record, stages, _ = run(engine, "P1", "p1.literature_update")
    stage, later = stages
    role = MemberRole.RESEARCH_LEAD
    workspace = engine.member_workspace(record, stage.stage_id, role)
    docs = p1_documents()
    write_outputs(workspace, {"p1.lead_literature": docs["p1.lead_literature"],
                              "p1.theory_literature": {"private_peer_draft": "must not be read"}})
    sealed = engine.run_dir(PID, record.run_id) / "outputs"
    write_outputs(sealed / stage.stage_id, {"p1.empirical_literature": None})
    write_outputs(sealed / later.stage_id, {"p1.research_basis": None})
    before, state = snapshot(engine.data_root), copy.deepcopy(asdict(record))
    result = check(engine, record, stage, role)
    assert result["status"] == "passed", result["findings"]
    assert result["checked_outputs"] == ["p1.lead_literature"]
    assert result["scientific_correctness"] == "not_assessed"
    assert any("p1.theory_literature" in item and "p1.research_basis" in item for item in result["deferred_checks"])
    assert snapshot(engine.data_root) == before
    assert asdict(record) == state
    assert engine.bridge.turns == []


def test_p1_duplicate_entries_checked_before_lead_basis(draft_engine):
    record, stages, _ = run(draft_engine, "P1", "p1.literature_update")
    doc = p1_documents()["p1.lead_literature"]
    doc["papers"].append(copy.deepcopy(doc["papers"][0]))
    write_outputs(draft_engine.member_workspace(record, stages[0].stage_id, MemberRole.RESEARCH_LEAD),
                  {"p1.lead_literature": doc})
    assert "literature.duplicate_entry" in codes(check(draft_engine, record, stages[0], MemberRole.RESEARCH_LEAD))


def test_stage_gate_retains_cross_member_reconciliation_without_future_basis(draft_engine):
    record, stages, _ = run(draft_engine, "P1", "p1.literature_update")
    docs = p1_documents()
    other = copy.deepcopy(docs["p1.lead_literature"])
    other["papers"][0]["source"]["title"] = "Different work using the same identifier"
    docs["p1.theory_literature"] = other
    write_outputs(draft_engine.run_dir(PID, record.run_id) / "outputs" / stages[0].stage_id,
                  {family: docs[family] for family in stages[0].writes})
    findings = draft_engine._validate_run_outputs(record, [stages[0]], [])
    pending = [finding for finding in findings if finding.code == "literature.metadata_reconciliation_pending"]
    assert {finding.object_id for finding in pending} == {
        "p1.lead_literature", "p1.theory_literature"}
    assert all(not finding.blocks_publication and finding.details.get("entries") for finding in pending)
    assert all(finding.object_id != "p1.research_basis" for finding in findings)


def test_p2_proposal_checks_own_source_without_demanding_lead_or_peer(draft_engine):
    record, stages, _ = run(draft_engine, "P2", "p2.researcher_proposal")
    record.supplied_method = copy.deepcopy(SEED)
    docs, files = p2_documents(True)
    role = MemberRole.THEORIST
    workspace = draft_engine.member_workspace(record, stages[0].stage_id, role)
    write_outputs(workspace, {"p2.theory_proposal": docs["p2.theory_proposal"]}, files)
    result = check(draft_engine, record, stages[0], role)
    assert result["status"] == "passed", result["findings"]
    (workspace / "method-theory.md").write_text("Changed definition", encoding="utf-8")
    result = check(draft_engine, record, stages[0], role)
    assert "artifact.digest_mismatch" in codes(result)
    assert not {"proposal.missing_lead", "proposal.missing_lead_response", "output.required_missing"} & codes(result)


@pytest.mark.parametrize("original_plan", [False, True])
def test_p2_review_reads_only_declared_completed_proposals(draft_engine, original_plan):
    record, stages, _ = run(draft_engine, "P2", "p2.full_catalog")
    if original_plan:
        # New runs retain the contract's in-memory stages through their live
        # callbacks; a reloaded run must enforce exactly the same input scope.
        stages = draft_engine.stage_plan(PID, record.phase, record.mode)
    proposal, review, later = stages
    record.stage_states[proposal.stage_id] = "succeeded"
    docs, files = p2_documents(False)
    sealed = draft_engine.run_dir(PID, record.run_id) / "outputs"
    write_outputs(sealed / proposal.stage_id, {
        "p2.empirical_proposal": docs["p2.empirical_proposal"],
        "p2.theory_proposal": {"hidden_own_proposal": "not a reviewer input"},
        "p2.lead_proposal": docs["p2.lead_proposal"],
    }, files)
    write_outputs(sealed / review.stage_id, {"p2.empirical_review": None})
    write_outputs(sealed / later.stage_id, {"p2.catalog_assessment": None})
    workspace = draft_engine.member_workspace(record, review.stage_id, MemberRole.THEORIST)
    write_outputs(workspace, {"p2.theory_review": docs["p2.theory_review"]})
    result = check(draft_engine, record, review, MemberRole.THEORIST)
    assert result["status"] == "passed", result["findings"]
    docs["p2.theory_review"]["assessments"][0]["proposal_id"] = "proposal.theory"
    write_outputs(workspace, {"p2.theory_review": docs["p2.theory_review"]})
    assert "review.target_coverage" in codes(check(draft_engine, record, review, MemberRole.THEORIST))


@pytest.mark.parametrize(("phase", "mode", "role"), [
    ("P3", "p3.theory_establishment", MemberRole.THEORIST),
    ("P4", "p4.preliminary", MemberRole.DATA_ANALYST),
    ("P5", "p5.review_revision", MemberRole.OUTSIDE_REVIEWER),
])
def test_later_phase_current_schema_drafts_need_no_future_outputs(draft_engine, phase, mode, role):
    if phase == "P5":
        use_legacy_p5_catalog(draft_engine.project_dir(PID) / "contracts")
    record, stages, identity = run(draft_engine, phase, mode)
    stage = stages[0]
    docs, files = scientific_output_documents(Catalog(draft_engine.project_dir(PID) / "contracts"), phase, identity)
    if phase == "P5":
        prepare_p5_draft_review(draft_engine, record, docs["p5.outside_review"])
    write_outputs(draft_engine.member_workspace(record, stage.stage_id, role),
                  {family: docs[family] for family in owned_writes(stage, role)}, files)
    result = check(draft_engine, record, stage, role)
    assert result["status"] == "passed", result["findings"]


def test_p3_graph_check_runs_before_audits(draft_engine):
    record, stages, identity = run(draft_engine, "P3", "p3.theory_establishment")
    docs, files = scientific_output_documents(Catalog(REPO / "contracts"), "P3", identity)
    docs["p3.claim_map"]["claims"][0]["depends_on"] = ["statement.missing"]
    write_outputs(draft_engine.member_workspace(record, stages[0].stage_id, MemberRole.THEORIST),
                  {family: docs[family] for family in stages[0].writes}, files)
    assert "theory.graph_dependency_mismatch" in codes(check(draft_engine, record, stages[0], MemberRole.THEORIST))


def test_p4_draft_recomputes_diagnostics_and_uses_workspace_paths(draft_engine):
    record, stages, identity = run(draft_engine, "P4", "p4.preliminary")
    docs, files = scientific_output_documents(Catalog(REPO / "contracts"), "P4", identity)
    docs["p4.diagnostics"]["headline_numbers"][0]["estimate"] = 99
    workspace = draft_engine.member_workspace(record, stages[0].stage_id, MemberRole.DATA_ANALYST)
    write_outputs(workspace, {family: docs[family] for family in stages[0].writes}, files)
    result = check(draft_engine, record, stages[0], MemberRole.DATA_ANALYST)
    assert "diagnostics.aggregate_mismatch" in codes(result)
    assert not {"diagnostics.script_missing", "diagnostics.provenance_mismatch", "exhibit.artifact_missing"} & codes(result)
    (workspace / "metrics_long.jsonl").write_text('{"case_id":\n', encoding="utf-8")
    result = check(draft_engine, record, stages[0], MemberRole.DATA_ANALYST)
    assert "output.jsonl_malformed" in codes(result)
    assert "scientific.invalid_structure" not in codes(result)


@pytest.mark.parametrize(("phase", "mode", "role", "family"), [
    ("P1", "p1.literature_update", MemberRole.RESEARCH_LEAD, "p1.lead_literature"),
    ("P2", "p2.full_catalog", MemberRole.THEORIST, "p2.theory_proposal"),
    ("P3", "p3.theory_establishment", MemberRole.THEORIST, "p3.theory_candidate"),
    ("P4", "p4.preliminary", MemberRole.DATA_ANALYST, "p4.protocol"),
    ("P5", "p5.assembly", MemberRole.RESEARCH_LEAD, "p5.manuscript_candidate"),
])
def test_schema_invalid_drafts_are_reported_without_semantic_crashes(draft_engine, phase, mode, role, family):
    if phase == "P5":
        use_legacy_p5_catalog(draft_engine.project_dir(PID) / "contracts")
    record, stages, _ = run(draft_engine, phase, mode)
    workspace = draft_engine.member_workspace(record, stages[0].stage_id, role)
    write_outputs(workspace, {family: ["not the declared object"]})
    result = check(draft_engine, record, stages[0], role)
    assert result["status"] == "failed"
    assert "schema.type" in codes(result)
    assert "scientific.invalid_structure" not in codes(result)
    assert any("malformed" in item for item in result["deferred_checks"])


def test_draft_checker_rejects_arbitrary_workspace_without_reading_it(draft_engine, tmp_path):
    record, stages, _ = run(draft_engine, "P1", "p1.literature_update")
    result = draft_engine.validate_member_artifacts(record, stages[0], MemberRole.RESEARCH_LEAD, tmp_path)
    assert result["status"] == "unavailable"
    assert codes(result) == {"draft.validation_unavailable"}


def prepare_p5_draft_review(engine, record, report):
    """Draft-check fixtures begin with the same frozen submission as dispatch."""
    directory = engine.run_dir(record.project_id, record.run_id)
    basis = read_json(directory / "basis.json")
    basis.update(packet_basis(directory))
    packet = prepare_engine_review_packet(engine, record, basis)
    target = packet["records"][0]["generation_id"]
    report["review_basis_generation_id"] = target
    for issue in report["prioritized_issues"]:
        issue["review_basis_generation_id"] = target
    return basis


def test_outside_reviewer_check_never_resolves_internal_sources(draft_engine, monkeypatch):
    record, stages, identity = run(draft_engine, "P5", "p5.review_revision")
    directory = draft_engine.run_dir(PID, record.run_id)
    docs, files = scientific_output_documents(Catalog(REPO / "contracts"), "P5", identity)
    basis = prepare_p5_draft_review(draft_engine, record, docs["p5.outside_review"])
    basis["records"] = [{"phase": "P3", "family": "private_theory", "snapshot_path": str(directory / "secret.json"),
                         "content_sha256": "0" * 64}]
    write_json_atomic(directory / "basis.json", basis)
    workspace = draft_engine.member_workspace(record, stages[0].stage_id, MemberRole.OUTSIDE_REVIEWER)
    write_outputs(workspace, {"p5.outside_review": docs["p5.outside_review"]}, files)
    def forbidden(*args, **kwargs):
        raise AssertionError("Independent review must not read private cumulative records")
    monkeypatch.setattr(draft_engine, "_cumulative_input", forbidden)
    result = check(draft_engine, record, stages[0], MemberRole.OUTSIDE_REVIEWER)
    assert result["status"] == "passed", result["findings"]
    assert not result["findings"]
    assert any("internal project records" in item for item in result["deferred_checks"])
    (directory / "basis.json").unlink()
    result = check(draft_engine, record, stages[0], MemberRole.OUTSIDE_REVIEWER)
    assert result["status"] == "passed", result["findings"]
    assert not result["findings"]
