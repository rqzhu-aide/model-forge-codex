"""Source-linked research views over exact published generations."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote, urlencode

from .empirical_context import evaluation_theory_context
from .empirical_targets import effective_protocol, protocol_questions
from .records import ArtifactError, committed_packages, current_records, generation_path, read_generation
from .storage import read_json, sha256_file
from .research_sources import (evaluated_method_projection, file_media, implementation_projection, literature_reference_links,
                               producing_role, theory_statement_projection, traceability_projection)


def source_ref(branch: str, phase: str, family: str, pointer: dict) -> dict:
    return {"branch": branch, "phase": phase, "family": family,
            "generation_id": pointer.get("generation_id"),
            "sha256": pointer.get("content_sha256", pointer.get("sha256", "")),
            "run_id": pointer.get("run_id", pointer.get("source_run_id", "")),
            "stage_id": pointer.get("stage_id"), "package_id": pointer.get("package_id")}


def _same_evaluation(left: dict, right: dict) -> bool:
    """Authored answers join only to their own protocol publication."""
    a, b = left.get("generation_ref", {}), right.get("generation_ref", {})
    return bool(a.get("run_id") and a["run_id"] == b.get("run_id")
                and all(not a.get(key) or not b.get(key) or a[key] == b[key]
                        for key in ("branch", "phase", "package_id")))


def _question_records(document: dict, field: str) -> dict:
    entries = document.get(field) if isinstance(document, dict) else None
    if not isinstance(entries, list):
        return {}
    result, ambiguous = {}, set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("question_id"), str):
            continue
        identifier = entry["question_id"]
        if identifier in result:
            ambiguous.add(identifier)
        result[identifier] = entry
    return {key: value for key, value in result.items() if key not in ambiguous}


def record_url(project_id: str, ref: dict) -> str:
    values = [project_id, ref["branch"], ref["phase"], ref["family"], ref["generation_id"]]
    pid, branch, phase, family, generation = [quote(str(value), safe="") for value in values]
    return f"/api/v1/projects/{pid}/branches/{branch}/phases/{phase}/records/{family}/{generation}"


def _run_for_generation(project_dir: Path, phase_dir: Path, family: str, pointer: dict) -> str | None:
    """Legacy resolution requires an exact publication receipt association."""
    run_id = pointer.get("run_id") or pointer.get("source_run_id")
    if run_id:
        return run_id
    generation = pointer.get("generation_id")
    matches = set()
    for receipt_path in (project_dir / "authority" / "receipts").glob("*.json"):
        receipt = read_json(receipt_path) or {}
        # Receipts have changed shape; match the exact generation, never an exhibit name.
        text = json.dumps(receipt)
        if generation and f'"{generation}"' in text:
            found = receipt.get("run_id") or receipt.get("source_run_id")
            if found:
                matches.add(found)
    return next(iter(matches)) if len(matches) == 1 else None


def exhibit_source(project_dir: Path, ref: dict, exhibit: dict) -> dict:
    """Resolve through the producing run and verify both manifest and file."""
    phase_dir = project_dir / "branches" / ref["branch"] / "phases" / ref["phase"].lower()
    run_id = _run_for_generation(project_dir, phase_dir, ref["family"], ref)
    if not run_id:
        return {"source_error": "The producing run is not recorded for this historical figure."}
    run_dir = project_dir / "runs" / run_id
    run = read_json(run_dir / "run.json") or {}
    if run.get("state") != "published" or run.get("branch_id") != ref["branch"] or run.get("phase") != ref["phase"]:
        return {"source_error": "The figure does not match a published run for this method and phase."}
    expected = exhibit.get("artifact_sha256")
    if not expected:
        return {"source_error": "This historical figure has no recorded digest."}
    relative = Path(exhibit.get("artifact_path", ""))
    if relative.is_absolute() or ".." in relative.parts or not str(relative):
        return {"source_error": "The figure path is invalid."}
    matches = []
    outputs = run_dir / "outputs"
    stages = [outputs / ref["stage_id"]] if ref.get("stage_id") else sorted(outputs.glob("*"))
    for stage in stages:
        if not stage.is_dir():
            continue
        manifest = read_json(stage / "exhibits.json")
        if not isinstance(manifest, list):
            continue
        if not any(isinstance(item, dict) and item.get("exhibit_id") == exhibit.get("exhibit_id")
                   and item.get("artifact_sha256") == expected and item.get("artifact_path") == str(exhibit.get("artifact_path"))
                   for item in manifest):
            continue
        target = (stage / relative).resolve()
        if not target.is_relative_to(stage.resolve()) or not target.is_file():
            continue
        if sha256_file(target) != expected:
            return {"source_error": "The figure bytes do not match their published digest."}
        matches.append((stage.name, target))
    if len(matches) != 1:
        return {"source_error": "The exact published figure source is missing or ambiguous."}
    query = urlencode({"path": str(exhibit["artifact_path"]), "sha256": expected})
    url = f"/api/v1/projects/{quote(project_dir.name)}/runs/{quote(run_id)}/outputs/{quote(matches[0][0])}/artifact?{query}"
    result = {"artifact_url": url, "source_verified": True, "producing_run_id": run_id}
    if exhibit.get("kind") == "table":
        from .table_exhibits import table_preview
        try:
            table = table_preview(matches[0][1], exhibit)
            page_url = url.replace("/artifact?", "/table?") + "&" + urlencode({"exhibit_id": exhibit.get("exhibit_id", "")})
            if table["truncated"]:
                table["next_page_url"] = page_url + "&offset=200"
            result["table"] = table
        except (OSError, ValueError, TypeError, UnicodeError) as error:
            result["source_error"] = f"The verified table could not be rendered inline: {error}"
    return result


def _figure_data_sources(exhibits: list[dict]) -> None:
    """A figure names its tables explicitly; captions never establish a join."""
    for figure in exhibits:
        if figure.get("kind") != "figure":
            continue
        declared = figure.get("data_exhibit_ids", [])
        sources = []
        for identifier in declared if isinstance(declared, list) else []:
            matches = [table for table in exhibits if table.get("exhibit_id") == identifier
                       and table.get("kind") == "table"
                       and table.get("generation_ref") == figure.get("generation_ref")]
            if len(matches) == 1:
                sources.append({key: value for key, value in matches[0].items() if key not in {"data_sources", "data_exhibit_ids"}})
            else:
                sources.append({"exhibit_id": identifier, "source_error": "The declared data table is missing or ambiguous in this saved exhibit record."})
        figure["data_sources"] = sources
        figure["data_source_status"] = ("missing" if not declared else "verified" if sources
                                        and all(item.get("source_verified") and not item.get("source_error") for item in sources) else "unavailable")


def _authored_markdown(document) -> str:
    if not isinstance(document, dict):
        return ""
    for key in ("body_md", "body_markdown", "markdown", "manuscript_markdown", "content_markdown", "evaluation_markdown", "summary_markdown", "body", "text"):
        if isinstance(document.get(key), str):
            return document[key]
    return ""


def _document_body(document) -> str:
    if isinstance(document, str):
        return document
    if isinstance(document, list):
        return _document_body({"issues": document})
    if not isinstance(document, dict):
        return ""
    for key in ("body_md", "body_markdown", "markdown", "manuscript_markdown", "content_markdown", "evaluation_markdown", "summary_markdown"):
        if isinstance(document.get(key), str):
            return document[key]
    # Faithful structured rendering; no generated scientific interpretation.
    sections = []
    for key in ("theory_scope", "current_conclusion", "scope_justification", "scientific_question", "summary", "abstract",
                "overall_assessment", "reviewed_scope"):
        if isinstance(document.get(key), str):
            sections.append(document[key])
    outcome = document.get("scientific_outcome")
    if isinstance(outcome, dict) and isinstance(outcome.get("conclusion"), str):
        sections.append(outcome["conclusion"])
    for field, label in (("assumptions", "Assumptions"), ("statements", "Statements"),
                         ("claim_tests", "Empirical questions"), ("limitations", "Limitations"),
                         ("sections", "Manuscript"), ("revision_account", "Revision account"),
                         ("work_summaries", "Contributions of cited work"), ("search_boundaries", "Search boundaries"),
                         ("covered_questions", "Questions covered"), ("coverage", "Coverage"),
                         ("exclusions", "Exclusions"), ("unresolved_gaps", "Open gaps"),
                         ("strengths", "Strengths"), ("missing_materials", "Missing materials"),
                         ("prioritized_issues", "Review findings"), ("issues", "Review findings"),
                         ("evidence_that_would_change_assessment", "Evidence that would change this assessment")):
        value = document.get(field)
        if not value:
            continue
        sections.append(f"## {label}")
        items = value if isinstance(value, list) else [value]
        for item in items:
            if isinstance(item, str):
                sections.append(item)
            elif isinstance(item, dict):
                title = item.get("title") or item.get("label") or item.get("issue") or item.get("statement_id") or item.get("assumption_id") or item.get("test_id")
                if title:
                    sections.append(f"### {title}")
                for name in ("text", "statement", "body", "body_md", "content", "question", "purpose", "proof", "proof_sketch", "status", "sensitivity", "change_summary",
                             "key_contribution", "relevance_to_question", "scientific_consequence", "requested_resolution", "resolution_summary", "rationale"):
                    entry = item.get(name)
                    if isinstance(entry, str):
                        sections.append(entry)
                if item.get("latex"):
                    sections.append("$$\n" + item["latex"] + "\n$$")
    return "\n\n".join(sections)


def _record_meta(project_dir: Path, branch: str, phase: str, family: str, pointer: dict, *, package=None) -> dict:
    ref = source_ref(branch, phase, family, pointer)
    meta = {"branch": branch, "phase": phase, "family": family, "generation_ref": ref,
            "source_url": record_url(project_dir.name, ref), "published_at": pointer.get("published_at", "")}
    if phase in {"P1", "P2"}:
        # The writing contract belongs to the generation's producing package.
        # A later package may retain the same pointer or correct one field.
        meta["catalog_pin"] = None
        store = project_dir / "branches" / branch / "phases" / phase.lower()
        producing_here = package is not None and (
            pointer.get("package_id") == package.get("package_id") if pointer.get("package_id") else
            ref.get("run_id") and ref["run_id"] == package.get("run_id"))
        packages = [package] if producing_here else committed_packages(store)
        for producing_package in packages:
            original = producing_package["records"].get(family) or {}
            if (original.get("generation_id") != ref["generation_id"]
                    or (original.get("content_sha256") or original.get("sha256")) != ref["sha256"]):
                continue
            if pointer.get("package_id"):
                if producing_package.get("package_id") != pointer["package_id"]:
                    continue
            elif not ref.get("run_id") or producing_package.get("run_id") != ref["run_id"]:
                continue
            meta["catalog_pin"] = deepcopy((producing_package.get("metadata") or {}).get("catalog_pin"))
            break
    return meta


def _bibliographic_tokens(document: dict) -> set[str]:
    """Use explicit locators only, never infer a source from its title."""
    from .literature import LiteratureError, canonical_identifier
    identifiers = list(document.get("identifiers", [])) if isinstance(document.get("identifiers"), list) else []
    identifiers.extend({"kind": kind, "value": document[field]}
                       for field, kind in (("doi", "doi"), ("arxiv", "arxiv"), ("url", "url"), ("primary_url", "url"))
                       if isinstance(document.get(field), str) and document[field].strip())
    tokens = set()
    for identifier in identifiers:
        if not isinstance(identifier, dict) or str(identifier.get("kind", "")).strip().lower() not in {"doi", "arxiv", "url"}:
            continue
        try:
            tokens.add(canonical_identifier(identifier))
        except LiteratureError:
            continue
    return tokens


def _discovery_source_links(document: dict, source_tokens: dict[str, set[str]]) -> dict:
    """Resolve role-local aliases from a single committed discovery document."""
    collections = [document.get("source_records"), document.get("literature_sources")]
    if isinstance(document.get("literature_basis"), dict):
        collections.append(document["literature_basis"].get("source_records"))
    candidates, matched_tokens = {}, {}
    for collection in collections:
        for record in collection if isinstance(collection, list) else []:
            if not isinstance(record, dict) or not isinstance(record.get("source_id"), str):
                continue
            alias = record["source_id"]
            tokens = _bibliographic_tokens(record)
            matches = {source_id for source_id, identifiers in source_tokens.items() if tokens & identifiers}
            # An unresolved duplicate or conflicting locator must not turn an
            # ambiguous role alias into a confident library association.
            candidates.setdefault(alias, set()).update(matches or {None})
            matched_tokens.setdefault(alias, set()).update(
                token for source_id in matches for token in tokens & source_tokens[source_id])
    return {alias: {"source_id": next(iter(matches)), "identifiers": sorted(matched_tokens[alias])}
            for alias, matches in candidates.items() if len(matches) == 1 and None not in matches}


def _direct_phase_projection(project_dir: Path, branch: str, phase: str, result: dict) -> None:
    """Expose exact authored records in committed order, including history."""
    from .direct_artifacts import LITERATURE_ROLES, PROPOSAL_ROLES, REVIEW_ROLES

    families = ({**{family: ("literature_collections", role) for family, role in LITERATURE_ROLES.items()},
                 "research_basis": ("research_bases", "research_lead")} if phase == "P1" else
                {**{family: ("method_proposals", role) for family, role in PROPOSAL_ROLES.items()},
                 **{family: ("method_reviews", role) for family, role in REVIEW_ROLES.items()},
                 "catalog_assessment": ("catalog_assessments", "research_lead")})
    phase_dir = project_dir / "branches" / branch / "phases" / phase.lower()
    seen = set()
    try:
        for index, package in enumerate(committed_packages(phase_dir)):
            if phase == "P2":
                metadata = package.get("metadata") or {}
                history = metadata.get("publication_history") or {}
                # Only publication-time counts describe this committed package.
                # Missing legacy metadata remains unknown, including when a
                # producing run's mutable execution history is still present.
                def count(name):
                    value = history.get(name) if isinstance(history, dict) else None
                    return value if type(value) is int and value >= 0 else None
                result["publication_history"].append({
                    "branch": branch, "phase": phase, "package_id": package.get("package_id"),
                    "run_id": package.get("run_id"), "published_at": package.get("published_at"),
                    "is_current_package": index == 0, "receipt_id": metadata.get("receipt_id"),
                    "mechanical_repair_rounds": count("mechanical_repair_rounds"),
                    "researcher_correction_attempts": count("researcher_correction_attempts"),
                })
            for family, (target, role) in families.items():
                pointer = package["records"].get(family)
                if pointer is None or (family, pointer.get("generation_id")) in seen:
                    continue
                seen.add((family, pointer.get("generation_id")))
                meta = _record_meta(project_dir, branch, phase, family, pointer, package=package)
                try:
                    document = read_generation(phase_dir, family, pointer)
                    if not isinstance(document, dict):
                        raise ArtifactError("Published direct research record must be an object")
                except ArtifactError as exc:
                    result["load_errors"].append({**meta, "message": str(exc)})
                    continue
                catalog_pointer = package["records"].get("method_catalog") if phase == "P2" and family in PROPOSAL_ROLES else None
                result[target].append({**deepcopy(document), **meta, "role": role,
                                       **({"catalog_ref": source_ref(branch, phase, "method_catalog", catalog_pointer)} if catalog_pointer else {}),
                                       "package_id": package.get("package_id"),
                                       "published_at": meta.get("published_at") or package.get("published_at"),
                                       "is_current_package": index == 0})
    except ArtifactError as exc:
        result["load_errors"].append({"branch": branch, "phase": phase, "family": "direct_records", "message": str(exc)})


def _citation_projection(binding: dict, snapshot: dict | None, card_for) -> dict:
    """Resolve an authored binding only inside its frozen publication library."""
    from .literature import _digest
    reference = binding.get("entry_ref") or {}
    citation = {"source_id": binding.get("source_id"), "entry_ref": deepcopy(reference), "status": "unavailable"}
    if not all(reference.get(key) for key in ("role", "family", "run_id", "entry_id", "entry_sha256")):
        return citation
    matches = []
    for source_index, retained in enumerate((snapshot or {}).get("sources", [])):
        for assessment_index, assessment in enumerate(retained.get("assessments", [])):
            entry = assessment.get("entry") or {}
            if (all(reference[key] == assessment.get(key) for key in ("role", "family", "run_id", "entry_sha256"))
                    and reference["entry_id"] == entry.get("entry_id")
                    and binding.get("source_id") == entry.get("source", {}).get("source_id")
                    and _digest(entry) == reference["entry_sha256"]):
                matches.append((retained, assessment, source_index, assessment_index))
    if len(matches) == 1:
        retained, assessment, source_index, assessment_index = matches[0]
        card = card_for(retained, assessment, source_index, assessment_index)
        if card:
            citation.update(status="available", bibliography=deepcopy(assessment["entry"]["source"]),
                            canonical_source_id=retained["source_id"], card=card)
    return citation


def _issue_citation_projection(project_dir: Path, issues: list[dict]) -> None:
    """Add display-only citations without consulting a newer source revision."""
    # Audits can also retain plain record IDs and manuscript locations here.
    if not any(isinstance(ref, dict) and ref.get("entry_ref")
               for issue in issues for ref in issue.get("source_refs", [])):
        return
    phase_dir = project_dir / "branches" / "trunk" / "phases" / "p1"
    try:
        packages = list(committed_packages(phase_dir))
    except ArtifactError:
        packages = []
    snapshots = {}
    for issue in issues:
        bindings = [ref for ref in issue.get("source_refs", [])
                    if isinstance(ref, dict) and ref.get("source_id") and ref.get("entry_ref")]
        if not bindings:
            continue
        issue["citations"] = []
        for binding in bindings:
            run_id = binding["entry_ref"].get("run_id")
            if run_id not in snapshots:
                matches = [package for package in packages if package.get("run_id") == run_id
                           and package.get("records", {}).get("literature_library")]
                snapshot, meta = None, None
                if len(matches) == 1:
                    package = matches[0]
                    pointer = package["records"]["literature_library"]
                    try:
                        snapshot = read_generation(phase_dir, "literature_library", pointer)
                        meta = _record_meta(project_dir, "trunk", "P1", "literature_library", pointer, package=package)
                    except ArtifactError:
                        pass
                snapshots[run_id] = snapshot, meta
            snapshot, meta = snapshots[run_id]
            def card_for(_retained, assessment, source_index, assessment_index):
                if meta is None:
                    return None
                pointer = f"/sources/{source_index}/assessments/{assessment_index}/entry"
                return {**deepcopy(assessment["entry"]), **meta, "role": assessment["role"],
                        "entry_sha256": assessment["entry_sha256"], "entry_pointer": pointer,
                        "generation_ref": {**meta["generation_ref"], "entry_pointer": pointer}}
            issue["citations"].append(_citation_projection(binding, snapshot, card_for))


def _literature_projection(project_dir: Path, records: dict, result: dict) -> None:
    """Join authored cards to accepted sources without changing research data."""
    from .literature import _digest, load_committed_library
    from .direct_artifacts import LITERATURE_ROLES
    if not any(family in records for family in ("source_changes", "literature_library", "research_basis", *LITERATURE_ROLES)):
        return
    phase_dir = project_dir / "branches" / "trunk" / "phases" / "p1"
    try:
        library = load_committed_library(project_dir)
    except ArtifactError as exc:
        result["load_errors"].append({"branch": "trunk", "phase": "P1", "family": "literature_library", "message": str(exc)})
        return
    sources = {source["source_id"]: source for source in library["sources"]}
    aliases = {alias: source for source in library["sources"] for alias in source["source_ids"]}
    source_tokens = {source_id: _bibliographic_tokens(source) for source_id, source in sources.items()}
    for source in sources.values():
        source["cards"] = []
    source_refs, current_cards, linked_cards, run_order, seen_versions = [], {}, set(), {}, set()
    direct = {(record["family"], record["generation_ref"]["generation_id"]): record
              for key in ("literature_collections", "research_bases") for record in result[key]
              if record["branch"] == "trunk"}
    seen_dispositions = set()
    origin_meta = {}
    def card_key(card, family, generation):
        return family, generation, card.get("card_id"), card.get("subject_ref")
    def attach_card(source, role, card, meta, association=None):
        version_key = (source["source_id"], role, *card_key(card, meta["family"], meta["generation_ref"]["generation_id"]))
        if version_key in seen_versions:
            return
        seen_versions.add(version_key)
        projected = {**deepcopy(card), **meta, **(association or {}), "kind": "paper", "role": role,
                     "canonical_source_id": source["source_id"], "source_status": source["source_status"],
                     "from_earlier_run": meta["generation_ref"]["run_id"] != library["run_id"]}
        key = source["source_id"], role
        if key in current_cards:
            current_cards[key].setdefault("assessment_history", []).append(projected)
        else:
            current_cards[key] = projected
            source["cards"].append(projected)
    role_families = {"lead_paper_cards": "research_lead", "theory_paper_cards": "theorist", "empirical_paper_cards": "data_analyst"}
    try:
        for index, package in enumerate(committed_packages(phase_dir)):
            pointers = package["records"]
            if package.get("run_id"):
                run_order[package["run_id"]] = index
            if "source_changes" in pointers:
                pointer = pointers["source_changes"]
                meta = _record_meta(project_dir, "trunk", "P1", "source_changes", pointer, package=package)
                source_refs.append({**meta["generation_ref"], "source_url": meta["source_url"]})
            basis_pointer = pointers.get("research_basis")
            basis = direct.get(("research_basis", basis_pointer["generation_id"])) if basis_pointer else None
            if basis:
                origin_meta[("research_basis", basis["generation_ref"]["run_id"])] = _record_meta(project_dir, "trunk", "P1", "research_basis", basis_pointer, package=package)
                for disposition in basis.get("source_dispositions", []):
                    source = aliases.get(disposition.get("source_id"))
                    if source is None or source["source_id"] in seen_dispositions:
                        continue
                    seen_dispositions.add(source["source_id"])
                    retained = source.get("landscape_disposition") or {}
                    if not (retained.get("entries") and retained.get("run_id") == basis["generation_ref"]["run_id"]):
                        source.update({"landscape_status": disposition["status"], "landscape_reason": disposition["reason"]})
                    source.update({"disposition_generation_ref": basis["generation_ref"],
                                   "disposition_source_url": basis["source_url"]})
            for family, role in LITERATURE_ROLES.items():
                pointer = pointers.get(family)
                collection = direct.get((family, pointer["generation_id"])) if pointer else None
                if collection is None:
                    continue
                meta = _record_meta(project_dir, "trunk", "P1", family, pointer, package=package)
                origin_meta[(family, meta["generation_ref"]["run_id"])] = meta
                if "source_changes" not in pointers:
                    source_refs.append({**meta["generation_ref"], "source_url": meta["source_url"]})
                for entry_index, entry in enumerate(collection.get("papers", [])):
                    if not isinstance(entry, dict) or not isinstance(entry.get("source"), dict):
                        continue
                    authored_source = entry["source"]
                    source = aliases.get(authored_source.get("source_id"))
                    association = {"source_association": {"method": "authored_entry_source",
                                   "generation_ref": meta["generation_ref"],
                                   "entry_pointer": f"/papers/{entry_index}"}}
                    if source is None:
                        tokens = _bibliographic_tokens(authored_source)
                        matches = [item for sid, item in sources.items() if tokens & source_tokens[sid]]
                        source = matches[0] if len(matches) == 1 else None
                    card = {**deepcopy(entry), "card_id": entry.get("entry_id"),
                            "subject_ref": authored_source.get("source_id"), "title": authored_source.get("title", ""),
                            "entry_pointer": f"/papers/{entry_index}", "direct_artifact": True,
                            "run_id": meta["generation_ref"]["run_id"], "entry_sha256": _digest(entry)}
                    if source is None:
                        result["cards"].append({**card, **meta, "role": role, "kind": "paper"})
                    else:
                        attach_card(source, role, card, meta, association)
            for family, role in role_families.items():
                if family not in pointers:
                    continue
                meta = _record_meta(project_dir, "trunk", "P1", family, pointers[family], package=package)
                try:
                    cards = read_generation(phase_dir, family, pointers[family])
                    if not isinstance(cards, list):
                        raise ArtifactError("Published paper cards are not a card collection")
                except ArtifactError as exc:
                    result["load_errors"].append({**meta, "message": str(exc)})
                    continue
                discovery_links, discovery_meta = {}, None
                discovery_family = family.replace("_paper_cards", "_discovery")
                if discovery_family in pointers and any(isinstance(card, dict) and card.get("subject_ref") not in aliases for card in cards):
                    discovery_meta = _record_meta(project_dir, "trunk", "P1", discovery_family, pointers[discovery_family], package=package)
                    try:
                        discovery = read_generation(phase_dir, discovery_family, pointers[discovery_family])
                        if (isinstance(discovery, dict) and meta["generation_ref"]["run_id"]
                                and discovery_meta["generation_ref"]["run_id"] == meta["generation_ref"]["run_id"]):
                            discovery_links = _discovery_source_links(discovery, source_tokens)
                    except ArtifactError as exc:
                        result["load_errors"].append({**discovery_meta, "message": str(exc)})
                for card in cards:
                    if not isinstance(card, dict):
                        continue
                    source = aliases.get(card.get("subject_ref"))
                    association = {}
                    link = discovery_links.get(card.get("subject_ref")) if source is None else None
                    if link:
                        source = sources[link["source_id"]]
                        association = {"source_association": {"method": "published_discovery_identifier",
                                       "generation_ref": discovery_meta["generation_ref"],
                                       "identifiers": link["identifiers"]}}
                    if source is None:
                        continue
                    linked_cards.add(card_key(card, family, meta["generation_ref"]["generation_id"]))
                    attach_card(source, role, card, meta, association)
    except ArtifactError as exc:
        result["load_errors"].append({"branch": "trunk", "phase": "P1", "family": "paper_cards", "message": str(exc)})
    # Current cards use the same effective assessments that later phases read.
    # Their authored files remain immutable and accessible in revision history.
    def effective_card(source, assessment):
        meta = origin_meta.get((assessment["family"], assessment["run_id"]))
        if meta is None:
            return None
        entry = assessment["entry"]
        card = {**deepcopy(entry), **meta, "card_id": entry["entry_id"], "subject_ref": entry["source"]["source_id"],
                "title": entry["source"].get("title", ""), "entry_pointer": assessment.get("entry_pointer"),
                "direct_artifact": True, "kind": "paper", "role": assessment["role"], "run_id": assessment["run_id"],
                "entry_sha256": assessment["entry_sha256"], "source_sha256": assessment["source_sha256"],
                "canonical_source_id": source["source_id"], "source_status": source["source_status"],
                "from_earlier_run": assessment["run_id"] != library["run_id"],
                "source_association": {"method": "authored_entry_source", "generation_ref": meta["generation_ref"],
                                       "entry_pointer": assessment.get("entry_pointer")}}
        if assessment.get("lead_revision"):
            revision = deepcopy(assessment["lead_revision"])
            revision_meta = origin_meta.get(("research_basis", revision["run_id"]))
            if revision_meta:
                revision.update({"generation_ref": {**revision_meta["generation_ref"], "entry_pointer": revision["entry_pointer"]},
                                 "source_url": revision_meta["source_url"]})
            card["lead_revision"] = revision
        return card
    for source in sources.values():
        for assessment in source.get("assessments", []):
            projected = effective_card(source, assessment)
            if projected is None:
                continue
            prior = next((card for card in source["cards"] if card["role"] == assessment["role"]), None)
            history = [card for version in assessment.get("assessment_history", []) if (card := effective_card(source, version))]
            known = {(card.get("run_id"), card.get("entry_sha256")) for card in history}
            if prior:
                history.extend(card for card in prior.get("assessment_history", [])
                               if (card.get("run_id"), card.get("entry_sha256")) not in known)
                source["cards"][source["cards"].index(prior)] = projected
            else:
                source["cards"].append(projected)
            if history:
                projected["assessment_history"] = history
    for source in sources.values():
        revision = source["revisions"][-1]
        revision_run = revision["run_id"]
        for card in [version for card in source["cards"] for version in [card, *card.get("assessment_history", [])]]:
            assessment_run = card["generation_ref"]["run_id"]
            known = revision_run in run_order and assessment_run in run_order
            card["current_source_revision"] = {"run_id": revision_run, "document_sha256": revision["document_sha256"]}
            card["assessment_predates_source_revision"] = known and run_order[assessment_run] > run_order[revision_run]
            card["assessment_basis_unverified"] = not known and assessment_run != revision_run
    if "literature_library" in records:
        _, meta = records["literature_library"]
        projection = {**library, **meta, "derived": False}
    else:
        projection = {**library, "branch": "trunk", "phase": "P1", "family": "literature_library",
                      "derived": True, "source_refs": source_refs,
                      "derivation": "Reconstructed from committed P1 source generations; no new research was authored."}
    result["literature_libraries"].append(projection)
    # Resolve each synthesis against its own publication, including no-op
    # corrections whose content digest is shared with a later revision.
    packages = {package.get("package_id"): package for package in committed_packages(phase_dir)}
    for basis in result["research_bases"]:
        bindings = (basis.get("landscape") or {}).get("citation_refs", [])
        if not bindings:
            continue
        package = packages.get(basis.get("package_id")) or {}
        pointer = package.get("records", {}).get("literature_library")
        snapshot = None
        try:
            if pointer:
                snapshot = read_generation(phase_dir, "literature_library", pointer)
        except ArtifactError:
            pass
        basis["citations"] = [_citation_projection(binding, snapshot,
                               lambda source, assessment, *_: effective_card(source, assessment)) for binding in bindings]
    # Older clients retain a cumulative card list. Unmatched current cards stay
    # visible as unlinked assessments rather than acquiring a false source link.
    result["cards"] = [card for card in result["cards"] if not (card.get("phase") == "P1" and card.get("branch") == "trunk"
                         and card.get("kind") == "paper" and card_key(card, card.get("family"),
                             card.get("generation_ref", {}).get("generation_id")) in linked_cards)]
    result["cards"].extend(card for source in library["sources"] for card in source["cards"])


def _primary_document_pointer(document):
    if not isinstance(document, dict):
        return None
    return (document.get("report_artifact") or document.get("primary_artifact") or document.get("manuscript_artifact")
            or next((r.get("artifact") for r in document.get("representations") or []
                     if isinstance(r, dict) and r.get("information_layer") == "primary_artifact"), None))


def _primary_document(project_dir: Path, ref: dict, document) -> dict:
    """Open an authored document only through its producing run and digest."""
    if not isinstance(document, dict):
        return {}
    analyst_account = ref.get("family") == "analyst_synthesis"
    label = "Analyst account" if analyst_account else "report" if document.get("record_type") == "technical_report" or ref.get("family") in {"technical_report", "technical_report_candidate"} else "manuscript"
    pointer = _primary_document_pointer(document)
    if not isinstance(pointer, dict):
        return {}
    relative = Path(pointer.get("path", ""))
    expected = pointer.get("sha256")
    if not pointer.get("path") or relative.is_absolute() or ".." in relative.parts or not expected:
        return {"document_error": f"The readable {label} has no verifiable local source pointer."}
    phase_dir = project_dir / "branches" / ref["branch"] / "phases" / ref["phase"].lower()
    run_id = _run_for_generation(project_dir, phase_dir, ref["family"], ref)
    run_dir = project_dir / "runs" / (run_id or "missing")
    run = read_json(run_dir / "run.json") or {}
    if run.get("state") != "published" or run.get("branch_id") != ref["branch"] or run.get("phase") != ref["phase"]:
        return {"document_error": f"The readable {label} cannot be linked to its published run."}
    candidates = ((stage, root) for stage in sorted((run_dir / "outputs").glob("*"))
                  for root in [stage, *sorted((stage / "working").glob("*"))])
    for stage, source_root in candidates:
        target = (source_root / relative).resolve()
        if not target.is_relative_to(stage.resolve()) or not target.is_file() or sha256_file(target) != expected:
            continue
        query = urlencode({"path": target.relative_to(stage.resolve()).as_posix(), "sha256": expected})
        url = f"/api/v1/projects/{quote(project_dir.name)}/runs/{quote(run_id)}/outputs/{quote(stage.name)}/artifact?{query}"
        suffix = target.suffix.lower()
        result = {"primary_artifact_url": url, "primary_source_verified": True,
                  "primary_artifact_media_type": file_media(target),
                  "primary_artifact_kind": "tex_source" if suffix == ".tex" else "pdf" if suffix == ".pdf" else "markdown" if suffix == ".md" else "source"}
        if analyst_account and suffix == ".json":
            from .table_exhibits import MAX_SOURCE_BYTES
            if target.stat().st_size > MAX_SOURCE_BYTES:
                result["document_error"] = "The readable Analyst account exceeds the source preview limit. Open the original account to read it in full."
            else:
                try:
                    content = json.loads(target.read_text(encoding="utf-8"))
                    if not isinstance(content, dict):
                        raise ValueError("The account is not a JSON object.")
                    result.update(primary_artifact_kind="json", primary_content=content)
                except (OSError, UnicodeError, ValueError):
                    result["document_error"] = "The readable Analyst account could not be decoded as a JSON object."
        elif suffix in (".md", ".txt", ".tex"):
            try:
                text = target.read_text(encoding="utf-8")
                if suffix == ".tex":
                    result["source_text"] = text
                else:
                    result["body_md"] = text
                    result["body"] = text
            except (OSError, UnicodeError):
                result["document_error"] = f"The readable {label} could not be decoded as text."
        return result
    return {"document_error": f"The readable {label} is missing or its bytes no longer match the published digest."}


def _report_material_projection(project_dir: Path, ref: dict, pointer: dict, basis: dict, roots: dict, report_document=None) -> dict:
    """Link required report bytes through their existing exact retained source."""
    from .research_sources import artifact_link, authored_pointer, frozen_artifact
    from .technical_reports import resolve_report_artifact
    action = artifact_link(project_dir, ref, pointer)
    if not action.get("source_verified"):
        run_id = ref.get("run_id")
        run = read_json(project_dir / "runs" / (run_id or "missing") / "run.json") or {}
        if (run.get("state") == "published" and run.get("branch_id") == ref.get("branch")
                and run.get("phase") == ref.get("phase")):
            try:
                digest = pointer.get("sha256") or pointer.get("artifact_sha256")
                resolved = resolve_report_artifact(pointer, basis, roots=list(roots.values()))
                # Frozen inputs deduplicate identical bytes across authored aliases.
                # Resolve the unique retained file by digest, then require the
                # same path selected by the report's exact source resolver.
                retained = frozen_artifact(project_dir, run_id, digest)
                if resolved == retained:
                    query = urlencode({"sha256": digest})
                    action = {"artifact_url": f"/api/v1/projects/{quote(project_dir.name)}/runs/{quote(run_id)}/inputs/artifact?{query}",
                              "source_verified": True, "source_kind": "retained_input", "media_type": file_media(retained)}
            except (ArtifactError, OSError, ValueError):
                pass
    notation = {}
    if report_document is not None:
        from .technical_reports import report_material_notation_source
        notation = report_material_notation_source(project_dir, report_document, pointer, basis) or {}
    return {**authored_pointer(pointer), **action, **notation}


def _document_projection(project_dir: Path, document, meta: dict) -> dict:
    """Use the same exact paper and source reader for current and saved drafts."""
    kind = meta["family"]
    body = (_authored_markdown(document) if kind in {"analyst_audit", "outside_review", "theory_audit", "empirical_audit",
            "review_issues", "review_issue_ledger", "limitations_record"} else _document_body(document))
    if kind in {"manuscript", "manuscript_candidate", "technical_report", "technical_report_candidate"}:
        body = _authored_markdown(document) or body
    result = {**meta, "title": kind.replace("_", " ").capitalize(), "kind": kind,
              "body_md": body, "body": body, "structured": document,
              "method_identity": document.get("method_identity") if isinstance(document, dict) else None,
              **_primary_document(project_dir, meta["generation_ref"], document)}
    if isinstance(document, dict) and isinstance(document.get("notation_snapshot"), dict):
        result.update(notation_snapshot=deepcopy(document["notation_snapshot"]),
                      notation_source_ref=deepcopy(meta["generation_ref"]))
    if meta.get("phase") == "P3" and isinstance(document, dict):
        from .research_sources import scientific_account_sources
        result["inline_sources"] = scientific_account_sources(project_dir, document, meta, result["body_md"])
    if kind in {"manuscript", "manuscript_candidate", "technical_report", "technical_report_candidate"} and isinstance(document, dict):
        from .research_sources import artifact_link, authored_pointer
        ref = meta["generation_ref"]
        phase_dir = project_dir / "branches" / ref["branch"] / "phases" / ref["phase"].lower()
        exact = {**ref, "run_id": _run_for_generation(project_dir, phase_dir, ref["family"], ref)}
        result["supplementary_artifacts"] = [
            {**authored_pointer(pointer), **artifact_link(project_dir, exact, pointer)}
            for pointer in document.get("supplementary_artifacts", []) if isinstance(pointer, dict)]
        if kind in {"technical_report", "technical_report_candidate"}:
            from .technical_reports import (derive_report_completion, exact_report_review_status, report_required_artifacts,
                                            completed_report_review_packets, report_context_basis, report_projection_basis)
            run_dir = project_dir / "runs" / (exact.get("run_id") or "missing")
            basis = report_projection_basis(report_context_basis(read_json(run_dir / "basis.json") or {}, document))
            roots = {str(folder): folder for stage in (run_dir / "outputs").glob("*")
                     for folder in [stage, *(stage / "working").glob("*")] if folder.is_dir()}
            result.update(title=document.get("title") or "Technical report", report_generation_id=ref.get("generation_id"),
                          completion=derive_report_completion(document, basis, artifact_roots=roots),
                          review_status="not_independently_reviewed", portable_artifact_url=meta.get("source_url", "") + "?view=portable",
                          problem_context_ref=document.get("problem_context_ref"))
            try:
                result["report_materials"] = [_report_material_projection(project_dir, exact, pointer, basis, roots, document)
                                              for pointer in report_required_artifacts(document, basis)]
            except (ArtifactError, OSError, ValueError):
                result["report_materials_error"] = "An exact report source or exhibit is unavailable."
            result["review_status"] = exact_report_review_status(document, ref, completed_report_review_packets(project_dir))
    if isinstance(document, dict) and meta.get("generation_ref", {}).get("run_id"):
        from .problem_context import context_change_notices, load_problem_context
        run_dir = project_dir / "runs" / meta["generation_ref"]["run_id"]
        basis = read_json(run_dir / "basis.json") or {}
        try:
            if isinstance(basis.get("problem_context"), dict):
                frozen_context = basis["problem_context"]
                if kind in {"technical_report", "technical_report_candidate"}:
                    items = {item["item_id"]: item for item in frozen_context.get("items", [])}
                    items.update({item["item_id"]: item for item in document.get("authorized_context_items", [])})
                    frozen_context = {**frozen_context, "items": list(items.values())}
                result["context_change_notices"] = context_change_notices(frozen_context, load_problem_context(project_dir), document.get("context_dependencies"))
        except (OSError, ValueError, TypeError):
            pass
    return result


def scientific_document_view(project_dir: Path, branch: str, phase: str, family: str,
                             generation_id: str) -> dict | None:
    """Read a named committed generation without substituting the current paper."""
    from .browse import _check_ident
    _check_ident(branch, phase, family, generation_id)
    phase = phase.upper()
    phase_dir = project_dir / "branches" / branch / "phases" / phase.lower()
    for package in committed_packages(phase_dir):
        pointer = package.get("records", {}).get(family)
        if pointer and pointer.get("generation_id") == generation_id:
            document = read_generation(phase_dir, family, pointer)
            meta = _record_meta(project_dir, branch, phase, family, pointer)
            return _document_projection(project_dir, document, meta)
    return None


def _revision_changes(project_dir: Path, ref: dict, theory: dict) -> list[dict]:
    """Compare scientific components to the exact previous theory used by this run."""
    run_dir = project_dir / "runs" / (ref.get("run_id") or "missing")
    basis = read_json(run_dir / "basis.json") or {}
    previous = next((r for family in ("theory_record", "complete_theory", "theory_candidate")
                     for r in basis.get("records", []) if r.get("branch") == ref["branch"]
                     and r.get("phase") == "P3" and r.get("family") == family), None)
    if not previous:
        return []
    try:
        old = read_generation(project_dir / "branches" / ref["branch"] / "phases" / "p3", previous["family"], previous)
    except ArtifactError:
        return []
    def components(doc):
        return {item.get("statement_id") or item.get("assumption_id"): item
                for name in ("statements", "assumptions") for item in doc.get(name, []) if isinstance(item, dict)}
    before, after = components(old), components(theory)
    changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
    all_components = {**before, **after}
    def downstream(key):
        found = {key}
        while True:
            added = {sid for sid, item in all_components.items()
                     if found.intersection(item.get("depends_on_statement_ids", []) + item.get("assumption_ids", []))}
            if added.issubset(found):
                return sorted(found - {key})
            found.update(added)
    account = theory.get("revision_account") or {}
    reason = account if isinstance(account, str) else account.get("change_summary", account.get("summary", "")) if isinstance(account, dict) else ""
    return [{"statement_id": key, "before": before.get(key), "after": after.get(key),
             "reason": reason, "affected": downstream(key)} for key in sorted(changed) if key]


def _theory_assessment_projection(project_dir: Path, records: dict, theory: dict, meta: dict,
                                  display: dict) -> tuple[dict, list]:
    """Attribute integration within one exact publication, without rewriting it."""
    ref = meta["generation_ref"]
    identity = theory.get("method_identity")

    def same_publication(entry):
        if not entry or not isinstance(entry[0], dict) or not identity:
            return False
        document, source = entry
        other = source.get("generation_ref", {})
        return (document.get("method_identity") == identity
                and all(ref.get(key) and ref[key] == other.get(key)
                        for key in ("branch", "phase", "run_id", "package_id")))

    def entry_ref(source, pointer, identifier):
        return {**source["generation_ref"], "entry_pointer": pointer, "object_id": identifier}

    candidate = records.get("theory_candidate")
    original = {}
    if same_publication(candidate):
        for family, key in (("statements", "statement_id"), ("assumptions", "assumption_id")):
            for index, item in enumerate(candidate[0].get(family, [])):
                if isinstance(item, dict) and item.get(key):
                    original[item[key]] = (item, entry_ref(candidate[1], f"/{family}/{index}", item[key]))
    decision = next((records[name] for name in ("phase_decision", "decision")
                     if name in records and same_publication(records[name])), None)
    changes = {}
    if decision:
        for index, change in enumerate(decision[0].get("assessment_changes", [])):
            if isinstance(change, dict) and change.get("component_id"):
                changes.setdefault(change["component_id"], []).append((change, index))

    issues = {}
    for name, field in (("analyst_audit", "issues"), ("analyst_handoff", "unresolved_issues")):
        entry = records.get(name)
        if not same_publication(entry):
            continue
        for index, issue in enumerate(entry[0].get(field, [])):
            if isinstance(issue, dict) and issue.get("issue_id"):
                issues.setdefault(issue["issue_id"], []).append(
                    (issue, entry_ref(entry[1], f"/{field}/{index}", issue["issue_id"])))

    def unique_issue(identifier):
        entries = issues.get(identifier, [])
        return entries[0] if entries and all(entry[0] == entries[0][0] for entry in entries) else None

    projected = {}
    for family, key in (("statements", "statement_id"), ("assumptions", "assumption_id")):
        for component in theory.get(family, []):
            if not isinstance(component, dict) or not component.get(key):
                continue
            identifier = component[key]
            previous = original.get(identifier)
            authored = changes.get(identifier, [])
            if previous is None:
                if authored:
                    projected[identifier] = {"assessment_source_error": "The original theorist account is unavailable for this assessment."}
                continue
            before, original_ref = previous
            changed = any(before.get(field) != component.get(field) for field in ("status", "justification"))
            if not changed:
                continue
            account = theory_statement_projection(project_dir, original_ref, before)
            original_account = {"status": before.get("status"), "generation_ref": original_ref}
            if "justification" in account:
                original_account["justification"] = account["justification"]
            if display.get(identifier, {}).get("proof_status"):
                original_account["proof_status"] = display[identifier]["proof_status"]
            result = {"theorist_account": original_account,
                      "original_justification_retained": before.get("justification") == component.get("justification")}
            if len(authored) == 1:
                change, index = authored[0]
                origin, reason = change.get("origin"), change.get("reason")
                if origin in {"lead_concern", "analyst_issue"} and isinstance(reason, str) and reason.strip():
                    context = {"origin": origin, "reason": reason,
                               "generation_ref": entry_ref(decision[1], f"/assessment_changes/{index}", identifier)}
                    if origin == "analyst_issue":
                        issue = unique_issue(change.get("issue_id"))
                        if issue:
                            context["issue_ref"] = issue[1]
                        else:
                            context["source_error"] = "The original Analyst issue is unavailable or ambiguous."
                    result["assessment_context"] = context
            if "assessment_context" not in result:
                result["assessment_source_error"] = "This published assessment has no exact attributed change account."
            projected[identifier] = result

    dispositions = []
    if decision:
        for index, item in enumerate(decision[0].get("issue_dispositions", [])):
            if not isinstance(item, dict) or not item.get("issue_id"):
                continue
            result = {**item, "generation_ref": entry_ref(decision[1], f"/issue_dispositions/{index}", item["issue_id"])}
            issue = unique_issue(item["issue_id"])
            if issue:
                result.update(issue=deepcopy(issue[0]), issue_ref=issue[1])
            else:
                result["source_error"] = "The original Analyst issue is unavailable or ambiguous."
            dispositions.append(result)
    return projected, dispositions


def _account_projection(project_dir: Path, document: dict, meta: dict) -> dict:
    result = {**document, **meta}
    if meta.get("phase") == "P3":
        from .research_sources import scientific_account_sources
        result["inline_sources"] = scientific_account_sources(project_dir, document, meta)
    return result


def _decision_projection(project_dir: Path, document: dict, meta: dict) -> dict:
    outcome = document.get("scientific_outcome") or {}
    return {**_account_projection(project_dir, document, meta), "outcome": outcome.get("state", ""),
            "conclusion": document.get("current_conclusion") or outcome.get("conclusion", ""),
            "material_disagreement": document.get("material_disagreement", outcome.get("material_disagreement", []))}


def current_decisions_view(project_dir: Path) -> list[dict]:
    """Read exact current decisions without projecting unrelated scientific history."""
    decisions = []
    branches = project_dir / "branches"
    if not branches.is_dir():
        return decisions
    for branch_dir in sorted(branches.iterdir()):
        if not branch_dir.is_dir():
            continue
        for phase_dir in sorted((branch_dir / "phases").glob("p[1-5]")):
            try:
                pointers = current_records(phase_dir)
            except ArtifactError:
                continue
            for family, pointer in pointers.items():
                if family.split(".", 1)[-1] not in ("decision", "phase_decision"):
                    continue
                try:
                    document = read_generation(phase_dir, family, pointer)
                except ArtifactError:
                    continue
                if not isinstance(document, dict):
                    continue
                ref = source_ref(branch_dir.name, phase_dir.name.upper(), family, pointer)
                meta = {"branch": branch_dir.name, "phase": phase_dir.name.upper(), "family": family,
                        "generation_ref": ref, "source_url": record_url(project_dir.name, ref),
                        "published_at": pointer.get("published_at", "")}
                decisions.append(_decision_projection(project_dir, document, meta))
    return decisions


def _attach_notation_views(result, loaded):
    """Link projections only to their own package's retained Lead account."""
    from .notation import LEAD_FAMILIES
    owners = {}
    for (_, phase), records in loaded.items():
        for family in LEAD_FAMILIES.get(phase, ()):
            record = records.get(family)
            if record is None:
                continue
            document, meta = record
            if not isinstance(document, dict) or not isinstance(document.get("notation_snapshot"), dict):
                continue
            ref = meta["generation_ref"]
            key = (ref["branch"], ref["phase"], ref.get("package_id"), ref.get("run_id"))
            if key[2] and key[3]:
                owners.setdefault(key, (ref, document["notation_snapshot"]))
    for values in result.values():
        if not isinstance(values, list):
            continue
        for row in values:
            if not isinstance(row, dict):
                continue
            ref = row.get("generation_ref") or {}
            owner = owners.get((ref.get("branch"), ref.get("phase"), ref.get("package_id"), ref.get("run_id")))
            if owner is None:
                continue
            source, pointer = owner
            row["notation_source_ref"] = deepcopy(source)
            row["notation_snapshot"] = deepcopy(pointer)


