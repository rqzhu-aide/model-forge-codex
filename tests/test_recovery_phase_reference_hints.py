"""Earlier-phase recovery identifies exact permitted inputs without repairing them."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.direct_validation import validate_direct_outputs
from model_forge_codex.p1_science import entry_reference, literature_entries, validate_p1_science
from model_forge_codex.p4_validation import check_progressive_evaluation
from model_forge_codex.storage import sha256_file, write_json_atomic
from model_forge_codex.validation import validate_scientific_outputs
from test_catalog_scientific import theory_outputs
from test_cross_version_reassessment import _revision_account
from test_direct_artifacts import basis
from test_direct_workflow import p1_documents
from test_p1_science import documents, framework, library_for
from test_researcher_workbench_engine import scientific_output_documents


CATALOG = Catalog(Path(__file__).resolve().parents[1] / "contracts")


def test_recovery_p1_stale_digest_names_only_its_exact_permitted_entry():
    library = library_for(documents())
    allowed = entry_reference(literature_entries({}, library, run_id="run.next")[0])
    output = {"research_basis": basis(entry_corrections=[], scientific_review={"findings": []})}
    output["research_basis"]["landscape"]["frameworks"] = [framework(allowed)]
    assert validate_p1_science(output, library, run_id="run.next") == []
    output["research_basis"]["landscape"]["frameworks"][0]["entry_refs"][0]["entry_sha256"] = "f" * 64
    before = deepcopy((output, library))
    findings = validate_p1_science(output, library, run_id="run.next")
    assert len(findings) == 1
    result = findings[0]
    assert result.code == "literature.invalid_support_reference" and result.blocks_publication
    assert result.json_pointer == "/landscape/frameworks/0/entry_refs/0"
    assert all(str(value) in result.message for value in allowed.values())
    assert "entry_sha256" in result.message and "f" * 64 in result.message
    assert "paper.theory" not in result.message
    assert (output, library) == before
    # Similar-looking identities must remain unresolved, not acquire that hint.
    output["research_basis"]["landscape"]["frameworks"][0]["entry_refs"][0]["entry_id"] += ".unmatched"
    result = validate_p1_science(output, library, run_id="run.next")[0]
    assert result.blocks_publication and allowed["entry_sha256"] not in result.message


def test_recovery_p1_topic_names_each_bad_array_entry_and_exact_lookup_sources():
    output = p1_documents()
    library = library_for({key.removeprefix("p1."): value for key, value in output.items()}, run_id="run.frozen")
    assert validate_direct_outputs("P1", output, previous_library=library, run_id="run.next", catalog=CATALOG) == []
    topic = output["p1.research_basis"]["landscape"]["topics"][0]
    topic["source_ids"] += ["citation.first.unmatched", "citation.another.unmatched"]
    before = deepcopy((output, library))
    findings = [item for item in validate_direct_outputs("P1", output, previous_library=library,
                run_id="run.next", catalog=CATALOG) if item.code == "literature.unknown_topic_source"]
    assert [item.json_pointer for item in findings] == ["/landscape/topics/0/source_ids/1", "/landscape/topics/0/source_ids/2"]
    revision = library["sources"][0]["revisions"][-1]
    for item, unknown in zip(findings, topic["source_ids"][1:]):
        assert item.blocks_publication and unknown in item.message
        assert "p1.lead_literature/papers/0/source" in item.message
        assert "frozen literature_library/sources/0" in item.message
        assert revision["document_sha256"] in item.message and revision["run_id"] in item.message
        assert "lookup" in item.message.lower()
    assert (output, library) == before


def test_recovery_p1_topic_does_not_present_a_damaged_library_as_lookup_context():
    output = p1_documents()
    library = library_for({key.removeprefix("p1."): value for key, value in output.items()}, run_id="run.frozen")
    output["p1.research_basis"]["landscape"]["topics"][0]["source_ids"] = ["citation.unmatched"]
    library["sources"][0]["revisions"][-1]["document_sha256"] = "f" * 64
    result = next(item for item in validate_direct_outputs("P1", output, previous_library=library,
                  run_id="run.next", catalog=CATALOG) if item.code == "literature.unknown_topic_source")
    assert "f" * 64 not in result.message
    assert "frozen literature_library/sources/0" not in result.message
    assert "p1.lead_literature/papers/0/source" in result.message


@pytest.mark.parametrize("source_state", ["verified", "changed", "missing"])
def test_recovery_p3_predecessor_hint_uses_only_verified_frozen_bytes(tmp_path, source_state):
    path = tmp_path / "frozen-theory.json"
    write_json_atomic(path, {"record_id": "theory.frozen", "statements": []})
    ref = {"generation_id": "generation.predecessor", "content_sha256": sha256_file(path), "snapshot_path": str(path)}
    frozen = {"predecessor_material": {"phase": "P3", "materials": {"theory_record": ref}}}
    output = theory_outputs()
    output["p3.complete_theory"]["revision_account"] = _revision_account(ref["generation_id"])
    assert validate_scientific_outputs(CATALOG, "P3", output, frozen_basis=frozen) == []
    if source_state == "changed":
        write_json_atomic(path, {"record_id": "changed"})
    elif source_state == "missing":
        path.unlink()
    current = tmp_path / "current.json"
    write_json_atomic(current, {"generation_id": "generation.current"})
    output["p3.complete_theory"]["revision_account"]["prior_generation_id"] = "generation.unmatched"
    before = deepcopy((output, frozen))
    result = next(item for item in validate_scientific_outputs(CATALOG, "P3", output, frozen_basis=frozen)
                  if item.code == "theory.revision_account_source")
    assert result.json_pointer == "/revision_account/prior_generation_id" and result.blocks_publication
    assert "generation.unmatched" in result.message
    assert ref["generation_id"] in result.message
    if source_state == "verified":
        assert str(path) in result.message and ref["content_sha256"] in result.message
    else:
        assert str(path) not in result.message and "verified" in result.message.lower()
    assert str(current) not in result.message and "generation.current" not in result.message
    assert (output, frozen) == before


@pytest.mark.parametrize("field,registry,id_key", [
    ("question_ids", "claim_tests", "test_id"),
    ("case_ids", "cases", "case_id"),
    ("depends_on", "work_items", "work_item_id"),
])
@pytest.mark.parametrize("amended", [False, True])
def test_recovery_p4_work_reference_points_to_the_authored_array_and_registry(field, registry, id_key, amended):
    # Reuse the current schema-valid protocol fixture, including its real tests.
    identity = json.loads((CATALOG.root / "examples/method.example.json").read_text())["identity"]
    output, _ = scientific_output_documents(CATALOG, "P4", identity, mode="p4.preliminary")
    protocol = output["p4.protocol"]
    assert CATALOG.validate_output("p4.protocol", protocol) == []
    findings = []
    check_progressive_evaluation({"p4.protocol": protocol}, findings)
    assert findings == []
    work = protocol["work_items"][0]
    prefix = "/work_items/0"
    if amended:
        work = deepcopy(work)
        work["work_item_id"] = "work.amended"
        protocol["amendments"] = [{"revision_id": "plan.amended", "supersedes_revision_id": protocol["plan_revision_id"],
                                    "created_at": "2026-10-02T00:00:00Z", "reason_markdown": "Add a declared verification work item.",
                                    "observed_evidence_ids": [], "changes_markdown": "Append the work item prospectively.",
                                    "inferential_consequences_markdown": "No existing result is changed.", "deferred_work_item_ids": [],
                                    "added_work_items": [work]}]
        prefix = "/amendments/0/added_work_items/0"
        assert CATALOG.validate_output("p4.protocol", protocol) == []
        check_progressive_evaluation({"p4.protocol": protocol}, findings)
        assert findings == []
    work[field] = ["reference.unmatched"]
    before = deepcopy(protocol)
    findings = []
    check_progressive_evaluation({"p4.protocol": protocol}, findings)
    result = next(item for item in findings if item.code == "empirical.work_reference")
    assert result.json_pointer == prefix + "/" + field + "/0" and result.blocks_publication
    assert "reference.unmatched" in result.message
    assert "/" + registry + "/0/" + id_key in result.message
    assert protocol[registry][0][id_key] in result.message
    assert protocol == before
