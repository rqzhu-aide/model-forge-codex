"""Members get live draft feedback; invalid handoffs never reach consumers."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import RunState
from model_forge_codex.storage import read_json, sha256_file
from test_direct_workflow import PID, SEED, complete, direct_engine, p1_documents, p2_documents, script
from test_researcher_workbench_engine import (workbench, script_scientific_run, seed_manuscript_context)


LEAD = "research_lead:PROJECT:trunk"


def response(**documents):
    return "ok", {name + ".json": json.dumps(value) for name, value in documents.items()}


async def finish(engine):
    run = await engine.start_run(PID, phase="P1", mode="p1.literature_update", branch_id="trunk")
    await engine._tasks[run.run_id]
    return engine.load_run(PID, run.run_id)


async def test_member_checks_draft_and_repairs_before_ending_its_turn(direct_engine):
    engine, _ = direct_engine
    documents = p1_documents()
    reports = []

    class CheckingBridge(FakeCodexBridge):
        async def run_turn(self, thread_id, *, validate_artifacts=None, **kwargs):
            if self.threads[thread_id]["key"] == LEAD and kwargs["workspace"].name == "p1.discovery":
                workspace = kwargs["workspace"]
                workspace.mkdir(parents=True, exist_ok=True)
                target = workspace / "lead_literature.json"
                target.write_text("{invalid", encoding="utf-8")
                reports.append(validate_artifacts())
                target.write_text(json.dumps(documents["p1.lead_literature"]), encoding="utf-8")
                reports.append(validate_artifacts())
            return await super().run_turn(thread_id, validate_artifacts=validate_artifacts, **kwargs)

    engine.bridge = CheckingBridge()
    script(engine, "P1", "p1.literature_update", documents)
    final = await finish(engine)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert [r["status"] for r in reports] == ["failed", "passed"]
    assert reports[0]["checked_outputs"] == ["p1.lead_literature"]
    assert reports[1]["scientific_correctness"] == "not_assessed"
    assert reports[1]["deferred_checks"]
    assert final.mechanical_repair_attempts == {} and final.correction_attempts == 0
    assert len(engine.bridge.turns) == 4


@pytest.mark.parametrize("with_seed", [False, True])
async def test_p2_review_callback_checks_original_stage_and_accepts_author_repair(direct_engine, with_seed):
    engine, _ = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    reports = {}

    class CheckingBridge(FakeCodexBridge):
        async def run_turn(self, thread_id, *, validate_artifacts=None, **kwargs):
            result = await super().run_turn(thread_id, validate_artifacts=validate_artifacts, **kwargs)
            workspace = kwargs["workspace"]
            if workspace.name in {"p2.cross_review", "p2.supplied_method_reviews"}:
                target = next(workspace.glob("*_review.json"))
                original = target.read_bytes()
                draft = json.loads(original)
                # A self-review is outside either specialist's two fixed
                # targets. The bound checker must report it during the turn.
                own = "theory" if target.name == "theory_review.json" else "empirical"
                draft["assessments"][0]["proposal_id"] = "proposal." + own
                target.write_text(json.dumps(draft), encoding="utf-8")
                rejected = validate_artifacts()
                target.write_bytes(original)
                reports[own] = [rejected, validate_artifacts()]
            return result

    engine.bridge = CheckingBridge()
    mode = "p2.researcher_proposal" if with_seed else "p2.full_catalog"
    outputs, files = p2_documents(with_seed)
    script(engine, "P2", mode, outputs, files)
    final = await complete(engine, "P2", mode, supplied_method=deepcopy(SEED) if with_seed else None)
    assert set(reports) == {"theory", "empirical"}
    for own, checks in reports.items():
        assert [report["status"] for report in checks] == ["failed", "passed"], checks
        assert {finding["code"] for finding in checks[0]["findings"]} == {"review.target_coverage"}
        assert checks[1]["checked_outputs"] == ["p2." + own + "_review"]
    assert final.mechanical_repair_attempts == {} and final.correction_attempts == 0
    assert len(engine.bridge.turns) == 6


async def test_schema_repair_precedes_synthesis_and_preserves_original(direct_engine):
    engine, _ = direct_engine
    documents = p1_documents()
    broken = deepcopy(documents["p1.lead_literature"])
    broken["papers"][0].pop("formulation_markdown")
    script(engine, "P1", "p1.literature_update", documents)
    engine.bridge.script_thread(LEAD, [
        response(lead_literature=broken),
        response(lead_literature=documents["p1.lead_literature"]),
        response(research_basis=documents["p1.research_basis"]),
    ])
    final = await finish(engine)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert final.mechanical_repair_attempts == {"p1.discovery": 1}
    assert final.correction_attempts == 0 and final.findings_history[-1] == []
    directory = engine.run_dir(PID, final.run_id)
    archive = directory / "mechanical-repairs/p1.discovery/attempt-1/outputs"
    assert read_json(archive / "lead_literature.json") == broken
    for name in ("theory_literature", "empirical_literature"):
        assert (archive / (name + ".json")).read_bytes() == (directory / "outputs/p1.discovery" / (name + ".json")).read_bytes()
    lead_turns = [t for t in engine.bridge.turns if engine.bridge.threads[t["thread_id"]]["key"] == LEAD]
    assert len(lead_turns) == 3
    assert "Mechanical repair before handoff" in lead_turns[1]["brief"]
    assert "formulation_markdown" in lead_turns[1]["brief"]
    assert "p1.lead_synthesis" in lead_turns[2]["brief"]
    assert final.usage["input_tokens"] == 500


async def test_persistent_invalid_artifact_stops_after_unchanged_repair(direct_engine):
    engine, project = direct_engine
    documents = p1_documents()
    broken = deepcopy(documents["p1.lead_literature"])
    broken["papers"][0].pop("formulation_markdown")
    script(engine, "P1", "p1.literature_update", documents)
    engine.bridge.script_thread(LEAD, [response(lead_literature=broken)] * 3)
    final = await finish(engine)
    assert final.state is RunState.FAILED
    assert final.mechanical_repair_attempts == {"p1.discovery": 1}
    assert final.stage_states["p1.lead_synthesis"] == "pending"
    assert final.correction_attempts == 0 and engine.correction_block_reason(final) is None
    assert len(engine.bridge.turns) == 4
    assert {f["object_id"] for f in final.findings_history[-1]} == {"p1.lead_literature"}
    assert not (project / "branches/trunk/phases/p1/current.json").exists()
    result = read_json(engine.run_dir(PID, final.run_id) / "mechanical-repairs/p1.discovery/attempt-1/result.json")
    assert result["unchanged"] and not result["changed_files"]
    assert "unchanged" in final.terminal_reason
    # Early stopping preserves the separately authorized correction allowance.
    engine.bridge.script_thread(LEAD, [
        response(lead_literature=documents["p1.lead_literature"]),
        response(research_basis=documents["p1.research_basis"]),
    ])
    await engine.correct(PID, final.run_id, note="Supply the missing formulation field.")
    await engine._tasks[final.run_id]
    corrected = engine.load_run(PID, final.run_id)
    assert corrected.state is RunState.PUBLISHED, (corrected.terminal_reason, corrected.findings_history)
    assert corrected.mechanical_repair_attempts == {"p1.discovery": 1}
    assert corrected.correction_attempts == 1


@pytest.mark.parametrize(("resolve_one", "new_blocker"), [(False, False), (True, False), (True, True)])
async def test_repair_changed_content_with_persistent_blocker_gets_informed_second_attempt(direct_engine, resolve_one, new_blocker):
    engine, _ = direct_engine
    documents = p1_documents()
    broken = deepcopy(documents["p1.lead_literature"])
    broken["papers"][0].pop("formulation_markdown")
    if resolve_one:
        broken.pop("title")
    partly_fixed = deepcopy(broken)
    partly_fixed["title"] = documents["p1.lead_literature"]["title"] + " (checked)"
    if new_blocker:
        partly_fixed.pop("search_scope")
    script(engine, "P1", "p1.literature_update", documents)
    engine.bridge.script_thread(LEAD, [response(lead_literature=broken), response(lead_literature=partly_fixed),
                                     response(lead_literature=documents["p1.lead_literature"]),
                                     response(research_basis=documents["p1.research_basis"])])
    final = await finish(engine)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert final.mechanical_repair_attempts == {"p1.discovery": 2}
    result = read_json(engine.run_dir(PID, final.run_id) / "mechanical-repairs/p1.discovery/attempt-1/result.json")
    assert result["unchanged"] is False
    assert [change["path"] for change in result["changed_files"]] == ["lead_literature.json"]
    assert result["remaining_findings"] and bool(result["new_findings"]) == new_blocker
    assert bool(result["resolved_findings"]) == resolve_one
    repairs = [turn for turn in engine.bridge.turns if "Mechanical repair before handoff" in turn["brief"]]
    assert len(repairs) == 2
    assert "Previous repair result" in repairs[1]["brief"] and "formulation_markdown" in repairs[1]["brief"]
    assert "File changes alone do not establish scientific progress" in repairs[1]["brief"]
    assert "## Stage objective" not in repairs[1]["brief"]


async def test_repair_repeat_signal_ignores_unrelated_files_and_resets_after_change(direct_engine):
    engine, _ = direct_engine
    documents = p1_documents()
    reports = []

    class RecheckingBridge(FakeCodexBridge):
        async def run_turn(self, thread_id, *, validate_artifacts=None, **kwargs):
            if self.threads[thread_id]["key"] == LEAD and kwargs["workspace"].name == "p1.discovery":
                workspace = kwargs["workspace"]
                broken = deepcopy(documents["p1.lead_literature"])
                broken.pop("title")
                path = workspace / "lead_literature.json"
                path.write_text(json.dumps(broken), encoding="utf-8")
                reports.append(validate_artifacts())
                (workspace / "cache.txt").write_text("unrelated scratch change", encoding="utf-8")
                reports.append(validate_artifacts())
                broken["papers"][0]["formulation_markdown"] += " Checked source."
                path.write_text(json.dumps(broken), encoding="utf-8")
                reports.append(validate_artifacts())
                reports.append(validate_artifacts())
                path.write_text(json.dumps(documents["p1.lead_literature"]), encoding="utf-8")
                reports.extend([validate_artifacts(), validate_artifacts()])
            return await super().run_turn(thread_id, validate_artifacts=validate_artifacts, **kwargs)

    engine.bridge = RecheckingBridge()
    script(engine, "P1", "p1.literature_update", documents)
    final = await finish(engine)
    assert final.state is RunState.PUBLISHED, final.terminal_reason
    assert [report["status"] for report in reports] == ["failed"] * 4 + ["passed"] * 2
    assert [bool(report.get("recovery", {}).get("stop_requested")) for report in reports] == [False, True, False, True, False, False]
    assert reports[1]["recovery"]["code"] == "artifact_check.unchanged_failure"
    assert final.mechanical_repair_attempts == {}


@pytest.mark.parametrize("citation_repair", [False, True])
async def test_repair_p5_brief_is_narrow_and_recreated_thread_retains_exact_sources(legacy_p5_workbench, citation_repair):
    engine, project, branch = legacy_p5_workbench
    seed_manuscript_context(project, branch)
    for phase, mode in (("P3", "p3.theory_establishment"), ("P4", "p4.preliminary")):
        script_scientific_run(engine, project, branch, phase, mode)
        run = await engine.start_run("project.test", phase=phase, mode=mode, branch_id=branch)
        await engine._tasks[run.run_id]
        assert engine.load_run("project.test", run.run_id).state is RunState.PUBLISHED

    class RecreatedBridge(FakeCodexBridge):
        def __init__(self):
            super().__init__()
            self.unavailable = set()

        async def resume_thread(self, thread_id, **kwargs):
            return False if thread_id in self.unavailable else await super().resume_thread(thread_id, **kwargs)

        async def run_turn(self, thread_id, **kwargs):
            result = await super().run_turn(thread_id, **kwargs)
            if "Mechanical repair before handoff" not in kwargs["brief_path"].read_text(encoding="utf-8"):
                self.unavailable.add(thread_id)
            return result

    engine.bridge = RecreatedBridge()
    script_scientific_run(engine, project, branch, "P5", "p5.assembly")
    original = deepcopy(engine.bridge.script_by_key[LEAD][0])
    filename = "claim_traceability.json" if citation_repair else "decision.json"
    broken = json.loads(original[1][filename])
    if citation_repair:
        broken[0]["supporting_evidence_ids"] = ["claim.invented"]
    else:
        broken.pop("headline")
    initial = deepcopy(original)
    initial[1][filename] = json.dumps(broken)
    engine.bridge.script_thread(LEAD, [initial, ("ok", {filename: original[1][filename]})])
    run = await engine.start_run("project.test", phase="P5", mode="p5.assembly", branch_id=branch)
    await engine._tasks[run.run_id]
    final = engine.load_run("project.test", run.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert len(engine.bridge.turns) == 2
    authored, repaired = engine.bridge.turns
    assert authored["thread_id"] != repaired["thread_id"]
    brief = repaired["brief"]
    assert brief.count("### `") == 1
    assert "## Stage objective" not in brief and "## Your scientific responsibility" not in brief
    assert filename in brief and "whole manuscript" not in brief
    directory = engine.run_dir("project.test", final.run_id)
    stage = engine._stages(final)[0]
    archive = directory / "mechanical-repairs" / stage.stage_id / "attempt-1"
    original_brief = archive / f"{stage.stage_id}.research_lead.md"
    assert str(original_brief) in brief
    assert original_brief.read_text(encoding="utf-8") == authored["brief"]
    basis = read_json(directory / "basis.json")
    for source in basis["artifacts"]:
        assert str(source["path"]) in original_brief.read_text(encoding="utf-8")
        assert sha256_file(Path(source["path"])) == source["content_sha256"]
    for output in stage.writes:
        name = engine._output_filename(output)
        if name != filename:
            assert (archive / "outputs" / name).read_bytes() == (directory / "outputs" / stage.stage_id / name).read_bytes()


async def test_conflicting_member_source_identities_are_repaired_before_lead_synthesis(direct_engine):
    engine, _ = direct_engine
    documents = p1_documents()
    documents["p1.lead_literature"]["papers"][0]["source"]["identifiers"].append({"kind": "pmid", "value": "101"})
    theory = deepcopy(documents["p1.theory_literature"])
    theory["papers"] = deepcopy(documents["p1.lead_literature"]["papers"])
    broken = deepcopy(theory)
    broken["papers"][0]["source"]["title"] = "An unrelated paper with the same identifier"
    broken["papers"][0]["source"]["identifiers"][-1]["value"] = "999"
    script(engine, "P1", "p1.literature_update", documents)
    engine.bridge.script_thread(LEAD, [
        response(lead_literature=documents["p1.lead_literature"]),
        response(lead_literature=documents["p1.lead_literature"]),
        response(research_basis=documents["p1.research_basis"]),
    ])
    engine.bridge.script_thread("theorist:P1:trunk", [response(theory_literature=broken), response(theory_literature=theory)])
    final = await finish(engine)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert final.mechanical_repair_attempts == {"p1.discovery": 1}
    assert len(engine.bridge.turns) == 6
    initial = final.findings_history[0]
    assert {f["code"] for f in initial} == {"literature.source_identity_conflict"}
    assert {f["object_id"] for f in initial} == {"p1.lead_literature", "p1.theory_literature"}
    repairs = [t for t in engine.bridge.turns if "Mechanical repair before handoff" in t["brief"]]
    assert len(repairs) == 2 and all("does not decide which record is correct" in t["brief"] for t in repairs)
    assert "p1.lead_synthesis" in engine.bridge.turns[-1]["brief"]


async def test_provider_failure_does_not_trigger_mechanical_retry(direct_engine):
    engine, _ = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    engine.bridge.script_thread(LEAD, [("fail", "Provider unavailable")])
    final = await finish(engine)
    assert final.state is RunState.FAILED
    assert final.mechanical_repair_attempts == {}
    assert len(engine.bridge.turns) == 3


async def test_cancel_during_automatic_repair_never_starts_consumer(direct_engine):
    engine, _ = direct_engine
    entered = asyncio.Event()

    class BlockingRepair(FakeCodexBridge):
        async def run_turn(self, thread_id, **kwargs):
            if "Mechanical repair before handoff" in kwargs["brief_path"].read_text(encoding="utf-8"):
                entered.set()
                await asyncio.Event().wait()
            return await super().run_turn(thread_id, **kwargs)

    engine.bridge = BlockingRepair()
    documents = p1_documents()
    documents["p1.lead_literature"].pop("title")
    script(engine, "P1", "p1.literature_update", documents)
    run = await engine.start_run(PID, phase="P1", mode="p1.literature_update", branch_id="trunk")
    await asyncio.wait_for(entered.wait(), timeout=10)
    await engine.cancel(PID, run.run_id)
    final = engine.load_run(PID, run.run_id)
    assert final.state is RunState.CANCELLED
    assert final.stage_states["p1.lead_synthesis"] == "pending"
    assert engine._mechanical_repairs == {}


async def test_cancellation_retains_completed_sibling_repair_usage(direct_engine):
    engine, _ = direct_engine
    completed = asyncio.Event()
    blocked = asyncio.Event()

    class PartialRepair(FakeCodexBridge):
        async def run_turn(self, thread_id, **kwargs):
            if "Mechanical repair before handoff" in kwargs["brief_path"].read_text(encoding="utf-8"):
                if self.threads[thread_id]["key"] == LEAD:
                    result = await super().run_turn(thread_id, **kwargs)
                    completed.set()
                    return result
                await completed.wait()
                blocked.set()
                await asyncio.Event().wait()
            return await super().run_turn(thread_id, **kwargs)

    engine.bridge = PartialRepair()
    documents = p1_documents()
    documents["p1.lead_literature"].pop("title")
    documents["p1.theory_literature"].pop("title")
    script(engine, "P1", "p1.literature_update", documents)
    engine.bridge.script_thread(LEAD, [response(lead_literature=documents["p1.lead_literature"]),
                                      response(lead_literature=p1_documents()["p1.lead_literature"])])
    run = await engine.start_run(PID, phase="P1", mode="p1.literature_update", branch_id="trunk")
    await asyncio.wait_for(blocked.wait(), timeout=10)
    await engine.cancel(PID, run.run_id)
    final = engine.load_run(PID, run.run_id)
    assert final.state is RunState.CANCELLED
    assert final.usage["input_tokens"] == 400 and final.usage["output_tokens"] == 200
