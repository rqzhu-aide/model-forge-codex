"""Deterministic cumulative P1 sources, derived only from accepted records.

The library is a projection, not an agent-authored replacement for source
records. Every submitted revision remains intact inside the same immutable
phase package. Publication and authorization stay with the caller.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit, urlunsplit

from .records import ArtifactError, committed_packages, current_records, read_generation


class LiteratureError(ArtifactError):
    pass


def _json_key(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return hashlib.sha256(_json_key(value).encode("utf-8")).hexdigest()


def _unique(values: list) -> list:
    result, seen = [], set()
    for value in values:
        key = _json_key(value)
        if key not in seen:
            seen.add(key)
            result.append(deepcopy(value))
    return result


def canonical_identifier(identifier: dict) -> str:
    """Match locators, never infer identity from a similar title or author.

    DOI resolver URLs and arXiv PDF/abstract/version locators share identities.
    Other URLs retain path case and query strings: those may name different
    resources. We deliberately do not equate arbitrary HTTP and HTTPS URLs.
    """
    kind = str(identifier.get("kind", "")).strip().lower()
    value = str(identifier.get("value", "")).strip()
    if not kind or not value:
        raise LiteratureError("A literature identifier needs a kind and value")
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise LiteratureError("A literature identifier contains an invalid URL") from exc
    host = (parts.hostname or "").lower()
    if host in {"doi.org", "dx.doi.org", "www.doi.org"}:
        kind, value = "doi", unquote(parts.path.lstrip("/"))
    elif host in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"} and re.match(r"^/(abs|pdf)/", parts.path):
        kind, value = "arxiv", re.sub(r"^/(abs|pdf)/", "", parts.path)
    if kind == "doi":
        value = re.sub(r"^doi\s*:\s*", "", value, flags=re.I).strip().lower()
    elif kind == "arxiv":
        value = re.sub(r"^arxiv\s*:\s*", "", value, flags=re.I)
        value = re.sub(r"\.pdf$", "", value, flags=re.I)
        value = re.sub(r"v\d+$", "", value, flags=re.I).lower()
    elif kind in {"url", "repository"} and parts.scheme.lower() in {"http", "https"} and host:
        try:
            port = parts.port
        except ValueError as exc:
            raise LiteratureError("A literature URL contains an invalid port") from exc
        netloc = host if port in {None, 80 if parts.scheme.lower() == "http" else 443} else f"{host}:{port}"
        value = urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))
        kind = "url"
    elif kind in {"isbn", "pmid"}:
        value = re.sub(r"[\s-]", "", value).lower()
    return f"{kind}:{value}"


def _source(document: object) -> dict:
    if not isinstance(document, dict):
        raise LiteratureError("Literature source changes must contain source objects")
    for key in ("source_id", "record_id", "title", "source_type", "source_status"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            raise LiteratureError(f"A literature source is missing {key}")
    if document["source_status"] not in {"active", "corrected", "retracted", "withdrawn"}:
        raise LiteratureError(f"Unknown literature status for {document['source_id']}")
    if document["source_status"] != "active" and not document.get("status_reason"):
        raise LiteratureError(f"Source status needs an explanation: {document['source_id']}")
    for key in ("identifiers", "search_provenance", "authors"):
        if not isinstance(document.get(key), list) or not document[key]:
            raise LiteratureError(f"A literature source needs nonempty {key}")
    if not all(isinstance(item, dict) for item in document["identifiers"] + document["search_provenance"]):
        raise LiteratureError("Literature identity and search provenance entries must be objects")
    for identifier in document["identifiers"]:
        canonical_identifier(identifier)
    return deepcopy(document)


def _tokens(source: dict) -> set[str]:
    return {canonical_identifier(item) for item in source["identifiers"]}


def source_lead_revisions(revision):
    """A source document may be the exact result of several member corrections."""
    return revision.get("lead_revisions", [revision["lead_revision"]] if revision.get("lead_revision") else [])


def retain_source_lead_revision(revision, lead):
    origins = source_lead_revisions(revision)
    if lead not in origins:
        origins = [*origins, deepcopy(lead)]
    revision["lead_revision"] = deepcopy(origins[0])
    if len(origins) > 1:
        revision["lead_revisions"] = origins


def _author_key(value: str) -> str:
    # Comparison only: retain order, organizations, names and display bytes.
    value = " ".join(value.casefold().split())
    return re.sub(r"(?<!\w)([^\W\d_])\.(?:\s*)", r"\1 ", value).strip()


def _bibliographic_key(item: dict, *, normalize_authors=False) -> tuple:
    authors = [_author_key(value) for value in item.get("authors", [])] if normalize_authors else item.get("authors", [])
    return (_json_key(authors).casefold(), item.get("year"),
            " ".join(item["title"].casefold().split()))


def source_identity_conflicts(sources: list[dict], *, normalize_authors=False, strict_identifiers=False) -> list[dict]:
    """Locate all contradictory pairs without choosing which citation is true.

    Use the same identity and citation rules as the cumulative merge. Original
    list positions let the caller retain member ownership and JSON pointers.
    Invalid source shapes are left to ordinary schema/source validation.
    """
    prepared = []
    for index, source in enumerate(sources):
        try:
            source = _source(source)
            prepared.append((index, source, _tokens(source)))
        except LiteratureError:
            continue
    conflicts = []
    for position, (left_index, left, left_tokens) in enumerate(prepared):
        for right_index, right, right_tokens in prepared[position + 1:]:
            shared = left_tokens & right_tokens
            same_id = left["source_id"] == right["source_id"]
            if not shared and not same_id:
                continue
            reasons = []
            for kind in ("doi", "arxiv", "pmid", "isbn"):
                old = {token for token in left_tokens if token.startswith(kind + ":")}
                new = {token for token in right_tokens if token.startswith(kind + ":")}
                if old and new and not old & new and (strict_identifiers or not shared):
                    reasons.append(f"different {kind.upper()} identifiers")
            if left["source_status"] != right["source_status"]:
                reasons.append("conflicting source statuses")
            if _bibliographic_key(left, normalize_authors=normalize_authors) != _bibliographic_key(right, normalize_authors=normalize_authors):
                reasons.append("conflicting title, authors, or year")
            if reasons:
                conflicts.append({"left": left_index, "right": right_index,
                                  "shared_identifiers": sorted(shared),
                                  "shared_source_id": left["source_id"] if same_id else None,
                                  "reasons": reasons,
                                  "metadata_only": reasons == ["conflicting title, authors, or year"],
                                  "differing_fields": [field for field in ("authors", "title", "year", "source_status", "identifiers")
                                                       if left.get(field) != right.get(field)]})
    return conflicts


def _project(entry: dict) -> None:
    """Expose research metadata without mislabelling the source's own digest."""
    document = entry["revisions"][-1]["document"]
    for field in ("title", "authors", "year", "venue", "source_type", "source_status", "status_reason"):
        if field in document:
            entry[field] = deepcopy(document[field])
        else:
            entry.pop(field, None)
    entry["current_revision_sha256"] = entry["revisions"][-1]["document_sha256"]


