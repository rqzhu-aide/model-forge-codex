"""Researcher-facing regressions for exact context, safe assessment and runs."""
import asyncio
import copy
import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import pytest

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import Finding, MemberRole, RunRecord, RunState, StageSpec
from model_forge_codex.members import provision_team
from model_forge_codex.methods import activate_method, get_method
from model_forge_codex.records import ArtifactError, current_records, generation_path, package_committed, publish_package, read_generation, source_artifact_path
from model_forge_codex.runs import RunEngine, RunError, owned_writes
from model_forge_codex.storage import read_json, write_json_atomic
from test_p5_review_packet import prepare_engine_review_packet

REPO = Path(__file__).resolve().parents[1]


def publish(project, branch, phase, documents, run_id="run.seed"):
    return publish_package(project / "branches" / branch / "phases" / phase.lower(),
                           {k: json.dumps(v).encode() for k, v in documents.items()},
                           run_id=run_id, phase=phase, branch_id=branch)


@pytest.fixture
def workbench(tmp_path):
    root = tmp_path / "data"
    project = root / "projects" / "project.test"
    project.mkdir(parents=True)
    write_json_atomic(project / "project.json", {"project_id": "project.test", "research_question": "Can the method handle dependence?"})
    shutil.copytree(REPO / "contracts", project / "contracts")
    provision_team(project)
    publish(project, "trunk", "P1", {"literature_synthesis": {"headline": "Frozen literature"}})
    method = json.loads((REPO / "contracts" / "examples" / "method.example.json").read_text())
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [method]}})
    branch = activate_method(project, method["identity"]["stable_id"])["branch_id"]
    bridge = FakeCodexBridge()
    engine = RunEngine(root, bridge)
    # These tests execute only bounded, authored fixture scripts. Exercise the
    # controller lifecycle through its existing runner seam; sandbox launch and
    # failure behavior have their own tests and live validation.
    from model_forge_codex.p4_execution import ManagedPythonRunner, shared_python_executable
    original_controller = engine._p4_controller
    def fixture_controller(*args, **kwargs):
        controller = original_controller(*args, **kwargs)
        controller.runner = ManagedPythonRunner(command_builder=lambda script, arguments, workspace:
            [str(shared_python_executable()), str(script), *arguments])
        return controller
    engine._p4_controller = fixture_controller
    return engine, project, branch


def seed_theory(project, branch):
    from model_forge_codex.methods import get_method
    return publish(project, branch, "P3", {
        "theory_record": {"method_identity": get_method(project, branch)["identity"],
                          "assumptions": [{"assumption_id": "assumption.independent", "statement": "Observations are independent."}],
                          "statements": [{"statement_id": "statement.consistency", "statement": "The estimator converges."}]},
        "claim_map": {"claims": [{"statement_id": "statement.consistency", "proof_status": "sketch", "depends_on": ["assumption.independent"]}]},
    })


def target(package, branch):
    p = package["records"]["theory_record"]
    return {"branch": branch, "phase": "P3", "family": "theory_record",
            "generation_id": p["generation_id"], "sha256": p["content_sha256"],
            "run_id": p["run_id"], "object_id": "assumption.independent", "kind": "assumption"}


def record(eng, branch, run_id, phase="P3", mode="p3.theory_revision"):
    r = RunRecord(run_id=run_id, project_id="project.test", phase=phase, mode=mode, branch_id=branch)
    eng._save_run(r)
    return r


def test_exact_generation_rejects_tamper_and_missing(tmp_path):
    p = publish(tmp_path, "method.a", "P3", {"theory": {"v": 1}})
    phase = tmp_path / "branches" / "method.a" / "phases" / "p3"
    pointer = p["records"]["theory"]
    path = generation_path(phase, "theory", pointer)
    path.write_text('{"v": 2}')
    with pytest.raises(ArtifactError, match="Digest mismatch"):
        read_generation(phase, "theory", pointer)
    with pytest.raises(ArtifactError, match="missing"):
        read_generation(phase, "theory", {**pointer, "generation_id": "generation.absent"})


def test_package_commit_failure_retains_entire_prior_package(tmp_path, monkeypatch):
    from model_forge_codex import records
    first = publish(tmp_path, "method.a", "P3", {"theory": {"v": 1}, "graph": {"v": 1}})
    phase = tmp_path / "branches" / "method.a" / "phases" / "p3"
    original = records.write_json_atomic
    def fail_marker(path, doc):
        if path.name == "current-package.json":
            raise OSError("disk failure at commit")
        original(path, doc)
    monkeypatch.setattr(records, "write_json_atomic", fail_marker)
    with pytest.raises(OSError):
        publish(tmp_path, "method.a", "P3", {"theory": {"v": 2}, "graph": {"v": 2}}, "run.new")
    assert current_records(phase) == first["records"]
    assert read_generation(phase, "theory", current_records(phase)["theory"]) == {"v": 1}
    orphan = next(read_json(p) for p in (phase / "packages").glob("*.json") if read_json(p)["run_id"] == "run.new")
    assert not package_committed(phase, orphan["package_id"])
    assert package_committed(phase, first["package_id"])


@pytest.mark.asyncio
async def test_preliminary_and_comprehensive_p4_start_without_theory(workbench):
    eng, project, branch = workbench
    for mode in ("p4.preliminary", "p4.comprehensive"):
        assert eng.check_readiness("project.test", "P4", branch, mode) == []
        script_scientific_run(eng, project, branch, "P4", mode)
        r = await eng.start_run("project.test", phase="P4", mode=mode, branch_id=branch)
        await eng._tasks[r.run_id]
        brief = eng.bridge.turns[-3]["brief"]
        assert "No current theory package exists" in brief
        assert mode in brief


@pytest.mark.asyncio
async def test_revision_freezes_current_theory_and_empirical_feedback(workbench):
    eng, project, branch = workbench
    package = seed_theory(project, branch)
    publish(project, branch, "P4", {"diagnostics": {"method_identity": get_method(project, branch)["identity"], "headline": "Dependence counterexample"}})
    r = await eng.start_run("project.test", phase="P3", mode="p3.theory_revision", branch_id=branch,
                            target=target(package, branch), instructions="Check assumption carefully.")
    # The current source changes after authorization, before the first agent turn.
    publish(project, branch, "P3", {"theory_record": {"text": "UNAUTHORIZED_NEW_THEORY"}}, "run.concurrent")
    await eng._tasks[r.run_id]
    brief = eng.bridge.turns[0]["brief"]
    assert "Observations are independent" in brief
    assert "UNAUTHORIZED_NEW_THEORY" not in brief
    assert "diagnostics" in brief
    assert "Check assumption carefully." in brief
    basis = read_json(eng.run_dir("project.test", r.run_id) / "basis.json")
    assert {"P3", "P4"} <= {ref["phase"] for ref in basis["records"]}


