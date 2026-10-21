"""Capture member settings applied to one turn, excluding authentication data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class ExecutionSettings(dict):
    """JSON-compatible public settings with process-only credential injection."""

    def __init__(self, settings, environment=None, environment_keys=()):
        super().__init__(settings)
        self.provider_environment = dict(environment or {})
        self.provider_environment_keys = tuple(environment_keys)


def redact_execution_text(execution, text: str) -> str:
    for name, secret in getattr(execution, "provider_environment", {}).items():
        if name == "SHIM_DUMMY" and secret == "x":
            continue  # The documented local shim placeholder is public.
        if secret:
            text = text.replace(secret, "[provider credential redacted]")
    return text


def capture_execution(config: dict, member_home: Path, provider_environment: dict | None = None,
                      provider_environment_keys: tuple[str, ...] = ()) -> dict:
    instructions_path = member_home / "AGENTS.md"
    instructions = instructions_path.read_bytes() if instructions_path.is_file() else b""
    provider = config.get("provider", "openai")
    result = {
        "model": config.get("model", "gpt-6.1-sol"),
        "reasoning_effort": config.get("reasoning_effort", "xhigh"),
        "provider": provider,
        "provider_id": config.get("provider_id", "") if provider == "custom" else "openai",
        "provider_base_url": config.get("provider_base_url", "") if provider == "custom" else "",
        "provider_env_key": config.get("provider_env_key", "") if provider == "custom" else "",
        "instructions": instructions.decode("utf-8"),
        "instructions_sha256": _digest(instructions),
        "instructions_source": str(instructions_path),
        "auto_compact_tokens": int(config.get("auto_compact_tokens") or 0),
        "max_turn_input_tokens": int(config.get("max_turn_input_tokens") or 0),
    }
    if provider not in ("openai", "custom"):
        raise ValueError("Unknown member provider mode")
    if provider == "custom" and not all(result[key] for key in ("provider_id", "provider_base_url", "provider_env_key")):
        raise ValueError("Custom provider settings are incomplete")
    result.update({key: config[key] for key in ("provider_source", "provider_config_path", "credential_source", "credential_configured")
                   if key in config})
    result["configuration_sha256"] = _digest(json.dumps(result, sort_keys=True, ensure_ascii=False).encode())
    return ExecutionSettings(result, provider_environment, provider_environment_keys)


def provider_fingerprint(execution: dict) -> str:
    settings = {key: execution.get(key) for key in ("provider", "provider_id", "provider_base_url", "provider_env_key")}
    return _digest(json.dumps(settings, sort_keys=True).encode())


def public_execution(execution: dict) -> dict:
    """Allowlisted provenance only. Never copy auth files or environment values."""
    result = {key: execution.get(key) for key in (
        "model", "reasoning_effort", "provider", "provider_id", "provider_env_key",
        "instructions_sha256", "instructions_source", "configuration_sha256",
        "auto_compact_tokens", "max_turn_input_tokens",
        "provider_source", "provider_config_path", "credential_source", "credential_configured",
    )}
    url = str(execution.get("provider_base_url") or "")
    if url:
        parsed = urlsplit(url)
        # Endpoint userinfo/query can contain credentials; they are never part
        # of the public execution receipt. The configuration digest binds bytes.
        hostname = parsed.hostname or ""
        netloc = f"[{hostname}]" if ":" in hostname else hostname
        if parsed.port:
            netloc += f":{parsed.port}"
        result["provider_base_url"] = urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    else:
        result["provider_base_url"] = ""
    return result


def sdk_settings(execution: dict) -> dict:
    # Research turns need current sources regardless of the host CLI default.
    config = {"model_reasoning_effort": execution["reasoning_effort"], "web_search": "live"}
    if execution["provider"] == "custom":
        provider_id = execution["provider_id"]
        config["model_providers"] = {provider_id: {
            "name": provider_id, "base_url": execution["provider_base_url"],
            "env_key": execution["provider_env_key"], "wire_api": "responses",
        }}
    return {"model": execution["model"], "model_provider": execution["provider_id"],
            "developer_instructions": execution["instructions"], "config": config}
