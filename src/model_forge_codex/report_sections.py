"""Exact report-section discussions and researcher comments, separate from science."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from .phase_interactions import digest
from .report_boundaries import reference_boundary, report_anchor_headings
from .records import ArtifactError, committed_packages, read_generation, source_artifact_path
from .storage import read_json, write_json_atomic
from .technical_reports import CONTENT_SECTIONS, resolve_report_source

_IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_ID = re.compile(r"(?<![\w:.-])id\s*=\s*([\"'])(.*?)\1", re.I)
_ANCHOR_LINE = re.compile(r"\s*<a\s+[^>]*>\s*</a>\s*", re.I)
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_TARGET_FIELDS = ("kind", "branch", "phase", "family", "generation_id", "sha256", "run_id", "package_id", "object_id")


def section_target(target):
    """Normalize display extras without accepting a weaker source identity."""
    if not isinstance(target, dict):
        raise ValueError("Select an exact technical report section")
    result = {key: target.get(key) for key in _TARGET_FIELDS}
    if (result["kind"] != "report_section" or result["phase"] != "P5"
            or result["family"] != "technical_report" or result["object_id"] not in CONTENT_SECTIONS
            or not all(isinstance(result[key], str) and _IDENT.fullmatch(result[key])
                       for key in ("branch", "generation_id", "run_id", "package_id"))
            or not isinstance(result["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", result["sha256"])):
        raise ValueError("Select an exact published technical report section")
    return result


def _section(markdown, anchors, key):
    """Use explicit authored anchors beside headings, never guessed prose."""
    if not isinstance(anchors, dict) or not isinstance(anchors.get(key), str) or not anchors[key]:
        raise ValueError("This report section has no authored anchor")
    boundary = reference_boundary(markdown, anchors, CONTENT_SECTIONS)
    if boundary is not None:
        # Explicit retained metadata selects the reader format independently of
        # the current catalog. Historical reports without it use the old path.
        found = report_anchor_headings(markdown, {name: anchors.get(name) for name in CONTENT_SECTIONS})
        if key not in found:
            raise ValueError("This report section is unavailable in its exact source")
        lines = markdown.splitlines(keepends=True)
        start = found[key]["start_line"]
        end = min([boundary["start_line"], *[row["start_line"] for row in found.values() if row["start_line"] > start]])
        return "".join(lines[start:end]).strip(), re.sub(r"<[^>]+>", "", found[key]["label"]).strip(), anchors[key]
    declared = {name: value for name, value in anchors.items() if name in CONTENT_SECTIONS and isinstance(value, str) and value}
    if len(set(declared.values())) != len(declared):
        raise ValueError("The report section anchors are ambiguous")
    lines = markdown.splitlines(keepends=True)
    clean, fence, math = [], None, None
    for line in lines:
        stripped = line.strip()
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not line[marker.end():].strip():
                fence = None
            clean.append("")
        elif marker:
            fence = marker[1]
            clean.append("")
        elif math:
            if stripped == math:
                math = None
            clean.append("")
        elif stripped in ("$$", r"\["):
            math = "$$" if stripped == "$$" else r"\]"
            clean.append("")
        elif line.startswith(("    ", "\t")) or re.match(r"^\s*(>|[-+*]\s|\d+[.)]\s)", line):
            clean.append("")
        else:
            clean.append(line.rstrip())
    headings = {index: _HEADING.match(line) for index, line in enumerate(clean) if _HEADING.match(line)}
    found = {}
    for name, anchor in declared.items():
        positions = [index for index, line in enumerate(clean)
                     for match in _ID.finditer(line) if html.unescape(match[2]) == anchor]
        if len(positions) != 1:
            if name == key or positions:
                raise ValueError("The report section anchor is missing or ambiguous")
            continue
        index = positions[0]
        heading = index if index in headings else None
        if heading is None and _ANCHOR_LINE.fullmatch(clean[index]):
            before, after = index - 1, index + 1
            while before >= 0 and not lines[before].strip():
                before -= 1
            while after < len(lines) and not lines[after].strip():
                after += 1
            # The standard authored form is an anchor immediately before its
            # heading, including when the document title precedes it.
            heading = after if after in headings else before if before in headings else None
        if heading is None:
            raise ValueError("The report section anchor does not identify one main heading")
        found[name] = (min(index, heading), heading)
    if key not in found:
        raise ValueError("This report section is unavailable in its exact source")
    if len({row[1] for row in found.values()}) != len(found):
        raise ValueError("The report section headings are ambiguous")
    start, heading = found[key]
    end = min((row[0] for row in found.values() if row[0] > start), default=len(lines))
    text = "".join(lines[start:end]).strip()
    label = re.sub(r"<[^>]+>", "", headings[heading][2]).strip()
    return text, label, anchors[key]


def resolve_report_section(project_dir, target):
    """Read one committed report generation and its retained Markdown bytes."""
    target = section_target(target)
    phase_dir = project_dir / "branches" / target["branch"] / "phases" / "p5"
    matches = [package["records"]["technical_report"] for package in committed_packages(phase_dir)
               if "technical_report" in package["records"]
               and all(package["records"]["technical_report"].get(key) == target[field]
                       for key, field in (("generation_id", "generation_id"), ("content_sha256", "sha256"),
                                          ("run_id", "run_id"), ("package_id", "package_id")))]
    if len(matches) != 1:
        raise ValueError("The report section source does not match one committed publication")
    pointer = matches[0]
    document = read_generation(phase_dir, "technical_report", pointer)
    if not isinstance(document, dict):
        raise ValueError("The retained technical report is unavailable")
    if target["object_id"] not in document.get("sections_present", []):
        raise ValueError("This section is not present in the retained technical report")
    source = source_artifact_path(project_dir, pointer, document.get("report_artifact") or {})
    if source.suffix.lower() != ".md":
        raise ValueError("This report has no retained Markdown source")
    text, title, anchor = _section(source.read_text(encoding="utf-8"), document.get("section_anchors"), target["object_id"])
    from .research import record_url
    ref = {key: target[key] for key in ("branch", "phase", "family", "generation_id", "sha256", "run_id", "package_id")}
    ids = {html.unescape(match[2]) for match in _ID.finditer(text)}
    claims = [row for row in document.get("claims", []) if isinstance(row, dict) and row.get("anchor") in ids]
    values = [row for row in document.get("prose_values", []) if isinstance(row, dict) and row.get("anchor") in ids]
    numerical = document.get("numerical_analysis", []) if target["object_id"] in ("numerical_analysis", "reproducibility") else []
    references = []
    for row in [*claims, *values, *numerical]:
        for name in ("source_refs", "evidence_refs", "exhibit_refs", "implementation_refs"):
            references.extend(row.get(name, []))
        if (row.get("theorist_check") or {}).get("check_ref"):
            references.append(row["theorist_check"]["check_ref"])
    return {"issue_id": "report.section." + digest(target)[:32], "title": title,
            "summary_markdown": text, "section_anchor": anchor, "report_title": document.get("title", "Technical report"),
            "branch": target["branch"], "phase": "P5", "kind": "report_section", "responsible_role": "research_lead",
            "generation_ref": ref, "source_url": record_url(project_dir.name, ref), "explanation_target": target,
            "claims": claims, "prose_values": values, "numerical_analysis": numerical, "supporting_source_refs": references}


def section_source_records(issue, basis):
    """Keep exact cited support and the section's phase context, without other reports."""
    families = {"existing_approaches": {"literature_synthesis", "literature_library", "research_basis"},
                "justification": {"theory_record", "complete_theory"}}.get(issue["explanation_target"]["object_id"], set())
    fields = ("branch", "phase", "family", "generation_id", "content_sha256")
    selected = []
    errors = []
    for reference in issue["supporting_source_refs"]:
        try:
            resolve_report_source(reference, basis)
        except (ArtifactError, OSError, ValueError) as exc:
            errors.append(str(exc))
    issue["unavailable_support"] = sorted(set(errors))
    for ref in basis.get("records", []):
        if ref.get("family") in families or any(all(ref.get(key) == reference.get(key) for key in fields)
                                                for reference in issue["supporting_source_refs"]):
            selected.append(ref)
    return selected