def _validate_findings(entry: dict, identities: set[str]) -> None:
    """Validate optional direct findings without upgrading legacy UI cards."""
    from .direct_artifacts import LITERATURE_ROLES
    from .p1_science import validate_lead_revision

    assessments = entry.get("assessments", [])
    if not isinstance(assessments, list):
        raise LiteratureError("Cumulative member findings are not a collection")
    roles = set()
    for assessment in assessments:
        if not isinstance(assessment, dict) or not isinstance(assessment.get("assessment_history", []), list):
            raise LiteratureError("A cumulative member finding is malformed")
        role = assessment.get("role")
        if role in roles:
            raise LiteratureError("A source has more than one current finding by the same member")
        roles.add(role)
        for version in [assessment, *assessment.get("assessment_history", [])]:
            if (not isinstance(version, dict) or not version.get("run_id")
                    or version.get("role") != role or LITERATURE_ROLES.get(version.get("family")) != role):
                raise LiteratureError("A cumulative member finding has no attributable producing member and run")
            if not isinstance(version.get("publication_sequence"), int) or version["publication_sequence"] < 1:
                raise LiteratureError("A cumulative member finding has no publication order")
            paper = version.get("entry")
            if not isinstance(paper, dict) or not paper.get("entry_id"):
                raise LiteratureError("A cumulative member finding has no exact paper entry")
            citation = _source(paper.get("source"))
            if citation["source_id"] not in identities or _digest(citation) != version.get("source_sha256"):
                raise LiteratureError("A cumulative member finding does not match its source identity or digest")
            if _digest(paper) != version.get("entry_sha256"):
                raise LiteratureError("A cumulative member finding does not match its authored entry digest")
        for version in [assessment, *assessment.get("assessment_history", [])]:
            try:
                validate_lead_revision(version, [assessment, *assessment.get("assessment_history", [])])
            except ArtifactError as exc:
                raise LiteratureError(str(exc)) from exc
    if "landscape_status" in entry:
        disposition = entry.get("landscape_disposition")
        if (entry["landscape_status"] not in {"retain", "exclude", "retract"} or not entry.get("landscape_reason")
                or not isinstance(disposition, dict) or not disposition.get("run_id")
                or disposition.get("source_id") not in identities or disposition.get("family") != "research_basis"
                or not isinstance(disposition.get("publication_sequence"), int) or disposition["publication_sequence"] < 1):
            raise LiteratureError("A cumulative landscape disposition has no exact source and producing basis")
        if "entries" in disposition:
            retained = disposition["entries"]
            if not isinstance(retained, list) or not retained:
                raise LiteratureError("A cumulative landscape disposition has no retained authored entries")
            reasons, pointers = [], set()
            for item in retained:
                document = item.get("disposition") if isinstance(item, dict) else None
                pointer = item.get("entry_pointer") if isinstance(item, dict) else None
                if (not isinstance(document, dict) or document.get("source_id") not in identities
                        or document.get("status") != entry["landscape_status"]
                        or not isinstance(document.get("reason"), str) or not document["reason"]
                        or not isinstance(pointer, str) or not re.fullmatch(r"/source_dispositions/\d+", pointer)
                        or pointer in pointers):
                    raise LiteratureError("A retained landscape disposition does not match its source, status, reason, or pointer")
                reasons.append(document["reason"])
                pointers.add(pointer)
            if (disposition["source_id"] != retained[0]["disposition"]["source_id"]
                    or entry["landscape_reason"] != "\n\n".join(dict.fromkeys(reasons))):
                raise LiteratureError("The landscape reason differs from its retained authored dispositions")


