"""Resolve each catalog method's producing P2 material as verifiable references.

The method catalog's method_sources index names the run, stage and record
family that produced each definition. This module turns that index into the
exact original material — the full proposal generation, the review
generations naming the proposal, and the catalog assessment carrying its
modification options — read back from the producing run's P2 package and
verified against the published digests. Material that cannot be resolved is
labeled unavailable; nothing is reconstructed or inferred.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from .records import ArtifactError, current_records, read_generation
from .storage import read_json, sha256_bytes


def current_method_catalog(project_dir: Path) -> dict:
    """The current complete catalog generation or an honest rebuilt view.

    The rebuilt view keeps every method's recorded producing reference instead
    of presenting a bare method list as a fresh catalog.
    """
    from .methods import _catalog_methods

    store = project_dir / "branches" / "trunk" / "phases" / "p2"
    records = current_records(store)
    if "method_catalog" in records:
        return read_generation(store, "method_catalog", records["method_catalog"])
    entries = sorted(_catalog_methods(project_dir).items())
    return {
        "schema_version": "1.0.0", "record_type": "method_catalog", "phase": "P2", "derived": True,
        "methods": [entry["definition"] for _, entry in entries],
        "method_sources": {
            stable_id: {
                "run_id": entry["source_ref"].get("run_id") or None,
                "stage_id": None,
                "family": entry["source_ref"]["family"],
                "generation_id": entry["source_ref"].get("generation_id"),
                "identity": deepcopy(entry["identity"]),
                **({"origin_unavailable": True} if not entry["source_ref"].get("run_id") else {}),
            }
            for stable_id, entry in entries
        },
        "derived_from": sorted({entry["source_ref"]["family"] for _, entry in entries}),
    }


def _producing_package(project_dir: Path, run_id: str) -> dict | None:
    """Find the P2 package a run published, preferring the committed one."""
    from .records import package_committed

    store = project_dir / "branches" / "trunk" / "phases" / "p2"
    packages_dir = store / "packages"
    if not packages_dir.is_dir():
        return None
    matches = []
    for path in sorted(packages_dir.glob("*.json")):
        package = read_json(path)
        if isinstance(package, dict) and package.get("run_id") == run_id:
            matches.append(package)
    if not matches:
        return None
    try:
        committed = [package for package in matches if package_committed(store, str(package.get("package_id", "")))]
    except ArtifactError:
        committed = []
    return committed[0] if committed else matches[0]


def resolve_method_provenance(project_dir: Path, catalog_document: dict, stable_ids) -> dict:
    """Verifiable origin material for each requested method definition.

    Returns one entry per stable_id: the recorded origin plus the exact
    producing generations (full documents with their publication references
    and content digests), or explicit notes naming what is unavailable.
    """
    from .direct_artifacts import PROPOSAL_ROLES, REVIEW_ROLES

    store = project_dir / "branches" / "trunk" / "phases" / "p2"
    sources = catalog_document.get("method_sources", {}) if isinstance(catalog_document, dict) else {}
    resolved = {}
    for stable_id in sorted(stable_ids):
        origin = deepcopy(sources.get(stable_id)) or None
        entry: dict = {"origin": origin, "materials": {}, "unavailable": []}
        resolved[stable_id] = entry
        run_id = (origin or {}).get("run_id")
        if not origin or not run_id:
            entry["unavailable"].append("The producing run for this method definition is not recorded.")
            continue
        package = _producing_package(project_dir, run_id)
        if package is None:
            entry["unavailable"].append(f"The P2 package published by run {run_id} is unavailable.")
            continue
        records = package.get("records", {})

        def material(family: str, kind: str) -> dict | None:
            pointer = records.get(family)
            if not pointer:
                entry["unavailable"].append(f"The producing run's {family} record is unavailable.")
                return None
            ref = {"branch": "trunk", "phase": "P2", "family": family,
                   "generation_id": pointer.get("generation_id"),
                   "content_sha256": pointer.get("content_sha256"),
                   "run_id": run_id, "package_id": package.get("package_id")}
            try:
                document = read_generation(store, family, pointer)
            except ArtifactError as exc:
                entry["unavailable"].append(f"The producing run's {family} record could not be verified: {exc}")
                return None
            return {"kind": kind, "ref": ref, "document": document, "sha256": pointer.get("content_sha256")}

        family = origin.get("family")
        proposal_id = origin.get("proposal_id")
        if family in PROPOSAL_ROLES:
            proposal = material(family, "proposal")
            if proposal is not None:
                method = proposal["document"].get("method", {}) if isinstance(proposal["document"], dict) else {}
                produced = method.get("identity") or method.get("method_identity") or {}
                if produced != origin.get("identity"):
                    entry["unavailable"].append("The recorded producing proposal no longer matches this definition.")
                else:
                    entry["materials"]["proposal"] = proposal
        elif family:
            changes = material(family, "method_changes")
            if changes is not None:
                entry["materials"]["method_changes"] = changes
        else:
            entry["unavailable"].append("The producing record family is not recorded.")

        if proposal_id:
            reviews = []
            for review_family in sorted(REVIEW_ROLES):
                review = material(review_family, "review")
                if review is None:
                    continue
                assessments = review["document"].get("assessments", []) if isinstance(review["document"], dict) else []
                if any(isinstance(item, dict) and item.get("proposal_id") == proposal_id for item in assessments):
                    review["matched_proposal_id"] = proposal_id
                    reviews.append(review)
            if reviews:
                entry["materials"]["reviews"] = reviews
            else:
                entry["unavailable"].append("No review generation naming the producing proposal is available.")
            assessment = material("catalog_assessment", "catalog_assessment")
            if assessment is not None:
                entry["materials"]["catalog_assessment"] = assessment
        elif family in PROPOSAL_ROLES:
            entry["unavailable"].append(
                "The producing proposal id is not recorded; its reviews and catalog assessment cannot be matched.")
        entry["sha256"] = sha256_bytes(json.dumps(
            {"origin": entry["origin"],
             "materials": {kind: ([item["ref"] for item in value] if isinstance(value, list) else value["ref"])
                           for kind, value in entry["materials"].items()},
             "unavailable": entry["unavailable"]},
            ensure_ascii=False, sort_keys=True).encode())
    return resolved
