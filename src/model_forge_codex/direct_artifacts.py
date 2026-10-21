"""Deterministic compatibility indexes over member-authored P1/P2 records.

Only exact member text and explicit lead field replacements are copied here.
These views keep existing consumers working without inferring scientific
judgments; the original records retain their attribution and revision history.
"""
from __future__ import annotations

from copy import deepcopy

from .records import ArtifactError


LITERATURE_ROLES = {
    "lead_literature": "research_lead",
    "theory_literature": "theorist",
    "empirical_literature": "data_analyst",
}
PROPOSAL_ROLES = {
    "theory_proposal": "theorist",
    "empirical_proposal": "data_analyst",
    "lead_proposal": "research_lead",
}
REVIEW_ROLES = {"theory_review": "theorist", "empirical_review": "data_analyst"}


def direct_literature_sources(documents: dict) -> list[dict]:
    """Retain every member's exact citation revision, including exclusions.

    Bibliographic coalescing belongs to the ordinary cumulative library. A
    lead's landscape exclusion is not a retraction by a paper's publisher.
    """
    from .literature import _source

    sources = []
    for family in LITERATURE_ROLES:
        if family not in documents:
            continue
        collection = documents[family]
        if not isinstance(collection, dict) or not isinstance(collection.get("papers"), list):
            raise ArtifactError(f"{family} is not a literature collection")
        for entry in collection["papers"]:
            if not isinstance(entry, dict):
                raise ArtifactError(f"{family} contains a malformed paper entry")
            sources.append(_source(entry.get("source")))
    return sources


def _decision_view(phase: str, family: str, document: dict, conclusion: str, run_id: str) -> dict:
    # No inferred outcome, evidence strength, score, or scientific verdict.
    return {"schema_version": "1.0.0", "phase": phase, "source_run_id": run_id,
            "headline": document.get("title", ""), "current_conclusion": conclusion,
            "derived": True, "derived_from": [family]}


def derive_direct_records(phase: str, documents: dict, *, run_id: str,
                          previous_library: dict | None = None) -> dict:
    """Return compatibility families without modifying any input document.

    Keys are family suffixes (``research_basis``, not ``p1.research_basis``).
    Old contracts and unrelated phases return no new records. The caller
    publishes the originals and these views atomically, then applies the
    existing cumulative-library/catalog transformation.
    """
    if phase == "P1":
        if not any(family in documents for family in (*LITERATURE_ROLES, "research_basis")):
            return {}
        from .p1_science import effective_literature_sources
        sources = effective_literature_sources(documents, previous_library, run_id=run_id)
        result = {"source_changes": sources}
        basis = documents.get("research_basis")
        if basis is None:
            return result
        if not isinstance(basis, dict):
            raise ArtifactError("research_basis must be an object")
        known_ids = {source["source_id"] for source in sources}
        if previous_library is not None:
            known_ids.update(alias for source in previous_library.get("sources", [])
                             for alias in source.get("source_ids", [source.get("source_id")]))
        for disposition in basis.get("source_dispositions", []):
            if disposition.get("source_id") not in known_ids:
                raise ArtifactError("A landscape disposition names an unknown literature source")
        landscape = basis.get("landscape") or {}
        # This adapter retains the full authored setting and P2 preparation;
        # the markdown alias is the lead's actual cross-paper account.
        result["literature_synthesis"] = {
            **deepcopy(basis), "body_md": landscape.get("summary_markdown", ""),
            "record_id": f"record.{run_id}.literature_synthesis", "record_type": "literature_synthesis", "phase": "P1",
            "derived": True, "derived_from": ["research_basis"],
        }
        result["literature_coverage"] = {
            "schema_version": "1.0.0", "coverage_limits": deepcopy(basis.get("coverage_limits", [])),
            "record_id": f"record.{run_id}.literature_coverage", "record_type": "literature_coverage", "phase": "P1",
            "search_scopes": [{"role": role, "title": documents[family].get("title", ""),
                               "search_scope": documents[family].get("search_scope", ""),
                               "coverage_limits": deepcopy(documents[family].get("coverage_limits", []))}
                              for family, role in LITERATURE_ROLES.items() if family in documents],
            "source_dispositions": deepcopy(basis.get("source_dispositions", [])),
            "derived": True, "derived_from": ["research_basis", *[f for f in LITERATURE_ROLES if f in documents]],
        }
        result["decision"] = _decision_view("P1", "research_basis", basis, landscape.get("summary_markdown", ""), run_id)
        result["attention_items"] = deepcopy(basis.get("attention_items", []))
        return result
    if phase == "P2" and "catalog_assessment" in documents:
        assessment = documents["catalog_assessment"]
        if not isinstance(assessment, dict):
            raise ArtifactError("catalog_assessment must be an object")
        proposals = {}
        for family in PROPOSAL_ROLES:
            if family not in documents:
                continue
            proposal = documents[family]
            if family == "lead_proposal" and isinstance(proposal, dict) and proposal.get("no_method_proposed") is True:
                continue
            if not isinstance(proposal, dict) or not isinstance(proposal.get("method"), dict) or not proposal.get("proposal_id"):
                raise ArtifactError(f"{family} is not a method proposal")
            if proposal["proposal_id"] in proposals:
                raise ArtifactError("Independent proposals must have distinct proposal IDs")
            proposals[proposal["proposal_id"]] = proposal
        dispositions = {}
        for item in assessment.get("method_dispositions", []):
            proposal_id = item.get("proposal_id")
            if proposal_id not in proposals:
                raise ArtifactError("A catalog disposition names an unknown proposal")
            if proposal_id in dispositions or item.get("status") not in {"retain", "exclude"}:
                raise ArtifactError("Every proposal needs one unambiguous catalog disposition")
            dispositions[proposal_id] = item["status"]
        if proposals.keys() != dispositions.keys():
            raise ArtifactError("The catalog comparison must account for every proposal")
        retained = [deepcopy(proposal["method"]) for pid, proposal in proposals.items() if dispositions[pid] == "retain"]
        identities = [(method.get("identity") or method.get("method_identity") or {}).get("stable_id") for method in retained]
        if len(identities) != len(set(identities)):
            raise ArtifactError("Retained independent proposals must have distinct method identities")
        return {"method_changes": {"methods": retained},
                "decision": _decision_view("P2", "catalog_assessment", assessment, assessment.get("comparison_markdown", ""), run_id),
                "attention_items": deepcopy(assessment.get("attention_items", []))}
    return {}


