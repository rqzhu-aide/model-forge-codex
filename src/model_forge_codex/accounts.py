"""Explicit, local Codex account login and member credential provisioning.

Only status labels, the official device-login URL, and its short user code may
leave this module. CLI output and cached credentials are never API payloads.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .domain import MemberRole
from .providers import load_provider_config
from .storage import read_json, write_json_atomic


DEVICE_URL = "https://auth.openai.com/codex/device"
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CODE = re.compile(r"^(?:(?:enter|code|your code|one-time code)\s*:?\s*)?([A-Z0-9]{4}-[A-Z0-9]{4,6})$", re.I)


class AccountError(ValueError):
    """A safe, user-facing account operation failure."""


def find_codex() -> str | None:
    configured = os.environ.get("MF_CODEX_BIN", "").strip()
    if configured:
        candidate = Path(configured)
        if (not candidate.is_absolute() or not candidate.is_file()
                or candidate.suffix.lower() in (".cmd", ".bat", ".ps1")
                or (os.name == "nt" and candidate.suffix.lower() != ".exe")
                or not os.access(candidate, os.X_OK)):
            raise AccountError("MF_CODEX_BIN must name an existing absolute native Codex executable. Set it to an installed shared CLI, or unset it to use automatic discovery.")
        return str(candidate.resolve())
    executable = shutil.which("codex")
    if executable and Path(executable).suffix.lower() not in (".cmd", ".bat", ".ps1"):
        return executable
    try:
        from codex_cli_bin import bundled_codex_path
        candidate = Path(bundled_codex_path())
        return str(candidate) if candidate.is_file() else None
    except (ImportError, OSError, RuntimeError):
        return None


def _cache(home: Path) -> tuple[bytes, str] | None:
    """Private ChatGPT cache plus authorization fingerprint, never a response."""
    path = home / "auth.json"
    try:
        if path.is_symlink() or path.stat().st_size > 1_048_576:
            return None
        raw = path.read_bytes()
        doc = json.loads(raw)
        tokens = doc.get("tokens")
        if doc.get("auth_mode") not in (None, "chatgpt") or not isinstance(tokens, dict):
            return None
        if not all(isinstance(tokens.get(key), str) and tokens[key] for key in ("access_token", "refresh_token")):
            return None
        account_id = tokens.get("account_id")
        identity = ("chatgpt:" + account_id).encode() if isinstance(account_id, str) and account_id else raw
        return raw, hashlib.sha256(identity).hexdigest()
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def _ignore(directory: Path, entry: str) -> None:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / ".gitignore"
    previous = path.read_text(encoding="utf-8") if path.is_file() else ""
    if entry not in previous.splitlines():
        with path.open("a", encoding="utf-8") as handle:
            handle.write(("\n" if previous and not previous.endswith("\n") else "") + entry + "\n")


class AccountService:
    def __init__(self, data_root: Path, *, shared_home: Path | None = None, executable: str | None = None):
        self.data_root = data_root.resolve()
        self.directory = self.data_root / "account"
        self.home = self.directory / "codex-home"
        self.shared_home = (shared_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))).resolve()
        self._uses_shared_runtime = os.name == "nt"
        self._executable = executable
        self._lock = asyncio.Lock()
        self._process = None
        self._task: asyncio.Task | None = None
        self._state: str | None = None
        self._message: str | None = None
        self._user_code: str | None = None
        self._login_url: str | None = None

    @property
    def read_only(self) -> bool:
        return os.environ.get("MF_CODEX_READ_ONLY") == "1"

    def _writable(self) -> None:
        if self.read_only:
            raise AccountError("This viewer is read-only. Open the normal workspace service to connect an account.")

    def _cli(self) -> str | None:
        return self._executable or find_codex()

    def _connection(self) -> dict:
        try:
            value = read_json(self.directory / "connection.json")
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _source(self) -> tuple[str, Path]:
        if self._uses_shared_runtime:
            # The Windows sandbox runs on this home. A separate workspace
            # login cannot supply its account, even after a successful login.
            return "shared", self.shared_home
        selected = self._connection().get("source")
        if selected == "workspace" or (self.home / "auth.json").is_file():
            return "workspace", self.home
        return "shared", self.shared_home

    def _members(self, project_dir: Path | None = None):
        provider_config = load_provider_config(self.data_root)
        if provider_config.error:
            # Do not provision from stale manual settings when the shared
            # authority is invalid. Account status explains the paused work.
            return
        projects = [project_dir] if project_dir else sorted((self.data_root / "projects").glob("*"))
        for project in projects:
            for config_path in sorted((project / "members").glob("*/config.json")):
                try:
                    config = read_json(config_path) or {}
                    home = config_path.parent / "codex-home"
                    effective = provider_config.effective_member(config, config_path.parent.name, home)
                    if effective.get("provider", "openai") == "openai" and home.resolve().is_relative_to(self.data_root):
                        yield config_path, home
                except (OSError, ValueError, AttributeError):
                    continue

    def _counts(self) -> dict:
        counts = {"connected": 0, "existing": 0, "total": 0}
        fingerprint = self._connection().get("account_fingerprint")
        for _, home in self._members():
            counts["total"] += 1
            if (home / "auth.json").exists():
                cache = _cache(home)
                counts["connected" if cache and fingerprint and cache[1] == fingerprint else "existing"] += 1
        return counts

    def _environment(self, home: Path) -> dict:
        env = dict(os.environ)
        env["CODEX_HOME"] = str(home)
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN"):
            env.pop(key, None)
        return env

    async def _spawn(self, home: Path, *args: str):
        executable = self._cli()
        if not executable:
            raise FileNotFoundError("Codex CLI unavailable")
        return await asyncio.create_subprocess_exec(
            executable, *args, cwd=str(home), env=self._environment(home),
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    async def _cli_status(self, home: Path) -> tuple[str, str]:
        try:
            executable = self._cli()
        except AccountError as exc:
            return "unavailable", str(exc)
        if not executable:
            return "unavailable", "The shared Codex CLI is unavailable. Install Codex for this user to sign in."
        if not home.is_dir():
            return "signed_out", "Sign in with your OpenAI account to use account-backed members."
        process = None
        try:
            process = await self._spawn(home, "-c", 'cli_auth_credentials_store="file"', "login", "status")
            output, _ = await asyncio.wait_for(process.communicate(), timeout=8)
            # Recognize fixed CLI messages only. Never return process output.
            clean = _ANSI.sub("", output.decode("utf-8", errors="replace")).lower()
            if process.returncode == 0 and "logged in using chatgpt" in clean:
                return "signed_in", "Signed in with an OpenAI account."
            if "not logged in" in clean:
                return "signed_out", "Sign in with your OpenAI account to use account-backed members."
            if "api key" in clean:
                return "signed_out", "The shared CLI uses an API key. Sign in here to connect an OpenAI account."
            return "failed", "Codex could not confirm the account status. Try again or check the local Codex installation."
        except (OSError, asyncio.TimeoutError):
            return "unavailable", "Codex account status is unavailable. Check the local Codex installation."
        finally:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()

    async def status(self) -> dict:
        provider_config = load_provider_config(self.data_root)
        _, source_home = self._source()
        if self._state in ("waiting", "failed"):
            state, message = self._state, self._message or "Waiting for account sign-in."
        else:
            state, message = await self._cli_status(source_home)
        cache = _cache(source_home) if state == "signed_in" else None
        connection = self._connection()
        connected = bool(cache and connection.get("account_fingerprint") == cache[1])
        if state == "signed_in" and not cache:
            message = "The shared CLI is signed in, but its credentials are not available as a file. Sign in here to connect workspace members."
        elif connected:
            message = "This OpenAI account is connected for workspace members. Existing credentials are preserved."
            if provider_config.active:
                providers = {provider_config.settings_for(role.value)["provider"] for role in MemberRole
                             if provider_config.governs(role.value)}
                if providers == {"custom"}:
                    message = "This OpenAI account is connected. Team members currently use configured custom providers."
                elif providers == {"openai", "custom"}:
                    message = "This OpenAI account is connected for account-backed members. Other team members use custom providers. Existing credentials are preserved."
        if provider_config.error:
            message += " Member credential provisioning is paused: " + provider_config.error
        return {"state": state, "read_only": self.read_only, "message": message,
                "login_url": self._login_url if state == "waiting" else None,
                "user_code": self._user_code if state == "waiting" else None,
                "can_connect_existing": bool(cache), "connected": connected,
                "shared_runtime": self._uses_shared_runtime,
                "member_homes": self._counts(), "provider_config": provider_config.status()}

    async def start_login(self) -> dict:
        self._writable()
        async with self._lock:
            if self._task and not self._task.done():
                return await self.status()
            login_home = self.shared_home if self._uses_shared_runtime else self.home
            if (login_home / "auth.json").exists() or (login_home / "auth.json").is_symlink():
                # Never replace an existing credential cache through this control.
                state, _ = await self._cli_status(login_home)
                if state != "signed_in":
                    raise AccountError("The selected Codex home already has credentials that Codex cannot confirm. Check that account locally before starting another login.")
                self._state = None
                return await self.status()
            if not self._cli():
                return await self.status()
            _ignore(self.directory, "*")
            login_home.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                self._process = await self._spawn(login_home, "-c", 'cli_auth_credentials_store="file"', "login", "--device-auth")
            except OSError:
                self._state, self._message = "failed", "Codex could not start account sign-in. Check the local installation."
                return await self.status()
            self._state, self._message = "waiting", "Complete sign-in on OpenAI's device login page. Device-code login may need enabling in your account security settings."
            self._login_url, self._user_code = None, None
            self._task = asyncio.create_task(self._watch_login(self._process, login_home))
        return await self.status()

    async def _watch_login(self, process, login_home: Path) -> None:
        try:
            async with asyncio.timeout(900):
                while line := await process.stdout.readline():
                    clean = _ANSI.sub("", line.decode("utf-8", errors="replace")).strip()
                    # The URL is a fixed official endpoint, never an arbitrary CLI URL.
                    if DEVICE_URL in clean:
                        self._login_url = DEVICE_URL
                    match = _CODE.fullmatch(clean)
                    if match:
                        self._user_code = match.group(1).upper()
                await process.wait()
            if process.returncode == 0 and _cache(login_home):
                self._state, self._message = None, None
                # Successful login remains separate from explicit member connection.
            else:
                self._state, self._message = "failed", "Sign-in did not complete. Try again; device-code login may need enabling in your account security settings."
        except asyncio.CancelledError:
            raise
        except (OSError, ValueError, asyncio.TimeoutError):
            self._state, self._message = "failed", "Sign-in expired or could not finish. Try again."
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    async def cancel_login(self) -> dict:
        self._writable()
        await self.close()
        self._state, self._message = None, None
        self._login_url, self._user_code = None, None
        return await self.status()

    async def close(self) -> None:
        async with self._lock:
            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            # Cancellation can arrive before the watcher has entered its finally
            # block. The service still owns and must stop the pending process.
            if self._process is not None and self._process.returncode is None:
                self._process.kill()
                await self._process.wait()

    async def connect(self) -> dict:
        self._writable()
        async with self._lock:
            if self._state == "waiting":
                raise AccountError("Finish sign-in before connecting members.")
            # A newly completed workspace login takes precedence over a previous
            # shared connection only when the researcher explicitly connects it.
            source, home = self._source()
            state, _ = await self._cli_status(home)
            cache = _cache(home)
            if state != "signed_in" or not cache:
                raise AccountError("A file-backed OpenAI account login is required. Sign in here, then connect the account.")
            _ignore(self.directory, "*")
            write_json_atomic(self.directory / "connection.json", {"source": source, "account_fingerprint": cache[1]})
            self.provision_project()
            self._state, self._message = None, None
        return await self.status()

    def _connected_cache_bytes(self) -> bytes | None:
        """Return credentials only for the account explicitly connected here."""
        connection = self._connection()
        if not connection.get("account_fingerprint"):
            return None
        home = self.home if connection.get("source") == "workspace" else self.shared_home
        cache = _cache(home)
        if not cache or cache[1] != connection["account_fingerprint"]:
            return None  # A changed account requires another explicit connection.
        return cache[0]

    def provision_probe_home(self, probe_home: Path) -> None:
        """Use an existing connection in a temporary probe, without changing members.

        The draft being tested may select OpenAI while the saved member still
        uses a custom provider. Its saved provider filter therefore cannot
        decide whether this temporary home needs the connected account.
        """
        self._writable()
        if not probe_home.resolve().is_relative_to(self.data_root / "probes"):
            raise AccountError("Connection tests must use a temporary probe home.")
        raw = self._connected_cache_bytes()
        if raw is None:
            return
        destination = probe_home / "auth.json"
        try:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return  # Preserve the member credential already copied for this test.
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
        except OSError:
            destination.unlink(missing_ok=True)
            raise AccountError("The connected account could not be prepared for the connection test.") from None

    def provision_project(self, project_dir: Path | None = None) -> None:
        """Apply a saved explicit connection during a project/member mutation."""
        self._writable()
        raw = self._connected_cache_bytes()
        if raw is None:
            return
        for config_path, member_home in self._members(project_dir):
            destination = member_home / "auth.json"
            if destination.exists() or destination.is_symlink():
                continue
            _ignore(member_home, "auth.json")
            try:
                fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(raw)
            except OSError:
                destination.unlink(missing_ok=True)
                raise AccountError("The account was connected, but a member credential cache could not be written.") from None
            config = read_json(config_path)
            config["openai_auth_present"] = True
            write_json_atomic(config_path, config)
