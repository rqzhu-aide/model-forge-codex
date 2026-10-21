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
