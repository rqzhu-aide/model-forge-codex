"""Real member/publication checks over labeled fixtures, without model turns."""
import copy
import hashlib
import runpy
import shutil

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole
from model_forge_codex.runs import owned_writes
from model_forge_codex.storage import read_json, write_json_atomic
from model_forge_codex.validation import validate_scientific_outputs
from test_draft_validation import REPO, check, draft_engine, run, write_outputs
from test_researcher_workbench_engine import scientific_output_documents

SID = "statement.example_consistency"
CAPABILITY = "p3.conservative_assessment_v1"


def pin(engine, enabled, version=None):
    root = engine.project_dir("project.draft") / "contracts"
    path = root / "contracts/phases/P3.json"
    contract = read_json(path)
    contract["capabilities"] = [cap for cap in contract.get("capabilities", []) if cap != CAPABILITY]
    if enabled:
        contract["capabilities"].append(CAPABILITY)
    write_json_atomic(path, contract)
    if version:
        current = read_json(root / "catalog-pin.json")
        write_json_atomic(root / "catalog-pin.json", {**current, "catalog_version": version})
    runpy.run_path(str(REPO / "contracts/refresh_manifest.py"))["refresh"](root)


def case(engine, *, enabled=True, version=None):
    pin(engine, enabled, version=version)
    record, stages, identity = run(engine, "P3", "p3.theory_establishment")
    documents, files = scientific_output_documents(engine._catalog(record), "P3", identity)
    documents["p3.analyst_audit"].pop("issues", None)
    documents["p3.analyst_handoff"]["unresolved_issues"] = []
    documents["p3.decision"].pop("assessment_changes", None)
    documents["p3.decision"].pop("issue_dispositions", None)
    return record, stages, documents, files


def statement(documents, family):
    return next(row for row in documents[family]["statements"] if row["statement_id"] == SID)


def original_status(documents, status):
    original = statement(documents, "p3.theory_candidate")
    original["status"] = status
    if status in {"incomplete", "untested"}:
        original["justification"] = {"kind": "open_obligation", "summary": "Fixture only: unresolved argument.",
                                     "artifacts": [], "open_obligation": "Check the argument under the stated scope."}
    elif status == "contradicted":
        original["justification"]["kind"] = "counterexample"
    elif status == "retracted":
        original["justification"] = {"kind": "not_applicable", "summary": "Fixture only: withdrawn.", "artifacts": []}
    statement(documents, "p3.complete_theory").update(copy.deepcopy(original))
    claim = next(row for row in documents["p3.claim_map"]["claims"] if row["statement_id"] == SID)
    claim.update(scientific_status=status, proof_status="full" if status in {"established", "conditional"} else "missing")


def concern(documents, component=SID):
    documents["p3.decision"]["assessment_changes"] = [{
        "component_id": component, "origin": "lead_concern",
        "reason": "Fixture only: the Lead's concern has not received independent Analyst review.",
    }]


def issue(documents):
    concern = {"issue_id": "issue.fixture.scope", "category": "scope", "severity": "major",
               "statement": "Fixture only: an independent scope concern.", "consequence": "The concern remains open.",
               "component_ids": [SID]}
    documents["p3.analyst_handoff"]["unresolved_issues"] = [concern]
    documents["p3.decision"]["issue_dispositions"] = [{
        "issue_id": concern["issue_id"], "status": "unresolved", "reason": "Fixture only: future investigation is needed."}]
    return concern


def counterexample(documents, *, kind="counterexample"):
    target = issue(documents)
    content = "Structural fixture only: Analyst counterexample bytes, no theorem truth asserted.\n"
    path = "sources/analyst_counterexample.md"
    target["justification"] = {"kind": kind, "summary": "Fixture only: exact Analyst negative support.",
        "artifacts": [{"artifact_id": "artifact.fixture.counterexample", "uri": "artifact://artifact.fixture.counterexample",
                       "path": path, "sha256": hashlib.sha256(content.encode()).hexdigest(), "media_type": "text/markdown"}]}
    statement(documents, "p3.complete_theory").update(status="contradicted", justification=copy.deepcopy(target["justification"]))
    documents["p3.decision"]["assessment_changes"] = [{
        "component_id": SID, "origin": "analyst_issue", "issue_id": target["issue_id"],
        "reason": "Fixture only: the exact retained Analyst support defeats the stated guarantee."}]
    return {path: content}


