"""A corrected report's delivery status uses its exact publication, not old prose."""
from copy import deepcopy
import hashlib
import json

import pytest

from model_forge_codex import browse
from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import RunRecord, RunState
from model_forge_codex.phase_interactions import published_issues
from model_forge_codex.records import generation_path
from model_forge_codex.report_delivery import delivery_display, project_run_terminal_reason, report_delivery_state
from model_forge_codex.research import current_decisions_view, scientific_document_view, source_ref
from model_forge_codex.technical_reports import CONTENT_SECTIONS
from test_researcher_workbench_api import api
from test_researcher_workbench_engine import publish, scientific_output_documents, workbench


OLD_REASON = "A retained source link has no portable target."
PORTABLE_ISSUE = {"issue_id": "issue.report.portable-source-link", "category": "reproducibility",
                  "statement": OLD_REASON, "consequence": "Repair the source link before publication."}
SCIENCE_ISSUE = {"issue_id": "issue.science.runtime", "category": "reproducibility",
                 "statement": "An achieved numerical tolerance was not retained.",
                 "consequence": "Its mathematical error bound remains unverified."}


def stale_companions():
    return {
        "decision": {"phase": "P5", "current_conclusion": "The claim remains conditional.",
                     "scientific_outcome": {"state": "partially_supported"},
                     "delivery_status": OLD_REASON,
                     "available_actions": [{"label": "Review the exact report",
                                             "consequence": "Repair delivery, then review the scientific argument."}]},
        "assembly_report": {"unresolved_issues": [deepcopy(PORTABLE_ISSUE), deepcopy(SCIENCE_ISSUE)],
                            "required_checks": ["Repair delivery before publication.", "Independently review the exact report."]},
        "citation_integrity_report": {"issues": [deepcopy(PORTABLE_ISSUE), deepcopy(SCIENCE_ISSUE)],
                                      "portable_export_check": {"status": "failed", "code": "report.portable_unresolved",
                                                                "blocks_publication": True, "message": OLD_REASON}},
    }


def corrected_publication(engine, project, branch, run_id="run.corrected"):
    documents = {"technical_report": {"title": "Qualified report", "claims": [], "completion": {"status": "interim"}},
                 **stale_companions()}
    package = publish(project, branch, "P5", documents, run_id)
    record = RunRecord(run_id, project.name, "P5", "p5.assembly", branch, state=RunState.PUBLISHED,
                       correction_attempts=1, terminal_reason=OLD_REASON,
                       stage_states={"p5.assembly_lead": "succeeded"},
                       findings_history=[[{"code": "report.portable_unresolved", "message": OLD_REASON, "blocks_publication": True}], []])
    engine._save_run(record)
    return package, documents


def test_exact_published_correction_projects_only_bound_delivery_issue(workbench):
    engine, project, branch = workbench
    package, documents = corrected_publication(engine, project, branch)
    phase_dir = project / "branches" / branch / "phases" / "p5"
    before = {family: generation_path(phase_dir, family, pointer).read_bytes() for family, pointer in package["records"].items()}
    reference = source_ref(branch, "P5", "assembly_report", package["records"]["assembly_report"])
    state = report_delivery_state(project, reference)
    assert state["publication"] == "published" and state["validation"] == "passed"
    assert state["passed_delivery_issue_ids"] == [PORTABLE_ISSUE["issue_id"]]
    assert state["report_ref"]["generation_id"] == package["records"]["technical_report"]["generation_id"]
    for family in stale_companions():
        pointer = package["records"][family]
        view = scientific_document_view(project, branch, "P5", family, pointer["generation_id"])
        assert view["structured"] == documents[family]
        assert view["delivery_state"] == state
        if family in {"assembly_report", "citation_integrity_report"}:
            field = "unresolved_issues" if family == "assembly_report" else "issues"
            assert view["display_structured"][field] == [SCIENCE_ISSUE]
            assert view["delivery_history"] == [PORTABLE_ISSUE]
        if family == "assembly_report":
            assert view["display_structured"]["recorded_checks"] == documents[family]["required_checks"]
            assert "Independently review the exact report." in view["display_structured"]["recorded_checks"]
    decision = next(item for item in current_decisions_view(project) if item["phase"] == "P5")
    assert decision["delivery_status"] == state["message"]
    assert decision["authored_delivery_status"] == OLD_REASON
    assert decision["current_conclusion"] == documents["decision"]["current_conclusion"]
    assert decision["available_actions"] == documents["decision"]["available_actions"]
    issues = {item["object_id"]: item for item in published_issues(project, branch) if item["phase"] == "P5"}
    assert "disposition" not in issues[PORTABLE_ISSUE["issue_id"]]
    assert issues[PORTABLE_ISSUE["issue_id"]]["title"] == "Export check passed"
    assert issues[PORTABLE_ISSUE["issue_id"]]["statement"] == OLD_REASON
    assert "disposition" not in issues[SCIENCE_ISSUE["issue_id"]]
    assert {family: generation_path(phase_dir, family, pointer).read_bytes() for family, pointer in package["records"].items()} == before


