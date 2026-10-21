"""Work receipts and delivery acceptance remain distinct across reloads."""
import copy

import pytest

from model_forge_codex.browse import list_runs
from model_forge_codex.run_progress import project_run_progress
from model_forge_codex.storage import read_json, write_json_atomic


ROLES = ["research_lead", "theorist", "data_analyst"]
DISCOVERY = {"stage_id": "p1.discovery", "sequence": 1, "execution": "parallel", "roles": ROLES,
             "writes": ["p1.lead_literature", "p1.theory_literature", "p1.empirical_literature"]}


def saved_run(directory, *, state="running", stage_state="running"):
    run = {"run_id": directory.name, "phase": "P1", "mode": "p1.literature_update", "branch_id": "trunk",
           "state": state, "stage_states": {"p1.discovery": stage_state, "p1.lead_synthesis": "pending"}}
    write_json_atomic(directory / "run.json", run)
    write_json_atomic(directory / "stage-plan.json", [DISCOVERY, {"stage_id": "p1.lead_synthesis", "sequence": 2,
        "execution": "serial", "roles": ["research_lead"], "writes": ["p1.research_basis"]}])
    return run


def execution(directory, role, *, purpose="scientific", state="completed", start="2026-09-30T10:00:00Z", finish="2026-09-30T10:01:00Z", suffix="first"):
    document = {"execution_id": f"execution.{role}.{suffix}", "stage_id": "p1.discovery", "role": role,
                "purpose": purpose, "state": state, "started_at": start,
                "submitted": {"private": "NOT_FOR_PROGRESS"}, "workspace": "PRIVATE_PATH"}
    if state != "running":
        document["finished_at"] = finish
    write_json_atomic(directory / "execution" / document["execution_id"] / "execution.json", document)


def seal(directory, role, *, when="2026-09-30T10:01:01Z"):
    doc = {"stage_id": "p1.discovery", "role": role, "sealed_at": when,
           "outputs": {role + ".json": {"sha256": "a" * 64}}}
    write_json_atomic(directory / "outputs/p1.discovery/seals" / f"{role}.json", doc)
    return doc


def discovery(directory, run):
    return project_run_progress(directory, run)["stages"][0]


def test_completed_model_turn_requires_collected_account_and_acceptance(tmp_path):
    run = saved_run(tmp_path)
    execution(tmp_path, "research_lead")
    first = discovery(tmp_path, run)
    assert first["received_accounts"] == 0
    assert first["members"][0]["state"] == "collecting"
    seal(tmp_path, "research_lead")
    received = discovery(tmp_path, read_json(tmp_path / "run.json"))
    assert received["received_accounts"] == 1
    assert received["members"][0]["state"] == "received"
    assert not received["members"][0]["accepted"]
    assert received["state"] == "running"
    for role in ROLES[1:]:
        execution(tmp_path, role)
        seal(tmp_path, role)
    run["stage_states"]["p1.discovery"] = "succeeded"
    accepted = discovery(tmp_path, run)
    assert accepted["received_accounts"] == accepted["total_accounts"] == 3
    assert all(member["accepted"] for member in accepted["members"])


def test_member_repair_reopens_only_affected_account_and_ignores_handoff(tmp_path):
    run = saved_run(tmp_path)
    for role in ROLES:
        execution(tmp_path, role)
        seal(tmp_path, role)
    execution(tmp_path, "research_lead", purpose="handoff", state="running", start="2026-09-30T10:02:00Z", suffix="rotation")
    execution(tmp_path, "theorist", purpose="connection_probe", state="completed", start="2026-09-30T10:02:00Z", suffix="probe")
    assert discovery(tmp_path, run)["received_accounts"] == 3
    run["stage_states"]["p1.discovery"] = "correcting"
    execution(tmp_path, "theorist", purpose="mechanical_repair", state="running", start="2026-09-30T10:03:00Z", suffix="repair")
    reopened = discovery(tmp_path, run)
    assert reopened["received_accounts"] == 2
    assert next(member for member in reopened["members"] if member["role"] == "theorist")["state"] == "correcting"
    execution(tmp_path, "theorist", purpose="mechanical_repair", start="2026-09-30T10:03:00Z", finish="2026-09-30T10:04:00Z", suffix="repair")
    assert discovery(tmp_path, run)["received_accounts"] == 2
    seal(tmp_path, "theorist", when="2026-09-30T10:04:01Z")
    assert discovery(tmp_path, run)["received_accounts"] == 3
    assert not any(member["accepted"] for member in discovery(tmp_path, run)["members"])


