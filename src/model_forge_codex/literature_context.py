"""Small navigation files over exact, current member-authored paper records."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .direct_artifacts import LITERATURE_ROLES
from .literature import _digest
from .storage import write_json_atomic


def _entry_detail(item: dict, reference: dict) -> dict:
    content = {"reference": reference, "entry": deepcopy(item["entry"])}
    if item.get("lead_revision"):
        revision = item["lead_revision"]
        correction = revision.get("correction") or {}
        content["lead_revision"] = {"role": revision.get("role"), "run_id": revision.get("run_id"),
                                   "correction_id": correction.get("correction_id"),
                                   "reason_markdown": correction.get("reason_markdown"),
                                   "evidence_locations": deepcopy(correction.get("evidence_locations", []))}
    return content


def write_literature_context(root: Path, library: dict, assessments: list[dict],
                             collections: dict, *, run_id: str) -> Path:
    """Create deterministic read views; no extra model or scientific summary.

    Caller restricts inputs to the frozen library and permitted completed
    stages. Entry filenames use content identities, never authored paths.
    """
    from .p1_science import entry_reference

    scopes = [{"role": LITERATURE_ROLES[family], "run_id": run_id,
               "title": document.get("title", ""), "search_scope": document.get("search_scope", ""),
               "coverage_limits": deepcopy(document.get("coverage_limits", [])),
               "proposed_questions": deepcopy(document.get("proposed_questions", [])),
               **({"data_profiles": deepcopy(document["data_profiles"])}
                  if family == "empirical_literature" and document.get("data_profiles") else {}),
               "assessment_count": len(document.get("papers", []))}
              for family, document in collections.items() if family in LITERATURE_ROLES]
    identity = _digest({"view_version": "1.2.0", "library": library,
                        "entries": [entry_reference(item) for item in assessments], "scopes": scopes})
    directory = root / identity
    index_path = directory / "index.json"
    if index_path.is_file():
        return index_path
    aliases = {alias: source["source_id"] for source in library.get("sources", [])
               for alias in source.get("source_ids", [source["source_id"]])}
    canonical_sources = {source["source_id"]: source for source in library.get("sources", [])}
    entries = []
    for item in assessments:
        reference = entry_reference(item)
        relative = "entries/" + _digest(reference) + ".json"
        entry = item["entry"]
        source = entry["source"]
        canonical = canonical_sources[aliases.get(source["source_id"], source["source_id"])]
        current_source = {key: deepcopy(canonical[key]) for key in (
            "source_id", "title", "authors", "year", "venue", "identifiers", "source_status", "status_reason",
            "landscape_status", "landscape_reason", "landscape_disposition") if key in canonical}
        content = {**_entry_detail(item, reference), "current_source": current_source,
                   "citation_state": "provisional" if any(doc.get("schema_version") == "1.2.0" for doc in collections.values()) else "accepted-comparison"}
        history_refs = []
        for earlier in item.get("assessment_history", []):
            prior_reference = entry_reference(earlier)
            prior_path = "history/" + _digest(prior_reference) + ".json"
            write_json_atomic(directory / prior_path, _entry_detail(earlier, prior_reference))
            history_refs.append({"reference": prior_reference, "entry_path": prior_path})
        if history_refs:
            content["earlier_versions"] = history_refs
        write_json_atomic(directory / relative, content)
        entries.append({"reference": reference, "source_id": aliases.get(source["source_id"], source["source_id"]),
                        "title": source.get("title", ""), "year": source.get("year"),
                        "authors": deepcopy(source.get("authors", [])),
                        "identifiers": deepcopy(source.get("identifiers", [])),
                        **{key: deepcopy(current_source[key]) for key in (
                            "source_status", "status_reason", "landscape_status", "landscape_reason") if key in current_source},
                        "topics": deepcopy(entry.get("topics", [])), "reading_extent": entry.get("reading_extent", "Not recorded"),
                        "entry_path": relative, "revised_by_lead": bool(item.get("lead_revision"))})
    entries.sort(key=lambda item: (item["title"], item["reference"]["role"], item["reference"]["entry_id"]))
    pages = []
    for offset in range(0, len(entries), 40):
        relative = f"pages/{offset // 40 + 1:04d}.json"
        batch = entries[offset:offset + 40]
        write_json_atomic(directory / relative, {"entries": batch, "path_base": "Paths are relative to the main index directory."})
        pages.append({"path": relative, "assessment_count": len(batch)})
    # Bibliographic-only sources still belong to the landscape. Their complete
    # source records remain accessible without importing old display-only cards.
    assessed_sources = {item["source_id"] for item in entries}
    unassessed = []
    for source in library.get("sources", []):
        if source["source_id"] in assessed_sources:
            continue
        relative = "sources/" + _digest(source["source_id"]) + ".json"
        write_json_atomic(directory / relative, {key: deepcopy(value) for key, value in source.items()
                                                 if key not in {"assessments", "cards", "card"}})
        unassessed.append({"source_id": source["source_id"], "title": source.get("title", ""),
                           "year": source.get("year"), "source_path": relative})
    from .literature import source_identity_conflicts
    conflicts = source_identity_conflicts([item["entry"]["source"] for item in assessments], normalize_authors=True, strict_identifiers=True)
    conflict_details = [{**conflict, "left_ref": entry_reference(assessments[conflict["left"]]),
                         "right_ref": entry_reference(assessments[conflict["right"]]),
                         "left_source": deepcopy(assessments[conflict["left"]]["entry"]["source"]),
                         "right_source": deepcopy(assessments[conflict["right"]]["entry"]["source"])} for conflict in conflicts]
    write_json_atomic(index_path, {"schema_version": "1.1.0", "unique_source_count": len(library.get("sources", [])),
                                  "assessment_count": len(entries), "collections": scopes, "pages": pages,
                                  "sources_without_mathematical_assessments": unassessed,
                                  "citation_conflicts": conflict_details,
                                  "reading_instruction": "Inspect the index for coverage, then open entries supporting the comparisons you need. Indexing is not scientific review.",
                                  "entry_digest_instruction": "Index references identify entries before this reconciliation. For an entry you correct in this turn, replace its changed fields. If source_metadata is present, replace only those nested source fields, remove the old source content_sha256, set content_sha256_scope to citation-record-excluding-content_sha256, and recompute source content_sha256 over the resulting source excluding content_sha256. Then compute entry_sha256 over the full effective entry. Each digest is hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest(). Citation and landscape support references identify the effective entry; scientific review and correction targets identify the original entry."})
    return index_path