def test_delivery_does_not_borrow_newer_or_other_branch_success(workbench):
    engine, project, branch = workbench
    old, _ = corrected_publication(engine, project, branch)
    old_ref = source_ref(branch, "P5", "decision", old["records"]["decision"])
    newer, _ = corrected_publication(engine, project, branch, "run.newer")
    state = report_delivery_state(project, old_ref)
    assert state["report_ref"]["package_id"] == old["package_id"]
    assert state["report_ref"]["generation_id"] != newer["records"]["technical_report"]["generation_id"]
    assert not state["is_current_report"]
    assert report_delivery_state(project, {**old_ref, "branch": "method.other"}) is None
    assert report_delivery_state(project, {**old_ref, "sha256": "0" * 64}) is None
    assert report_delivery_state(project, {**old_ref, "package_id": newer["package_id"]}) is None
    run = engine.load_run(project.name, "run.corrected")
    run.state, run.terminal_reason = RunState.FAILED, "Correction still fails."
    engine._save_run(run)
    assert report_delivery_state(project, old_ref) is None


def test_unrelated_issue_needs_explicit_delivery_binding(workbench):
    engine, project, branch = workbench
    package, _ = corrected_publication(engine, project, branch)
    state = report_delivery_state(project, source_ref(branch, "P5", "decision", package["records"]["decision"]))
    document = {"issues": [SCIENCE_ISSUE], "required_checks": ["Check the numerical error bound."]}
    display, history = delivery_display(document, state)
    assert display == document and history == []


def test_mixed_issue_keeps_complete_scientific_content_and_open_state(workbench):
    engine, project, branch = workbench
    documents = stale_companions()
    mixed = {**PORTABLE_ISSUE, "scientific_consequence": "The numerical error bound remains unverified."}
    documents["citation_integrity_report"]["issues"][0] = mixed
    corrected_publication(engine, project, branch)
    package = publish(project, branch, "P5", {"technical_report": {"title": "Report"}, **documents}, "run.mixed")
    run = engine.load_run(project.name, "run.corrected")
    run.run_id = "run.mixed"
    engine._save_run(run)
    reference = source_ref(branch, "P5", "citation_integrity_report", package["records"]["citation_integrity_report"])
    state = report_delivery_state(project, reference)
    display, history = delivery_display(documents["citation_integrity_report"], state)
    assert history == [mixed]
    assert display["issues"] == [SCIENCE_ISSUE]
    issue = next(item for item in published_issues(project, branch) if item["object_id"] == mixed["issue_id"])
    assert issue["scientific_consequence"] == mixed["scientific_consequence"]
    assert not issue.get("disposition")
    assert issue["delivery_state"]["portable_export_check"] == "passed"


@pytest.mark.parametrize("changes", [
    {"phase": "P4"}, {"correction_attempts": 0}, {"state": "failed"}, {"state": "assessed"},
    {"terminal_reason": "publication_recovered_after_restart"},
    {"terminal_reason": "assessment_recovered_after_restart"},
    {"terminal_reason": "A distinct operational note."},
])
def test_non_failure_reasons_and_unrelated_runs_are_unchanged(changes):
    original = {"phase": "P5", "state": "published", "correction_attempts": 1, "terminal_reason": OLD_REASON,
                "findings_history": [[{"message": OLD_REASON, "blocks_publication": True}], []], **changes}
    assert project_run_terminal_reason(original) == original


async def test_old_published_run_api_exposes_current_reason_and_immutable_history(api):
    client, engine, project, branch = api
    package, documents = corrected_publication(engine, project, branch)
    run_file = project / "runs/run.corrected/run.json"
    before = run_file.read_bytes()
    base = f"/api/v1/projects/{project.name}"
    for _ in range(2):
        result = await client.get(base + "/runs/run.corrected")
        assert result.status_code == 200
        assert result.json()["terminal_reason"] is None
        assert result.json()["recorded_terminal_reason"] == OLD_REASON
        summary = next(item for item in browse.list_runs(project) if item["run_id"] == "run.corrected")
        assert summary["terminal_reason"] is None and summary["recorded_terminal_reason"] == OLD_REASON
        pointer = package["records"]["citation_integrity_report"]
        url = base + f"/branches/{branch}/phases/P5/records/citation_integrity_report/{pointer['generation_id']}"
        raw = await client.get(url)
        assert raw.json() == documents["citation_integrity_report"]
        projected = await client.get(url + "?view=document")
        assert projected.json()["delivery_state"]["publication"] == "published"
        assert projected.json()["display_structured"]["portable_export_check"]["blocks_publication"] is False
    assert run_file.read_bytes() == before


