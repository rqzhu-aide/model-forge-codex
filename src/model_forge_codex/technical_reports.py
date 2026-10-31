"""Technical reports use exact retained sources and a separate publication family.

Completion describes the declared scientific account and its retained support.
It never certifies a proof or the adequacy of a numerical investigation.
"""
from __future__ import annotations

import csv
import html
import io
import json
import mimetypes
import math
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote

from .alignment import method_identity
from .domain import Finding
from .records import ArtifactError, committed_packages, read_generation
from .report_boundaries import reference_boundary
from .storage import read_json, sha256_bytes, sha256_file

TECHNICAL_REPORT_CAPABILITY = "p5.technical_report.v1"
READER_REPORT_CAPABILITY = "p5.reader_report.v1"
REPORT_FAMILIES = ("technical_report", "technical_report_candidate")
CONTENT_SECTIONS = ("problem", "model", "existing_approaches", "justification", "numerical_analysis", "limitations", "reproducibility")


def technical_report_enabled(catalog) -> bool:
    try:
        contract = read_json(catalog.root / "contracts/phases/P5.json") or {}
        return TECHNICAL_REPORT_CAPABILITY in contract.get("capabilities", [])
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def reader_report_enabled(catalog) -> bool:
    """Read the capability from the run's captured catalog, including retries."""
    try:
        contract = read_json(catalog.root / "contracts/phases/P5.json") or {}
        return READER_REPORT_CAPABILITY in contract.get("capabilities", [])
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def technical_report_scope_brief(basis: dict) -> str:
    return ("## Frozen technical report scope\n\nWrite a concise statistical technical report for the selected exact model and frozen problem context. "
            "Keep the seven anchored content sections, with depth proportional to their scientific purpose and no word or equation quota. "
            "Define the target and exact model once, including consequential assumptions, constraints, normalization and fitting steps. "
            "Compare only relevant existing approaches; give the applicable mathematical support and the numerical findings needed to assess this model. "
            "Use cross-references instead of repeating definitions, result tables, caveat lists or section summaries. "
            "Keep qualifications beside affected claims, then synthesize the decisive limitations and unresolved expectations briefly. "
            "An abstract, extended introduction, exhaustive literature review and full proof development are not required. "
            "Keep generation IDs, digests, scalar pointers, review dispositions and detailed reproduction files in their structured records or declared supplements; "
            "the narrative retains scientific attribution, essential design choices and short reproduction instructions. "
            "Detailed derivations, secondary full tables and lengthy reproduction recipes may be linked as declared supplementary detail; "
            "retain the defining model equations, decisive conditions and main findings without copying all earlier mathematics.\n\n"
            "Use conventional statistical terminology and connected explanatory prose. Distinguish the estimand, estimator and realized estimate; "
            "sampling variability, resampling variability and Monte Carlo standard error; association, prediction and causal effects. "
            "State the actual model relation or statistical operation rather than inventing software metaphors or labels. "
            "Preserve mathematical objects, conditions, quantifiers, conditioning, signs, bounds, tuning conventions, units, numerical values and evidence strength. "
            "A shorter account must not replace the defining formulation with an unexplained tuple, omit a material constraint or imply unsupported equivalence.\n\n"
            "Use Markdown with KaTeX-supported LaTeX: $...$ inline and $$...$$ or \\[...\\] for central displays, with aligned line breaks when needed. "
            "Do not use custom TeX macros or document-level commands. Check the actual report Markdown with validate_artifacts, correct the reported syntax "
            "without changing mathematical meaning, and inspect rendered equations when rendering is available. A syntax pass does not establish mathematical fidelity. "
            "Missing numerical work permits a visibly interim report. New formal results require P3; verified established results require "
            "a retained Theorist applicability check. Describe unchecked conditions honestly. Completion and exact-byte independent review "
            "are separate. Report expectations against the frozen context item revisions. "
            "Do not reopen P1-P4 problem, collection, method or study-design questions. Keep scientific open items in the report's source records or review ledger "
            "and route resolving work upstream. attention_items may be empty; ask only for an indispensable editorial choice needed to write this exact report.\n\n")


def report_assembly_readiness(basis: dict) -> list[str]:
    reasons = []
    if method_identity(basis.get("method")) is None:
        reasons.append("Select an exact published model before assembling its technical report")
    context = basis.get("problem_context")
    if not isinstance(context, dict) or not context.get("revision"):
        reasons.append("Capture the exact problem-context revision before report assembly")
    return reasons


def report_context_basis(basis: dict, document: dict) -> dict:
    """Use the exact researcher context snapshots sealed with this report.

    A later pause cannot add expectations to an already retained generation.
    Its original context revision and digest remain its provenance.
    """
    result = dict(basis)
    context = deepcopy(basis.get("problem_context") or {})
    source = context.get("document", context)
    original = context.get("frozen_effective_account") or source.get("frozen_effective_account")
    if original is None:
        original = source.get("effective_account") or {"items": source.get("items", [])}
    account = deepcopy(original)
    accepted = deepcopy(document.get("authorized_context_items", []))
    items = {row["item_id"]: row for row in _rows(account.get("items"))}
    items.update({row["item_id"]: row for row in _rows(accepted)})
    superseded = {ref.get("item_id") for item in _rows(accepted) for ref in item.get("amends", [])
                  if isinstance(ref, dict) and ref.get("kind") == "context_item" and ref.get("item_id") != item.get("item_id")}
    account["items"] = [item for identifier, item in items.items() if identifier not in superseded]
    instructions = account.get("unamended_instructions")
    if isinstance(instructions, str):
        for item in _rows(accepted):
            for ref in item.get("amends", []):
                if isinstance(ref, dict) and ref.get("kind") == "project_brief" and ref.get("text"):
                    instructions = instructions.replace(ref["text"], "")
        account["unamended_instructions"] = instructions
    account["incorporated_answer_refs"] = [deepcopy(ref) for item in account["items"] for ref in item.get("answer_refs", [])]
    context["frozen_effective_account"] = deepcopy(original)
    context["authorized_context_items"] = accepted
    context["authorized_context_refs"] = [{"item_id": item["item_id"], "revision": item["revision"],
                                            "answer_refs": deepcopy(item.get("answer_refs", []))} for item in _rows(accepted)]
    context["effective_account"] = account
    if source is not context:
        source["effective_account"] = account
    result["problem_context"] = context
    return result