def actual_check(engine, prepared, *, analyst_files=None, role=MemberRole.RESEARCH_LEAD, final=False):
    record, stages, documents, files = prepared
    selected = stages[-1] if role is MemberRole.RESEARCH_LEAD else stages[1]
    for stage in stages:
        if stage.sequence >= selected.sequence and not final:
            continue
        root = engine.run_dir(record.project_id, record.run_id) / "outputs" / stage.stage_id
        stage_files = {**files, **(analyst_files or {})} if stage.stage_id == "p3.analyst" else files
        write_outputs(root, {output: documents[output] for output in stage.writes}, stage_files)
        record.stage_states[stage.stage_id] = "succeeded"
    engine._save_run(record)
    if final:
        findings = engine._validate_run_outputs(record, stages)
        result = {"status": "failed" if any(row.blocks_publication for row in findings) else "passed",
                  "findings": [{"code": row.code} for row in findings]}
    else:
        write_outputs(engine.member_workspace(record, selected.stage_id, role),
                      {output: documents[output] for output in owned_writes(selected, role)},
                      {**files, **(analyst_files or {})} if role is MemberRole.DATA_ANALYST else files)
        result = check(engine, record, selected, role)
    assert engine.bridge.turns == []
    return result


def codes(result):
    return {finding["code"] for finding in result["findings"]}


@pytest.mark.parametrize(("old", "new"), [
    ("established", "conditional"), ("established", "incomplete"), ("conditional", "incomplete"),
    ("untested", "incomplete"), ("established", "retracted"), ("conditional", "retracted"),
    ("untested", "retracted"), ("incomplete", "retracted"),
    ("contradicted", "retracted"), ("retracted", "retracted"),
])
def test_real_lead_accepts_conservative_assessment_without_new_argument(draft_engine, old, new):
    prepared = case(draft_engine)
    documents = prepared[2]
    original_status(documents, old)
    original = copy.deepcopy(statement(documents, "p3.theory_candidate"))
    statement(documents, "p3.complete_theory")["status"] = new
    if old != new:
        concern(documents)
    result = actual_check(draft_engine, prepared)
    assert result["status"] == "passed", result["findings"]
    assert statement(documents, "p3.theory_candidate") == original
    assert statement(documents, "p3.complete_theory")["justification"] == original["justification"]


@pytest.mark.parametrize("kind", ["counterexample", "empirical_evidence"])
@pytest.mark.parametrize("final", [False, True])
def test_real_lead_and_publication_gate_accept_exact_analyst_support(draft_engine, kind, final):
    prepared = case(draft_engine)
    analyst_files = counterexample(prepared[2], kind=kind)
    result = actual_check(draft_engine, prepared, analyst_files=analyst_files, final=final)
    assert result["status"] == "passed", result["findings"]
    lead = draft_engine.member_workspace(prepared[0], prepared[1][-1].stage_id, MemberRole.RESEARCH_LEAD)
    assert not (lead / "sources/analyst_counterexample.md").exists()


