from types import SimpleNamespace

import pytest
from openai_codex._run import Notification
from openai_codex.generated.v2_all import ItemCompletedNotification, ItemStartedNotification, ThreadItem

from model_forge_codex.bridge import _summarize_notification


def notification(item, *, started=False):
    payload = ItemStartedNotification if started else ItemCompletedNotification
    return Notification(
        method="item/started" if started else "item/completed",
        payload=payload(thread_id="thread.test", turn_id="turn.test", item=ThreadItem.model_validate(item),
                        **{"startedAtMs" if started else "completedAtMs": 1}),
    )


def command_item(**updates):
    return {
        "type": "commandExecution", "id": "command.one", "command": "rg target papers",
        "commandActions": [], "cwd": "C:/research", "status": "completed", "exitCode": 0,
        **updates,
    }


def test_command_lifecycle_never_reports_a_started_or_failed_command_as_completed():
    started = notification(command_item(status="inProgress", exitCode=None), started=True)
    completed = notification(command_item())
    failed = notification(command_item(status="failed", exitCode=1, aggregatedOutput="private output"))
    assert _summarize_notification(started) == "running: rg target papers"
    assert _summarize_notification(completed) == "completed: rg target papers"
    assert _summarize_notification(failed) == "failed (exit 1): rg target papers"
    assert _summarize_notification(notification(command_item(status="declined", exitCode=None))).startswith("declined:")


@pytest.mark.parametrize("wrapped", [
    r'''"C:\Program Files\A very long installed runtime location\PowerShell\7\pwsh.exe" -NoProfile -NonInteractive -Command "Get-Content papers\landscape.md"''',
    r'''powershell.exe -ExecutionPolicy Bypass -Command 'Get-Content papers\landscape.md' ''',
    r'''/bin/bash -lc 'Get-Content papers\landscape.md' ''',
    r'''cmd.exe /d /s /c "Get-Content papers\landscape.md"''',
])
def test_shell_launchers_are_removed_before_truncating_the_actual_activity(wrapped):
    assert _summarize_notification(notification(command_item(command=wrapped))) == r"completed: Get-Content papers\landscape.md"


def test_parsed_command_actions_expose_the_files_and_query_instead_of_the_shell():
    item = command_item(command="opaque shell launcher", commandActions=[
        {"type": "read", "command": "cat papers/setting.md", "name": "setting.md", "path": "papers/setting.md"},
        {"type": "search", "command": "rg invariant papers", "query": "invariant", "path": "papers"},
    ])
    assert _summarize_notification(notification(item)) == "completed: read papers/setting.md; search files for invariant in papers"


@pytest.mark.parametrize("action,expected", [
    ({"type": "search", "queries": ["", "Langevin interacting particles", "equal cost", "equal cost"]}, "searched: Langevin interacting particles; equal cost"),
    ({"type": "search", "query": "Bellman fixed point"}, "searched: Bellman fixed point"),
    ({"type": "openPage", "url": "https://papers.example/article"}, "opened page: https://papers.example/article"),
    ({"type": "findInPage", "pattern": "invariant measure", "url": "https://papers.example/article"}, "find in page completed: invariant measure in https://papers.example/article"),
])
def test_native_web_activity_uses_its_typed_action_when_top_level_query_is_empty(action, expected):
    item = {"type": "webSearch", "id": "search.one", "query": "", "action": action}
    assert _summarize_notification(notification(item)) == expected
    start = _summarize_notification(notification(item, started=True))
    assert start != expected and start


@pytest.mark.parametrize("item", [
    {"type": "webSearch", "id": "empty", "query": "   "},
    {"type": "webSearch", "id": "empty", "query": "", "action": {"type": "search", "queries": [""]}},
    {"type": "webSearch", "id": "empty", "query": "", "action": {"type": "openPage"}},
    {"type": "webSearch", "id": "empty", "query": "", "action": {"type": "findInPage"}},
    command_item(command=" \n "),
    {"type": "fileChange", "id": "empty", "changes": [], "status": "completed"},
])
def test_empty_activity_is_omitted(item):
    assert _summarize_notification(notification(item)) is None


def test_query_fallback_and_non_item_events_remain_supported():
    assert _summarize_notification(notification({"type": "webSearch", "id": "legacy", "query": "coupled Langevin"})) == "searched: coupled Langevin"
    assert _summarize_notification(SimpleNamespace(payload=None)) is None


@pytest.mark.parametrize("tool,arguments,expected", [
    ("search_web", {"query": "recent budgeted RL"}, "searched: recent budgeted RL"),
    ("read_web_page", {"url": "https://papers.org/source"}, "read page: https://papers.org/source"),
])
def test_direct_retrieval_activity_exposes_query_or_url_not_returned_content(tool, arguments, expected):
    item = {"type": "dynamicToolCall", "id": "web.one", "tool": tool, "arguments": arguments,
            "status": "completed", "success": True,
            "contentItems": [{"type": "inputText", "text": "PRIVATE_SOURCE_CONTENT"}]}
    assert _summarize_notification(notification(item)) == expected
    assert _summarize_notification(notification({**item, "status": "inProgress", "success": None}, started=True)) != expected
    failed = _summarize_notification(notification({**item, "status": "failed", "success": False}))
    assert "failed:" in failed and "PRIVATE_SOURCE_CONTENT" not in failed


def test_validation_activity_reports_mechanical_check_without_claiming_scientific_pass():
    item = {"type": "dynamicToolCall", "id": "validation.one", "tool": "validate_artifacts", "arguments": {},
            "status": "completed", "success": True,
            "contentItems": [{"type": "inputText", "text": '{"valid":false,"findings":["PRIVATE_CONTENT"]}'}]}
    assert _summarize_notification(notification(item, started=True)) == "checking saved artifacts"
    assert _summarize_notification(notification(item)) == "artifact validation report returned"
    assert _summarize_notification(notification({**item, "success": False})) == "artifact validation could not complete"


def test_one_compaction_reports_start_then_completion():
    item = {"type": "contextCompaction", "id": "compaction.one"}
    started = notification(item, started=True)
    completed = notification(item)
    assert started.payload.item.root.id == completed.payload.item.root.id
    assert [_summarize_notification(event) for event in (started, completed)] == [
        "compacting context", "context compacted",
    ]
