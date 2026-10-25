"""The complete Analyst account is a lazy, exact retained source, not a join."""
import copy
import json

import pytest

from model_forge_codex.research import artifacts_view, scientific_document_view
from model_forge_codex.storage import sha256_file, write_json_atomic
from test_researcher_workbench_engine import publish


def retained_account(project, run_id, content, suffix=".json"):
    run_dir = project / "runs" / run_id
    path = run_dir / "outputs/p4.analyst/working/data_analyst" / ("analyst_text" + suffix)
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    write_json_atomic(run_dir / "run.json", {"run_id": run_id, "phase": "P4", "branch_id": "method.a", "state": "published"})
    compact = {"question_results": [{"question_id": "question.original", "answer_markdown": "Full Q4.", "outcome": "mixed"}],
               "representations": [{"information_layer": "primary_artifact", "artifact": {
                   "artifact_id": "artifact.analyst", "path": path.name, "sha256": sha256_file(path),
                   "locator": "questions: Q1-Q9 in array order"}}]}
    package = publish(project, "method.a", "P4", {"analyst_synthesis": compact,
        "protocol": {"claim_tests": [{"test_id": "question.original", "hypothesis": "Original question"}]}}, run_id)
    return package["records"]["analyst_synthesis"]["generation_id"], path, compact


def test_declared_account_is_lazy_and_does_not_hydrate_or_rekey_questions(tmp_path):
    account = {"title": "Complete account", "questions": [{"key": "unrelated.informal.key", "answer_markdown": "Full scientific finding."}]}
    content = json.dumps(account).encode()
    generation, path, compact = retained_account(tmp_path, "run.original", content)
    before = copy.deepcopy(compact)
    projected = artifacts_view(tmp_path, "method.a")
    result = projected["questions"][0]["result"]
    assert result == {**compact["question_results"][0], "generation_ref": result["generation_ref"], "has_full_analyst_account": True}
    assert result["generation_ref"]["generation_id"] == generation
    assert "primary_content" not in json.dumps(projected)
    assert "Full scientific finding." not in json.dumps(projected)
    opened = scientific_document_view(tmp_path, "method.a", "P4", "analyst_synthesis", generation)
    assert opened["primary_source_verified"] is True
    assert opened["primary_artifact_kind"] == "json"
    assert opened["primary_content"] == account
    assert opened["structured"] == before == compact
    assert path.read_bytes() == content
    assert "run.original/outputs/p4.analyst/artifact?" in opened["primary_artifact_url"]
    assert "sha256=" + sha256_file(path) in opened["primary_artifact_url"]


@pytest.mark.parametrize("damage", ["missing", "tampered", "unpublished", "wrong_branch"])
def test_historical_account_never_substitutes_current_or_unverified_source(tmp_path, damage):
    old, path, compact = retained_account(tmp_path, "run.original", b'{"conclusion":"Original qualified result."}')
    retained_account(tmp_path, "run.current", b'{"conclusion":"CURRENT MUST NOT REPLACE ORIGINAL"}')
    if damage == "missing":
        path.unlink()
    elif damage == "tampered":
        path.write_bytes(b'{"conclusion":"TAMPERED"}')
    else:
        write_json_atomic(tmp_path / "runs/run.original/run.json", {
            "state": "running" if damage == "unpublished" else "published", "phase": "P4",
            "branch_id": "method.other" if damage == "wrong_branch" else "method.a"})
    opened = scientific_document_view(tmp_path, "method.a", "P4", "analyst_synthesis", old)
    assert "Analyst account" in opened["document_error"]
    assert "primary_content" not in opened and "primary_artifact_url" not in opened
    assert opened["structured"] == compact
    assert "CURRENT MUST NOT REPLACE ORIGINAL" not in json.dumps(opened)


def test_markdown_account_uses_existing_readable_document_path(tmp_path):
    content = b"# Full Analyst account\n\nConditional on $n=40$.\n"
    generation, path, compact = retained_account(tmp_path, "run.markdown", content, ".md")
    opened = scientific_document_view(tmp_path, "method.a", "P4", "analyst_synthesis", generation)
    assert opened["primary_artifact_kind"] == "markdown"
    assert opened["body_md"] == content.decode()
    assert opened["structured"] == compact
    assert path.read_bytes() == content


@pytest.mark.parametrize("content,reason", [(b"not json", "decoded"), (b'[]', "decoded"), (b'"' + b'x' * 5_000_000 + b'"', "preview limit")],
                         ids=["invalid-json", "non-object", "over-preview-limit"])
def test_unreadable_or_large_account_keeps_exact_download_and_compact_record(tmp_path, content, reason):
    generation, path, compact = retained_account(tmp_path, "run.source", content)
    opened = scientific_document_view(tmp_path, "method.a", "P4", "analyst_synthesis", generation)
    assert reason in opened["document_error"]
    assert "primary_content" not in opened
    assert opened["primary_source_verified"] is True and opened["primary_artifact_url"]
    assert opened["structured"] == compact
    assert path.read_bytes() == content


def test_older_inline_account_has_no_invented_full_account_control(tmp_path):
    compact = {"question_results": [{"question_id": "question.original", "answer_markdown": "Original inline finding."}]}
    publish(tmp_path, "method.a", "P4", {"analyst_synthesis": compact,
        "protocol": {"claim_tests": [{"test_id": "question.original", "hypothesis": "Original question"}]}}, "run.inline")
    assert "has_full_analyst_account" not in artifacts_view(tmp_path, "method.a")["questions"][0]["result"]
