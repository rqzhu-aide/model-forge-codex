"""Editable researcher direction stays distinct from each run's frozen brief."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import MemberRole
from model_forge_codex.methods import get_method
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import publish, record, seed_theory, target, workbench
from test_p5_review_packet import prepare_engine_review_packet


@pytest.fixture
async def brief_api(engine, monkeypatch):
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    source, bridge, project_id = engine
    app = create_app(data_root=source.data_root, bridge=bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, app.state.engine, project_id


@pytest.mark.parametrize("instructions", [None, "Use reinforcement learning to propose interacting particle dynamics."])
async def test_create_project_persists_optional_research_instructions(tmp_path, monkeypatch, instructions):
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    app = create_app(data_root=tmp_path / "data", bridge=FakeCodexBridge())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = {"name": "Entangled Langevin"}
        if instructions is not None:
            body["research_instructions"] = instructions
        created = await client.post("/api/v1/projects", json=body)
        assert created.status_code == 200
        project_id = created.json()["project_id"]
        saved = (await client.get(f"/api/v1/projects/{project_id}")).json()["project"]
        assert saved["research_instructions"] == (instructions or "")
        assert "research_question" not in saved
        assert read_json(app.state.engine.project_dir(project_id) / "project.json") == saved


async def test_create_legacy_split_fields_stores_one_combined_instruction(brief_api):
    client, eng, _ = brief_api
    created = await client.post("/api/v1/projects", json={
        "name": "Legacy client", "research_question": "Can particles help?", "research_instructions": "Use reinforcement learning.",
    })
    assert created.status_code == 200
    saved = read_json(eng.project_dir(created.json()["project_id"]) / "project.json")
    assert saved["research_instructions"] == "Can particles help?\n\nUse reinforcement learning."
    assert "research_question" not in saved


@pytest.mark.parametrize("question, instructions, combined", [
    ("Legacy question", "", "Legacy question"),
    ("Legacy question", "Legacy direction", "Legacy question\n\nLegacy direction"),
    ("Same text", "Same text", "Same text"),
])
async def test_legacy_get_and_list_normalize_without_writing(brief_api, question, instructions, combined):
    client, eng, project_id = brief_api
    path = eng.project_dir(project_id) / "project.json"
    old = {**read_json(path), "research_question": question, "research_instructions": instructions}
    write_json_atomic(path, old)
    before = path.read_bytes()
    detail = (await client.get(f"/api/v1/projects/{project_id}")).json()["project"]
    listed = next(p for p in (await client.get("/api/v1/projects")).json()["projects"] if p["project_id"] == project_id)
    assert detail == listed
    assert detail["research_instructions"] == combined and "research_question" not in detail
    assert path.read_bytes() == before


async def test_partial_edit_preserves_project_metadata_and_team(brief_api):
    client, eng, project_id = brief_api
    project = eng.project_dir(project_id)
    path = project / "project.json"
    original = {**read_json(path), "venue_length": "conference", "research_instructions": "Original direction", "custom_metadata": {"owner": "researcher"}}
    write_json_atomic(path, original)
    team_before = {str(p.relative_to(project)): p.read_bytes() for p in (project / "members").rglob("*") if p.is_file()}

    response = await client.patch(f"/api/v1/projects/{project_id}", json={"name": "  Entangled Langevin  "})
    assert response.status_code == 200
    renamed = response.json()["project"]
    assert renamed["name"] == "Entangled Langevin"
    assert renamed["research_instructions"] == original["research_question"] + "\n\nOriginal direction"
    assert "research_question" not in renamed
    combined = "Can interacting particles help at equal computational cost?\n\nDevelop partial Bellman operators with the target distribution as a fixed point."
    response = await client.patch(f"/api/v1/projects/{project_id}", json={
        "research_instructions": combined,
    })
    assert response.status_code == 200
    saved = response.json()["project"]
    assert saved["project_id"] == project_id and saved["custom_metadata"] == original["custom_metadata"]
    assert saved["venue_length"] == "conference"
    assert saved["research_instructions"] == combined and "research_question" not in saved
    assert original["research_question"] not in saved["research_instructions"]
    assert (await client.get(f"/api/v1/projects/{project_id}")).json()["project"] == saved
    assert {str(p.relative_to(project)): p.read_bytes() for p in (project / "members").rglob("*") if p.is_file()} == team_before
    cleared = await client.patch(f"/api/v1/projects/{project_id}", json={"research_instructions": ""})
    assert cleared.json()["project"]["research_instructions"] == ""
    assert "research_question" not in read_json(path)
    assert (await client.get(f"/api/v1/projects/{project_id}")).json()["project"]["research_instructions"] == ""


@pytest.mark.parametrize("body", [
    {}, {"name": ""}, {"name": " \n\t "}, {"name": "x" * 161},
    {"research_instructions": None}, {"research_question": "Obsolete split field"}, {"name": None},
    {"research_instructions": ["wrong type"]}, {"project_id": "project.replacement"},
    {"name": "valid", "provider": "custom"},
])
async def test_invalid_brief_edits_do_not_write(brief_api, body):
    client, eng, project_id = brief_api
    path = eng.project_dir(project_id) / "project.json"
    before = path.read_bytes()
    response = await client.patch(f"/api/v1/projects/{project_id}", json=body)
    assert response.status_code == 422
    assert path.read_bytes() == before


async def test_unknown_project_edit_returns_404_without_creation(brief_api):
    client, eng, _ = brief_api
    response = await client.patch("/api/v1/projects/project.unknown", json={"name": "Absent"})
    assert response.status_code == 404
    assert not eng.project_dir("project.unknown").exists()


async def test_read_only_viewer_blocks_brief_edit(brief_api, monkeypatch):
    client, eng, project_id = brief_api
    path = eng.project_dir(project_id) / "project.json"
    before = path.read_bytes()
    monkeypatch.setenv("MF_CODEX_READ_ONLY", "1")
    response = await client.patch(f"/api/v1/projects/{project_id}", json={"research_instructions": "Changed"})
    assert response.status_code == 403
    assert path.read_bytes() == before


async def test_p2_preparation_persists_without_changing_shared_inputs(brief_api):
    client, eng, project_id = brief_api
    project = eng.project_dir(project_id)
    project_before = (project / "project.json").read_bytes()
    basis_before = eng.compute_basis(project_id, "P2", "trunk", "p2.full_catalog")
    url = f"/api/v1/projects/{project_id}/phase2-preparation"
    empty = await client.get(url)
    assert empty.status_code == 200
    assert empty.json() == {"instructions": "", "updated_at": None, "revision": 0}
    text = "Lead only: preserve the exact equation.\n\\[U=T_\\pi U\\]"
    saved = await client.put(url, json={"instructions": text})
    assert saved.status_code == 200 and saved.json()["instructions"] == text
    assert saved.json()["updated_at"]
    assert (await client.get(url)).json() == saved.json()
    assert read_json(project / "researcher" / "preparation" / "P2" / "trunk.json") == saved.json()
    assert not (project / "researcher" / "p2_preparation.json").exists()
    scoped_url = f"/api/v1/projects/{project_id}/branches/trunk/phases/P2/preparation"
    assert (await client.get(scoped_url)).json() == saved.json()
    assert (await client.put(url, json={"instructions": text})).json() == saved.json()
    assert (project / "project.json").read_bytes() == project_before
    assert eng.compute_basis(project_id, "P2", "trunk", "p2.full_catalog") == basis_before
    assert eng.bridge.turns == []
    cleared = await client.put(url, json={"instructions": ""})
    assert cleared.status_code == 200 and (await client.get(url)).json()["instructions"] == ""


@pytest.mark.parametrize("body", [{}, {"instructions": None}, {"instructions": []}, {"instructions": "x", "project_id": "elsewhere"}])
async def test_p2_preparation_rejects_invalid_values(brief_api, body):
    client, eng, project_id = brief_api
    response = await client.put(f"/api/v1/projects/{project_id}/phase2-preparation", json=body)
    assert response.status_code == 422
    assert not (eng.project_dir(project_id) / "researcher" / "p2_preparation.json").exists()


async def test_p2_preparation_requires_existing_project_and_write_access(brief_api, monkeypatch):
    client, eng, project_id = brief_api
    missing = "/api/v1/projects/project.unknown/phase2-preparation"
    assert (await client.get(missing)).status_code == 404
    assert (await client.put(missing, json={"instructions": "x"})).status_code == 404
    assert not eng.project_dir("project.unknown").exists()
    monkeypatch.setenv("MF_CODEX_READ_ONLY", "1")
    assert (await client.put(f"/api/v1/projects/{project_id}/phase2-preparation", json={"instructions": "x"})).status_code == 403
    assert not (eng.project_dir(project_id) / "researcher" / "p2_preparation.json").exists()


async def test_active_and_new_runs_use_separate_frozen_project_instructions(brief_api, monkeypatch):
    client, eng, project_id = brief_api
    project = eng.project_dir(project_id)
    # Reproduce the first P1 launch, before any literature exists.
    (project / "branches" / "trunk" / "phases" / "p1" / "seed_record" / "current.json").unlink()
    old = {"research_question": "ORIGINAL_QUESTION", "research_instructions": "ORIGINAL_PROJECT_DIRECTION"}
    write_json_atomic(project / "project.json", {**read_json(project / "project.json"), **old})
    initial = eng.compute_basis(project_id, "P1", "trunk", "p1.literature_update")
    assert initial["records"] == [] and initial["sha256"]

    async def hold_run(_record, _stages):
        await asyncio.Event().wait()

    monkeypatch.setattr(eng, "_drive", hold_run)
    started = await eng.start_run(project_id, phase="P1", mode="p1.literature_update", branch_id="trunk",
                                 basis_sha256=initial["sha256"], instructions="THIS_RUN_ONLY")
    run_dir = eng.run_dir(project_id, started.run_id)
    frozen_bytes = (run_dir / "basis.json").read_bytes()
    try:
        changed = await client.patch(f"/api/v1/projects/{project_id}", json={
            "research_instructions": "UPDATED_QUESTION\n\nUPDATED_PROJECT_DIRECTION",
        })
        assert changed.status_code == 200
        for stage in eng.stage_plan(project_id, "P1", started.mode):
            for role in stage.roles:
                brief = eng._render_brief(started, stage, role, run_dir)
                assert "ORIGINAL_QUESTION" in brief and "UPDATED_QUESTION" not in brief
                assert "## Project instructions (verbatim)\n\nORIGINAL_QUESTION\n\nORIGINAL_PROJECT_DIRECTION" in brief
                assert "## Research question" not in brief and "## Project research instructions" not in brief
                assert "## Researcher instructions for this run (verbatim)\n\nTHIS_RUN_ONLY" in brief
                assert "UPDATED_PROJECT_DIRECTION" not in brief
        assert (run_dir / "basis.json").read_bytes() == frozen_bytes
        # Project edits do not silently change the active run's publication policy.
        assert eng._assert_publication_current(started)
    finally:
        await eng.cancel(project_id, started.run_id)

    rejected = await client.post(f"/api/v1/projects/{project_id}/runs", json={
        "phase": "P1", "mode": "p1.literature_update", "basis_sha256": initial["sha256"],
    })
    assert rejected.status_code == 409 and "project brief" in rejected.json()["detail"]
    assert eng.bridge.turns == []

    current = eng.compute_basis(project_id, "P1", "trunk", "p1.literature_update")
    assert current["sha256"] != initial["sha256"]
    following = await eng.start_run(project_id, phase="P1", mode="p1.literature_update", branch_id="trunk",
                                   basis_sha256=current["sha256"])
    try:
        next_dir = eng.run_dir(project_id, following.run_id)
        stage = eng.stage_plan(project_id, "P1", following.mode)[0]
        brief = eng._render_brief(following, stage, stage.roles[0], next_dir)
        assert "UPDATED_QUESTION" in brief and "UPDATED_PROJECT_DIRECTION" in brief
        assert "ORIGINAL_PROJECT_DIRECTION" not in brief and "THIS_RUN_ONLY" not in brief
        assert read_json(next_dir / "basis.json")["project"] == changed.json()["project"]
    finally:
        await eng.cancel(project_id, following.run_id)


async def test_assessment_gets_frozen_direction_and_outside_review_stays_isolated(legacy_p5_workbench, monkeypatch):
    eng, project, branch = legacy_p5_workbench
    original = {**read_json(project / "project.json"), "research_instructions": "FROZEN_TEAM_DIRECTION"}
    write_json_atomic(project / "project.json", original)
    package = seed_theory(project, branch)

    async def hold_run(_record, _stages):
        await asyncio.Event().wait()

    monkeypatch.setattr(eng, "_drive", hold_run)
    assessment = await eng.start_run("project.test", phase="P3", mode="p3.theory_revision", branch_id=branch,
                                     intent="assessment", target=target(package, branch), instructions="ASSESS_ONLY")
    try:
        write_json_atomic(project / "project.json", {**original, "research_instructions": "LATER_TEAM_DIRECTION"})
        stage = eng.stage_plan("project.test", "P3", assessment.mode)[0]
        brief = eng._render_brief(assessment, stage, stage.roles[0], eng.run_dir("project.test", assessment.run_id))
        assert "FROZEN_TEAM_DIRECTION" in brief and "ASSESS_ONLY" in brief
        assert "LATER_TEAM_DIRECTION" not in brief
        assert "Do not change the theory" in brief
    finally:
        await eng.cancel("project.test", assessment.run_id)

    publish(project, branch, "P5", {"manuscript": {
        "text": "MANUSCRIPT_FOR_REVIEW", "method_identity": get_method(project, branch)["identity"],
    }})
    reviewer = record(eng, branch, "run.project-direction-review", "P5", "p5.review_revision")
    run_dir = eng.run_dir("project.test", reviewer.run_id)
    prepare_engine_review_packet(eng, reviewer)
    stage = eng.stage_plan("project.test", "P5", reviewer.mode)[0]
    review_brief = eng._render_brief(reviewer, stage, MemberRole.OUTSIDE_REVIEWER, run_dir)
    assert "Independent manuscript review" in review_brief
    assert "TEAM_DIRECTION" not in review_brief and "Project instructions" not in review_brief
