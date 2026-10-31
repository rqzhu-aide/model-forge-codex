"""Frozen, source-qualified notation views for scientific accounts.

The scientific package owns its definitions. These complete views are generated
supporting artifacts, never a mutable project registry or a freshness gate.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from .records import (ArtifactError, _segment, committed_packages, read_generation,
                      source_artifact_path)
from .storage import read_json, sha256_bytes, sha256_file, write_json_atomic


CAPABILITY = "project_notation_v1"
LEAD_FAMILIES = {
    "P1": ("research_basis",), "P2": ("catalog_assessment",),
    "P3": ("theory_record", "complete_theory"),
    "P4": ("empirical_synthesis", "empirical_synthesis_candidate"),
    "P5": ("technical_report", "technical_report_candidate"),
}
SOURCE_FIELDS = ("phase", "branch", "family", "generation_id", "content_sha256")


def notation_enabled(catalog, phase=None) -> bool:
    phases = (phase,) if phase else LEAD_FAMILIES
    return any(CAPABILITY in (read_json(catalog.root / "contracts" / "phases" / f"{item}.json") or {}).get("capabilities", [])
               for item in phases)


def digest(document) -> str:
    return sha256_bytes(json.dumps(document, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode())


def _pointer(document, pointer):
    if pointer == "":
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ArtifactError("A notation definition needs an exact JSON Pointer")
    try:
        for part in pointer[1:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            document = document[int(part)] if isinstance(document, list) else document[part]
        return document
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise ArtifactError("A notation definition's source field is unavailable") from exc


def _committed(project_dir: Path, reference: dict):
    """Verify visibility through package ancestry, excluding orphan generations."""
    reference = dict(reference)
    if reference.get("content_sha256") and reference.get("sha256") and reference["content_sha256"] != reference["sha256"]:
        raise ArtifactError("The notation source contains conflicting generation digests")
    reference["content_sha256"] = reference.get("content_sha256") or reference.get("sha256")
    if (reference.get("phase") not in LEAD_FAMILIES
            or not all(isinstance(reference.get(key), str) and reference[key]
                       for key in ("branch", "family", "generation_id", "content_sha256"))):
        raise ArtifactError("The notation source needs an exact scientific generation and digest")
    directory = project_dir / "branches" / _segment(reference["branch"]) / "phases" / _segment(reference["phase"]).lower()
    found = None
    for package in committed_packages(directory):
        candidate = package["records"].get(reference["family"])
        if candidate and all(candidate.get(key) == reference.get(key)
                             for key in ("generation_id", "content_sha256")):
            if any(reference.get(key) is not None and reference.get(key) != candidate.get(key)
                   for key in ("run_id", "stage_id", "package_id")):
                raise ArtifactError("The notation source's producing account identity does not match its committed generation")
            found = candidate
            break
    if found is None:
        raise ArtifactError("The notation source is not a committed scientific generation")
    return read_generation(directory, reference["family"], found), {**reference, **found}


def _verify_definition(project_dir: Path, reference: dict):
    if not reference.get("output_id"):
        document, _ = _committed(project_dir, reference)
        return _pointer(document, reference.get("pointer"))
    phase, family = reference["output_id"].split(".", 1)
    directory = project_dir / "branches" / _segment(reference["branch"]) / "phases" / phase
    candidates = [package["records"][family] for package in committed_packages(directory)
                  if family in package["records"] and package["records"][family].get("run_id") == reference.get("run_id")
                  and package["records"][family].get("stage_id") == reference.get("stage_id")]
    if len(candidates) != 1:
        raise ArtifactError("A notation definition no longer resolves to its exact committed scientific output")
    document = read_generation(directory, family, candidates[0])
    value = _pointer(document, reference.get("pointer"))
    if digest(value) != reference.get("field_sha256"):
        raise ArtifactError("A notation definition differs from its retained scientific source field")
    return value


def retained_notation(project_dir: Path, source_ref: dict) -> dict | None:
    """Read the selected account's own final view, without a latest fallback."""
    document, source_ref = _committed(Path(project_dir), source_ref)
    pointer = document.get("notation_snapshot") if isinstance(document, dict) else None
    if pointer is None:
        return None
    if not isinstance(pointer, dict):
        raise ArtifactError("The account's retained notation pointer is invalid")
    path = source_artifact_path(Path(project_dir), source_ref, pointer)
    snapshot = read_json(path)
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != "1.0.0" or not isinstance(snapshot.get("entries"), list):
        raise ArtifactError("The retained notation view is unreadable")
    markdown = pointer.get("markdown")
    if not isinstance(markdown, dict):
        raise ArtifactError("The retained notation view has no matching readable file")
    markdown_path = source_artifact_path(Path(project_dir), source_ref, markdown)
    if markdown_path.read_text(encoding="utf-8") != render_notation(snapshot):
        raise ArtifactError("The readable notation file differs from its structured view")
    verified = {}
    entries = {entry.get("entry_id"): entry for entry in snapshot["entries"]}
    for entry in snapshot["entries"]:
        references = [*entry.get("source_refs", []), entry.get("adoption_ref")]
        if entry.get("account_scope_ref") is not None:
            references.append(entry["account_scope_ref"])
        for reference in references:
            if not isinstance(reference, dict):
                raise ArtifactError("An adopted notation entry has no exact adoption source")
            key = digest(reference)
            if key not in verified:
                verified[key] = _verify_definition(Path(project_dir), reference)
        if entry.get("account_scope_ref") is not None:
            adoption = verified[digest(entry["adoption_ref"])]
            previous_ref = adoption.get("replaces") if isinstance(adoption, dict) else None
            previous = entries.get(previous_ref.get("entry_id")) if isinstance(previous_ref, dict) else None
            if previous_ref and (previous is None or previous.get("quantity_key") != entry.get("quantity_key")
                                 or previous.get("scope") != entry.get("scope")):
                raise ArtifactError("The account-local notation scope has no exact earlier definition")
            expected = (previous.get("account_scope_ref") or previous["adoption_ref"]) if previous else entry["adoption_ref"]
            if entry.get("scope", {}).get("kind") != "account" or entry["account_scope_ref"] != expected:
                raise ArtifactError("The account-local notation scope differs from its exact authored adoption")
    return snapshot


