"""Match scientific inputs to the selected method before they enter a run.

The phase catalog decides whether an input needs the exact definition or only
the same stable method lineage. Historical generations remain untouched.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .catalog import Catalog
from .records import ArtifactError, generation_path, read_generation
from .storage import read_json, sha256_file


# Canonical publication slots and their existing compatibility aliases.
_INPUT_FAMILIES = {
    "theory_record": ("P3", ("theory_record", "complete_theory")),
    "empirical_evidence_index": ("P4", ("empirical_evidence_index", "empirical_index_candidate")),
    "empirical_synthesis": ("P4", ("empirical_synthesis", "empirical_synthesis_candidate")),
    "implementation_record": ("P4", ("implementation_record", "implementation_record_candidate")),
    "manuscript": ("P5", ("manuscript", "manuscript_candidate")),
    "technical_report": ("P5", ("technical_report", "technical_report_candidate")),
    "review_issue_ledger": ("P5", ("review_issue_ledger", "review_issues")),
}


def method_identity(value: dict | None) -> tuple | None:
    """Return the calculation-defining identity, ignoring display metadata."""
    if not isinstance(value, dict):
        return None
    value = value.get("identity") or value.get("method_identity") or value
    if not isinstance(value, dict):
        return None
    identity = tuple(value.get(key) for key in ("stable_id", "version", "definition_sha256"))
    stable_id, version, digest = identity
    return identity if (isinstance(stable_id, str) and stable_id
                        and type(version) is int and version > 0
                        and isinstance(digest, str) and digest) else None


def _matches(actual: tuple | None, selected: tuple | None, rule: str) -> bool:
    if not actual or not selected:
        return False
    if rule == "same_stable_method":
        return actual[0] == selected[0]
    # "exact" is definition-exact: the digest covers the canonical definition,
    # so an editorial revision (unchanged digest, new version) keeps existing
    # support aligned. A changed digest is a different definition.
    return actual[0] == selected[0] and actual[2] == selected[2]


def _document(project_dir: Path, ref: dict):
    if ref.get("snapshot_path"):
        path = Path(ref["snapshot_path"])
        if not path.is_file() or sha256_file(path) != ref.get("content_sha256"):
            raise ArtifactError(f"Frozen input for {ref['family']} is missing or changed")
        if ref.get("format") == "jsonl":
            return None  # Replicate rows inherit the producing package's method.
        return json.loads(path.read_text(encoding="utf-8"))
    directory = project_dir / "branches" / ref["branch"] / "phases" / ref["phase"].lower()
    if ref.get("format") == "jsonl":
        generation_path(directory, ref["family"], ref)  # Verify bytes without parsing every replicate.
        return None
    return read_generation(directory, ref["family"], ref)


def _authored_identity(document):
    if isinstance(document, dict):
        return method_identity(document.get("method_identity"))
    return None


def _source_key(ref: dict):
    return ref.get("package_id") or ref.get("run_id") or ref.get("source_run_id")


def filter_method_inputs(
    project_dir: Path, records: list[dict], selected_method: dict | None,
    phase: str, mode: str | None, catalog: Catalog,
) -> tuple[list[dict], list[dict], list[str]]:
    """Return compatible references, excluded history, and readiness reasons.

    Current P3/P4 inputs require the exact method definition: the same stable
    id and definition digest (an editorial revision keeps the digest). P5's
    previous manuscript may use an older version when its catalog rule says
    same_stable_method. Ancillary cards, packets and graphs inherit only their
    producing package's association, not an arbitrary other record on the branch.
    """
    if phase not in {"P3", "P4", "P5"} or not catalog.scientific_validation_enabled:
        return list(records), [], []
    selected = method_identity(selected_method)
    if selected is None:
        return [r for r in records if r["phase"] in {"P1", "P2"}], [], ["Select an active registered method"]
    contract = read_json(catalog.root / "contracts" / "phases" / f"{phase}.json") or {}
    from .technical_reports import technical_report_enabled
    report_mode = phase == "P5" and technical_report_enabled(catalog)
    inputs = [item for item in contract.get("required_inputs", []) if item.get("record_type") in _INPUT_FAMILIES]
    if mode == "p3.assessment":
        inputs.append({"record_type": "theory_record", "method_match": "exact", "presence": "always"})
    rules = {item["record_type"]: item.get("method_match", "exact") for item in inputs}
    family_types = {family: kind for kind, (_, families) in _INPUT_FAMILIES.items() for family in families}
    documents = {}
    source_identities = defaultdict(set)
    for index, ref in enumerate(records):
        if ref["phase"] not in {"P3", "P4", "P5"}:
            continue
        document = _document(project_dir, ref)
        documents[index] = document
        identity = _authored_identity(document)
        if identity and ref["family"] in family_types and _source_key(ref):
            source_identities[(ref["branch"], ref["phase"], _source_key(ref))].add(identity)

    included, excluded, reasons = [], [], []
    matching_phases = set()
    for index, ref in enumerate(records):
        source_phase = ref["phase"]
        if report_mode and source_phase == "P5" and ref["family"] in _INPUT_FAMILIES["manuscript"][1]:
            # Explicitly selected legacy history is readable, but never makes
            # this a report rerun or supplies a current report prerequisite.
            included.append(ref)
            continue
        if source_phase not in {"P3", "P4", "P5"}:
            included.append(ref)
            continue
        document = documents[index]
        explicit = isinstance(document, dict) and "method_identity" in document
        identity = _authored_identity(document)
        # Non-method records (for example claim maps) belong to the same sealed
        # package as its canonical scientific record. Never infer across runs.
        related = source_identities.get((ref["branch"], source_phase, _source_key(ref)), set())
        if identity is None and not explicit and len(related) == 1:
            identity = next(iter(related))
        kind = family_types.get(ref["family"])
        rule = rules.get(kind, "same_stable_method" if source_phase == "P5" and phase == "P5" else "exact")
        matches = _matches(identity, selected, rule)
        if matches:
            matching_phases.add(source_phase)
            included.append(ref)
        else:
            requirement = "the selected method lineage" if rule == "same_stable_method" else f"the selected method version {selected[1]}"
            reason = f"{source_phase} {ref['family']} is not aligned to {requirement}"
            if identity is None:
                reason += " (its method identity is unavailable)"
            excluded.append({**ref, "reason": reason})

    present = {(ref["phase"], ref["family"]) for ref in included}
    for item in inputs:
        source_phase, families = _INPUT_FAMILIES[item["record_type"]]
        presence = item.get("presence")
        required = (presence == "always"
                    or presence == "required_in_modes" and mode in item.get("required_in_modes", [])
                    or presence == "required_on_rerun" and source_phase == phase and source_phase in matching_phases)
        if required and not any((source_phase, family) in present for family in families):
            match_label = "the same method lineage" if item.get("method_match") == "same_stable_method" else f"the selected method version {selected[1]}"
            reasons.append(f"{source_phase} needs a complete current {item['record_type']} aligned to {match_label}")
    return included, excluded, list(dict.fromkeys(reasons))


def validate_frozen_basis_alignment(
    project_dir: Path, basis: dict, phase: str, mode: str | None, catalog: Catalog | None = None,
) -> list[str]:
    """Check included frozen inputs at commit, without consulting current slots.

    Pass the run's frozen catalog. This checks method compatibility and required
    inputs; the caller separately checks the current publication parent.
    """
    catalog = catalog or Catalog(project_dir / "contracts")
    try:
        _, excluded, reasons = filter_method_inputs(project_dir, basis.get("records", []), basis.get("method"), phase, mode, catalog)
    except (OSError, ValueError) as error:
        return [f"Frozen scientific input could not be verified: {error}"]
    return list(dict.fromkeys(reasons + [ref["reason"] for ref in excluded]))
