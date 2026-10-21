"""Method origin material is frozen into later runs as verifiable references."""
import json

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.method_provenance import current_method_catalog, resolve_method_provenance
from model_forge_codex.methods import activate_method, get_method
from model_forge_codex.records import generation_path
from model_forge_codex.runs import owned_writes
from model_forge_codex.storage import read_json
from test_direct_workflow import PID, REPO, complete, direct_engine, p1_documents, p2_documents, script
from test_researcher_workbench_engine import scientific_output_documents, script_scientific_run, workbench


def script_branch_run(engine, branch, phase, mode, documents, files=None):
    queues = {}
    for stage in engine.stage_plan(PID, phase, mode):
        for role in stage.roles:
            key = "research_lead:PROJECT:trunk" if role is MemberRole.RESEARCH_LEAD else f"{role.value}:{phase}:{branch}"
            docs = dict(files or {})
            docs.update({output.split(".", 1)[1] + ".json": json.dumps(documents[output])
                         for output in owned_writes(stage, role)})
            queues.setdefault(key, []).append(("ok", docs))
    for key, queue in queues.items():
        engine.bridge.script_thread(key, queue)


async def run_p2(direct_engine):
    engine, project = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    outputs, files = p2_documents(False)
    script(engine, "P2", "p2.full_catalog", outputs, files)
    p2_run = await complete(engine, "P2", "p2.full_catalog")
    return engine, project, outputs, p2_run


@pytest.mark.asyncio
async def test_branch_basis_freezes_exact_proposal_reviews_and_assessment(direct_engine):
    engine, project, outputs, p2_run = await run_p2(direct_engine)
    branch = activate_method(project, "method.theory")["branch_id"]
    basis = engine.compute_basis(PID, "P3", branch, "p3.theory_establishment")
    assert set(basis["method_provenance"]) == {"method.theory"}
    entry = basis["method_provenance"]["method.theory"]
    assert entry["unavailable"] == []
    assert entry["origin"]["run_id"] == p2_run.run_id
    proposal = entry["materials"]["proposal"]
    assert proposal["document"] == outputs["p2.theory_proposal"]
    assert proposal["ref"]["run_id"] == p2_run.run_id
    assert proposal["ref"]["family"] == "theory_proposal"
    reviews = entry["materials"]["reviews"]
    assert [review["document"]["review_id"] for review in reviews] == ["review.empirical"]
    assert reviews[0]["matched_proposal_id"] == "proposal.theory"
    assessment = entry["materials"]["catalog_assessment"]
    assert assessment["document"] == outputs["p2.catalog_assessment"]
    assert any(option["applies_to"] == "proposal.theory" for option in assessment["document"]["modification_options"])
    # Every reference verifies against the published bytes.
    store = project / "branches/trunk/phases/p2"
    for material in [proposal, assessment, *reviews]:
        path = generation_path(store, material["ref"]["family"], material["ref"])
        assert json.loads(path.read_text()) == material["document"]
        assert material["sha256"] == material["ref"]["content_sha256"]
    # Provenance stays outside the filtered scientific inputs.
    assert "method_provenance" not in basis["cumulative_inputs"]


@pytest.mark.asyncio
async def test_p2_rerun_basis_covers_every_catalog_method(direct_engine):
    engine, project, outputs, p2_run = await run_p2(direct_engine)
    basis = engine.compute_basis(PID, "P2", "trunk", "p2.full_catalog")
    provenance = basis["method_provenance"]
    assert set(provenance) == {"method.theory", "method.empirical", "method.lead"}
    for stable_id, entry in provenance.items():
        assert entry["origin"]["run_id"] == p2_run.run_id
        assert entry["materials"]["proposal"]["document"]["proposal_id"] == f"proposal.{stable_id.split('.')[-1]}"
        assert entry["unavailable"] == []