def account_notation_source(project_dir: Path, source_ref: dict) -> dict | None:
    """Find the final Lead view in this source's committed package only."""
    document, verified = _committed(Path(project_dir), source_ref)
    if isinstance(document, dict) and document.get("notation_snapshot"):
        return {key: verified[key] for key in (*SOURCE_FIELDS, "run_id", "stage_id", "package_id") if key in verified}
    directory = Path(project_dir) / "branches" / verified["branch"] / "phases" / verified["phase"].lower()
    for package in committed_packages(directory):
        original = package["records"].get(verified["family"])
        if not original or any(original.get(key) != verified.get(key) for key in ("generation_id", "content_sha256")):
            continue
        for family in LEAD_FAMILIES[verified["phase"]]:
            pointer = package["records"].get(family)
            if pointer is None:
                continue
            account = read_generation(directory, family, pointer)
            if isinstance(account, dict) and account.get("notation_snapshot"):
                return {"phase": verified["phase"], "branch": verified["branch"], "family": family, **pointer}
        return None
    return None


def _allowed(phase):
    return {"P1"} if phase == "P1" else ({"P1", "P2"} if phase == "P2" else
            {"P1", "P2", "P3", "P4"} | ({"P5"} if phase == "P5" else set()))


def _same_method(scope: dict, method: dict | None):
    actual = scope.get("method_identity")
    if actual is None or method is None:
        return True
    selected = method.get("identity") or method.get("method_identity") or method
    return all(actual.get(key) == selected.get(key) for key in ("stable_id", "definition_sha256"))


def _method_identity(method):
    selected = (method or {}).get("identity") or (method or {}).get("method_identity") or method or {}
    return {key: selected[key] for key in ("stable_id", "definition_sha256") if key in selected}