@pytest.mark.asyncio
async def test_stale_component_refuses_before_agent_turn(workbench):
    eng, project, branch = workbench
    old = seed_theory(project, branch)
    seed_theory(project, branch)
    with pytest.raises(RunError, match="stale"):
        await eng.start_run("project.test", phase="P3", mode="p3.theory_revision", branch_id=branch, target=target(old, branch))
    assert eng.bridge.turns == []


@pytest.mark.asyncio
async def test_assessment_saves_discussion_without_changing_science(workbench):
    eng, project, branch = workbench
    package = seed_theory(project, branch)
    phase = project / "branches" / branch / "phases" / "p3"
    before = {str(p): p.read_bytes() for p in phase.rglob("*") if p.is_file()}
    response = {"headline": "Assumption needs qualification", "assessment_markdown": "The proof uses independence at factorization.",
                "limitations": ["Dependent case not checked"], "suggested_actions": ["Consider a mixing condition"],
                "evidence_refs": [{"family": "theory_record", "generation_id": package["records"]["theory_record"]["generation_id"]}]}
    eng.bridge.default_behavior = ("ok", {"assessment.json": json.dumps(response)})
    r = await eng.start_run("project.test", phase="P3", mode="p3.assessment", branch_id=branch,
                            intent="assessment", target=target(package, branch), instructions="Take another look.")
    await eng._tasks[r.run_id]
    final = eng.load_run("project.test", r.run_id)
    assert final.state is RunState.ASSESSED
    assert before == {str(p): p.read_bytes() for p in phase.rglob("*") if p.is_file()}
    doc = read_json(eng.run_dir("project.test", r.run_id) / "assessment.json")
    assert doc["options"] == response["suggested_actions"]
    assert doc["messages"][0]["content"] == "Take another look."
    assert Path(eng.bridge.turns[0]["workspace"]) == eng.member_workspace(r, "p3.assessment", MemberRole.THEORIST)
    assert Path(eng.bridge.threads[eng.bridge.turns[0]["thread_id"]]["member_home"]) == eng.run_dir("project.test", r.run_id) / "isolated/theorist/codex-home"
    assert not (project / "members" / "theorist" / "notebooks" / f"{branch}.md").exists()
    assert not list((project / "authority" / "receipts").glob("*.json"))


@pytest.mark.asyncio
async def test_assessment_followup_retains_original_theory_after_replacement(workbench):
    eng, project, branch = workbench
    package = seed_theory(project, branch)
    response = {"headline": "Original assessment", "assessment_markdown": "Independence enters the original proof.",
                "limitations": [], "suggested_actions": [], "evidence_refs": []}
    eng.bridge.default_behavior = ("ok", {"assessment.json": json.dumps(response)})
    first = await eng.start_run("project.test", phase="P3", mode="p3.assessment", branch_id=branch,
                                intent="assessment", target=target(package, branch), instructions="Where is independence used?")
    await eng._tasks[first.run_id]
    assert eng.load_run("project.test", first.run_id).state is RunState.ASSESSED
    current = publish(project, branch, "P3", {"theory_record": {"method_identity": get_method(project, branch)["identity"], "assumptions": [
        {"assumption_id": "assumption.independent", "statement": "NEW_CURRENT_MIXING_CONDITION"}]}}, "run.revised")
    followup = await eng.start_run("project.test", phase="P3", mode="p3.assessment", branch_id=branch,
                                   intent="assessment", target=target(package, branch), assessment_id=first.assessment_id,
                                   instructions="Explain that original proof step.")
    await eng._tasks[followup.run_id]
    assert eng.load_run("project.test", followup.run_id).state is RunState.ASSESSED
    brief = eng.bridge.turns[-1]["brief"]
    assert "Observations are independent" in brief
    assert "Where is independence used?" in brief
    assert "NEW_CURRENT_MIXING_CONDITION" not in brief
    saved = read_json(eng.run_dir("project.test", followup.run_id) / "assessment.json")
    assert len(saved["messages"]) == 4
    assert saved["target"] == target(package, branch)
    assert current_records(project / "branches" / branch / "phases" / "p3") == current["records"]
    with pytest.raises(RunError, match="stale"):
        await eng.start_run("project.test", phase="P3", mode="p3.theory_revision", branch_id=branch,
                            target=target(package, branch), instructions="Repair now.")


@pytest.mark.asyncio
async def test_outside_review_is_fresh_and_receives_only_frozen_packet(workbench):
    eng, project, branch = workbench
    seed_theory(project, branch)
    publish(project, branch, "P4", {"decision": {"method_identity": get_method(project, branch)["identity"], "headline": "INTERNAL_VERDICT_SECRET"}})
    publish(project, branch, "P5", {"manuscript": {"method_identity": get_method(project, branch)["identity"], "text": "THE_FROZEN_MANUSCRIPT"}})
    stage = eng.stage_plan("project.test", "P5", "p5.review_revision")[0]
    for run_id in ("run.review1", "run.review2"):
        r = record(eng, branch, run_id, "P5", "p5.review_revision")
        prepare_engine_review_packet(eng, r)
        await eng._drive_member_turn(r, stage, MemberRole.OUTSIDE_REVIEWER, eng.run_dir("project.test", run_id))
    first, second = eng.bridge.turns
    assert first["thread_id"] != second["thread_id"]
    assert "INTERNAL_VERDICT_SECRET" not in first["brief"]
    assert "review-packet" in first["brief"]
    assert "THE_FROZEN_MANUSCRIPT" in (eng.run_dir("project.test", "run.review1") / "review-packet" / "manuscript.json").read_text()


@pytest.mark.asyncio
async def test_parallel_member_cannot_replace_owned_output(workbench):
    eng, _, branch = workbench
    r = record(eng, "trunk", "run.ownership", "P1", "p1.literature_update")
    stage = eng.stage_plan("project.test", "P1", r.mode)[0]
    eng.bridge.script_thread("theorist:P1:trunk", [("ok", {"theory_literature.json": '{"owner":"theorist"}'})])
    eng.bridge.script_thread("data_analyst:P1:trunk", [("ok", {"theory_literature.json": '{"owner":"analyst"}'})])
    await eng._drive_member_turn(r, stage, MemberRole.THEORIST, eng.run_dir("project.test", r.run_id))
    result = await eng._drive_member_turn(r, stage, MemberRole.DATA_ANALYST, eng.run_dir("project.test", r.run_id))
    assert not result.succeeded
    output = eng.run_dir("project.test", r.run_id) / "outputs" / stage.stage_id
    assert read_json(output / "theory_literature.json")["owner"] == "theorist"
    assert (output / "seals" / "theorist.json").exists()


