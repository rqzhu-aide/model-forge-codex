"""Provider connection probes (plan 2026-09-20 §7, Workstream E).

One short bounded exchange per probe through the same client/credential path
as a real member turn: the bridge builds its client with the member's
resolved environment, starts a throwaway thread on an isolated home, asks the
model for one harmless tool call, submits that tool's result, and requires a
final response. Probes never touch research threads, run history, or project
documents; the isolated home and workspace are deleted on success, failure,
and timeout.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from uuid import uuid4

from .accounts import AccountError, AccountService
from .domain import MemberRole
from .execution import capture_execution, public_execution, redact_execution_text
from .members import codex_home
from .providers import (
    ProviderConfigError,
    load_provider_config,
    preview_provider_config,
    provider_config_path,
)
from .storage import read_json

#: One bounded exchange: connect, one model response, one tool round trip.
PROBE_TIMEOUT_SECONDS = 45

#: The probe's harmless tool: the model is asked to call it exactly once.
PROBE_TOOL = "provider_probe"

PROBE_PROMPT = (
    "This is an automated connection test, not a research task. "
    f'Call the {PROBE_TOOL} tool exactly once with {{"value": "ping"}}, then reply with the '
    'single word "pong". Do not use any other tool, do not read or write files, and do not browse the web.'
)

#: Ordered probe stages; the UI renders these to distinguish connection/model
#: response from tool compatibility.
CHECK_ORDER = ("configuration", "connection", "model_response", "tool_exchange", "final_response")

SUCCESS_MESSAGE = "Basic connection and tool use verified."

#: Actionable fixed messages per failure category. Details from the provider
#: are only ever surfaced redacted and truncated under "unknown".
FAILURE_MESSAGES = {
    "runtime_setup": "The local Windows Codex runtime is not ready. Complete its sandbox setup in Codex, connect the same OpenAI account if using account access, then test again in Team Settings.",
    "invalid_configuration": "The effective provider settings are incomplete or invalid.",
    "authentication": "The provider rejected the configured credential. Check the API key or its environment variable.",
    "model_unavailable": "The configured model is unavailable for this provider or account. Check the model name and account access.",
    "endpoint_protocol": "The endpoint did not answer as a Responses-compatible provider. Check the base URL and protocol support.",
    "tool_call": "The model responded, but the probe tool exchange did not complete; research turns need function-calling support.",
    "timeout": f"The provider did not complete the probe within {PROBE_TIMEOUT_SECONDS} seconds.",
    "rate_limit": "The provider rate-limited the probe. Wait a moment and try again.",
    "unknown": "The probe failed for a reason the harness could not classify.",
}

_PARTIAL_SUMMARY = "The provider connected and responded, but the probe tool exchange did not complete."


def probe_tool_spec() -> dict:
    return {"type": "function", "name": PROBE_TOOL,
            "description": "Connectivity check tool with no side effects. Call it exactly once with the value 'ping'.",
            "inputSchema": {"type": "object", "properties": {"value": {"type": "string"}},
                            "required": ["value"], "additionalProperties": False}}


def classify_probe_failure(text: str) -> str:
    """Map redacted failure text to a category, only where the evidence
    supports it; an unclassifiable failure stays "unknown"."""
    lowered = text.lower()
    if "windows sandbox" in lowered:
        return "runtime_setup"
    if "429" in lowered or "rate limit" in lowered or "rate_limit" in lowered or "too many requests" in lowered:
        return "rate_limit"
    if any(marker in lowered for marker in ("401", "403", "unauthorized", "forbidden",
                                            "authentication", "invalid api key", "incorrect api key")):
        return "authentication"
    if "model" in lowered and (any(marker in lowered for marker in ("404", "not found", "does not exist", "unknown model"))
                               or "model is not supported" in lowered and "chatgpt account" in lowered):
        return "model_unavailable"
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if any(marker in lowered for marker in ("404", "connection refused", "connect error", "name or service",
                                            "dns", "protocol", "unexpected end", "invalid response",
                                            "not a responses", "tls", "ssl")):
        return "endpoint_protocol"
    return "unknown"


def _failure(category: str, detail: str = "", execution=None) -> dict:
    message = FAILURE_MESSAGES[category]
    if category == "model_unavailable" and "model is not supported when using codex with a chatgpt account" in detail.lower():
        message = "The provider rejected this model for Codex with a ChatGPT account. Check the account's supported models before starting research."
    # invalid_configuration details are our own validation messages (designed
    # to never echo file content). Upstream text is surfaced only when the
    # failure could not be classified, redacted and truncated.
    if detail and category in ("invalid_configuration", "unknown"):
        safe = redact_execution_text(execution, detail).strip()
        if safe:
            message = message + " Detail: " + safe[:240]
    return {"category": category, "message": message}


def _result(role: str, scope: str, execution, *, simulated: bool, checks: dict,
            failure: dict | None, elapsed_ms: int, partial: bool = False) -> dict:
    if failure is None:
        status, summary = "ok", SUCCESS_MESSAGE
    elif partial:
        status, summary = "partial", _PARTIAL_SUMMARY
    else:
        status, summary = "failed", failure["message"]
    public = public_execution(execution) if execution else {}
    return {
        "role": role,
        "scope": scope,
        "simulated": bool(simulated),
        "status": status,
        "summary": summary,
        "checks": {stage: checks.get(stage, "skipped") for stage in CHECK_ORDER},
        "failure": failure,
        "provider": public.get("provider", ""),
        "provider_id": public.get("provider_id", ""),
        "provider_base_url": public.get("provider_base_url", ""),
        "model": public.get("model", ""),
        "elapsed_ms": elapsed_ms,
        "timeout_seconds": PROBE_TIMEOUT_SECONDS,
    }


def public_probe_result(raw: dict, *, role: str, scope: str, execution, elapsed_ms: int) -> dict:
    """Shape the bridge's raw report into the API payload (redacted, classified)."""
    checks = {stage: raw.get("checks", {}).get(stage, "skipped") for stage in CHECK_ORDER}
    error = str(raw.get("error") or "")
    simulated = bool(raw.get("simulated"))
    if not error and all(checks[stage] == "ok" for stage in CHECK_ORDER):
        return _result(role, scope, execution, simulated=simulated, checks=checks, failure=None,
                       elapsed_ms=elapsed_ms)
    if raw.get("timeout"):
        failure = _failure("timeout", execution=execution)
        return _result(role, scope, execution, simulated=simulated, checks=checks, failure=failure,
                       elapsed_ms=elapsed_ms)
    if checks.get("model_response") == "ok":
        # The provider connected and answered; the tool exchange or the final
        # response did not complete — a partial success, not a hard failure.
        category = classify_probe_failure(error) if error else "tool_call"
        failure = _failure(category if category != "unknown" else "tool_call", error, execution)
        return _result(role, scope, execution, simulated=simulated, checks=checks, failure=failure,
                       elapsed_ms=elapsed_ms, partial=True)
    category = classify_probe_failure(error) if error else "unknown"
    return _result(role, scope, execution, simulated=simulated, checks=checks,
                   failure=_failure(category, error, execution), elapsed_ms=elapsed_ms)


