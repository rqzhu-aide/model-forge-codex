"""No-model checks for reviewer independence and exact manuscript sources."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole, RunState, StageResult, StageSpec
from model_forge_codex.p5_review_packet import prepare_review_packet, read_review_packet
from model_forge_codex.storage import read_json, write_json_atomic
from model_forge_codex.validation import validate_scientific_outputs
from test_researcher_workbench_engine import REPO, publish, record, seed_theory, workbench
from test_p5_review_packet import FOCUS, packet_basis


def test_p4_audit_mentions_lead_summary_but_keeps_canonical_theory(workbench):
    eng, project, branch = workbench
    seed_theory(project, branch)
    from model_forge_codex.methods import get_method
    from model_forge_codex.records import current_records, read_generation
    directory = project / "branches" / branch / "phases" / "p3"
    theory = read_generation(directory, "theory_record", current_records(directory)["theory_record"])
    publish(project, branch, "P3", {"theory_record": theory, "phase_summary": {
        "headline": "Lead theory assessment", "evaluation_markdown": "INLINE_LEAD_VERDICT_MARKER",
        "method_identity": get_method(project, branch)["identity"]}})
    run = record(eng, branch, "run.brief", "P4", "p4.preliminary")
    stages = eng.stage_plan("project.test", "P4", run.mode)
    analyst = eng._render_brief(run, stages[0], MemberRole.DATA_ANALYST, eng.run_dir("project.test", run.run_id))
    reviewer = eng._render_brief(run, stages[1], MemberRole.THEORIST, eng.run_dir("project.test", run.run_id))
    assert "INLINE_LEAD_VERDICT_MARKER" in analyst
    assert "INLINE_LEAD_VERDICT_MARKER" not in reviewer
    assert "phase_summary" in reviewer
    assert "theory_record" in reviewer and "Open and read the applicable scientific content" in reviewer


def test_same_specialist_gets_summary_for_proposal_but_not_cross_review(workbench):
    eng, _, _ = workbench
    run = record(eng, "trunk", "run.proposal", "P2", "p2.full_catalog")
    stages = eng.stage_plan("project.test", "P2", run.mode)
    assert eng._t2s_delivery("P1", run, MemberRole.THEORIST, stages[0]) == "inline"
    assert eng._t2s_delivery("P1", run, MemberRole.THEORIST, stages[1]) == "mention"
    assert eng._t2s_delivery("P1", run, MemberRole.RESEARCH_LEAD, stages[2]) == "inline"
    assert eng._t2s_delivery("P1", run, MemberRole.OUTSIDE_REVIEWER, stages[1]) == "never"


def test_t1_never_delivered_even_with_incorrect_inline_metadata(workbench, monkeypatch):
    eng, project, branch = workbench
    publish(project, "trunk", "P1", {"display_card": {"headline": "CARD_MUST_NOT_ENTER_BRIEF"}})
    catalog = Catalog(project / "contracts")
    monkeypatch.setattr(catalog, "artifact_contracts", lambda: {"p1.display_card": {
        "artifact_type": "t1_card", "delivery": "inline", "audience": ["data_analyst"]}})
    run = record(eng, branch, "run.cards", "P4", "p4.preliminary")
    sections = eng._classify_upstream(run, MemberRole.DATA_ANALYST, catalog)
    assert "display_card" not in str(sections)
    assert "CARD_MUST_NOT_ENTER_BRIEF" not in str(sections)


def test_same_run_required_science_is_available_without_reviewer_summary(workbench, monkeypatch):
    eng, _, branch = workbench
    run = record(eng, branch, "run.same", "P4", "p4.preliminary")
    previous = StageSpec("p4.author", 1, "serial", (MemberRole.RESEARCH_LEAD,),
        ("p4.phase_summary", "p4.protocol"), artifact_contracts={
            "p4.phase_summary": {"artifact_type": "t2s", "delivery": "inline", "audience": ["theorist"]},
            "p4.protocol": {"artifact_type": "t2m", "delivery": "mention", "audience": []}})
    reviewer = StageSpec("p4.theorist", 2, "serial", (MemberRole.THEORIST,), ("p4.theory_audit",), reads=("p4.protocol",))
    monkeypatch.setattr(eng, "_stages", lambda _: [previous, reviewer])
    folder = eng.run_dir("project.test", run.run_id) / "outputs" / previous.stage_id
    write_json_atomic(folder / "phase_summary.json", {"evaluation_markdown": "INTERNAL_VERDICT"})
    write_json_atomic(folder / "protocol.json", {"test": "canonical scientific protocol"})
    sections = eng._same_run_sections(run, reviewer, MemberRole.THEORIST)
    assert not sections["packets"]
    assert "INTERNAL_VERDICT" not in str(sections)
    assert "phase_summary" in str(sections["mentions"])
    assert "p4.protocol" in str(sections["instructed"])


@pytest.fixture
def manuscript_sources(tmp_path, legacy_p5_catalog):
    basis = {"records": [], "artifacts": [], "catalog_root": str(legacy_p5_catalog.root)}
    bindings, statements, index = [], [], {}
    for number, group in enumerate(("p1_literature_claim_ids", "p2_method_claim_ids", "p3_theory_claim_ids", "p4_empirical_claim_ids"), 1):
        phase = f"P{number}"
        source = tmp_path / f"source-{phase}.md"
        source.write_text(f"Recorded support from {phase}", encoding="utf-8")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        artifact = {"artifact_id": f"artifact.{phase}", "sha256": digest, "uri": f"artifact://artifact.{phase}"}
        document = {"record_id": f"record.{phase}", "record_type": "theory_record", "phase": phase,
                    "statements": [{"statement_id": f"support.{phase}", "text": "Actual authored support"}],
                    "primary_artifact": artifact}
        path = tmp_path / f"input-{phase}.json"
        write_json_atomic(path, document)
        ref = {"phase": phase, "branch": "trunk" if number < 3 else "method.a", "family": "science",
               "generation_id": f"generation.{phase}", "snapshot_path": str(path),
               "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        basis["records"].append(ref)
        basis["artifacts"].append({"phase": phase, "family": "science", "generation_id": ref["generation_id"],
            "artifact_id": artifact["artifact_id"], "content_sha256": digest, "path": str(source)})
        bindings.append({"record_id": document["record_id"], "record_type": document["record_type"],
            "generation_id": ref["generation_id"], "content_sha256": ref["content_sha256"],
            "publication_state_at_use": "formal", "record_position_at_use": "current", "dependency_class": "hard"})
        statement = {"statement_id": f"claim.{phase}", "record_id": "record.paper", "record_generation_id": "candidate.paper",
            "supporting_evidence_ids": [f"support.{phase}"], "counterevidence_ids": [],
            "source_locations": [artifact], "scientific_outcome": {"state": "supported"}}
        statements.append(statement)
        index[group] = [statement["statement_id"]]
    index["interpretation_claim_ids"] = []
    outputs = {"p5.manuscript_candidate": {"record_id": "record.paper", "claim_support_index": index, "basis": copy.deepcopy(bindings)},
               "p5.claim_traceability": statements, "p5.upstream_basis_manifest": {"basis": bindings}}
    return outputs, basis


def check(outputs, basis):
    return validate_scientific_outputs(Catalog(Path(basis["catalog_root"])), "P5", outputs, frozen_basis=basis)


def test_exact_manuscript_references_resolve_without_mutation(manuscript_sources):
    outputs, basis = manuscript_sources
    before = copy.deepcopy((outputs, basis))
    assert check(outputs, basis) == []
    assert (outputs, basis) == before


@pytest.mark.parametrize("mutation,code", [
    (lambda o, b: o["p5.manuscript_candidate"]["claim_support_index"]["p3_theory_claim_ids"].append("claim.missing"), "manuscript.claim_unmapped"),
    (lambda o, b: o["p5.claim_traceability"].append(copy.deepcopy(o["p5.claim_traceability"][0])), "reference.duplicate_or_missing_id"),
    (lambda o, b: o["p5.claim_traceability"][0]["supporting_evidence_ids"].append("evidence.invented"), "manuscript.evidence_unresolved"),
    (lambda o, b: o["p5.claim_traceability"][0]["counterevidence_ids"].append("evidence.invented"), "manuscript.evidence_unresolved"),
    (lambda o, b: o["p5.claim_traceability"][0]["scientific_outcome"].update(strongest_evidence_ids=["evidence.invented"]), "manuscript.evidence_unresolved"),
    (lambda o, b: o["p5.claim_traceability"][0].update(assumptions=["assumption.invented"]), "manuscript.evidence_unresolved"),
    (lambda o, b: o["p5.claim_traceability"][0]["source_locations"][0].update(sha256="0" * 64), "manuscript.source_unresolved"),
    (lambda o, b: o["p5.upstream_basis_manifest"]["basis"][0].update(generation_id="generation.stale"), "manuscript.basis_unresolved"),
    (lambda o, b: o["p5.upstream_basis_manifest"]["basis"][0].update(content_sha256="0" * 64), "manuscript.basis_mismatch"),
    (lambda o, b: o["p5.upstream_basis_manifest"]["basis"][0].update(record_position_at_use="historical"), "manuscript.basis_mismatch"),
    (lambda o, b: o["p5.upstream_basis_manifest"]["basis"][0].update(method_identity={"stable_id": "method.other"}), "manuscript.basis_mismatch"),
    (lambda o, b: o["p5.upstream_basis_manifest"].update(basis=[]), "manuscript.basis_not_manifested"),
    (lambda o, b: o["p5.claim_traceability"][0].update(record_id="record.P1", record_generation_id="generation.stale"), "manuscript.statement_generation_unresolved"),
    (lambda o, b: o["p5.manuscript_candidate"]["claim_support_index"].update(p3_theory_claim_ids=["claim.P1"]), "manuscript.claim_phase_unsupported"),
])
def test_manuscript_rejects_false_reference_bindings(manuscript_sources, mutation, code):
    outputs, basis = manuscript_sources
    mutation(outputs, basis)
    assert code in {finding.code for finding in check(outputs, basis)}


def test_manuscript_does_not_reuse_previous_paper_as_evidence(manuscript_sources):
    outputs, basis = manuscript_sources
    basis["records"][0]["phase"] = "P5"
    basis["artifacts"][0]["phase"] = "P5"
    assert "manuscript.evidence_unresolved" in {f.code for f in check(outputs, basis)}


def test_manuscript_checks_saved_bytes_not_live_current_state(manuscript_sources):
    outputs, basis = manuscript_sources
    Path(basis["records"][0]["snapshot_path"]).write_text('{"replacement": true}')
    assert "manuscript.frozen_source_changed" in {f.code for f in check(outputs, basis)}


def test_inconclusive_claim_still_requires_real_declared_sources(manuscript_sources):
    outputs, basis = manuscript_sources
    statement = outputs["p5.claim_traceability"][0]
    statement["scientific_outcome"]["state"] = "inconclusive"
    assert check(outputs, basis) == []
    statement["supporting_evidence_ids"] = ["evidence.not_checked"]
    assert "manuscript.evidence_unresolved" in {f.code for f in check(outputs, basis)}


def test_new_interpretation_may_locate_itself_in_the_manuscript(manuscript_sources):
    outputs, basis = manuscript_sources
    location = {"artifact_id": "artifact.paper", "sha256": "a" * 64}
    paper = outputs["p5.manuscript_candidate"]
    paper["manuscript_artifact"] = location
    interpretation = {"statement_id": "claim.interpretation", "record_id": "record.paper", "record_generation_id": "candidate.paper",
        "supporting_evidence_ids": [], "counterevidence_ids": [], "source_locations": [location], "scientific_outcome": {"state": "not_assessed"}}
    outputs["p5.claim_traceability"].append(interpretation)
    paper["claim_support_index"]["interpretation_claim_ids"] = ["claim.interpretation"]
    assert check(outputs, basis) == []
    paper["claim_support_index"]["p3_theory_claim_ids"].append("claim.interpretation")
    interpretation["scientific_outcome"]["state"] = "supported"
    assert "manuscript.claim_phase_unsupported" in {f.code for f in check(outputs, basis)}


async def test_p5_prepares_once_before_dispatch_and_delivers_focus_to_all_four_roles(legacy_p5_workbench, monkeypatch):
    eng, project, branch = legacy_p5_workbench
    run = record(eng, branch, "run.p5_delivery", "P5", "p5.review_revision")
    run.instructions = FOCUS
    eng._save_run(run)
    run_dir = eng.run_dir(run.project_id, run.run_id)
    basis = packet_basis(run_dir)
    basis["records"][0]["branch"] = branch
    write_json_atomic(run_dir / "basis.json", basis)
    stages = eng.stage_plan(run.project_id, "P5", run.mode)
    briefs, packet_ids = {}, []

    async def capture(record, stage, role, directory):
        # This is the engine's dispatch boundary. Preparation must already be
        # complete before the first role starts, with no paid provider turn.
        packet_ids.append(read_review_packet(directory / "review-packet")["packet_sha256"])
        briefs[role] = eng._render_brief(record, stage, role, directory)
        return StageResult(stage.stage_id, False, diagnostic="Delivery-only fixture")

    monkeypatch.setattr(eng, "_drive_member_turn", capture)
    await eng._execute_stage(run, stages[0])
    assert len(packet_ids) == 3 and len(set(packet_ids)) == 1
    assert set(briefs) == {MemberRole.THEORIST, MemberRole.DATA_ANALYST, MemberRole.OUTSIDE_REVIEWER}
    packet_dir = run_dir / "review-packet"
    before = {path.name: path.read_bytes() for path in packet_dir.iterdir()}
    # Live settings and mutable run instructions cannot change what a reviewer
    # already received or what the revision lead receives from that packet.
    write_json_atomic(project / "project.json", {"venue_length": "journal", "research_instructions": "LATER_PROJECT_SETTINGS"})
    run.instructions = "LATER_UNDELIVERED_FOCUS"
    briefs[MemberRole.RESEARCH_LEAD] = eng._render_brief(run, stages[1], MemberRole.RESEARCH_LEAD, run_dir)
    run.state = RunState.CORRECTING
    run.findings_history = [[]]
    run.correction_note = "Repair review schema fields only."
    corrected = eng._render_brief(run, stages[0], MemberRole.OUTSIDE_REVIEWER, run_dir)
    for brief in [*briefs.values(), corrected]:
        assert brief.count(FOCUS) == 1
        assert "venue_length: conference" in brief
        assert "generation.reviewed_draft" in brief
        assert "LATER_UNDELIVERED_FOCUS" not in brief and "LATER_PROJECT_SETTINGS" not in brief
        assert "sha256 " + packet_ids[0] in brief
    outside = briefs[MemberRole.OUTSIDE_REVIEWER]
    assert "PRIVATE" not in outside
    assert "internal-notebook" not in outside
    assert "basis.json" not in outside
    assert "Frozen scientific source files" not in outside
    assert "Repair review schema fields only." in corrected
    assert {path.name: path.read_bytes() for path in packet_dir.iterdir()} == before


def test_p5_brief_does_not_create_or_rebuild_the_prepared_packet(legacy_p5_workbench):
    from model_forge_codex.records import ArtifactError
    eng, _, branch = legacy_p5_workbench
    run = record(eng, branch, "run.p5_unprepared", "P5", "p5.review_revision")
    run_dir = eng.run_dir(run.project_id, run.run_id)
    basis = packet_basis(run_dir)
    write_json_atomic(run_dir / "basis.json", basis)
    stage = eng.stage_plan(run.project_id, "P5", run.mode)[0]
    with pytest.raises(ArtifactError):
        eng._render_brief(run, stage, MemberRole.OUTSIDE_REVIEWER, run_dir)
    assert not (run_dir / "review-packet").exists()


def test_isolated_p5_validation_uses_prepared_instructions_without_internal_sources(legacy_p5_workbench):
    eng, _, branch = legacy_p5_workbench
    run = record(eng, branch, "run.p5_isolated_validation", "P5", "p5.review_revision")
    run_dir = eng.run_dir(run.project_id, run.run_id)
    basis = packet_basis(run_dir)
    write_json_atomic(run_dir / "basis.json", basis)
    prepare_review_packet(run_dir, basis=basis, instructions=FOCUS, run_id=run.run_id)
    stage = eng.stage_plan(run.project_id, "P5", run.mode)[0]
    workspace = eng.member_workspace(run, stage.stage_id, MemberRole.OUTSIDE_REVIEWER)
    outside = read_json(REPO / "contracts/examples/review-report.example.json")
    outside["review_basis_generation_id"] = "generation.reviewed_draft"
    for issue in outside["prioritized_issues"]:
        issue["review_basis_generation_id"] = "generation.reviewed_draft"
    write_json_atomic(workspace / "outside_review.json", outside)
    # Internal source files are unavailable. Isolated draft checks may open
    # only the prepared external submission and the caller's own draft.
    for entry in basis["artifacts"]:
        Path(entry["path"]).unlink()
    Path(basis["records"][0]["snapshot_path"]).unlink()
    (run_dir / "basis.json").unlink()
    result = eng.validate_member_artifacts(run, stage, MemberRole.OUTSIDE_REVIEWER, workspace)
    assert result["status"] == "passed", result
    assert result["findings"] == []
    outside["review_basis_generation_id"] = "generation.unreviewed_revision"
    write_json_atomic(workspace / "outside_review.json", outside)
    result = eng.validate_member_artifacts(run, stage, MemberRole.OUTSIDE_REVIEWER, workspace)
    assert result["status"] == "failed"
    assert [finding["code"] for finding in result["findings"]] == ["review.target_mismatch"]
