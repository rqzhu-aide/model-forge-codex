"""Carried questions cite the retained P1 assessment, never a newer alias."""
from copy import deepcopy

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.literature import _digest
from model_forge_codex.research import artifacts_view
from model_forge_codex.service import create_app
from test_direct_artifacts import collection, paper
from test_direct_workflow import PID, direct_engine
from test_literature import source
from test_literature_projection import publish
from test_p1_science import library_for


def publication(project, run_id, title):
    entry = paper(source(run_id=run_id, title=title))
    documents = {"lead_literature": collection(entry)}
    library = library_for(documents, run_id=run_id)
    package = publish(project, {**documents, "literature_library": library}, run_id)
    binding = {"source_id": entry["source"]["source_id"], "entry_ref": {
        "role": "research_lead", "family": "lead_literature", "run_id": run_id,
        "entry_id": entry["entry_id"], "entry_sha256": _digest(entry)}}
    return package, entry, binding


def question(project, binding, branch="method.a"):
    item = {"issue_id": "question.observation", "kind": "researcher_decision",
            "question": "Which observations are available?", "target_phase": "P1",
            "context_markdown": "See [Original author](#cite:citation.first).",
            "source_refs": [binding]}
    publish(project, {"analyst_audit": {"issues": [item]}}, "run.question", "P3", branch)
    return item


def test_carried_question_keeps_old_bibliography_and_exact_source_despite_new_alias(tmp_path):
    original, entry, binding = publication(tmp_path, "run.old", "Original cited paper")
    publication(tmp_path, "run.new", "New paper with the same local source ID")
    question(tmp_path, binding)
    question(tmp_path, binding, branch="method.other")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    issues = artifacts_view(tmp_path, "method.a")["issues"]

    assert len(issues) == 1 and issues[0]["branch"] == "method.a"
    citation = issues[0]["citations"][0]
    assert citation["status"] == "available"
    assert citation["entry_ref"] == binding["entry_ref"]
    assert citation["bibliography"] == entry["source"]
    exact = citation["card"]["generation_ref"]
    assert exact["run_id"] == "run.old" and exact["branch"] == "trunk" and exact["phase"] == "P1"
    assert exact["family"] == "literature_library"
    assert exact["generation_id"] == original["records"]["literature_library"]["generation_id"]
    assert exact["sha256"] == original["records"]["literature_library"]["content_sha256"]
    assert exact["entry_pointer"] == citation["card"]["entry_pointer"] == "/sources/0/assessments/0/entry"
    assert before == {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}


@pytest.mark.parametrize("field", ["source_id", "role", "family", "run_id", "entry_id", "entry_sha256"])
def test_question_citation_requires_every_exact_identity_field(tmp_path, field):
    _, _, binding = publication(tmp_path, "run.old", "Original cited paper")
    if field == "source_id":
        binding[field] = "citation.unrelated"
    else:
        binding["entry_ref"][field] = "0" * 64 if field == "entry_sha256" else "unmatched"
    question(tmp_path, binding)

    citation = artifacts_view(tmp_path, "method.a")["issues"][0]["citations"][0]

    assert citation["status"] == "unavailable"
    assert "card" not in citation and "bibliography" not in citation


def test_question_does_not_borrow_a_matching_source_from_another_project(tmp_path):
    _, _, binding = publication(tmp_path / "project.other", "run.old", "Other project's paper")
    question(tmp_path / "project.current", binding)

    citation = artifacts_view(tmp_path / "project.current", "method.a")["issues"][0]["citations"][0]

    assert citation["status"] == "unavailable" and "card" not in citation


def test_missing_older_p1_package_keeps_question_readable_with_unavailable_citation(tmp_path):
    original, _, binding = publication(tmp_path, "run.old", "Original cited paper")
    publication(tmp_path, "run.new", "Newer retained paper")
    item = question(tmp_path, binding)
    package_path = (tmp_path / "branches" / "trunk" / "phases" / "p1" / "packages"
                    / f"{original['package_id']}.json")
    package_path.unlink()

    issues = artifacts_view(tmp_path, "method.a")["issues"]

    assert len(issues) == 1 and issues[0]["question"] == item["question"]
    assert issues[0]["context_markdown"] == item["context_markdown"]
    citation = issues[0]["citations"][0]
    assert citation["status"] == "unavailable" and "card" not in citation
    assert citation["entry_ref"] == binding["entry_ref"]


@pytest.mark.parametrize("damage", ["entry_content", "duplicate", "missing_library"])
def test_question_citation_does_not_guess_past_invalid_or_ambiguous_snapshot(tmp_path, damage):
    entry = paper(source(run_id="run.old"))
    documents = {"lead_literature": collection(entry)}
    library = library_for(documents, run_id="run.old")
    binding = {"source_id": "citation.first", "entry_ref": {
        key: library["sources"][0]["assessments"][0][key]
        for key in ("role", "family", "run_id", "entry_sha256")}}
    binding["entry_ref"]["entry_id"] = entry["entry_id"]
    if damage == "entry_content":
        library["sources"][0]["assessments"][0]["entry"]["source"]["title"] = "Changed without updating entry digest"
    elif damage == "duplicate":
        library["sources"].append(deepcopy(library["sources"][0]))
    if damage != "missing_library":
        documents["literature_library"] = library
    publish(tmp_path, documents, "run.old")
    question(tmp_path, binding)

    citation = artifacts_view(tmp_path, "method.a")["issues"][0]["citations"][0]

    assert citation["status"] == "unavailable" and "card" not in citation


@pytest.mark.parametrize("with_binding", [False, True])
async def test_p3_text_source_refs_keep_artifacts_and_decision_inbox_readable(direct_engine, with_binding):
    engine, project = direct_engine
    _, entry, binding = publication(project, "run.old", "Original cited paper")
    # P3 audits also retain authored record IDs and manuscript locations.
    # Put a structured citation first to exercise the per-issue scan as well
    # as the early no-citations path when only text references are present.
    references = ([binding] if with_binding else []) + [
        "review.empirical.burden", "theory_manuscript.md:Section 3",
    ]
    item = {"issue_id": "issue.protocol", "statement": "Declare the burden comparison protocol.",
            "severity": "major", "source_refs": references}
    publish(project, {"analyst_audit": {"issues": [item]}}, "run.p3", "P3", "method.a")
    before = {path: path.read_bytes() for path in (project / "branches").rglob("*") if path.is_file()}
    app = create_app(engine.data_root, engine.bridge)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        artifacts = await client.get(f"/api/v1/projects/{PID}/artifacts")
        assert artifacts.status_code == 200
        pending = await client.get(f"/api/v1/projects/{PID}/decisions-pending")
        assert pending.status_code == 200

    issue = next(row for row in artifacts.json()["issues"] if row["object_id"] == item["issue_id"])
    assert issue["source_refs"] == references
    if with_binding:
        assert len(issue["citations"]) == 1
        citation = issue["citations"][0]
        assert citation["status"] == "available"
        assert citation["entry_ref"] == binding["entry_ref"]
        assert citation["bibliography"] == entry["source"]
        assert citation["card"]["generation_ref"]["run_id"] == "run.old"
    else:
        assert "citations" not in issue
    assert before == {path: path.read_bytes() for path in (project / "branches").rglob("*") if path.is_file()}