def _merge_findings(entry: dict, other: dict) -> None:
    """A newly resolved DOI/arXiv alias must retain both finding histories."""
    if other.get("assessments"):
        by_role = {}
        for current in entry.get("assessments", []) + other["assessments"]:
            for version in [current, *current.get("assessment_history", [])]:
                plain = {key: value for key, value in version.items() if key != "assessment_history"}
                by_role.setdefault(version["role"], []).append(plain)
        combined = []
        for versions in by_role.values():
            ordered = sorted(_unique(versions), key=lambda item: item["publication_sequence"], reverse=True)
            latest = ordered[0]
            if len(ordered) > 1:
                latest["assessment_history"] = ordered[1:]
            combined.append(latest)
        entry["assessments"] = combined
    other_disposition = other.get("landscape_disposition") or {}
    if other_disposition.get("publication_sequence", 0) > (entry.get("landscape_disposition") or {}).get("publication_sequence", 0):
        for field in ("landscape_status", "landscape_reason", "landscape_disposition"):
            entry[field] = deepcopy(other[field])


def validate_library(library: object) -> dict:
    """Reject damaged projections rather than quietly dropping old sources."""
    if not isinstance(library, dict) or library.get("schema_version") != "1.0.0" or not isinstance(library.get("sources"), list):
        raise LiteratureError("The cumulative literature library is malformed")
    seen_ids, seen_tokens = set(), set()
    for entry in library["sources"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("source_ids"), list) or not entry.get("revisions"):
            raise LiteratureError("A cumulative literature source has no retained identities or revisions")
        identities = set(entry["source_ids"])
        if not identities or entry.get("source_id") not in identities or seen_ids & identities:
            raise LiteratureError("The literature library contains duplicate or missing stable source identities")
        try:
            tokens = _tokens(entry)
        except (KeyError, TypeError) as exc:
            raise LiteratureError("A cumulative source has malformed identifiers") from exc
        if not tokens or seen_tokens & tokens:
            raise LiteratureError("The literature library contains duplicate source locators")
        seen_ids |= identities
        seen_tokens |= tokens
        for revision in entry["revisions"]:
            if not isinstance(revision, dict) or not revision.get("run_id"):
                raise LiteratureError("A literature revision is missing its producing run")
            document = _source(revision.get("document"))
            if document["source_id"] not in identities or _digest(document) != revision.get("document_sha256"):
                raise LiteratureError("A retained literature revision does not match its identity or digest")
        documents = [revision["document"] for revision in entry["revisions"]]
        if identities != {document["source_id"] for document in documents}:
            raise LiteratureError("The literature source aliases differ from their retained revisions")
        for field in ("identifiers", "search_provenance"):
            retained = {_json_key(item) for document in documents for item in document[field]}
            if retained != {_json_key(item) for item in entry.get(field, [])}:
                raise LiteratureError(f"Cumulative literature {field} differs from its retained revisions")
        if entry.get("current_revision_sha256") != entry["revisions"][-1]["document_sha256"]:
            raise LiteratureError("The current literature revision does not match its retained history")
        _validate_findings(entry, identities)
        versions = [version for current in entry.get("assessments", []) for version in [current, *current.get("assessment_history", [])]]
        for revision in entry["revisions"]:
            origins = source_lead_revisions(revision)
            if "lead_revisions" in revision and (not isinstance(origins, list) or len(origins) < 2
                    or len(_unique(origins)) != len(origins) or revision.get("lead_revision") != origins[0]):
                raise LiteratureError("An effective source revision has malformed Lead correction origins")
            for lead in origins:
                if not any(version.get("lead_revision") == lead
                        and version.get("source_sha256") == revision["document_sha256"] for version in versions):
                    raise LiteratureError("An effective source revision has lost its exact Lead correction provenance")
        for version in versions:
            lead = version.get("lead_revision") or {}
            if (lead.get("correction") or {}).get("source_metadata") and not any(revision["run_id"] == lead["run_id"]
                    and revision["document_sha256"] == version["source_sha256"] and lead in source_lead_revisions(revision)
                    for revision in entry["revisions"]):
                raise LiteratureError("A metadata-corrected assessment has lost its attributed effective source revision")
        projected = deepcopy(entry)
        _project(projected)
        if projected != entry:
            raise LiteratureError("The literature projection differs from its retained current revision")
    if library.get("total_sources") != len(library["sources"]):
        raise LiteratureError("The literature source count does not match its records")
    return deepcopy(library)


