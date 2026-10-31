"""Notation definitions cite scientific fields and malformed authoring is repairable."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import RunState
from model_forge_codex.notation import _resolve_source, validate_notation_updates
from model_forge_codex.records import ArtifactError, current_records
from model_forge_codex.storage import read_json, write_json_atomic
from test_notation_lifecycle import account, basis, entry, updates
from test_researcher_workbench_engine import record, script_scientific_run, workbench


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("family", ["attention_items", "phase2_handoff", "decision", "review_issue_ledger"])
def test_current_output_references_cannot_bypass_restricted_family_check(tmp_path, family):
    output_id = "p1." + family
    reference = {"output_id": output_id, "pointer": "/scientific_definition"}
    current = {output_id: ({"scientific_definition": "Restricted material."}, "p1.synthesis")}
    with pytest.raises(ArtifactError, match="Restricted researcher directions"):
        _resolve_source(tmp_path, tmp_path / "runs/run.current", basis(), reference, current)


@pytest.mark.parametrize("pointer", ["/notation_updates/entries/0/definition_markdown", "/notation_snapshot"])
def test_current_and_committed_definitions_cannot_cite_notation_itself(tmp_path, pointer):
    reference, _, document = account(tmp_path)
    current_ref = {"output_id": "p1.research_basis", "pointer": pointer}
    committed_ref = {**reference, "pointer": pointer}
    current = {"p1.research_basis": (document, "p1.synthesis")}
    admitted = basis(refs=[reference])
    for source in (current_ref, committed_ref):
        with pytest.raises(ArtifactError, match="scientific field, not notation"):
            _resolve_source(tmp_path, tmp_path / "runs/run.new", admitted, source, current)


def test_incoming_committed_view_is_not_a_definition_self_citation(tmp_path):
    reference, _, document = account(tmp_path)
    admitted = basis(refs=[reference])
    snapshot_ref = {**reference, "pointer": "/notation_snapshot"}
    resolved = _resolve_source(tmp_path, tmp_path / "runs/run.new", admitted, snapshot_ref, {}, incoming=True)
    assert resolved["generation_id"] == reference["generation_id"]
    # The same committed account still supplies its actual scientific field.
    scientific = {**reference, "pointer": "/scientific_definition"}
    assert _resolve_source(tmp_path, tmp_path / "runs/run.new", admitted, scientific, {})["pointer"] == "/scientific_definition"
    with pytest.raises(ArtifactError, match="shared scientific field"):
        _resolve_source(tmp_path, tmp_path / "runs/run.new", admitted, {**reference, "pointer": ""}, {})


def malformed_updates(case):
    document = updates([entry()])
    if case == "root":
        return "not an update object"
    if case == "entry":
        document["entries"] = ["not an entry"]
    elif case == "retirement":
        document["retirements"] = [{}]
    elif case == "mapping":
        document["entries"][0]["source_symbol_mapping"] = {}
    elif case == "replaces":
        document["entries"][0]["replaces"] = "not an entry reference"
    else:
        document["entries"][0]["scope"] = "study"
    return document


@pytest.mark.parametrize("case", ["root", "entry", "retirement", "mapping", "replaces", "scope"])
def test_canonical_schema_reports_malformed_updates_before_nested_access(workbench, case):
    engine, project, branch = workbench
    document = {"notation_updates": malformed_updates(case)}
    catalog = Catalog(project / "contracts")
    with pytest.raises(ArtifactError, match="frozen schema at /notation_updates"):
        validate_notation_updates(catalog, document)
    run = record(engine, branch, "run.malformed", "P3", "p3.theory_establishment")
    directory = engine.run_dir(run.project_id, run.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    write_json_atomic(directory / "basis.json", engine.compute_basis(run.project_id, "P3", branch, run.mode))
    output_id = "p3.complete_theory"
    findings = engine._notation_findings(run, {output_id: document}, {output_id: directory / "outputs/p3.lead"})
    assert len(findings) == 1 and findings[0].code == "notation.invalid_account"
    assert "frozen schema at /notation_updates" in findings[0].message
    assert not (project / "branches" / branch / "phases/p3/current-package.json").exists()


def test_update_shape_validation_uses_the_frozen_producing_schema(workbench):
    engine, project, branch = workbench
    run = record(engine, branch, "run.frozen_shape", "P3", "p3.theory_establishment")
    directory = engine.run_dir(run.project_id, run.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    write_json_atomic(directory / "basis.json", engine.compute_basis(run.project_id, "P3", branch, run.mode))
    schema_path = project / "contracts/schemas/notation-updates.schema.json"
    changed = read_json(schema_path)
    changed["properties"]["entries"]["items"] = {}
    write_json_atomic(schema_path, changed)
    document = {"notation_updates": malformed_updates("entry")}
    validate_notation_updates(Catalog(project / "contracts"), document)
    output_id = "p3.complete_theory"
    findings = engine._notation_findings(run, {output_id: document}, {output_id: directory / "outputs/p3.lead"})
    assert len(findings) == 1 and "frozen schema" in findings[0].message


@pytest.mark.asyncio
async def test_malformed_lead_update_gets_normal_repair_and_publishes_only_corrected_bytes(workbench):
    engine, project, _ = workbench
    from test_direct_workflow import p1_documents

    def authored(outputs):
        outputs.clear()
        outputs.update(p1_documents())

    script_scientific_run(engine, project, "trunk", "P1", "p1.literature_update", transform=authored)
    queue = engine.bridge.script_by_key["research_lead:PROJECT:trunk"]
    corrected = deepcopy(queue[-1][1])
    broken = json.loads(queue[-1][1]["research_basis.json"])
    broken["notation_updates"]["entries"] = ["malformed entry"]
    queue[-1][1]["research_basis.json"] = json.dumps(broken)
    queue.append(("ok", corrected))
    run = await engine.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    await engine._tasks[run.run_id]
    final = engine.load_run("project.test", run.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert sum(final.mechanical_repair_attempts.values()) >= 1
    pointer = current_records(project / "branches/trunk/phases/p1")["research_basis"]
    saved = read_json(project / "runs" / run.run_id / "outputs" / pointer["stage_id"] / "research_basis.json")
    assert saved["notation_updates"]["entries"] == []
    assert saved["notation_snapshot"]