def _failed_before_probe(role: str, scope: str, execution, category: str, detail: str,
                         started: float, simulated: bool) -> dict:
    checks = {"configuration": "failed"}
    failure = _failure(category, detail, execution)
    return _result(role, scope, execution, simulated=simulated, checks=checks, failure=failure,
                   elapsed_ms=int((time.monotonic() - started) * 1000))


async def run_provider_probe(data_root: Path, engine, *, project_id: str, role: str,
                             draft_document: dict | None = None,
                             timeout: float = PROBE_TIMEOUT_SECONDS) -> dict:
    """Resolve the member's effective settings — the saved file plus stored
    member config, or an unsaved editor draft — and drive one bounded probe
    exchange. Provider failures return a classified result; only an unknown
    project or role raises ValueError."""
    started = time.monotonic()
    project_dir = engine.project_dir(project_id)
    if not (project_dir / "project.json").is_file():
        raise ValueError(f"unknown project {project_id}")
    try:
        member_role = MemberRole(role)
    except ValueError:
        raise ValueError(f"unknown role {role}") from None
    scope = "draft" if draft_document is not None else "saved"
    simulated = bool(getattr(engine.bridge, "simulated_bridge", False))

    path = provider_config_path(data_root)
    if draft_document is not None:
        try:
            config = preview_provider_config(path, draft_document)
        except ProviderConfigError as exc:
            return _failed_before_probe(role, scope, None, "invalid_configuration", str(exc), started, simulated)
        if config.error:
            return _failed_before_probe(role, scope, None, "invalid_configuration", config.error, started, simulated)
    else:
        config = load_provider_config(data_root)
        if config.error:
            return _failed_before_probe(role, scope, None, "invalid_configuration", config.error, started, simulated)

    stored = read_json(project_dir / "members" / role / "config.json") or {}
    resolved = config.resolve_member(stored, role, codex_home(project_dir, member_role))

    probe_root = data_root / "probes" / f"{role}-{uuid4().hex}"
    probe_home = probe_root / "codex-home"
    probe_workspace = probe_root / "workspace"
    try:
        probe_home.mkdir(parents=True, exist_ok=True)
        probe_workspace.mkdir(parents=True, exist_ok=True)
        # Mirror the isolated-turn home: same instructions and account auth,
        # short-lived and discarded afterwards. No project documents.
        member_home = codex_home(project_dir, member_role)
        for name in ("config.toml", "AGENTS.md", "auth.json"):
            source = member_home / name
            if source.is_file():
                shutil.copyfile(source, probe_home / name)
        if resolved.config.get("provider", "openai") == "openai":
            accounts = engine.account_service or AccountService(data_root)
            accounts.provision_probe_home(probe_home)
            resolved.config["credential_configured"] = (probe_home / "auth.json").is_file()
        try:
            execution = capture_execution(resolved.config, probe_home, resolved.environment, resolved.strip_keys)
        except ValueError as exc:
            return _failed_before_probe(role, scope, None, "invalid_configuration", str(exc), started, simulated)
        if not resolved.config.get("credential_configured"):
            env_key = resolved.config.get("provider_env_key", "")
            detail = (f"The API key environment variable {env_key} is not available to this backend process."
                      if resolved.config.get("credential_source") == "environment" and env_key else
                      "The configured account credential is not available for this member.")
            return _failed_before_probe(role, scope, execution, "invalid_configuration", detail, started, simulated)
        raw = await engine.bridge.probe_connection(member_home=probe_home, execution=execution,
                                                   workspace=probe_workspace, timeout=timeout)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return public_probe_result(raw, role=role, scope=scope, execution=execution, elapsed_ms=elapsed_ms)
    except (AccountError, OSError) as exc:
        detail = (str(exc) if isinstance(exc, AccountError) else
                  "The connection test could not prepare its temporary settings or account credential. Check local file permissions.")
        return _failed_before_probe(role, scope, None, "invalid_configuration", detail, started, simulated)
    finally:
        shutil.rmtree(probe_root, ignore_errors=True)
        try:
            probe_root.parent.rmdir()  # drop the probes/ parent when it is now empty
        except OSError:
            pass