def apply_direct_literature(library: dict, documents: dict, *, run_id: str) -> dict:
    """Carry the exact member findings and landscape dispositions forward.

    The library is built from this run's citations first. These additional
    fields give later phases the same mathematical entries that the UI reads,
    including papers a later literature run did not revisit. Legacy display
    cards are deliberately not promoted into scientific input.
    """
    from .literature import validate_library
    from .p1_science import literature_entries

    result = validate_library(library)
    aliases = {alias: source for source in result["sources"] for alias in source["source_ids"]}
    recorded = [version for source in result["sources"] for current in source.get("assessments", [])
                for version in [current, *current.get("assessment_history", [])]]
    recorded.extend(source["landscape_disposition"] for source in result["sources"] if "landscape_disposition" in source)
    same_run = [item.get("publication_sequence", 0) for item in recorded if item.get("run_id") == run_id
                or (item.get("lead_revision") or {}).get("run_id") == run_id]
    sequence = max(same_run) if same_run else 1 + max((item.get("publication_sequence", 0) for item in recorded), default=0)
    assessments = literature_entries(documents, result, run_id=run_id)
    for source in result["sources"]:
        if "assessments" in source:
            source["assessments"] = []
    for assessment in assessments:
        source = aliases.get(assessment["canonical_source_id"])
        if source is None:
            raise ArtifactError("A member paper cannot be attached to an unknown cumulative source")
        source.setdefault("assessments", []).append({key: value for key, value in assessment.items() if key != "canonical_source_id"})
        revision = assessment.get("lead_revision") or {}
        if (revision.get("correction") or {}).get("source_metadata"):
            effective = next((item for item in source["revisions"] if item["run_id"] == revision["run_id"]
                              and item["document_sha256"] == assessment["source_sha256"]), None)
            if effective is None:
                raise ArtifactError("A metadata-corrected assessment has no retained effective source revision")
            from .literature import retain_source_lead_revision
            retain_source_lead_revision(effective, revision)
    basis = documents.get("research_basis") or {}
    grouped_dispositions = {}
    for index, disposition in enumerate(basis.get("source_dispositions", [])):
        source = aliases.get(disposition["source_id"])
        if source is None:
            raise ArtifactError("A landscape disposition names an unknown cumulative source")
        group = grouped_dispositions.setdefault(source["source_id"], [])
        if group and group[0]["disposition"]["status"] != disposition["status"]:
            raise ArtifactError("A source must have one unambiguous landscape disposition")
        group.append({"entry_pointer": f"/source_dispositions/{index}", "disposition": deepcopy(disposition)})
    for source_id, entries in grouped_dispositions.items():
        source = aliases[source_id]
        disposition = entries[0]["disposition"]
        reasons = list(dict.fromkeys(item["disposition"]["reason"] for item in entries))
        source.update({"landscape_status": disposition["status"], "landscape_reason": "\n\n".join(reasons),
                       "landscape_disposition": {"run_id": run_id, "family": "research_basis", "source_id": disposition["source_id"],
                                                 "publication_sequence": sequence, "entries": entries}})
    return validate_library(result)


