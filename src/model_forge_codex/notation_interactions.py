"""Source-bound explanation and one editable correction per notation quantity."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .notation import digest, resolve_notation_entry
from .records import ArtifactError, committed_packages, read_generation


def source_identity(reference):
    return tuple(reference.get(key) for key in ("phase", "branch", "family", "generation_id")) + (
        reference.get("content_sha256") or reference.get("sha256"),)


def public_notation(project_dir, reference):
    """Add clickable exact sources without changing retained notation bytes."""
    from .notation import LEAD_FAMILIES, _committed, _pointer, retained_notation
    from .research import source_ref
    document, committed = _committed(Path(project_dir), reference)
    snapshot = retained_notation(Path(project_dir), reference)
    if snapshot is None:
        raise ValueError("This saved account has no shared notation view")
    snapshot = deepcopy(snapshot)
    exact = source_ref(reference["branch"], reference["phase"], reference["family"], committed)

    def clickable(raw):
        if not isinstance(raw, dict):
            return None
        if raw.get("generation_id"):
            try:
                doc, pointer = _committed(Path(project_dir), raw)
                _pointer(doc, raw.get("pointer", ""))
                return {"generation_ref": source_ref(raw["branch"], raw["phase"], raw["family"], pointer),
                        "entry_pointer": raw.get("pointer", "")}
            except (ArtifactError, KeyError, ValueError):
                return None
        phase, branch, run = raw.get("phase"), raw.get("branch"), raw.get("run_id")
        family = raw.get("family") or str(raw.get("output_id", "")).split(".", 1)[-1]
        if not phase or not branch or not run or not family:
            return None
        families = [family]
        if family in LEAD_FAMILIES.get(phase, ()):
            families.extend(name for name in LEAD_FAMILIES[phase] if name != family)
        directory = Path(project_dir) / "branches" / branch / "phases" / phase.lower()
        for package in committed_packages(directory):
            for name in families:
                pointer = package["records"].get(name)
                if not pointer or pointer.get("run_id") != run or (raw.get("stage_id") and pointer.get("stage_id") != raw["stage_id"]):
                    continue
                try:
                    value = _pointer(read_generation(directory, name, pointer), raw.get("pointer", ""))
                    if raw.get("field_sha256") and digest(value) != raw["field_sha256"]:
                        continue
                    return {"generation_ref": source_ref(branch, phase, name, pointer), "entry_pointer": raw.get("pointer", "")}
                except ArtifactError:
                    continue
        return None

    for entry in snapshot["entries"]:
        refs = [("definition", entry.get("definition_ref")), ("adoption", entry.get("adoption_ref")),
                *(("scientific", ref) for ref in entry.get("source_refs", []))]
        entry["ui_source_refs"] = [{**linked, "source_role": role} for role, raw in refs
                                   if (linked := clickable(raw)) is not None]
    snapshot.update(snapshot_sha256=document["notation_snapshot"]["sha256"], source_ref=exact)
    return {"notation": snapshot, "source_ref": exact}


def correction_owner(entry):
    """Inherited displays share ownership; a different mathematical scope does not."""
    identity = {"quantity_key": entry["quantity_key"], "scope": entry["scope"]}
    if entry["scope"].get("kind") == "account":
        identity["account_scope_ref"] = entry.get("account_scope_ref") or entry["adoption_ref"]
    return "context.notation." + digest(identity)[:32]


def _resolve(project_dir, target):
    resolved = resolve_notation_entry(Path(project_dir), target)
    entry = resolved["entry"]
    canonical = {**deepcopy(resolved["target"]), "notation_scope": deepcopy(entry["scope"])}
    return resolved, canonical


def notation_issue(project_dir, target):
    resolved, canonical = _resolve(project_dir, target)
    entry = resolved["entry"]
    text = (f"${entry['symbol_latex']}$\n\n{entry['definition_markdown']}\n\n"
            f"{entry['meaning_markdown']}")
    return {"kind": "notation_entry", "title": "Discuss this definition", "summary_markdown": text,
            "responsible_role": "research_lead", "audience": ["research_lead"],
            "object_id": entry["entry_id"], "generation_ref": resolved["source_ref"],
            "explanation_target": canonical, "notation": resolved["snapshot"],
            "entry": entry, "branch": canonical["branch"], "phase": canonical["phase"],
            "family": canonical["family"]}


def validate_correction(project_dir, item):
    references = [ref for ref in item.get("source_refs", []) if ref.get("kind") == "notation_entry"]
    if item.get("topic") != "notation_correction" and not references:
        return
    if item.get("topic") != "notation_correction" or len(references) != 1:
        raise ValueError("A notation correction needs its one exact definition source")
    resolved, canonical = _resolve(project_dir, references[0])
    if item["item_id"] != correction_owner(resolved["entry"]):
        raise ValueError("Edit this definition's existing correction instead of creating a duplicate")
    if item.get("scope") != {"kind": "project"}:
        raise ValueError("Notation corrections use their definition's source and scope")
    # Project scope is only the storage container. freeze_context independently
    # enforces the exact scientific source and method before delivery to members.
    item["source_refs"] = [canonical]


def _published_dispositions(project_dir, item):
    if not item:
        return []
    from .notation import LEAD_FAMILIES
    expected = {"context_id": item["item_id"], "revision": item["revision"], "sha256": digest(item)}
    outcomes, seen = [], set()
    for branch in (Path(project_dir) / "branches").glob("*"):
        for phase, families in LEAD_FAMILIES.items():
            directory = branch / "phases" / phase.lower()
            if not directory.is_dir():
                continue
            for package in committed_packages(directory):
                for family, pointer in package["records"].items():
                    if family not in families:
                        continue
                    doc = read_generation(directory, family, pointer)
                    for disposition in (doc.get("notation_updates") or {}).get("correction_dispositions", []):
                        if disposition.get("correction_ref") != expected:
                            continue
                        key = (pointer.get("run_id"), digest(disposition))
                        if key in seen:
                            continue
                        seen.add(key)
                        from .research import source_ref
                        outcomes.append({**deepcopy(disposition),
                                         "source_ref": source_ref(branch.name, phase, family, pointer)})
    return outcomes


def load_correction(project_dir, target):
    from .problem_context import load_problem_context
    resolved, canonical = _resolve(project_dir, target)
    context = load_problem_context(project_dir)
    owner = correction_owner(resolved["entry"])
    item = next((row for row in context["items"] if row["item_id"] == owner), None)
    dispositions = _published_dispositions(project_dir, item)
    displayed = deepcopy(item)
    if displayed is not None:
        history = {row["revision"]: row for version in context.get("history", []) for row in version.get("items", [])
                   if row["item_id"] == owner and row["revision"] != item["revision"]}
        displayed["history"] = [deepcopy(history[revision]) for revision in sorted(history)]
    return {"item": displayed, "context_revision": context["revision"], "target": canonical,
            "disposition": dispositions[0] if len(dispositions) == 1 else None,
            "dispositions": dispositions}


def save_correction(project_dir, target, statement, *, expected_revision):
    from .problem_context import save_context_item, supports_problem_context
    from .catalog import Catalog
    from .notation import notation_enabled
    if not supports_problem_context(project_dir) or not notation_enabled(Catalog(Path(project_dir) / "contracts")):
        raise ValueError("Adopt the shared-notation workflow before saving a notation correction")
    resolved, canonical = _resolve(project_dir, target)
    save_context_item(project_dir, statement, expected_revision=expected_revision,
                      item_id=correction_owner(resolved["entry"]), origin="researcher_reported",
                      scope={"kind": "project"}, topic="notation_correction", source_refs=[canonical])
    return load_correction(project_dir, canonical)


def notation_context_visible(item, admitted_records, model_ref=None, *, notation=None, phase=None, branch_id=None):
    """A saved correction retains its source's admission and exact method scope."""
    if item.get("topic") != "notation_correction":
        return True
    refs = [ref for ref in item.get("source_refs", []) if ref.get("kind") == "notation_entry"]
    allowed = {source_identity(ref) for ref in admitted_records}
    if len(refs) != 1:
        return False
    source = refs[0]
    if phase:
        from .notation import _allowed
        if source.get("phase") not in _allowed(phase):
            return False
    inherited = source.get("entry_id") and any(entry.get("entry_id") == source["entry_id"]
                                               for entry in (notation or {}).get("entries", []))
    if branch_id and source.get("branch") not in {"trunk", branch_id}:
        inherited = False
    if source_identity(source) not in allowed and not inherited:
        return False
    selected = (model_ref or {}).get("identity") or model_ref or {}
    identity = (refs[0].get("notation_scope") or {}).get("method_identity")
    return (not identity or not selected or all(identity.get(key) == selected.get(key)
                                               for key in ("stable_id", "definition_sha256")))


