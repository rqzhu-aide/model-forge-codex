"""Display links for authored question evidence, pinned to its original inputs."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .records import ArtifactError, _segment, committed_packages, read_generation
from .storage import read_json, sha256_bytes


def _entry(document, pointer):
    from .technical_reports import _pointer
    # Array positions in an authored locator must be nonnegative JSON indices.
    if not isinstance(pointer, str) or re.search(r"/(?:-\d+|\d+\.\d+)(?:/|$)", pointer):
        raise ArtifactError("Invalid scientific source pointer")
    return _pointer(document, pointer)


def _published(project_dir, reference):
    from .research import source_ref
    phase_dir = project_dir / "branches" / _segment(reference["branch"]) / "phases" / _segment(reference["phase"]).lower()
    matches = []
    for package in committed_packages(phase_dir):
        pointer = package.get("records", {}).get(reference["family"])
        if pointer and all(source_ref(reference["branch"], reference["phase"], reference["family"], pointer).get(key)
                           == reference.get(key) for key in ("generation_id", "sha256", "run_id", "package_id")):
            matches.append((pointer, package))
    if not matches:
        raise ArtifactError("The question source is not a committed generation")
    # A later package may retain this exact pointer alongside newer siblings.
    # Evidence belongs to the producing envelope, never its newest retention.
    if reference.get("package_id"):
        owners = [(pointer, package) for pointer, package in matches
                  if package.get("package_id") == reference["package_id"]
                  and package.get("run_id") == reference.get("run_id")]
    else:
        owners = [(pointer, package) for pointer, package in matches
                  if reference.get("run_id") and package.get("run_id") == reference["run_id"]]
        if not owners:
            owners = [(pointer, package) for pointer, package in matches if package.get("legacy")]
    if len(owners) != 1:
        raise ArtifactError("The question's producing publication is unavailable or ambiguous")
    pointer, package = owners[0]
    return read_generation(phase_dir, reference["family"], pointer), package


def attention_source_references(project_dir: Path, item: dict) -> list[dict]:
    """Resolve authored output pointers and frozen prior questions without current-slot lookup."""
    from .research import source_ref
    from .technical_reports import resolve_report_source

    origin = item.get("generation_ref") or item.get("explanation_target") or {}
    if not item.get("source_refs") or not origin.get("run_id"):
        return []
    try:
        _, package = _published(project_dir, origin)
        run_dir = project_dir / "runs" / _segment(origin["run_id"])
        basis = read_json(run_dir / "basis.json") or {}
    except (ArtifactError, OSError, ValueError, KeyError, TypeError):
        return []
    result = []
    seen = set()
    for authored in item.get("source_refs", []):
        if not isinstance(authored, dict):
            continue
        try:
            pointer = authored.get("pointer", "")
            output = re.fullmatch(r"(p[1-5])\.([A-Za-z0-9._-]+)", authored.get("output_id") or "")
            if output:
                phase, family = output[1].upper(), output[2]
                candidates = [(key, value) for key, value in package.get("records", {}).items()
                              if key == family or key == authored["output_id"]]
                candidates = [(key, value) for key, value in candidates if phase == origin["phase"]
                              and (value.get("run_id") or value.get("source_run_id")) == origin["run_id"]]
                if len(candidates) == 1:
                    family, saved = candidates[0]
                    reference = source_ref(origin["branch"], phase, family, saved)
                    document, _ = _published(project_dir, reference)
                else:
                    if phase == origin["phase"]:
                        continue
                    frozen = [row for row in basis.get("records", []) if row.get("phase") == phase
                              and row.get("family") in (family, authored["output_id"])]
                    if len(frozen) != 1:
                        continue
                    saved = frozen[0]
                    snapshot = Path(saved.get("snapshot_path") or "").resolve()
                    if not snapshot.is_relative_to((run_dir / "inputs").resolve()):
                        continue
                    _, _, document = resolve_report_source(saved, basis)
                    reference = source_ref(saved["branch"], phase, saved["family"], saved)
                    _published(project_dir, reference)
                entry = _entry(document, pointer)
                reference = {**reference, "entry_pointer": pointer}
            elif authored.get("path") == "inputs/cumulative/open_attention.json":
                saved = basis.get("cumulative_inputs", {}).get("open_attention") or {}
                snapshot = run_dir / "inputs/cumulative/open_attention.json"
                if Path(saved.get("snapshot_path") or "").resolve() != snapshot.resolve():
                    continue
                document = read_json(snapshot)
                digest = sha256_bytes(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
                if digest != saved.get("sha256"):
                    continue
                entry = _entry(document, pointer)
                reference = entry.get("generation_ref") if isinstance(entry, dict) else None
                if not reference:
                    continue
                original, _ = _published(project_dir, reference)
                original = _entry(original, reference.get("entry_pointer", ""))
                if not isinstance(original, dict) or original.get("attention_id") != entry.get("attention_id"):
                    continue
            else:
                continue
            key = json.dumps(reference, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            label = (entry.get("title") or entry.get("question")) if isinstance(entry, dict) else None
            if not label:
                label = {"analyst_synthesis": "Analyst finding", "theory_audit": "Theory finding",
                         "attention_items": "Earlier question"}.get(reference.get("family"), "Scientific evidence")
                label += f" {len(result) + 1}"
            result.append({"label": label, "reference": reference})
        except (ArtifactError, OSError, ValueError, KeyError, TypeError):
            # A missing source stays missing. Never redirect to a later publication.
            continue
    return result
