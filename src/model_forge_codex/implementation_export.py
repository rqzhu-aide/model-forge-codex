"""Download the exact declared model/example sources, never a whole run tree."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import PurePosixPath

from .records import ArtifactError, source_artifact_path
from .storage import read_json


def reproduction_files(document):
    reproduction = document.get("reproduction") or {}
    if reproduction.get("status") != "available":
        raise ArtifactError("This evaluation has no verified portable implementation account")
    entries = [reproduction.get(key) for key in ("model_entrypoint", "example_generator", "example_runner", "readme")]
    if any(not isinstance(entry, dict) or not isinstance(entry.get("artifact"), dict) for entry in entries):
        raise ArtifactError("The model, generator, example runner and README must all be retained")
    entries.extend(reproduction.get("support_files") or [])
    return [entry for entry in entries if isinstance(entry, dict) and isinstance(entry.get("artifact"), dict)]


def verified_implementation_files(project_dir, record, document):
    entries = reproduction_files(document)
    if not entries:
        raise ArtifactError("No retained implementation files were declared")
    basis = read_json(project_dir / "runs" / record["run_id"] / "basis.json") or {}
    private_hashes = {item.get("sha256") for item in basis.get("p4_inputs", {}).get("inputs", []) if item.get("role") == "dataset"}
    files = {}
    manifest = []
    total_bytes = 0
    for entry in entries:
        pointer = entry["artifact"]
        path = PurePosixPath(str(pointer.get("path", "")).replace("\\", "/"))
        if not path.parts or path.is_absolute() or ".." in path.parts or ":" in str(path) or str(path) == "model-forge-export.json":
            raise ArtifactError("Portable sources require safe relative paths")
        if pointer.get("sha256") in private_hashes:
            raise ArtifactError("Researcher datasets cannot be included in the default code export")
        try:
            source = source_artifact_path(project_dir, record, pointer)
        except ArtifactError:
            from .research_sources import frozen_artifact
            matches = [item for item in basis.get("artifacts", []) if isinstance(item, dict)
                       and item.get("content_sha256") == pointer.get("sha256")
                       and (item.get("artifact_id") == pointer.get("artifact_id") and pointer.get("artifact_id")
                            or item.get("original_path") == pointer.get("path") and pointer.get("path"))]
            if not matches:
                raise
            source = frozen_artifact(project_dir, record["run_id"], pointer["sha256"], matches[0].get("artifact_id") or "")
        if str(path) in files:
            if files[str(path)] != source:
                raise ArtifactError("Conflicting files have the same portable path")
            continue
        files[str(path)] = source
        total_bytes += source.stat().st_size
        if total_bytes > 128 * 1024 * 1024:
            raise ArtifactError("The declared source bundle exceeds 128 MiB; inspect individual sources")
        manifest.append({"path": str(path), "sha256": pointer.get("sha256"), "kind": entry.get("kind")})
    return files, manifest


def export_implementation(project_dir, record, document):
    files, manifest = verified_implementation_files(project_dir, record, document)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, source in files.items():
            archive.writestr(name, source.read_bytes())
        archive.writestr("model-forge-export.json", json.dumps({"method_identity": document.get("method_identity"),
            "generation_id": record.get("generation_id"), "reproduction": document["reproduction"], "files": manifest}, indent=2))
    return output.getvalue()