def _rows(value):
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _pointer(document, pointer):
    if pointer in (None, ""):
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/") or re.search(r"~(?![01])", pointer):
        raise ArtifactError("An exact report source has an invalid JSON Pointer")
    try:
        for part in pointer[1:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            document = document[int(part)] if isinstance(document, list) else document[part]
        return document
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise ArtifactError("An exact report source locator does not resolve") from exc


class _ReportProjectionBasis(dict):
    """Verified snapshots and derived indexes owned by one projection call."""
    def __init__(self, basis):
        super().__init__(basis)
        self.verified_sources = {}
        self.source_materials = {}


def report_projection_basis(basis: dict) -> dict:
    """Reuse exact source bytes while projecting one report, never across requests."""
    return _ReportProjectionBasis(basis)


def _source_identity(reference):
    return tuple(reference.get(key) for key in ("phase", "branch", "family", "generation_id", "content_sha256",
                                               "run_id", "stage_id", "package_id", "snapshot_path", "format"))


def resolve_report_source(reference: dict, basis: dict):
    """Resolve only captured bytes, never the live current slot."""
    fields = ("phase", "branch", "family", "generation_id", "content_sha256")
    candidates = [row for row in _rows(basis.get("records")) if all(reference.get(key) == row.get(key) for key in fields)]
    if len(candidates) != 1:
        raise ArtifactError("A report source does not name one exact frozen source generation and digest")
    ref = candidates[0]
    path = Path(ref.get("snapshot_path", ""))
    cache = getattr(basis, "verified_sources", None)
    key = _source_identity(ref)
    if cache is not None and key in cache:
        document = cache[key]
    else:
        if not path.is_file() or sha256_file(path) != ref.get("content_sha256"):
            raise ArtifactError("A report's frozen source changed or disappeared")
        if ref.get("format") == "jsonl":
            document = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            document = read_json(path)
        if cache is not None:
            cache[key] = document
    return _pointer(document, reference.get("pointer")), ref, document


def resolve_report_artifact(pointer: dict, basis: dict, *, roots=()) -> Path:
    expected = pointer.get("sha256") or pointer.get("artifact_sha256")
    if not expected:
        raise ArtifactError("A report artifact has no exact digest")
    for entry in _rows(basis.get("artifacts")):
        if entry.get("content_sha256") == expected:
            path = Path(entry.get("path", ""))
            if path.is_file() and sha256_file(path) == expected:
                return path
    relative = Path(pointer.get("path") or pointer.get("artifact_path") or "")
    if not str(relative) or relative.is_absolute() or ".." in relative.parts:
        raise ArtifactError("A report artifact has no safe retained source path")
    for root in roots:
        root = Path(root).resolve()
        path = (root / relative).resolve()
        if path.is_relative_to(root) and path.is_file() and sha256_file(path) == expected:
            return path
    raise ArtifactError("A report artifact is unavailable or its exact bytes changed")


def resolve_report_scalar(reference: dict, basis: dict):
    """Resolve a prose scalar without changing the ordinary source selection."""
    source, ref, full = resolve_report_source(reference, basis)
    if "scalar_pointer" not in reference:
        return source, ref, full
    selected = method_identity(basis.get("method"))
    if (ref.get("phase") != "P4" or not selected or not isinstance(source, dict)
            or not (source.get("sha256") or source.get("artifact_sha256"))
            or not (source.get("path") or source.get("artifact_path") or source.get("artifact_id"))):
        raise ArtifactError("A report artifact scalar must select an exact-model retained P4 artifact pointer")
    owner = full
    if isinstance(full, list):
        # A collection pointer names its owning record explicitly; do not
        # search other entries for a matching model or artifact.
        owner = _pointer(full, "/" + reference["pointer"].split("/", 2)[1])
    if method_identity(owner) != selected:
        raise ArtifactError("A report artifact scalar must select an exact-model retained P4 artifact pointer")
    path = resolve_report_artifact(source, basis)
    value = _pointer(read_json(path), reference["scalar_pointer"])
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ArtifactError("A report artifact scalar must select one finite JSON number")
    return value, ref, full


def _artifact_pointers(value):
    if isinstance(value, dict):
        if value.get("information_layer") in {"structured_record", "compact_decision_view"}:
            return
        if (value.get("sha256") or value.get("artifact_sha256")) and (value.get("path") or value.get("artifact_path") or value.get("artifact_id")):
            yield value
        for child in value.values():
            yield from _artifact_pointers(child)
    elif isinstance(value, list):
        for child in value:
            yield from _artifact_pointers(child)


def report_required_artifacts(document: dict, basis: dict) -> list[dict]:
    """Every cited exhibit and its declared data dependencies travel to review."""
    result = [document.get("report_artifact"), *document.get("supplementary_artifacts", [])]
    notation = document.get("notation_snapshot")
    if isinstance(notation, dict):
        result.extend(({key: value for key, value in notation.items() if key != "markdown"}, notation.get("markdown")))
    for analysis in _rows(document.get("numerical_analysis")):
        for reference in [*analysis.get("evidence_refs", []), *analysis.get("exhibit_refs", []), *analysis.get("implementation_refs", [])]:
            source, ref, full = resolve_report_source(reference, basis)
            result.extend(_artifact_pointers(source))
            if reference in analysis.get("implementation_refs", []):
                result.extend(_artifact_pointers(full))
            if isinstance(source, dict) and source.get("data_exhibit_ids"):
                if isinstance(full, list):
                    exhibits = full
                elif ref.get("family") in {"empirical_evidence_index", "empirical_index_candidate"}:
                    exhibits = full.get("exhibit_index", [])
                else:
                    exhibits = full.get("exhibits", [])
                for identifier in source["data_exhibit_ids"]:
                    matches = [row for row in _rows(exhibits) if row.get("exhibit_id") == identifier]
                    if len(matches) != 1:
                        raise ArtifactError("A report figure's retained data exhibit is unavailable")
                    result.extend(_artifact_pointers(matches[0]))
    for claim in _rows(document.get("claims")):
        for reference in claim.get("source_refs", []):
            source, _, _ = resolve_report_source(reference, basis)
            result.extend(_artifact_pointers(source))
    for value in _rows(document.get("prose_values")):
        for reference in value.get("source_refs", []):
            if "scalar_pointer" in reference:
                source, _, _ = resolve_report_source(reference, basis)
                result.extend(_artifact_pointers(source))
    unique = {}
    for pointer in result:
        if isinstance(pointer, dict):
            authored = (document.get("artifact_authored_paths") or {}).get(pointer.get("artifact_id"))
            material = {**pointer, **({"authored_path": authored} if authored else {})}
            unique.setdefault((pointer.get("sha256") or pointer.get("artifact_sha256"), pointer.get("artifact_id")), material)
    return list(unique.values())


def report_material_notation_source(project_dir, document, material, basis):
    """A retained proof uses the notation of its declared exact source account."""
    from .notation import account_notation_source, _committed
    expected = material.get("sha256") or material.get("artifact_sha256")
    if not expected:
        return None
    references = [reference for group in ("claims", "numerical_analysis", "prose_values")
                  for row in _rows(document.get(group))
                  for field in ("source_refs", "evidence_refs", "exhibit_refs", "implementation_refs")
                  for reference in row.get(field, [])]
    matches = {}
    cache = getattr(basis, "source_materials", None)
    for reference in references:
        try:
            _, source, full = resolve_report_source(reference, basis)
            key = _source_identity(source)
            indexed = cache.get(key) if cache is not None else None
            if indexed is None:
                indexed = {"digests": {pointer.get("sha256") or pointer.get("artifact_sha256")
                                       for pointer in _artifact_pointers(full)}}
                if cache is not None:
                    cache[key] = indexed
            if expected not in indexed["digests"]:
                continue
            if "notation" not in indexed:
                notation = None
                owner = account_notation_source(project_dir, source)
                if owner is not None:
                    retained, _ = _committed(Path(project_dir), owner)
                    pointer = retained.get("notation_snapshot")
                    if pointer:
                        from .research import source_ref
                        exact = source_ref(owner["branch"], owner["phase"], owner["family"], owner)
                        notation = {"notation_source_ref": exact, "notation_snapshot": deepcopy(pointer)}
                indexed["notation"] = notation
            notation = indexed["notation"]
            if notation:
                matches[notation["notation_snapshot"]["sha256"]] = deepcopy(notation)
        except (ArtifactError, ValueError, KeyError):
            continue
    return next(iter(matches.values())) if len(matches) == 1 else None


_SUBMITTED_SOURCE_FIELDS = {
    "record_id", "record_type", "statement_id", "evidence_id", "evidence_kind", "exhibit_id", "question_id", "test_id",
    "method_identity", "identity", "title", "statement", "statement_used", "conditions", "model_fit", "source_locator",
    "checked_by", "status", "eligibility", "applicability_at_creation", "mathematical_definition", "formulation", "notation",
    "assumptions", "inputs", "outputs", "algorithm", "procedure", "justification", "question", "scope", "relevance",
    "metrics", "results", "values", "value", "estimate", "metric_value", "mean", "standard_error", "lower", "upper",
    "units", "uncertainty", "configuration", "parameters", "seed", "seeds", "random_seed", "data_origin",
    "data_identity", "simulation_identity", "data_or_simulation_identity", "data_definition", "simulation_definition",
    "sample_size", "replications", "environment", "implementation_summary", "caption", "labels", "kind", "data_exhibit_ids",
}
_SUBMITTED_IMPLEMENTATION_FIELDS = {"rule", "correspondence", "environment", "verification", "limitations", "configuration", "choices", "departures"}


def _submitted_excerpt(source):
    if isinstance(source, list):
        return [_submitted_excerpt(item) for item in source]
    if not isinstance(source, dict):
        return source
    excerpt = {key: value for key, value in source.items() if key in _SUBMITTED_SOURCE_FIELDS}
    summary = excerpt.get("implementation_summary")
    if isinstance(summary, dict):
        excerpt["implementation_summary"] = {key: value for key, value in summary.items() if key in _SUBMITTED_IMPLEMENTATION_FIELDS}
    return excerpt


def report_submitted_source_materials(document: dict, basis: dict) -> dict:
    """Public cited science for a first reader, without private basis or audits."""
    basis = report_context_basis(basis, document)
    sources = {}
    for name in ("claims", "numerical_analysis", "expectation_outcomes", "prose_values"):
        for row in _rows(document.get(name)):
            references = [ref for key in ("source_refs", "evidence_refs", "exhibit_refs", "implementation_refs")
                          for ref in row.get(key, [])]
            if (row.get("theorist_check") or {}).get("check_ref"):
                references.append(row["theorist_check"]["check_ref"])
            for reference in references:
                resolver = resolve_report_scalar if name == "prose_values" else resolve_report_source
                source, _, _ = resolver(reference, basis)
                excerpt = _submitted_excerpt(source)
                # Pointer-selected scalars and arrays are themselves exact cited
                # scientific material, rather than another whole internal record.
                exact_ref = {key: reference[key] for key in ("phase", "branch", "family", "generation_id", "content_sha256", "pointer", "scalar_pointer") if key in reference}
                sources.setdefault(json.dumps(exact_ref, sort_keys=True), {"source_ref": exact_ref, "scientific_excerpt": excerpt})
    context = basis.get("problem_context") or {}
    context = context.get("document", context)
    account = context.get("effective_account") or {"items": context.get("items", [])}
    referenced = {(row.get("context_item_id"), row.get("context_item_revision")) for row in _rows(document.get("expectation_outcomes"))}
    referenced.update((row.get("item_id"), row.get("revision")) for row in _rows(document.get("context_dependencies")))
    context_items = [{key: item[key] for key in ("item_id", "revision", "statement", "origin", "topic", "scope", "answer_refs", "source_refs", "amends") if key in item}
                     for item in _rows(account.get("items")) if (item.get("item_id"), item.get("revision")) in referenced
                     or item.get("topic") == "expectation" or item.get("kind") == "expectation"]
    return {"claims": document.get("claims", []), "prose_values": document.get("prose_values", []),
            "numerical_analysis": document.get("numerical_analysis", []), "expectation_outcomes": document.get("expectation_outcomes", []),
            "problem_context_ref": document.get("problem_context_ref"), "referenced_context_items": context_items,
            "scientific_sources": list(sources.values())}


_NUMERIC_METADATA_FIELDS = {"metadata", "configuration", "config", "settings", "parameters", "environment", "provenance", "budget",
                            "method_identity", "identity", "applicability_at_creation", "seed", "seeds",
                            "random_seed", "version", "sample_size", "replications", "planned", "iterations", "n"}
_MEASUREMENT_WORDS = {"value", "estimate", "mean", "median", "error", "residual", "bias", "mae", "mse", "rmse",
                      "sd", "se", "mcse", "variance", "quantile", "lower", "upper", "interval", "coverage",
                      "delta", "difference", "fraction", "runtime", "seconds"}


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _numeric_metadata(key):
    return (key in _NUMERIC_METADATA_FIELDS or key.startswith("n_")
            or bool({"seed", "seeds", "planned", "version", "budget", "timeout"}.intersection(key.lower().split("_"))))


def _numeric_support(source, basis):
    """Require measured numbers or retained numeric results, not an execution label."""
    if isinstance(source, list):
        return any(_numeric_support(row, basis) for row in source)
    if not isinstance(source, dict):
        return False
    if (source.get("status") in {"failed", "not_run", "not_started", "cancelled", "invalidated", "excluded"}
            or source.get("eligibility") in {"invalidated", "excluded"}
            or (_finite_number(source.get("completed")) and source["completed"] == 0)):
        return False
    # Metrics-long rows deliberately allow protocol-defined metric names. A
    # seed or execution count elsewhere in the record is not a measured result.
    metrics = source.get("metrics")
    if isinstance(metrics, dict) and any(_finite_number(value) for key, value in metrics.items()
                                         if not _numeric_metadata(key)):
        return True
    # Tables retain their descriptive measurement column names (for example
    # estimate_months, paired_mae_difference_months and method_seconds).
    if any(_finite_number(value) and not _numeric_metadata(key)
           and _MEASUREMENT_WORDS.intersection(key.lower().split("_")) for key, value in source.items()):
        return True
    scientific = {key: value for key, value in source.items() if not _numeric_metadata(key)}
    for pointer in _artifact_pointers(scientific):
        path = resolve_report_artifact(pointer, basis)
        if path.suffix.lower() in {".json", ".jsonl", ".csv", ".tsv"}:
            text = path.read_text(encoding="utf-8")
            if path.suffix.lower() == ".json":
                if _numeric_support(json.loads(text), basis):
                    return True
            elif path.suffix.lower() == ".jsonl":
                if any(_numeric_support(json.loads(line), basis) for line in text.splitlines() if line.strip()):
                    return True
            else:
                rows = csv.DictReader(io.StringIO(text), delimiter="\t" if path.suffix.lower() == ".tsv" else ",")
                for row in rows:
                    numeric_row = {}
                    for key, value in row.items():
                        if key is None:
                            continue
                        try:
                            numeric_row[key] = float(value)
                        except (ValueError, TypeError):
                            numeric_row[key] = value
                    if _numeric_support(numeric_row, basis):
                        return True
    return any(_numeric_support(value, basis) for value in scientific.values() if isinstance(value, (dict, list)))


def _retained_implementation(analysis, basis, selected):
    for reference in analysis.get("implementation_refs", []):
        source, ref, full = resolve_report_source(reference, basis)
        if ref.get("phase") != "P4" or not isinstance(full, dict) or method_identity(full) != selected:
            continue
        if full.get("record_type") != "implementation_record" or not (full.get("implementation_summary") or {}).get("environment"):
            continue
        for pointer in _artifact_pointers(full):
            path = resolve_report_artifact(pointer, basis)
            if path.suffix.lower() in {".py", ".r", ".jl", ".cpp", ".c", ".m", ".ipynb", ".js", ".ts"}:
                return True
    return False


def _exact_numeric_support(source, ref, full, basis, selected):
    return (ref.get("phase") == "P4" and (method_identity(source) or method_identity(full)) == selected
            and isinstance(source, dict) and source.get("evidence_kind") in {"computation", "simulation", "experiment", "external_validation"}
            and (source.get("applicability_at_creation") or {}).get("method_match") == "exact"
            and source.get("eligibility") not in {"invalidated", "excluded"} and _numeric_support(source, basis))


def derive_report_completion(document: dict, basis: dict, *, artifact_roots: dict | None = None) -> dict:
    """Return derived status and missing work; author labels cannot set status."""
    roots = list((artifact_roots or {}).values())
    missing = report_assembly_readiness(basis)
    selected = method_identity(basis.get("method"))
    if method_identity(document.get("method_identity")) != selected:
        missing.append("The report formulation must name the exact selected model version")
    sections = document.get("sections_present", [])
    missing.extend(f"Explain the {section.replace('_', ' ')} content" for section in CONTENT_SECTIONS if section not in sections)
    try:
        primary = resolve_report_artifact(document.get("report_artifact") or {}, basis, roots=roots)
        markdown = primary.read_text(encoding="utf-8")
        if primary.suffix.lower() != ".md":
            missing.append("Retain the primary report as Markdown with LaTeX")
        for section in sections:
            anchor = (document.get("section_anchors") or {}).get(section)
            if not anchor or f'id="{anchor}"' not in markdown:
                missing.append(f"Retain the readable {section.replace('_', ' ')} section at its authored anchor")
    except ArtifactError as exc:
        missing.append(str(exc))
    relevant_numeric = False
    for analysis in _rows(document.get("numerical_analysis")):
        if not analysis.get("question") or not analysis.get("scope") or not analysis.get("relevance"):
            continue
        if not analysis.get("implementation_refs") or not analysis.get("data_origin") or not analysis.get("data_or_simulation_identity"):
            continue
        for reference in analysis.get("evidence_refs", []):
            try:
                source, ref, full = resolve_report_source(reference, basis)
                if (_exact_numeric_support(source, ref, full, basis, selected)
                        and _retained_implementation(analysis, basis, selected)):
                    relevant_numeric = True
            except (ArtifactError, ValueError, OSError):
                continue
    if not relevant_numeric:
        missing.append("Perform and retain relevant numerical analysis for this exact model")
    for claim in _rows(document.get("claims")):
        route = claim.get("support_route")
        if route in {"qualified", "open"}:
            if not claim.get("qualification"):
                missing.append(f"State the unresolved scope of claim {claim.get('claim_id', '?')}")
            continue
        refs = claim.get("source_refs", [])
        if not refs:
            missing.append(f"Retain support for claim {claim.get('claim_id', '?')}")
        for reference in refs:
            try:
                resolve_report_source(reference, basis)
            except (ArtifactError, ValueError, OSError) as exc:
                missing.append(str(exc))
        if route == "numerical":
            supported = False
            for reference in refs:
                try:
                    source, ref, full = resolve_report_source(reference, basis)
                    supported |= _exact_numeric_support(source, ref, full, basis, selected)
                except (ArtifactError, ValueError, OSError):
                    pass
            if not supported:
                missing.append(f"Retain eligible exact numerical support for claim {claim.get('claim_id', '?')}")
        if route == "new_formal_result":
            checked = False
            for reference in refs:
                try:
                    source, ref, full = resolve_report_source(reference, basis)
                    checked |= bool(ref.get("phase") == "P3" and ref.get("family") == "theory_record" and method_identity(full) == selected
                                and isinstance(source, dict) and source.get("status") == "established"
                                and (source.get("justification") or {}).get("kind") in {"proof", "derivation"}
                                and (source.get("justification") or {}).get("artifacts"))
                except (ArtifactError, ValueError, OSError):
                    pass
            if not checked:
                missing.append(f"Complete P3 mathematical work for new formal claim {claim.get('claim_id', '?')}")
        if route == "established_result":
            check = claim.get("theorist_check") or {}
            if not (check.get("statement_used") and check.get("conditions") and check.get("model_fit")
                    and check.get("source_locator") and check.get("checked_by") == "theorist"
                    and method_identity(check.get("method_identity")) == selected and check.get("status") == "checked"
                    and check.get("check_ref")):
                missing.append(f"Retain the Theorist's cited-result applicability check for {claim.get('claim_id', '?')}")
    context = basis.get("problem_context") or {}
    context = context.get("document", context)
    outcomes = {(row.get("context_item_id"), row.get("context_item_revision")): row for row in _rows(document.get("expectation_outcomes"))}
    account = context.get("effective_account")
    expected_items = account.get("items", []) if isinstance(account, dict) else context.get("items")
    for item in _rows(expected_items):
        if item.get("topic") == "expectation" or item.get("kind") == "expectation":
            row = outcomes.get((item.get("item_id"), item.get("revision")))
            if not row or not row.get("explanation"):
                missing.append(f"Address frozen researcher expectation {item.get('item_id')}")
    return {"status": "interim" if missing else "complete", "missing_work": list(dict.fromkeys(missing)),
            "basis_scope": "Declared support and exact retained source integrity; scientific adequacy remains an expert judgment."}


def validate_technical_report(outputs: dict, basis: dict, *, artifact_roots: dict | None = None,
                              run_dir: Path | None = None, reader_report: bool = False) -> list[Finding]:
    document = outputs.get("p5.technical_report_candidate")
    if not isinstance(document, dict):
        return []
    findings = []
    family = "p5.technical_report_candidate"
    def issue(code, message, pointer="", *, details=None):
        findings.append(Finding(code, message, family, pointer, details=details or {}))
    anchors = document.get("section_anchors")
    declares_references = isinstance(anchors, dict) and "references" in anchors
    if reader_report and not declares_references:
        issue("report.references_boundary", "This captured report format requires section_anchors.references after all seven scientific sections",
              "/section_anchors/references")
    for reason in report_assembly_readiness(basis):
        issue("report.assembly_basis", reason)
    if method_identity(document) != method_identity(basis.get("method")):
        issue("report.model_mismatch", "The report must describe the exact selected model version", "/method_identity")
    context = basis.get("problem_context") or {}
    declared_context = document.get("problem_context_ref") or {}
    if document.get("authorized_context_items", []) != context.get("authorized_context_items", []):
        issue("report.context_authorization_mismatch", "Report context additions must equal the researcher's exact accepted snapshots", "/authorized_context_items")
    if (declared_context.get("revision") != context.get("revision")
            or declared_context.get("sha256") != context.get("sha256")):
        issue("report.context_mismatch", "The report must name the frozen problem-context revision and digest", "/problem_context_ref")
    for name in ("claims", "numerical_analysis", "expectation_outcomes", "prose_values"):
        for index, row in enumerate(_rows(document.get(name))):
            for key in ("source_refs", "evidence_refs", "exhibit_refs", "implementation_refs"):
                for position, reference in enumerate(row.get(key, [])):
                    try:
                        resolve_report_source(reference, basis)
                    except (ArtifactError, OSError, ValueError) as exc:
                        issue("report.source_unresolved", str(exc), f"/{name}/{index}/{key}/{position}")
            check_ref = (row.get("theorist_check") or {}).get("check_ref")
            if check_ref:
                try:
                    check, _, _ = resolve_report_source(check_ref, basis)
                    authored = row["theorist_check"]
                    if not isinstance(check, dict) or any(check.get(key) != authored.get(key) for key in ("checked_by", "status", "statement_used", "conditions", "model_fit", "source_locator", "method_identity")):
                        issue("report.theorist_check_mismatch", "The claimed Theorist check differs from its retained source", f"/{name}/{index}/theorist_check")
                except (ArtifactError, OSError, ValueError) as exc:
                    issue("report.source_unresolved", str(exc), f"/{name}/{index}/theorist_check/check_ref")
            if name == "claims" and row.get("support_route") == "numerical":
                valid = False
                for reference in row.get("source_refs", []):
                    try:
                        source, ref, full = resolve_report_source(reference, basis)
                        valid |= _exact_numeric_support(source, ref, full, basis, method_identity(basis.get("method")))
                    except (ArtifactError, OSError, ValueError):
                        pass
                if not valid:
                    issue("report.numeric_claim_unsupported", "A numerical claim needs actual retained numerical support for the exact model", f"/{name}/{index}/source_refs")
            if name == "prose_values":
                try:
                    reference = row.get("source_refs", [])[0]
                    value, ref, _ = resolve_report_scalar(reference, basis)
                    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or ref.get("phase") != "P4":
                        raise ArtifactError("A prose number must cite its exact retained P4 numerical value")
                    transform = row.get("transformation") or {"kind": "identity"}
                    if transform.get("kind") in {"scale", "scale_round"}:
                        value *= transform["scale"]
                    if transform.get("kind") in {"round", "scale_round"}:
                        value = round(value, transform["decimals"])
                    if row.get("reported_value") != value:
                        raise ArtifactError("The prose value differs from the retained result and declared presentation transformation")
                    numbers = [float(token) for token in re.findall(r"(?<![A-Za-z0-9_])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", row.get("text", ""))]
                    if row.get("reported_value") not in numbers:
                        raise ArtifactError("The authored prose number text does not contain the declared reported value")
                    if not row.get("presentation"):
                        raise ArtifactError("A numerical presentation must explain its rounding or transformation")
                except (ArtifactError, OSError, ValueError, IndexError, KeyError, TypeError) as exc:
                    issue("report.prose_value_mismatch", str(exc), f"/prose_values/{index}")
    roots = list((artifact_roots or {}).values()) + ([run_dir] if run_dir else [])
    if roots:
        try:
            primary = resolve_report_artifact(document.get("report_artifact") or {}, basis, roots=roots)
            text = primary.read_text(encoding="utf-8")
            if declares_references:
                try:
                    reference_boundary(text, anchors, CONTENT_SECTIONS)
                except ValueError as exc:
                    issue("report.references_boundary", str(exc), "/section_anchors/references")
            for name in ("claims", "prose_values"):
                for index, row in enumerate(_rows(document.get(name))):
                    if row.get("text") not in text or not row.get("anchor") or f'id="{row["anchor"]}"' not in text:
                        issue("report.prose_location", "The exact claim/value text and authored anchor must occur in the retained report source", f"/{name}/{index}")
            for pointer in report_required_artifacts(document, basis):
                resolve_report_artifact(pointer, basis, roots=roots)
        except (ArtifactError, OSError, ValueError, UnicodeError) as exc:
            issue("report.artifact_unresolved", str(exc), "/report_artifact")
    derived = derive_report_completion(document, basis, artifact_roots=artifact_roots)
    for index, claim in enumerate(_rows(document.get("claims"))):
        identifier = claim.get("claim_id", "?")
        if claim.get("support_route") == "new_formal_result" and any(f"new formal claim {identifier}" in item for item in derived["missing_work"]):
            issue("report.new_result_unestablished", "A new formal result requires completed P3 support; otherwise retain it as a qualified or open claim", f"/claims/{index}")
        if claim.get("support_route") == "established_result" and any(f"applicability check for {identifier}" in item for item in derived["missing_work"]):
            issue("report.cited_result_unchecked", "An established result needs its retained Theorist applicability check; unchecked conditions must remain qualified", f"/claims/{index}")
    if document.get("completion") and document["completion"] != derived:
        missing_work = "; ".join(derived["missing_work"]) or "None"
        issue("report.completion_mismatch",
              "Completion must equal the harness-derived support disposition. "
              f"Expected status: {derived['status']}. Missing work: {missing_work}. "
              "See details.expected_completion for the exact metadata; preserve unresolved scientific work honestly.",
              "/completion", details={"expected_completion": derived})
    if reader_report and roots and not findings:
        # Validate the same linked documents and offline assets the researcher
        # receives. A declared file's digest alone does not make its links work.
        try:
            export_roots = dict(artifact_roots or {})
            if run_dir:
                export_roots["retained_run"] = run_dir
            export_technical_report(document, basis, generation_ref={}, artifact_roots=export_roots,
                                    exported_at="", validate_materials=True)
        except (ArtifactError, OSError, ValueError, UnicodeError, subprocess.TimeoutExpired) as exc:
            issue("report.portable_unresolved",
                  f"{exc}. Repair the owned report or declare its exact retained linked dependencies, refresh their digests, "
                  "and call validate_artifacts again.", "/report_artifact")
    return findings


def exact_report_review_status(document: dict, generation_ref: dict, review_packets: list[dict] | None = None) -> str:
    """Only completed committed independent reviews attach to these exact bytes."""
    for packet in review_packets or []:
        target = packet.get("target") or {}
        if (packet.get("independent_review_completed") is True
                and target.get("generation_id") == generation_ref.get("generation_id")
                and target.get("content_sha256") == (generation_ref.get("content_sha256") or generation_ref.get("sha256"))
                and target.get("report_artifact_sha256") == (document.get("report_artifact") or {}).get("sha256")):
            return "independently_reviewed"
    return "not_independently_reviewed"


def completed_report_review_packets(project_dir: Path) -> list[dict]:
    """Return packets only when the exact independent review was committed."""
    from .p5_review_packet import read_review_packet, validate_review_packet_outputs
    result = []
    project_dir = Path(project_dir)
    for manifest in (project_dir / "runs").glob("*/review-packet/manifest.json"):
        run_dir = manifest.parent.parent
        try:
            run = read_json(run_dir / "run.json") or {}
            if run.get("state") != "published" or run.get("phase") != "P5":
                continue
            packet = read_review_packet(manifest.parent)
            if packet.get("packet_version") != "2.0.0":
                continue
            phase_dir = project_dir / "branches" / run["branch_id"] / "phases/p5"
            matches = [package for package in committed_packages(phase_dir) if package.get("run_id") == run.get("run_id")]
            if len(matches) != 1:
                continue
            reference = matches[0].get("records", {}).get("outside_review")
            if not reference:
                continue
            review = read_generation(phase_dir, "outside_review", reference)
            if not validate_review_packet_outputs(manifest.parent, {"p5.outside_review": review}):
                result.append({**packet, "independent_review_completed": True})
        except (ArtifactError, OSError, ValueError, TypeError, KeyError):
            continue
    return result


def export_technical_report(document: dict, basis: dict, *, generation_ref: dict, artifact_roots: dict,
                            exported_at: str, review_packets: list[dict] | None = None, node_executable: str | None = None,
                            print_material_id: str | None = None, validate_materials: bool = False,
                            html_download_base_url: str | None = None) -> bytes:
    """Render immutable sources; only the hosted view uses HTTP HTML downloads."""
    basis = report_context_basis(basis, document)
    roots = list(artifact_roots.values())
    primary = resolve_report_artifact(document.get("report_artifact") or {}, basis, roots=roots)
    markdown = primary.read_bytes().decode("utf-8") if validate_materials else primary.read_text(encoding="utf-8")
    try:
        reference_boundary(markdown, document.get("section_anchors") or {}, CONTENT_SECTIONS)
    except ValueError as exc:
        raise ArtifactError(str(exc)) from exc
    completion = derive_report_completion(document, basis, artifact_roots=artifact_roots)
    digest = sha256_file(primary)
    review_status = exact_report_review_status(document, generation_ref, review_packets)
    reviewed = review_status == "independently_reviewed"
    app_root = Path(__file__).resolve().parents[2]
    script = app_root / "web/runtime/export-report.mjs"
    if not script.is_file():
        script = app_root / "web/scripts/export-report.mjs"
    report_pointer = document.get("report_artifact") or {}
    materials = report_required_artifacts(document, basis)
    if print_material_id is not None:
        selected = [pointer for pointer in materials if pointer.get("artifact_id") == print_material_id]
        if (not isinstance(print_material_id, str) or not print_material_id or len(selected) != 1
                or print_material_id == report_pointer.get("artifact_id")):
            raise ArtifactError("Choose one declared supplementary Markdown material for printing")
        selected_path = resolve_report_artifact(selected[0], basis, roots=roots)
        selected_media = selected[0].get("media_type") or mimetypes.guess_type(selected_path.name)[0]
        if selected_media != "text/markdown":
            raise ArtifactError("Only a declared Markdown material can be printed separately")
    request = {"markdown": markdown, "title": document.get("title", "Technical report"), "asset_files": {},
               "validate_materials": validate_materials,
               "section_anchors": document.get("section_anchors") or {}, "print_material_id": print_material_id,
               "primary_path": (document.get("artifact_authored_paths") or {}).get(report_pointer.get("artifact_id"))
                               or report_pointer.get("authored_path") or primary.name,
               "primary_paths": list(dict.fromkeys(value for value in
                   ((document.get("artifact_authored_paths") or {}).get(report_pointer.get("artifact_id")),
                    report_pointer.get("authored_path"), report_pointer.get("path"),
                    report_pointer.get("artifact_path"), report_pointer.get("uri"),
                    report_pointer.get("artifact_id"), primary.name) if isinstance(value, str) and value))}
    notation_pointer = document.get("notation_snapshot")
    if isinstance(notation_pointer, dict):
        from .notation import render_notation
        notation_path = resolve_report_artifact(notation_pointer, basis, roots=roots)
        notation_view = read_json(notation_path)
        notation_markdown = resolve_report_artifact(notation_pointer.get("markdown") or {}, basis, roots=roots).read_text(encoding="utf-8")
        if not isinstance(notation_view, dict) or render_notation(notation_view) != notation_markdown:
            raise ArtifactError("The report's readable notation differs from its retained definitions")
        request["notation_markdown"] = notation_markdown
    for pointer in materials:
        path = resolve_report_artifact(pointer, basis, roots=roots)
        media = pointer.get("media_type") or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        source = {"path": str(path.resolve()), "media_type": media, "artifact_id": pointer.get("artifact_id"),
                  "sha256": pointer.get("sha256") or pointer.get("artifact_sha256"),
                  "authored_path": pointer.get("authored_path") or pointer.get("path")}
        if html_download_base_url and media == "text/html" and pointer.get("artifact_id"):
            source["download_url"] = html_download_base_url + "&material_id=" + quote(pointer["artifact_id"], safe="")
        for key in (pointer.get("authored_path"), pointer.get("path"), pointer.get("artifact_path"), pointer.get("uri"), pointer.get("artifact_id")):
            if key:
                if not isinstance(key, str):
                    raise ArtifactError("Portable report material aliases must be single nonempty strings; each artifact_authored_paths value must name one relative path, not an array")
                request["asset_files"][key] = source
    if node_executable is None:
        from .math_validation import _node_executable
        node_executable = _node_executable()
    process = subprocess.run([str(node_executable), str(script)], input=json.dumps(request), capture_output=True,
                             text=True, encoding="utf-8", timeout=60, check=False)
    if process.returncode:
        stderr = process.stderr.strip()
        error = re.search(r"^[A-Za-z]*Error: (.+)$", stderr, re.MULTILINE)
        raise ArtifactError("Portable report rendering failed: " + (error[1] if error else stderr[:1000]))
    rendered = json.loads(process.stdout)
    metadata = {"generation_id": generation_ref.get("generation_id"), "content_sha256": generation_ref.get("content_sha256") or generation_ref.get("sha256"),
                "report_artifact_sha256": digest, "method_identity": document.get("method_identity"), "completion": completion,
                "review_status": review_status, "exported_at": exported_at,
                "print_material_id": print_material_id, "print_scopes": rendered.get("print_scopes")}
    if isinstance(notation_pointer, dict):
        metadata["notation"] = {"snapshot_sha256": notation_pointer["sha256"], "snapshot": notation_view}
    identity = method_identity(document)
    banner = (f"<aside><strong>{html.escape(completion['status'].capitalize())} technical report</strong>"
              f"<p>This version {'has' if reviewed else 'has not'} been independently reviewed.</p>"
              + ("<ul>" + "".join("<li>" + html.escape(item) + "</li>" for item in completion["missing_work"]) + "</ul>" if completion["missing_work"] else "")
              + f"<details><summary>Source details</summary><p>Report generation: {html.escape(str(metadata['generation_id']))}. "
              f"Model: {html.escape(str(identity[0]))}, version {identity[1]}. Exported: {html.escape(exported_at)}.</p></details></aside>")
    metadata_json = json.dumps(metadata).replace("<", "\\u003c")
    support = html.escape(json.dumps(report_submitted_source_materials(document, basis), ensure_ascii=False, indent=2))
    return ("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            + "<title>" + html.escape(request["title"]) + "</title><style>" + rendered["css"]
            + "body{box-sizing:border-box;max-width:54rem;margin:2rem auto;padding:0 1.4rem;color:#20242c;font:17px/1.65 Georgia,serif;overflow-wrap:anywhere}img,svg{max-width:100%}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd0d6;padding:.5rem}aside{background:#eef2f5;padding:1rem;font:14px/1.5 sans-serif}pre{overflow:auto}h1,h2,h3{line-height:1.25}"
            + ".report-table,.report-equation{display:block;max-width:100%;overflow-x:auto}.report-table{overflow-wrap:normal}.report-equation{overflow-y:hidden;padding:.2rem 0}.report-equation .katex-display>.katex{min-width:max-content}.report-table:focus-visible,.report-equation:focus-visible{outline:2px solid #2c5c87;outline-offset:3px}"
            + "@media print{body{max-width:none;margin:0;font-size:11pt}aside{background:white;border:1px solid #999}h1,h2,h3,p:has(+.report-table){break-after:avoid}figure,table,.katex-display{break-inside:avoid}.report-table,.report-equation{overflow:visible;max-width:none}.report-equation .katex-display>.katex{min-width:0}a{color:inherit}img{max-height:24cm}}"
            + rendered.get("print_css", "")
            + "</style><body>" + banner + rendered["html"]
            + '<details class="report-provenance"><summary>Exact scientific sources and expectation revisions</summary><pre>' + support + "</pre></details>"
            + '<script type="application/json" id="report-provenance">' + metadata_json + "</script></body></html>").encode("utf-8")