def artifacts_view(project_dir: Path, branch: str | None = None, *, _p4_records: dict | None = None,
                   _p4_metadata: dict | None = None) -> dict:
    result = {key: [] for key in ("cards", "summaries", "scores", "exhibits", "diagnostics", "claim_maps",
                                   "falsification_logs", "decisions", "glossaries", "documents", "protocols",
                                   "case_manifests", "load_errors", "evidence_status", "prior_evaluations", "questions",
                                   "literature_libraries", "literature_coverage", "literature_syntheses",
                                   "research_bases", "literature_collections", "method_proposals", "method_reviews", "catalog_assessments",
                                   "publication_history", "empirical_summaries", "issues", "manuscript_review_context",
                                   "implementations", "claim_traceability", "data_profiles")}
    loaded = {}
    branches = project_dir / "branches"
    if not branches.is_dir():
        return result
    for branch_dir in sorted(branches.iterdir()):
        if not branch_dir.is_dir() or (branch is not None and branch_dir.name != branch):
            continue
        for phase_dir in sorted((branch_dir / "phases").glob("p[1-5]")):
            phase = phase_dir.name.upper()
            if _p4_records is not None and phase != "P4":
                continue
            try:
                pointers = _p4_records if _p4_records is not None else current_records(phase_dir)
            except ArtifactError as exc:
                result["load_errors"].append({"branch": branch_dir.name, "phase": phase, "message": str(exc)})
                continue
            phase_records = loaded.setdefault((branch_dir.name, phase), {})
            for family, pointer in pointers.items():
                ref = source_ref(branch_dir.name, phase, family, pointer)
                meta = {"branch": branch_dir.name, "phase": phase, "family": family, "generation_ref": ref,
                        "source_url": record_url(project_dir.name, ref), "published_at": pointer.get("published_at", "")}
                try:
                    doc = read_generation(phase_dir, family, pointer)
                except ArtifactError as exc:
                    result["load_errors"].append({**meta, "message": str(exc)})
                    continue
                suffix = family.split(".", 1)[-1]
                phase_records[suffix] = (doc, meta)
                if phase == "P1" and suffix == "empirical_literature" and isinstance(doc, dict):
                    result["data_profiles"].extend({**profile, **meta, "producer_role": "data_analyst"}
                                                   for profile in doc.get("data_profiles", []) if isinstance(profile, dict))
                if suffix.endswith(("paper_cards", "method_cards")) and isinstance(doc, list):
                    result["cards"].extend({**card, **meta, "kind": "paper" if suffix.endswith("paper_cards") else "method"}
                                           for card in doc if isinstance(card, dict))
                elif suffix in ("phase_summary", "revision_account") and isinstance(doc, dict):
                    result["summaries"].append(_account_projection(project_dir, doc, meta))
                elif suffix == "exhibits" and isinstance(doc, list):
                    for exhibit in doc:
                        if isinstance(exhibit, dict):
                            authored = {key: value for key, value in exhibit.items() if key not in {
                                "artifact_url", "source_verified", "source_error", "table", "data_sources", "data_source_status"}}
                            result["exhibits"].append({**authored, **meta, **exhibit_source(project_dir, ref, exhibit)})
                elif suffix in ("diagnostics", "protocol", "case_manifest", "falsification_log") and isinstance(doc, dict):
                    key = {"protocol": "protocols", "case_manifest": "case_manifests", "falsification_log": "falsification_logs"}.get(suffix, suffix)
                    result[key].append({**doc, **meta})
                    if suffix == "protocol" and isinstance(doc.get("cases"), list):
                        result["case_manifests"].append({"cases": effective_protocol(doc)["cases"], **meta})
                elif suffix in ("decision", "phase_decision") and isinstance(doc, dict):
                    result["decisions"].append(_decision_projection(project_dir, doc, meta))
                    result["scores"].extend({**score, **meta} for score in doc.get("method_scores", []) if isinstance(score, dict))
    # Derive the graph from the complete theory, with the candidate as an explicit legacy fallback.
    status_catalog: dict | None = None
    for (branch_name, phase), records in loaded.items():
        if phase in {"P1", "P2"}:
            _direct_phase_projection(project_dir, branch_name, phase, result)
        if phase == "P1" and branch_name == "trunk":
            _literature_projection(project_dir, records, result)
            for names, target, kind in ((('synthesis_compact',), "literature_syntheses", "compact"),
                                        (('literature_synthesis', 'synthesis_candidate'), "literature_syntheses", "full"),
                                        (('literature_coverage', 'coverage_candidate'), "literature_coverage", "coverage")):
                entry = next((records[name] for name in names if name in records), None)
                if entry and isinstance(entry[0], dict):
                    document, meta = entry
                    body = _authored_markdown(document)
                    result[target].append({**document, **meta, "kind": kind, "body_md": body,
                                           "structured": document, **_primary_document(project_dir, meta["generation_ref"], document)})
        if phase == "P4":
            implementation = records.get("implementation_record")
            if implementation and isinstance(implementation[0], dict):
                audit = records.get("theory_audit")
                if not audit or not _same_evaluation(implementation[1], audit[1]):
                    audit = None
                account = implementation_projection(project_dir, *implementation, audit=audit)
                evaluation = next((records[key] for key in ("protocol", "empirical_synthesis", "empirical_synthesis_candidate", "diagnostics") if key in records), None)
                if evaluation and not _same_evaluation(implementation[1], evaluation[1]):
                    account["evaluation_source_error"] = "This implementation account belongs to a different publication from the displayed evaluation."
                result["implementations"].append(account)
            entry = next((records[key] for key in ("protocol", "empirical_synthesis", "empirical_synthesis_candidate", "diagnostics") if key in records), None)
            if entry:
                doc, meta = entry
                questions = protocol_questions(doc, meta["generation_ref"]) if "protocol" in records else []
                status, questions = evaluation_theory_context(project_dir, branch_name, meta["generation_ref"], questions)
                result["evidence_status"].append({**meta, **status})
                analyst, analyst_meta = records.get("analyst_synthesis", ({}, {}))
                lead, lead_meta = next((records[key] for key in ("empirical_synthesis", "empirical_synthesis_candidate")
                                       if key in records), ({}, {}))
                answers = _question_records(analyst, "question_results") if _same_evaluation(meta, analyst_meta) else {}
                reviews = _question_records(lead, "question_reviews") if _same_evaluation(meta, lead_meta) else {}
                for question in questions:
                    answer = answers.get(question["question_id"])
                    if answer:
                        question["result"] = {**answer, "generation_ref": analyst_meta.get("generation_ref")}
                        if isinstance(_primary_document_pointer(analyst), dict):
                            question["result"]["has_full_analyst_account"] = True
                        question.update(conclusion=answer.get("answer_markdown", ""), status=answer.get("outcome"),
                                        category=answer.get("category"), title=answer.get("title") or question["title"])
                        for key in ("test_ids", "case_ids", "metric_ids", "exhibit_ids", "plan_revision_ids"):
                            if isinstance(answer.get(key), list):
                                question[key] = answer[key]
                    if question["question_id"] in reviews:
                        question["review"] = {**reviews[question["question_id"]], "generation_ref": lead_meta.get("generation_ref")}
                    observations, observation_meta = records.get("metrics_long", ([], {}))
                    if isinstance(observations, list) and _same_evaluation(meta, observation_meta):
                        groups = {}
                        for row in observations:
                            if (not isinstance(row, dict) or row.get("eligibility") != "invalidated"
                                    or row.get("case_id") not in question.get("case_ids", [])):
                                continue
                            key = (row.get("case_id"), row.get("attempt_id"), row.get("plan_revision_id"), row.get("invalidation_reason"))
                            if key not in groups:
                                groups[key] = {field: row.get(field) for field in ("case_id", "attempt_id", "plan_revision_id", "invalidation_reason")}
                                groups[key].update(count=0, generation_ref=observation_meta["generation_ref"], source_url=observation_meta["source_url"])
                            groups[key]["count"] += 1
                        question["excluded_observations"] = list(groups.values())
                if isinstance(lead, dict) and isinstance(lead.get("decision_summary"), dict) and _same_evaluation(meta, lead_meta):
                    from .research_sources import empirical_run_sources
                    summary = {**lead, **lead_meta}
                    summary["run_sources"] = empirical_run_sources(project_dir, lead, lead_meta, records)
                    evaluated_method = evaluated_method_projection(project_dir, lead, lead_meta["generation_ref"], _p4_metadata)
                    if evaluated_method:
                        summary["evaluated_method"] = evaluated_method
                    if _same_evaluation(meta, analyst_meta) and isinstance(analyst.get("actual_data_application"), dict):
                        summary["actual_data_application"] = analyst["actual_data_application"]
                    result["empirical_summaries"].append(summary)
                result["questions"].extend({**question, **meta} for question in questions)
        if phase == "P5" and "claim_traceability" in records:
            trace, trace_meta = records["claim_traceability"]
            manuscript = next((records[key] for key in ("technical_report", "technical_report_candidate", "manuscript", "manuscript_candidate") if key in records), None)
            if manuscript and not _same_evaluation(trace_meta, manuscript[1]):
                manuscript = None
            if isinstance(trace, list):
                result["claim_traceability"].append(traceability_projection(project_dir, trace, trace_meta, manuscript))
        if phase == "P3":
            theory_entry = next((records[key] for key in ("theory_record", "complete_theory", "theory_candidate") if key in records), None)
            map_doc, map_meta = records.get("claim_map", ({}, {}))
            if theory_entry and isinstance(theory_entry[0], dict) and isinstance(theory_entry[0].get("statements"), list):
                theory, meta = theory_entry
                if not _same_evaluation(meta, map_meta):
                    map_doc, map_meta = {}, {}
                display = {claim.get("statement_id"): claim for claim in map_doc.get("claims", []) if isinstance(claim, dict)}
                assessments, dispositions = _theory_assessment_projection(project_dir, records, theory, meta, display)
                claims, glossary = [], {}
                novelty_ids = list(dict.fromkeys(identifier for item in [*display.values(), *theory["statements"]]
                                   if isinstance(item, dict) for identifier in item.get("novelty_refs", [])))
                novelty_links = literature_reference_links(project_dir, map_meta.get("generation_ref", meta["generation_ref"]), novelty_ids)
                for statement in theory["statements"]:
                    if not isinstance(statement, dict) or not statement.get("statement_id"):
                        continue
                    sid = statement["statement_id"]
                    projected = {**theory_statement_projection(project_dir, meta["generation_ref"], statement),
                                 **assessments.get(sid, {})}
                    decoration = {key: value for key, value in display.get(sid, {}).items()
                                  if key not in {"assessment_context", "theorist_account", "original_justification_retained", "assessment_source_error"}}
                    item = {**decoration, **projected}
                    item["depends_on"] = statement.get("depends_on_statement_ids", []) + statement.get("assumption_ids", statement.get("depends_on_assumption_ids", []))
                    item.setdefault("proof_status", display.get(sid, {}).get("proof_status", "missing"))
                    item["novelty_links"] = [link for identifier in item.get("novelty_refs", []) for link in novelty_links if link["identifier"] == identifier]
                    claims.append(item)
                    glossary[sid] = {**projected, "text": statement.get("text", statement.get("statement", ""))}
                assumptions = [{**theory_statement_projection(project_dir, meta["generation_ref"], item),
                                **assessments.get(item.get("assumption_id"), {})}
                               for item in theory.get("assumptions", []) if isinstance(item, dict)]
                for item in assumptions:
                    glossary[item["assumption_id"]] = {**item, "statement_type": "assumption", "text": item.get("text", item.get("statement", ""))}
                result["claim_maps"].append({**map_doc, **meta, "claims": claims, "assumptions": assumptions,
                                              "theory_generation_ref": meta["generation_ref"], "authoritative": True,
                                              "issue_dispositions": dispositions,
                                              "revision_changes": _revision_changes(project_dir, meta["generation_ref"], theory),
                                              "revision_account": theory.get("revision_account", {})})
                result["glossaries"].append({**meta, "glossary": glossary})
            elif map_doc:
                legacy_claims = [item for item in map_doc.get("claims", []) if isinstance(item, dict)]
                novelty_ids = list(dict.fromkeys(identifier for item in legacy_claims for identifier in item.get("novelty_refs", [])))
                novelty_links = literature_reference_links(project_dir, map_meta["generation_ref"], novelty_ids)
                result["claim_maps"].append({**map_doc, **map_meta,
                                              "claims": [{**theory_statement_projection(project_dir, map_meta["generation_ref"], item), "novelty_links": [link for identifier in item.get("novelty_refs", []) for link in novelty_links if link["identifier"] == identifier]} for item in legacy_claims],
                                              "authoritative": False,
                                              "source_warning": "The complete theory source for this graph is unavailable."})
        seen = set()
        for key in ("theory_record", "complete_theory", "theory_candidate", "protocol", "empirical_synthesis",
                    "empirical_synthesis_candidate", "implementation_record", "technical_report", "technical_report_candidate", "manuscript", "manuscript_candidate",
                    "literature_synthesis", "method_catalog", "revision_account", "analyst_audit", "outside_review", "theory_audit",
                    "empirical_audit", "review_issues", "review_issue_ledger", "limitations_record", "claim_traceability"):
            if key not in records:
                continue
            if key == "theory_candidate" and any(name in records for name in ("theory_record", "complete_theory")):
                continue
            doc, meta = records[key]
            digest = meta["generation_ref"]["sha256"]
            if digest in seen:
                continue
            seen.add(digest)
            document_entry = _document_projection(project_dir, doc, meta)
            if phase == "P3" and key == "analyst_audit":
                role = producing_role(project_dir, meta["generation_ref"])
                document_entry.update(producer_role=role,
                                      title="Independent audit by Data Analyst" if role == "data_analyst" else "Analyst audit")
            if phase == "P5" and key in {"outside_review", "theory_audit", "empirical_audit"}:
                packet = {}
                packet_dir = project_dir / "runs" / (meta["generation_ref"].get("run_id") or "missing") / "review-packet"
                if (packet_dir / "instructions.md").is_file():
                    from .p5_review_packet import read_review_packet
                    try:
                        packet = read_review_packet(packet_dir)
                        instruction = packet["instructions"]
                        document_entry["review_focus"] = Path(instruction["path"]).read_text(encoding="utf-8")
                        document_entry["review_focus_url"] = (
                            f"/api/v1/projects/{quote(project_dir.name)}/runs/"
                            f"{quote(meta['generation_ref']['run_id'])}/review-packet/instructions?"
                            + urlencode({"sha256": instruction["content_sha256"]}))
                    except (ArtifactError, OSError):
                        document_entry["review_focus_error"] = "The original review focus could not be verified."
                basis = read_json(project_dir / "runs" / (meta["generation_ref"].get("run_id") or "missing") / "basis.json") or {}
                from .technical_reports import REPORT_FAMILIES
                packet_families = set(REPORT_FAMILIES) if packet.get("packet_version") == "2.0.0" else {"manuscript", "manuscript_candidate"}
                targets = [pointer for pointer in basis.get("records", []) if pointer.get("phase") == "P5"
                           and pointer.get("branch") == branch_name and pointer.get("family") in packet_families]
                if packet.get("packet_version") == "2.0.0":
                    reviewed = packet.get("target") or {}
                    targets = [pointer for pointer in targets if all(pointer.get(field) == reviewed.get(field)
                               for field in ("family", "generation_id", "content_sha256"))]
                if len(targets) == 1:
                    pointer = targets[0]
                    try:
                        read_generation(project_dir / "branches" / branch_name / "phases" / "p5", pointer["family"], pointer)
                        exact = source_ref(branch_name, "P5", pointer["family"], pointer)
                        document_entry.update(reviewed_source_url=record_url(project_dir.name, exact))
                        document_entry["reviewed_report_ref" if pointer["family"] in REPORT_FAMILIES else "reviewed_manuscript_ref"] = exact
                    except ArtifactError:
                        document_entry["review_document_error"] = "The exact manuscript assessed by this review is unavailable."
                else:
                    document_entry["review_document_error"] = "The manuscript assessed by this review was not recorded unambiguously."
            if branch_name != "trunk" and phase in ("P3", "P4", "P5"):
                from .methods import _catalog_methods, output_method_status
                recorded = document_entry["method_identity"]
                if recorded is None:
                    if _p4_records is not None:
                        recorded = ((_p4_metadata or {}).get("method") or {}).get("identity")
                    else:
                        package = read_json(project_dir / "branches" / branch_name / "phases" / phase.lower()
                                            / "current-package.json") or {}
                        recorded = ((package.get("metadata") or {}).get("method") or {}).get("identity")
                if status_catalog is None:
                    status_catalog = _catalog_methods(project_dir)
                document_entry["method_status"] = output_method_status(project_dir, recorded, catalog=status_catalog)
            result["documents"].append(document_entry)
    _figure_data_sources(result["exhibits"])
    if _p4_records is None:
        for branch_name, phase in loaded:
            if phase != "P4":
                continue
            phase_dir = project_dir / "branches" / branch_name / "phases" / "p4"
            package = read_json(phase_dir / "current-package.json") or {}
            seen = set()
            while package:
                previous_id = package.get("previous_package_id")
                if not previous_id:
                    # First atomic publication can retain exact legacy evidence.
                    refs = package.get("metadata", {}).get("prior_evidence", [])
                    prior = {ref["family"]: ref for ref in refs if ref.get("branch") == branch_name and ref.get("phase") == "P4"}
                    if prior:
                        # The first atomic package's method belongs to its new
                        # evaluation, not the legacy generations it retained.
                        view = artifacts_view(project_dir, branch_name, _p4_records=prior)
                        result["prior_evaluations"].append({"branch": branch_name, "phase": "P4", "label": "Earlier recorded evaluation", "historical": True, "artifacts": view})
                    break
                if previous_id in seen:
                    result["load_errors"].append({"branch": branch_name, "phase": "P4", "message": "Evaluation history contains a circular package reference."})
                    break
                seen.add(previous_id)
                if not isinstance(previous_id, str) or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in previous_id):
                    break
                package = read_json(phase_dir / "packages" / (previous_id + ".json")) or {}
                if not package:
                    result["load_errors"].append({"branch": branch_name, "phase": "P4", "message": "An earlier committed evaluation package is unavailable."})
                    break
                prior = package.get("records", {})
                view = artifacts_view(project_dir, branch_name, _p4_records=prior, _p4_metadata=package.get("metadata"))
                run = read_json(project_dir / "runs" / (package.get("run_id") or "missing") / "run.json") or {}
                result["prior_evaluations"].append({"branch": branch_name, "phase": "P4", "package_id": previous_id,
                                                    "published_at": package.get("published_at"), "run_id": package.get("run_id"),
                                                    "mode": run.get("mode"), "historical": True, "artifacts": view})
    if _p4_records is None:
        from .phase_interactions import published_issues, manuscript_review_context
        result["issues"] = published_issues(project_dir, branch)
        _issue_citation_projection(project_dir, result["issues"])
        result["manuscript_review_context"] = manuscript_review_context(project_dir, loaded)
    _attach_notation_views(result, loaded)
    return result