def test_saved_repair_reopens_owner_before_the_next_execution_record(tmp_path):
    run = saved_run(tmp_path, stage_state="correcting")
    for role in ROLES:
        execution(tmp_path, role)
        original = seal(tmp_path, role)
        write_json_atomic(tmp_path / "mechanical-repairs/p1.discovery/attempt-1/outputs/seals" / f"{role}.json", original)
    run["mechanical_repair_attempts"] = {"p1.discovery": 1}
    write_json_atomic(tmp_path / "mechanical-repairs/p1.discovery/attempt-1/findings.json", {"scope": ["p1.theory_literature"]})
    progress = discovery(tmp_path, run)
    assert progress["received_accounts"] == 2
    assert progress["members"][1]["state"] == "correcting"
    seal(tmp_path, "theorist", when="2026-09-30T10:05:00Z")
    assert discovery(tmp_path, run)["received_accounts"] == 3


def test_historical_stage_state_has_no_inferred_member_counts(tmp_path):
    run = saved_run(tmp_path, state="published", stage_state="succeeded")
    progress = project_run_progress(tmp_path, run)
    assert progress["stages"][0]["state"] == "succeeded"
    assert progress["stages"][0]["received_accounts"] is None
    assert progress["stages"][0]["members"] == []
    assert progress["publication"]["state"] == "completed"
    (tmp_path / "stage-plan.json").unlink()
    legacy = project_run_progress(tmp_path, run)
    assert legacy["stages"][0]["state"] == "succeeded"
    assert legacy["stages"][0]["total_accounts"] is None


@pytest.mark.parametrize("state", ["running", "published"])
@pytest.mark.parametrize("missing", ["executions_and_seals", "seals"])
def test_accepted_stage_with_partial_receipt_history_has_no_misleading_counts(tmp_path, state, missing):
    run = saved_run(tmp_path, state=state, stage_state="succeeded")
    execution(tmp_path, "research_lead")
    seal(tmp_path, "research_lead")
    if missing == "seals":
        for role in ROLES[1:]:
            execution(tmp_path, role)
    before = (tmp_path / "run.json").read_bytes()
    progress = discovery(tmp_path, read_json(tmp_path / "run.json"))
    assert progress["state"] == "succeeded"
    assert progress["received_accounts"] is None
    assert progress["total_accounts"] == 3
    assert not progress["member_detail_available"]
    assert progress["members"] == []
    assert (tmp_path / "run.json").read_bytes() == before
    assert not (tmp_path / "progress.json").exists()


def test_repair_status_uses_saved_outcome_and_survives_reload(tmp_path):
    run = saved_run(tmp_path, stage_state="correcting")
    run["mechanical_repair_attempts"] = {"p1.discovery": 1}
    active = discovery(tmp_path, run)["repair"]
    assert active["state"] == "working" and "attempt 1" in active["message"]
    run.update(state="failed", stage_states={"p1.discovery": "failed"})
    write_json_atomic(tmp_path / "run.json", run)
    write_json_atomic(tmp_path / "mechanical-repairs/p1.discovery/attempt-1/result.json",
                      {"attempt": 1, "unchanged": True, "remaining_findings": [{"code": "schema.required"}]})
    stopped = discovery(tmp_path, read_json(tmp_path / "run.json"))["repair"]
    assert stopped["state"] == "stopped" and "same issue remained" in stopped["message"]
    assert "/" not in stopped["message"] and "schema.required" not in stopped["message"]
    run.update(state="correcting", stage_states={"p1.discovery": "correcting"}, correction_attempts=1)
    assert "repair" not in discovery(tmp_path, run)


def test_browse_progress_does_not_depend_on_events_or_disclose_provider_settings(tmp_path):
    directory = tmp_path / "runs/run.progress"
    run = saved_run(directory, state="failed", stage_state="failed")
    execution(directory, "research_lead")
    seal(directory, "research_lead")
    before = copy.deepcopy(read_json(directory / "run.json"))
    summary = list_runs(tmp_path)[0]
    assert summary["progress"]["stages"][0]["received_accounts"] == 1
    assert summary["progress"]["stages"][0]["state"] == "failed"
    assert "PRIVATE_PATH" not in str(summary) and "NOT_FOR_PROGRESS" not in str(summary)
    assert read_json(directory / "run.json") == before == run
    assert not (directory / "progress.json").exists()


