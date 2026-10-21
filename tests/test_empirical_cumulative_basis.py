"""Published claim links retain the cumulative inputs frozen at authorization."""
import base64
from copy import deepcopy
from pathlib import Path

import pytest

from model_forge_codex.domain import RunState
from model_forge_codex.literature import build_library
from model_forge_codex.research import artifacts_view
from model_forge_codex.researcher_inputs import import_input
from model_forge_codex.storage import read_json, write_json_atomic
from test_empirical_theory_context import _theory
from test_p4_integration import DECISION, continuation
from test_researcher_workbench_engine import workbench, publish, script_scientific_run


@pytest.mark.asyncio
@pytest.mark.parametrize("with_dataset", [False, True])
async def test_published_links_verify_real_cumulative_freeze_after_pause_resume(workbench, with_dataset):
    engine, project, branch = workbench
    publish(project, "trunk", "P1", {
        "literature_synthesis": {"headline": "Frozen literature"},
        "literature_library": build_library(None, [], run_id="run.literature")})
    theory = _theory(project, branch)
    theory["statements"].append({"statement_id": "statement.consistency", "text": "Consistency.",
                                 "assumption_ids": ["assumption.independent"]})
    package = publish(project, branch, "P3", {"theory_record": theory})
    input_ids = []
    if with_dataset:
        row = import_input(project, filename="cohort.csv", role="dataset",
                           content_base64=base64.b64encode(b"time,event\n3,1\n").decode(),
                           mapping={"time": "time", "event": "event"})
        input_ids = [row["input_id"]]

    def selected_data_disposition(documents):
        if with_dataset:
            documents["p4.protocol"]["data_sources"].append({
                "data_source_id": "source.selected.cohort", "label": "Selected test cohort",
                "origin": "researcher_observed", "input_ids": input_ids, "support_files": [],
                "description_markdown": "Recorded test input; no application is claimed.",
                "mapping_markdown": "The time and event columns are mapped as supplied."})
            documents["p4.analyst_synthesis"]["actual_data_application"] = {
                "status": "supplied_not_analyzed", "data_source_ids": ["source.selected.cohort"],
                "question_ids": [], "summary_markdown": "This provenance test performs no actual-data analysis."}

    script_scientific_run(engine, project, branch, "P4", "p4.preliminary", transform=selected_data_disposition)
    engine.bridge.script_by_key[f"data_analyst:P4:{branch}"].insert(0, ("p4", ({}, [DECISION])))
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch,
                                    input_ids=input_ids)
    await engine._tasks[record.run_id]
    record = engine.load_run("project.test", record.run_id)
    assert record.state == RunState.AWAITING_USER
    basis_path = engine.run_dir("project.test", record.run_id) / "basis.json"
    frozen = basis_path.read_bytes()
    basis = read_json(basis_path)
    cumulative = basis["cumulative_inputs"]["literature_library"]
    assert "document" not in cumulative and cumulative["snapshot_path"]
    await engine.continue_p4("project.test", record.run_id, **continuation(engine, record))
    await engine._tasks[record.run_id]
    final = engine.load_run("project.test", record.run_id)
    assert final.state == RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert basis_path.read_bytes() == frozen
    assert final.basis_sha256 == basis["sha256"]
    contexts = [question["theory_context"] for question in artifacts_view(project, branch)["questions"]]
    assert contexts and all(context["tested_ref"] is not None for context in contexts)
    assert {context["tested_ref"]["generation_id"] for context in contexts} == {
        package["records"]["theory_record"]["generation_id"]}

    if with_dataset:
        selected = basis["p4_inputs"]["inputs"][0]
        source = Path(selected["snapshot_path"])
        selected_bytes = source.read_bytes()
        source.write_bytes(b"changed selected data")
        assert all(question["theory_context"]["tested_ref"] is None
                   for question in artifacts_view(project, branch)["questions"])
        source.write_bytes(selected_bytes)
        changed = deepcopy(basis)
        changed["p4_inputs"]["inputs"][0]["mapping"]["time"] = "another_column"
        write_json_atomic(basis_path, changed)
        assert all(question["theory_context"]["tested_ref"] is None
                   for question in artifacts_view(project, branch)["questions"])
        basis_path.write_bytes(frozen)
        assert all(question["theory_context"]["tested_ref"] is not None
                   for question in artifacts_view(project, branch)["questions"])

    # Snapshot contents and their recorded digest remain mandatory. Neither
    # changing both nor dropping the cumulative input can bless a new basis.
    snapshot = Path(cumulative["snapshot_path"])
    original = snapshot.read_bytes()
    snapshot.write_text("{}", encoding="utf-8")
    assert all(question["theory_context"]["tested_ref"] is None
               for question in artifacts_view(project, branch)["questions"])
    cumulative["sha256"] = engine._cumulative_digest({})
    write_json_atomic(basis_path, basis)
    assert all(question["theory_context"]["tested_ref"] is None
               for question in artifacts_view(project, branch)["questions"])
    basis_path.write_bytes(frozen)
    snapshot.unlink()
    assert all(question["theory_context"]["tested_ref"] is None
               for question in artifacts_view(project, branch)["questions"])
    snapshot.write_bytes(original)
    basis["cumulative_inputs"] = {}
    write_json_atomic(basis_path, basis)
    assert all(question["theory_context"]["tested_ref"] is None
               for question in artifacts_view(project, branch)["questions"])