@pytest.mark.parametrize(("old", "new"), [
    ("incomplete", "established"), ("untested", "established"), ("incomplete", "conditional"),
    ("contradicted", "established"), ("contradicted", "conditional"), ("contradicted", "incomplete"),
    ("retracted", "established"), ("retracted", "conditional"), ("retracted", "incomplete"),
    ("established", "untested"),
])
def test_real_lead_rejects_positive_promotion_and_rehabilitation(draft_engine, old, new):
    prepared = case(draft_engine)
    documents = prepared[2]
    positive_support = copy.deepcopy(statement(documents, "p3.theory_candidate")["justification"])
    original_status(documents, old)
    statement(documents, "p3.complete_theory")["status"] = new
    if new == "established":
        statement(documents, "p3.complete_theory")["justification"] = positive_support
    concern(documents)
    assert "theory.unaudited_assessment_change" in codes(actual_check(draft_engine, prepared))


@pytest.mark.parametrize("mutation", ["text", "type", "dependencies", "remove_claim", "assumption_text", "remove_assumption", "new_proof"])
def test_real_lead_rejects_unaudited_mathematics_or_argument(draft_engine, mutation):
    prepared = case(draft_engine)
    documents = prepared[2]
    complete = documents["p3.complete_theory"]
    current = statement(documents, "p3.complete_theory")
    if mutation == "text": current["text"] += " Stronger claim."
    if mutation == "type": current["statement_type"] = "definition"
    if mutation == "dependencies": current["assumption_ids"] = []
    if mutation == "remove_claim": complete["statements"].remove(current)
    if mutation == "assumption_text": complete["assumptions"][0]["text"] += " Stronger condition."
    if mutation == "remove_assumption": complete["assumptions"].pop()
    if mutation == "new_proof":
        current["justification"]["summary"] = "Fixture only: a new Lead-authored proof."
        concern(documents)
    expected = "theory.unaudited_justification_change" if mutation == "new_proof" else "theory.unaudited_math_change"
    assert expected in codes(actual_check(draft_engine, prepared))


@pytest.mark.parametrize("mutation", ["unknown_issue", "wrong_component", "modified_support", "lead_origin", "missing_change", "missing_file", "damaged_file", "lead_only_file"])
def test_real_lead_rejects_unsourced_or_damaged_counterexample(draft_engine, mutation):
    prepared = case(draft_engine)
    documents = prepared[2]
    analyst_files = counterexample(documents)
    change = documents["p3.decision"]["assessment_changes"][0]
    if mutation == "unknown_issue": change["issue_id"] = "issue.unknown"
    if mutation == "wrong_component": documents["p3.analyst_handoff"]["unresolved_issues"][0]["component_ids"] = ["statement.other"]
    if mutation == "modified_support": statement(documents, "p3.complete_theory")["justification"]["summary"] += " Changed by Lead."
    if mutation == "lead_origin": change.update(origin="lead_concern"); change.pop("issue_id")
    if mutation == "missing_change": documents["p3.decision"].pop("assessment_changes")
    if mutation == "missing_file": analyst_files = {}
    if mutation == "damaged_file": analyst_files = {name: "Damaged fixture bytes." for name in analyst_files}
    if mutation == "lead_only_file": prepared[3].update(analyst_files); analyst_files = {}
    # For the last case, withhold the added support from the sealed Analyst.
    if mutation == "lead_only_file":
        original_files = prepared[3].copy()
        prepared[3].pop("sources/analyst_counterexample.md")
        result = actual_check(draft_engine, prepared, analyst_files={})
        lead = draft_engine.member_workspace(prepared[0], prepared[1][-1].stage_id, MemberRole.RESEARCH_LEAD)
        write_outputs(lead, {}, {"sources/analyst_counterexample.md": original_files["sources/analyst_counterexample.md"]})
        result = check(draft_engine, prepared[0], prepared[1][-1], MemberRole.RESEARCH_LEAD)
    else:
        result = actual_check(draft_engine, prepared, analyst_files=analyst_files)
    assert "theory.unaudited_justification_change" in codes(result)
    if mutation in {"missing_file", "lead_only_file"}: assert "artifact.source_missing" in codes(result)
    if mutation == "damaged_file": assert "artifact.digest_mismatch" in codes(result)


