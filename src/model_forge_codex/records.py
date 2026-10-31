"""Exact generation reads and one atomic current package per phase.

Legacy family/current.json pointers remain readable. New publication stages all
immutable generations and commits one package pointer, so readers never combine
half of one run with half of another.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .domain import new_id
from .storage import sha256_bytes, write_json_atomic


class ArtifactError(ValueError):
    pass


def _segment(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ArtifactError(f"Invalid artifact identifier: {value!r}")
    return value


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactError(f"Cannot read artifact metadata {path.name}: {exc}") from exc


def current_records(phase_dir: Path) -> dict[str, dict]:
    marker = phase_dir / "current-package.json"
    if marker.exists():
        package = _json(marker)
        if not isinstance(package, dict) or not isinstance(package.get("records"), dict):
            raise ArtifactError("Current phase package is malformed")
        return dict(package["records"])
    records = {}
    if phase_dir.is_dir():
        for family in sorted(p for p in phase_dir.iterdir() if p.is_dir()):
            pointer = family / "current.json"
            if pointer.exists():
                value = _json(pointer)
                if not isinstance(value, dict):
                    raise ArtifactError(f"Current pointer for {family.name} is malformed")
                records[family.name] = value
    return records


def committed_packages(phase_dir: Path):
    """Walk visible publication ancestry, newest first, never orphan manifests.

    Legacy family pointers are used only before the first atomic publication,
    or when that publication explicitly retained their exact references.
    """
    marker = phase_dir / "current-package.json"
    if not marker.is_file():
        records = current_records(phase_dir)
        if records:
            yield {"package_id": None, "records": records, "legacy": True,
                   "published_at": max((str(p.get("published_at", "")) for p in records.values()), default="")}
        return
    package = _json(marker)
    seen = set()
    while True:
        if not isinstance(package, dict) or not isinstance(package.get("records"), dict):
            raise ArtifactError("Committed phase package is malformed")
        package_id = _segment(str(package.get("package_id", "")))
        if package_id in seen:
            raise ArtifactError("Phase package ancestry contains a cycle")
        seen.add(package_id)
        yield package
        previous = package.get("previous_package_id")
        if previous:
            previous = _segment(str(previous))
            package = _json(phase_dir / "packages" / (previous + ".json"))
            if not isinstance(package, dict) or package.get("package_id") != previous:
                raise ArtifactError("Committed package ancestry has a mismatched identity")
            continue
        legacy = package.get("metadata", {}).get("legacy_records")
        if legacy:
            if not isinstance(legacy, dict) or not all(isinstance(p, dict) for p in legacy.values()):
                raise ArtifactError("Retained legacy publication references are malformed")
            yield {"package_id": None, "records": legacy, "legacy": True,
                   "published_at": max((str(p.get("published_at", "")) for p in legacy.values()), default="")}
        return


def current_package_token(phase_dir: Path) -> str:
    """Identify the current publication, including legacy family pointers."""
    marker = phase_dir / "current-package.json"
    if marker.exists():
        package = _json(marker)
        if not isinstance(package, dict) or not isinstance(package.get("records"), dict):
            raise ArtifactError("Current phase package is malformed")
        state = {"package": package}
    else:
        state = {"legacy_records": current_records(phase_dir)}
    return sha256_bytes(json.dumps(state, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def generation_path(phase_dir: Path, family: str, pointer: dict) -> Path:
    family = _segment(family)
    generation = _segment(str(pointer.get("generation_id", "")))
    suffix = ".jsonl" if pointer.get("format") == "jsonl" else ".json"
    path = phase_dir / family / "generations" / (generation + suffix)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ArtifactError(f"Generation {generation} for {family} is missing or unreadable") from exc
    expected = pointer.get("content_sha256") or pointer.get("sha256")
    if not expected or sha256_bytes(data) != expected:
        raise ArtifactError(f"Digest mismatch for {family}/{generation}")
    return path


def read_generation(phase_dir: Path, family: str, pointer: dict) -> Any:
    path = generation_path(phase_dir, family, pointer)
    try:
        text = path.read_text(encoding="utf-8")
        if pointer.get("format") == "jsonl":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        return json.loads(text)
    except (OSError, ValueError) as exc:
        raise ArtifactError(f"Generation {pointer.get('generation_id')} is not valid {pointer.get('format', 'json')}") from exc


def package_committed(phase_dir: Path, package_id: str) -> bool:
    """A prepared manifest is authoritative only in the committed ancestry."""
    marker = phase_dir / "current-package.json"
    if not marker.is_file():
        return False
    package = _json(marker)
    seen = set()
    while package.get("package_id") not in seen:
        current_id = package.get("package_id")
        if current_id == package_id:
            return True
        seen.add(current_id)
        previous = package.get("previous_package_id")
        if not previous:
            return False
        package = _json(phase_dir / "packages" / (_segment(previous) + ".json"))
    raise ArtifactError("Phase package ancestry contains a cycle")


def source_artifact_path(project_dir: Path, record_pointer: dict, artifact: dict) -> Path:
    """Resolve exact bytes only inside the record's producing run outputs."""
    run_id = _segment(str(record_pointer.get("run_id", "")))
    relative = str(artifact.get("path") or artifact.get("artifact_path") or "")
    expected = artifact.get("sha256") or artifact.get("artifact_sha256")
    if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts or not expected:
        raise ArtifactError("Artifact needs a safe relative path and exact digest")
    outputs = (project_dir / "runs" / run_id / "outputs").resolve()
    if not outputs.is_dir():
        raise ArtifactError(f"Source run {run_id} has no retained output files")
    stages = sorted((p for p in outputs.iterdir() if p.is_dir()),
                    key=lambda p: (p.name != record_pointer.get("stage_id"), p.name))
    for stage in stages:
        roots = [stage] + sorted(p for p in (stage / "working").glob("*") if p.is_dir())
        for root in roots:
            path = (root / relative).resolve()
            if path.is_relative_to(outputs) and path.is_file() and sha256_bytes(path.read_bytes()) == expected:
                return path
    raise ArtifactError(f"The supporting file could not be verified from the retained outputs (file: {relative}; source run {run_id})")