def build_library(previous_library: dict | None, source_changes: object, *, run_id: str,
                  allow_metadata_conflicts=False, normalize_authors=False, strict_identifiers=False) -> dict:
    """Apply one accepted run's revisions, preserving its exact predecessor.

    ``previous_library`` must be the library frozen when the run was authorized.
    No filesystem access, time, random identifiers, or mutable current pointers
    participate in this transformation.
    """
    if not isinstance(source_changes, list):
        raise LiteratureError("P1 source_changes must be an array of literature source records")
    if not run_id:
        raise LiteratureError("The literature update needs its producing run")
    previous = validate_library(previous_library) if previous_library is not None else {"sources": []}
    entries = previous["sources"]
    original_ids = {alias for entry in entries for alias in entry["source_ids"]}
    added, updated, rediscovered = set(), set(), set()
    batch_documents: dict[str, dict] = {}
    provenance_added = 0
    duplicates = 0
    for candidate in source_changes:
        document = _source(candidate)
        tokens = _tokens(document)
        matches = [entry for entry in entries if document["source_id"] in entry["source_ids"] or tokens & _tokens(entry)]
        if matches:
            entry = matches[0]
            # A locator may newly establish that two earlier aliases are one
            # source. Keep the earliest canonical ID and every previous alias.
            for other in matches[1:]:
                entry["source_ids"] = _unique(entry["source_ids"] + other["source_ids"])
                entry["identifiers"] = _unique(entry["identifiers"] + other["identifiers"])
                entry["search_provenance"] = _unique(entry["search_provenance"] + other["search_provenance"])
                entry["revisions"] = _unique(entry["revisions"] + other["revisions"])
                _merge_findings(entry, other)
                entries.remove(other)
            old = entry["revisions"][-1]["document"]
            old_tokens = _tokens(entry)
            for kind in ("doi", "arxiv", "pmid", "isbn"):
                old_identifiers = {token for token in old_tokens if token.startswith(f"{kind}:")}
                new_identifiers = {token for token in tokens if token.startswith(f"{kind}:")}
                if old_identifiers and new_identifiers and not old_identifiers & new_identifiers and (strict_identifiers or not tokens & old_tokens):
                    raise LiteratureError(f"Source identity {document['source_id']} was reused for a different {kind.upper()}")
            if old["source_status"] in {"retracted", "withdrawn"} and document["source_status"] in {"active", "corrected"} and not document.get("status_reason"):
                raise LiteratureError(f"Restoring {entry['source_id']} requires an explicit status_reason")
            duplicates += 1
        else:
            entry = {"source_id": document["source_id"], "source_ids": [], "identifiers": [],
                     "search_provenance": [], "revisions": []}
            entries.append(entry)
        source_id = entry["source_id"]
        prior_in_batch = next((batch_documents[alias] for alias in entry["source_ids"] if alias in batch_documents), None)
        if prior_in_batch:
            if prior_in_batch["source_status"] != document["source_status"]:
                raise LiteratureError(f"Conflicting statuses for {source_id} in the same literature update")
            if (not allow_metadata_conflicts and
                    _bibliographic_key(prior_in_batch, normalize_authors=normalize_authors) != _bibliographic_key(document, normalize_authors=normalize_authors)):
                raise LiteratureError(f"Conflicting citation metadata for {source_id} in the same literature update")
        previous_document = entry["revisions"][-1]["document"] if entry["revisions"] else None
        before_provenance = len(entry["search_provenance"])
        entry["source_ids"] = _unique(entry["source_ids"] + [document["source_id"]])
        entry["identifiers"] = _unique(entry["identifiers"] + document["identifiers"])
        entry["search_provenance"] = _unique(entry["search_provenance"] + document["search_provenance"])
        provenance_added += len(entry["search_provenance"]) - before_provenance
        revision = {"run_id": run_id, "record_id": document["record_id"],
                    "document_sha256": _digest(document), "document": document}
        revision = next((old for old in entry["revisions"] if old["run_id"] == run_id
                         and old["record_id"] == document["record_id"] and old["document_sha256"] == revision["document_sha256"]), revision)
        entry["revisions"] = _unique(entry["revisions"] + [revision])
        _project(entry)
        batch_documents[source_id] = document
        if not original_ids.intersection(entry["source_ids"]):
            added.add(source_id)
        elif previous_document:
            # Repeated search metadata is a rediscovery, not a scientific change.
            fields = ("title", "authors", "year", "venue", "source_type", "source_status", "status_reason", "source_artifact")
            if any(previous_document.get(field) != document.get(field) for field in fields):
                updated.add(source_id)
            else:
                rediscovered.add(source_id)
    # Canonical IDs can coalesce when a new DOI/arXiv cross-link is supplied.
    canonical = {alias: entry["source_id"] for entry in entries for alias in entry["source_ids"]}
    added = {canonical[item] for item in added} - {entry["source_id"] for entry in entries if original_ids.intersection(entry["source_ids"])}
    updated = {canonical[item] for item in updated} - added
    rediscovered = {canonical[item] for item in rediscovered} - added - updated
    result = {"schema_version": "1.0.0", "run_id": run_id, "sources": entries, "total_sources": len(entries),
              "changes": {"added": len(added), "updated": len(updated), "rediscovered": len(rediscovered),
                          "duplicates": duplicates, "provenance_added": provenance_added,
                          "added_source_ids": sorted(added), "updated_source_ids": sorted(updated),
                          "rediscovered_source_ids": sorted(rediscovered)}}
    return validate_library(result)


