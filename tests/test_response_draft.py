"""REST discussions preserve unsaved response kinds without adopting them."""
import pytest

from model_forge_codex.phase_interactions import published_issues, save_scoped_answer
from test_decision_choices import choice
from test_phase_interactions import answer
from test_researcher_workbench_api import api
from test_researcher_workbench_engine import publish, workbench


@pytest.mark.parametrize("draft", [
    {"kind": "choice", "option_id": "observed", "note": ""},
    {"kind": "custom", "note": "Use a separate specified cohort."},
    {"kind": "unknown", "note": ""},
])
async def test_response_draft_api_round_trip_preserves_saved_answer_and_never_saves_draft(api, draft):
    client, engine, project, branch = api
    item = choice(target_phase="P3", options=[
        {"id": "all", "label": "All eligible individuals", "consequence": "Includes incomplete follow-up."},
        {"id": "observed", "label": "Observed individuals", "consequence": "Restricts the target population."},
    ])
    publish(project, branch, "P3", {"attention_items": [item]}, "run.api-draft-source")
    issue = next(row for row in published_issues(project, branch) if row.get("attention_id") == item["attention_id"])
    saved = save_scoped_answer(project, issue, "Saved answer remains separate.", expected_revision=0)
    answer_path = project / "researcher" / "attention_resolutions.json"
    before = answer_path.read_bytes()
    answer(engine)
    root = "/api/v1/projects/project.test"
    response = await client.post(root + "/runs", json={"phase": "P3", "mode": "p3.assessment", "branch_id": branch,
        "intent": "assessment", "assessment_purpose": "issue_suggestions", "target": issue["explanation_target"],
        "instructions": "Explain my tentative response.", "researcher_response_draft": draft,
        "idempotency_key": "api.response-draft." + draft["kind"]})
    assert response.status_code == 200, response.text
    created = response.json()
    await engine._tasks[created["run_id"]]
    history = (await client.get(root + "/assessments")).json()["assessments"][0]
    canonical = history["researcher_response_draft"]
    assert canonical["kind"] == draft["kind"] and canonical["note"] == draft["note"]
    if draft["kind"] == "choice":
        assert canonical["option_id"] == "observed"
        assert canonical["label"] == "Observed individuals"
        assert canonical["consequence"] == "Restricts the target population."
    assert history["researcher_answer"]["note"] == saved["note"]
    assert history["researcher_answer"]["revision"] == saved["revision"]
    assert history["turns"][0]["researcher_response_draft"] == canonical
    assert history["messages"][0]["researcher_response_draft"] == canonical
    assert "unsaved" in engine.bridge.turns[-1]["brief"]
    assert answer_path.read_bytes() == before


async def test_response_draft_api_rejects_unlisted_id_and_client_authored_option_text(api):
    client, engine, project, branch = api
    item = choice(target_phase="P3")
    publish(project, branch, "P3", {"attention_items": [item]}, "run.api-invalid-draft")
    issue = next(row for row in published_issues(project, branch) if row.get("attention_id") == item["attention_id"])
    payload = {"phase": "P3", "mode": "p3.assessment", "branch_id": branch,
        "intent": "assessment", "assessment_purpose": "issue_suggestions", "target": issue["explanation_target"],
        "instructions": "Explain the choice."}
    for draft in [{"kind": "choice", "option_id": "unlisted"},
                  {"kind": "choice", "option_id": item["options"][0]["id"], "label": "Client replacement"}]:
        response = await client.post("/api/v1/projects/project.test/runs", json={**payload, "researcher_response_draft": draft})
        assert response.status_code == 409, response.text
    assert not (project / "researcher" / "attention_resolutions.json").exists()
    assert not engine._tasks