def collect_notation_inputs(project_dir: Path, records: list[dict], method: dict | None, phase: str) -> dict:
    """Merge only complete views belonging to already-admitted scientific inputs."""
    entries, sources, seen_entries, seen_sources = [], [], {}, set()
    present = {(row["phase"], row["branch"], row["family"]) for row in records}
    for ref in records:
        families = LEAD_FAMILIES.get(ref["phase"], ())
        if ref["phase"] not in _allowed(phase) or ref["family"] not in families:
            continue
        # Canonical aliases are identical publication bytes, not distinct sources.
        if any((ref["phase"], ref["branch"], earlier) in present
               for earlier in families[:families.index(ref["family"])]):
            continue
        snapshot = retained_notation(project_dir, ref)
        if snapshot is None:
            continue  # Historical prose is never parsed into invented definitions.
        source = {key: ref[key] for key in SOURCE_FIELDS}
        source["pointer"] = "/notation_snapshot"
        source_document, _ = _committed(project_dir, ref)
        source["snapshot_sha256"] = source_document["notation_snapshot"]["sha256"]
        source["entry_ids"] = [entry["entry_id"] for entry in snapshot["entries"]]
        source["active_entry_ids"] = [entry["entry_id"] for entry in snapshot["entries"]
                                      if entry.get("status", "active") == "active"]
        source_key = digest(source)
        if source_key not in seen_sources:
            sources.append(source)
            seen_sources.add(source_key)
        for entry in snapshot["entries"]:
            scope = entry.get("scope") or {}
            defining_phase = (entry.get("adoption_ref") or {}).get("phase") or scope.get("phase")
            if defining_phase and defining_phase not in _allowed(phase):
                continue
            if scope.get("kind") in {"method", "account"} and not _same_method(scope, method):
                continue
            key = entry.get("entry_id")
            previous = seen_entries.get(key)
            if previous is not None:
                # An explicit owning retirement is retained when an older
                # consumer still carries this exact entry as active. Each
                # source's own active view remains recorded above.
                definition = {k: v for k, v in entry.items() if k != "status"}
                prior = {k: v for k, v in previous.items() if k != "status"}
                if definition != prior:
                    raise ArtifactError("An inherited notation identity has inconsistent source definitions")
                if entry.get("status", "active") == "retired":
                    previous["status"] = "retired"
                continue
            copied = deepcopy(entry)
            entries.append(copied)
            seen_entries[key] = copied
    replaced = {entry["replaces"]["entry_id"] for entry in entries
                if entry.get("status", "active") == "active" and isinstance(entry.get("replaces"), dict)}
    for entry in entries:
        if entry["entry_id"] in replaced:
            entry["status"] = "retired"
    return {"schema_version": "1.0.0", "sources": sources, "entries": entries}


def frozen_notation(basis: dict) -> dict | None:
    reference = basis.get("notation")
    if reference is None:
        return None
    document = (read_json(Path(reference["snapshot_path"])) if reference.get("snapshot_path")
                else reference.get("document"))
    if not isinstance(document, dict) or digest(document) != reference.get("sha256"):
        raise ArtifactError("The run's frozen notation changed or disappeared")
    if reference.get("markdown_path"):
        path = Path(reference["markdown_path"])
        if not path.is_file() or sha256_file(path) != reference.get("markdown_sha256") or path.read_text(encoding="utf-8") != render_notation(document):
            raise ArtifactError("The run's readable frozen notation changed or disappeared")
    return deepcopy(document)


def freeze_notation_inputs(run_dir: Path, basis: dict):
    snapshot = frozen_notation(basis)
    if snapshot is None:
        return
    path = run_dir / "inputs" / "notation.json"
    write_json_atomic(path, snapshot)
    readable = path.with_suffix(".md")
    readable.write_text(render_notation(snapshot), encoding="utf-8", newline="\n")
    basis["notation"] = {"snapshot_path": str(path), "sha256": digest(snapshot),
                         "markdown_path": str(readable), "markdown_sha256": sha256_file(readable)}


