"""Historical paper reading follows the retained publication and exact bytes."""
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.p5_review_packet import prepare_review_packet, read_review_packet
from model_forge_codex.records import ArtifactError
from model_forge_codex.research import artifacts_view
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from test_p5_review_packet import FOCUS, packet_basis
from test_researcher_workbench_engine import REPO, publish, record, workbench


def saved_pdf():
    stream = b"BT /F1 12 Tf 20 50 Td (Original limited support.) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 100] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    payload, offsets = b"%PDF-1.4\n", [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(payload))
        payload += str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    start = len(payload)
    payload += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return payload + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()


def retained_paper(project, branch, run_id, suffix, content):
    directory = project / "runs" / run_id / "outputs/p5.assembly_lead/working/research_lead"
    directory.mkdir(parents=True)
    paper = directory / ("paper" + suffix)
    paper.write_bytes(content)
    supplement = directory / "paper-source.tex"
    supplement.write_text("% exact source for " + run_id, encoding="utf-8")
    write_json_atomic(project / "runs" / run_id / "run.json", {
        "run_id": run_id, "phase": "P5", "branch_id": branch, "state": "published"})
    document = {"title": "Saved paper " + run_id, "manuscript_kind": "assembly_candidate",
                "venue_length": "journal", "target_audience": "Statistical researchers",
                "manuscript_artifact": {"artifact_id": "artifact.paper", "path": paper.name, "sha256": sha256_file(paper)},
                "supplementary_artifacts": [{"artifact_id": "artifact.source", "path": supplement.name,
                                              "label": "Manuscript TeX source", "sha256": sha256_file(supplement)}]}
    package = publish(project, branch, "P5", {"manuscript": document}, run_id)
    return package["records"]["manuscript"], paper, supplement, document