def _comment_path(project_dir, target):
    return project_dir / "researcher" / "report_section_comments" / (digest(target) + ".json")


def load_section_comment(project_dir, target, *, verify_source=True):
    target = section_target(target)
    if verify_source:
        resolve_report_section(project_dir, target)
    saved = read_json(_comment_path(project_dir, target))
    if not saved:
        return None
    if saved.get("target") != target:
        raise ValueError("The saved comment does not match this report section")
    return {key: saved.get(key) for key in ("target", "note", "revision", "updated_at")}


def save_section_comment(project_dir, target, note, expected_revision):
    target = section_target(target)
    resolve_report_section(project_dir, target)
    if not isinstance(note, str):
        raise ValueError("Your report comment must be text")
    path = _comment_path(project_dir, target)
    previous = read_json(path) or {}
    if expected_revision != previous.get("revision", 0):
        raise ValueError("Your saved comment changed; reload it before saving this edit")
    if previous.get("note") == note:
        return load_section_comment(project_dir, target, verify_source=False)
    saved = {"target": target, "note": note, "revision": previous.get("revision", 0) + 1,
             "updated_at": datetime.now(timezone.utc).isoformat(),
             "history": [*previous.get("history", []), *([{key: value for key, value in previous.items() if key != "history"}] if previous else [])]}
    write_json_atomic(path, saved)
    return load_section_comment(project_dir, target, verify_source=False)