def render_notation(snapshot: dict, *, heading="Notation", level=1) -> str:
    lines = [f"{'#' * level} {heading}", "", "Definitions retain the scope and scientific sources of the account that adopted them.", ""]
    entries = [entry for entry in snapshot.get("entries", []) if entry.get("status", "active") == "active"]
    if not entries:
        lines += ["No active mathematical notation is recorded for this account.", ""]
    for entry in entries:
        scope = entry["scope"]
        label = {"study": "Shared study", "method": "Method", "account": "Account"}.get(scope["kind"], scope["kind"])
        if scope.get("kind") == "account":
            phase_name = {"P3": "Theory", "P4": "Numerical evaluation", "P5": "Report"}.get(scope.get("phase"), scope.get("phase", "Account"))
            label = phase_name + (": " + scope["section"] if scope.get("section") else " account")
        lines += [f"<a id=\"{entry['entry_id']}\"></a>", f"{'#' * (level + 1)} \\({entry['symbol_latex']}\\)", "", f"Scope: {label}", "",
                  entry["definition_markdown"], "", entry["meaning_markdown"], ""]
        mapping = entry.get("source_symbol_mapping")
        if mapping:
            lines += [f"Source correspondence: \\({mapping['source_symbol_latex']}\\) to \\({entry['symbol_latex']}\\).",
                      "", mapping["explanation_markdown"], ""]
    return "\n".join(lines)


def validate_notation_updates(catalog, document):
    """Check authored shape before generated retention touches nested fields."""
    from jsonschema import Draft202012Validator
    schema = catalog.schema_doc("notation-updates.schema.json")
    validator = Draft202012Validator(schema, registry=catalog._registry)
    error = next(validator.iter_errors(document.get("notation_updates")), None)
    if error is not None:
        parts = [str(part).replace("~", "~0").replace("/", "~1") for part in error.absolute_path]
        pointer = "/notation_updates" + ("/" + "/".join(parts) if parts else "")
        raise ArtifactError(f"Notation updates do not match the frozen schema at {pointer}: {error.message}")


def _resolve_source(project_dir, run_dir, basis, reference, current_documents, *, incoming=False):
    pointer = reference.get("pointer")
    output_id = reference.get("output_id")
    family = reference.get("family") or (output_id.split(".", 1)[-1] if output_id else None)
    first = pointer.split("/", 2)[1].replace("~1", "/").replace("~0", "~") if isinstance(pointer, str) and pointer.startswith("/") else None
    if first == "notation_updates" or first == "notation_snapshot" and (not incoming or output_id):
        raise ArtifactError("A notation definition must cite its scientific field, not notation updates or a generated view")
    # Restricted researcher input is not a scientific definition source.
    if (family in {"attention_items", "phase2_handoff", "decision", "review_issue_ledger"}
            or any(part in str(pointer).split("/") for part in ("attention_items", "authorized_context_items", "researcher_answers", "instructions", "phase2_preparation"))):
        raise ArtifactError("Restricted researcher directions cannot supply shared notation")
    if output_id:
        if output_id not in current_documents:
            raise ArtifactError("A notation addition cites an unavailable scientific output")
        document, stage_id = current_documents[output_id]
        if not pointer:
            raise ArtifactError("A current notation definition must cite a scientific field, not its generated view")
        _source_audience(project_dir, run_dir, reference, output_id)
        value = _shared_pointer(document, pointer)
        _shared_scientific_field(value)
        return {"phase": output_id.split(".")[0].upper(), "branch": basis.get("basis_branch"),
                "run_id": run_dir.name, "stage_id": stage_id, "output_id": output_id,
                "pointer": pointer, "field_sha256": digest(value)}
    candidates = [row for row in basis.get("records", [])
                  if all(reference.get(key) == row.get(key) for key in SOURCE_FIELDS)]
    if len(candidates) != 1:
        raise ArtifactError("A notation addition cites a source outside the admitted frozen scientific inputs")
    row = candidates[0]
    document, _ = _committed(project_dir, row)
    _source_audience(project_dir, run_dir, row, row["phase"].lower() + "." + row["family"])
    _shared_scientific_field(_shared_pointer(document, pointer))
    return {key: reference[key] for key in (*SOURCE_FIELDS, "pointer")}


