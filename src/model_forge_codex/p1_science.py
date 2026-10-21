"""Exact, attributed P1 corrections and references, without scientific inference."""
from __future__ import annotations

from copy import deepcopy
import json
import re

from .domain import Finding
from .records import ArtifactError


CONTENT_FIELDS = frozenset({"formulation_markdown", "explanation_markdown", "relevance_markdown",
                            "limitations_markdown", "evidence_locations", "topics", "reading_extent"})
_IDENTITY = ("role", "family", "run_id", "entry_id")
METADATA_FIELDS = frozenset({"authors", "title", "year", "venue"})


def reconciliation_enabled(documents=None, catalog=None):
    if catalog is not None:
        try:
            return tuple(int(part) for part in catalog.version.split(".")[:3]) >= (1, 18, 0)
        except (AttributeError, ValueError):
            return False
    documents = _documents(documents or {})
    return any(document.get("schema_version") == ("1.3.0" if family == "research_basis" else "1.2.0")
               for family, document in documents.items() if isinstance(document, dict)
               and family in {"research_basis", "lead_literature", "theory_literature", "empirical_literature"})


def required_p1_version(catalog, output_id):
    """New basis shape is required only for newly authored adopted P1 work."""
    try:
        six_cards = tuple(int(part) for part in catalog.version.split(".")[:3]) >= (1, 17, 0)
    except (AttributeError, ValueError):
        six_cards = False
    if reconciliation_enabled(catalog=catalog):
        return "1.3.0" if output_id == "p1.research_basis" else "1.2.0"
    return "1.2.0" if six_cards and output_id == "p1.research_basis" else "1.1.0"


def validate_overview(basis, effective, rows):
    """Check overview identities and exact citation bindings without judging fit."""
    if basis.get("schema_version") not in {"1.2.0", "1.3.0"}:
        return []
    landscape = basis.get("landscape") or {}
    findings, citations, seen = [], {}, set()
    records = {item.get(field): item for name, field in (
        ("frameworks", "framework_id"), ("variants", "variant_id"),
        ("relationships", "relationship_id"), ("algorithm_families", "algorithm_family_id"))
        for _, item in rows.get(name, [])}
    for index, binding in enumerate(landscape.get("citation_refs", [])):
        pointer = f"/landscape/citation_refs/{index}"
        try:
            source_id = binding.get("source_id")
            if not isinstance(source_id, str) or not source_id or source_id in citations:
                raise ArtifactError("Each citation source ID needs one distinct exact binding.")
            matched = _resolve(binding.get("entry_ref"), effective)
            if source_id != matched["entry"]["source"]["source_id"]:
                raise ArtifactError("The citation source ID differs from the source in its exact bound entry.")
            citations[source_id] = matched
        except (ArtifactError, AttributeError, KeyError, TypeError) as error:
            findings.append(_issue("invalid_citation_reference", str(error), pointer))
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, child in value.items():
                if key != "citation_refs":
                    yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)
    for value in strings(basis):
        for source_id in re.findall(r"\]\(#cite:([^\s)]+)\)", value):
            if source_id not in citations:
                findings.append(_issue("unbound_inline_citation", f"Inline citation {source_id} has no valid exact binding.", "/landscape/citation_refs"))
    for index, identity in enumerate(landscape.get("overview_item_ids", [])):
        item = records.get(identity)
        if item is None or identity in seen:
            findings.append(_issue("invalid_overview_item", "Overview selections must identify distinct declared landscape records.", f"/landscape/overview_item_ids/{index}"))
        elif item.get("project_relevance") not in {"direct", "conditional", "background"} or not str(item.get("relevance_reason_markdown", "")).strip():
            findings.append(_issue("missing_project_relevance", "Each selected object needs its authored relevance and qualifying explanation.", f"/landscape/overview_item_ids/{index}"))
        seen.add(identity)
    assumption_ids = set()
    for index, item in enumerate(landscape.get("common_assumptions", [])):
        pointer = f"/landscape/common_assumptions/{index}"
        if item.get("assumption_id") in assumption_ids:
            findings.append(_issue("duplicate_assumption_id", "Shared assumption IDs must be distinct.", pointer))
        assumption_ids.add(item.get("assumption_id"))
        if any(identity not in records for identity in item.get("landscape_item_ids", [])):
            findings.append(_issue("invalid_assumption_item", "The assumption names an unavailable landscape item.", pointer + "/landscape_item_ids"))
        if any(identity not in citations for identity in item.get("citation_ids", [])):
            findings.append(_issue("invalid_assumption_citation", "The assumption names an unavailable exact citation.", pointer + "/citation_ids"))
    return findings


