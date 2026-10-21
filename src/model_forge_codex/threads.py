"""Thread registry (design/01 §7, 04 §4, ADR-002).

Member threads are persistent Codex threads keyed (member, phase, branch).
They live in a project-level registry so they survive across runs and
service restarts:

    projects/<id>/branches/<branch_id>/threads.json

Trunk's registry also holds the research_lead's project-spanning thread
(key phase = PROJECT). Registries are atomic-write JSON like everything
else; corruption is loud at load time (storage.read_json raises).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .domain import ThreadKey
from .storage import read_json, write_json_atomic


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ThreadRegistration:
    thread_id: str
    created_at: str
    turns: int = 0
    input_tokens: int = 0  # cumulative across turns; reset on compaction
    output_tokens: int = 0  # cumulative across turns; reset on compaction
    archived: bool = False
    execution: dict = field(default_factory=dict)  # last acknowledged non-secret settings


class ThreadRegistry:
    """Registry for one branch directory."""

    def __init__(self, branch_dir: Path):
        self._path = branch_dir / "threads.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, ThreadRegistration] = {}
        if self._path.is_file():
            for key, doc in (read_json(self._path) or {}).items():
                self._entries[key] = ThreadRegistration(**doc)

    def lookup(self, key: ThreadKey) -> ThreadRegistration | None:
        reg = self._entries.get(key.as_string())
        if reg is None or reg.archived:
            return None
        return reg

    def reload(self) -> None:
        """Re-read from disk (call inside the engine's per-branch lock)."""
        self._entries = {}
        if self._path.is_file():
            for key, doc in (read_json(self._path) or {}).items():
                self._entries[key] = ThreadRegistration(**doc)

    def register(self, key: ThreadKey, thread_id: str) -> ThreadRegistration:
        reg = ThreadRegistration(thread_id=thread_id, created_at=_now())
        self._entries[key.as_string()] = reg
        self._save()
        return reg

    def note_turn(self, key: ThreadKey) -> None:
        reg = self._entries.get(key.as_string())
        if reg is not None:
            reg.turns += 1
            self._save()

    def note_usage(self, key: ThreadKey, input_tokens: int, output_tokens: int = 0) -> None:
        """Record the provider-reported cumulative thread input tokens
        (absolute, not a delta — Codex tracks totals per thread)."""
        reg = self._entries.get(key.as_string())
        if reg is not None and input_tokens >= 0:
            reg.input_tokens = input_tokens
            if output_tokens:
                reg.output_tokens = output_tokens
            self._save()

    def note_execution(self, key: ThreadKey, execution: dict) -> None:
        reg = self._entries.get(key.as_string())
        if reg is not None:
            reg.execution = dict(execution)
            self._save()

    def reset_tokens(self, key: ThreadKey) -> None:
        reg = self._entries.get(key.as_string())
        if reg is not None:
            reg.input_tokens = 0
            reg.output_tokens = 0
            self._save()

    def archive(self, key: ThreadKey) -> None:
        """Method retirement archives its branch threads (ADR-002)."""
        reg = self._entries.get(key.as_string())
        if reg is not None:
            reg.archived = True
            self._save()

    def all(self) -> dict[str, ThreadRegistration]:
        return dict(self._entries)

    def _save(self) -> None:
        write_json_atomic(self._path, {k: vars(v).copy() for k, v in self._entries.items()})
