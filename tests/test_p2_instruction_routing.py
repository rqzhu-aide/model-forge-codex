"""P2 input reaches the lead while mathematical proposals remain independent."""
import copy
import json
import importlib.util
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.direct_validation import validate_direct_outputs
from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.p2_delivery import specialist_view
from model_forge_codex.records import current_records, read_generation, publish_package
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json
from test_direct_workflow import PID, SEED, REPO, complete, direct_engine, p1_documents, p2_documents, script


NOTE = "LEAD_ONLY_DIRECTION: compare implementability carefully; consider the attached operator idea."
PREPARATION = "LEAD_ONLY_P1_PREPARATION"


def retain_legacy_p2_catalog(project):
    """Exercise the actual historical stage plan and its permissive schema."""
    root = project / "contracts"
    phase = read_json(REPO / "tests/fixtures/catalog-v1.7-p2/P2.json")
    (root / "contracts/phases/P2.json").write_text(json.dumps(phase), encoding="utf-8")
    registry = read_json(root / "contracts/phases.json")
    registry["contracts"] = [phase if item["phase_id"] == "P2" else item for item in registry["contracts"]]
    (root / "contracts/phases.json").write_text(json.dumps(registry), encoding="utf-8")
    schema = read_json(root / "schemas/lead-proposal-legacy.schema.json")
    schema["$id"] = schema["$id"].replace("lead-proposal-legacy", "lead-proposal")
    (root / "schemas/lead-proposal.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    pin = read_json(root / "catalog-pin.json")
    pin["catalog_version"] = "1.7.0"
    (root / "catalog-pin.json").write_text(json.dumps(pin), encoding="utf-8")
    (root / "VERSION").write_text("1.7.0\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("refresh_test_catalog", REPO / "contracts/refresh_manifest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.refresh(root)


def test_scientific_views_preserve_exact_math_without_mutating_originals():
    basis = p1_documents()["p1.research_basis"]
    proposal = p2_documents(True)[0]["p2.lead_proposal"]
    original_basis, original_proposal = copy.deepcopy(basis), copy.deepcopy(proposal)
    shared = specialist_view("P1", "research_basis", basis)
    assert "phase2_preparation" not in shared
    assert shared["research_setting"] == basis["research_setting"]
    assert shared["landscape"] == basis["landscape"]
    review = specialist_view("P2", "lead_proposal", proposal)
    assert "researcher_origin" not in review
    assert review["method"] == proposal["method"]
    assert basis == original_basis and proposal == original_proposal
    assert specialist_view("P2", "lead_proposal", {"no_method_proposed": True, "reason_markdown": NOTE}) == {
        "schema_version": "1.0.0", "no_method_proposed": True}


async def test_contextual_answers_keep_shared_setting_and_p2_lead_delivery(direct_engine, monkeypatch):
    engine, project = direct_engine
    from test_cumulative_attention import issue
    questions = [issue("question." + phase, schema_version="1.1.0",
                       kind="researcher_decision", target_phase=phase,
                       context_markdown=r"$$J(\pi)=\mathbb E_\pi[\sum_{t\geq0}\gamma^tR_t].$$")
                 for phase in ("P1", "P2")]
    # A committed question's origin and intended phase survive its answer.
    publish_package(project / "branches/trunk/phases/p1", {
        "attention_items": json.dumps(questions).encode()
    }, run_id="run.questions", phase="P1", branch_id="trunk")
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    app = create_app(engine.data_root, engine.bridge)
    shared_answer = "SHARED_SETTING: use discount factor 0.95."
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for phase, note in (("P1", shared_answer), ("P2", NOTE)):
            response = await client.post(f"/api/v1/projects/{PID}/attention/question.{phase}/resolve", json={"note": note})
            assert response.status_code == 200, response.text
    outputs, files = p2_documents(False)
    script(engine, "P2", "p2.full_catalog", outputs, files)
    run = await complete(engine, "P2", "p2.full_catalog")
    frozen = read_json(engine.run_dir(PID, run.run_id) / "basis.json")
    original_path = Path(frozen["cumulative_inputs"]["researcher_answers"]["snapshot_path"])
    original = read_json(original_path)
    assert {answer["note"] for answer in original["items"]} == {shared_answer, NOTE}
    assert all(answer["attention"]["context_markdown"] == questions[0]["context_markdown"] for answer in original["items"])
    for role in (MemberRole.THEORIST, MemberRole.DATA_ANALYST):
        view_paths = list((engine.run_dir(PID, run.run_id) / "inputs/answer-views" / role.value).glob("researcher_answers.json"))
        assert view_paths
        for path in view_paths:
            assert shared_answer in path.read_text() and NOTE not in path.read_text()
        brief = (engine.run_dir(PID, run.run_id) / "briefs" / f"p2.independent_proposals.{role.value}.md").read_text()
        assert str(original_path) not in brief
        assert any(str(path) in brief for path in view_paths)
    lead_briefs = list((engine.run_dir(PID, run.run_id) / "briefs").glob("*.research_lead.md"))
    lead_view = engine.run_dir(PID, run.run_id) / "inputs/answer-views/research_lead/researcher_answers.json"
    assert {answer["note"] for answer in read_json(lead_view)["items"]} == {shared_answer, NOTE}
    assert any(str(lead_view) in path.read_text() for path in lead_briefs)


@pytest.mark.parametrize("proposes_method", [False, True])
async def test_unified_input_routes_only_to_lead_and_reviews_only_real_proposals(direct_engine, monkeypatch, proposes_method):
    engine, project = direct_engine
    if not proposes_method:
        retain_legacy_p2_catalog(project)
    p1 = p1_documents()
    if not proposes_method:
        for family in ("lead_literature", "theory_literature", "empirical_literature", "research_basis"):
            p1[f"p1.{family}"]["schema_version"] = "1.1.0"
    p1["p1.research_basis"]["phase2_preparation"]["instructions_markdown"] = PREPARATION
    script(engine, "P1", "p1.literature_update", p1)
    await complete(engine, "P1", "p1.literature_update")
    engine.bridge.turns.clear()
    outputs, files = p2_documents(proposes_method, include_lead=proposes_method)
    if proposes_method:
        outputs["p2.lead_proposal"]["researcher_origin"] = {
            "title": "Researcher's direction", "specification_markdown": NOTE,
            "source_reference": "Additional instructions or ideas for Phase 2"}
    else:
        outputs["p2.lead_proposal"] = {"schema_version": "1.0.0", "no_method_proposed": True,
                                       "reason_markdown": "These are comparison directions, not a separate method. " + NOTE}
    script(engine, "P2", "p2.researcher_proposal", outputs, files)
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    app = create_app(engine.data_root, engine.bridge)
    basis = engine.compute_basis(PID, "P2", "trunk", "p2.full_catalog")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/projects/{PID}/runs", json={
            "phase": "P2", "mode": "p2.full_catalog", "instructions": NOTE,
            "basis_sha256": basis["sha256"], "idempotency_key": "single-p2-text-input"})
        assert response.status_code == 200, response.text
        started = response.json()
    record = app.state.engine.load_run(PID, started["run_id"])
    await app.state.engine._tasks[record.run_id]
    final = app.state.engine.load_run(PID, record.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert final.mode == "p2.researcher_proposal" and final.instructions == NOTE
    assert final.supplied_method is None  # No synthetic method manufactured from text.
    stages = app.state.engine._stages(final)
    assert len(stages) == 3 and len(engine.bridge.turns) == 6
    run_dir = engine.run_dir(PID, record.run_id)
    for stage in stages:
        for role in stage.roles:
            brief = (run_dir / "briefs" / f"{stage.stage_id}.{role.value}.md").read_text()
            if role is MemberRole.RESEARCH_LEAD:
                assert NOTE in brief
            else:
                assert NOTE not in brief and PREPARATION not in brief
                assert SEED["specification_markdown"] not in brief
                if stage.sequence == 1:
                    assert "(this run, stage" not in brief
                else:
                    other = "empirical" if role is MemberRole.THEORIST else "theory"
                    assert f'"proposal_id": "proposal.{other}"' in brief
                    if proposes_method:
                        assert '"proposal_id": "proposal.lead"' in brief
                        assert '"researcher_origin"' not in brief
                    else:
                        assert '"no_method_proposed": true' in brief
                        assert '"proposal_id": "proposal.lead"' not in brief
    for path in (run_dir / "inputs/specialist-views").rglob("*.json"):
        assert NOTE not in path.read_text() and PREPARATION not in path.read_text()
    frozen = read_json(run_dir / "basis.json")
    original_basis_ref = next(ref for ref in frozen["records"] if ref["family"] == "research_basis")
    assert PREPARATION in Path(original_basis_ref["snapshot_path"]).read_text()
    p2_dir = project / "branches/trunk/phases/p2"
    refs = current_records(p2_dir)
    catalog = read_generation(p2_dir, "method_catalog", refs["method_catalog"])
    assert len(catalog["methods"]) == (3 if proposes_method else 2)
    original_lead = read_generation(p2_dir, "lead_proposal", refs["lead_proposal"])
    assert original_lead == outputs["p2.lead_proposal"]
    # Subsequent specialist delivery also omits raw origin and no-proposal reasons.
    engine.bridge.turns.clear()
    later_outputs, later_files = p2_documents(False, include_lead=proposes_method)
    script(engine, "P2", "p2.full_catalog", later_outputs, later_files)
    later = await complete(engine, "P2", "p2.full_catalog")
    later_dir = engine.run_dir(PID, later.run_id)
    for path in (later_dir / "briefs").glob("*.md"):
        if "research_lead" not in path.name:
            assert NOTE not in path.read_text() and PREPARATION not in path.read_text()
    for path in (later_dir / "inputs/specialist-views").rglob("*.json"):
        assert NOTE not in path.read_text() and PREPARATION not in path.read_text()


def test_audits_do_not_target_a_lead_response_that_contains_no_method():
    outputs, _ = p2_documents(False, include_lead=False)
    outputs["p2.lead_proposal"] = {"schema_version": "1.0.0", "no_method_proposed": True,
                                   "reason_markdown": "Only comparison instructions were supplied."}
    assert validate_direct_outputs("P2", outputs, mode="p2.researcher_proposal", lead_instructions=NOTE) == []
    outputs["p2.theory_review"]["assessments"].append({"proposal_id": "proposal.lead"})
    assert any(f.code == "review.target_coverage" for f in validate_direct_outputs("P2", outputs, mode="p2.researcher_proposal", lead_instructions=NOTE))


@pytest.mark.parametrize("mode", ["p2.full_catalog", "p2.focused_method", "p2.researcher_proposal"])
def test_current_p2_plan_requires_three_distinct_role_foci_and_full_cross_audits(direct_engine, mode):
    engine, project = direct_engine
    catalog = Catalog(project / "contracts")
    proposal, audit, comparison = engine.stage_plan(PID, "P2", mode)
    assert len(proposal.roles) == 3
    assert set(proposal.writes) == {"p2.lead_proposal", "p2.theory_proposal", "p2.empirical_proposal"}
    assert all("exactly one" in text.lower() for text in proposal.role_objectives.values())
    assert "researcher" in proposal.role_objectives["research_lead"]
    assert "assumptions" in proposal.role_objectives["theorist"]
    assert "data" in proposal.role_objectives["data_analyst"]
    assert "No proposer reads another member" in proposal.isolation_rule
    assert "p2.lead_proposal" in audit.role_reads["theorist"]
    assert "p2.lead_proposal" in audit.role_reads["data_analyst"]
    assert "p2.theory_proposal" not in audit.role_reads["theorist"]
    assert "p2.empirical_proposal" not in audit.role_reads["data_analyst"]
    assert comparison.writes == ("p2.catalog_assessment",)
    assert "Do not invent a fourth method" in comparison.objective
    documents, _ = p2_documents(False)
    assert not validate_direct_outputs("P2", documents, mode=mode, catalog=catalog)
    declined = {**documents, "p2.lead_proposal": {"schema_version": "1.0.0", "no_method_proposed": True,
                                                "reason_markdown": "Only general guidance was provided."}}
    assert catalog.validate_output("p2.lead_proposal", declined["p2.lead_proposal"])
    assert any(f.code == "proposal.missing_lead" for f in validate_direct_outputs("P2", declined, catalog=catalog, mode=mode))
    missing = {key: value for key, value in documents.items() if key != "p2.lead_proposal"}
    assert any(f.code == "proposal.missing_lead" for f in validate_direct_outputs("P2", missing, catalog=catalog, mode=mode))
    documents["p2.catalog_assessment"]["method_dispositions"].append({"proposal_id": "proposal.fourth", "status": "retain", "rationale": "New hybrid"})
    assert any(f.code == "catalog.proposal_coverage" for f in validate_direct_outputs("P2", documents, catalog=catalog, mode=mode))
