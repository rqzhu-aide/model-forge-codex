"""Storage primitives (design/03 §3).

- Every JSON write is temp-file-then-rename in the same directory.
- JSONL appends are whole-line; reads are resilient (skip-and-count bad
  lines, never silently return []).
- Digests are sha256 over exact bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_atomic(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(tmp, path)


def read_json(path: Path) -> Any | None:
    """Parse JSON; on corruption return None (caller decides; never [])."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def append_jsonl(path: Path, record: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)


def read_jsonl(path: Path) -> tuple[list[Any], int]:
    """Return (records, skipped_bad_line_count). Missing file → ([], 0)."""
    if not path.is_file():
        return [], 0
    records: list[Any] = []
    skipped = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            skipped += 1
    return records, skipped
