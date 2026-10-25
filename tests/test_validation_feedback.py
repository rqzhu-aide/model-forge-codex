"""Large draft checks remain exact on disk and bounded on the member channel."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import RunState
from model_forge_codex.execution import ExecutionSettings
from model_forge_codex.member_tools import MemberToolDispatcher
from model_forge_codex.storage import read_json, read_jsonl
from model_forge_codex.validation_feedback import MAX_FEEDBACK_BYTES, member_validation_feedback
from test_direct_workflow import PID, direct_engine, p1_documents, script


def finding(index, **updates):
    return {"code": f"schema.category_{index % 4}", "object_id": f"p4.output_{index % 2}",
            "message": f"Exact finding {index}", "json_pointer": f"/rows/{index}/value",
            "blocks_publication": index % 3 != 0, **updates}


def report(findings):
    return {"status": "failed", "checked_outputs": ["p4.output_0", "p4.output_1"],
            "findings": findings, "deferred_checks": ["Scientific validity is not assessed."],
            "scientific_correctness": "not_assessed"}


def directories(tmp_path):
    workspace, archive = tmp_path / "workspace", tmp_path / "execution"
    workspace.mkdir()
    archive.mkdir()
    return workspace, archive


def bound(document, workspace, archive, execution=None):
    result = member_validation_feedback(document, workspace=workspace, report_dir=archive, execution=execution)
    wire = MemberToolDispatcher._result(result, success=True, execution=execution)["contentItems"][0]["text"]
    assert len(wire.encode("utf-8")) <= MAX_FEEDBACK_BYTES
    return result


def test_small_report_is_unchanged_and_creates_no_copies(tmp_path):
    workspace, archive = directories(tmp_path)
    document = report([finding(0)])
    assert bound(document, workspace, archive) is document
    assert not list(workspace.iterdir()) and not list(archive.iterdir())


def test_large_report_preserves_every_finding_and_counts_all_categories(tmp_path):
    workspace, archive = directories(tmp_path)
    source = workspace / "authored.json"
    source.write_bytes(b'{ "scientific_source": "must stay exact" }\r\n')
    source_bytes = source.read_bytes()
    document = report([finding(index) for index in range(8215)])
    original = deepcopy(document)
    result = bound(document, workspace, archive)
    assert document == original and source.read_bytes() == source_bytes
    summary = result["finding_summary"]
    assert result["status"] == "failed" and result["findings_truncated"] is True
    assert summary["total"] == 8215
    assert summary["blocking"] == sum(item["blocks_publication"] for item in document["findings"])
    assert summary["nonblocking"] + summary["blocking"] == summary["total"]
    assert summary["returned"] == len(result["findings"]) <= 24
    assert summary["returned"] + summary["omitted"] == 8215
    assert summary["category_count"] == summary["categories_returned"] == 4
    assert summary["categories_omitted"] == 0
    assert sum(category["count"] for category in summary["categories"]) == 8215
    assert sum(category["blocking"] for category in summary["categories"]) == summary["blocking"]
    for category in summary["categories"]:
        matching = [item for item in document["findings"]
                    if item["code"] == category["code"] and item["object_id"] == category["object_id"]]
        assert category["count"] == len(matching)
        assert matching[0] in result["findings"]
    assert all(item in document["findings"] for item in result["findings"])
    saved = Path(result["full_report"]["path"])
    assert saved.parent == workspace.resolve()
    assert json.loads(saved.read_bytes()) == document
    assert hashlib.sha256(saved.read_bytes()).hexdigest() == result["full_report"]["sha256"]
    assert saved.stat().st_size == result["full_report"]["bytes"]
    assert next(archive.iterdir()).read_bytes() == saved.read_bytes()
    second = bound(document, workspace, archive)
    assert second["full_report"]["path"] != str(saved)
    assert len(list(archive.iterdir())) == 2


def test_single_huge_utf8_finding_is_retained_exactly_and_recovery_survives(tmp_path):
    workspace, archive = directories(tmp_path)
    document = report([finding(0, message="研究" * 100000), finding(1)])
    document["recovery"] = {"code": "artifact_check.unchanged_failure", "stop_requested": True,
                            "unchanged": True, "message": "Stop and retain findings for repair."}
    result = bound(document, workspace, archive)
    assert result["recovery"] == document["recovery"]
    assert result["findings"] == [finding(1)]
    assert result["finding_summary"]["total"] == 2
    assert result["finding_summary"]["omitted"] == 1
    assert json.loads(Path(result["full_report"]["path"]).read_bytes()) == document


def test_large_category_metadata_reports_omissions_explicitly(tmp_path):
    workspace, archive = directories(tmp_path)
    document = report([finding(index, code=f"schema.unique_{index}", object_id="long." + "x" * 200)
                       for index in range(500)])
    document["deferred_checks"] = ["unexpectedly huge metadata " * 10000]
    result = bound(document, workspace, archive)
    summary = result["finding_summary"]
    assert 0 < summary["categories_returned"] < summary["category_count"] == 500
    assert summary["categories_returned"] + summary["categories_omitted"] == 500
    assert "deferred_checks" in result["omitted_report_fields"]
    assert json.loads(Path(result["full_report"]["path"]).read_bytes()) == document


def test_member_copy_uses_existing_credential_redaction_boundary(tmp_path):
    workspace, archive = directories(tmp_path)
    execution = ExecutionSettings({}, {"TEST_KEY": "synthetic-test-secret"})
    document = report([finding(0, message="synthetic-test-secret " * 2000)])
    result = bound(document, workspace, archive, execution)
    member_bytes = Path(result["full_report"]["path"]).read_bytes()
    assert b"synthetic-test-secret" not in member_bytes
    assert result["full_report"]["credentials_redacted"] is True
    assert hashlib.sha256(member_bytes).hexdigest() == result["full_report"]["sha256"]
    assert json.loads(next(archive.iterdir()).read_bytes()) == document


async def test_engine_uses_full_findings_for_recovery_and_events_before_bounding(direct_engine, monkeypatch):
    engine, _ = direct_engine
    documents = p1_documents()
    reports, states = [], []
    original_validate = engine.validate_member_artifacts
    original_state = engine._artifact_check_state

    def validate(*args, **kwargs):
        checked = original_validate(*args, **kwargs)
        if checked["status"] == "failed" and checked["checked_outputs"] == ["p1.lead_literature"]:
            checked["findings"] = [finding(index, object_id="p1.lead_literature") for index in range(8215)]
        return checked

    def state(*args, **kwargs):
        value = original_state(*args, **kwargs)
        states.append(value)
        return value

    class RecheckingBridge(FakeCodexBridge):
        async def run_turn(self, thread_id, *, validate_artifacts=None, **kwargs):
            if self.threads[thread_id]["key"] == "research_lead:PROJECT:trunk" and kwargs["workspace"].name == "p1.discovery":
                workspace = kwargs["workspace"]
                broken = deepcopy(documents["p1.lead_literature"])
                broken.pop("title")
                path = workspace / "lead_literature.json"
                path.write_text(json.dumps(broken), encoding="utf-8")
                before = path.read_bytes()
                reports.extend([validate_artifacts(), validate_artifacts()])
                assert path.read_bytes() == before
            return await super().run_turn(thread_id, validate_artifacts=validate_artifacts, **kwargs)

    monkeypatch.setattr(engine, "validate_member_artifacts", validate)
    monkeypatch.setattr(engine, "_artifact_check_state", state)
    engine.bridge = RecheckingBridge()
    script(engine, "P1", "p1.literature_update", documents)
    run = await engine.start_run(PID, phase="P1", mode="p1.literature_update", branch_id="trunk")
    await engine._tasks[run.run_id]
    final = engine.load_run(PID, run.run_id)
    assert final.state is RunState.PUBLISHED, final.terminal_reason
    assert len(reports) == 2 and all(len(item["findings"]) < 8215 for item in reports)
    assert len(states[0]["findings"]) == 8215 and states[0] == states[1]
    assert not reports[0].get("recovery")
    assert reports[1]["recovery"]["stop_requested"] is True
    assert read_json(Path(reports[1]["full_report"]["path"]))["recovery"] == reports[1]["recovery"]
    directory = engine.run_dir(PID, run.run_id)
    events, invalid_rows = read_jsonl(directory / "events.jsonl")
    assert invalid_rows == 0
    checks = [event for event in events if event.get("type") == "member.artifact_check"]
    assert [event["finding_count"] for event in checks] == [8215, 8215]
    archived = list((directory / "execution").glob("*/validation-report.*.json"))
    assert len(archived) == 2 and all(len(read_json(path)["findings"]) == 8215 for path in archived)
