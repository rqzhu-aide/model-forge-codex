"""Check authored UI mathematics with the same KaTeX engine as the renderer.

These checks assess syntax and JSON escaping, never mathematical correctness.
No authored document is modified and no model call is made.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from .domain import Finding


def _math_strings(value, pointer="", key="", parent_key=""):
    if isinstance(value, dict):
        for child_key, child in value.items():
            escaped = str(child_key).replace("~", "~0").replace("/", "~1")
            yield from _math_strings(child, f"{pointer}/{escaped}", str(child_key), key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _math_strings(child, f"{pointer}/{index}", key, parent_key)
    elif isinstance(value, str) and value.strip():
        raw = key in {"latex", "symbol"}
        if key == "definition" and parent_key in {
                "target_or_estimand", "objective_or_estimating_equation", "constraints_and_normalization"}:
            # The shared JS predicate decides whether this is a bare formula,
            # exactly as the UI does. Do not infer mathematical prose here.
            raw = "named-definition"
        if raw or "$" in value or "\\[" in value or "\\]" in value or "\\(" in value:
            yield pointer, value, raw


def _node_executable():
    executable = shutil.which("node")
    if executable:
        return executable
    # A Windows service can inherit a narrower PATH than the user's terminal.
    for root in (os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if root:
            candidate = Path(root) / "nodejs/node.exe"
            if candidate.is_file():
                return str(candidate)
    raise OSError("Shared Node.js was not found. Make the existing user-wide or machine-wide Node.js installation available to the backend.")


@lru_cache(maxsize=32)
def _check_batch(items):
    app_root = Path(__file__).resolve().parents[2]
    script = app_root / "web/runtime/validate-math.mjs"
    if not script.is_file():
        script = app_root / "web/scripts/validate-math.mjs"
    result = subprocess.run(
        [_node_executable(), str(script)],
        input=json.dumps([{"text": text, "raw": raw} for text, raw in items]),
        text=True, encoding="utf-8", capture_output=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )
    if result.returncode:
        raise OSError("The math checker could not run. Check the backend's shared Node.js installation and application files. "
                      + result.stderr.strip()[-500:])
    reports = json.loads(result.stdout)
    if not isinstance(reports, list) or len(reports) != len(items):
        raise ValueError("The shared KaTeX checker returned an invalid report.")
    return reports


def _primary_markdown_fields(documents: dict, roots: dict[str, Path], findings: list[Finding]):
    """Read only explicitly declared, digest-matched authored primary Markdown."""
    for family, document in documents.items():
        if not isinstance(document, dict):
            continue
        pointers = [(f"/{name}", document.get(name))
                    for name in ("primary_artifact", "manuscript_artifact", "report_artifact")]
        pointers += [(f"/representations/{index}/artifact", representation.get("artifact"))
                     for index, representation in enumerate(document.get("representations") or [])
                     if isinstance(representation, dict)
                     and representation.get("information_layer") == "primary_artifact"]
        checked = set()
        search_roots = list(dict.fromkeys([roots[family], *roots.values()])) if family in roots else list(roots.values())
        search_roots += [child for root in list(search_roots)
                         for child in (Path(root) / "working").glob("*") if child.is_dir()]
        for location, pointer in pointers:
            if not isinstance(pointer, dict):
                continue
            rel, digest = pointer.get("path"), pointer.get("sha256")
            media_type = pointer.get("media_type")
            if not isinstance(rel, str) or not isinstance(digest, str):
                continue
            if not (media_type == "text/markdown" or media_type is None
                    and Path(rel).suffix.lower() in {".md", ".markdown"}):
                continue
            if (rel, digest) in checked:
                continue
            checked.add((rel, digest))
            for root in search_roots:
                root = Path(root).resolve()
                candidate = (root / rel).resolve()
                if not candidate.is_relative_to(root) or not candidate.is_file():
                    continue
                try:
                    content = candidate.read_bytes()
                except OSError as exc:
                    findings.append(Finding("math.primary_source_unreadable",
                        f"Declared primary Markdown {rel!r} could not be read: {exc}", family, location))
                    break
                if hashlib.sha256(content).hexdigest() != digest:
                    continue  # Existing artifact checks own missing/digest findings.
                try:
                    text = content.decode("utf-8")
                except UnicodeError:
                    findings.append(Finding("math.primary_source_unreadable",
                        f"Declared primary Markdown {rel!r} is not readable UTF-8. Correct this owned artifact and its digest.",
                        family, location, details={"artifact_path": rel, "artifact_sha256": digest}))
                    break
                yield family, location, text, False, {"artifact_path": rel, "artifact_sha256": digest}
                break


def validate_authored_math(documents: dict, *, artifact_roots: dict[str, Path] | None = None) -> list[Finding]:
    fields = [(family, pointer, text, raw, {}) for family, document in documents.items()
              for pointer, text, raw in _math_strings(document)]
    findings = []
    if artifact_roots:
        fields.extend(_primary_markdown_fields(documents, artifact_roots, findings))
    if not fields:
        return findings
    try:
        reports = _check_batch(tuple((text, raw) for _, _, text, raw, _ in fields))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return findings + [Finding("math.validation_unavailable", str(exc), fields[0][0], fields[0][1])]
    return findings + [Finding(report["code"],
                    (f"In primary Markdown {source['artifact_path']!r}, equation at character {report['offset'] + 1}: "
                     f"{report['message']} Fix this owned source and call validate_artifacts again." if source else
                     f"Equation at character {report['offset'] + 1}: {report['message']} Fix this field and call validate_artifacts again."),
                    family, pointer, details={**source, "character_offset": report["offset"]} if source else {})
            for (family, pointer, _, _, source), errors in zip(fields, reports) for report in errors]
