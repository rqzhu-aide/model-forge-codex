"""Later manuscript assembly must not erase unresolved review findings."""
from copy import deepcopy
import json

import pytest

from model_forge_codex.records import ArtifactError, publish_package
from model_forge_codex.review_ledger import build_review_ledger, load_review_ledger


def issue(identifier, disposition="open", version=1, manuscript="manuscript.v1"):
    return {"issue_id": identifier, "issue_version_id": f"{identifier}.v{version}",
            "review_basis_generation_id": manuscript, "source_run_id": f"run.review{version}",
            "issue": "The acceleration claim exceeds the tested setting.", "disposition": disposition,
            "disposition_reason": "Narrowed the claim." if disposition == "fixed" else "Requires comparison.",
            "requested_resolution": "Compare at equal computational cost.", "revision_locations": ["Abstract"]}


def publish(directory, documents, run="run.review"):
    return publish_package(directory, {family: json.dumps(document).encode() for family, document in documents.items()},
                           run_id=run, phase="P5", branch_id="entangled")


def test_review_index_preserves_omitted_issues_and_explicit_dispositions():
    old = build_review_ledger(None, [issue("cost"), issue("scope")], "run.review1")
    original = deepcopy(old)
    result = build_review_ledger(old, [issue("scope", "fixed", 2)], "run.review2")
    assert old == original
    assert {item["issue_id"]: item["disposition"] for item in result["issues"]} == {"cost": "open", "scope": "fixed"}
    assert result["issues"][0]["review_basis_generation_id"] == "manuscript.v1"
    assert result["issues"][1]["revision_locations"] == ["Abstract"]
    assert build_review_ledger(result, [], "run.assembly") == result


def test_changed_immutable_issue_version_is_rejected():
    old = build_review_ledger(None, [issue("cost")], "run.review1")
    with pytest.raises(ArtifactError, match="new immutable issue version"):
        build_review_ledger(old, [issue("cost", "fixed")], "run.review2")


def test_legacy_reviews_survive_assembly_and_keep_exact_sources(tmp_path):
    directory = tmp_path / "branches/entangled/phases/p5"
    first = publish(directory, {"review_issues": [issue("cost"), issue("scope")]})
    publish(directory, {"review_issues": [issue("scope", "fixed", 2)]}, "run.review2")
    publish(directory, {"manuscript": {"body_md": "A later complete manuscript."}}, "run.assembly")
    ledger = load_review_ledger(directory)
    assert [item["issue_id"] for item in ledger["issues"]] == ["cost", "scope"]
    assert ledger["issue_sources"]["cost"]["generation_id"] == first["records"]["review_issues"]["generation_id"]
    assert ledger["issue_sources"]["cost"]["branch"] == "entangled"
    assert ledger["issues"][0]["review_basis_generation_id"] == "manuscript.v1"


def test_index_and_authored_outputs_are_not_double_counted(tmp_path):
    directory = tmp_path / "branches/entangled/phases/p5"
    issues = [issue("cost")]
    first = publish(directory, {"review_issues": issues, "review_issue_ledger": build_review_ledger(None, issues, "run.review")})
    recovered = load_review_ledger(directory)
    assert len(recovered["issues"]) == 1
    assert recovered["issue_sources"]["cost"]["generation_id"] == first["records"]["review_issues"]["generation_id"]
    publish(directory, {"review_issue_ledger": recovered, "manuscript": {"body_md": "Later manuscript"}}, "run.assembly")
    assert load_review_ledger(directory) == recovered


def test_uncommitted_review_is_excluded(tmp_path):
    directory = tmp_path / "branches/entangled/phases/p5"
    publish(directory, {"review_issues": [issue("cost")]})
    def fail(_package):
        raise RuntimeError("publication interrupted")
    with pytest.raises(RuntimeError):
        publish_package(directory, {"review_issues": json.dumps([issue("orphan")]).encode()},
                        run_id="run.failed", phase="P5", branch_id="entangled", before_commit=fail)
    assert [item["issue_id"] for item in load_review_ledger(directory)["issues"]] == ["cost"]