def _restricted_audience(value):
    roles = {"research_lead", "theorist", "data_analyst"}
    return (isinstance(value, list) and bool(value) and bool(set(value) & roles)
            and not roles.issubset(set(value)) and "user" not in value
            and not any(str(item) in {"p1", "p2", "p3", "p4", "p5"} for item in value))


def _shared_pointer(document, pointer):
    """Audience on an enclosing object governs its scalar scientific fields."""
    if not isinstance(pointer, str) or pointer and not pointer.startswith("/"):
        raise ArtifactError("A notation definition needs an exact JSON Pointer")
    current = document
    parts = pointer[1:].split("/") if pointer else []
    for part in [*parts, None]:
        if isinstance(current, dict) and _restricted_audience(current.get("audience")):
            raise ArtifactError("A restricted-audience source cannot supply a shared notation definition")
        if part is not None:
            current = _pointer(current, "/" + part)
    return current


def _source_audience(project_dir, run_dir, reference, output_id):
    source_run = project_dir / "runs" / _segment(reference["run_id"]) if reference.get("run_id") else run_dir
    contract = read_json(source_run / "contracts/contracts/phases" / (output_id.split(".")[0].upper() + ".json")) or {}
    for stage in contract.get("role_stages", []):
        metadata = (stage.get("artifact_contracts") or {}).get(output_id) or {}
        if _restricted_audience(metadata.get("audience")):
            raise ArtifactError("The source output contract restricts this material's audience")


def _shared_scientific_field(value):
    if isinstance(value, dict):
        if any(key in value for key in ("phase2_preparation", "attention_items", "authorized_context_items", "researcher_answers", "notation_updates", "notation_snapshot")):
            raise ArtifactError("A notation definition must select its shared scientific field without restricted directions or answers")
        if _restricted_audience(value.get("audience")):
            raise ArtifactError("A restricted-audience source cannot supply a shared notation definition")
        for child in value.values():
            _shared_scientific_field(child)
    elif isinstance(value, list):
        for child in value:
            _shared_scientific_field(child)


def _scope_owned(scope, phase, branch, family, method):
    kind = scope.get("kind")
    if kind == "study":
        return phase == "P1"
    if kind == "method":
        return phase == "P2" and bool(scope.get("method_identity"))
    if kind == "account":
        return (phase in {"P3", "P4", "P5"} and scope.get("phase") == phase
                and scope.get("branch") == branch and scope.get("account_family") in LEAD_FAMILIES[phase]
                and _same_method(scope, method))
    return False


def _known_method_identities(project_dir, basis, current_documents):
    identities = set()
    def visit(value):
        if isinstance(value, dict):
            identity = value.get("identity") or value.get("method_identity")
            if (isinstance(identity, dict) and identity.get("stable_id") and identity.get("definition_sha256")
                    and type(identity.get("version")) is int and identity["version"] > 0):
                identities.add((identity["stable_id"], identity["definition_sha256"]))
            for key, child in value.items():
                if key not in {"notation_updates", "notation_snapshot"}:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    for document, _ in current_documents.values():
        visit(document)
    for reference in basis.get("records", []):
        if reference.get("phase") == "P2" and reference.get("family") in {"method_catalog", "method_changes", "lead_proposal", "theory_proposals", "empirical_proposals"}:
            document, _ = _committed(project_dir, reference)
            visit(document)
    return identities


