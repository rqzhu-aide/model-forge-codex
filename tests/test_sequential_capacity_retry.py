"""Resume only the interrupted serial scientific stage against retained inputs."""
import pytest

from model_forge_codex.bridge import CAPACITY_FAILURE, BridgeUnavailable, TerminalTurnFailure
from model_forge_codex.domain import RunState
from model_forge_codex.runs import RunError
from model_forge_codex.storage import read_json, write_json_atomic
from test_direct_workflow import p1_documents
from test_researcher_workbench_engine import publish, script_scientific_run, workbench


@pytest.fixture
async def sequential_capacity_run(workbench, monkeypatch):
    engine, project, _ = workbench
    script_scientific_run(engine, project, "trunk", "P1", "p1.literature_update",
                          transform=lambda documents: documents.update(p1_documents()))
    original = engine.bridge.run_turn
    failed = False

    async def turn(thread_id, **kwargs):
        nonlocal failed
        if kwargs["workspace"].name == "p1.lead_synthesis" and not failed:
            failed = True
            engine.bridge._execution[thread_id]["turn_id"] = "turn.capacity"
            raise TerminalTurnFailure(CAPACITY_FAILURE)
        return await original(thread_id, **kwargs)

    confirmations = []

    async def confirm(thread_id, turn_id, **kwargs):
        assert turn_id == "turn.capacity"
        confirmations.append((thread_id, turn_id))
        return {"turn_id": turn_id, "status": "failed", "failure_code": "provider.capacity",
                "confirmation": "app_server_read"}

    monkeypatch.setattr(engine.bridge, "run_turn", turn)
    monkeypatch.setattr(engine.bridge, "confirm_capacity_failure", confirm, raising=False)
    record = await engine.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    await engine._tasks[record.run_id]
    record = engine.load_run(record.project_id, record.run_id)
    assert record.state == RunState.FAILED and record.terminal_reason == CAPACITY_FAILURE
    assert record.stage_states == {"p1.discovery": "succeeded", "p1.lead_synthesis": "failed"}
    return engine, record, confirmations


def retained(engine, record):
    directory = engine.run_dir(record.project_id, record.run_id)
    paths = [directory / name for name in ("basis.json", "stage-plan.json", "publication-base.json")]
    paths += list((directory / "contracts").rglob("*"))
    paths += list((directory / "inputs").rglob("*"))
    paths += list((directory / "outputs/p1.discovery").rglob("*"))
    paths += list((directory / "execution").rglob("*"))
    paths += list((directory / "briefs").glob("*"))
    return {path: path.read_bytes() for path in paths if path.is_file()}


def failed_receipt(engine, record):
    directory = engine.run_dir(record.project_id, record.run_id)
    return next(path for path in (directory / "execution").glob("*/execution.json")
                if read_json(path).get("stage_id") == "p1.lead_synthesis")


