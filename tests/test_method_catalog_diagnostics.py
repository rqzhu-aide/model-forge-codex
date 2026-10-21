"""Malformed catalog entries shadow honestly; output freshness is derived, never assumed."""
import copy

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.browse import list_runs
from model_forge_codex.domain import RunState
from model_forge_codex.methods import (
    _catalog_methods,
    activate_method,
    branch_output_statuses,
    catalog_diagnostics,
    get_method,
    list_methods,
    output_method_status,
)
from model_forge_codex.research import artifacts_view
from model_forge_codex.service import create_app
from test_method_input_alignment import revise_method
from test_researcher_workbench_engine import publish, script_scientific_run, seed_theory, workbench


def test_malformed_complete_catalog_entry_shadows_the_older_incremental(workbench):
    eng, project, branch = workbench
    method = get_method(project, branch)["definition"]
    stable_id = method["identity"]["stable_id"]
    malformed = copy.deepcopy(method)
    malformed["identity"]["version"] = 0
    publish(project, "trunk", "P2", {
        "method_changes": [method],
        "method_catalog": {"methods": [malformed]},
    }, "run.broken_catalog")
    assert stable_id not in _catalog_methods(project)
    assert get_method(project, branch) is None
    with pytest.raises(ValueError, match="no published P2 definition"):
        activate_method(project, stable_id)
    assert "Select an active registered method" in eng.check_readiness("project.test", "P3", branch, "p3.theory_establishment")
    diagnostics = catalog_diagnostics(project)
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic["stable_id"] == stable_id
    assert diagnostic["shadowed"] is True
    assert diagnostic["source_ref"]["family"] == "method_catalog"
    assert diagnostic["source_ref"]["run_id"] == "run.broken_catalog"
    assert diagnostic["message"] == "Method identity is missing or invalid; applicability cannot be established."


def test_malformed_incremental_never_shadows_the_complete_catalog(workbench):
    eng, project, branch = workbench
    method = get_method(project, branch)["definition"]
    stable_id = method["identity"]["stable_id"]
    malformed = copy.deepcopy(method)
    malformed["identity"]["definition_sha256"] = "not-a-digest"
    publish(project, "trunk", "P2", {
        "method_changes": [malformed],
        "method_catalog": {"methods": [method]},
    }, "run.mixed")
    assert stable_id in _catalog_methods(project)
    assert get_method(project, branch)["aligned"] is True
    diagnostics = catalog_diagnostics(project)
    assert len(diagnostics) == 1
    assert diagnostics[0]["shadowed"] is False
    assert diagnostics[0]["source_ref"]["family"] == "method_changes"


def test_non_string_identity_is_a_diagnostic_not_a_crash(workbench):
    eng, project, branch = workbench
    method = get_method(project, branch)["definition"]
    broken = {"identity": {"stable_id": 123, "version": 1, "definition_sha256": "a" * 64},
              "mathematical_definition": {"canonical_definition": {}}}
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [method, broken]}}, "run.odd")
    stable_id = method["identity"]["stable_id"]
    assert stable_id in _catalog_methods(project)
    diagnostics = catalog_diagnostics(project)
    assert len(diagnostics) == 1
    assert diagnostics[0]["stable_id"] is None
    assert diagnostics[0]["detail"] == "invalid stable_id"


@pytest.mark.asyncio
async def test_methods_endpoint_exposes_diagnostics_and_dependent_outputs(workbench, monkeypatch):
    eng, project, branch = workbench
    seed_theory(project, branch)
    method = get_method(project, branch)["definition"]
    malformed = copy.deepcopy(method)
    malformed["identity"]["version"] = "two"
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [malformed]}}, "run.broken")
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    app = create_app(data_root=eng.data_root, bridge=eng.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = (await client.get("/api/v1/projects/project.test/methods")).json()
    assert payload["methods"] == []
    diagnostic = payload["diagnostics"][0]
    assert diagnostic["stable_id"] == method["identity"]["stable_id"]
    assert diagnostic["detail"] == "invalid version"
    assert diagnostic["shadowed"] is False


def test_output_status_current_needs_update_and_unknown(workbench):
    eng, project, branch = workbench
    seed_theory(project, branch)
    statuses = branch_output_statuses(project, branch)
    assert len(statuses) == 1
    assert statuses[0]["phase"] == "P3"
    assert statuses[0]["status"] == "current"
    assert statuses[0]["identity_source"] == "theory_record"
    identity = revise_method(project, branch)
    statuses = branch_output_statuses(project, branch)
    assert statuses[0]["status"] == "needs_update"
    assert statuses[0]["current_version"] == 2
    assert statuses[0]["current_identity"] == identity
    assert statuses[0]["source_ref"]["family"] == "method_catalog"
    entry = next(m for m in list_methods(project) if m["branch_id"] == branch)
    assert entry["dependent_outputs"][0]["status"] == "needs_update"
    assert output_method_status(project, None)["status"] == "unknown"
    assert output_method_status(project, {"stable_id": "method.absent", "version": 1,
                                          "definition_sha256": "a" * 64})["status"] == "unknown"


def test_editorial_revision_with_unchanged_definition_stays_current(workbench):
    eng, project, branch = workbench
    seed_theory(project, branch)
    method = copy.deepcopy(get_method(project, branch)["definition"])
    method["identity"]["version"] = 2  # definition bytes unchanged
    method["lineage"] = {"change_class": "editorial", "change_summary": "Clarified the wording of the estimator description.",
                         "change_source": {"kind": "research_run", "run_id": "run.editorial"}}
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [method]}}, "run.editorial")
    assert branch_output_statuses(project, branch)[0]["status"] == "current"


def test_artifacts_view_documents_carry_derived_method_status(workbench):
    eng, project, branch = workbench
    seed_theory(project, branch)
    theory = next(d for d in artifacts_view(project)["documents"] if d["kind"] == "theory_record")
    assert theory["method_status"]["status"] == "current"
    revise_method(project, branch)
    theory = next(d for d in artifacts_view(project)["documents"] if d["kind"] == "theory_record")
    assert theory["method_status"]["status"] == "needs_update"
    assert theory["method_status"]["current_version"] == 2


@pytest.mark.asyncio
async def test_list_runs_derives_method_status_without_changing_state(workbench):
    eng, project, branch = workbench
    script_scientific_run(eng, project, branch, "P3", "p3.theory_establishment")
    run = await eng.start_run("project.test", phase="P3", mode="p3.theory_establishment", branch_id=branch)
    await eng._tasks[run.run_id]
    assert eng.load_run("project.test", run.run_id).state is RunState.PUBLISHED
    revise_method(project, branch)
    summary = next(r for r in list_runs(project) if r["run_id"] == run.run_id)
    assert summary["state"] == "published"
    assert summary["method_status"]["status"] == "needs_update"
    assert summary["method_status"]["current_version"] == 2
    trunk_run = next((r for r in list_runs(project) if r["branch_id"] == "trunk"), None)
    assert trunk_run is None or "method_status" not in trunk_run