def build_account_notation(project_dir: Path, run_dir: Path, phase: str, branch: str,
                           stage_id: str, document: dict, family: str, basis: dict,
                           current_documents: dict) -> dict:
    """Apply a Lead's owned additions to the exact incoming complete views."""
    updates = document.get("notation_updates")
    if not isinstance(updates, dict):
        raise ArtifactError("This Lead account requires notation_updates, with empty arrays when no updates are needed")
    snapshot = frozen_notation(basis) or {"schema_version": "1.0.0", "sources": [], "entries": []}
    incoming = deepcopy(snapshot)
    for source in updates.get("incoming_sources", []):
        # A committed incoming view can identify itself through its snapshot;
        # entry definitions must still cite the scientific fields that own it.
        _resolve_source(project_dir, run_dir, basis, source, current_documents, incoming=True)
    entries = snapshot["entries"]
    entry_refs = {}
    # Each admitted source view supplies entry identities under its own digest.
    for source in incoming.get("sources", []):
        for entry in entries:
            if entry["entry_id"] not in source.get("entry_ids", []):
                continue
            entry_refs[(source.get("snapshot_sha256"), entry["entry_id"])] = entry
    entry_refs.update({(digest(incoming), entry["entry_id"]): entry for entry in entries})
    account = {"phase": phase, "branch": branch, "run_id": run_dir.name,
               "stage_id": stage_id, "family": family}
    if basis.get("method"):
        account["method_identity"] = deepcopy(basis["method"].get("identity") or basis["method"].get("method_identity") or basis["method"])
    explicit, symbols, adopted_entries = set(), {}, []
    for index, update in enumerate(updates.get("entries", [])):
        if "account_scope_ref" in update:
            raise ArtifactError("The harness owns the exact account-local notation scope reference")
        scope = deepcopy(update.get("scope") or {})
        if scope.get("kind") == "account" and basis.get("method"):
            scope.setdefault("method_identity", _method_identity(basis["method"]))
        if not _scope_owned(scope, phase, branch, family, basis.get("method")):
            raise ArtifactError("This phase cannot replace canonical notation owned by another scientific account")
        if scope.get("kind") == "method":
            identity = scope["method_identity"]
            if (identity.get("stable_id"), identity.get("definition_sha256")) not in _known_method_identities(project_dir, basis, current_documents):
                raise ArtifactError("A notation method scope must match an exact admitted candidate definition")
        key = (digest(scope), update.get("quantity_key"))
        if key in explicit:
            raise ArtifactError("Notation updates contain a duplicate quantity key in the same explicit scope")
        explicit.add(key)
        symbol_key = (digest(scope), update.get("symbol_latex"))
        if symbol_key in symbols and symbols[symbol_key] != update.get("quantity_key"):
            raise ArtifactError("This account binds one symbol to different quantities in the same explicit scope")
        symbols[symbol_key] = update.get("quantity_key")
        previous = None
        if update.get("replaces"):
            ref = update["replaces"]
            previous = entry_refs.get((ref.get("snapshot_sha256"), ref.get("entry_id")))
            if previous is None or previous.get("quantity_key") != update.get("quantity_key") or previous.get("scope") != scope:
                raise ArtifactError("A notation clarification must name its earlier entry and preserve its quantity and scope")
            if previous.get("status", "active") != "active":
                raise ArtifactError("A notation clarification must name the current active definition; a retired entry cannot be replaced again")
            previous["status"] = "retired"
        elif scope.get("kind") != "account" and any(entry.get("status", "active") == "active" and entry.get("scope") == scope
                 and entry.get("quantity_key") == update.get("quantity_key") for entry in entries):
            raise ArtifactError("Changing an adopted quantity requires its explicit earlier entry reference")
        if scope.get("kind") in {"study", "method"} and any(
                entry.get("status", "active") == "active" and entry.get("scope") == scope
                and entry.get("symbol_latex") == update.get("symbol_latex")
                and entry.get("quantity_key") != update.get("quantity_key") for entry in entries):
            raise ArtifactError("This account binds one symbol to different quantities in the same explicit scope")
        refs = update.get("source_refs") or []
        if not refs:
            raise ArtifactError("An adopted notation entry needs an exact scientific definition source")
        resolved = [_resolve_source(project_dir, run_dir, basis, ref, current_documents) for ref in refs]
        adoption = {**account, "output_id": phase.lower() + "." + family,
                    "pointer": f"/notation_updates/entries/{index}", "field_sha256": digest(update)}
        item = {**deepcopy(update), "entry_id": "notation." + digest(adoption)[:24],
                "scope": scope,
                "definition_ref": resolved[0], "source_refs": resolved,
                "adoption_ref": adoption, "status": "active"}
        if scope.get("kind") == "account":
            item["account_scope_ref"] = deepcopy(
                (previous.get("account_scope_ref") or previous["adoption_ref"]) if previous else adoption)
        mapping = update.get("source_symbol_mapping")
        if mapping:
            ref = mapping["source_entry_ref"]
            original = entry_refs.get((ref.get("snapshot_sha256"), ref.get("entry_id")))
            if original is None or original["symbol_latex"] != mapping.get("source_symbol_latex"):
                raise ArtifactError("A source-symbol mapping must name an exact admitted notation entry")
        entries.append(item)
        adopted_entries.append(item)
    retired_entries = []
    for retirement in updates.get("retirements", []):
        ref = retirement["entry_ref"]
        entry = entry_refs.get((ref.get("snapshot_sha256"), ref.get("entry_id")))
        if entry is None or not _scope_owned(entry["scope"], phase, branch, family, basis.get("method")):
            raise ArtifactError("A notation retirement must name an admitted entry owned by this scientific phase")
        if entry.get("status", "active") != "active":
            raise ArtifactError("A notation retirement must name the current active definition; a retired entry cannot be retired again")
        entry["status"] = "retired"
        retired_entries.append(entry)
    corrections = (basis.get("problem_context") or {}).get("notation_correction_refs", [])
    correction_keys = {(row.get("context_id"), row.get("revision"), row.get("sha256")) for row in corrections}
    context = basis.get("problem_context") or {}
    correction_items = [*context.get("items", []), *context.get("authorized_context_items", [])]
    seen_corrections = set()
    for disposition in updates.get("correction_dispositions", []):
        ref = disposition["correction_ref"]
        key = (ref.get("context_id"), ref.get("revision"), ref.get("sha256"))
        if key not in correction_keys or key in seen_corrections:
            raise ArtifactError("A notation correction disposition must name one exact admitted saved correction revision")
        if disposition.get("disposition") == "adopted":
            item = next((row for row in correction_items if row.get("topic") == "notation_correction"
                         and (row.get("item_id"), row.get("revision"), digest(row)) == key), None)
            sources = [source for source in (item or {}).get("source_refs", []) if source.get("kind") == "notation_entry"]
            if len(sources) != 1:
                raise ArtifactError("An adopted correction needs its exact admitted saved item and definition source")
            corrected = resolve_notation_entry(project_dir, sources[0])["entry"]
            scope = corrected["scope"]
            if not _scope_owned(scope, phase, branch, family, basis.get("method")):
                raise ArtifactError("This phase cannot adopt a correction to another phase's canonical notation")
            changed = [entry for entry in adopted_entries if entry.get("quantity_key") == corrected.get("quantity_key")
                       and entry.get("scope") == scope and entry.get("adoption_ref", {}).get("run_id") == run_dir.name
                       and entry.get("adoption_ref", {}).get("stage_id") == stage_id]
            retired = [entry for entry in retired_entries if entry.get("quantity_key") == corrected.get("quantity_key")
                       and entry.get("scope") == scope]
            if scope.get("kind") == "account":
                origin = corrected.get("account_scope_ref") or corrected["adoption_ref"]
                changed = [entry for entry in changed if entry.get("account_scope_ref") == origin]
                retired = [entry for entry in retired if (entry.get("account_scope_ref") or entry["adoption_ref"]) == origin]
            if not changed and not retired:
                raise ArtifactError("An adopted correction requires an actual update to its owned quantity and scope")
        seen_corrections.add(key)
    snapshot["account"] = account
    snapshot["correction_dispositions"] = deepcopy(updates.get("correction_dispositions", []))
    return snapshot