def _documents(documents):
    return {key.removeprefix("p1."): value for key, value in documents.items()}


def entry_reference(assessment: dict) -> dict:
    return {**{key: assessment[key] for key in _IDENTITY[:3]},
            "entry_id": assessment["entry"]["entry_id"], "entry_sha256": assessment["entry_sha256"]}


def validate_current_papers(documents, previous_library=None, *, run_id=None) -> list[Finding]:
    """One current assessment per member and canonical paper, with exact owners."""
    from .direct_artifacts import LITERATURE_ROLES, direct_literature_sources
    from .literature import _tokens

    documents = _documents(documents)
    # Identity-only union, independent of bibliographic merge success.
    parents, tokens, identifiers = {}, {}, {}
    def root(identity):
        parents.setdefault(identity, identity)
        if parents[identity] != identity:
            parents[identity] = root(parents[identity])
        return parents[identity]
    sources = list((previous_library or {}).get("sources", []))
    try:
        sources += direct_literature_sources(documents)
    except (ArtifactError, KeyError, TypeError):
        sources += [entry.get("source", {}) for document in documents.values() if isinstance(document, dict)
                    for entry in document.get("papers", []) if isinstance(entry, dict)]
    for source in sources:
        try:
            identity = source["source_id"]
            identities = source.get("source_ids", [identity])
            root(identity)
            for alias in identities:
                parents[root(alias)] = root(identity)
            source_tokens = _tokens(source)
            identifiers.setdefault(identity, set()).update(source_tokens)
            for token in source_tokens:
                for other in tokens.get(token, []):
                    left = set().union(*(value for key, value in identifiers.items() if root(key) == root(identity)))
                    right = set().union(*(value for key, value in identifiers.items() if root(key) == root(other)))
                    incompatible = any((a := {value for value in left if value.startswith(kind + ":")})
                                       and (b := {value for value in right if value.startswith(kind + ":")}) and not a & b
                                       for kind in ("doi", "arxiv", "pmid", "isbn"))
                    if token.split(":", 1)[0] in {"doi", "arxiv", "pmid", "isbn"} or not incompatible:
                        parents[root(identity)] = root(other)
                tokens.setdefault(token, []).append(identity)
        except (ArtifactError, KeyError, TypeError):
            continue
    findings = []
    for family in LITERATURE_ROLES:
        groups = {}
        for index, entry in enumerate((documents.get(family) or {}).get("papers", [])):
            if not isinstance(entry, dict) or not isinstance(entry.get("entry_id"), str):
                continue  # The entry's structural validator reports its missing identity.
            source_id = (entry.get("source") or {}).get("source_id")
            if source_id in parents:
                groups.setdefault(root(source_id), []).append((index, entry["entry_id"]))
        for canonical, entries in groups.items():
            if len({entry_id for _, entry_id in entries}) < 2:
                continue  # Duplicate entry IDs already have their own schema/reference finding.
            labels = ", ".join(f"/papers/{index} ({entry_id})" for index, entry_id in entries)
            message = (f"These entries describe the same canonical paper {canonical}: {labels}. "
                       "Combine this member's account into one entry so all of its content remains available to the lead and later phases.")
            findings.extend(Finding("literature.duplicate_current_paper", message, "p1." + family, f"/papers/{index}")
                            for index, _ in entries)
    return findings


def _key(reference):
    return tuple(reference.get(key) for key in _IDENTITY) if isinstance(reference, dict) else None


def _plain(assessment):
    return {key: deepcopy(value) for key, value in assessment.items()
            if key not in {"assessment_history", "canonical_source_id"}}


def _issue(code, message, pointer):
    return Finding("literature." + code, message, "p1.research_basis", pointer)


def _before_this_run(assessment, corrections, run_id):
    """Replaying the same committed projection starts at its exact prior version."""
    revision = assessment.get("lead_revision") or {}
    history = assessment.get("assessment_history", [])
    if revision.get("run_id") == run_id and revision.get("correction") in corrections and history:
        return {**deepcopy(history[0]), **({"assessment_history": deepcopy(history[1:])} if len(history) > 1 else {})}
    return deepcopy(assessment)


