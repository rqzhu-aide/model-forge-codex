"""Future P4 briefs keep actionable control facts without repeating case grids."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from model_forge_codex.domain import MemberRole
from model_forge_codex.p4_execution import P4Controller
from model_forge_codex.p4_lifecycle import P4LifecycleMixin
from model_forge_codex.storage import write_json_atomic


def render(tmp_path):
    renderer = SimpleNamespace(_progressive_p4=lambda _: True, run_dir=lambda *_: tmp_path)
    record = SimpleNamespace(project_id="project.test", run_id="run.test")
    text = P4LifecycleMixin._p4_brief(renderer, record, None, MemberRole.DATA_ANALYST)
    encoded = text.split("Current controller state", 1)[1].split("```json\n", 1)[1].split("\n```", 1)[0]
    return text, json.loads(encoded)


def test_amendment_grid_is_referenced_without_losing_limits_or_active_work(tmp_path, monkeypatch):
    original_work = {"work_item_id": "work.pilot", "case_ids": ["case.pilot"], "depends_on": [],
                     "estimated_seconds": 5, "stop_conditions_markdown": "Stop if the implementation check fails."}
    added_work = {"work_item_id": "work.comparison", "case_ids": [f"case.{i}" for i in range(125)],
                  "depends_on": ["work.pilot"], "estimated_seconds": 120,
                  "stop_conditions_markdown": "Retain a partial comparison if the budget expires."}
    amendment = {"revision_id": "plan.r2", "supersedes_revision_id": "plan.r1",
                 "created_at": "2026-10-22T00:00:00Z", "reason_markdown": "The pilot exposes limited support.",
                 "observed_evidence_ids": ["evidence.pilot"], "changes_markdown": "Add a conditional comparison.",
                 "inferential_consequences_markdown": "Synthetic evidence does not establish human applicability.",
                 "work_item_order": ["work.pilot", "work.comparison", "work.deferred"],
                 "deferred_work_item_ids": ["work.deferred"],
                 "added_cases": [{"case_id": f"case.{i}", "metric_ids": [f"metric.{j}" for j in range(72)],
                                  "conditions": {"exact_scientific_condition": "retained only in the full plan"}}
                                 for i in range(125)],
                 "added_metrics": [{"metric_id": f"metric.{i}", "definition": "exact definition"} for i in range(72)],
                 "added_work_items": [added_work], "added_data_sources": [{"data_source_id": "source.synthetic"}],
                 "added_tests": [{"test_id": "test.conditional"}], "added_baselines": [],
                 "added_decision_thresholds": [{"threshold_id": "threshold.conditional"}]}
    plan = {"protocol_id": "protocol.one", "plan_revision_id": "plan.r1",
            "decision_context": {"limits": "No observed human data supplied."},
            "work_items": [original_work], "amendments": [amendment]}
    state = {"schema_version": 1, "plan": plan, "budget": {"authorized_seconds": 180, "remaining_seconds": 120},
             "pending_batch": {"attempt_id": "attempt.one", "status": "queued"}, "finish_requested": False,
             "checkpoint": {"summary": "Pilot is complete; comparison remains conditional."},
             "answer_revisions": [{"answer": "Continue with synthetic evidence only."}],
             "ledger": [{"attempt_id": "attempt.pilot", "status": "completed", "elapsed_seconds": 5,
                         "output_dir": "retained/pilot", "artifacts": [{"path": "rows.jsonl"}]}],
             "plan_history": [deepcopy(plan)], "checkpoints": [{"summary": "Earlier checkpoint"}]}
    path = tmp_path / "p4-execution/state.json"
    write_json_atomic(path, state)
    before, original = path.read_bytes(), deepcopy(state)
    monkeypatch.setattr(P4Controller, "load_snapshot", lambda _: state)
    text, delivered = render(tmp_path)

    assert state == original and path.read_bytes() == before
    assert Path(delivered["saved_state_path"]) == path
    assert json.loads(path.read_bytes()) == state
    summary = delivered["plan_summary"]
    compact = summary["amendments"][0]
    assert compact == {**{key: value for key, value in amendment.items() if not key.startswith("added_")},
                       "added_counts": {"added_cases": 125, "added_metrics": 72, "added_work_items": 1,
                                        "added_data_sources": 1, "added_tests": 1, "added_baselines": 0,
                                        "added_decision_thresholds": 1}}
    assert summary["work_items"] == [original_work, added_work]
    assert summary["decision_context"] == plan["decision_context"]
    for key in ("budget", "pending_batch", "finish_requested", "checkpoint", "answer_revisions"):
        assert delivered[key] == state[key]
    assert delivered["ledger"][0]["status"] == "completed"
    assert "read the full saved plan at saved_state_path" in text
    assert "exact_scientific_condition" not in text
    assert len(text.encode()) < len(json.dumps(plan).encode()) // 4


@pytest.mark.parametrize("plan", [None, {"protocol_id": "protocol.one", "plan_revision_id": "plan.r1",
                                       "work_items": [{"work_item_id": "work.one"}], "amendments": []}])
def test_unamended_and_unsaved_plans_keep_existing_control_facts(tmp_path, plan):
    state = {"schema_version": 1, "plan": plan, "budget": {"remaining_seconds": 60},
             "finish_requested": True, "ledger": []}
    path = tmp_path / "p4-execution/state.json"
    write_json_atomic(path, state)
    before = path.read_bytes()
    _, delivered = render(tmp_path)
    assert path.read_bytes() == before
    assert delivered["budget"] == state["budget"] and delivered["finish_requested"] is True
    assert delivered["plan_summary"] == (plan or {})
