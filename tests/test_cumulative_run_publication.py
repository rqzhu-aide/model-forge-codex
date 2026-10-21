"""Cumulative research is exercised through real run validation/publication."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from model_forge_codex.domain import RunState
from model_forge_codex.literature import build_library
from model_forge_codex.records import ArtifactError, current_records, generation_path, read_generation
from model_forge_codex.runs import RunError
from model_forge_codex.storage import read_json, write_json_atomic
from test_direct_workflow import p1_documents
from test_researcher_workbench_engine import (
    REPO, publish, script_scientific_run, seed_manuscript_context, workbench,
)


def source(identifier, doi, *, title=None):
    document = read_json(REPO / "contracts/examples/literature-source.example.json")
    document.update(source_id=identifier, record_id="record." + identifier,
                    title=title or "An interacting Langevin research source",
                    identifiers=[{"kind": "doi", "value": doi}])
    return document


def direct_p1(documents):
    outputs = p1_documents(tuple(document["source_id"] for document in documents))
    for entry, document in zip(outputs["p1.lead_literature"]["papers"], documents):
        entry["source"] = deepcopy(document)
    if not documents:
        outputs["p1.research_basis"]["landscape"]["topics"] = []
    return outputs


def script_p1(engine, project, documents):
    def change(outputs):
        outputs.clear()
        outputs.update(direct_p1(documents))
    script_scientific_run(engine, project, "trunk", "P1", "p1.literature_update", transform=change)


async def run(engine, phase="P1", mode="p1.literature_update", branch="trunk"):
    started = await engine.start_run("project.test", phase=phase, mode=mode, branch_id=branch)
    await engine._tasks[started.run_id]
    return engine.load_run("project.test", started.run_id)


def library(project):
    directory = project / "branches/trunk/phases/p1"
    pointers = current_records(directory)
    return read_generation(directory, "literature_library", pointers["literature_library"])


async def test_two_successful_p1_runs_preserve_sources_deduplicate_and_leave_changes_immutable(workbench):
    engine, project, _ = workbench
    first_sources = [source("citation.first", "10.1234/first"), source("citation.second", "10.1234/second")]
    script_p1(engine, project, first_sources)
    first = await run(engine)
    assert first.state is RunState.PUBLISHED, (first.terminal_reason, first.findings_history)
    directory = project / "branches/trunk/phases/p1"
    first_pointer = current_records(directory)["lead_literature"]
    first_generation = generation_path(directory, "lead_literature", first_pointer)
    first_bytes = first_generation.read_bytes()
    collected = engine.run_dir("project.test", first.run_id) / "outputs/p1.discovery/lead_literature.json"
    collected_bytes = collected.read_bytes()

    following = [source("citation.rediscovered", "https://doi.org/10.1234/FIRST"),
                 source("citation.third", "10.1234/third")]
    script_p1(engine, project, following)
    second = await run(engine)
    assert second.state is RunState.PUBLISHED, (second.terminal_reason, second.findings_history)
    result = library(project)
    assert result["total_sources"] == 3
    assert {entry["source_id"] for entry in result["sources"]} == {"citation.first", "citation.second", "citation.third"}
    first_entry = next(entry for entry in result["sources"] if entry["source_id"] == "citation.first")
    assert set(first_entry["source_ids"]) == {"citation.first", "citation.rediscovered"}
    assert {revision["run_id"] for revision in first_entry["revisions"]} == {first.run_id, second.run_id}
    current_finding = first_entry["assessments"][0]
    assert current_finding["family"] == "lead_literature"
    assert current_finding["run_id"] == second.run_id
    assert current_finding["entry"]["source"]["source_id"] == "citation.rediscovered"
    assert current_finding["assessment_history"][0]["run_id"] == first.run_id
    assert first_generation.read_bytes() == first_bytes and collected.read_bytes() == collected_bytes
    latest_changes = read_generation(directory, "source_changes", current_records(directory)["source_changes"])
    assert {entry["source_id"] for entry in latest_changes} == {"citation.rediscovered", "citation.third"}
    basis = read_json(engine.run_dir("project.test", second.run_id) / "basis.json")
    frozen = basis["cumulative_inputs"]["literature_library"]
    frozen_library = read_json(Path(frozen["snapshot_path"]))
    assert frozen_library["total_sources"] == 2
    assert frozen_library["sources"][0]["assessments"][0]["entry"]["formulation_markdown"] == json.loads(collected_bytes)["papers"][0]["formulation_markdown"]
    second_briefs = [turn["brief"] for turn in engine.bridge.turns if str(second.run_id) in turn["brief"]]
    navigation = engine.run_dir("project.test", second.run_id) / "inputs/literature-context"
    indexes = list(navigation.glob("p1.discovery/*/*/index.json"))
    assert len(indexes) == 3 and second_briefs
    expected = {assessment["entry"]["entry_id"]: assessment["entry"]
                for entry in frozen_library["sources"] for assessment in entry.get("assessments", [])}
    for index_path in indexes:
        assert any(str(index_path) in brief for brief in second_briefs)
        index = read_json(index_path)
        rows = [row for page in index["pages"] for row in read_json(index_path.parent / page["path"])["entries"]]
        assert index["unique_source_count"] == 2 and index["assessment_count"] == len(expected)
        assert {row["source_id"] for row in rows} == {"citation.first", "citation.second"}
        assert {row["reference"]["run_id"] for row in rows} == {first.run_id}
        assert {row["reference"]["entry_id"]: read_json(index_path.parent / row["entry_path"])["entry"] for row in rows} == expected
    lead_index = next(navigation.glob("p1.lead_synthesis/*/*/index.json"))
    lead_navigation = read_json(lead_index)
    lead_rows = [row for page in lead_navigation["pages"] for row in read_json(lead_index.parent / page["path"])["entries"]]
    assert lead_navigation["unique_source_count"] == 3
    assert {row["reference"]["entry_id"]: read_json(lead_index.parent / row["entry_path"])["entry"] for row in lead_rows} == {
        assessment["entry"]["entry_id"]: assessment["entry"] for entry in result["sources"] for assessment in entry.get("assessments", [])}


async def test_conflicting_p1_source_identity_fails_before_any_current_record_changes(workbench):
    engine, project, _ = workbench
    script_p1(engine, project, [source("citation.first", "10.1234/first")])
    first = await run(engine)
    assert first.state is RunState.PUBLISHED, first.findings_history
    directory = project / "branches/trunk/phases/p1"
    before = (directory / "current-package.json").read_bytes()
    script_p1(engine, project, [source("citation.first", "10.1234/unrelated")])
    failed = await run(engine)
    assert failed.state is RunState.FAILED
    assert any(finding["code"] == "output.cumulative_conflict" for attempt in failed.findings_history for finding in attempt)
    assert (directory / "current-package.json").read_bytes() == before
    assert library(project)["total_sources"] == 1


async def test_cumulative_merge_uses_authorized_snapshot_and_rejects_snapshot_tamper(workbench, monkeypatch):
    engine, project, _ = workbench
    script_p1(engine, project, [source("citation.first", "10.1234/first")])
    first = await run(engine)
    assert first.state is RunState.PUBLISHED, first.findings_history
    async def hold(_record, _stages):
        await asyncio.Event().wait()
    monkeypatch.setattr(engine, "_drive", hold)
    started = await engine.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    try:
        later = build_library(library(project), [source("citation.later", "10.1234/later")], run_id="run.concurrent")
        publish(project, "trunk", "P1", {"literature_library": later}, run_id="run.concurrent")
        requested = {key.split(".", 1)[1]: document for key, document in direct_p1([source("citation.requested", "10.1234/requested")]).items()}
        derived = engine._cumulative_outputs(started, requested)
        assert {entry["source_id"] for entry in derived["literature_library"]["sources"]} == {"citation.first", "citation.requested"}
        with pytest.raises(RunError, match="Current research changed"):
            engine._assert_publication_current(started)
        basis = read_json(engine.run_dir("project.test", started.run_id) / "basis.json")
        snapshot = Path(basis["cumulative_inputs"]["literature_library"]["snapshot_path"])
        write_json_atomic(snapshot, later)
        with pytest.raises(ArtifactError, match="frozen literature_library changed"):
            engine._cumulative_outputs(started, {"lead_literature": {"papers": []}})
    finally:
        await engine.cancel("project.test", started.run_id)


async def test_p5_assembly_preserves_preceding_review_issues_and_original_manuscript_basis(legacy_p5_workbench):
    engine, project, branch = legacy_p5_workbench
    seed_manuscript_context(project, branch)
    for phase, mode in (("P3", "p3.theory_establishment"), ("P4", "p4.preliminary"), ("P5", "p5.assembly")):
        script_scientific_run(engine, project, branch, phase, mode)
        completed = await run(engine, phase, mode, branch)
        assert completed.state is RunState.PUBLISHED, (completed.terminal_reason, completed.findings_history)
    directory = project / "branches" / branch / "phases/p5"
    reviewed_manuscript = current_records(directory)["manuscript"]["generation_id"]
    def open_issue(outputs):
        for item in outputs["p5.review_issues"]:
            item.update(disposition="open", review_basis_generation_id=reviewed_manuscript)
        for family in ("p5.theory_audit", "p5.empirical_audit"):
            for finding in outputs[family]:
                finding["review_basis_generation_id"] = reviewed_manuscript
        report = outputs["p5.outside_review"]
        report["review_basis_generation_id"] = reviewed_manuscript
        for finding in report["prioritized_issues"]:
            finding["review_basis_generation_id"] = reviewed_manuscript
    script_scientific_run(engine, project, branch, "P5", "p5.review_revision", transform=open_issue)
    reviewed = await run(engine, "P5", "p5.review_revision", branch)
    assert reviewed.state is RunState.PUBLISHED, (reviewed.terminal_reason, reviewed.findings_history)
    pointer = current_records(directory)["review_issues"]
    issues = read_generation(directory, "review_issues", pointer)
    script_scientific_run(engine, project, branch, "P5", "p5.assembly")
    assembled = await run(engine, "P5", "p5.assembly", branch)
    assert assembled.state is RunState.PUBLISHED, (assembled.terminal_reason, assembled.findings_history)
    current = current_records(directory)
    assert "review_issues" not in current
    ledger = read_generation(directory, "review_issue_ledger", current["review_issue_ledger"])
    assert ledger["issues"] == issues
    assert all(item["disposition"] == "open" and item["review_basis_generation_id"] == reviewed_manuscript for item in ledger["issues"])
    assert ledger["issue_sources"][issues[0]["issue_id"]]["generation_id"] == pointer["generation_id"]
    basis = read_json(engine.run_dir("project.test", assembled.run_id) / "basis.json")
    frozen = basis["cumulative_inputs"]["review_issue_ledger"]["snapshot_path"]
    assert read_json(Path(frozen))["issues"] == issues