@pytest.mark.asyncio
async def test_concurrent_branches_serialize_shared_lead(workbench):
    eng, _, branch = workbench
    class OverlapBridge(FakeCodexBridge):
        active = 0
        overlaps = 0
        async def run_turn(self, thread_id, **kwargs):
            self.active += 1
            if self.active > 1:
                self.overlaps += 1
            await asyncio.sleep(0.01)
            result = await super().run_turn(thread_id, **kwargs)
            self.active -= 1
            return result
    eng.bridge = OverlapBridge()
    stage = eng.stage_plan("project.test", "P3", "p3.theory_establishment")[-1]
    rs = [record(eng, b, "run.lead." + str(i)) for i, b in enumerate((branch, "method.other"))]
    await asyncio.gather(*(eng._drive_member_turn(r, stage, MemberRole.RESEARCH_LEAD, eng.run_dir("project.test", r.run_id)) for r in rs))
    assert eng.bridge.overlaps == 0
    assert len({t["thread_id"] for t in eng.bridge.turns}) == 1


def legacy_correction_setup(eng, project, monkeypatch):
    # The unchanged legacy contract remains supported; this fixture isolates
    # the correction state machine from new scientific semantic validation.
    pin = read_json(project / "contracts" / "catalog-pin.json")
    write_json_atomic(project / "contracts" / "catalog-pin.json", {**pin, "catalog_version": "1.3.0"})
    stages = [StageSpec("p1.discovery", 1, "serial", (MemberRole.THEORIST,), ("p1.phase_summary", "p1.theory_discovery")),
              StageSpec("p1.lead_synthesis", 2, "serial", (MemberRole.RESEARCH_LEAD,), ("p1.complete_theory",))]
    monkeypatch.setattr(eng, "stage_plan", lambda *args: stages)
    good = {"summary_id": "summary.test", "phase": "P1", "headline": "Fixed", "evaluation_markdown": "Summary", "created_at": "2026-09-01T00:00:00Z"}
    eng.bridge.script_thread("theorist:P1:trunk", [
        ("ok", {"phase_summary.json": "{}", "theory_discovery.json": '{"unchanged":true}'}),
        ("ok", {"phase_summary.json": json.dumps(good)}),
    ])
    eng.bridge.script_thread("research_lead:PROJECT:trunk", [("ok", {"complete_theory.json": '{"review":1}'}), ("ok", {"complete_theory.json": '{"review":2}'})])
    return stages


@pytest.mark.asyncio
async def test_correction_delivers_note_and_findings_before_review(workbench, monkeypatch):
    eng, project, _ = workbench
    eng._MAX_MECHANICAL_REPAIRS = 0  # Isolate researcher-authorized correction.
    legacy_correction_setup(eng, project, monkeypatch)
    r = await eng.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    await eng._tasks[r.run_id]
    assert eng.load_run("project.test", r.run_id).state is RunState.FAILED
    observed = []
    original_turn = eng._drive_member_turn
    async def observe_stage_progress(record, stage, role, run_dir):
        if record.state is RunState.CORRECTING:
            observed.append(dict(eng.load_run("project.test", record.run_id).stage_states))
        return await original_turn(record, stage, role, run_dir)
    monkeypatch.setattr(eng, "_drive_member_turn", observe_stage_progress)
    await eng.correct("project.test", r.run_id, note="Only fix the missing summary fields.")
    await eng._tasks[r.run_id]
    final = eng.load_run("project.test", r.run_id)
    assert final.state is RunState.PUBLISHED, final.terminal_reason
    assert "Only fix the missing summary fields." in eng.bridge.turns[1]["brief"]
    assert "schema.required" in eng.bridge.turns[1]["brief"]
    assert len(eng.bridge.turns) == 3
    assert observed == [{"p1.discovery": "correcting", "p1.lead_synthesis": "pending"}]
    assert read_json(eng.run_dir("project.test", r.run_id) / "outputs" / "p1.lead_synthesis" / "complete_theory.json") == {"review": 1}


@pytest.mark.asyncio
async def test_correction_rejects_unrelated_changes(workbench, monkeypatch):
    eng, project, _ = workbench
    eng._MAX_MECHANICAL_REPAIRS = 0  # Isolate researcher-authorized correction.
    legacy_correction_setup(eng, project, monkeypatch)
    eng.bridge.script_by_key["theorist:P1:trunk"][1][1]["theory_discovery.json"] = '{"unrelated_change":true}'
    r = await eng.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    await eng._tasks[r.run_id]
    await eng.correct("project.test", r.run_id, note="Fix the summary only.")
    await eng._tasks[r.run_id]
    final = eng.load_run("project.test", r.run_id)
    assert final.state is RunState.FAILED
    assert "out-of-scope" in final.terminal_reason
    assert final.stage_states["p1.discovery"] == "failed"


