"""Bound member-facing draft feedback without changing validation decisions."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from .execution import redact_execution_text


MAX_FEEDBACK_BYTES = 16 * 1024
MAX_REPRESENTATIVE_FINDINGS = 24


def member_validation_feedback(report: dict, *, workspace: Path, report_dir: Path, execution=None) -> dict:
    """Keep small reports intact; archive large ones and return an explicit sample.

    Both directories come from the active execution, never tool arguments. The
    workspace copy is a direct, exclusively created file, outside authored output
    names and their reference fingerprints. Internal callers retain the full report.
    """
    def serialized(value):
        return json.dumps(value, ensure_ascii=False)

    def wire_bytes(value):
        return redact_execution_text(execution, serialized(value)).encode("utf-8")

    if len(wire_bytes(report)) <= MAX_FEEDBACK_BYTES:
        return report

    exact_bytes = serialized(report).encode("utf-8")
    member_bytes = redact_execution_text(execution, exact_bytes.decode("utf-8")).encode("utf-8")
    name = f"validation-report.{uuid4().hex}.json"
    # An unpredictable leaf and exclusive creation do not follow a pre-existing
    # member-controlled file or directory link. No scientific output is rewritten.
    archive = report_dir / name
    member_path = workspace.resolve() / (".model-forge-" + name)
    with archive.open("xb") as stream:
        stream.write(exact_bytes)
    with member_path.open("xb") as stream:
        stream.write(member_bytes)

    findings = report.get("findings", [])
    groups = defaultdict(list)
    for finding in findings:
        groups[(finding.get("code", ""), finding.get("object_id", ""))].append(finding)
    blocking = sum(bool(finding.get("blocks_publication", True)) for finding in findings)
    summary = {
        "total": len(findings), "blocking": blocking, "nonblocking": len(findings) - blocking,
        "returned": 0, "omitted": len(findings),
        "category_count": len(groups), "categories_returned": 0, "categories_omitted": len(groups),
        "categories": [],
    }
    result = {
        "status": report["status"], "findings": [], "findings_truncated": True,
        "finding_summary": summary,
        "full_report": {"path": str(member_path), "sha256": hashlib.sha256(member_bytes).hexdigest(),
                        "bytes": len(member_bytes), "credentials_redacted": member_bytes != exact_bytes},
        "feedback_note": "Findings below are only a bounded sample, not the complete list. "
                         "Totals cover all findings. Category counts say explicitly if categories were omitted. "
                         "Read or filter the full report through normal protected file access; do not print it in full.",
    }
    # Preserve the recovery signal used by the bridge, including stop_requested.
    if "recovery" in report:
        result["recovery"] = report["recovery"]
    if len(wire_bytes(result)) > MAX_FEEDBACK_BYTES:
        raise ValueError("Validation feedback metadata exceeds its response limit; the full report was retained.")

    omitted_fields = []
    for key, value in report.items():
        if key in {"status", "findings", "recovery"}:
            continue
        result[key] = value
        # Reserve space for category counts and samples, even if other metadata
        # itself is unexpectedly large.
        if len(wire_bytes(result)) > MAX_FEEDBACK_BYTES // 2:
            del result[key]
            omitted_fields.append(key)
    if omitted_fields:
        result["omitted_report_fields"] = omitted_fields

    ordered_groups = sorted(groups.items())
    for (code, object_id), members in ordered_groups:
        category = {"code": code, "object_id": object_id, "count": len(members),
                    "blocking": sum(bool(item.get("blocks_publication", True)) for item in members)}
        summary["categories"].append(category)
        summary["categories_returned"] += 1
        summary["categories_omitted"] -= 1
        if len(wire_bytes(result)) > MAX_FEEDBACK_BYTES * 3 // 4:
            summary["categories"].pop()
            summary["categories_returned"] -= 1
            summary["categories_omitted"] += 1

    # First try one exact representative from every category. A single enormous
    # finding is omitted rather than silently editing its message or pointer.
    candidates = [members[0] for _, members in ordered_groups]
    candidates.extend(item for _, members in ordered_groups for item in members[1:])
    for finding in candidates:
        if summary["returned"] >= MAX_REPRESENTATIVE_FINDINGS:
            break
        result["findings"].append(finding)
        summary["returned"] += 1
        summary["omitted"] -= 1
        if len(wire_bytes(result)) > MAX_FEEDBACK_BYTES:
            result["findings"].pop()
            summary["returned"] -= 1
            summary["omitted"] += 1
    if len(wire_bytes(result)) > MAX_FEEDBACK_BYTES:
        raise ValueError("Validation feedback exceeds its response limit; the full report was retained.")
    return result