@pytest.mark.parametrize("response", ["resolved", "contested", "unresolved"])
def test_real_lead_response_requires_coverage_not_agreement(draft_engine, response):
    prepared = case(draft_engine)
    target = issue(prepared[2])
    prepared[2]["p3.analyst_audit"]["issues"] = [copy.deepcopy(target)]
    prepared[2]["p3.decision"]["issue_dispositions"][0]["status"] = response
    result = actual_check(draft_engine, prepared)
    assert result["status"] == "passed", result["findings"]


@pytest.mark.parametrize("mutation", ["missing", "unknown", "duplicate_disposition", "blank_reason", "duplicate_issue", "missing_issue_id"])
def test_real_lead_issue_traceability_rejects_missing_or_invalid_responses(draft_engine, mutation):
    prepared = case(draft_engine)
    documents = prepared[2]
    target = issue(documents)
    dispositions = documents["p3.decision"]["issue_dispositions"]
    if mutation == "missing": dispositions.clear()
    if mutation == "unknown": dispositions[0]["issue_id"] = "issue.other"
    if mutation == "duplicate_disposition": dispositions.append(copy.deepcopy(dispositions[0]))
    if mutation == "blank_reason": dispositions[0]["reason"] = "   "
    if mutation == "duplicate_issue": documents["p3.analyst_handoff"]["unresolved_issues"].append(copy.deepcopy(target))
    if mutation == "missing_issue_id": target.pop("issue_id")
    result = actual_check(draft_engine, prepared)
    assert result["status"] == "failed"
    assert ("schema.pattern" if mutation == "blank_reason" else "p3.issue_traceability") in codes(result)


def test_analyst_check_defers_lead_response_coverage(draft_engine):
    prepared = case(draft_engine)
    issue(prepared[2])
    prepared[2]["p3.decision"].pop("issue_dispositions")
    result = actual_check(draft_engine, prepared, role=MemberRole.DATA_ANALYST)
    assert result["status"] == "passed", result["findings"]


def test_frozen_old_pin_does_not_acquire_new_metadata_after_project_adoption(draft_engine):
    prepared = case(draft_engine, enabled=False, version="1.19.1")
    issue(prepared[2])
    prepared[2]["p3.decision"].pop("issue_dispositions")
    statement(prepared[2], "p3.complete_theory")["status"] = "incomplete"
    record = prepared[0]
    frozen = draft_engine.run_dir(record.project_id, record.run_id) / "contracts"
    shutil.copytree(draft_engine.project_dir(record.project_id) / "contracts", frozen)
    basis_path = draft_engine.run_dir(record.project_id, record.run_id) / "basis.json"
    write_json_atomic(basis_path, {**read_json(basis_path), "catalog_sha256": Catalog(frozen).snapshot_sha256})
    pin(draft_engine, True, version="1.20.0")
    result = actual_check(draft_engine, prepared)
    assert result["status"] == "passed", result["findings"]
    assert CAPABILITY not in read_json(frozen / "contracts/phases/P3.json")["capabilities"]
    assert draft_engine._catalog(record).version == "1.19.1"


def test_assumption_status_change_is_attributed_without_truth_ranking(draft_engine):
    prepared = case(draft_engine)
    assumption = prepared[2]["p3.complete_theory"]["assumptions"][0]
    assumption["status"] = "unverified"
    concern(prepared[2], assumption["assumption_id"])
    result = actual_check(draft_engine, prepared)
    assert result["status"] == "passed", result["findings"]


@pytest.mark.parametrize("field", ["statement", "component_ids", "justification"])
def test_shared_issue_identity_rejects_conflicting_analyst_objects_even_without_theory_change(draft_engine, field):
    prepared = case(draft_engine)
    target = issue(prepared[2])
    conflicting = copy.deepcopy(target)
    conflicting[field] = {"statement": "A distinct concern.", "component_ids": ["statement.other"],
                          "justification": {"kind": "open_obligation", "summary": "A distinct gap.",
                                            "artifacts": [], "open_obligation": "Investigate."}}[field]
    prepared[2]["p3.analyst_audit"]["issues"] = [conflicting]
    result = actual_check(draft_engine, prepared, final=True)
    assert "p3.issue_traceability" in codes(result)
    assert statement(prepared[2], "p3.theory_candidate") == statement(prepared[2], "p3.complete_theory")