@pytest.mark.asyncio
async def test_correction_refreshes_failed_downstream_stage_once(workbench, monkeypatch):
    eng, project, _ = workbench
    eng._MAX_MECHANICAL_REPAIRS = 0  # Isolate researcher-authorized correction.
    legacy_correction_setup(eng, project, monkeypatch)
    # Discovery must pass its immediate check before a downstream failure
    # can occur. The explicit correction then retries only that failed stage.
    eng.bridge.script_by_key["theorist:P1:trunk"][0][1]["phase_summary.json"] = (
        eng.bridge.script_by_key["theorist:P1:trunk"][1][1]["phase_summary.json"]
    )
    eng.bridge.script_by_key["research_lead:PROJECT:trunk"][0][1].pop("complete_theory.json")
    r = await eng.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    await eng._tasks[r.run_id]
    assert eng.load_run("project.test", r.run_id).state is RunState.FAILED
    await eng.correct("project.test", r.run_id, note="Repair both missing outputs.")
    await eng._tasks[r.run_id]
    final = eng.load_run("project.test", r.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert len(eng.bridge.turns) == 3
    assert sum(turn["thread_id"] == eng.bridge.turns[0]["thread_id"] for turn in eng.bridge.turns) == 1
    assert "Repair both missing outputs." in eng.bridge.turns[-1]["brief"]
    assert "output.required_missing" in eng.bridge.turns[-1]["brief"]


@pytest.mark.asyncio
async def test_correction_exception_has_visible_terminal_state(workbench, monkeypatch):
    eng, project, _ = workbench
    eng._MAX_MECHANICAL_REPAIRS = 0  # Isolate researcher-authorized correction.
    legacy_correction_setup(eng, project, monkeypatch)
    r = await eng.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    await eng._tasks[r.run_id]
    def unavailable(*args):
        raise OSError("Disk read unavailable")
    monkeypatch.setattr(eng, "_validate_run_outputs", unavailable)
    await eng.correct("project.test", r.run_id)
    await eng._tasks[r.run_id]
    final = eng.load_run("project.test", r.run_id)
    assert final.state is RunState.FAILED
    assert "Disk read unavailable" in final.terminal_reason


@pytest.mark.asyncio
async def test_advisory_finding_does_not_block_publication(workbench, monkeypatch):
    eng, project, _ = workbench
    legacy_correction_setup(eng, project, monkeypatch)
    monkeypatch.setattr(eng, "_validate_run_outputs", lambda *a: [Finding("output.size_cap_exceeded", "Advisory length", "p1.complete_theory", "", False)])
    r = await eng.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    await eng._tasks[r.run_id]
    final = eng.load_run("project.test", r.run_id)
    assert final.state is RunState.PUBLISHED
    assert final.findings_history[0][0]["blocks_publication"] is False


def scientific_output_documents(catalog, phase, method_identity, *, mode=None, supplied_method=None):
    """Full contract envelopes with a small, independently checkable experiment."""
    examples = {schema: example for example, schema in read_json(REPO / "contracts/catalog-index.json")["valid_examples"].items()}
    definitions = catalog.output_definitions(phase)
    documents = {}
    for output_id, definition in definitions.items():
        if output_id == "p3.assessment":
            continue
        schema = catalog.schema_for_output(output_id)
        document = read_json(REPO / "contracts/examples" / examples[schema])
        if definition.get("schema_application") in ("each_item", "jsonl"):
            document = [document]
        documents[output_id] = document
    if phase == "P3":
        theory = documents["p3.theory_candidate"]
        for assumption in theory["assumptions"]:
            assumption["used_by_statement_ids"] = [s["statement_id"] for s in theory["statements"]
                                                     if assumption["assumption_id"] in s["assumption_ids"]]
        documents["p3.complete_theory"] = copy.deepcopy(theory)
        documents["p3.claim_map"] = {"claims": [{"statement_id": s["statement_id"],
            "depends_on": s["depends_on_statement_ids"] + s["assumption_ids"],
            "proof_status": "full" if s["justification"]["kind"] in ("proof", "definition") else "sketch",
            "scientific_status": s["status"]} for s in theory["statements"]]}
        documents["p3.falsification_log"] = {"probes": []}
        contract = read_json(catalog.root / "contracts/phases/P3.json")
        if "p3.conservative_assessment_v1" in contract.get("capabilities", []):
            concerns = [*documents["p3.analyst_handoff"].get("unresolved_issues", []),
                        *documents["p3.analyst_audit"].get("issues", [])]
            documents["p3.decision"]["issue_dispositions"] = [{
                "issue_id": identifier, "status": "unresolved",
                "reason": "Fixture only: this authored concern remains open under the stated scientific scope."}
                for identifier in dict.fromkeys(issue["issue_id"] for issue in concerns)]
    if phase == "P4":
        protocol = documents["p4.protocol"]
        protocol["mode"] = mode or protocol["mode"]
        protocol["claim_tests"] = [protocol["claim_tests"][0]]
        protocol["claim_tests"][0].update(test_id="test.feasibility", target_statement_ids=[])
        protocol["metrics"] = [protocol["metrics"][0]]
        protocol["metrics"][0].update(metric_id="metric.error", summary={"aggregation": "mean", "uncertainty": "mcse",
            "decision_rule": {"operator": ">", "threshold": 2}})
        protocol["cases"] = [{"case_id": "case.small", "label": "Small feasibility screen", "test_ids": ["test.feasibility"],
            "metric_ids": ["metric.error"], "comparator_id": "selected_method", "regime": "small",
            "replicates": [{"replicate_id": "r1", "seed": 1}, {"replicate_id": "r2", "seed": 2}]}]
        documents["p4.metrics_long"] = [
            {"case_id": "case.small", "replicate_id": "r1", "seed": 1, "status": "completed", "runtime_ms": 5, "metrics": {"metric.error": 1}},
            {"case_id": "case.small", "replicate_id": "r2", "seed": 2, "status": "completed", "runtime_ms": 7, "metrics": {"metric.error": 3}}]
        documents["p4.diagnostics"] = {"diagnostics_id": "diag.screen", "headline_numbers": [
            {"case_id": "case.small", "metric": "metric.error", "estimate": 2, "mcse": 1, "uncertainty_kind": "mcse", "n_replicates": 2}],
            "stability": [{"case_id": "case.small", "metric": "metric.error", "mean": 2, "sd": 2 ** .5, "n_seeds": 2, "seed_flip": True, "assessment": "assessed"}],
            "solver_health": [], "runtime": {"total_ms": 12, "per_case": [{"case_id": "case.small", "mean_ms": 6, "max_ms": 7}]},
            "regenerated_by": "summarize.py", "environment": {"platform": "test"}, "provenance": {}}
        for evidence in documents["p4.evidence"]:
            evidence.update(test_ids=["test.feasibility"], case_ids=["case.small"], comparator_id="selected_method")
        for exhibit in documents["p4.exhibits"]:
            exhibit.update(test_ids=["test.feasibility"], case_ids=["case.small"])
    files = {}
    def normalize(value):
        if isinstance(value, list):
            for item in value:
                normalize(item)
        elif isinstance(value, dict):
            if set(("stable_id", "version", "definition_sha256")) <= value.keys():
                value.update(method_identity)
            if value.get("phase") in ("P1", "P2", "P3", "P4", "P5"):
                value["phase"] = phase
            if value.get("artifact_id") and "sha256" in value:
                name = "sources/" + value["artifact_id"] + ".md"
                content = "Saved scientific source: " + value["artifact_id"] + "\n"
                files[name] = content
                value.update(path=name, sha256=hashlib.sha256(content.encode()).hexdigest())
            if "artifact_path" in value:
                name = "figure.svg"
                content = '<svg xmlns="http://www.w3.org/2000/svg"><text x="0" y="20">Recorded estimate: 2</text></svg>'
                files[name] = content
                value.update(artifact_path=name, artifact_sha256=hashlib.sha256(content.encode()).hexdigest())
            for child in value.values():
                normalize(child)
    normalize(documents)
    if phase == "P2":
        roles = ["theory", "empirical", "lead"]
        titles = {
            "theory": "Doubly Robust Series Estimator (DRSE)",
            "empirical": "Penalized Inverse-Propensity Sieve (PIPS)",
            "lead": "Overlap-Stabilized Orthogonal Score (OSOS)",
        }
        for role in roles:
            proposal = documents[f"p2.{role}_proposal"]
            proposal["proposal_id"] = f"proposal.{role}"
            proposal["method"]["identity"]["stable_id"] = f"method.{role}"
            proposal["method"].update(record_id=f"record.method.{role}", title=titles[role], lifecycle_state="proposed")
            if role == "lead" and supplied_method is not None:
                proposal["researcher_origin"] = copy.deepcopy(supplied_method)
            else:
                proposal.pop("researcher_origin", None)
        for role, other in (("theory", "empirical"), ("empirical", "theory")):
            report = documents[f"p2.{role}_review"]
            report["review_id"] = f"review.{role}"
            template = report["assessments"][0]
            report["assessments"] = [{**copy.deepcopy(template), "proposal_id": f"proposal.{target}"}
                                     for target in [other] + (["lead"] if "lead" in roles else [])]
        assessment = documents["p2.catalog_assessment"]
        id_map = {
            "proposal.overlap_stabilized_score": "proposal.lead",
            "proposal.doubly_robust_series": "proposal.theory",
            "proposal.penalized_ipw_sieve": "proposal.empirical",
        }
        assessment["method_dispositions"] = [
            {**d, "proposal_id": id_map[d["proposal_id"]]} for d in assessment["method_dispositions"]]
        for option in assessment.get("modification_options", []):
            target = option.get("applies_to")
            if target in id_map:
                option["option_id"] = option["option_id"].replace(target, id_map[target])
                option["applies_to"] = id_map[target]
    if phase == "P4":
        from model_forge_codex.p4_validation import progressive_evaluation_enabled
        if progressive_evaluation_enabled(catalog):
            from p4_fixtures import add_progressive_documents
            add_progressive_documents(documents, files)
        # Test bytes represent recorded outputs. The harness verifies their
        # arithmetic independently and does not execute untrusted scripts.
        files["summarize.py"] = "import json\nprint(json.dumps({'mean': 2, 'mcse': 1, 'n': 2}))\n"
        documents["p4.diagnostics"]["provenance"] = {
            "protocol_sha256": hashlib.sha256(json.dumps(documents["p4.protocol"]).encode()).hexdigest(),
            "metrics_sha256": hashlib.sha256("\n".join(json.dumps(r) for r in documents["p4.metrics_long"]).encode()).hexdigest(),
            "script_sha256": hashlib.sha256(files["summarize.py"].encode()).hexdigest()}
    return documents, files


def seed_manuscript_context(project, branch):
    """Give the paper fixture actual literature and method source bytes."""
    from model_forge_codex.methods import get_method
    for phase, family, record_type in (("P1", "literature_synthesis", "literature_synthesis"), ("P2", "method_catalog", "method_catalog")):
        content = f"Saved scientific source: manuscript {phase} context\n"
        path = project / "runs/run.seed/outputs/context" / f"{phase}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        doc = {"record_id": f"record.context.{phase.lower()}", "record_type": record_type, "phase": phase,
               "claims": [{"statement_id": f"claim.context.{phase.lower()}", "text": "An explicitly recorded contextual claim."}],
               "primary_artifact": {"artifact_id": f"artifact.context.{phase.lower()}", "uri": f"artifact://artifact.context.{phase.lower()}",
                   "path": f"{phase}.md", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "media_type": "text/markdown"}}
        if phase == "P2":
            doc["methods"] = [get_method(project, branch)["definition"]]
        publish(project, "trunk", phase, {family: doc})