@pytest.mark.parametrize("phase,mode,stage_ids,labels,publication", [
    ("P1", "p1.literature_update", ["p1.discovery", "p1.lead_synthesis"], ["Member literature searches", "Lead synthesis"], "Literature update published"),
    ("P2", "p2.researcher_proposal", ["p2.supplied_method_proposals", "p2.supplied_method_reviews", "p2.supplied_method_reconciliation"], ["Three method proposals", "Specialist cross-reviews", "Lead comparison"], "Methods published"),
    ("P3", "p3.theory_revision", ["p3.theorist", "p3.analyst", "p3.lead"], ["Theory development", "Analyst audit", "Lead synthesis"], "Theory account published"),
    ("P4", "p4.preliminary", ["p4.analyst", "p4.theorist", "p4.lead"], ["Protocol and empirical work", "Theorist audit", "Lead interpretation"], "Evaluation published"),
    ("P5", "p5.assembly", ["p5.assembly_lead"], ["Technical report assembly"], "Technical report published"),
    ("P5", "p5.review_revision", ["p5.parallel_reviews", "p5.revision_lead"], ["Independent report reviews", "Lead revision"], "Technical report published"),
])
def test_phase_and_mode_stages_remain_named(tmp_path, phase, mode, stage_ids, labels, publication):
    write_json_atomic(tmp_path / "stage-plan.json", [{"stage_id": stage_id, "sequence": index} for index, stage_id in enumerate(stage_ids)])
    progress = project_run_progress(tmp_path, {"phase": phase, "mode": mode, "state": "validating"})
    assert [stage["label"] for stage in progress["stages"]] == labels
    assert progress["publication"] == {"label": publication, "state": "checking"}


@pytest.mark.parametrize("relative,document", [
    ("stage-plan.json", [{**DISCOVERY, "sequence": "first"}]),
    ("stage-plan.json", [{**DISCOVERY, "roles": None}]),
    ("stage-plan.json", [{**DISCOVERY, "roles": "research_lead"}]),
    ("stage-plan.json", [{**DISCOVERY, "writes": None}]),
    ("execution/broken/execution.json", ["unreadable execution"]),
    ("execution/broken/execution.json", {"purpose": ["scientific"]}),
    ("execution/broken/execution.json", {"purpose": "scientific", "stage_id": "p1.discovery", "role": "theorist", "state": {"running": True}}),
    ("outputs/p1.discovery/seals/theorist.json", ["unreadable seal"]),
    ("outputs/p1.discovery/seals/theorist.json", {"stage_id": "p1.discovery", "role": "theorist", "outputs": ["theory_literature.json"]}),
    ("mechanical-repairs/p1.discovery/attempt-1/findings.json", {"scope": ["p1.theory_literature", {}]}),
    ("mechanical-repairs/p1.discovery/attempt-1/outputs/seals/theorist.json", ["unreadable prior seal"]),
    ("stage-plan.json", b"\xff\xfe\xfd"),
    ("execution/broken/execution.json", b"\xff\xfe\xfd"),
    ("outputs/p1.discovery/seals/theorist.json", b"\xff\xfe\xfd"),
])
def test_malformed_optional_metadata_keeps_project_runs_readable_with_unknown_counts(tmp_path, relative, document):
    directory = tmp_path / "runs/run.historical"
    run = saved_run(directory, stage_state="correcting")
    run["mechanical_repair_attempts"] = {"p1.discovery": 1}
    write_json_atomic(directory / "run.json", run)
    for role in ROLES:
        execution(directory, role)
        original = seal(directory, role)
        write_json_atomic(directory / "mechanical-repairs/p1.discovery/attempt-1/outputs/seals" / f"{role}.json", original)
    write_json_atomic(directory / "mechanical-repairs/p1.discovery/attempt-1/findings.json", {"scope": ["p1.theory_literature"]})
    path = directory / relative
    if isinstance(document, bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(document)
    else:
        write_json_atomic(path, document)
    before = (directory / "run.json").read_bytes()
    summary = list_runs(tmp_path)[0]
    progress = summary["progress"]
    assert summary["state"] == progress["state"] == "running"
    assert {stage["stage_id"]: stage["state"] for stage in progress["stages"]} == run["stage_states"]
    recorded = next(stage for stage in progress["stages"] if stage["stage_id"] == "p1.discovery")
    assert recorded["received_accounts"] is None
    assert not recorded["member_detail_available"]
    assert recorded["members"] == []
    assert (directory / "run.json").read_bytes() == before
    assert not (directory / "progress.json").exists()
