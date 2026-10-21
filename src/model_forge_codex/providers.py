"""Optional shared provider settings.

The file is the single source of truth: the Team Settings editor validates
and rewrites it atomically, and hand edits are honored on the next read.
Stored api_key values leave the backend only through the guarded editor
endpoint; they are never written to research artifacts, run records, or logs.
"""
from __future__ import annotations

import os
import re
import tempfile
import threading
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from .domain import MemberRole
from .storage import sha256_bytes


CONTROLLED_FIELDS = frozenset({"provider", "provider_id", "provider_base_url", "provider_env_key", "model", "reasoning_effort"})
FILE_KEY_ENV = "MODEL_FORGE_PROVIDER_API_KEY"

# Serialization order for editor saves (connection fields first, credentials last).
EDITOR_KEY_ORDER = ("type", "id", "base_url", "model", "reasoning_effort", "api_key", "api_key_env")


class ProviderConfigError(ValueError):
    pass


class ProviderConfigConflict(ProviderConfigError):
    """The file changed between the editor's snapshot and this save."""


@dataclass
class ResolvedMember:
    """One member's effective settings resolved together with its credentials.

    config is the public effective-settings view (status surfaces); environment
    is the credential mapping to inject into this member's child process;
    strip_keys are the credential names to remove from the inherited child
    environment first. Status, execution capture, and the connection probe all
    consume this single resolution so they cannot disagree about credentials."""
    config: dict
    environment: dict
    strip_keys: tuple


def provider_config_path(data_root: Path) -> Path:
    """Resolve the configured provider file (MF_CODEX_PROVIDER_CONFIG wins)."""
    configured = os.environ.get("MF_CODEX_PROVIDER_CONFIG", "").strip()
    return (Path(configured).expanduser() if configured else data_root / "providers.toml").resolve()


def _text(value, message):
    if not isinstance(value, str) or not value.strip():
        raise ProviderConfigError(message)
    return value.strip()


def _effort(value):
    from openai_codex.generated.v2_all import ReasoningEffort
    allowed = {item.value for item in ReasoningEffort}
    if not isinstance(value, str) or value not in allowed:
        raise ProviderConfigError("reasoning_effort must be a supported SDK value: " + ", ".join(sorted(allowed)) + ".")
    return value


def _connection(provider: dict):
    """Parse a complete connection; never borrow another connection's fields."""
    kind = provider.get("type")
    if kind not in {"openai", "custom"}:
        raise ProviderConfigError("provider.type must be 'openai' or 'custom'.")
    allowed = {"type", "model", "reasoning_effort"}
    if kind == "custom":
        allowed |= {"id", "base_url", "api_key", "api_key_env"}
    if set(provider) - allowed:
        raise ProviderConfigError("The provider table contains unsupported fields for its type.")
    settings = {"provider": kind, "model": _text(provider.get("model"), "Each complete provider definition requires a nonblank model."),
                "reasoning_effort": _effort(provider.get("reasoning_effort", "xhigh")),
                "provider_id": "openai", "provider_base_url": "", "provider_env_key": ""}
    if kind == "openai":
        return settings, "account", {}
    identifier = _text(provider.get("id"), "Custom providers require a nonblank id.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", identifier) or identifier == "openai":
        raise ProviderConfigError("Custom provider id must use letters, digits, underscores or hyphens and must not be 'openai'.")
    url = _text(provider.get("base_url"), "Custom providers require a base_url.")
    parsed = urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment or any(c.isspace() for c in url)):
        raise ProviderConfigError("Provider base_url must be an HTTP(S) endpoint without embedded credentials, query parameters or fragments.")
    parsed.port
    if ("api_key" in provider) == ("api_key_env" in provider):
        raise ProviderConfigError("Custom providers require exactly one of api_key or api_key_env.")
    if "api_key" in provider:
        key = _text(provider["api_key"], "provider.api_key must be a nonblank string.")
        env_name, source = FILE_KEY_ENV, "file"
    else:
        env_name = _text(provider["api_key_env"], "provider.api_key_env must name an environment variable.")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_name):
            raise ProviderConfigError("provider.api_key_env must name an environment variable.")
        key, source = os.environ.get(env_name, ""), "environment"
    settings.update(provider_id=identifier, provider_base_url=url, provider_env_key=env_name)
    return settings, source, {env_name: key} if key else {}