def load_committed_library(project_dir: Path) -> dict:
    """Read the accepted registry or reconstruct pre-registry publications.

    Only the current pointer's committed ancestry is eligible. Failed attempts,
    prepared-but-uncommitted manifests, and unrelated generation files never
    enter the library. Call this at authorization, then freeze the result.
    """
    phase_dir = project_dir / "branches" / "trunk" / "phases" / "p1"
    records = current_records(phase_dir)
    if "literature_library" in records:
        return validate_library(read_generation(phase_dir, "literature_library", records["literature_library"]))
    def reconstruct(previous, pointers, run_id):
        from .direct_artifacts import LITERATURE_ROLES, apply_direct_literature, direct_literature_sources
        direct = {family: read_generation(phase_dir, family, pointers[family])
                  for family in (*LITERATURE_ROLES, "research_basis") if family in pointers}
        from .p1_science import reconciliation_enabled, reconciled_library
        if reconciliation_enabled(direct):
            return reconciled_library(direct, previous, run_id=run_id)
        if "source_changes" in pointers:
            changes = read_generation(phase_dir, "source_changes", pointers["source_changes"])
        elif direct:
            changes = direct_literature_sources(direct)
        else:
            raise LiteratureError("Committed P1 history is missing its literature source changes")
        library = build_library(previous, changes, run_id=run_id)
        return apply_direct_literature(library, direct, run_id=run_id) if direct else library
    marker = phase_dir / "current-package.json"
    if not marker.exists():
        if not records:
            return build_library(None, [], run_id="literature.empty")
        pointer = records.get("source_changes") or next(iter(records.values()))
        return reconstruct(None, records, pointer.get("run_id") or f"legacy.{pointer['generation_id']}")
    history = list(committed_packages(phase_dir))
    library = None
    for package in reversed(history):
        pointer = package["records"].get("source_changes") or next(iter(package["records"].values()), {})
        run_id = package.get("run_id") or pointer.get("run_id") or f"legacy.{pointer['generation_id']}"
        library = reconstruct(library, package["records"], run_id)
    return library
