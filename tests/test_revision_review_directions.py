"""Researchers can inspect the same immutable directions sent to P5 reviewers."""
from model_forge_codex.p5_review_packet import prepare_review_packet
from model_forge_codex.research import artifacts_view
from test_p5_review_packet import packet_basis
from test_researcher_workbench_api import api
from test_researcher_workbench_engine import workbench, publish, record


async def test_frozen_review_directions_access_and_projection(api):
    client, engine, project, branch = api
    run = record(engine, branch, "run.review.focus", phase="P5", mode="p5.review_revision")
    run_dir = engine.run_dir(run.project_id, run.run_id)
    prepare_review_packet(run_dir, basis=packet_basis(run_dir),
                          instructions="Check the unsupported comparison.", run_id=run.run_id)
    publish(project, branch, "P5", {"outside_review": {"summary": "Qualified finding."}}, run_id=run.run_id)
    doc = next(item for item in artifacts_view(project, branch=branch)["documents"]
               if item["kind"] == "outside_review")
    assert "Check the unsupported comparison." in doc["review_focus"]
    response = await client.get(doc["review_focus_url"])
    assert response.status_code == 200
    assert response.text == doc["review_focus"]
    wrong = doc["review_focus_url"].split("?", 1)[0] + "?sha256=" + "0" * 64
    assert (await client.get(wrong)).status_code == 409
    (run_dir / "review-packet" / "instructions.md").write_text("Changed directions", encoding="utf-8")
    assert (await client.get(doc["review_focus_url"])).status_code == 404
    broken = next(item for item in artifacts_view(project, branch=branch)["documents"]
                  if item["kind"] == "outside_review")
    assert "review_focus" not in broken and broken["review_focus_error"]


async def test_old_review_has_no_invented_focus(api):
    client, engine, project, branch = api
    run = record(engine, branch, "run.review.legacy", phase="P5", mode="p5.review_revision")
    publish(project, branch, "P5", {"outside_review": {"summary": "An older review."}}, run_id=run.run_id)
    doc = next(item for item in artifacts_view(project, branch=branch)["documents"]
               if item["kind"] == "outside_review")
    assert "review_focus" not in doc and "review_focus_url" not in doc
    url = f"/api/v1/projects/{run.project_id}/runs/{run.run_id}/review-packet/instructions?sha256={'0' * 64}"
    assert (await client.get(url)).status_code == 404