@dataclass
class ProviderConfig:
    path: Path
    exists: bool = False
    error: str | None = None
    settings: dict = field(default_factory=dict)
    members: dict = field(default_factory=dict)
    credential_source: str = "account"
    _environment: dict = field(default_factory=dict, repr=False)
    _member_environments: dict = field(default_factory=dict, repr=False)
    _member_credential_sources: dict = field(default_factory=dict, repr=False)

    @property
    def active(self):
        return self.exists and self.error is None

    def status(self):
        return {"path": str(self.path), "exists": self.exists, "active": self.active, "error": self.error}

    def settings_for(self, role: str):
        return {**self.settings, **self.members.get(role, {})}

    def governs(self, role: str):
        """Whether this file controls the member's provider settings: a
        [provider] default governs every member; a [members.<role>] table
        governs that member. Other members keep their per-project settings."""
        return self.active and (bool(self.settings) or role in self.members)

    def require_ready(self, role: str | None = None):
        if self.error:
            raise ProviderConfigError(self.error)
        if self.active:
            for selected in (role,) if role else (member.value for member in MemberRole):
                if self.governs(selected) and self.settings_for(selected)["provider"] == "custom" and not self._member_environments.get(selected, self._environment):
                    raise ProviderConfigError("The configured provider API key environment variable is not available to this backend process for " + selected + ".")

    def environment(self, role: str | None = None):
        self.require_ready(role)
        return dict(self._member_environments.get(role, self._environment))

    def environment_keys(self):
        """Credential variable names to remove before injecting one role's key."""
        return tuple(sorted({settings["provider_env_key"] for settings in (self.settings, *self.members.values())
                             if settings.get("provider_env_key")})) if self.active else ()

    def resolve_member(self, stored: dict, role: str, member_home: Path) -> ResolvedMember:
        """Resolve settings and credentials together for one member.

        A governed member receives the file's credential environment. An
        ungoverned member with a custom provider receives its own
        provider_env_key value from this process's environment, so a variable
        name that also appears in the file configuration still carries this
        member's own credential. strip_keys always covers every name the
        bridge must clear first: all file-managed names plus the member's own,
        so unrelated credentials stay excluded while the intended member
        receives its own."""
        result = dict(stored)
        governed = self.governs(role)
        if governed:
            result.update(self.settings_for(role))
        source = (self._member_credential_sources.get(role, self.credential_source) if governed else
                  "environment" if result.get("provider") == "custom" else "account")
        configured = (bool(self._member_environments.get(role, self._environment)) if governed and source != "account" else
                      bool(os.environ.get(result.get("provider_env_key", ""))) if source == "environment" else
                      (member_home / "auth.json").is_file())
        result.update(provider_source="file" if governed else "member", provider_config_path=str(self.path),
                      credential_source=source, credential_configured=configured)
        if governed:
            environment = dict(self._member_environments.get(role, self._environment))
        else:
            env_key = result.get("provider_env_key", "") if result.get("provider") == "custom" else ""
            value = os.environ.get(env_key, "") if env_key else ""
            environment = {env_key: value} if value else {}
        strip_keys = tuple(sorted(set(self.environment_keys()) | set(environment)))
        return ResolvedMember(config=result, environment=environment, strip_keys=strip_keys)

    def effective_member(self, stored: dict, role: str, member_home: Path):
        return self.resolve_member(stored, role, member_home).config


def _apply_document(result: ProviderConfig, document: dict) -> None:
    """Validate a parsed document into result. Never echo file content in errors.

    Member-first: the [provider] default is optional. A [members.<role>] table
    with a type is a complete standalone connection; a table with only model or
    reasoning_effort merges with the default, so it requires one."""
    if set(document) - {"provider", "members"}:
        raise ProviderConfigError("Provider configuration contains unsupported top-level fields.")
    provider = document.get("provider")
    if provider is not None:
        if not isinstance(provider, dict):
            raise ProviderConfigError("The [provider] default must be a TOML table.")
        result.settings, result.credential_source, result._environment = _connection(provider)
    overrides = document.get("members", {})
    if not isinstance(overrides, dict) or set(overrides) - {role.value for role in MemberRole}:
        raise ProviderConfigError("The members table must use the four existing team role IDs.")
    members = {}
    for role, override in overrides.items():
        if not isinstance(override, dict):
            raise ProviderConfigError("Member overrides must be TOML tables.")
        if "type" in override:
            try:
                members[role], result._member_credential_sources[role], result._member_environments[role] = _connection(override)
            except ProviderConfigError as exc:
                raise ProviderConfigError("members." + role + ": " + str(exc)) from None
        elif override:
            if set(override) - {"model", "reasoning_effort"}:
                raise ProviderConfigError("Member connection fields require an explicit type and complete provider definition.")
            if provider is None:
                raise ProviderConfigError("members." + role + ": model and reasoning effort overrides require a [provider] default table.")
            members[role] = {name: (_effort(value) if name == "reasoning_effort" else
                                    _text(value, "Member model overrides must be nonblank strings."))
                             for name, value in override.items()}
    result.members = members