def assembly_outputs(engine, project, branch):
    from model_forge_codex.methods import get_method
    from model_forge_codex.problem_context import initialize_problem_context
    initialize_problem_context(project)
    documents, files = scientific_output_documents(Catalog(project / "contracts"), "P5", get_method(project, branch)["identity"])
    basis = engine.compute_basis(project.name, "P5", branch, "p5.assembly")
    report = documents["p5.technical_report_candidate"]
    report["problem_context_ref"] = {key: basis["problem_context"][key] for key in ("revision", "sha256")}
    source = "\n\n".join(f'<a id="{key}"></a>\n## {key.replace("_", " ").capitalize()}\n\n'
        + ("No numerical analysis is available. This report is interim." if key == "numerical_analysis" else
           "The selected exact model and unknown collection conditions remain explicit. $x^2$.") for key in CONTENT_SECTIONS)
    source += f'\n\n<a id="{report["section_anchors"]["references"]}"></a>\n## References\n\nNo external sources are cited in this synthetic interim report.\n'
    pointer = report["report_artifact"]
    files[pointer["path"]] = source
    pointer["sha256"] = hashlib.sha256(source.encode()).hexdigest()
    report["representations"] = [{"information_layer": "primary_artifact", "artifact": deepcopy(pointer)}]
    report["basis"] = []
    documents["p5.claim_traceability"], documents["p5.attention_items"] = [], []
    documents["p5.decision"].update(headline="Interim report", current_conclusion="Relevant numerical analysis remains unavailable.", strongest_evidence_ids=[])
    documents["p5.decision"]["scientific_outcome"].update(strongest_evidence_ids=[], strongest_counterevidence_ids=[])
    return documents, files


@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_p5_normal_correction_clears_only_previous_failure(workbench, repair_succeeds):
    engine, project, branch = workbench
    engine._MAX_MECHANICAL_REPAIRS = 0
    documents, files = assembly_outputs(engine, project, branch)
    good = deepcopy(documents["p5.technical_report_candidate"])
    documents["p5.technical_report_candidate"].pop("title")
    stage = engine.stage_plan(project.name, "P5", "p5.assembly")[0]
    writes = {**files, **{output.split(".", 1)[1] + ".json": json.dumps(documents[output]) for output in stage.writes}}
    engine.bridge.script_thread("research_lead:PROJECT:trunk", [("ok", writes)])
    run = await engine.start_run(project.name, phase="P5", mode="p5.assembly", branch_id=branch)
    await engine._tasks[run.run_id]
    failed = engine.load_run(project.name, run.run_id)
    assert failed.state is RunState.FAILED and failed.terminal_reason
    original_bytes = (engine.run_dir(project.name, run.run_id) / "outputs" / stage.stage_id / "technical_report_candidate.json").read_bytes()
    prior_reason, history = failed.terminal_reason, deepcopy(failed.findings_history)
    response = good if repair_succeeds else documents["p5.technical_report_candidate"]
    engine.bridge.script_thread("research_lead:PROJECT:trunk", [("ok", {"technical_report_candidate.json": json.dumps(response)})])
    correcting = await engine.correct(project.name, run.run_id, "Restore only the missing report title.")
    assert correcting.state is RunState.CORRECTING and correcting.terminal_reason is None
    await engine._tasks[run.run_id]
    final = engine.load_run(project.name, run.run_id)
    assert final.state is (RunState.PUBLISHED if repair_succeeds else RunState.FAILED), (final.terminal_reason, final.findings_history)
    assert final.terminal_reason is None if repair_succeeds else bool(final.terminal_reason)
    assert final.findings_history[:len(history)] == history
    events, _ = engine.run_events(project.name, run.run_id)
    assert next(event for event in events if event["type"] == "run.correcting")["previous_reason"] == prior_reason
    archived = engine.run_dir(project.name, run.run_id) / "attempts/original/outputs" / stage.stage_id / "technical_report_candidate.json"
    assert archived.read_bytes() == original_bytes