def _base_entries(documents, previous_library, run_id, publication_sequence=None):
    from .direct_artifacts import LITERATURE_ROLES, direct_literature_sources
    from .literature import _digest, build_library

    documents = _documents(documents)
    modern = reconciliation_enabled(documents)
    if modern and validate_current_papers(documents, previous_library, run_id=run_id):
        raise ArtifactError("A member has multiple current entries for one paper; consolidate them before synthesis.")
    library = build_library(previous_library, direct_literature_sources(documents), run_id=run_id,
                            allow_metadata_conflicts=modern, normalize_authors=modern, strict_identifiers=modern)
    aliases = {alias: source["source_id"] for source in library["sources"] for alias in source["source_ids"]}
    recorded = [version for source in library["sources"] for current in source.get("assessments", [])
                for version in [current, *current.get("assessment_history", [])]]
    recorded.extend(source["landscape_disposition"] for source in library["sources"] if "landscape_disposition" in source)
    same_run = [item.get("publication_sequence", 0) for item in recorded if item.get("run_id") == run_id
                or (item.get("lead_revision") or {}).get("run_id") == run_id]
    sequence = publication_sequence or (max(same_run) if same_run else
                                        1 + max((item.get("publication_sequence", 0) for item in recorded), default=0))
    corrections = (documents.get("research_basis") or {}).get("entry_corrections", [])
    if not isinstance(corrections, list):
        corrections = []  # Shape findings belong to the authored correction list.
    current = {}
    for source in library["sources"]:
        for assessment in source.get("assessments", []):
            item = _before_this_run(assessment, corrections, run_id)
            current[(source["source_id"], item["role"])] = {**item, "canonical_source_id": source["source_id"]}
    for family, role in LITERATURE_ROLES.items():
        for index, entry in enumerate((documents.get(family) or {}).get("papers", [])):
            canonical = aliases[entry["source"]["source_id"]]
            item = {"role": role, "family": family, "run_id": run_id, "publication_sequence": sequence,
                    "entry_pointer": f"/papers/{index}", "entry": deepcopy(entry),
                    "source_sha256": _digest(entry["source"]), "entry_sha256": _digest(entry)}
            old = current.get((canonical, role))
            if old and _plain(old) == item:
                continue
            if old:
                item["assessment_history"] = [_plain(old), *deepcopy(old.get("assessment_history", []))]
            current[(canonical, role)] = {**item, "canonical_source_id": canonical}
    return list(current.values()), sequence


def _resolve(reference, entries, *, digest_required=True):
    from .direct_artifacts import LITERATURE_ROLES

    if (not isinstance(reference, dict) or any(not isinstance(reference.get(key), str) or not reference[key] for key in _IDENTITY)
            or LITERATURE_ROLES.get(reference.get("family")) != reference.get("role")):
        raise ArtifactError("The entry reference needs its exact original role, family, run, and entry ID.")
    matches = [entry for entry in entries if _key(entry_reference(entry)) == _key(reference)]
    if len(matches) != 1:
        raise ArtifactError("The target is not one unambiguous current entry in the supplied collections and frozen library; history is not eligible.")
    digest = reference.get("entry_sha256")
    if (digest_required or digest is not None) and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                                                   or digest != matches[0]["entry_sha256"]):
        permitted = json.dumps(entry_reference(matches[0]), sort_keys=True)
        raise ArtifactError(f"The entry_sha256 {digest!r} is stale or invalid. The exact permitted effective entry in "
                            f"the supplied collections and frozen library is {permitted}. Verify its saved content "
                            "before correcting the reference; earlier versions and similar identifiers are not substitutes.")
    return matches[0]


