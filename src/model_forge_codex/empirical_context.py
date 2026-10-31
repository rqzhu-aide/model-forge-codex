"""Compare an evaluation's exact theory with current, linked scientific components.

These views report source changes, not whether an empirical or theoretical claim
is true. Unknown provenance and incomplete dependency links stay explicit.
"""
from __future__ import annotations

import json
from pathlib import Path

from .alignment import method_identity
from .methods import get_method
from .records import ArtifactError, current_records, read_generation
from .storage import read_json, sha256_bytes, sha256_file

_THEORY_FAMILIES = ("theory_record", "complete_theory", "theory_candidate")
_BASIS_RUNTIME_FIELDS = {"sha256", "basis_phase", "basis_branch", "artifacts", "unavailable_artifacts", "p4_inputs"}


def _reference(branch: str, family: str, pointer: dict) -> dict:
    return {"branch": branch, "phase": "P3", "family": family,
            "generation_id": pointer.get("generation_id"),
            "sha256": pointer.get("content_sha256") or pointer.get("sha256"),
            "run_id": pointer.get("run_id") or pointer.get("source_run_id"),
            "stage_id": pointer.get("stage_id"), "package_id": pointer.get("package_id")}


def load_evaluation_basis(project_dir: Path, reference: dict) -> dict:
    """Load a producing P4 run's basis and check its recorded content binding."""
    run_id = reference.get("run_id")
    if not isinstance(run_id, str) or not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in run_id):
        raise ArtifactError("The evaluation's producing run is unavailable.")
    _verify_evaluation_producer(project_dir, reference)
    run_dir = project_dir / "runs" / run_id
    run = read_json(run_dir / "run.json")
    if (not isinstance(run, dict) or run.get("state") != "published"
            or run.get("phase") != "P4" or run.get("branch_id") != reference.get("branch")):
        raise ArtifactError("The evaluation cannot be linked to its published run.")
    basis = read_json(run_dir / "basis.json")
    if not isinstance(basis, dict) or not isinstance(basis.get("records"), list):
        raise ArtifactError("The evaluation's frozen basis is missing or unreadable.")
    expected = run.get("basis_sha256")
    if not expected or expected != basis.get("sha256"):
        raise ArtifactError("The evaluation's frozen basis has no matching recorded digest.")
    original = {key: value for key, value in basis.items() if key not in _BASIS_RUNTIME_FIELDS}
    if any(not isinstance(ref, dict) for ref in basis["records"]):
        raise ArtifactError("The evaluation's frozen basis contains malformed references.")
    original["records"] = [{key: value for key, value in ref.items() if key != "snapshot_path"}
                           for ref in basis["records"]]
    # Authorization hashes the cumulative documents before start_run replaces
    # them with frozen file paths. Reconstruct those exact, verified inputs.
    cumulative = basis.get("cumulative_inputs", {})
    if not isinstance(cumulative, dict):
        raise ArtifactError("The evaluation's cumulative inputs are malformed.")
    if "cumulative_inputs" in basis:
        original["cumulative_inputs"] = {}
    for family, ref in cumulative.items():
        if not isinstance(ref, dict):
            raise ArtifactError("The evaluation's cumulative input reference is malformed.")
        if ref.get("snapshot_path"):
            path = Path(ref["snapshot_path"])
            if not path.resolve().is_relative_to((run_dir / "inputs" / "cumulative").resolve()):
                raise ArtifactError("The evaluation's cumulative input is outside its frozen sources.")
            document = read_json(path)
        else:
            document = ref.get("document")
        digest = sha256_bytes(json.dumps(document, ensure_ascii=False, sort_keys=True,
                                        separators=(",", ":")).encode())
        if document is None or digest != ref.get("sha256"):
            raise ArtifactError(f"The evaluation's frozen {family} changed or disappeared.")
        original["cumulative_inputs"][family] = {
            **{key: value for key, value in ref.items() if key != "snapshot_path"}, "document": document}
    if "notation" in basis:
        from .notation import frozen_notation
        notation = basis["notation"]
        if not isinstance(notation, dict):
            raise ArtifactError("The evaluation's frozen notation reference is malformed.")
        for field in ("snapshot_path", "markdown_path"):
            if notation.get(field) and not Path(notation[field]).resolve().is_relative_to((run_dir / "inputs").resolve()):
                raise ArtifactError("The evaluation's notation is outside its frozen sources.")
        original["notation"] = {"document": frozen_notation(basis), "sha256": notation.get("sha256")}
    digest = sha256_bytes(json.dumps(original, sort_keys=True).encode())
    # start_run adds this manifest after authorization and wraps the research
    # digest only when inputs were selected. Paths are runtime metadata; the
    # selected identities, bytes and mappings retain their separate binding.
    manifest = basis.get("p4_inputs", {})
    if not isinstance(manifest, dict) or not isinstance(manifest.get("inputs", []), list):
        raise ArtifactError("The evaluation's selected inputs are malformed.")
    inputs = manifest.get("inputs", [])
    for row in inputs:
        if (not isinstance(row, dict)
                or not all(isinstance(row.get(key), str) and row[key] for key in ("input_id", "sha256", "snapshot_path"))
                or not isinstance(row.get("mapping"), dict)):
            raise ArtifactError("The evaluation's selected input reference is malformed.")
        path = Path(row["snapshot_path"])
        if (not path.resolve().is_relative_to((run_dir / "inputs" / "researcher").resolve())
                or not path.is_file() or sha256_file(path) != row["sha256"]):
            raise ArtifactError("The evaluation's selected input bytes changed or disappeared.")
    if inputs:
        digest = sha256_bytes(json.dumps({"research_basis": digest,
            "inputs": [(row["input_id"], row["sha256"], row["mapping"]) for row in inputs]},
            sort_keys=True, ensure_ascii=False).encode())
    if digest != expected:
        raise ArtifactError("The evaluation's frozen basis no longer matches its recorded digest.")
    if basis.get("basis_phase", "P4") != "P4" or basis.get("basis_branch", reference["branch"]) != reference["branch"]:
        raise ArtifactError("The evaluation's frozen basis belongs to another phase or method.")
    return basis


