"""Researcher workflow API regressions over published sources, not UI mocks."""
import json
from copy import deepcopy

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex import browse
from model_forge_codex.migration import upgrade_catalog
from model_forge_codex.records import current_records, generation_path, publish_package
from model_forge_codex.research import artifacts_view
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, sha256_bytes, write_json_atomic
from test_researcher_workbench_engine import workbench, publish, seed_theory, target, REPO


@pytest.fixture
async def api(workbench, monkeypatch):
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    eng, project, branch = workbench
    app = create_app(data_root=eng.data_root, bridge=eng.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, app.state.engine, project, branch


async def test_exact_branch_scope_and_array_source(api):
    client, eng, project, branch = api
    seed_theory(project, branch)
    publish(project, "method.other", "P3", {"claim_map": {"claims": [{"statement_id": "secret.other"}]}})
    trunk = (await client.get("/api/v1/projects/project.test/artifacts?branch=trunk")).json()
    assert trunk["claim_maps"] == []
    method = (await client.get(f"/api/v1/projects/project.test/artifacts?branch={branch}")).json()
    assert len(method["claim_maps"]) == 1
    assert method["claim_maps"][0]["theory_generation_ref"]["family"] == "theory_record"
    assert "secret.other" not in json.dumps(method)
    p = publish(project, branch, "P4", {"exhibits": []})
    gid = p["records"]["exhibits"]["generation_id"]
    response = await client.get(f"/api/v1/projects/project.test/branches/{branch}/phases/p4/records/exhibits/{gid}")
    assert response.status_code == 200 and response.json() == []


async def test_missing_or_corrupt_record_is_visible(api):
    client, eng, project, branch = api
    package = seed_theory(project, branch)
    directory = project / "branches" / branch / "phases" / "p3"
    generation_path(directory, "theory_record", package["records"]["theory_record"]).write_text('{"wrong":true}')
    view = (await client.get(f"/api/v1/projects/project.test/artifacts?branch={branch}")).json()
    assert "Digest mismatch" in view["load_errors"][0]["message"]
    assert not view["claim_maps"][0]["authoritative"]


async def test_method_activation_requires_existing_definition_and_tracks_revision(api):
    client, eng, project, branch = api
    base = "/api/v1/projects/project.test"
    rejected = await client.post(base + "/methods", json={"method_id": "made.up", "title": "A convincing card title"})
    assert rejected.status_code == 409
    assert not (project / "branches" / "made.up").exists()
    method = (await client.get(base + "/methods")).json()["methods"][0]
    changed = deepcopy(method["definition"])
    changed["identity"]["version"] += 1
    changed["identity"]["definition_sha256"] = "b" * 64
    changed["lifecycle_state"] = "proposed"
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [changed]}})
    readiness = (await client.get(f"{base}/branches/{branch}/phases/P4/readiness")).json()
    assert not readiness["ready"]
    stale = await client.post(base + "/methods/activate", json={"method_id": method["method_id"], "expected_identity": method["identity"]})
    assert stale.status_code == 409 and "changed" in stale.text
    response = await client.post(base + "/methods/activate", json={"method_id": method["method_id"]})
    assert response.status_code == 200
    assert response.json()["version"] == changed["identity"]["version"]
    assert response.json()["status"] == "active"
    assert read_json(project / "researcher/methods.json")["branches"][branch]["activation"]["authorized_by"] == "researcher"
    assert (await client.get(f"{base}/branches/{branch}/phases/P4/readiness")).json()["ready"]


def test_explicit_activation_is_recorded_even_if_scientific_identity_was_selected(workbench):
    from model_forge_codex.methods import activate_method, get_method
    eng, project, branch = workbench
    before = get_method(project, branch)
    proposal = deepcopy(before["definition"])
    proposal["lifecycle_state"] = "proposed"
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [proposal]}})
    assert get_method(project, branch)["status"] == "proposed"
    activate_method(project, before["method_id"], before["identity"])
    assert get_method(project, branch)["status"] == "active"


async def test_preliminary_without_theory_and_mode_specific_readiness(api):
    client, eng, project, branch = api
    response = await client.get(f"/api/v1/projects/project.test/branches/{branch}/phases/P4/readiness?mode=p4.preliminary")
    assert response.status_code == 200
    modes = {m["mode"]: m for m in response.json()["modes"]}
    assert modes["p4.preliminary"]["ready"]
    assert modes["p4.preliminary"]["label"] == "Feasibility check"
    assert modes["p4.comprehensive"]["label"] == "Detailed evaluation"
    assert modes["p4.preliminary"]["progressive_evaluation"]