def _correction_findings(entries, basis, run_id, sequence, catalog=None):
    from .literature import _digest

    result, findings = deepcopy(entries), []
    seen_ids, seen_targets = set(), set()
    corrections = basis.get("entry_corrections", [])
    if not isinstance(corrections, list):
        return result, [_issue("invalid_entry_correction", "Entry corrections must be an array.", "/entry_corrections")]
    for index, correction in enumerate(corrections):
        pointer = f"/entry_corrections/{index}"
        try:
            if not isinstance(correction, dict):
                raise ArtifactError("An entry correction must be an object.")
            correction_id, target = correction.get("correction_id"), correction.get("target")
            if not isinstance(correction_id, str) or not correction_id or correction_id in seen_ids:
                raise ArtifactError("Each correction needs a distinct correction ID.")
            seen_ids.add(correction_id)
            old = _resolve(target, entries)
            key = _key(target)
            if key in seen_targets:
                raise ArtifactError("Use one correction per target entry, combining its field changes explicitly.")
            seen_targets.add(key)
            changes = correction.get("changes", {})
            metadata = correction.get("source_metadata", {})
            if (not isinstance(changes, dict) or set(changes) - CONTENT_FIELDS or
                    not isinstance(metadata, dict) or set(metadata) - METADATA_FIELDS or not (changes or metadata)):
                raise ArtifactError("Corrections may replace only paper content fields; entry and source identities are immutable.")
            if metadata and (basis.get("schema_version") != "1.3.0" or catalog is not None and not reconciliation_enabled(catalog=catalog)):
                raise ArtifactError("Source metadata correction requires the revised P1 catalog and basis 1.3.0.")
            for field, value in metadata.items():
                valid = (isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)
                         if field == "authors" else isinstance(value, int) and not isinstance(value, bool) and 1000 <= value <= 3000
                         if field == "year" else isinstance(value, str) and bool(value.strip()))
                if not valid:
                    raise ArtifactError(f"The corrected citation {field} is invalid.")
            for field, value in changes.items():
                if field in {"evidence_locations", "topics"}:
                    valid = isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)
                else:
                    valid = isinstance(value, str) and bool(value.strip())
                if not valid:
                    raise ArtifactError(f"The corrected {field} is not a valid paper field value.")
            if not isinstance(correction.get("reason_markdown"), str) or not correction["reason_markdown"].strip():
                raise ArtifactError("A correction must retain the lead's stated reason.")
            evidence = correction.get("evidence_locations")
            if not isinstance(evidence, list) or not evidence or not all(isinstance(value, str) and value.strip() for value in evidence):
                raise ArtifactError("A correction must identify its evidence locations.")
            paper = corrected_entry(old["entry"], correction)
            if catalog is not None:
                envelope = {"schema_version": "1.0.0", "title": "Corrected entry", "search_scope": "Retained source",
                            "coverage_limits": [], "papers": [paper]}
                errors = catalog.validate_output("p1." + old["family"], envelope)
                if errors:
                    findings.extend(_issue("invalid_corrected_entry", error.message,
                                           pointer + "/changes" + error.json_pointer.removeprefix("/papers/0")) for error in errors)
                    continue
            updated = {**_plain(old), "entry": paper, "entry_sha256": _digest(paper), "publication_sequence": sequence,
                       "source_sha256": _digest(paper["source"]),
                       "lead_revision": {"role": "research_lead", "family": "research_basis", "run_id": run_id,
                                         "entry_pointer": pointer, "correction": deepcopy(correction),
                                         "previous_entry_sha256": old["entry_sha256"], "entry_sha256": _digest(paper)},
                       "assessment_history": [_plain(old), *deepcopy(old.get("assessment_history", []))],
                       "canonical_source_id": old["canonical_source_id"]}
            position = next(i for i, item in enumerate(result) if _key(entry_reference(item)) == key)
            result[position] = updated
        except (ArtifactError, KeyError, TypeError) as exc:
            findings.append(_issue("invalid_entry_correction", str(exc), pointer))
    return result, findings


def corrected_entry(entry, correction):
    """Exact authored replacements; derived metadata checksum has an explicit scope."""
    from .literature import _digest
    paper = {**deepcopy(entry), **deepcopy(correction.get("changes", {}))}
    metadata = correction.get("source_metadata", {})
    if metadata:
        source = {**deepcopy(paper["source"]), **deepcopy(metadata)}
        source.pop("content_sha256", None)
        source["content_sha256_scope"] = "citation-record-excluding-content_sha256"
        source["content_sha256"] = _digest(source)
        paper["source"] = source
    return paper


def effective_literature_sources(documents, previous_library, *, run_id):
    from .direct_artifacts import direct_literature_sources
    if not reconciliation_enabled(documents):
        return direct_literature_sources(documents)
    entries = literature_entries(documents, previous_library, run_id=run_id)
    return [deepcopy(item["entry"]["source"]) for item in entries
            if item["run_id"] == run_id or (item.get("lead_revision") or {}).get("run_id") == run_id]