def retain_account_notation(project_dir: Path, run_dir: Path, phase: str, branch: str,
                            stage_id: str, document: dict, family: str, basis: dict,
                            current_documents: dict) -> tuple[dict, list[Path]]:
    snapshot = build_account_notation(project_dir, run_dir, phase, branch, stage_id,
                                      document, family, basis, current_documents)
    directory = run_dir / "outputs" / stage_id
    path = directory / "notation.json"
    write_json_atomic(path, snapshot)
    markdown = directory / "notation.md"
    markdown.write_text(render_notation(snapshot), encoding="utf-8", newline="\n")
    result = deepcopy(document)
    result["notation_snapshot"] = {"path": "notation.json", "sha256": sha256_file(path),
        "media_type": "application/json", "markdown": {"path": "notation.md", "sha256": sha256_file(markdown),
                                                       "media_type": "text/markdown"}}
    return result, [path, markdown]


def resolve_notation_entry(project_dir: Path, target: dict) -> dict:
    """Resolve a row only within the exact selected account and retained view."""
    if target.get("project_id") is not None and target["project_id"] != Path(project_dir).name:
        raise ArtifactError("The notation row belongs to another project")
    source_ref = {key: target[key] for key in (*SOURCE_FIELDS, "run_id", "stage_id", "package_id", "sha256") if key in target}
    if not source_ref.get("content_sha256"):
        source_ref["content_sha256"] = target.get("sha256")
    document, committed_ref = _committed(Path(project_dir), source_ref)
    pointer = document.get("notation_snapshot") if isinstance(document, dict) else None
    if not pointer or target.get("snapshot_sha256") != pointer.get("sha256"):
        raise ArtifactError("The notation row does not match the selected account's retained view")
    snapshot = retained_notation(Path(project_dir), source_ref)
    matches = [entry for entry in snapshot["entries"] if entry.get("entry_id") == target.get("entry_id")]
    if len(matches) != 1:
        raise ArtifactError("The selected notation entry is unavailable in this exact account")
    if target.get("object_id") is not None and target["object_id"] != matches[0]["entry_id"]:
        raise ArtifactError("The selected notation row contains conflicting entry identities")
    normalized = {**target, **source_ref, "kind": "notation_entry", "object_id": matches[0]["entry_id"],
                  "run_id": committed_ref.get("run_id"), "stage_id": committed_ref.get("stage_id"),
                  "package_id": committed_ref.get("package_id")}
    return {"entry": deepcopy(matches[0]), "snapshot": snapshot,
            "source_ref": {**source_ref, "run_id": committed_ref.get("run_id"), "stage_id": committed_ref.get("stage_id"),
                           "package_id": committed_ref.get("package_id")},
            "target": normalized}