def bind_manuscript_test_sources(eng, project, branch, documents):
    """Bind the synthetic manuscript to the exact packages it will read."""
    manifest = []
    traces = []
    index = {"interpretation_claim_ids": []}
    template = documents["p5.claim_traceability"][0]
    paper = documents["p5.manuscript_candidate"]
    for phase, family, group in (("P1", "literature_synthesis", "p1_literature_claim_ids"),
            ("P2", "method_catalog", "p2_method_claim_ids"), ("P3", "theory_record", "p3_theory_claim_ids"),
            ("P4", "empirical_evidence_index", "p4_empirical_claim_ids")):
        source_branch = "trunk" if phase in ("P1", "P2") else branch
        directory = project / "branches" / source_branch / "phases" / phase.lower()
        pointer = current_records(directory)[family]
        source = read_generation(directory, family, pointer)
        manifest.append({"record_id": source["record_id"], "record_type": source["record_type"],
            "generation_id": pointer["generation_id"], "content_sha256": pointer["content_sha256"],
            "publication_state_at_use": "formal", "record_position_at_use": "current", "dependency_class": "hard"})
        if source.get("method_identity"):
            manifest[-1]["method_identity"] = source["method_identity"]
        if phase == "P4":
            evidence_pointer = current_records(directory)["evidence"]
            support = read_generation(directory, "evidence", evidence_pointer)[0]
            support_id = support["evidence_id"]
        else:
            support = source
            support_id = (source.get("claims") or source.get("statements"))[0]["statement_id"]
        location = next(eng._artifact_pointers(support))
        trace = copy.deepcopy(template)
        trace.update(statement_id=f"claim.paper.{phase.lower()}", record_id=paper["record_id"],
            record_generation_id=paper.get("generation_id", "candidate.paper"),
            supporting_evidence_ids=[support_id], counterevidence_ids=[], source_locations=[copy.deepcopy(location)], assumptions=[])
        trace["scientific_outcome"].update(strongest_evidence_ids=[support_id], strongest_counterevidence_ids=[])
        traces.append(trace)
        index[group] = [trace["statement_id"]]
    documents["p5.claim_traceability"] = traces
    documents["p5.upstream_basis_manifest"]["basis"] = copy.deepcopy(manifest)
    paper.update(basis=manifest, claim_support_index=index)