@pytest.mark.asyncio
async def test_brief_links_origin_files_without_casting_them_as_instructions(direct_engine):
    engine, project, outputs, p2_run = await run_p2(direct_engine)
    branch = activate_method(project, "method.theory")["branch_id"]
    method = get_method(project, branch)
    documents, files = scientific_output_documents(Catalog(project / "contracts"), "P3", method["identity"])
    script_branch_run(engine, branch, "P3", "p3.theory_establishment", documents, files)
    record = await engine.start_run(PID, phase="P3", mode="p3.theory_establishment", branch_id=branch)
    await engine._tasks[record.run_id]
    final = engine.load_run(PID, record.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    run_dir = engine.run_dir(PID, record.run_id)
    saved = read_json(run_dir / "inputs" / "method-sources" / "method.theory.json")
    assert saved["materials"]["proposal"]["document"] == outputs["p2.theory_proposal"]
    assert saved["origin"]["run_id"] == p2_run.run_id
    basis = read_json(run_dir / "basis.json")
    assert basis["method_provenance"]["method.theory"]["sha256"] == saved["sha256"]
    briefs = list((run_dir / "briefs").glob("*.md"))
    assert briefs
    text = "\n".join(path.read_text() for path in briefs)
    assert "Method source provenance" in text
    assert "not new instructions" in text
    assert "method-sources" in text


@pytest.mark.asyncio
async def test_legacy_catalog_origin_is_explicitly_unavailable(workbench):
    eng, project, branch = workbench
    basis = eng.compute_basis("project.test", "P3", branch, "p3.theory_establishment")
    entry = basis["method_provenance"]["method.overlap_stabilized_score"]
    assert entry["origin"] is None
    assert entry["materials"] == {}
    assert entry["unavailable"] == ["The producing run for this method definition is not recorded."]
    script_scientific_run(eng, project, branch, "P3", "p3.theory_establishment")
    record = await eng.start_run("project.test", phase="P3", mode="p3.theory_establishment", branch_id=branch)
    await eng._tasks[record.run_id]
    final = eng.load_run("project.test", record.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    run_dir = eng.run_dir("project.test", record.run_id)
    saved = read_json(run_dir / "inputs" / "method-sources" / "method.overlap_stabilized_score.json")
    assert saved["unavailable"] == ["The producing run for this method definition is not recorded."]
    text = "\n".join(path.read_text() for path in (run_dir / "briefs").glob("*.md"))
    assert "Unavailable: The producing run for this method definition is not recorded." in text


def test_unverifiable_producing_generation_is_reported_not_dropped(direct_engine):
    # Synchronous body; the fixture is only used for its project layout.
    engine, project = direct_engine
    catalog = {"methods": [], "method_sources": {"method.ghost": {
        "run_id": "run.absent", "stage_id": None, "family": "theory_proposal",
        "proposal_id": "proposal.ghost", "identity": {"stable_id": "method.ghost", "version": 1, "definition_sha256": "a" * 64}}}}
    entry = resolve_method_provenance(project, catalog, ["method.ghost"])["method.ghost"]
    assert entry["materials"] == {}
    assert entry["unavailable"] == ["The P2 package published by run run.absent is unavailable."]


def test_current_method_catalog_rebuild_keeps_incremental_provenance(direct_engine):
    engine, project = direct_engine
    from test_researcher_workbench_engine import publish
    method = read_json(REPO / "contracts/examples/method.example.json")
    publish(project, "trunk", "P2", {"method_changes": [method]}, "run.legacy.p2")
    rebuilt = current_method_catalog(project)
    stable_id = method["identity"]["stable_id"]
    assert rebuilt["methods"] == [method]
    source = rebuilt["method_sources"][stable_id]
    assert source["run_id"] == "run.legacy.p2"
    assert source["family"] == "method_changes"
    assert source["identity"] == method["identity"]
    assert "origin_unavailable" not in source
    assert rebuilt["derived"] is True
