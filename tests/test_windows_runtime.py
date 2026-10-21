"""Shared native setup must not share member memory or alter permissions."""

from pathlib import Path
from types import SimpleNamespace
import tomllib

from model_forge_codex import windows_runtime


def test_windows_reuses_selected_home_with_separate_member_state(tmp_path, monkeypatch):
    selected = tmp_path / "Shared user's Codex 日本語"
    member = tmp_path / "Research lead's home"
    environment = {"CODEX_HOME": str(selected)}
    monkeypatch.setattr(windows_runtime, "os", SimpleNamespace(name="nt", environ=environment))

    runtime_home, arguments = windows_runtime.runtime_settings(member)
    config = tomllib.loads("\n".join(arguments))

    assert runtime_home == selected.resolve()
    assert config == {
        "sqlite_home": str((member / "state").resolve()),
        "memories": {"use_memories": False, "generate_memories": False},
        "features": {"memories": False},
        "project_doc_max_bytes": 0,
        "skills": {"include_instructions": False},
    }
    assert not selected.exists() and not member.exists()
    assert environment == {"CODEX_HOME": str(selected)}


def test_windows_defaults_to_user_home_and_keeps_members_distinct(tmp_path, monkeypatch):
    monkeypatch.setattr(windows_runtime, "os", SimpleNamespace(name="nt", environ={}))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "user"))
    first_home, first_args = windows_runtime.runtime_settings(tmp_path / "lead")
    second_home, second_args = windows_runtime.runtime_settings(tmp_path / "theorist")

    assert first_home == second_home == (tmp_path / "user" / ".codex").resolve()
    first = tomllib.loads("\n".join(first_args))
    second = tomllib.loads("\n".join(second_args))
    assert first["sqlite_home"] != second["sqlite_home"]
    # The user's native implementation and the bridge's explicit permissions
    # remain authoritative; this helper cannot enable an unsandboxed runtime.
    assert {"windows", "sandbox_mode", "approval_policy", "sandbox_workspace_write"}.isdisjoint(first)


def test_non_windows_keeps_existing_member_home(tmp_path, monkeypatch):
    member = tmp_path / "member"
    monkeypatch.setattr(
        windows_runtime, "os",
        SimpleNamespace(name="posix", environ={"CODEX_HOME": str(tmp_path / "shared")}),
    )

    runtime_home, arguments = windows_runtime.runtime_settings(member)

    assert runtime_home is member
    assert arguments == ()