@pytest.mark.parametrize("mutation", ["assumption_remove_source", "assumption_replace_source"])
def test_assumption_sources_cannot_be_replaced_or_dropped_by_lead(draft_engine, mutation):
    prepared = case(draft_engine)
    sources = prepared[2]["p3.complete_theory"]["assumptions"][0]["source_artifacts"]
    if mutation == "assumption_remove_source":
        sources.clear()
    else:
        sources[0]["locator"] = "An invented replacement source location."
    assert "theory.unaudited_justification_change" in codes(actual_check(draft_engine, prepared))


def test_lead_can_explain_assumption_sensitivity_without_replacing_its_sources(draft_engine):
    prepared = case(draft_engine)
    prepared[2]["p3.complete_theory"]["assumptions"][0]["sensitivity"] = "Fixture only: the guarantee remains conditional on this unchanged assumption."
    result = actual_check(draft_engine, prepared)
    assert result["status"] == "passed", result["findings"]


@pytest.mark.parametrize(("field", "value"), [
    ("status", []), ("status", {}), ("origin", []), ("origin", {}),
    ("component_ids", 1), ("component_ids", {}), ("component_ids", "statement.fixture"),
])
def test_malformed_new_metadata_is_rejected_without_semantic_crash(draft_engine, field, value):
    prepared = case(draft_engine)
    target = issue(prepared[2])
    concern(prepared[2])
    statement(prepared[2], "p3.complete_theory")["status"] = "incomplete"
    if field == "status":
        prepared[2]["p3.decision"]["issue_dispositions"][0][field] = value
    elif field == "origin":
        prepared[2]["p3.decision"]["assessment_changes"][0][field] = value
    else:
        target[field] = value
    result = actual_check(draft_engine, prepared, final=True)
    assert result["status"] == "failed"
    findings = validate_scientific_outputs(draft_engine._catalog(prepared[0]), "P3", prepared[2])
    assert any(row.code in {"p3.issue_traceability", "theory.assessment_change"} for row in findings)
    assert all(row.code != "scientific.invalid_structure" for row in findings)


def test_old_capability_pin_still_rejects_unaudited_positive_promotion(draft_engine):
    prepared = case(draft_engine, enabled=False, version="1.19.1")
    support = copy.deepcopy(statement(prepared[2], "p3.theory_candidate")["justification"])
    original_status(prepared[2], "incomplete")
    statement(prepared[2], "p3.complete_theory").update(status="established", justification=support)
    result = actual_check(draft_engine, prepared)
    assert "theory.unaudited_assessment_change" in codes(result)
    assert "theory.assessment_change" not in codes(result)


@pytest.mark.parametrize("mutation", ["missing", "extra", "unknown", "duplicate", "blank_reason"])
def test_changed_assessment_requires_exact_valid_annotation_coverage(draft_engine, mutation):
    prepared = case(draft_engine)
    statement(prepared[2], "p3.complete_theory")["status"] = "incomplete"
    concern(prepared[2])
    changes = prepared[2]["p3.decision"]["assessment_changes"]
    if mutation == "missing": changes.clear()
    if mutation == "extra": changes.append({**changes[0], "component_id": "statement.example_normality"})
    if mutation == "unknown": changes[0]["component_id"] = "statement.unknown"
    if mutation == "duplicate": changes.append(copy.deepcopy(changes[0]))
    if mutation == "blank_reason": changes[0]["reason"] = "   "
    result = actual_check(draft_engine, prepared)
    assert result["status"] == "failed"
    assert ("schema.pattern" if mutation == "blank_reason" else "theory.assessment_change") in codes(result)
