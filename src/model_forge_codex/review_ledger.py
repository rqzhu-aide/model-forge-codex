"""A cumulative index of authored review issues, not a manuscript verdict."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .records import ArtifactError, committed_packages, read_generation


def _issues(document) -> list[dict]:
    if document is None:
        return []
    entries = document if isinstance(document, list) else document.get("issues", []) if isinstance(document, dict) else None
    if not isinstance(entries, list) or any(not isinstance(item, dict) or not item.get("issue_id") for item in entries):
        raise ArtifactError("The manuscript review issue collection is malformed")
    identifiers = [item["issue_id"] for item in entries]
    if len(identifiers) != len(set(identifiers)):
        raise ArtifactError("A manuscript review update contains duplicate issue identifiers")
    return entries


def build_review_ledger(previous_ledger: dict | list | None, new_issues: list | None, run_id: str) -> dict:
    """Keep each issue's latest explicit disposition and exact review basis.

    Empty updates retain open, fixed, deferred, and rejected issues alike.
    Historical review findings are never reclassified by a later assembly.
    """
    previous = {item["issue_id"]: deepcopy(item) for item in _issues(previous_ledger)}
    sources = deepcopy(previous_ledger.get("issue_sources", {})) if isinstance(previous_ledger, dict) else {}
    for item in _issues(new_issues):
        identifier = item["issue_id"]
        old = previous.get(identifier)
        if (old and old.get("issue_version_id") and old.get("issue_version_id") == item.get("issue_version_id")
                and old != item):
            raise ArtifactError("A changed review issue must have a new immutable issue version")
        if old == item:
            continue
        previous[identifier] = deepcopy(item)
        sources[identifier] = {"run_id": run_id, "family": "review_issues"}
    return {"record_type": "review_issue_ledger", "issues": [previous[key] for key in sorted(previous)],
            "issue_sources": {key: sources[key] for key in sorted(previous) if key in sources}}


def load_review_ledger(phase_dir: Path) -> dict:
    """Recover prior issues from committed reviews, including pre-index runs."""
    ledger = build_review_ledger(None, [], "")
    for package in reversed(list(committed_packages(phase_dir))):
        records = package["records"]
        # A committed index retains issues across assembly-only packages.
        if "review_issue_ledger" in records:
            pointer = records["review_issue_ledger"]
            document = read_generation(phase_dir, "review_issue_ledger", pointer)
            ledger = build_review_ledger(ledger, _issues(document), pointer.get("run_id", ""))
            if isinstance(document, dict):
                ledger["issue_sources"].update(deepcopy(document.get("issue_sources", {})))
        for family, pointer in records.items():
            if family.split(".", 1)[-1] != "review_issues":
                continue
            issues = _issues(read_generation(phase_dir, family, pointer))
            ledger = build_review_ledger(ledger, issues, pointer.get("run_id", ""))
            reference = {"branch": phase_dir.parent.parent.name, "phase": "P5", "family": family,
                         "generation_id": pointer.get("generation_id"),
                         "sha256": pointer.get("content_sha256") or pointer.get("sha256"),
                         "run_id": pointer.get("run_id") or pointer.get("source_run_id"),
                         "package_id": pointer.get("package_id")}
            for item in issues:
                ledger["issue_sources"][item["issue_id"]] = dict(reference)
    return ledger
