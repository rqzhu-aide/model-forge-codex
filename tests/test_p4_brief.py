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
    renderer = SimpleNamespace(_progressive_p4=lambda _: True, run_dir=lambda *_: tmp_path,
                               _catalog=lambda _: SimpleNamespace(root=tmp_path / "contracts"))
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


@pytest.mark.parametrize("role", [MemberRole.THEORIST, MemberRole.RESEARCH_LEAD])
def test_adopted_p4_reviewers_keep_review_authority_without_batch_authoring(tmp_path, role):
    contract = tmp_path / "contracts/contracts/phases/P4.json"
    renderer = SimpleNamespace(_progressive_p4=lambda _: True, run_dir=lambda *_: tmp_path,
                               _catalog=lambda _: SimpleNamespace(root=tmp_path / "contracts"))
    record = SimpleNamespace(project_id="project.test", run_id="run.test")
    write_json_atomic(contract, {"capabilities": ["research_account_focus_v1"]})
    reviewer = P4LifecycleMixin._p4_brief(renderer, record, None, role)
    analyst = P4LifecycleMixin._p4_brief(renderer, record, None, MemberRole.DATA_ANALYST)

    for instruction in ("run_batch requires", "script_path", "Declare result_paths in run_batch",
                        "MODEL_FORGE_P4_ATTEMPT_ID", "call save_plan with protocol_path",
                        "analyst calls complete only", "Provide an analysis script",
                        "Record prospective amendments before changed work", "generate the data before starting the timer"):
        assert instruction in analyst and instruction not in reviewer
    for requirement in ("For a checkpoint, send", "request_decision", "final eligible rows and tables",
                        "paired difference", "timing boundaries", "exact captured script and support files",
                        "prospective amendments", "host-recorded budget", "Invalidated rows retain their values",
                        "finish_requested", "read the full saved plan at saved_state_path",
                        "normal owned outputs", "changed method requires upstream revision",
                        "Reviewers must not call complete or run_batch", "Check that the declared analysis script"):
        assert requirement in reviewer
    assert len(reviewer.encode()) < len(analyst.encode())

    # Adoption is frozen with the run. An old or absent capability preserves
    # the common authoring text for all three roles.
    write_json_atomic(contract, {"capabilities": []})
    legacy = P4LifecycleMixin._p4_brief(renderer, record, None, role)
    assert legacy == P4LifecycleMixin._p4_brief(renderer, record, None, MemberRole.DATA_ANALYST)
    assert legacy == analyst


def test_reviewer_instructions_use_the_resolved_catalog_without_a_run_copy(tmp_path):
    catalog_root = tmp_path / "project-catalog"
    write_json_atomic(catalog_root / "contracts/phases/P4.json", {"capabilities": ["research_account_focus_v1"]})
    renderer = SimpleNamespace(_progressive_p4=lambda _: True, run_dir=lambda *_: tmp_path / "run",
                               _catalog=lambda _: SimpleNamespace(root=catalog_root))
    record = SimpleNamespace(project_id="project.test", run_id="run.test")
    text = P4LifecycleMixin._p4_brief(renderer, record, None, MemberRole.RESEARCH_LEAD)
    assert "run_batch requires" not in text
    assert "host-recorded budget" in text and "Check that the declared analysis script" in text
