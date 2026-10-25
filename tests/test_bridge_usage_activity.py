"""Actual SDK usage updates can establish activity without inventing tool events."""
from types import SimpleNamespace

import pytest
from openai_codex._run import Notification
from openai_codex.generated.v2_all import ThreadTokenUsageUpdatedNotification, TurnCompletedNotification

from model_forge_codex import bridge as bridge_module
from model_forge_codex.bridge import SdkCodexBridge
from test_bridge_notifications import command_item, notification


def usage(total, *, thread="thread.test", turn="turn.test"):
    tokens = {"inputTokens": total, "outputTokens": 0, "cachedInputTokens": 0,
              "reasoningOutputTokens": 0, "totalTokens": total}
    return Notification(method="thread/tokenUsage/updated", payload=ThreadTokenUsageUpdatedNotification.model_validate({
        "threadId": thread, "turnId": turn,
        "tokenUsage": {"total": tokens, "last": tokens, "modelContextWindow": 200000},
    }))


async def collect(monkeypatch, schedule, bridge=None):
    clock = SimpleNamespace(now=0)
    monkeypatch.setattr(bridge_module, "monotonic", lambda: clock.now)
    completed = Notification(method="turn/completed", payload=TurnCompletedNotification.model_validate({
        "threadId": "thread.test", "turn": {"id": "turn.test", "status": "completed", "items": [], "error": None},
    }))

    class Handle:
        id = "turn.test"
        thread_id = "thread.test"

        async def stream(self):
            for timestamp, event in schedule:
                clock.now = timestamp
                yield event
            yield completed

    lines = []
    result = await (bridge or SdkCodexBridge())._collect_tapped(Handle(), lambda line: lines.append((clock.now, line)))
    return result, lines


async def test_fresh_usage_increase_after_quiet_is_throttled_and_preserves_sdk_result(monkeypatch):
    result, lines = await collect(monkeypatch, [(0, usage(10)), (30, usage(11)), (31, usage(12)), (60, usage(13))])
    assert lines == [(30, "Member activity continued"), (60, "Member activity continued")]
    assert result.status.value == "completed"
    assert result.usage.total.total_tokens == 13 and result.usage.last.input_tokens == 13
    assert result.items == []


async def test_duplicate_zero_and_decreasing_totals_do_not_claim_activity(monkeypatch):
    _, lines = await collect(monkeypatch, [(0, usage(10)), (30, usage(10)), (60, usage(0)),
                                         (90, usage(9)), (120, usage(10))])
    assert lines == []


async def test_first_cumulative_snapshot_is_only_a_baseline_even_after_long_silence(monkeypatch):
    _, lines = await collect(monkeypatch, [(300, usage(500))])
    assert lines == []


@pytest.mark.parametrize("item,expected", [
    (command_item(), "completed: rg target papers"),
    ({"type": "webSearch", "id": "search.one", "query": "current sources"}, "searched: current sources"),
])
async def test_detailed_activity_resets_quiet_time_and_suppressed_increases_are_not_replayed(monkeypatch, item, expected):
    result, lines = await collect(monkeypatch, [(0, usage(10)), (29, notification(item)),
                                             (31, usage(11)), (60, usage(11)), (61, usage(12))])
    assert lines == [(29, expected), (61, "Member activity continued")]
    assert len(result.items) == 1 and result.items[0].root.id == item["id"]


@pytest.mark.parametrize("identity", [{"thread": "thread.other"}, {"turn": "turn.other"}])
async def test_usage_from_another_thread_or_turn_cannot_emit_or_change_the_baseline(monkeypatch, identity):
    result, lines = await collect(monkeypatch, [(0, usage(10)), (31, usage(10000, **identity)), (32, usage(11))])
    assert lines == [(32, "Member activity continued")]
    assert result.usage.total.total_tokens == 11


async def test_usage_baseline_and_throttle_belong_to_each_collected_turn(monkeypatch):
    bridge = SdkCodexBridge()
    _, first = await collect(monkeypatch, [(0, usage(1000)), (31, usage(1001))], bridge)
    _, second = await collect(monkeypatch, [(40, usage(10)), (70, usage(11))], bridge)
    assert first == [(31, "Member activity continued")]
    assert second == [(70, "Member activity continued")]