def script_scientific_run(eng, project, branch, phase, mode, *, proposed_method_id=None, supplied_method=None, transform=None, reference_diagnostics=False):
    from model_forge_codex.methods import get_method
    method = get_method(project, branch) if branch != "trunk" else read_json(REPO / "contracts/examples/method.example.json")
    documents, files = scientific_output_documents(Catalog(project / "contracts"), phase, method["identity"],
                                                 mode=mode, supplied_method=supplied_method)
    if phase == "P5":
        bind_manuscript_test_sources(eng, project, branch, documents)
    if proposed_method_id:
        documents["p2.theory_proposal"]["method"]["identity"]["stable_id"] = proposed_method_id
    if transform:
        transform(documents)
    behaviors = {}
    for stage in eng.stage_plan("project.test", phase, mode):
        for role in stage.roles:
            writes = dict(files)
            for output in owned_writes(stage, role):
                suffix = output.split(".", 1)[1]
                writes[suffix + (".jsonl" if suffix == "metrics_long" else ".json")] = (
                    "\n".join(json.dumps(row) for row in documents[output]) if suffix == "metrics_long" else json.dumps(documents[output]))
            key = "research_lead:PROJECT:trunk" if role == MemberRole.RESEARCH_LEAD else f"{role.value}:{phase}:{branch}"
            if role == MemberRole.OUTSIDE_REVIEWER:
                eng.bridge.default_behavior = ("ok", writes)
            else:
                from model_forge_codex.p4_validation import progressive_evaluation_enabled
                if phase == "P4" and role == MemberRole.DATA_ANALYST and progressive_evaluation_enabled(Catalog(project / "contracts")):
                    # Exercise actual managed computation and bind the emitted
                    # numerical rows to the host-generated execution identity.
                    from p4_fixtures import managed_files
                    behaviors.setdefault(key, []).extend([
                        ("p4", (managed_files(writes, reference_diagnostics=reference_diagnostics), [
                            {"operation": "save_plan", "protocol_path": "protocol.json"},
                            {"operation": "run_batch", "batch_id": "batch.feasibility", "work_item_id": "work.feasibility",
                             "script_path": "managed_fixture.py", "timeout_seconds": 30,
                               "support_files": ["fixture_source.json"],
                               "result_paths": list(writes)} ])),
                        ("p4", ({}, [{"operation": "complete"}]))])
                else:
                    behaviors.setdefault(key, []).append(("ok", writes))
    for key, turns in behaviors.items():
        eng.bridge.script_thread(key, turns)
    return documents