@pytest.mark.parametrize("suffix,kind,content", [
    (".md", "markdown", b"# Reviewed draft\n\nThe original support is limited.\n"),
    (".pdf", "pdf", saved_pdf()),
    (".tex", "tex_source", b"\\documentclass{article}\n\\begin{document}Original limited support.\\end{document}\n"),
])
async def test_saved_draft_api_reads_original_paper_and_supplements_after_revision(workbench, suffix, kind, content):
    eng, project, branch = workbench
    old, paper, supplement, document = retained_paper(project, branch, "run.old_paper", suffix, content)
    new, _, _, _ = retained_paper(project, branch, "run.new_paper", suffix, b"CURRENT_REVISION_MUST_NOT_REPLACE_OLD_PAPER")
    current = next(doc for doc in artifacts_view(project, branch)["documents"] if doc["kind"] == "manuscript")
    assert current["generation_ref"]["generation_id"] == new["generation_id"]
    base = f"/api/v1/projects/project.test/branches/{branch}/phases/P5/records/manuscript/{old['generation_id']}"
    app = create_app(data_root=eng.data_root, bridge=eng.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Existing raw-source consumers keep the immutable package record.
        assert (await client.get(base)).json() == document
        response = await client.get(base + "?view=document")
        assert response.status_code == 200, response.text
        saved = response.json()
        assert saved["generation_ref"]["generation_id"] == old["generation_id"]
        assert saved["generation_ref"]["run_id"] == "run.old_paper"
        assert saved["primary_source_verified"] is True
        assert saved["primary_artifact_kind"] == kind
        if kind == "markdown":
            assert saved["body_md"] == content.decode()
        elif kind == "tex_source":
            assert saved["source_text"] == content.decode()
        linked = await client.get(saved["primary_artifact_url"])
        assert linked.status_code == 200 and linked.content == content
        source = saved["supplementary_artifacts"][0]
        assert source["source_verified"] is True and source["label"] == "Manuscript TeX source"
        assert (await client.get(source["artifact_url"])).content == supplement.read_bytes()
        assert "CURRENT_REVISION" not in response.text
        # A once valid link also checks bytes when opened later.
        paper.write_bytes(b"CHANGED_OLD_FILE")
        assert (await client.get(saved["primary_artifact_url"])).status_code == 409
        unavailable = (await client.get(base + "?view=document")).json()
        assert "document_error" in unavailable and "primary_artifact_url" not in unavailable
        assert "CURRENT_REVISION" not in str(unavailable)
        supplement.write_bytes(b"CHANGED_OLD_SOURCE")
        unavailable = (await client.get(base + "?view=document")).json()
        assert "source_error" in unavailable["supplementary_artifacts"][0]
        assert "artifact_url" not in unavailable["supplementary_artifacts"][0]


async def test_legacy_inline_paper_remains_readable_without_inventing_scope(workbench):
    eng, project, branch = workbench
    package = publish(project, branch, "P5", {"manuscript": {"text": "# The saved inline manuscript\n\nA qualified result."}})
    generation = package["records"]["manuscript"]["generation_id"]
    app = create_app(data_root=eng.data_root, bridge=eng.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/project.test/branches/{branch}/phases/P5/records/manuscript/{generation}?view=document")
        assert response.status_code == 200
        saved = response.json()
        assert saved["body_md"] == "# The saved inline manuscript\n\nA qualified result."
        assert "venue_length" not in saved["structured"]
        assert "primary_artifact_url" not in saved


async def test_outside_correction_turn_delivers_original_packet_without_internal_inputs(workbench):
    eng, _, branch = workbench
    run = record(eng, branch, "run.p5_packet_correction", "P5", "p5.review_revision")
    run.instructions = FOCUS
    run_dir = eng.run_dir(run.project_id, run.run_id)
    basis = packet_basis(run_dir)
    write_json_atomic(run_dir / "basis.json", basis)
    packet = prepare_review_packet(run_dir, basis=basis, instructions=FOCUS, run_id=run.run_id)
    before = {path.name: path.read_bytes() for path in (run_dir / "review-packet").iterdir()}
    stage = eng.stage_plan(run.project_id, "P5", run.mode)[0]
    outside = read_json(REPO / "contracts/examples/review-report.example.json")
    outside["review_basis_generation_id"] = "generation.reviewed_draft"
    for issue in outside["prioritized_issues"]:
        issue["review_basis_generation_id"] = "generation.reviewed_draft"
    eng.bridge.default_behavior = ("ok", {"outside_review.json": json.dumps(outside)})
    initial = await eng._drive_member_turn(run, stage, MemberRole.OUTSIDE_REVIEWER, run_dir)
    assert initial.succeeded
    for source in [*basis["artifacts"], basis["records"][0]]:
        Path(source.get("path") or source["snapshot_path"]).unlink()
    (run_dir / "basis.json").unlink()
    run.state = RunState.CORRECTING
    run.instructions = "LATER_UNDELIVERED_FOCUS"
    run.findings_history = [[{"object_id": "p5.outside_review", "code": "schema.required", "message": "Repair the declared review field."}]]
    run.correction_note = "Repair the review field without changing its draft."
    eng._save_run(run)
    correction = await eng._drive_member_turn(run, stage, MemberRole.OUTSIDE_REVIEWER, run_dir)
    assert correction.succeeded
    assert len(eng.bridge.turns) == 2
    delivered = eng.bridge.turns[-1]["brief"]
    assert FOCUS in delivered and "LATER_UNDELIVERED_FOCUS" not in delivered
    assert "Repair the review field without changing its draft." in delivered
    assert "sha256 " + packet["packet_sha256"] in delivered
    assert "generation.reviewed_draft" in delivered and "PRIVATE" not in delivered
    assert "basis.json" not in delivered and "internal-notebook" not in delivered
    assert read_review_packet(run_dir / "review-packet") == packet
    assert {path.name: path.read_bytes() for path in (run_dir / "review-packet").iterdir()} == before
    workspace = eng.member_workspace(run, stage.stage_id, MemberRole.OUTSIDE_REVIEWER)
    assert eng.validate_member_artifacts(run, stage, MemberRole.OUTSIDE_REVIEWER, workspace)["status"] == "passed"
    # Isolated correction still refuses a damaged submission before dispatch.
    (run_dir / "review-packet/manuscript-0.md").write_bytes(b"CHANGED_SUBMISSION")
    with pytest.raises(ArtifactError, match="changed or disappeared"):
        await eng._drive_member_turn(run, stage, MemberRole.OUTSIDE_REVIEWER, run_dir)
    assert len(eng.bridge.turns) == 2