def reconciled_library(documents, previous_library, *, run_id):
    """Retain raw revisions, then publish only explicitly reconciled effective citations."""
    from .direct_artifacts import direct_literature_sources, apply_direct_literature
    from .literature import build_library, source_identity_conflicts, _digest, validate_library, retain_source_lead_revision
    documents = _documents(documents)
    if not reconciliation_enabled(documents):
        library = build_library(previous_library, direct_literature_sources(documents), run_id=run_id)
        return apply_direct_literature(library, documents, run_id=run_id)
    entries = literature_entries(documents, previous_library, run_id=run_id)
    if source_identity_conflicts([item["entry"]["source"] for item in entries], normalize_authors=True, strict_identifiers=True):
        raise ArtifactError("Effective citation metadata remains unresolved; author explicit source_metadata corrections before publication.")
    raw = build_library(previous_library, direct_literature_sources(documents), run_id=run_id,
                        allow_metadata_conflicts=True, normalize_authors=True, strict_identifiers=True)
    sources = effective_literature_sources(documents, previous_library, run_id=run_id)
    comparison = build_library(previous_library, sources, run_id=run_id, normalize_authors=True, strict_identifiers=True)
    library = build_library(raw, sources, run_id=run_id,
                            normalize_authors=True, strict_identifiers=True)
    library["changes"] = comparison["changes"]
    library = apply_direct_literature(library, documents, run_id=run_id)
    for item in entries:
        revision = item.get("lead_revision") or {}
        if revision.get("run_id") != run_id or not (revision.get("correction") or {}).get("source_metadata"):
            continue
        for source in library["sources"]:
            for retained in source["revisions"]:
                if retained["run_id"] == run_id and retained["document_sha256"] == _digest(item["entry"]["source"]):
                    retain_source_lead_revision(retained, revision)
    return validate_library(library)


def literature_entries(documents, previous_library, *, run_id, apply_corrections=True) -> list[dict]:
    """Current exact assessments for compact navigation, excluding superseded history."""
    documents = _documents(documents)
    entries, sequence = _base_entries(documents, previous_library, run_id)
    if apply_corrections:
        entries, findings = _correction_findings(entries, documents.get("research_basis") or {}, run_id, sequence)
        if findings:
            raise ArtifactError("; ".join(f"{finding.json_pointer}: {finding.message}" for finding in findings))
    return entries


def validate_lead_revision(version, versions) -> None:
    """A corrected retained entry must be exactly its recorded field replacement."""
    from .literature import _digest

    revision = version.get("lead_revision")
    if revision is None:
        return
    correction = revision.get("correction") if isinstance(revision, dict) else None
    target = correction.get("target") if isinstance(correction, dict) else None
    if (not isinstance(target, dict) or revision.get("role") != "research_lead"
            or revision.get("family") != "research_basis" or not revision.get("run_id")
            or not re.fullmatch(r"/entry_corrections/\d+", str(revision.get("entry_pointer")))
            or _key(target) != _key(entry_reference(version))
            or revision.get("previous_entry_sha256") != target.get("entry_sha256")
            or revision.get("entry_sha256") != version.get("entry_sha256")):
        raise ArtifactError("A lead revision has no exact correction target or producing research basis.")
    originals = [item for item in versions if item is not version and _key(entry_reference(item)) == _key(target)
                 and item.get("entry_sha256") == target.get("entry_sha256")]
    changes = correction.get("changes", {})
    metadata = correction.get("source_metadata", {})
    if (not originals or not isinstance(changes, dict) or set(changes) - CONTENT_FIELDS or
            not isinstance(metadata, dict) or set(metadata) - METADATA_FIELDS or not (changes or metadata)):
        raise ArtifactError("A lead revision has lost its original assessment or changes an identity field.")
    expected = corrected_entry(originals[0]["entry"], correction)
    if expected != version["entry"] or _digest(expected) != version["entry_sha256"]:
        raise ArtifactError("A corrected entry differs from the lead's exact recorded field changes.")