@pytest.mark.asyncio
@pytest.mark.parametrize("phase,mode,canonical", [
    ("P3", "p3.theory_establishment", "theory_record"),
    ("P4", "p4.preliminary", "empirical_evidence_index"),
])
async def test_strict_catalog_full_scientific_run_publishes_coherent_package(workbench, phase, mode, canonical):
    eng, project, branch = workbench
    documents = script_scientific_run(eng, project, branch, phase, mode, reference_diagnostics=phase == "P4")
    r = await eng.start_run("project.test", phase=phase, mode=mode, branch_id=branch)
    await eng._tasks[r.run_id]
    final = eng.load_run("project.test", r.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert not [f for attempt in final.findings_history for f in attempt if f["blocks_publication"]]
    directory = project / "branches" / branch / "phases" / phase.lower()
    pointers = current_records(directory)
    assert canonical in pointers
    assert {p["run_id"] for p in pointers.values()} == {r.run_id}
    assert {p["package_id"] for p in pointers.values()} == {read_json(directory / "current-package.json")["package_id"]}
    if phase == "P3":
        assert read_generation(directory, canonical, pointers[canonical])["statements"] == documents["p3.complete_theory"]["statements"]
        assert read_generation(directory, "claim_map", pointers["claim_map"]) == documents["p3.claim_map"]
    else:
        assert not (project / "branches" / branch / "phases" / "p3" / "current-package.json").exists()
        recorded_rows = read_generation(directory, "metrics_long", pointers["metrics_long"])
        assert [{key: value for key, value in row.items() if key != "attempt_id"} for row in recorded_rows] == [
            {key: value for key, value in row.items() if key != "attempt_id"} for row in documents["p4.metrics_long"]]
        execution = read_json(eng.run_dir("project.test", r.run_id) / "p4-execution/state.json")
        assert {row["attempt_id"] for row in recorded_rows} == {execution["ledger"][0]["attempt_id"]}
        assert read_generation(directory, "diagnostics", pointers["diagnostics"])["headline_numbers"][0]["estimate"] == 2
        collected = eng.run_dir("project.test", r.run_id) / "outputs/p4.analyst"
        authored = eng.member_workspace(r, "p4.analyst", MemberRole.DATA_ANALYST) / "diagnostics.json"
        sealed_diagnostic = next(item for item in execution["ledger"][0]["artifacts"] if item["source_path"] == "diagnostics.json")
        assert (collected / "diagnostics.json").read_bytes() == authored.read_bytes() == Path(sealed_diagnostic["path"]).read_bytes()
        reference = next(item for item in read_json(collected / "evidence.json")[0]["artifacts"] if item["artifact_id"] == "artifact.diagnostics")
        assert reference["sha256"] == hashlib.sha256(authored.read_bytes()).hexdigest()
        assert read_json(authored)["regenerated_by"] == "summarize.py"
        assert (collected / "working/data_analyst/summarize.py").is_file()


@pytest.mark.asyncio
async def test_new_report_assembly_publishes_interim_without_p3_or_p4(workbench):
    from model_forge_codex.problem_context import initialize_problem_context
    from model_forge_codex.technical_reports import CONTENT_SECTIONS
    eng, project, branch = workbench
    initialize_problem_context(project)
    catalog = Catalog(project / "contracts")
    identity = get_method(project, branch)["identity"]
    documents, files = scientific_output_documents(catalog, "P5", identity)
    basis = eng.compute_basis("project.test", "P5", branch, "p5.assembly")
    report = documents["p5.technical_report_candidate"]
    report["problem_context_ref"] = {key: basis["problem_context"][key] for key in ("revision", "sha256")}
    source = "\n\n".join(f'<a id="{key}"></a>\n## {key.replace("_", " ").capitalize()}\n\n'
        + ("No numerical analysis is available. This report is interim." if key == "numerical_analysis" else
           "The selected exact model and unknown collection conditions remain explicit. $x^2$.")
        for key in CONTENT_SECTIONS)
    pointer = report["report_artifact"]
    files[pointer["path"]] = source
    pointer["sha256"] = hashlib.sha256(source.encode()).hexdigest()
    report["representations"] = [{"information_layer": "primary_artifact", "artifact": copy.deepcopy(pointer)}]
    report["basis"] = []
    documents["p5.claim_traceability"] = []
    documents["p5.attention_items"] = []
    decision = documents["p5.decision"]
    decision.update(headline="Interim model report", current_conclusion="Relevant numerical analysis remains unavailable.",
                    strongest_evidence_ids=[])
    decision["scientific_outcome"].update(strongest_evidence_ids=[], strongest_counterevidence_ids=[])
    stage = eng.stage_plan("project.test", "P5", "p5.assembly")[0]
    writes = {**files, **{output.split(".", 1)[1] + ".json": json.dumps(documents[output]) for output in stage.writes}}
    eng.bridge.script_thread("research_lead:PROJECT:trunk", [("ok", writes)])
    run = await eng.start_run("project.test", phase="P5", mode="p5.assembly", branch_id=branch)
    await eng._tasks[run.run_id]
    final = eng.load_run("project.test", run.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    directory = project / "branches" / branch / "phases/p5"
    refs = current_records(directory)
    assert "technical_report" in refs and "manuscript" not in refs
    retained = read_generation(directory, "technical_report", refs["technical_report"])
    assert retained["completion"]["status"] == "interim"
    assert "Perform and retain relevant numerical analysis for this exact model" in retained["completion"]["missing_work"]
    retained_source = source_artifact_path(project, refs["technical_report"], retained["report_artifact"])
    assert retained_source.read_text(encoding="utf-8") == source
    assert report["report_artifact"]["path"] in retained["artifact_authored_paths"].values()


@pytest.mark.asyncio
async def test_strict_manuscript_assembly_then_fresh_review_publishes_replacement(legacy_p5_workbench):
    eng, project, branch = legacy_p5_workbench
    seed_manuscript_context(project, branch)
    for phase, mode in (("P3", "p3.theory_establishment"), ("P4", "p4.preliminary"), ("P5", "p5.assembly")):
        script_scientific_run(eng, project, branch, phase, mode)
        r = await eng.start_run("project.test", phase=phase, mode=mode, branch_id=branch)
        await eng._tasks[r.run_id]
        final = eng.load_run("project.test", r.run_id)
        assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    directory = project / "branches" / branch / "phases" / "p5"
    first = current_records(directory)["manuscript"]
    def bind_review_target(documents):
        for family in ("p5.theory_audit", "p5.empirical_audit", "p5.review_issues"):
            for issue in documents[family]:
                issue["review_basis_generation_id"] = first["generation_id"]
        report = documents["p5.outside_review"]
        report["review_basis_generation_id"] = first["generation_id"]
        for issue in report["prioritized_issues"]:
            issue["review_basis_generation_id"] = first["generation_id"]
    script_scientific_run(eng, project, branch, "P5", "p5.review_revision", transform=bind_review_target)
    reviewed = await eng.start_run("project.test", phase="P5", mode="p5.review_revision", branch_id=branch)
    # Late edits to the producing workspace must not alter the authorized packet.
    manuscript = read_generation(directory, "manuscript", first)
    source_artifact_path(project, first, manuscript["manuscript_artifact"]).write_bytes(b"LATE_UNAUTHORIZED_PAPER")
    await eng._tasks[reviewed.run_id]
    final = eng.load_run("project.test", reviewed.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    packet = read_json(eng.run_dir("project.test", reviewed.run_id) / "review-packet" / "manifest.json")
    assert packet["records"][0]["generation_id"] == first["generation_id"]
    assert "Saved scientific source:" in Path(packet["records"][0]["path"]).read_text()
    assert "LATE_UNAUTHORIZED_PAPER" not in Path(packet["records"][0]["path"]).read_text()
    assert current_records(directory)["manuscript"]["generation_id"] != first["generation_id"]
    outside = next(t for t in eng.bridge.turns if "# Independent manuscript review" in t["brief"])
    assert "Frozen scientific source files" not in outside["brief"]
    outside_home = eng.run_dir("project.test", reviewed.run_id) / "isolated/outside_reviewer/codex-home"
    assert Path(eng.bridge.threads[outside["thread_id"]]["member_home"]) == outside_home
    assert Path(outside["workspace"]).is_relative_to(eng.workspace_root(outside_home))


@pytest.mark.asyncio
async def test_strict_literature_and_method_proposal_preserve_catalog(workbench):
    from model_forge_codex.methods import list_methods
    from test_direct_workflow import p1_documents
    eng, project, branch = workbench
    original = read_json(REPO / "contracts/examples/method.example.json")
    def current_literature(outputs):
        outputs.clear()
        outputs.update(p1_documents())
        outputs["p1.research_basis"]["phase2_preparation"].pop("supplied_method", None)
    for phase, mode in (("P1", "p1.literature_update"), ("P2", "p2.full_catalog")):
        script_scientific_run(eng, project, "trunk", phase, mode,
                              proposed_method_id="method.proposed_new" if phase == "P2" else None,
                              transform=current_literature if phase == "P1" else None)
        r = await eng.start_run("project.test", phase=phase, mode=mode, branch_id="trunk")
        await eng._tasks[r.run_id]
        final = eng.load_run("project.test", r.run_id)
        assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    directory = project / "branches/trunk/phases/p2"
    pointers = current_records(directory)
    catalog = read_generation(directory, "method_catalog", pointers["method_catalog"])
    methods = {m["identity"]["stable_id"]: m for m in catalog["methods"]}
    assert methods[original["identity"]["stable_id"]] == original
    assert methods["method.proposed_new"]["lifecycle_state"] == "proposed"
    proposed = next(m for m in list_methods(project) if m["method_id"] == "method.proposed_new")
    assert not proposed["registered"]
    assert "Select an active registered method" in eng.check_readiness("project.test", "P3", "method.proposed_new")


@pytest.mark.asyncio
@pytest.mark.parametrize("drop_unrelated", [False, True])
async def test_targeted_repair_preserves_unrelated_math(workbench, drop_unrelated):
    eng, project, branch = workbench
    script_scientific_run(eng, project, branch, "P3", "p3.theory_establishment")
    first = await eng.start_run("project.test", phase="P3", mode="p3.theory_establishment", branch_id=branch)
    await eng._tasks[first.run_id]
    assert eng.load_run("project.test", first.run_id).state is RunState.PUBLISHED
    directory = project / "branches" / branch / "phases/p3"
    pointer = current_records(directory)["theory_record"]
    selected = {"branch": branch, "phase": "P3", "family": "theory_record", "generation_id": pointer["generation_id"],
                "sha256": pointer["content_sha256"], "run_id": pointer["run_id"], "object_id": "assumption.example_a1", "kind": "assumption"}
    def repair(documents):
        for output in ("p3.theory_candidate", "p3.complete_theory"):
            theory = documents[output]
            theory["assumptions"][0]["text"] += " The bound is required only on the evaluated compact domain."
            if drop_unrelated:
                theory["statements"] = [s for s in theory["statements"] if s["statement_id"] != "statement.example_def_estimator"]
                for s in theory["statements"]:
                    s["depends_on_statement_ids"] = [dep for dep in s["depends_on_statement_ids"] if dep != "statement.example_def_estimator"]
        if drop_unrelated:
            graph = documents["p3.claim_map"]
            graph["claims"] = [c for c in graph["claims"] if c["statement_id"] != "statement.example_def_estimator"]
            for c in graph["claims"]:
                c["depends_on"] = [dep for dep in c["depends_on"] if dep != "statement.example_def_estimator"]
    script_scientific_run(eng, project, branch, "P3", "p3.theory_revision", transform=repair)
    revision = await eng.start_run("project.test", phase="P3", mode="p3.theory_revision", branch_id=branch,
                                   target=selected, instructions="Clarify the first assumption's domain.")
    await eng._tasks[revision.run_id]
    final = eng.load_run("project.test", revision.run_id)
    if drop_unrelated:
        assert final.state is RunState.FAILED
        assert any(f["code"] == "theory.repair_out_of_scope" for attempt in final.findings_history for f in attempt)
        assert current_records(directory)["theory_record"] == pointer
    else:
        assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
        current = read_generation(directory, "theory_record", current_records(directory)["theory_record"])
        assert current["assumptions"][0]["text"].endswith("evaluated compact domain.")


@pytest.mark.asyncio
async def test_catalog_and_required_generation_integrity_refuse_before_launch(workbench):
    eng, project, branch = workbench
    phase = project / "branches/trunk/phases/p1"
    pointer = current_records(phase)["literature_synthesis"]
    source = generation_path(phase, "literature_synthesis", pointer)
    original = source.read_bytes()
    source.write_bytes(b'{"changed":"without publication"}')
    with pytest.raises(RunError, match="Digest mismatch"):
        await eng.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    source.write_bytes(original)
    (project / "contracts/schemas/claim-map.schema.json").write_bytes(b'{}')
    with pytest.raises(RunError, match="catalog integrity"):
        await eng.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    assert eng.bridge.turns == []


def test_readable_legacy_method_changes_survives_explicit_catalog_adoption(workbench):
    eng, project, branch = workbench
    method = read_json(REPO / "contracts/examples/method.example.json")
    publish(project, "trunk", "P2", {"method_changes": [method]}, "run.legacy.p2")
    assert eng.check_readiness("project.test", "P4", branch, "p4.preliminary") == []


@pytest.mark.asyncio
async def test_unfrozen_historical_correction_requires_a_new_run(workbench):
    eng, project, branch = workbench
    old = record(eng, branch, "run.old")
    old.state = RunState.FAILED
    old.findings_history = [[asdict(Finding("schema.required", "Missing field", "p3.complete_theory", ""))]]
    eng._save_run(old)
    with pytest.raises(RunError, match="historical run did not freeze"):
        await eng.correct("project.test", old.run_id)
    assert eng.bridge.turns == []


def test_restart_recovers_committed_publication_and_marks_interrupted_work(workbench):
    eng, project, branch = workbench
    committed = record(eng, branch, "run.committed")
    interrupted = record(eng, branch, "run.interrupted", "P4", "p4.preliminary")
    interrupted.stage_states = {"p4.execution": "running", "p4.review": "pending"}
    eng._save_run(interrupted)
    publish(project, branch, "P3", {"theory_record": {"text": "Retained"}}, committed.run_id)
    fresh = RunEngine(eng.data_root, FakeCodexBridge())
    assert set(fresh.reconcile_on_boot()) == {committed.run_id, interrupted.run_id}
    assert fresh.load_run("project.test", committed.run_id).state is RunState.PUBLISHED
    lost = fresh.load_run("project.test", interrupted.run_id)
    assert lost.state is RunState.FAILED
    assert lost.terminal_reason == "interrupted_by_restart"
    assert lost.stage_states == {"p4.execution": "failed", "p4.review": "pending"}
    assert fresh.bridge.turns == []


@pytest.mark.asyncio
async def test_failed_run_marks_active_stage_failed(workbench):
    eng, _, branch = workbench
    r = record(eng, branch, "run.failed_active")
    r.state = RunState.RUNNING
    r.stage_states = {"p3.theory": "running", "p3.review": "pending"}
    eng._save_run(r)
    await eng._fail(r, "Worker unavailable")
    assert eng.load_run("project.test", r.run_id).stage_states == {"p3.theory": "failed", "p3.review": "pending"}


@pytest.mark.asyncio
async def test_sdk_resume_after_restart_reapplies_scoped_write_settings(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from model_forge_codex.bridge import SdkCodexBridge
    calls = []
    class Transport:
        _sync = SimpleNamespace(_approval_handler=lambda *_: {"decision": "decline"})
        async def thread_resume(self, thread_id, params):
            calls.append((thread_id, params.model_dump(mode="json")))
            return SimpleNamespace(thread=SimpleNamespace(id=thread_id), model="retained-model",
                                   model_provider="openai", reasoning_effort="medium")
    class Client:
        _client = Transport()
        async def _ensure_initialized(self):
            pass
    bridge = SdkCodexBridge()
    client = Client()
    async def client_for(member_home, *, execution=None, workspace_root=None):
        return client
    monkeypatch.setattr(bridge, "_client", client_for)
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (home, ()))
    home = tmp_path / "member/codex-home"
    assert await bridge.resume_thread("persisted.thread", member_home=home)
    assert len(calls) == 1
    thread_id, parameters = calls[0]
    assert thread_id == parameters["thread_id"] == "persisted.thread"
    assert parameters["sandbox"] == "workspace-write"
    assert parameters["cwd"] == str(home.parent / "work")
    assert parameters["approval_policy"] == "never"
    assert parameters["approvals_reviewer"] is None
    assert bridge._thread_homes["persisted.thread"] == home
    assert bridge._thread_tools["persisted.thread"] is bridge._client_tools[id(client)]