def _verify_evaluation_producer(project_dir: Path, reference: dict) -> None:
    """Require the exact generation to belong to the identified publication."""
    from .empirical_targets import _committed_evaluations
    directory = project_dir / "branches" / reference["branch"] / "phases" / "p4"
    for package in _committed_evaluations(directory):
        pointer = package.get("records", {}).get(reference.get("family"))
        if not pointer or pointer.get("generation_id") != reference.get("generation_id"):
            continue
        if ((pointer.get("content_sha256") or pointer.get("sha256")) != reference.get("sha256")
                or (pointer.get("run_id") or pointer.get("source_run_id")) != reference.get("run_id")):
            raise ArtifactError("The evaluation's exact generation does not match its recorded producer and digest.")
        if package.get("package_id"):
            if (package.get("run_id") != reference["run_id"] or package.get("phase") != "P4"
                    or package.get("branch_id") != reference["branch"]
                    or package["package_id"] != reference.get("package_id")
                    or pointer.get("package_id") != package["package_id"]):
                raise ArtifactError("The evaluation's producing run does not match its committed publication.")
            manifest = read_json(directory / "packages" / (package["package_id"] + ".json"))
            if (not isinstance(manifest, dict) or manifest.get("run_id") != package["run_id"]
                    or manifest.get("records", {}).get(reference["family"]) != pointer):
                raise ArtifactError("The evaluation's publication association is missing or changed.")
            return
        # Legacy family pointers need an independent exact publication receipt.
        matches = []
        for path in (project_dir / "authority" / "receipts").glob("*.json"):
            receipt = read_json(path)
            if not isinstance(receipt, dict) or receipt.get("run_id") != reference["run_id"]:
                continue
            if receipt.get("phase") != "P4" or receipt.get("branch_id") != reference["branch"]:
                continue
            if receipt.get("receipt_sha256"):
                payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
                if sha256_bytes(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()) != receipt["receipt_sha256"]:
                    continue
            if any(isinstance(ref, dict) and ref.get("family") == reference["family"]
                   and ref.get("generation_id") == reference["generation_id"]
                   and (ref.get("content_sha256") or ref.get("sha256")) == reference["sha256"]
                   for ref in receipt.get("generations", [])):
                matches.append(receipt)
        if len(matches) == 1:
            return
        raise ArtifactError("The legacy evaluation has no unambiguous exact publication receipt.")
    raise ArtifactError("The evaluation generation is not in the committed publication history.")


