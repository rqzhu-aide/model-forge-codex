import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from model_forge_codex.execution import ExecutionSettings
from model_forge_codex.kimi_web import KimiWebTools, MAX_RESPONSE_BYTES, SERVICE_ROOT, _public_url, install_handler, tool_specs, uses_kimi_web
from test_execution_control import running
from test_researcher_workbench_engine import workbench


@pytest.fixture(autouse=True)
def public_dns_only(monkeypatch):
    monkeypatch.delenv("MF_CODEX_PROVIDER_CONFIG", raising=False)
    monkeypatch.setattr("model_forge_codex.kimi_web.socket.getaddrinfo", lambda *_args, **_kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))])


def execution(secret="PRIVATE_KIMI_KEY"):
    return ExecutionSettings({"provider": "custom", "provider_id": "kimi", "provider_base_url": SERVICE_ROOT,
                              "provider_env_key": "TEST_KIMI_KEY", "model": "k3", "reasoning_effort": "high",
                              "instructions": "Research the supplied question."}, {"TEST_KIMI_KEY": secret})


def result_body(result):
    return json.loads(result["contentItems"][0]["text"])


def test_adapter_is_scoped_to_official_coding_endpoint():
    assert uses_kimi_web(execution())
    assert uses_kimi_web({**execution(), "provider_base_url": SERVICE_ROOT + "/"})
    for override in ({"provider": "openai"}, {"provider_base_url": "https://api.z.ai/api/v1"},
                     {"provider_base_url": SERVICE_ROOT + "@example.com"}, {"provider_base_url": "http://api.kimi.com/coding/v1"}):
        assert not uses_kimi_web({**execution(), **override})
    assert {spec["name"] for spec in tool_specs()} == {"search_web", "read_web_page"}


def test_search_preserves_actual_sources_with_explicit_excerpt_extent(monkeypatch):
    tool = KimiWebTools(execution())
    calls = []
    source = {"title": "An exact paper title", "url": "https://arxiv.org/abs/2609.12345", "snippet": "The actual service snippet.",
              "content": "A" * 9000, "date": "2026-09-10"}

    def post(endpoint, payload):
        calls.append((endpoint, payload))
        return json.dumps({"search_results": [source]}).encode(), "application/json"

    monkeypatch.setattr(tool, "_post", post)
    result = tool.call("search_web", {"query": "recent constrained reinforcement learning", "include_content": True, "limit": 7})
    body = result_body(result)
    assert result["success"]
    assert calls == [("search", {"text_query": "recent constrained reinforcement learning", "enable_page_crawling": True, "limit": 7, "timeout_seconds": 30})]
    record = body["results"][0]
    for key in ("title", "url", "snippet", "date"):
        assert record[key] == source[key]
    assert len(record["content"]) == 8000 and record["content_truncated"] and record["content_characters_available"] == 9000
    assert "full papers have not necessarily been read" in body["read_extent"]


def test_fetch_can_read_successive_exact_text_extents(monkeypatch):
    tool = KimiWebTools(execution())
    source = "Original mathematical source: " + "x" * 3000
    monkeypatch.setattr(tool, "_post", lambda *_: (source.encode(), "text/markdown; charset=utf-8"))
    result = tool.call("read_web_page", {"url": "https://arxiv.org/html/2609.12345", "offset": 1000, "max_chars": 1000})
    body = result_body(result)
    assert result["success"] and body["content"] == source[1000:2000]
    assert body["offset"] == 1000 and body["characters_available"] == len(source) and body["truncated"]
    assert "No local PDF download" in body["read_extent"]


@pytest.mark.parametrize("url", ["file:///C:/secret", "ftp://papers.org/a", "https://user:password@papers.org/", "http://localhost/", "http://127.0.0.1/", "http://10.0.0.1/", "http://[::1]/", "https://machine.local/", "https://intranet/", "https://papers.org/\nAuthorization: secret"])
def test_fetch_rejects_local_or_credential_bearing_urls(url):
    with pytest.raises(ValueError):
        _public_url(url)


def test_fetch_rejects_hostnames_resolving_to_private_networks(monkeypatch):
    monkeypatch.setattr("model_forge_codex.kimi_web.socket.getaddrinfo", lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="Private and local"):
        _public_url("https://private.papers.org/secret")


@pytest.mark.parametrize("failure", [HTTPError(SERVICE_ROOT, 401, "PRIVATE_KIMI_KEY", {}, None),
                                     URLError("PRIVATE_KIMI_KEY"), RuntimeError("PRIVATE_KIMI_KEY")])