async def test_assessment_discussion_remains_linked_to_original_target_after_revision(api):
    client, eng, project, branch = api
    package = seed_theory(project, branch)
    directory = project / "branches" / branch / "phases" / "p3"
    before = current_records(directory)
    eng.bridge.default_behavior = ("ok", {"assessment.json": json.dumps({
        "headline": "Examine independence", "assessment_markdown": "Factorization needs independence.",
        "limitations": ["Dependence not checked"], "suggested_actions": ["Consider mixing conditions"],
        "evidence_refs": [{"family": "theory_record", "generation_id": before["theory_record"]["generation_id"]}],
    })})
    base = "/api/v1/projects/project.test"
    response = await client.post(base + "/runs", json={"phase": "P3", "mode": "p3.assessment", "intent": "assessment",
        "branch_id": branch, "target": target(package, branch), "instructions": "Check this step."})
    assert response.status_code == 200, response.text
    run = response.json()
    await eng._tasks[run["run_id"]]
    assert (await client.get(base + "/runs/" + run["run_id"])).json()["state"] == "assessed"
    aid = run["assessment_id"]
    followup = await client.post(f"{base}/assessments/{aid}/messages", json={"instructions": "Explain the alternatives."})
    assert followup.status_code == 200, followup.text
    await eng._tasks[followup.json()["run_id"]]
    discussion = (await client.get(base + f"/assessments?branch={branch}")).json()["assessments"][0]
    assert len(discussion["messages"]) == 4
    assert discussion["messages"][2]["content"] == "Explain the alternatives."
    assert discussion["evidence_refs"][0]["generation_ref"]["branch"] == branch
    assert (await client.get(discussion["evidence_refs"][0]["source_url"])).status_code == 200
    assert current_records(directory) == before and browse.receipts(project) == []
    seed_theory(project, branch)
    historical = await client.post(f"{base}/assessments/{aid}/messages", json={"instructions": "Continue."})
    assert historical.status_code == 200, historical.text
    await eng._tasks[historical.json()["run_id"]]
    discussion = (await client.get(base + f"/assessments?branch={branch}")).json()["assessments"][0]
    assert discussion["target"]["generation_id"] == before["theory_record"]["generation_id"]


def test_figure_uses_exact_producing_run_not_same_id_in_new_failed_run(workbench):
    eng, project, branch = workbench
    svg = b"<svg>published source</svg>"
    exhibit = {"exhibit_id": "figure.reused", "artifact_path": "figures/result.svg", "artifact_sha256": sha256_bytes(svg), "media_type": "image/svg+xml"}
    for run_id, state, data in (("run.published", "published", svg), ("run.new_failed", "failed", b"wrong new image")):
        run_dir = project / "runs" / run_id
        write_json_atomic(run_dir / "run.json", {"run_id": run_id, "state": state, "phase": "P4", "branch_id": branch})
        stage = run_dir / "outputs" / "p4.analyst"
        write_json_atomic(stage / "exhibits.json", [exhibit])
        (stage / "figures").mkdir()
        (stage / "figures" / "result.svg").write_bytes(data)
    publish(project, branch, "P4", {"exhibits": [exhibit]}, "run.published")
    view = artifacts_view(project, branch)["exhibits"][0]
    assert view["source_verified"] and "/run.published/" in view["artifact_url"]
    (project / "runs/run.published/outputs/p4.analyst/figures/result.svg").write_bytes(b"changed")
    corrupted = artifacts_view(project, branch)["exhibits"][0]
    assert "artifact_url" not in corrupted and "digest" in corrupted["source_error"]


async def test_readable_manuscript_uses_collected_source_and_checks_bytes(api):
    client, eng, project, branch = api
    text = "# Complete proof\n\nThe argument, with $x^2$, remains readable."
    artifact = {"path": "proof.md", "sha256": sha256_bytes(text.encode()), "media_type": "text/markdown"}
    publish(project, branch, "P3", {"theory_record": {"primary_artifact": artifact, "statements": []}}, "run.proof")
    run = project / "runs" / "run.proof"
    write_json_atomic(run / "run.json", {"state": "published", "branch_id": branch, "phase": "P3"})
    source = run / "outputs" / "p3.theorist" / "working" / "theorist" / "proof.md"
    source.parent.mkdir(parents=True)
    source.write_text(text, encoding="utf-8", newline="\n")
    doc = artifacts_view(project, branch)["documents"][0]
    assert doc["body_md"] == text and doc["primary_source_verified"]
    assert (await client.get(doc["primary_artifact_url"])).text == text
    source.write_text("Changed bytes", encoding="utf-8")
    assert (await client.get(doc["primary_artifact_url"])).status_code == 409
    assert artifacts_view(project, branch)["documents"][0]["document_error"]