def verified_basis_theory(project_dir: Path, basis: dict, branch: str) -> tuple[dict | None, dict | None]:
    """Read verified frozen and canonical bytes; never substitute current theory."""
    entries = basis.get("records", [])
    for family in _THEORY_FAMILIES:
        matches = [ref for ref in entries if ref.get("branch") == branch
                   and ref.get("phase") == "P3" and ref.get("family") == family]
        if not matches:
            continue
        if len(matches) != 1:
            raise ArtifactError("The evaluation's tested theory source is ambiguous.")
        pointer = matches[0]
        document = read_generation(project_dir / "branches" / branch / "phases" / "p3", family, pointer)
        if pointer.get("snapshot_path"):
            path = Path(pointer["snapshot_path"])
            if (not path.resolve().is_relative_to((project_dir / "runs").resolve())
                    or not path.is_file() or sha256_file(path) != (pointer.get("content_sha256") or pointer.get("sha256"))):
                raise ArtifactError("The evaluation's frozen theory bytes are missing or changed.")
        if not isinstance(document, dict):
            raise ArtifactError("The evaluation's tested theory source is malformed.")
        return document, _reference(branch, family, pointer)
    return None, None


def _current_theory(project_dir: Path, branch: str) -> tuple[dict | None, dict | None]:
    directory = project_dir / "branches" / branch / "phases" / "p3"
    records = current_records(directory)
    for family in _THEORY_FAMILIES:
        if family in records:
            document = read_generation(directory, family, records[family])
            if not isinstance(document, dict):
                raise ArtifactError("The current theory source is malformed.")
            return document, _reference(branch, family, records[family])
    return None, None


