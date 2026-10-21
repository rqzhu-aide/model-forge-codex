"""Reference and ownership checks for directly displayed P1/P2 records."""

import re

from .domain import Finding
from .records import ArtifactError


def _rows(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _has_json_pointer(document, pointer):
    """Resolve an authored RFC 6901 pointer without guessing a missing anchor."""
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return False
    for part in pointer[1:].split("/"):
        # Invalid escapes are not alternative spellings of object keys.
        if re.search(r"~(?![01])", part):
            return False
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(document, dict) and part in document:
            document = document[part]
        elif isinstance(document, list) and (part == "0" or part.isascii() and part.isdigit() and not part.startswith("0")):
            try:
                index = int(part)
            except ValueError:
                return False
            if index >= len(document):
                return False
            document = document[index]
        else:
            return False
    return True


def _p1_topic_source_hint(outputs, previous_library):
    """Name only supplied records and verified retained literature, without choosing an ID."""
    from .literature import _digest, _source, validate_library

    locations = []
    try:
        frozen = validate_library(previous_library) if previous_library is not None else {"sources": []}
    except (ArtifactError, KeyError, TypeError):
        frozen = {"sources": []}  # The existing context check reports damaged inputs.
    for index, source in enumerate(frozen["sources"]):
        revision = source["revisions"][-1]
        locations.append(f"frozen literature_library/sources/{index} (source IDs {source['source_ids']!r}, "
                         f"record {revision['record_id']}, run {revision['run_id']}, source record sha256 {revision['document_sha256']})")
    for role in ("lead", "theory", "empirical"):
        family = f"p1.{role}_literature"
        collection = outputs.get(family)
        entries = collection.get("papers") if isinstance(collection, dict) else None
        for index, entry in enumerate(entries if isinstance(entries, list) else []):
            try:
                source = _source(entry.get("source") if isinstance(entry, dict) else None)
            except (ArtifactError, KeyError, TypeError):
                continue
            locations.append(f"{family}/papers/{index}/source (source {source['source_id']}, "
                             f"record {source['record_id']}, source record sha256 {_digest(source)})")
    return (" Exact lookup sources supplied to this check: " + "; ".join(locations)
            + ". Verify the intended source; no replacement ID is selected." if locations else
            " No verified source lookup context is available in the supplied collections or frozen library; retain the unresolved reference.")


def validate_direct_outputs(phase, outputs, *, supplied_method=None, lead_instructions="", previous_library=None,
                            mode=None, frozen_method=None, previous_catalog=None, run_id=None, catalog=None):
    findings = []

    def issue(code, message, family, pointer=""):
        findings.append(Finding(code, message, family, pointer))

    if phase == "P1":
        from .direct_artifacts import LITERATURE_ROLES
        from .literature import source_identity_conflicts
        from .p1_science import reconciliation_enabled, literature_entries
        from .literature import _digest
        modern = reconciliation_enabled(catalog=catalog) if catalog is not None else reconciliation_enabled(outputs)
        basis_present = isinstance(outputs.get("p1.research_basis"), dict)
        citations = []
        origins = []
        for suffix in LITERATURE_ROLES:
            family = "p1." + suffix
            collection = outputs.get(family)
            papers = collection.get("papers") if isinstance(collection, dict) else None
            if not isinstance(papers, list):
                continue
            for index, entry in enumerate(papers):
                if not isinstance(entry, dict) or not isinstance(entry.get("source"), dict):
                    continue
                citations.append(entry["source"])
                origins.append((family, f"/papers/{index}/source", entry.get("entry_id")))
        if modern and basis_present:
            try:
                effective = literature_entries(outputs, previous_library, run_id=run_id or "")
                citations = [item["entry"]["source"] for item in effective]
                origins = [("p1." + item["family"], item["entry_pointer"] + "/source", item["entry"]["entry_id"]) for item in effective]
            except (ArtifactError, KeyError, TypeError):
                pass  # Exact correction findings below retain their owning basis.
        conflicts = source_identity_conflicts(citations, normalize_authors=modern, strict_identifiers=modern)
        parents = list(range(len(citations)))
        def conflict_root(position):
            while parents[position] != position:
                position = parents[position]
            return position
        for conflict in conflicts:
            if conflict["metadata_only"]:
                parents[conflict_root(conflict["right"])] = conflict_root(conflict["left"])
        for conflict in conflicts:
            labels = []
            positions = (conflict["left"], conflict["right"])
            for position in positions:
                source = citations[position]
                family, pointer, entry_id = origins[position]
                labels.append(f"{family}{pointer} (entry {entry_id}, source {source['source_id']}, "
                              f"record {source['record_id']}, title {source['title']!r})")
            shared = list(conflict["shared_identifiers"])
            if conflict["shared_source_id"]:
                shared.append("source_id:" + conflict["shared_source_id"])
            message = ("Source identity collision: " + " and ".join(labels) + "; shared identity: "
                       + ", ".join(shared) + "; " + ", ".join(conflict["reasons"])
                       + ". Verify the source identities and citation metadata; this check does not decide which record is correct.")
            deferred = modern and not basis_present and conflict["metadata_only"]
            group_positions = [p for p in range(len(citations)) if conflict_root(p) == conflict_root(positions[0])] if conflict["metadata_only"] else list(positions)
            group_key = sorted((origins[p][0], origins[p][1], origins[p][2] or "", _digest(citations[p])) for p in group_positions)
            details = {"kind": "citation_conflict", "paper_title": citations[positions[0]]["title"],
                       "group_id": _digest(group_key), "shared_identifiers": shared,
                       "differing_fields": conflict["differing_fields"],
                       "action": "The Lead must verify the byline/title/year and author exact source_metadata corrections." if conflict["metadata_only"] else "The original member must verify incompatible source identities or status.",
                       "entries": [{"family": origins[p][0], "json_pointer": origins[p][1], "entry_id": origins[p][2],
                                    "source_sha256": _digest(citations[p]), "source": citations[p]} for p in positions]}
            for position in positions:
                family, pointer, _ = origins[position]
                findings.append(Finding("literature.metadata_reconciliation_pending" if deferred else "literature.source_identity_conflict",
                                        message, "p1.research_basis" if modern and basis_present and conflict["metadata_only"] else family,
                                        "/entry_corrections" if modern and basis_present and conflict["metadata_only"] else pointer,
                                        not deferred, details))
        from .p1_science import validate_current_papers
        if modern or not any(item.code == "literature.source_identity_conflict" for item in findings):
            findings.extend(validate_current_papers(outputs, previous_library, run_id=run_id))

    if phase == "P1":
        known_sources = set()
        for source in _rows((previous_library or {}).get("sources")):
            known_sources.update(source.get("source_ids", []))
            if source.get("source_id"):
                known_sources.add(source["source_id"])
        for role in ("lead", "theory", "empirical"):
            family = f"p1.{role}_literature"
            collection = outputs.get(family)
            if not isinstance(collection, dict):
                continue
            entries = _rows(collection.get("papers"))
            ids = [entry["entry_id"] for entry in entries if isinstance(entry.get("entry_id"), str)]
            if len(set(ids)) != len(ids):
                issue("literature.duplicate_entry", "Paper entry IDs must be unique within the member's collection.", family, "/papers")
            for entry in entries:
                source = entry.get("source")
                if isinstance(source, dict) and isinstance(source.get("source_id"), str):
                    known_sources.add(source["source_id"])
        basis = outputs.get("p1.research_basis")
        if not isinstance(basis, dict):
            return findings
        landscape = basis.get("landscape") or {}
        topics = landscape.get("topics") if isinstance(landscape, dict) else None
        source_hint = None
        for index, topic in enumerate(topics if isinstance(topics, list) else []):
            if not isinstance(topic, dict):
                continue
            ids = topic.get("source_ids")
            for ref_index, value in enumerate(ids if isinstance(ids, list) else []):
                if isinstance(value, str) and value not in known_sources:
                    if source_hint is None:
                        source_hint = _p1_topic_source_hint(outputs, previous_library)
                    issue("literature.unknown_topic_source", f"Source {value!r} is outside the new findings and frozen library." + source_hint,
                          "p1.research_basis", f"/landscape/topics/{index}/source_ids/{ref_index}")
        for disposition in _rows(basis.get("source_dispositions")):
            if not isinstance(disposition.get("source_id"), str) or disposition["source_id"] not in known_sources:
                issue("literature.unknown_disposition_source", "A source disposition must identify a new or retained source.", "p1.research_basis", "/source_dispositions")
        from .p1_science import validate_p1_science
        if modern or not any(item.code in {"literature.source_identity_conflict", "literature.duplicate_current_paper"} for item in findings):
            findings.extend(validate_p1_science(outputs, previous_library, run_id=run_id or "", catalog=catalog))

    if phase != "P2":
        return findings
    proposal_ids = {}
    method_ids = set()
    from .p2_delivery import _decision_support_p2, requires_method_sections, requires_reader_summaries, requires_three_proposals
    three_proposals = requires_three_proposals(catalog)
    reader_summaries = requires_reader_summaries(catalog)
    decision_support = _decision_support_p2(catalog)
    method_sections = requires_method_sections(catalog)
    lead_response = outputs.get("p2.lead_proposal")
    lead_declined = isinstance(lead_response, dict) and lead_response.get("no_method_proposed") is True
    from .methods import _method_documents
    existing_ids = {(method.get("identity") or method.get("method_identity") or {}).get("stable_id")
                    for method in _method_documents(previous_catalog)}
    selected_id = ((frozen_method or {}).get("identity") or frozen_method or {}).get("stable_id")
    for role in ("theory", "empirical", "lead"):
        family = f"p2.{role}_proposal"
        proposal = outputs.get(family)
        if not isinstance(proposal, dict):
            continue  # Required-output/schema validation reports missing records.
        if role == "lead" and lead_declined:
            continue  # A reasoned response to directions is not a method proposal.
        pid = proposal.get("proposal_id")
        if not isinstance(pid, str):
            continue
        if pid in proposal_ids.values():
            issue("proposal.duplicate_id", "Independent proposals must have distinct proposal IDs.", family, "/proposal_id")
        proposal_ids[role] = pid
        method = proposal.get("method") or {}
        identity = method.get("identity") if isinstance(method, dict) else None
        if isinstance(identity, dict):
            mid = identity.get("stable_id")
            if isinstance(mid, str) and mid in method_ids:
                issue("proposal.duplicate_method", "Independent alternatives must have distinct method identities.", family, "/method/identity")
            if isinstance(mid, str):
                method_ids.add(mid)
                if mode == "p2.focused_method" and mid in existing_ids and mid != selected_id:
                    issue("proposal.focus_scope", "Focused work may revise the selected method or propose a new alternative, but cannot change another catalog method.", family, "/method/identity")
        if role == "lead" and supplied_method and proposal.get("researcher_origin") != supplied_method:
            issue("proposal.researcher_origin", "The lead proposal must preserve the exact supplied method as its researcher origin.", family, "/researcher_origin")
    check_lead = "p2.lead_proposal" in outputs or "p2.catalog_assessment" in outputs
    if three_proposals and check_lead and "lead" not in proposal_ids:
        issue("proposal.missing_lead", "This P2 contract requires one actual lead method aligned with researcher intent, including when no method idea was supplied.", "p2.lead_proposal")
    if not three_proposals and check_lead and supplied_method and "lead" not in proposal_ids and not (lead_declined and lead_instructions.strip()):
        issue("proposal.missing_lead", "The supplied method requires a lead proposal.", "p2.lead_proposal")
    if not three_proposals and check_lead and mode == "p2.researcher_proposal" and lead_response is None:
        issue("proposal.missing_lead_response", "The lead must respond to the Phase 2 instructions or ideas.", "p2.lead_proposal")
    if not three_proposals and not supplied_method and not lead_instructions.strip() and "lead" in proposal_ids:
        issue("proposal.unrequested_lead", "The lead proposal requires a researcher-supplied method.", "p2.lead_proposal")
    for reviewer, other in (("theory", "empirical"), ("empirical", "theory")):
        family = f"p2.{reviewer}_review"
        review = outputs.get(family)
        if not isinstance(review, dict):
            continue
        expected_review_version = "1.2.0" if method_sections else "1.1.0"
        if reader_summaries and review.get("schema_version") != expected_review_version:
            requirement = ("This pinned P2 contract requires review schema_version 1.2.0 with specialist-authored applicability_markdown for each assessment."
                           if method_sections else
                           "This pinned P2 contract requires review schema_version 1.1.0 with an authored headline for each assessment and title for each finding.")
            issue("review.reader_summary_version", requirement, family, "/schema_version")
        actual = [assessment["proposal_id"] for assessment in _rows(review.get("assessments")) if isinstance(assessment.get("proposal_id"), str)]
        expected = {proposal_ids[other]} if other in proposal_ids else set()
        if "lead" in proposal_ids:
            expected.add(proposal_ids["lead"])
        if set(actual) != expected or len(actual) != len(expected):
            issue("review.target_coverage", "Audit the other specialist proposal and the lead proposal exactly once; do not substitute self-review.", family, "/assessments")
        for assessment_index, target_assessment in enumerate(_rows(review.get("assessments"))):
            target_role = next((role for role, pid in proposal_ids.items() if pid == target_assessment.get("proposal_id")), None)
            target_proposal = outputs.get(f"p2.{target_role}_proposal")
            if target_proposal is None:
                continue  # Target coverage reports a missing or invalid proposal.
            for finding_index, finding in enumerate(_rows(target_assessment.get("findings"))):
                refs = finding.get("statement_refs")
                if not isinstance(refs, list):
                    continue  # The schema owns malformed reference arrays.
                for ref_index, reference in enumerate(refs):
                    if not _has_json_pointer(target_proposal, reference):
                        issue("review.unknown_statement_reference", "A statement_refs JSON Pointer must resolve in this assessment's exact original proposal; do not infer or invent an equation anchor.", family,
                              f"/assessments/{assessment_index}/findings/{finding_index}/statement_refs/{ref_index}")
    assessment = outputs.get("p2.catalog_assessment")
    if isinstance(assessment, dict):
        if reader_summaries:
            expected_version = "1.3.0" if method_sections else "1.2.0" if decision_support else "1.1.0"
            if assessment.get("schema_version") != expected_version:
                requirement = ("This pinned P2 contract requires catalog-assessment schema_version 1.3.0 with a lead-authored method_summary_markdown separate from each candidate's evaluation rationale."
                               if method_sections else
                               "This pinned P2 contract requires catalog-assessment schema_version 1.2.0 with the lead's compact overview_markdown and authored modification options."
                               if decision_support else
                               "This pinned P2 contract requires catalog-assessment schema_version 1.1.0 with the lead's compact overview_markdown.")
                issue("catalog.reader_summary_version", requirement, "p2.catalog_assessment", "/schema_version")
        ids = [item["proposal_id"] for item in _rows(assessment.get("method_dispositions")) if isinstance(item.get("proposal_id"), str)]
        if set(ids) != set(proposal_ids.values()) or len(ids) != len(proposal_ids):
            issue("catalog.proposal_coverage", "The catalog assessment must record one disposition for each submitted proposal.", "p2.catalog_assessment", "/method_dispositions")
        if reader_summaries:
            known_method_ids = method_ids | {mid for mid in existing_ids if isinstance(mid, str)}
            for index, attention in enumerate(_rows(assessment.get("attention_items"))):
                affected = attention.get("affected_record_ids")
                if not isinstance(affected, list):
                    continue  # The contextual attention schema owns this shape.
                pointer = f"/attention_items/{index}/affected_record_ids"
                if attention.get("kind") == "researcher_decision" and not affected:
                    issue("catalog.decision_method_scope", "A P2 researcher decision must name the affected method stable IDs in affected_record_ids so its answer stays with those method branches.", "p2.catalog_assessment", pointer)
                if any(not isinstance(mid, str) or mid not in known_method_ids for mid in affected):
                    issue("catalog.unknown_attention_method", "P2 attention affected_record_ids must name method stable IDs from the actual proposals or frozen method catalog. Use an empty list only for a phase-wide research_task; do not use proposal IDs or unrelated record IDs.", "p2.catalog_assessment", pointer)
        if decision_support:
            options = _rows(assessment.get("modification_options"))
            known_proposals = set(proposal_ids.values())
            for index, option in enumerate(options):
                if option.get("applies_to") not in known_proposals:
                    issue("catalog.unknown_modification_target", "A modification option must apply to one of this run's actual proposals.", "p2.catalog_assessment", f"/modification_options/{index}/applies_to")
            option_ids = [option["option_id"] for option in options if isinstance(option.get("option_id"), str)]
            if len(set(option_ids)) != len(option_ids):
                issue("catalog.modification_coverage", "Modification option ids must be unique within the catalog assessment.", "p2.catalog_assessment", "/modification_options")
            per_proposal = {}
            for option in options:
                target = option.get("applies_to")
                if isinstance(target, str):
                    per_proposal[target] = per_proposal.get(target, 0) + 1
            for target, count in per_proposal.items():
                if count > 3:
                    issue("catalog.modification_coverage", f"Each proposal carries at most three modification options; {target} has {count}.", "p2.catalog_assessment", "/modification_options")
            for disposition in _rows(assessment.get("method_dispositions")):
                retained_id = disposition.get("proposal_id")
                if disposition.get("status") == "retain" and isinstance(retained_id, str) and per_proposal.get(retained_id, 0) == 0:
                    issue("catalog.modification_coverage", f"Each retained proposal carries at least one modification option; {retained_id} has none.", "p2.catalog_assessment", "/modification_options")
    return findings