def publish_package(
    phase_dir: Path, records: dict[str, bytes], *, run_id: str, phase: str,
    branch_id: str, metadata: dict | None = None,
    before_commit: Callable[[dict], None] | None = None,
    expected_current: str | None = None,
) -> dict:
    """Stage exact bytes, then atomically replace the sole current pointer.

Optional before_commit writes receipts before visibility changes. Any exception
before the final replace leaves the entire prior package authoritative.
The expected-current check prevents stale work from replacing a later package
within the single service process; it is not distributed write coordination.
"""
    def check_current() -> None:
        if expected_current is not None and current_package_token(phase_dir) != expected_current:
            raise ArtifactError("Current research changed after this run was authorized; start a new revision against the current evidence")

    check_current()
    # Freeze the final legacy heads before an atomic package takes authority.
    # Later readers must follow these explicit references, never leftover
    # current.json files that might also contain unrelated orphan history.
    legacy_records = current_records(phase_dir) if not (phase_dir / "current-package.json").exists() else {}
    package_id = new_id("package")
    now = datetime.now(timezone.utc).isoformat()
    pointers = {}
    metadata = dict(metadata or {})
    if legacy_records:
        metadata["legacy_records"] = legacy_records
    formats = metadata.pop("formats", {})
    stage_ids = metadata.pop("stage_ids", {})
    for family, data in records.items():
        _segment(family)
        generation_id = new_id("generation")
        fmt = formats.get(family, "json")
        suffix = ".jsonl" if fmt == "jsonl" else ".json"
        path = phase_dir / family / "generations" / (generation_id + suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Generations are new unique files and never exposed until commit.
        with path.open("xb") as handle:
            handle.write(data)
        pointers[family] = {
            "generation_id": generation_id, "content_sha256": sha256_bytes(data),
            "published_at": now, "run_id": run_id, "package_id": package_id,
            "format": fmt, "stage_id": stage_ids.get(family),
        }
    previous = _json(phase_dir / "current-package.json") if (phase_dir / "current-package.json").exists() else {}
    package = {"package_id": package_id, "previous_package_id": previous.get("package_id"), "run_id": run_id, "phase": phase,
               "branch_id": branch_id, "published_at": now,
               "records": pointers, "metadata": metadata}
    write_json_atomic(phase_dir / "packages" / (package_id + ".json"), package)
    if before_commit:
        before_commit(package)
    check_current()
    write_json_atomic(phase_dir / "current-package.json", package)
    return package