def _scientific_content(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in ("source_artifacts", "artifacts", "used_by_statement_ids"):
                continue
            if key in ("assumption_ids", "depends_on_assumption_ids", "depends_on_statement_ids", "depends_on", "empirical_implication_ids") and isinstance(item, list) and all(isinstance(entry, str) for entry in item):
                item = sorted(set(item))
            result[key] = _scientific_content(item)
        return result
    if isinstance(value, list):
        return [_scientific_content(item) for item in value]
    return value


def _supporting_sources(value) -> list[str]:
    result = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("source_artifacts", "artifacts"):
                sources = item if isinstance(item, list) else [item]
                for source in sources:
                    # Moving exact bytes does not revise a scientific source.
                    if isinstance(source, dict) and source.get("sha256"):
                        source = {k: v for k, v in source.items() if k not in ("path", "uri", "artifact_id")}
                    result.append(json.dumps(source, sort_keys=True))
            else:
                result.extend(_supporting_sources(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(_supporting_sources(item))
    return sorted(result)


def _components(theory: dict) -> tuple[dict, dict, set, set, dict]:
    components, dependencies, statements, invalid, sources = {}, {}, set(), set(), {}
    for field, key in (("assumptions", "assumption_id"), ("statements", "statement_id")):
        items = theory.get(field, [])
        if not isinstance(items, list):
            invalid.add("<unidentified component>")
            continue
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get(key), str):
                invalid.add("<unidentified component>")
                continue
            identifier = item[key]
            if identifier in components:
                invalid.add(identifier)
            components[identifier] = _scientific_content(item)
            sources[identifier] = _supporting_sources(item)
            deps = set()
            for name in ("depends_on_statement_ids", "assumption_ids", "depends_on_assumption_ids", "depends_on"):
                value = item.get(name, [])
                if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                    invalid.add(identifier)
                else:
                    deps.update(value)
            dependencies[identifier] = deps
            if field == "statements":
                statements.add(identifier)
    return components, dependencies, statements, invalid, sources


def _closure(roots: set[str], graph: dict[str, set[str]]) -> set[str]:
    found = set(roots)
    while True:
        expanded = found | {dep for identifier in found for dep in graph.get(identifier, set())}
        if expanded == found:
            return found
        found = expanded


def _has_cycle(roots: set[str], graph: dict[str, set[str]]) -> bool:
    visited = set()
    for root in roots:
        stack = [(root, False)]
        active = set()
        while stack:
            node, exiting = stack.pop()
            if exiting:
                active.discard(node)
                visited.add(node)
                continue
            if node in active:
                return True
            if node in visited:
                continue
            active.add(node)
            stack.append((node, True))
            stack.extend((dep, False) for dep in graph.get(node, set()))
    return False


def _question_changes(before: dict, after: dict, linked: list[str]) -> dict:
    old, old_deps, old_statements, old_invalid, old_sources = _components(before)
    new, new_deps, new_statements, new_invalid, new_sources = _components(after)
    changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    union = {key: old_deps.get(key, set()) | new_deps.get(key, set()) for key in old.keys() | new.keys()}
    roots = set(linked)
    affected = {key for key in roots if _closure({key}, union) & changed}
    old_path, new_path = _closure(roots, old_deps), _closure(roots & new.keys(), new_deps)
    incomplete = (not roots or not roots.issubset(old_statements)
                  or bool(old_path - old.keys()) or bool(new_path - new.keys())
                  or bool(old_path & old_invalid) or bool(new_path & new_invalid)
                  or "<unidentified component>" in old_invalid | new_invalid
                  or _has_cycle(roots, old_deps) or _has_cycle(roots & new.keys(), new_deps))
    broader_changes = [field for field in ("theory_scope", "notation", "notation_glossary", "definitions", "regime", "limitations", "scientific_outcome")
                       if before.get(field) != after.get(field)]
    relevant_changed = changed & _closure(roots, union)
    # Expectations may be revised without rewriting the underlying theorem.
    implications = []
    for document in (before, after):
        entries = document.get("empirical_implications", [])
        mapping = {}
        if not isinstance(entries, list):
            incomplete = True
            entries = []
        for item in entries:
            if not isinstance(item, dict) or not isinstance(item.get("implication_id"), str) or item["implication_id"] in mapping:
                incomplete = True
                continue
            mapping[item["implication_id"]] = item
        implications.append(mapping)
    old_implications, new_implications = implications
    for identifier in old_implications.keys() | new_implications.keys():
        old_item, new_item = old_implications.get(identifier), new_implications.get(identifier)
        if old_item == new_item:
            continue
        implication_links = set()
        for item in (old_item, new_item):
            if item is None:
                continue
            links = item.get("statement_ids")
            if not isinstance(links, list) or not links or any(not isinstance(key, str) for key in links):
                incomplete = True
                continue
            if not set(links).issubset(old_statements | new_statements):
                incomplete = True
            implication_links.update(links)
        linked_roots = {key for key in roots if _closure({key}, union) & implication_links}
        if linked_roots:
            relevant_changed.add(identifier)
            affected.update(linked_roots)
    source_changed = {key for key in old.keys() & new.keys() if old_sources[key] != new_sources[key]}
    return {"changed_component_ids": sorted(relevant_changed),
            "affected_statement_ids": sorted(roots & affected),
            "source_changed_component_ids": sorted(source_changed & _closure(roots, union)),
            "incomplete": incomplete, "broader_context_changes": broader_changes}


def evaluation_theory_context(project_dir: Path, branch: str, reference: dict, questions: list[dict]) -> tuple[dict, list[dict]]:
    """Annotate each authored question against its own exact theory dependency paths."""
    base = {"tested_ref": None, "current_ref": None, "state": "unknown",
            "message": "The theory context could not be established from recorded sources.",
            "changed_component_ids": [], "affected_statement_ids": []}
    tested = current = None
    current_error = None
    try:
        current, base["current_ref"] = _current_theory(project_dir, branch)
    except (ArtifactError, OSError, TypeError, ValueError) as error:
        current_error = str(error)
    try:
        basis = load_evaluation_basis(project_dir, reference)
        tested, base["tested_ref"] = verified_basis_theory(project_dir, basis, branch)
        if current_error:
            raise ArtifactError(current_error)
        selected = get_method(project_dir, branch)
        old_identity = method_identity(basis.get("method"))
        current_identity = method_identity(selected)
        if not old_identity or not current_identity:
            base["message"] = "The evaluation's method identity cannot be compared with the current definition."
        elif old_identity != current_identity:
            base.update(state="method_changed", message="The method definition changed. These results describe the earlier definition; assess what follow-up is needed.")
        elif tested is None:
            base.update(state="early_exploration", message="This evaluation began without aligned theory. Its results remain exploratory; assess how they relate to current claims.")
        elif method_identity(tested) != old_identity or current is not None and method_identity(current) != current_identity:
            base["message"] = "The theory sources cannot be matched to the evaluation's method definition."
        elif current is None:
            base["message"] = "Current theory is unavailable for comparison; the tested theory remains recorded."
        else:
            base.update(state="comparable", message="")
    except (ArtifactError, OSError, TypeError, ValueError) as error:
        base["message"] = str(error)
    annotated = []
    for question in questions:
        linked = question.get("statement_ids", [])
        context = {**base, "linked_statement_ids": linked}
        if base["state"] == "comparable":
            changes = _question_changes(tested, current, linked)
            incomplete = changes.pop("incomplete")
            context.update(changes)
            if incomplete:
                context.update(state="unknown", message="This question's links or theory dependencies are incomplete; its revision impact needs assessment.")
            elif changes["broader_context_changes"]:
                context.update(state="unknown", message="The broader theory scope or interpretation changed; component links alone cannot establish this question's revision impact.")
            elif context["affected_statement_ids"]:
                context.update(state="affected", message="Linked theory changed; interpretation needs reassessment.")
            elif context["source_changed_component_ids"]:
                context.update(state="unknown", message="Supporting theory sources changed while linked component text stayed the same; inspect those sources to assess the interpretation.")
            else:
                same = all(base["tested_ref"][key] == base["current_ref"][key] for key in ("family", "generation_id", "sha256"))
                context.update(state="current" if same else "unchanged", message="No changes detected in linked claims or dependencies. This does not establish scientific support.")
        annotated.append({**question, "theory_context": context})
    summary = dict(base)
    if base["state"] == "comparable":
        states = {q["theory_context"]["state"] for q in annotated}
        summary["state"] = next((state for state in ("unknown", "affected", "unchanged", "current") if state in states), "unknown")
        summary["message"] = {
            "unknown": "Some empirical questions' theory context needs assessment; inspect each question's recorded sources and links.",
            "affected": "Linked theory changed for some questions. Inspect their context before interpreting the recorded results as current support.",
            "unchanged": "No changes detected in the questions' linked claims or dependencies. This does not establish scientific support.",
            "current": "The questions use current theory sources. Scientific support remains a research judgment.",
        }[summary["state"]]
        for field in ("changed_component_ids", "affected_statement_ids"):
            summary[field] = sorted({identifier for q in annotated for identifier in q["theory_context"][field]})
    summary["theory_basis_ref"] = summary["tested_ref"]
    summary["current_theory_ref"] = summary["current_ref"]
    return summary, annotated