def _provider_config_from_document(path: Path, document: dict) -> ProviderConfig:
    """Validate one parsed document. Never include file content in errors."""
    result = ProviderConfig(path, exists=True)
    try:
        _apply_document(result, document)
    except ProviderConfigError as exc:
        result.error = str(exc)
    except (ValueError, TypeError):
        result.error = "Provider configuration contains an invalid value. Check the provider endpoint and field types."
    if result.error:
        result.settings = {}
        result.members = {}
        result._environment = {}
        result._member_environments = {}
        result._member_credential_sources = {}
    return result


def _parse_snapshot(path: Path, raw: bytes) -> tuple[ProviderConfig, dict | None]:
    """(validated config, raw document) from one byte snapshot of the file.
    The raw document is None when the bytes are not parseable TOML."""
    try:
        document = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError:
        return ProviderConfig(path, exists=True,
                              error="Provider configuration is not valid TOML. Check its syntax locally."), None
    except (ValueError, TypeError):
        return ProviderConfig(path, exists=True,
                              error="Provider configuration contains an invalid value. Check the provider endpoint and field types."), None
    return _provider_config_from_document(path, document), document


def load_provider_config(data_root: Path) -> ProviderConfig:
    """Read on each request/turn. Never include file content in error messages."""
    path = provider_config_path(data_root)
    try:
        if not path.exists():
            return ProviderConfig(path)
        raw = path.read_bytes()
    except OSError:
        return ProviderConfig(path, exists=True,
                              error="Provider configuration could not be read. Check the file and its permissions.")
    return _parse_snapshot(path, raw)[0]


def provider_config_token(path: Path) -> str:
    """Freshness token for the editor's conflict guard: content digest, or 'missing'."""
    try:
        return "sha256:" + sha256_bytes(path.read_bytes())
    except OSError:
        return "missing"


def preview_provider_config(path: Path, document: dict) -> ProviderConfig:
    """Validate an unsaved editor document as if it were the file on disk.
    Nothing is written; the result resolves members against the draft, so a
    connection probe tests exactly what a turn would use after saving."""
    return _provider_config_from_document(path, normalize_editor_document(document))


def _editor_table(table: dict) -> dict:
    """One raw table for the editor. Scalar values are coerced to strings;
    nested TOML values are dropped (the load error already reports the file)."""
    result = {}
    for key, value in table.items():
        if isinstance(value, str):
            result[str(key)] = value
        elif isinstance(value, bool):
            result[str(key)] = "true" if value else "false"
        elif isinstance(value, (int, float)):
            result[str(key)] = str(value)
    return result


def editor_view(data_root: Path) -> dict:
    """Secrets-bearing editor view of the provider file. Serve only behind the
    same-origin JSON guard: the document includes stored api_key values.

    The document, freshness token, and validation state all derive from one
    byte snapshot: a hand edit mid-read cannot pair an old document with a
    token for newer bytes (which would let a later save pass the staleness
    check and silently overwrite the edit)."""
    path = provider_config_path(data_root)
    try:
        raw = path.read_bytes()
    except OSError:
        raw = None
    if raw is None:
        error = "Provider configuration could not be read. Check the file and its permissions." if path.exists() else None
        return {"path": str(path), "exists": error is not None, "error": error,
                "token": "missing", "document": None if error else {"provider": {}, "members": {}}}
    config, document = _parse_snapshot(path, raw)
    if isinstance(document, dict):
        members = document.get("members")
        editor_document = {
            "provider": _editor_table(document["provider"]) if isinstance(document.get("provider"), dict) else {},
            "members": {str(role): _editor_table(table) for role, table in members.items()
                        if isinstance(table, dict)} if isinstance(members, dict) else {},
        }
    else:
        editor_document = None
    return {"path": str(path), "exists": True, "error": config.error,
            "token": "sha256:" + sha256_bytes(raw), "document": editor_document}


