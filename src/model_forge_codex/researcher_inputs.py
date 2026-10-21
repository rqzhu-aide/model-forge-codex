"""Explicit local researcher inputs, kept separate from published source files."""
from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .storage import read_json, write_json_atomic, sha256_bytes, sha256_file

MAX_INPUT_BYTES = 64 * 1024 * 1024
_ID = re.compile(r"input\.[a-f0-9]{32}\Z")
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z", re.I)


def _root(project_dir):
    project_dir = Path(project_dir)
    if not (project_dir / "project.json").is_file():
        raise ValueError("Unknown project")
    return project_dir / "researcher" / "inputs"


def _metadata(project_dir, input_id):
    if not isinstance(input_id, str) or not _ID.fullmatch(input_id):
        raise ValueError("Invalid researcher input ID")
    root = _root(project_dir)
    metadata = read_json(root / input_id / "input.json")
    if not metadata or metadata.get("input_id") != input_id:
        raise ValueError("The selected researcher input is unavailable")
    return metadata


def import_input(project_dir, *, filename, role, content_base64, description="", mapping=None):
    root = _root(project_dir)
    if (not isinstance(filename, str) or not filename or len(filename) > 160
            or filename != filename.strip() or filename.endswith((".", " "))
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', filename) or _RESERVED.fullmatch(filename)
            or filename in (".", "..")):
        raise ValueError("Use a plain filename without folders or reserved characters")
    if role not in {"dataset", "code", "configuration"}:
        raise ValueError("Input role must be dataset, code or configuration")
    if not isinstance(mapping or {}, dict):
        raise ValueError("Input mapping must be an object")
    if not isinstance(content_base64, str) or len(content_base64) > ((MAX_INPUT_BYTES + 2) // 3) * 4:
        raise ValueError("Each local input must be at most 64 MiB")
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Input content is not valid base64") from exc
    if not content or len(content) > MAX_INPUT_BYTES:
        raise ValueError("Select a nonempty local file of at most 64 MiB")
    input_id = "input." + uuid4().hex
    destination = root / input_id
    destination.mkdir(parents=True)
    (destination / "content").mkdir()
    (destination / "content" / filename).write_bytes(content)
    metadata = {"input_id": input_id, "filename": filename, "role": role,
                "description": description, "mapping": mapping or {},
                "size_bytes": len(content), "sha256": sha256_bytes(content),
                "created_at": datetime.now(timezone.utc).isoformat()}
    write_json_atomic(destination / "input.json", metadata)
    return metadata


def list_inputs(project_dir):
    return sorted((read_json(path) for path in _root(project_dir).glob("input.*/input.json")),
                  key=lambda row: row.get("created_at", ""), reverse=True)


def selected_inputs(project_dir, input_ids):
    if not isinstance(input_ids, list) or len(input_ids) > 32 or any(not isinstance(v, str) for v in input_ids):
        raise ValueError("Select at most 32 researcher inputs")
    if len(set(input_ids)) != len(input_ids):
        raise ValueError("Select each researcher input once")
    rows = [_metadata(project_dir, value) for value in input_ids]
    for row in rows:
        source = _root(project_dir) / row["input_id"] / "content" / row["filename"]
        if not source.is_file() or source.is_symlink() or sha256_file(source) != row["sha256"]:
            raise ValueError("A selected input changed or disappeared; import the intended file again")
    return rows


def freeze_inputs(project_dir, run_dir, input_ids):
    frozen = []
    for row in selected_inputs(project_dir, input_ids):
        source = _root(project_dir) / row["input_id"] / "content" / row["filename"]
        content = source.read_bytes()
        if sha256_bytes(content) != row["sha256"]:
            raise ValueError("A selected input changed while preparing the run")
        destination = Path(run_dir) / "inputs" / "researcher" / row["input_id"] / row["filename"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        frozen.append({**row, "snapshot_path": str(destination.resolve())})
    manifest = {"inputs": frozen, "variable_mapping": {}}
    write_json_atomic(Path(run_dir) / "inputs" / "researcher-inputs.json", manifest)
    return manifest


def input_brief(manifest):
    """Metadata only. Data bytes and private absolute filenames never enter prose."""
    import json
    rows = [{key: row[key] for key in ("input_id", "filename", "role", "description", "mapping", "size_bytes", "sha256")
             if key in row} for row in (manifest or {}).get("inputs", [])]
    return ("## Selected local researcher inputs\n\n" + json.dumps(rows, ensure_ascii=False, indent=2)
            + "\n\nThese are local frozen inputs. Read dataset rows only in the managed numerical script, "
              "through MODEL_FORGE_P4_INPUTS_PATH; do not open raw patient records in member tools or include them "
              "in prompts, logs, published sources or portable examples. Return approved aggregate analysis only. "
              "Use input_ids in protocol data_sources. Code/configuration inputs may be incorporated into "
              "declared source files with their provenance. No selected dataset means actual_data_application "
              "is not_supplied; do not invent actual data.\n\n")


def retain_support_files(workspace, destination, owned_names, manifest):
    """Copy scientific support while excluding raw selected data and symlinks."""
    private = {row["sha256"] for row in (manifest or {}).get("inputs", []) if row.get("role") == "dataset"}
    private_sizes = {row["size_bytes"] for row in (manifest or {}).get("inputs", []) if row.get("role") == "dataset"}
    excluded = []
    for source in Path(workspace).rglob("*"):
        relative = source.relative_to(workspace)
        if relative.parts[0] in owned_names or any(part in {"_researcher_inputs", "raw-inputs"} for part in relative.parts):
            continue
        if source.is_symlink() or not source.is_file():
            continue
        if source.stat().st_size in private_sizes and sha256_file(source) in private:
            excluded.append(str(relative))
            continue
        target = Path(destination) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return excluded
