"""Lead reporting notes stay separate from the exact sealed Analyst account."""
import json

import pytest

from model_forge_codex.records import generation_path, publish_package
from model_forge_codex.research import scientific_document_view
from model_forge_codex.storage import write_json_atomic


def evaluation(project, run_id, *, corrections=None, index_fields=None, lead_role="research_lead"):
    phase_dir = project / "branches/method.a/phases/p4"
    account = {"question_results": [{"question_id": "question.original", "answer_markdown": "Original endpoint 0.835254."}]}
    index = {"record_type": "empirical_evidence_index", "phase": "P4", "source_run_id": run_id,
             "reporting_corrections": corrections if corrections is not None else [
                 {"correction": "The saved endpoint rounds to 0.835253.", "source_field": "an informal position"},
                 {"correction": "Singleton timing is recorded separately.", "sealed_source_changed": False}],
             **(index_fields or {})}
    write_json_atomic(project / "runs" / run_id / "stage-plan.json", [
        {"stage_id": "p4.analyst", "roles": ["data_analyst"]},
        {"stage_id": "p4.lead", "roles": [lead_role]}])
    contents = {"analyst_synthesis": json.dumps(account).encode(), "empirical_evidence_index": json.dumps(index).encode()}
    package = publish_package(phase_dir, contents, run_id=run_id, phase="P4", branch_id="method.a",
                              metadata={"stage_ids": {"analyst_synthesis": "p4.analyst", "empirical_evidence_index": "p4.lead"}})
    return package, account, index, contents


def open_account(project, package):
    return scientific_document_view(project, "method.a", "P4", "analyst_synthesis",
                                    package["records"]["analyst_synthesis"]["generation_id"])


def test_separate_notes_preserve_authored_text_exact_entry_sources_and_original_bytes(tmp_path):
    package, account, index, contents = evaluation(tmp_path, "run.original")
    opened = open_account(tmp_path, package)
    notes = opened["lead_reporting_notes"]
    assert notes["producer_role"] == "research_lead"
    assert [note["text"] for note in notes["notes"]] == [item["correction"] for item in index["reporting_corrections"]]
    for position, note in enumerate(notes["notes"]):
        ref = note["generation_ref"]
        assert ref["family"] == "empirical_evidence_index"
        assert ref["generation_id"] == package["records"]["empirical_evidence_index"]["generation_id"]
        assert ref["package_id"] == package["package_id"] and ref["run_id"] == "run.original"
        assert ref["entry_pointer"] == f"/reporting_corrections/{position}"
        assert "question_id" not in note and "source_field" not in note
    assert opened["structured"] == account
    phase_dir = tmp_path / "branches/method.a/phases/p4"
    for family, data in contents.items():
        assert generation_path(phase_dir, family, package["records"][family]).read_bytes() == data


def test_historical_reader_never_borrows_notes_from_newer_publication(tmp_path):
    old, _, _, _ = evaluation(tmp_path, "run.original", corrections=[{"correction": "Original Lead note."}])
    new, _, _, _ = evaluation(tmp_path, "run.current", corrections=[{"correction": "Newer Lead note."}])
    assert [note["text"] for note in open_account(tmp_path, old)["lead_reporting_notes"]["notes"]] == ["Original Lead note."]
    assert [note["text"] for note in open_account(tmp_path, new)["lead_reporting_notes"]["notes"]] == ["Newer Lead note."]


@pytest.mark.parametrize("fields", [{"source_run_id": "run.other"}, {"phase": "P3"},
                                    {"record_type": "theory_audit"}, {"reporting_corrections": None}])
def test_notes_require_same_run_index_and_supported_list(tmp_path, fields):
    package, account, _, _ = evaluation(tmp_path, "run.original", index_fields=fields)
    opened = open_account(tmp_path, package)
    assert "lead_reporting_notes" not in opened
    assert opened["structured"] == account


@pytest.mark.parametrize("damage", ["other-role", "unknown-role", "other-package", "other-run", "tampered-index"])
def test_notes_require_exact_publication_and_frozen_lead_authorship(tmp_path, damage):
    role = "theorist" if damage == "other-role" else "research_lead"
    package, _, _, _ = evaluation(tmp_path, "run.original", lead_role=role)
    phase_dir = tmp_path / "branches/method.a/phases/p4"
    if damage == "unknown-role":
        (tmp_path / "runs/run.original/stage-plan.json").unlink()
    elif damage in {"other-package", "other-run"}:
        key = "package_id" if damage == "other-package" else "run_id"
        package["records"]["empirical_evidence_index"][key] = "package.other" if key == "package_id" else "run.other"
        write_json_atomic(phase_dir / "current-package.json", package)
    elif damage == "tampered-index":
        generation_path(phase_dir, "empirical_evidence_index", package["records"]["empirical_evidence_index"]).write_bytes(b"{}")
    assert "lead_reporting_notes" not in open_account(tmp_path, package)


def test_absent_or_empty_notes_leave_records_alone_and_invalid_entries_keep_exact_positions(tmp_path):
    package, _, _, _ = evaluation(tmp_path, "run.empty", corrections=[])
    assert "lead_reporting_notes" not in open_account(tmp_path, package)
    package, _, _, _ = evaluation(tmp_path, "run.mixed", corrections=[None, {"correction": " "}, {"correction": "A recorded note."}])
    notes = open_account(tmp_path, package)["lead_reporting_notes"]["notes"]
    assert len(notes) == 1 and notes[0]["generation_ref"]["entry_pointer"] == "/reporting_corrections/2"
    other = scientific_document_view(tmp_path, "method.a", "P4", "empirical_evidence_index",
                                     package["records"]["empirical_evidence_index"]["generation_id"])
    assert "lead_reporting_notes" not in other