def validate_p1_science(documents, previous_library=None, *, run_id, catalog=None) -> list[Finding]:
    """Check exact references and authored replacements, never mathematical truth."""
    documents = _documents(documents)
    basis = documents.get("research_basis")
    if not isinstance(basis, dict):
        return []
    landscape = basis.get("landscape") or {}
    if not (any(key in basis for key in ("entry_corrections", "scientific_review"))
            or isinstance(landscape, dict) and any(key in landscape for key in ("frameworks", "variants", "relationships", "algorithm_families"))):
        return []
    try:
        original, sequence = _base_entries(documents, previous_library, run_id)
    except (ArtifactError, KeyError, TypeError) as exc:
        return [_issue("science_context_invalid", str(exc), "")]
    effective, findings = _correction_findings(original, basis, run_id, sequence, catalog)
    review = basis.get("scientific_review") or {}
    if not isinstance(review, dict) or not isinstance(review.get("findings", []), list):
        findings.append(_issue("invalid_review_reference", "Scientific review must contain a findings array.", "/scientific_review"))
        review = {}
    seen = set()
    corrected = {_key(entry_reference(item)) for item in effective if (item.get("lead_revision") or {}).get("run_id") == run_id}
    for index, finding in enumerate(review.get("findings", [])):
        pointer = f"/scientific_review/findings/{index}"
        try:
            if finding.get("finding_id") in seen:
                raise ArtifactError("Scientific review finding IDs must be unique.")
            seen.add(finding.get("finding_id"))
            _resolve(finding.get("target"), original)
            if finding.get("status") == "corrected" and _key(finding.get("target")) not in corrected:
                raise ArtifactError("A review marked corrected must identify an explicit entry correction.")
        except (ArtifactError, AttributeError, TypeError) as exc:
            findings.append(_issue("invalid_review_reference", str(exc), pointer))
    landscape = basis.get("landscape") or {}
    if not isinstance(landscape, dict):
        return [*findings, _issue("invalid_landscape", "The scientific landscape must be an object.", "/landscape")]
    kinds = {"frameworks": "framework_id", "variants": "variant_id", "relationships": "relationship_id",
             "algorithm_families": "algorithm_family_id"}
    ids = {}
    all_ids = set()
    rows = {}
    for name, field in kinds.items():
        ids[name] = set()
        rows[name] = []
        values = landscape.get(name, [])
        if not isinstance(values, list):
            findings.append(_issue("invalid_landscape", "Landscape items must be an array.", f"/landscape/{name}"))
            continue
        for index, item in enumerate(values):
            if not isinstance(item, dict) or not isinstance(item.get(field), str):
                findings.append(_issue("invalid_landscape", "Each landscape item needs its named identity.", f"/landscape/{name}/{index}"))
                continue
            rows[name].append((index, item))
            identity = item.get(field)
            if identity in all_ids:
                findings.append(_issue("duplicate_landscape_id", "Scientific landscape IDs must be unique.", f"/landscape/{name}/{index}/{field}"))
            ids[name].add(identity)
            all_ids.add(identity)
    nodes = ids["frameworks"] | ids["variants"] | ids["algorithm_families"]
    for name in kinds:
        for index, item in rows[name]:
            pointer = f"/landscape/{name}/{index}"
            references = item.get("entry_refs", [])
            if not isinstance(references, list):
                findings.append(_issue("invalid_support_reference", "Supporting entry references must be an array.", pointer + "/entry_refs"))
                references = []
            seen_refs = set()
            for ref_index, reference in enumerate(references):
                try:
                    target = _resolve(reference, effective, digest_required=False)
                    key = _key(entry_reference(target))
                    if key in seen_refs:
                        raise ArtifactError("Do not repeat the same supporting entry in one landscape item.")
                    seen_refs.add(key)
                except (ArtifactError, TypeError) as exc:
                    findings.append(_issue("invalid_support_reference", str(exc), pointer + f"/entry_refs/{ref_index}"))
            if item.get("support_status") in {"source_supported", "partially_supported"} and not references:
                findings.append(_issue("missing_support_reference", "A source-supported statement must link its source entries.", pointer + "/entry_refs"))
            if name == "variants" and (not isinstance(item.get("framework_id"), str) or item["framework_id"] not in ids["frameworks"]):
                findings.append(_issue("unknown_framework", "The variant must identify a declared framework.", pointer + "/framework_id"))
            if name == "algorithm_families":
                targets = item.get("framework_ids", [])
                if (not isinstance(targets, list) or not all(isinstance(target, str) for target in targets)
                        or len(targets) != len(set(targets)) or set(targets) - ids["frameworks"]):
                    findings.append(_issue("unknown_framework", "Algorithm families must name distinct declared frameworks.", pointer + "/framework_ids"))
            if name == "relationships" and (not all(isinstance(item.get(key), str) for key in ("from_id", "to_id"))
                                              or item["from_id"] not in nodes or item["to_id"] not in nodes or item["from_id"] == item["to_id"]):
                findings.append(_issue("invalid_relationship", "A relationship must connect two distinct declared landscape nodes.", pointer))
    findings.extend(validate_overview(basis, effective, rows))
    return findings