async def test_p1_retry_publishes_once_preserving_completed_discovery_and_exact_brief(sequential_capacity_run, monkeypatch):
    engine, record, confirmations = sequential_capacity_run
    directory = engine.run_dir(record.project_id, record.run_id)
    saved = retained(engine, record)
    failed = read_json(failed_receipt(engine, record))
    project = engine.project_dir(record.project_id)
    notebook = project / "members/research_lead/notebooks/trunk.md"
    notebook.parent.mkdir(parents=True, exist_ok=True)
    notebook.write_text("Later mutable notebook must not enter the retry.", encoding="utf-8")
    handoff = project / "branches/trunk/handoffs/research_lead_PROJECT_trunk.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("Later mutable handoff must not enter the retry.", encoding="utf-8")
    preflight = []

    async def native_check(thread_id, workspace):
        preflight.append(str(workspace))
        return {"status": "passed"}

    monkeypatch.setattr(engine.bridge, "check_native_tools", native_check, raising=False)
    original_render = engine._render_brief

    def render(*args):
        raise AssertionError("A retry must reuse its exact saved brief, including after native preflight")

    monkeypatch.setattr(engine, "_render_brief", render)
    assert engine.provider_retry_preview(record) == {"eligible": True, "reason": None, "failure_code": "provider.capacity"}
    result = await engine.retry_provider(record.project_id, record.run_id)
    with pytest.raises(RunError):
        await engine.retry_provider(record.project_id, record.run_id)
    await engine._tasks[record.run_id]
    final = engine.load_run(record.project_id, record.run_id)
    assert final.state == RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert result.run_id == record.run_id and final.correction_attempts == 0
    assert final.stage_states == {"p1.discovery": "succeeded", "p1.lead_synthesis": "succeeded"}
    assert len(engine.bridge.turns) == 4 and len(preflight) == 1
    assert confirmations == [(failed["thread_id"], "turn.capacity")] * 2
    assert all(path.read_bytes() == content for path, content in saved.items())
    assert notebook.read_text(encoding="utf-8").startswith("Later mutable notebook")
    assert handoff.read_text(encoding="utf-8").startswith("Later mutable handoff")
    resumed = engine.bridge.turns[-1]
    assert resumed["brief"] == (directory / "briefs/p1.lead_synthesis.research_lead.md").read_text(encoding="utf-8")
    assert resumed["execution"]["submitted"]["model"] == failed["submitted"]["model"]
    assert resumed["execution"]["submitted"]["reasoning_effort"] == failed["submitted"]["reasoning_effort"]
    events, _ = engine.run_events(record.project_id, record.run_id)
    assert len([event for event in events if event["type"] == "run.provider_retry"]) == 1
    assert len([event for event in events if event["type"] == "run.published"]) == 1
    with pytest.raises(RunError):
        await engine.retry_provider(record.project_id, record.run_id)
    monkeypatch.setattr(engine, "_render_brief", original_render)


@pytest.mark.parametrize("change", ["parallel", "assessment", "correction", "scientific_failure", "brief", "completed_output",
                                  "source", "catalog", "instructions", "model", "limits", "project_context", "notation",
                                  "publication", "receipt", "active"])
async def test_p1_retry_refuses_changed_sources_or_unsupported_recovery(sequential_capacity_run, change):
    engine, record, confirmations = sequential_capacity_run
    directory = engine.run_dir(record.project_id, record.run_id)
    project = engine.project_dir(record.project_id)
    if change == "parallel":
        record.stage_states["p1.discovery"] = "failed"
    elif change == "assessment":
        record.intent = "assessment"
    elif change == "correction":
        record.correction_attempts = 1
    elif change == "scientific_failure":
        record.terminal_reason = "A scientific finding needs correction."
    elif change == "brief":
        (directory / "briefs/p1.lead_synthesis.research_lead.md").write_text("Changed brief", encoding="utf-8")
    elif change == "completed_output":
        (directory / "outputs/p1.discovery/lead_literature.json").write_text("{}", encoding="utf-8")
    elif change == "source":
        source = read_json(directory / "basis.json")["records"][0]["snapshot_path"]
        from pathlib import Path
        Path(source).write_text("{}", encoding="utf-8")
    elif change == "catalog":
        (directory / "contracts/contracts/phases/P1.json").write_text("{}", encoding="utf-8")
    elif change == "instructions":
        (project / "members/research_lead/codex-home/AGENTS.md").write_text("Changed instructions", encoding="utf-8")
    elif change in ("model", "limits"):
        path = project / "members/research_lead/config.json"
        update = {"model": "different"} if change == "model" else {"max_turn_input_tokens": 1000}
        write_json_atomic(path, {**read_json(path), **update})
    elif change == "project_context":
        from model_forge_codex.problem_context import load_problem_context, save_context_item
        context = load_problem_context(project)
        save_context_item(project, "Use a different target population.", topic="research_goal",
                          expected_revision=context["revision"])
    elif change == "notation":
        # The identity comparison must include shared notation even with
        # unchanged source record pointers and problem statements.
        original = engine.compute_basis
        engine.compute_basis = lambda *args, **kwargs: {**original(*args, **kwargs), "notation": {"sha256": "changed"}}
    elif change == "publication":
        publish(project, "trunk", "P1", {"literature_synthesis": {"headline": "A later published update."}}, "run.later")
    elif change == "receipt":
        path = failed_receipt(engine, record)
        write_json_atomic(path, {**read_json(path), "purpose": "mechanical_repair"})
    else:
        engine._active_turns[record.run_id] = {"thread.still_running"}
    engine._save_run(record)
    before = (directory / "run.json").read_bytes()
    calls = len(engine.bridge.turns)
    assert not engine.provider_retry_preview(record)["eligible"]
    with pytest.raises((RunError, ValueError)):
        await engine.retry_provider(record.project_id, record.run_id)
    assert (directory / "run.json").read_bytes() == before
    assert len(engine.bridge.turns) == calls and confirmations == []