def test_theory_diff_uses_previous_basis_and_retains_old_empirical_evidence(workbench):
    eng, project, branch = workbench
    old = seed_theory(project, branch)
    oldref = {**old["records"]["theory_record"], "branch": branch, "phase": "P3", "family": "theory_record"}
    write_json_atomic(project / "runs/run.revision/basis.json", {"records": [oldref]})
    basis = eng.compute_basis("project.test", "P4", branch, "p4.preliminary")
    write_json_atomic(project / "runs/run.evaluation/basis.json", basis)
    write_json_atomic(project / "runs/run.evaluation/run.json", {"state": "published", "phase": "P4", "branch_id": branch, "basis_sha256": basis["sha256"]})
    publish(project, branch, "P4", {"protocol": {"claim_tests": [{"test_id": "test.consistency", "target_statement_ids": ["statement.consistency"]}]}}, "run.evaluation")
    publish(project, branch, "P3", {"theory_record": {"method_identity": basis["method"]["identity"], "assumptions": [], "statements": [
        {"statement_id": "statement.consistency", "statement": "Convergence requires mixing."},
        {"statement_id": "statement.rate", "statement": "Rate result", "depends_on_statement_ids": ["statement.consistency"]},
    ]}}, "run.revision")
    view = artifacts_view(project, branch)
    changed = {c["statement_id"]: c for c in view["claim_maps"][0]["revision_changes"]}
    assert changed["statement.consistency"]["before"]["statement"] == "The estimator converges."
    assert "statement.rate" in changed["statement.consistency"]["affected"]
    assert view["evidence_status"][0]["state"] == "affected"
    assert view["protocols"][0]["generation_ref"]["run_id"] == "run.evaluation"


def test_prepared_receipt_is_not_published_until_package_commit(workbench):
    eng, project, branch = workbench
    write_json_atomic(project / "authority/receipts/receipt.orphan.json", {"package_id": "package.orphan", "branch_id": branch, "phase": "P3"})
    assert browse.receipts(project) == []


def test_later_small_evaluation_retains_earlier_case_sources(workbench):
    eng, project, branch = workbench
    first = publish(project, branch, "P4", {"protocol": {"claim_tests": [{"test_id": "test.baseline"}]},
                                            "diagnostics": {"headline_numbers": [{"case_id": "case.baseline", "estimate": 1}]}}, "run.first")
    publish(project, branch, "P4", {"protocol": {"claim_tests": [{"test_id": "test.followup"}]},
                                    "diagnostics": {"headline_numbers": [{"case_id": "case.followup", "estimate": 2}]}}, "run.followup")
    view = artifacts_view(project, branch)
    assert view["protocols"][0]["claim_tests"][0]["test_id"] == "test.followup"
    previous = view["prior_evaluations"][0]["artifacts"]
    assert previous["diagnostics"][0]["headline_numbers"][0]["case_id"] == "case.baseline"
    assert previous["protocols"][0]["generation_ref"]["generation_id"] == first["records"]["protocol"]["generation_id"]
    assert previous["protocols"][0]["generation_ref"]["run_id"] == "run.first"


def test_catalog_upgrade_retains_old_science_and_rejects_tampered_offer(workbench, tmp_path):
    import shutil
    eng, project, branch = workbench
    old = seed_theory(project, branch)
    current_pin = read_json(project / "contracts/catalog-pin.json")
    write_json_atomic(project / "contracts/catalog-pin.json", {**current_pin, "catalog_version": "1.3.0"})
    offer = tmp_path / "offered-catalog"
    shutil.copytree(REPO / "contracts", offer)
    (offer / "schemas/assessment.schema.json").write_text("{}")
    with pytest.raises(ValueError, match="integrity"):
        upgrade_catalog(project, offer)
    assert read_json(project / "contracts/catalog-pin.json")["catalog_version"] == "1.3.0"
    result = upgrade_catalog(project, REPO / "contracts")
    assert result["version"] == read_json(REPO / "contracts/catalog-pin.json")["catalog_version"]
    assert read_json(project / result["previous_catalog"] / "catalog-pin.json")["catalog_version"] == "1.3.0"
    assert current_records(project / "branches" / branch / "phases/p3") == old["records"]


async def test_read_only_preview_rejects_mutation(api, monkeypatch):
    client, eng, project, branch = api
    monkeypatch.setenv("MF_CODEX_READ_ONLY", "1")
    assert (await client.get("/api/v1/projects")).status_code == 200
    assert (await client.post("/api/v1/projects", json={"name": "Unauthorized preview edit"})).status_code == 403