def _retained_methods(previous: dict) -> tuple[dict, dict]:
    """Carry retained definitions and their recorded origins forward verbatim."""
    from .methods import _method_documents

    def identity(method):
        return method.get("identity") or method.get("method_identity") or {}

    def legacy_origin(method):
        change_source = (method.get("lineage") or {}).get("change_source") or {}
        producing_run = change_source.get("run_id") if change_source.get("kind") == "research_run" else None
        return {"run_id": producing_run, "stage_id": None, "family": "method_changes", "identity": deepcopy(identity(method)),
                **({"origin_unavailable": True} if not producing_run else {})}

    methods = {identity(method)["stable_id"]: deepcopy(method) for method in _method_documents(previous)}
    old_sources = previous.get("method_sources", {}) if isinstance(previous, dict) else {}
    origins = {}
    for stable_id, method in methods.items():
        origin = deepcopy(old_sources.get(stable_id) or legacy_origin(method))
        if origin.get("identity") != identity(method):
            raise ArtifactError("A cumulative method origin does not match the retained definition")
        origins[stable_id] = origin
    return methods, origins


def _catalog_envelope(methods: dict, origins: dict, *, run_id: str, derived_from: list) -> dict:
    return {"schema_version": "1.0.0", "record_id": f"record.{run_id}.method_catalog", "record_type": "method_catalog", "phase": "P2",
            "methods": [methods[key] for key in sorted(methods)],
            "method_sources": {key: origins[key] for key in sorted(methods)},
            "derived": True, "derived_from": derived_from}


def build_direct_method_catalog(previous: dict, changes: object, *, run_id: str, documents: dict) -> dict:
    """Keep each retained definition's actual producing run as the catalog grows.

    File resolution uses this separate provenance index. Rebuilding the
    catalog must not make an older definition's attachments appear to have
    been created by the latest lead reconciliation.
    """
    from .methods import _method_documents

    def identity(method):
        return method.get("identity") or method.get("method_identity") or {}

    methods, origins = _retained_methods(previous)
    proposals = {family: document for family, document in documents.items() if family in PROPOSAL_ROLES}
    for method in _method_documents(changes):
        current_identity = identity(method)
        stable_id = current_identity["stable_id"]
        matches = [(family, proposal) for family, proposal in proposals.items()
                   if identity(proposal.get("method", {})) == current_identity]
        if len(matches) != 1:
            raise ArtifactError("A changed method must have exactly one producing proposal")
        family, proposal = matches[0]
        methods[stable_id] = deepcopy(method)
        origins[stable_id] = {"run_id": run_id, "stage_id": None, "family": family,
                              "proposal_id": proposal["proposal_id"], "identity": deepcopy(current_identity)}
    return _catalog_envelope(methods, origins, run_id=run_id, derived_from=["catalog_assessment", *proposals])


def build_incremental_method_catalog(previous: dict, changes: object, *, run_id: str, stage_id: str | None = None) -> dict:
    """Catalog rebuild for method_changes runs that carried no full proposals.

    A changed definition's origin is this run's method_changes record itself;
    no proposal is invented for it. Retained definitions keep their recorded
    producing source unchanged.
    """
    from .methods import _method_documents

    def identity(method):
        return method.get("identity") or method.get("method_identity") or {}

    methods, origins = _retained_methods(previous)
    for method in _method_documents(changes):
        current_identity = identity(method)
        stable_id = current_identity["stable_id"]
        methods[stable_id] = deepcopy(method)
        origins[stable_id] = {"run_id": run_id, "stage_id": stage_id, "family": "method_changes",
                              "identity": deepcopy(current_identity)}
    return _catalog_envelope(methods, origins, run_id=run_id, derived_from=["method_changes"])