def notation_brief(basis: dict, *, lead=False) -> str:
    snapshot = frozen_notation(basis)
    if snapshot is None:
        return ""
    path = basis["notation"].get("snapshot_path")
    markdown = basis["notation"].get("markdown_path")
    text = ("## Frozen scientific notation\n\n"
        f"Use the exact admitted notation view: `{path}`; readable view: `{markdown}`. "
        "Preserve each definition's study, method or source-local scope. Define essential symbols in the scientific account as well. "
        "Keep target, estimator and estimate distinct, preserve unknown units and original paper/proof notation, and define necessary additions in your existing scientific fields. "
        "A transformation is not an alias. A later phase cannot rewrite an upstream canonical definition. "
        "P2 receives only admitted P1/P2 definitions, including on reruns.\n\n")
    core = [entry for entry in snapshot.get("entries", [])
            if entry.get("status", "active") == "active" and entry.get("scope", {}).get("kind") in {"study", "method"}]
    if core:
        text += ("The shared study and admitted method definitions below are required mathematical context. "
                 "The complete frozen files also retain source-local definitions for the scientific accounts you use.\n\n")
        text += render_notation({"entries": core}, heading="Shared study and admitted method definitions", level=3) + "\n"
    if lead:
        text += ("Reconcile additions in notation_updates on your existing owned Lead account, citing exact incoming sources and definition fields. "
                 "Use empty arrays when nothing changes; omission does not delete inherited definitions. "
                 "A changed mathematical object requires the existing scientific revision route. "
                 "The harness generates the complete final lookup and readable file from this frozen input and your adopted additions.\n\n")
    return text
