"""An unresolved research question must not vanish on an unrelated rerun."""
import json

import pytest

from model_forge_codex.cumulative_attention import open_attention_items
from model_forge_codex.records import ArtifactError, generation_path, publish_package
from model_forge_codex.service import _open_attention_items
from model_forge_codex.storage import sha256_bytes, write_json_atomic


def publish(project, items, phase="P1", branch="trunk", *, before_commit=None):
    directory = project / "branches" / branch / "phases" / phase.lower()
    return publish_package(directory, {"attention_items": json.dumps(items).encode()},
                           run_id="run." + phase.lower(), phase=phase, branch_id=branch,
                           before_commit=before_commit)


def issue(identifier, disposition="open", **extra):
    return {"attention_id": identifier, "disposition": disposition, "severity": "major",
            "question": "Does particle dependence change the comparison?",
            "likely_consequence": "The effective sample size may be overstated.",
            "raised_by": "theorist", **extra}


def test_unrelated_updates_preserve_open_questions_and_exact_origin(tmp_path):
    first = publish(tmp_path, [issue("dependence")])
    publish(tmp_path, [issue("cost")])
    publish(tmp_path, [])
    result = {item["attention_id"]: item for item in open_attention_items(tmp_path, {})}
    assert set(result) == {"dependence", "cost"}
    reference = result["dependence"]["generation_ref"]
    assert reference["generation_id"] == first["records"]["attention_items"]["generation_id"]
    assert reference["sha256"] == first["records"]["attention_items"]["content_sha256"]
    assert result["dependence"]["question"] == issue("dependence")["question"]


def test_later_cross_phase_disposition_wins_without_duplicate_inbox_entries(tmp_path):
    publish(tmp_path, [issue("dependence"), issue("cost")])
    publish(tmp_path, [issue("dependence", "resolved", disposition_reason="Accounted for joint dependence.")],
            phase="P4", branch="entangled")
    publish(tmp_path, [issue("cost", severity="blocking", rerun_question="Include interaction overhead.")],
            phase="P2")
    result = open_attention_items(tmp_path, {})
    assert [item["attention_id"] for item in result] == ["cost"]
    assert result[0]["phase"] == "P2" and result[0]["severity"] == "blocking"
    assert result[0]["rerun_question"] == "Include interaction overhead."


@pytest.mark.parametrize("disposition", ["resolved", "deferred", "accepted_limitation", "rejected",
                                          "addressed", "fixed", "wont_fix"])
def test_explicit_disposition_is_not_reopened_by_empty_rerun(tmp_path, disposition):
    publish(tmp_path, [issue("dependence")])
    publish(tmp_path, [issue("dependence", disposition)])
    publish(tmp_path, [])
    assert open_attention_items(tmp_path, {}) == []


def test_partial_team_progress_keeps_latest_shared_task_pending_without_reopening_earlier_source(tmp_path):
    identifier = "reference-identification"
    first = publish(tmp_path, [issue(identifier, kind="research_task", scope={"kind": "project"})], phase="P2")
    partial = issue(identifier, "partially_fixed", kind="research_task", scope={"kind": "project"},
                    target_phase="P3", question="Other models still need the reference-value check.",
                    disposition_reason="Only the selected model has been checked.")
    latest = publish(tmp_path, [partial], phase="P3", branch="method.a")
    publish(tmp_path, [], phase="P3", branch="method.a")
    before = {path: path.read_bytes() for path in (tmp_path / "branches").rglob("*") if path.is_file()}

    pending = open_attention_items(tmp_path, {})

    assert len(pending) == 1
    item = pending[0]
    assert item["attention_id"] == identifier and item["disposition"] == "partially_fixed"
    assert item["question"] == partial["question"] and item["scope"] == {"kind": "project"}
    assert item["generation_ref"]["generation_id"] == latest["records"]["attention_items"]["generation_id"]
    assert item["generation_ref"]["generation_id"] != first["records"]["attention_items"]["generation_id"]
    assert item["generation_ref"]["entry_pointer"] == "/0"
    assert before == {path: path.read_bytes() for path in (tmp_path / "branches").rglob("*") if path.is_file()}
    publish(tmp_path, [issue(identifier, "resolved", kind="research_task", scope={"kind": "project"})],
            phase="P3", branch="method.a")
    assert open_attention_items(tmp_path, {}) == []


def test_partial_disposition_does_not_turn_a_recorded_decision_into_new_input(tmp_path):
    publish(tmp_path, [issue("choice", "partially_fixed", kind="researcher_decision")])
    assert open_attention_items(tmp_path, {}) == []


def test_researcher_resolution_stays_separate_from_frozen_record(tmp_path):
    first = publish(tmp_path, [issue("dependence")])
    directory = tmp_path / "branches/trunk/phases/p1"
    source = generation_path(directory, "attention_items", first["records"]["attention_items"])
    original = source.read_bytes()
    write_json_atomic(tmp_path / "researcher/attention_resolutions.json", {"dependence": {"note": "Addressed"}})
    publish(tmp_path, [])
    assert _open_attention_items(tmp_path) == []
    assert source.read_bytes() == original


def test_prepared_uncommitted_issue_is_excluded(tmp_path):
    publish(tmp_path, [issue("dependence")])
    def fail(_package):
        raise RuntimeError("publication interrupted")
    with pytest.raises(RuntimeError):
        publish(tmp_path, [issue("orphan")], before_commit=fail)
    assert [item["attention_id"] for item in open_attention_items(tmp_path, {})] == ["dependence"]


def test_corrupt_historical_issue_cannot_silently_disappear(tmp_path):
    first = publish(tmp_path, [issue("dependence")])
    source = generation_path(tmp_path / "branches/trunk/phases/p1", "attention_items", first["records"]["attention_items"])
    publish(tmp_path, [])
    source.write_text("[]")
    with pytest.raises(ArtifactError, match="Digest mismatch"):
        open_attention_items(tmp_path, {})


def test_legacy_current_attention_survives_first_atomic_update(tmp_path):
    directory = tmp_path / "branches/trunk/phases/p1/attention_items"
    content = json.dumps([issue("dependence")]).encode()
    source = directory / "generations/generation.legacy.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(content)
    write_json_atomic(directory / "current.json", {"generation_id": "generation.legacy",
                      "content_sha256": sha256_bytes(content), "source_run_id": "run.legacy"})
    assert [item["attention_id"] for item in open_attention_items(tmp_path, {})] == ["dependence"]
    publish(tmp_path, [])
    result = open_attention_items(tmp_path, {})
    assert [item["attention_id"] for item in result] == ["dependence"]
    assert result[0]["generation_ref"]["run_id"] == "run.legacy"
