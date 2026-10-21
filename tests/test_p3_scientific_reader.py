"""P3 reading projections from a complete, contract-validated publication."""
from copy import deepcopy

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.domain import RunState
from model_forge_codex.records import current_records, generation_path, read_generation, source_artifact_path
from model_forge_codex.research import artifacts_view
from model_forge_codex.research_sources import theory_statement_projection
from model_forge_codex.service import create_app
from test_researcher_workbench_engine import script_scientific_run, workbench


@pytest.fixture
async def published_theory(workbench):
    eng, project, branch = workbench
    def record_audit(documents):
        audit = documents["p3.analyst_audit"]
        audit["scientific_outcome"]["conclusion"] = "Identification is supported only with positive overlap."
        audit["scientific_outcome"]["material_disagreement"] = [
            "The analyst contests the operational scope of the uniform claim."]
        issue = {"issue_id": "issue.fixture.overlap", "category": "scope", "severity": "major",
                 "title": "Overlap boundary", "statement": "Zero weights leave the target unidentified.",
                 "consequence": "The guarantee does not cover the boundary.", "status": "open"}
        audit["issues"] = [deepcopy(issue)]
        documents["p3.analyst_handoff"]["unresolved_issues"] = [issue]
        documents["p3.decision"]["issue_dispositions"] = [{
            "issue_id": issue["issue_id"], "status": "contested",
            "reason": "Fixture only: the Analyst and Lead retain different assessments of boundary relevance."}]
    documents = script_scientific_run(eng, project, branch, "P3", "p3.theory_establishment", transform=record_audit)
    run = await eng.start_run("project.test", phase="P3", mode="p3.theory_establishment", branch_id=branch)
    await eng._tasks[run.run_id]
    final = eng.load_run("project.test", run.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    phase = project / "branches" / branch / "phases" / "p3"
    pointers = current_records(phase)
    ref = {"branch": branch, "phase": "P3", "run_id": run.run_id, **pointers["theory_record"]}
    theory = read_generation(phase, "theory_record", pointers["theory_record"])
    statement = next(item for item in theory["statements"] if item["justification"]["artifacts"])
    proof = statement["justification"]["artifacts"][0]
    # A lead can preserve a theorist's pointer without retaining its own copy.
    outputs = project / "runs" / run.run_id / "outputs"
    for stage in outputs.iterdir():
        if not stage.is_dir() or stage.name == "p3.theorist":
            continue
        for root in [stage, *sorted((stage / "working").glob("*"))]:
            path = root / proof["path"]
            if path.is_file():
                path.unlink()
    retained = source_artifact_path(project, ref, proof)
    assert retained.is_relative_to(outputs / "p3.theorist")
    return eng, project, branch, phase, pointers, theory, statement, retained, documents


async def test_published_theory_links_retained_proofs_in_claims_and_glossary(published_theory, monkeypatch):
    eng, project, branch, phase, pointers, theory, statement, retained, _ = published_theory
    before = {family: generation_path(phase, family, pointer).read_bytes() for family, pointer in pointers.items()}
    view = artifacts_view(project, branch)
    claim = next(item for item in view["claim_maps"][0]["claims"] if item["statement_id"] == statement["statement_id"])
    glossary = view["glossaries"][0]["glossary"][statement["statement_id"]]
    proof = claim["justification"]["artifacts"][0]
    assert proof == glossary["justification"]["artifacts"][0]
    assert proof["source_verified"]
    assert "/outputs/p3.theorist/artifact?" in proof["artifact_url"]
    assert proof["sha256"] == statement["justification"]["artifacts"][0]["sha256"]
    assert proof["locator"] == statement["justification"]["artifacts"][0]["locator"]
    assert "artifact_url" not in statement["justification"]["artifacts"][0]
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    app = create_app(data_root=eng.data_root, bridge=eng.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(proof["artifact_url"])
    assert response.status_code == 200
    assert response.content == retained.read_bytes()
    assert before == {family: generation_path(phase, family, pointer).read_bytes() for family, pointer in pointers.items()}


async def test_published_theory_keeps_attributed_audit_and_scientific_disagreement(published_theory):
    _, project, branch, phase, pointers, _, _, _, documents = published_theory
    view = artifacts_view(project, branch)
    audit = next(item for item in view["documents"] if item["kind"] == "analyst_audit")
    assert audit["title"] == "Independent audit by Data Analyst"
    assert audit["producer_role"] == "data_analyst"
    assert audit["generation_ref"]["stage_id"] == "p3.analyst"
    assert audit["generation_ref"]["generation_id"] == pointers["analyst_audit"]["generation_id"]
    assert audit["primary_source_verified"] and audit["body_md"]
    assert audit["structured"]["issues"] == documents["p3.analyst_audit"]["issues"]
    assert audit["structured"]["scientific_outcome"]["material_disagreement"] == [
        "The analyst contests the operational scope of the uniform claim."]
    assert read_generation(phase, "analyst_audit", pointers["analyst_audit"]) == audit["structured"]


async def test_corrupt_retained_proof_does_not_become_a_usable_or_favorable_claim(published_theory):
    _, project, branch, _, _, _, statement, retained, _ = published_theory
    retained.write_text("Changed proof bytes", encoding="utf-8")
    view = artifacts_view(project, branch)
    claim = next(item for item in view["claim_maps"][0]["claims"] if item["statement_id"] == statement["statement_id"])
    proof = claim["justification"]["artifacts"][0]
    assert "artifact_url" not in proof and not proof.get("source_verified")
    assert "digest" in proof["source_error"]
    assert claim["status"] == statement["status"]
    assert claim["justification"]["summary"] == statement["justification"]["summary"]
    assert proof == view["glossaries"][0]["glossary"][statement["statement_id"]]["justification"]["artifacts"][0]


def test_unverified_authored_urls_are_discarded_without_mutating_the_statement(tmp_path):
    statement = {"statement_id": "statement.historical", "status": "conditional", "justification": {
        "kind": "proof_sketch", "artifacts": [{"path": "proof.md", "sha256": "a" * 64,
            "locator": "Lemma 2", "artifact_url": "/api/forged-proof", "source_verified": True,
            "source_error": "Authored error"}]}}
    before = deepcopy(statement)
    projected = theory_statement_projection(tmp_path, {"branch": "method.a", "phase": "P3"}, statement)
    proof = projected["justification"]["artifacts"][0]
    assert "artifact_url" not in proof and "source_verified" not in proof
    assert proof["source_error"] == "The producing run was not recorded for this file."
    assert proof["locator"] == "Lemma 2"
    assert statement == before