def test_service_errors_are_contained_without_returning_credentials(monkeypatch, failure):
    tool = KimiWebTools(execution())
    def fail(*_):
        raise failure
    monkeypatch.setattr(tool, "_post", fail)
    result = tool.call("search_web", {"query": "papers"})
    assert not result["success"] and "PRIVATE_KIMI_KEY" not in json.dumps(result)
    assert "No source content was retrieved" in result_body(result)["error"]


def test_credentials_are_redacted_even_if_service_echoes_them(monkeypatch):
    tool = KimiWebTools(execution())
    monkeypatch.setattr(tool, "_post", lambda *_: (b'{"search_results":[{"title":"PRIVATE_KIMI_KEY"}]}', "application/json"))
    result = tool.call("search_web", {"query": "papers"})
    assert "PRIVATE_KIMI_KEY" not in json.dumps(result)
    assert "redacted" in result_body(result)["results"][0]["title"]


def test_transport_keeps_key_in_header_and_bounds_response(monkeypatch):
    tool = KimiWebTools(execution())
    requests = []
    class Response(io.BytesIO):
        headers = {"Content-Type": "application/json"}
    def open_request(request, timeout):
        requests.append((request, timeout))
        return Response(b"x" * (MAX_RESPONSE_BYTES + 1))
    tool._opener = SimpleNamespace(open=open_request)
    result = tool.call("search_web", {"query": "papers"})
    request, timeout = requests[0]
    assert request.full_url == SERVICE_ROOT + "/search" and timeout == 40
    assert request.get_header("Authorization") == "Bearer PRIVATE_KIMI_KEY"
    assert b"PRIVATE_KIMI_KEY" not in request.data
    assert not result["success"] and "4 MiB" in result_body(result)["error"]


def test_unrecognized_or_nontext_service_responses_do_not_claim_sources(monkeypatch):
    tool = KimiWebTools(execution())
    monkeypatch.setattr(tool, "_post", lambda *_: (b'{"unexpected":"PRIVATE_KIMI_KEY"}', "application/json"))
    assert not tool.call("search_web", {"query": "papers"})["success"]
    result = tool.call("read_web_page", {"url": "https://papers.org/a.pdf"})
    assert not result["success"] and "no PDF reading is claimed" in result_body(result)["error"]


def test_sdk_handler_dispatches_only_dynamic_tools_and_preserves_approvals(monkeypatch):
    preserved = []
    def previous(method, params):
        preserved.append((method, params))
        return {"decision": "decline"}
    transport = SimpleNamespace(_approval_handler=previous)
    client = SimpleNamespace(_client=SimpleNamespace(_sync=transport))
    monkeypatch.setattr(KimiWebTools, "_post", lambda *_: (b'{"search_results":[]}', "application/json"))
    install_handler(client, execution())
    handler = transport._approval_handler
    result = handler("item/tool/call", {"tool": "search_web", "arguments": {"query": "current papers"}, "threadId": "t", "callId": "c"})
    assert result["success"] and result_body(result)["results"] == []
    assert not handler("item/tool/call", {"tool": "unknown"})["success"]
    assert handler("item/commandExecution/requestApproval", {"command": "read"}) == {"decision": "decline"}
    assert preserved == [("item/commandExecution/requestApproval", {"command": "read"})]
    assert "PRIVATE_KIMI_KEY" not in json.dumps(result)


async def test_bridge_registers_tools_on_start_and_preserves_normal_resume(tmp_path, monkeypatch):
    from model_forge_codex.bridge import SdkCodexBridge
    bridge = SdkCodexBridge()
    captured = []
    response = SimpleNamespace(thread=SimpleNamespace(id="thread.kimi"), model="k3", model_provider="kimi", reasoning_effort="high")
    async def initialize():
        pass
    async def request(method, params, **kwargs):
        captured.append((method, params))
        return response
    async def resume(thread_id, params):
        captured.append(("thread/resume", params.model_dump(mode="json", by_alias=True, exclude_none=True)))
        return response
    client = SimpleNamespace(_ensure_initialized=initialize, _client=SimpleNamespace(request=request, thread_resume=resume,
                             _sync=SimpleNamespace(_approval_handler=lambda *_: {})))
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (home, ()))
    await bridge._configured_thread(client, tmp_path, execution())
    await bridge._configured_thread(client, tmp_path, execution(), "thread.kimi")
    method, params = captured[0]
    assert method == "thread/start" and params["modelProvider"] == "kimi"
    assert params["config"]["web_search"] == "disabled"
    assert "search_web" in params["developerInstructions"]
    assert {entry["name"] for entry in params["dynamicTools"]} == {"validate_artifacts", "search_web", "read_web_page"}
    assert captured[1][0] == "thread/resume" and "dynamicTools" not in captured[1][1]
    assert "PRIVATE_KIMI_KEY" not in json.dumps(captured)
    assert "PRIVATE_KIMI_KEY" not in json.dumps(bridge.execution_configuration("thread.kimi"))


