"""Read publication status without rewriting authored P5 records or their history."""
from __future__ import annotations

from pathlib import Path
from copy import deepcopy

from .records import ArtifactError, committed_packages, current_records, read_generation
from .storage import read_json


REPORT_FAMILIES = {"technical_report", "technical_report_candidate"}
COMPANION_FAMILIES = {"decision", "phase_decision", "assembly_report", "citation_integrity_report"}
CORRECTED_DELIVERY_NOTE = (
    "The earlier portable-rendering check passed after correction. Requests to repair that check describe "
    "the earlier attempt. Scientific concerns, independent review requirements and proposed scientific work remain as recorded."
)


def _matches(pointer: dict, reference: dict) -> bool:
    digest = reference.get("sha256") or reference.get("content_sha256")
    return bool(reference.get("generation_id") and digest
                and pointer.get("generation_id") == reference["generation_id"]
                and pointer.get("content_sha256") == digest)


def report_delivery_state(project_dir: Path, reference: dict) -> dict | None:
    """Bind delivery to the report committed with this exact generation.

    A later branch publication, an uncommitted package, or a different report
    from the same branch cannot clear this record's failure. No export or model
    call is repeated when reading status, and publication says nothing about
    scientific completion or independent review.
    """
    family, branch, run_id = (reference.get(key) for key in ("family", "branch", "run_id"))
    if reference.get("phase") != "P5" or family not in REPORT_FAMILIES | COMPANION_FAMILIES or not branch or not run_id:
        return None
    phase_dir = project_dir / "branches" / branch / "phases" / "p5"
    try:
        for package in committed_packages(phase_dir):
            if package.get("run_id") != run_id:
                continue
            if reference.get("package_id") and package.get("package_id") != reference["package_id"]:
                continue
            pointer = package.get("records", {}).get(family) or {}
            if not _matches(pointer, reference):
                continue
            report_pointer = package["records"].get("technical_report") or {}
            if (report_pointer.get("run_id") != run_id
                    or report_pointer.get("package_id") != package.get("package_id")):
                continue
            # Verify the record and report identities, rather than trusting
            # authored delivery prose or merely finding a run named published.
            read_generation(phase_dir, family, pointer)
            read_generation(phase_dir, "technical_report", report_pointer)
            run = read_json(project_dir / "runs" / run_id / "run.json") or {}
            if (run.get("run_id") != run_id or run.get("branch_id") != branch
                    or run.get("phase") != "P5" or run.get("state") != "published"):
                return None
            latest = (run.get("findings_history") or [[]])[-1]
            if any(item.get("blocks_publication", True) for item in latest):
                return None
            current = current_records(phase_dir).get("technical_report") or {}
            corrected = bool(run.get("correction_attempts"))
            passed_issues = []
            portable_passed = False
            integrity = package["records"].get("citation_integrity_report") or {}
            prior_portable_failure = any(item.get("code") == "report.portable_unresolved"
                                         and item.get("blocks_publication", True)
                                         for findings in (run.get("findings_history") or [])[:-1] for item in findings)
            if corrected and prior_portable_failure and integrity.get("run_id") == run_id:
                authored = read_generation(phase_dir, "citation_integrity_report", integrity)
                check = authored.get("portable_export_check") or {}
                if (check.get("code") == "report.portable_unresolved" and check.get("status") == "failed"
                        and check.get("blocks_publication") is True):
                    portable_passed = True
                    passed_issues = [item["issue_id"] for item in authored.get("issues", [])
                                if isinstance(item, dict) and item.get("issue_id") and
                                (item.get("code") == check["code"]
                                 or item["issue_id"] == "issue.report.portable-source-link")]
            return {
                "publication": "published", "validation": "passed",
                "message": "The report passed publication checks and was published.",
                "corrected": corrected,
                "portable_export_check": "passed" if portable_passed else "not_recorded",
                "passed_delivery_issue_ids": passed_issues,
                "authored_delivery_note": CORRECTED_DELIVERY_NOTE if portable_passed else None,
                "is_current_report": _matches(current, report_pointer),
                "report_ref": {"branch": branch, "phase": "P5", "family": "technical_report",
                               "generation_id": report_pointer["generation_id"],
                               "sha256": report_pointer["content_sha256"], "run_id": run_id,
                               "package_id": package["package_id"]},
                "published_at": package.get("published_at"),
            }
    except (ArtifactError, OSError, ValueError, TypeError):
        return None
    return None


def delivery_display(document: dict, state: dict) -> tuple[dict, list]:
    """Project the export check separately, preserving entire authored issues.

    The one legacy issue identity is admitted only with its structured failed
    export check and a recorded engine failure followed by successful correction
    in the same publication. Neither the whole issue nor any scientific part is
    automatically resolved, including when one entry mixes both concerns.
    """
    result, history = deepcopy(document), []
    passed = set(state.get("passed_delivery_issue_ids") or [])
    for field in ("issues", "unresolved_issues"):
        if isinstance(result.get(field), list):
            # Retain the entire earlier account, including mixed scientific
            # content, under a clearly scoped check heading in the reader.
            history.extend(item for item in result[field] if isinstance(item, dict) and item.get("issue_id") in passed)
            result[field] = [item for item in result[field] if not isinstance(item, dict) or item.get("issue_id") not in passed]
    if history and state.get("portable_export_check") == "passed" and "required_checks" in result:
        result["recorded_checks"] = result.pop("required_checks")
    if "delivery_status" in result:
        result["delivery_status"] = state["message"]
    if state.get("portable_export_check") == "passed" and "portable_export_check" in result:
        result["portable_export_check"] = {"status": "passed", "blocks_publication": False,
                                            "message": state["message"], "basis": "publication_checks"}
    return result, history


def project_run_terminal_reason(document: dict) -> dict:
    """Old successful runs may retain a failed attempt's diagnostic on disk."""
    history = document.get("findings_history") or []
    reason = document.get("terminal_reason")
    if reason in {"publication_recovered_after_restart", "assessment_recovered_after_restart"}:
        return document
    stale_failure = any(item.get("blocks_publication", True) and item.get("message") == reason
                        for findings in history[:-1] for item in findings)
    if (document.get("phase") == "P5" and document.get("state") == "published"
            and document.get("correction_attempts") and reason and stale_failure
            and history and not any(item.get("blocks_publication", True) for item in history[-1])):
        return {**document, "terminal_reason": None, "recorded_terminal_reason": document["terminal_reason"]}
    return document