def freeze_context(context, admitted_records, *, branch_id="trunk", model_ref=None, notation=None, phase=None):
    """A note cannot smuggle a later or excluded scientific source into a brief."""
    if not isinstance(context, dict):
        return context
    items = context.get("items", [])
    proposals = context.get("proposals", [])
    if not any(row.get("topic") == "notation_correction" for row in
               [*items, *(p.get("item", {}) for p in proposals)]):
        return context  # Frozen v1 behavior is unchanged.
    def visible(item):
        return notation_context_visible(item, admitted_records, model_ref, notation=notation, phase=phase, branch_id=branch_id)

    filtered = deepcopy(context)
    filtered["items"] = [row for row in items if visible(row)]
    filtered["proposals"] = [row for row in proposals if visible(row.get("item", {}))]
    # A context history is not supplied as an alternative route to excluded notes.
    if "history" in filtered:
        filtered["history"] = [{**version, "items": [row for row in version.get("items", []) if visible(row)],
                                "proposals": [row for row in version.get("proposals", []) if visible(row.get("item", {}))]}
                               for version in filtered["history"]]
    from .problem_context import effective_account
    filtered["effective_account"] = effective_account(filtered, branch_id, model_ref)
    filtered["notation_correction_refs"] = [
        {"context_id": row["item_id"], "revision": row["revision"], "sha256": digest(row)}
        for row in filtered["items"] if row.get("topic") == "notation_correction"]
    # Match context_snapshot's scientific content, excluding derived projections.
    filtered["sha256"] = digest({key: value for key, value in filtered.items() if key not in
                                 {"history", "sha256", "effective_account", "answer_routes", "notation_correction_refs"}})
    return filtered