async def test_other_providers_keep_native_search_with_member_validation(tmp_path, monkeypatch):
    from model_forge_codex.bridge import SdkCodexBridge
    bridge = SdkCodexBridge()
    captured = []
    async def initialize():
        pass
    async def request(method, params, **kwargs):
        assert method == "thread/start"
        captured.append(params)
        return SimpleNamespace(thread=SimpleNamespace(id="thread.other"), model="other", model_provider="zai", reasoning_effort="high")
    client = SimpleNamespace(_ensure_initialized=initialize, _client=SimpleNamespace(request=request,
                             _sync=SimpleNamespace(_approval_handler=lambda *_: {})))
    monkeypatch.setattr("model_forge_codex.bridge.runtime_settings", lambda home: (home, ()))
    await bridge._configured_thread(client, tmp_path, {**execution(), "provider_base_url": "https://api.z.ai/api/v1", "provider_id": "zai"})
    assert captured[0]["config"]["web_search"] == "live"
    assert [tool["name"] for tool in captured[0]["dynamicTools"]] == ["validate_artifacts"]


@pytest.mark.parametrize("same_run", [True, False])
async def test_engine_renews_only_when_persistent_web_tool_mode_changes(workbench, monkeypatch, same_run):
    from model_forge_codex.domain import MemberRole, StageSpec
    engine, _, branch = workbench
    monkeypatch.setattr(engine, "_render_brief", lambda *_: "Review current research sources.")
    stage = StageSpec("stage.test", 1, "serial", (MemberRole.RESEARCH_LEAD,), ())
    current = running(engine, branch, "run.web.0")
    ids = []
    for number, endpoint in enumerate(("https://api.z.ai/api/v1", SERVICE_ROOT, SERVICE_ROOT, "https://api.z.ai/api/v1")):
        (engine.data_root / "providers.toml").write_text(
            '[provider]\ntype="custom"\nid="test"\nmodel="test-model"\napi_key="PRIVATE_KIMI_KEY"\n'
            f'base_url="{endpoint}"\n', encoding="utf-8")
        if not same_run:
            current = running(engine, branch, f"run.web.{number}")
        directory = engine.run_dir(current.project_id, current.run_id)
        assert (await engine._drive_member_turn(current, stage, MemberRole.RESEARCH_LEAD, directory)).succeeded
        ids.append(engine.bridge.turns[-1]["thread_id"])
        engine.bridge._execution.clear()  # Subsequent checks must use persisted acknowledgements.
    assert ids[0] != ids[1] == ids[2] != ids[3]
    assert len(engine.bridge.threads) == 3


async def test_changed_web_tools_defer_optional_handoff_without_failing_scientific_turn(workbench, monkeypatch):
    from model_forge_codex.bridge import FakeCodexBridge
    from model_forge_codex.domain import MemberConfig, MemberRole, StageSpec
    from model_forge_codex.members import provision_member
    engine, project, branch = workbench
    provision_member(project, MemberConfig(role=MemberRole.RESEARCH_LEAD, auto_compact_tokens=1))
    monkeypatch.setattr(engine, "_render_brief", lambda *_: "Research sources.")
    def configure(endpoint):
        (engine.data_root / "providers.toml").write_text(
            '[provider]\ntype="custom"\nid="test"\nmodel="test-model"\napi_key="PRIVATE_KIMI_KEY"\n'
            f'base_url="{endpoint}"\n', encoding="utf-8")
    class ChangingBridge(FakeCodexBridge):
        async def run_turn(self, thread_id, **kwargs):
            outcome = await super().run_turn(thread_id, **kwargs)
            configure(SERVICE_ROOT)
            return outcome
    engine.bridge = ChangingBridge()
    configure("https://api.z.ai/api/v1")
    current = running(engine, branch, "run.web.handoff")
    stage = StageSpec("stage.test", 1, "serial", (MemberRole.RESEARCH_LEAD,), ())
    result = await engine._drive_member_turn(current, stage, MemberRole.RESEARCH_LEAD, engine.run_dir(current.project_id, current.run_id))
    assert result.succeeded and len(engine.bridge.turns) == 1