def normalize_editor_document(document: dict) -> dict:
    """JSON editor document -> TOML-ready tables. Blank strings are dropped;
    a blank provider or member table disappears (no default / the member
    is not governed by the file)."""
    if not isinstance(document, dict) or set(document) - {"provider", "members"}:
        raise ProviderConfigError("The provider editor document must contain only provider and members tables.")
    provider = document.get("provider") or {}
    members = document.get("members") or {}

    def clean(table, label):
        if not isinstance(table, dict):
            raise ProviderConfigError(f"The {label} table must be an object of string fields.")
        result = {}
        for key, value in table.items():
            if not isinstance(value, str):
                raise ProviderConfigError(f"The {label} field {key!r} must be a string.")
            if value.strip():
                result[str(key)] = value.strip()
        return result

    normalized = {"members": {str(role): cleaned for role, table in members.items()
                              if (cleaned := clean(table, f"members.{role}"))}}
    cleaned_provider = clean(provider, "provider")
    if cleaned_provider:
        normalized["provider"] = cleaned_provider
    return normalized


def _toml_basic(value: str) -> str:
    escapes = {"\\": "\\\\", '"': '\\"', "\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r"}
    out = []
    for char in value:
        if char in escapes:
            out.append(escapes[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04X}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def _dump_table(lines: list[str], header: str, table: dict) -> None:
    lines.append(header)
    keys = [key for key in EDITOR_KEY_ORDER if key in table]
    keys += sorted(key for key in table if key not in EDITOR_KEY_ORDER)
    for key in keys:
        lines.append(f"{key} = {_toml_basic(table[key])}")


def dump_provider_config(document: dict) -> str:
    """Serialize a validated editor document. The [provider] default is
    optional; comments and formatting from a hand-edited file are normalized
    away by this canonical form."""
    lines = ["# Provider settings for this backend (see config/providers.example.toml).",
             "# Edit by hand or in Team Settings; a UI save rewrites this file in this form."]
    blocks = []
    if document.get("provider"):
        block = []
        _dump_table(block, "[provider]", document["provider"])
        blocks.append(block)
    members = document.get("members", {})
    roles = [role.value for role in MemberRole if role.value in members]
    roles += sorted(role for role in members if role not in roles)
    for role in roles:
        block = []
        _dump_table(block, f"[members.{role}]", members[role])
        blocks.append(block)
    body = "\n\n".join("\n".join(block) for block in blocks)
    return "\n".join(lines) + ("\n\n" + body if body else "") + "\n"


_WRITE_LOCK = threading.Lock()

_CONFLICT_MESSAGE = ("The provider file changed on disk since this editor loaded. "
                     "Refresh the editor and try again.")


def write_provider_config(path: Path, document: dict, expected_token: str | None = None) -> str:
    """Validate an editor document, then atomically replace the file (unique
    temp file per save, then rename, mirroring storage.py). An all-blank
    document removes the file, restoring per-project member settings. Returns
    the freshness token of the resulting state ("missing" after a removal).

    With expected_token the save is guarded, including removal: the token must
    match the file's current bytes or the save fails with ProviderConfigConflict
    and changes nothing. The module lock serializes writers inside this
    process and the token is rechecked against the current bytes immediately
    before the removal or replacement. External editors honor neither the lock
    nor the token, so an external write racing the final filesystem operation
    cannot be excluded; ordinary intervening edits are detected and rejected."""
    normalized = normalize_editor_document(document)
    removal = not normalized.get("provider") and not normalized["members"]
    payload = b""
    if not removal:
        probe = ProviderConfig(path)
        try:
            _apply_document(probe, normalized)
        except ProviderConfigError:
            raise
        except (ValueError, TypeError):
            raise ProviderConfigError("Provider configuration contains an invalid value. Check the provider endpoint and field types.") from None
        payload = dump_provider_config(normalized).encode("utf-8")
    with _WRITE_LOCK:
        if expected_token is not None and expected_token != provider_config_token(path):
            raise ProviderConfigConflict(_CONFLICT_MESSAGE)
        if removal:
            path.unlink(missing_ok=True)
            return "missing"
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False)
        try:
            handle.write(payload)
            handle.close()
            if expected_token is not None and expected_token != provider_config_token(path):
                raise ProviderConfigConflict(_CONFLICT_MESSAGE)
            os.replace(handle.name, path)
        except BaseException:
            if not handle.closed:
                handle.close()
            Path(handle.name).unlink(missing_ok=True)
            raise
        return "sha256:" + sha256_bytes(payload)
