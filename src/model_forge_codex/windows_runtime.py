"""Reuse the user's native Windows sandbox without duplicating its identities.

Codex 0.147 stores native sandbox setup under CODEX_HOME but uses machine-wide
sandbox users. Provisioning that setup separately for each member rotates the
same users' passwords. Keep runtime setup shared and member state separate.

The shared user's global AGENTS instructions remain researcher-wide guidance.
The bridge supplies each member's exact role instructions per thread. The
project-doc setting below only disables additional project AGENTS discovery.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class P4WindowsSetupError(RuntimeError):
    """The selected native setup cannot enforce the managed P4 contract."""


def require_p4_windows_setup(config: dict, readiness: str) -> dict:
    """Validate native config/read output, never infer mode from OS groups.

    Codex 0.147 resolves explicit windows.sandbox before its legacy feature
    flags. config/read supplies selected layers and exact managed requirements;
    reading just the user's config.toml would miss those settings.
    """
    windows = config.get("windows") or {}
    features = config.get("features") or {}
    mode = windows.get("sandbox")
    if mode is None:
        if features.get("elevated_windows_sandbox") is True:
            mode = "elevated"
        elif any(features.get(name) is True for name in
                 ("experimental_windows_sandbox", "enable_experimental_windows_sandbox")):
            mode = "unelevated"
    if mode != "elevated":
        raise P4WindowsSetupError(
            "Managed P4 experiments on Windows require Codex's elevated sandbox mode "
            "to preserve the required read, denied-read and write boundaries. "
            f"The selected mode is {mode or 'not configured'}. Select elevated sandbox "
            "mode and complete its setup in Codex, then continue P4. "
            "No computation was started."
        )
    if readiness != "ready":
        raise P4WindowsSetupError(
            "Managed P4 experiments on Windows require completed elevated sandbox setup. "
            f"Codex reports {readiness}. Complete or repair elevated sandbox setup in "
            "Codex, then continue P4. No computation was started."
        )
    return {"status": "passed", "windows_sandbox_mode": mode, "readiness": readiness}


def runtime_settings(member_home: Path) -> tuple[Path, tuple[str, ...]]:
    """Return SDK home and process config arguments without changing any files.

    The caller must verify the selected account and native sandbox readiness.
    No approval, network, or filesystem permission settings are changed here.
    """
    if os.name != "nt":
        return member_home, ()

    configured_home = os.environ.get("CODEX_HOME", "").strip()
    runtime_home = (
        Path(configured_home).expanduser() if configured_home else Path.home() / ".codex"
    ).resolve()
    # JSON string escaping is also valid for TOML basic strings. These are
    # individual SDK argv values, never interpolated into a shell command.
    sqlite_home = json.dumps(str((member_home / "state").resolve()), ensure_ascii=False)
    overrides = (
        f"sqlite_home={sqlite_home}",
        "memories.use_memories=false",
        "memories.generate_memories=false",
        "features.memories=false",
        "project_doc_max_bytes=0",
        "skills.include_instructions=false",
    )
    return runtime_home, overrides