@pytest.mark.parametrize("changed_during_read", [False, True])
async def test_nonp4_exact_terminal_read_or_context_change_cannot_dispatch(sequential_capacity_run, monkeypatch, changed_during_read):
    engine, record, _ = sequential_capacity_run
    calls = len(engine.bridge.turns)
    directory = engine.run_dir(record.project_id, record.run_id)
    before = (directory / "run.json").read_bytes()

    async def confirm(*args, **kwargs):
        if not changed_during_read:
            raise BridgeUnavailable("The exact interrupted turn is no longer the latest stopped capacity turn.")
        project = engine.project_dir(record.project_id) / "project.json"
        write_json_atomic(project, {**read_json(project), "research_instructions": "A changed scientific goal."})
        return {"turn_id": "turn.capacity", "status": "failed"}

    monkeypatch.setattr(engine.bridge, "confirm_capacity_failure", confirm)
    with pytest.raises(RunError, match="Research context changed|Retry did not start"):
        await engine.retry_provider(record.project_id, record.run_id)
    assert (directory / "run.json").read_bytes() == before
    assert len(engine.bridge.turns) == calls


async def test_shared_thread_advance_after_acceptance_is_rechecked_under_member_lock(sequential_capacity_run, monkeypatch):
    engine, record, _ = sequential_capacity_run
    calls = len(engine.bridge.turns)
    confirmations = 0

    async def confirm(*args, **kwargs):
        nonlocal confirmations
        confirmations += 1
        if confirmations == 2:
            raise BridgeUnavailable("A later turn entered this shared member thread.")
        return {"turn_id": "turn.capacity", "status": "failed"}

    monkeypatch.setattr(engine.bridge, "confirm_capacity_failure", confirm)
    await engine.retry_provider(record.project_id, record.run_id)
    await engine._tasks[record.run_id]
    final = engine.load_run(record.project_id, record.run_id)
    assert confirmations == 2 and len(engine.bridge.turns) == calls
    assert final.state == RunState.FAILED and "later turn" in final.terminal_reason


@pytest.mark.parametrize("change", ["model", "context", "publication"])
async def test_preflight_changes_cannot_enter_resumed_scientific_turn(sequential_capacity_run, monkeypatch, change):
    engine, record, _ = sequential_capacity_run
    calls = len(engine.bridge.turns)
    project = engine.project_dir(record.project_id)

    async def native_check(thread_id, workspace):
        if change == "model":
            path = project / "members/research_lead/config.json"
            write_json_atomic(path, {**read_json(path), "model": "changed.during.preflight"})
        elif change == "context":
            path = project / "project.json"
            write_json_atomic(path, {**read_json(path), "research_instructions": "A different scientific objective."})
        else:
            publish(project, "trunk", "P1", {"literature_synthesis": {"headline": "A later update."}}, "run.later")
        return {"status": "passed"}

    monkeypatch.setattr(engine.bridge, "check_native_tools", native_check, raising=False)
    await engine.retry_provider(record.project_id, record.run_id)
    await engine._tasks[record.run_id]
    final = engine.load_run(record.project_id, record.run_id)
    assert final.state == RunState.FAILED and len(engine.bridge.turns) == calls
    assert not any(event["type"] == "run.published" for event in engine.run_events(record.project_id, record.run_id)[0])


async def test_retry_refuses_replacement_of_the_interrupted_member_thread(sequential_capacity_run, monkeypatch):
    engine, record, confirmations = sequential_capacity_run
    calls = len(engine.bridge.turns)

    async def unavailable(*args, **kwargs):
        return False

    monkeypatch.setattr(engine.bridge, "resume_thread", unavailable)
    await engine.retry_provider(record.project_id, record.run_id)
    await engine._tasks[record.run_id]
    final = engine.load_run(record.project_id, record.run_id)
    assert final.state == RunState.FAILED and "thread is unavailable" in final.terminal_reason
    assert len(confirmations) == 1 and len(engine.bridge.turns) == calls
