"""Researcher-selected workspaces for exact published methods.

Selection does not change a scientific definition. Explicit researcher
activation is recorded against the exact proposed identity and superseded
when the P2 definition changes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from .storage import append_jsonl, read_json, write_json_atomic

_IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _method_documents(document):
    if isinstance(document, list):
        for item in document:
            yield from _method_documents(item)
    elif isinstance(document, dict):
        identity = document.get("identity") or document.get("method_identity") or {}
        if identity.get("stable_id") and document.get("mathematical_definition"):
            yield document
        else:
            for key in ("methods", "method_records", "method_changes", "entries"):
                if key in document:
                    value = document[key]
                    if isinstance(value, dict):
                        value = list(value.values())
                    yield from _method_documents(value)


def _method_entries(document):
    """Yield every method-shaped entry, including malformed ones.

    A malformed entry must stay visible: a broken entry in the current
    complete catalog shadows the older incremental record for the same
    method instead of silently inheriting it.
    """
    if isinstance(document, list):
        for item in document:
            yield from _method_entries(item)
    elif isinstance(document, dict):
        identity = document.get("identity") or document.get("method_identity")
        if isinstance(identity, dict) and identity.get("stable_id") and document.get("mathematical_definition"):
            yield document
            return
        for key in ("methods", "method_records", "method_changes", "entries"):
            value = document.get(key)
            if isinstance(value, dict):
                value = list(value.values())
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, dict):
                    continue
                item_identity = item.get("identity") or item.get("method_identity")
                if isinstance(item_identity, dict) or item.get("mathematical_definition"):
                    yield item
                else:
                    yield from _method_entries(item)


def _entry_error(method: dict) -> str | None:
    identity = method.get("identity") or method.get("method_identity")
    if not isinstance(identity, dict) or not identity.get("stable_id"):
        return "no stable identity"
    stable_id = identity["stable_id"]
    if not isinstance(stable_id, str) or not _IDENT.fullmatch(stable_id):
        return "invalid stable_id"
    if not isinstance(identity.get("version"), int) or identity["version"] < 1:
        return "invalid version"
    if not re.fullmatch(r"[a-fA-F0-9]{64}", str(identity.get("definition_sha256") or "")):
        return "invalid definition_sha256"
    if not method.get("mathematical_definition"):
        return "no mathematical definition"
    return None


def _scan_catalog(project_dir: Path) -> tuple[dict[str, dict], list[dict]]:
    from .records import current_records, read_generation

    store = project_dir / "branches" / "trunk" / "phases" / "p2"
    records = current_records(store)
    found: dict[str, dict] = {}
    diagnostics: list[dict] = []
    # Complete catalog supersedes incremental method_changes when both exist.
    for family, pointer in sorted(records.items(), key=lambda pair: "catalog" in pair[0]):
        suffix = family.split(".", 1)[-1]
        if not ("method" in suffix or suffix == "catalog"):
            continue
        document = read_generation(store, family, pointer)
        source_ref = {
            "branch": "trunk", "phase": "P2", "family": family,
            "generation_id": pointer.get("generation_id"),
            "sha256": pointer.get("content_sha256", pointer.get("sha256", "")),
            "run_id": pointer.get("run_id", pointer.get("source_run_id", "")),
        }
        complete = "catalog" in family
        for method in _method_entries(document):
            identity = method.get("identity") or method.get("method_identity") or {}
            stable_id = identity.get("stable_id")
            error = _entry_error(method)
            if error is not None:
                shadowed = bool(complete and isinstance(stable_id, str) and found.pop(stable_id, None) is not None)
                diagnostics.append({
                    "code": "method.identity_invalid",
                    "message": "Method identity is missing or invalid; applicability cannot be established.",
                    "detail": error,
                    "stable_id": stable_id if isinstance(stable_id, str) else None,
                    "source_ref": source_ref,
                    "shadowed": shadowed,
                })
                continue
            found[stable_id] = {
                "method_id": stable_id,
                "name": method.get("title", stable_id),
                "title": method.get("title", stable_id),
                "version": identity["version"],
                "definition_sha256": identity["definition_sha256"],
                "identity": dict(identity),
                "status": method.get("lifecycle_state", "proposed"),
                "definition": method,
                "source_ref": source_ref,
            }
    for selection in _registry(project_dir).get("branches", {}).values():
        method = found.get(selection.get("method_id"))
        action = selection.get("activation") or {}
        if (method and method["status"] == "proposed" and selection.get("identity") == method["identity"]
                and action.get("target_lifecycle_state") == "active"):
            method["status"] = "active"
            method["lifecycle_authority"] = action
    return found, diagnostics


def _catalog_methods(project_dir: Path) -> dict[str, dict]:
    return _scan_catalog(project_dir)[0]


def catalog_diagnostics(project_dir: Path) -> list[dict]:
    """Malformed current catalog entries, each linked to its exact source record."""
    return _scan_catalog(project_dir)[1]


def _registry(project_dir: Path) -> dict:
    result = read_json(project_dir / "researcher" / "methods.json") or {"branches": {}}
    if not isinstance(result, dict) or not isinstance(result.get("branches"), dict):
        raise ValueError("The researcher method selection record is malformed")
    return result


def _legacy_identity(project_dir: Path, branch_id: str) -> dict | None:
    """Infer only an unambiguous historical scientific association."""
    from .records import current_records, read_generation

    identities = {}
    for phase in ("p3", "p4", "p5"):
        store = project_dir / "branches" / branch_id / "phases" / phase
        for family, pointer in current_records(store).items():
            document = read_generation(store, family, pointer)
            if isinstance(document, dict) and isinstance(document.get("method_identity"), dict):
                identity = document["method_identity"]
                key = (identity.get("stable_id"), identity.get("version"), identity.get("definition_sha256"))
                if all(key):
                    identities[key] = identity
    return next(iter(identities.values())) if len(identities) == 1 else None


def list_methods(project_dir: Path) -> list[dict]:
    registry = _registry(project_dir).get("branches", {})
    result = []
    for stable_id, method in _catalog_methods(project_dir).items():
        entries = [(branch, value) for branch, value in registry.items() if value.get("method_id") == stable_id]
        branch, selected = entries[0] if entries else (stable_id, {})
        legacy = None
        if not entries and (project_dir / "branches" / branch).is_dir():
            legacy = _legacy_identity(project_dir, branch)
        chosen = selected.get("identity") or legacy
        dependent = []
        for dependent_branch in ([branch for branch, _ in entries] or ([branch] if legacy else [])):
            dependent.extend(branch_output_statuses(project_dir, dependent_branch))
        result.append({
            **method, "branch_id": branch,
            "registered": bool(entries or legacy),
            "aligned": not chosen or chosen == method["identity"],
            "selected_identity": chosen, "current_identity": method["identity"],
            "dependent_outputs": dependent,
        })
    return sorted(result, key=lambda item: item["name"].lower())


def output_method_status(project_dir: Path, recorded_identity, catalog: dict | None = None) -> dict:
    """Compare a published output's recorded method identity to the current catalog.

    The current catalog is the authority — never the branch's stored
    selection. A missing or malformed recorded identity is unknown, never
    assumed current. An editorial revision with unchanged definition bytes
    leaves dependent outputs current.
    """
    from .alignment import method_identity

    recorded = method_identity(recorded_identity)
    if recorded is None:
        return {"status": "unknown", "reason": "identity_unavailable",
                "message": "This output's recorded method identity is missing or malformed; freshness cannot be established."}
    current = (catalog if catalog is not None else _catalog_methods(project_dir)).get(recorded[0])
    if current is None:
        return {"status": "unknown", "reason": "method_not_in_catalog",
                "message": "This method is absent from the current catalog; freshness cannot be established."}
    identity = current["identity"]
    if recorded == (identity["stable_id"], identity["version"], identity["definition_sha256"]):
        return {"status": "current", "current_identity": dict(identity)}
    lineage = current["definition"].get("lineage") or {}
    if recorded[2] == identity["definition_sha256"] and lineage.get("change_class") == "editorial":
        return {"status": "current", "current_identity": dict(identity)}
    return {"status": "needs_update", "current_identity": dict(identity),
            "current_version": identity["version"],
            "recorded_version": recorded[1],
            "change_class": lineage.get("change_class"),
            "change_summary": lineage.get("change_summary", ""),
            "source_ref": dict(current["source_ref"]),
            "message": (f"The current catalog carries version {identity['version']} of this method; "
                        f"this output was produced for version {recorded[1]}.")}


def branch_output_statuses(project_dir: Path, branch_id: str) -> list[dict]:
    """Freshness of a branch's current published P3–P5 outputs against the catalog."""
    from .alignment import method_identity
    from .records import ArtifactError, current_records, read_generation

    if branch_id == "trunk" or not _IDENT.fullmatch(branch_id):
        return []
    catalog = _catalog_methods(project_dir)
    results = []
    for phase in ("P3", "P4", "P5"):
        store = project_dir / "branches" / branch_id / "phases" / phase.lower()
        if not store.is_dir():
            continue
        try:
            records = current_records(store)
        except ArtifactError:
            continue
        if not records:
            continue
        package = read_json(store / "current-package.json") or {}
        package_method = (package.get("metadata") or {}).get("method") or {}
        recorded = None
        identity_source = None
        run_id = package.get("run_id")
        for family in sorted(records):
            pointer = records[family]
            try:
                document = read_generation(store, family, pointer)
            except ArtifactError:
                continue
            identity = document.get("method_identity") if isinstance(document, dict) else None
            if method_identity(identity):
                recorded = identity
                identity_source = family
                run_id = pointer.get("run_id", run_id)
                break
        if recorded is None and method_identity(package_method):
            recorded = package_method.get("identity") or package_method
            identity_source = "package_metadata"
        results.append({"branch": branch_id, "phase": phase, "run_id": run_id,
                        "package_id": package.get("package_id"),
                        "recorded_identity": dict(recorded) if isinstance(recorded, dict) else None,
                        "identity_source": identity_source,
                        **output_method_status(project_dir, recorded, catalog=catalog)})
    return results


def predecessor_material(project_dir: Path, branch_id: str, phase: str, selected_method: dict) -> dict | None:
    """The branch's published package for this phase as historical reassessment material.

    Supplied only when the package was produced for the same stable method under
    a different definition digest — a revised calculation-defining payload. The
    references stay outside the run's admitted records: they are historical
    material for reassessment, never current scientific support. An editorial
    revision (unchanged digest) supplies nothing.
    """
    from .alignment import method_identity
    from .records import ArtifactError, current_records, read_generation

    if branch_id == "trunk" or not _IDENT.fullmatch(branch_id) or phase not in ("P3", "P4", "P5"):
        return None
    selected = method_identity(selected_method)
    if selected is None:
        return None
    store = project_dir / "branches" / branch_id / "phases" / phase.lower()
    if not store.is_dir():
        return None
    try:
        records = current_records(store)
    except ArtifactError:
        return None
    if not records:
        return None
    package = read_json(store / "current-package.json") or {}
    recorded = None
    for family in sorted(records):
        try:
            document = read_generation(store, family, records[family])
        except ArtifactError:
            continue
        identity = document.get("method_identity") if isinstance(document, dict) else None
        if method_identity(identity):
            recorded = dict(identity)
            break
    if recorded is None:
        package_method = (package.get("metadata") or {}).get("method")
        if isinstance(package_method, dict):
            identity = package_method.get("identity") or package_method
            if method_identity(identity):
                recorded = dict(identity)
    if recorded is None:
        return None
    key = method_identity(recorded)
    if key[0] != selected[0] or key[2] == selected[2]:
        return None
    lineage = (selected_method.get("definition") or {}).get("lineage") or {}
    return {
        "phase": phase,
        "branch": branch_id,
        "predecessor_identity": recorded,
        "revised_identity": dict(selected_method.get("identity") or {}),
        "change_class": lineage.get("change_class"),
        "change_summary": lineage.get("change_summary", ""),
        "run_id": package.get("run_id"),
        "package_id": package.get("package_id"),
        "materials": {
            family: {"branch": branch_id, "phase": phase, "family": family,
                     "generation_id": pointer.get("generation_id"),
                     "content_sha256": pointer.get("content_sha256"),
                     "run_id": pointer.get("run_id", package.get("run_id")),
                     "package_id": pointer.get("package_id", package.get("package_id"))}
            for family, pointer in sorted(records.items())
        },
    }


def get_method(project_dir: Path, branch_id: str) -> dict | None:
    if branch_id == "trunk" or not _IDENT.fullmatch(branch_id):
        return None
    selected = _registry(project_dir).get("branches", {}).get(branch_id)
    identity = selected.get("identity") if selected else _legacy_identity(project_dir, branch_id)
    stable_id = selected.get("method_id") if selected else (identity or {}).get("stable_id")
    method = _catalog_methods(project_dir).get(stable_id)
    if not method or not identity:
        return None
    return {**method, "branch_id": branch_id, "registered": True,
            "selected_identity": identity, "current_identity": method["identity"],
            "aligned": identity == method["identity"]}


def activate_method(project_dir: Path, method_id: str, expected_identity: dict | None = None) -> dict:
    if not _IDENT.fullmatch(method_id):
        raise ValueError("Invalid method identifier")
    method = _catalog_methods(project_dir).get(method_id)
    if method is None:
        raise ValueError("This method has no published P2 definition. Ask the lead to register it through P2 first.")
    if expected_identity is not None and expected_identity != method["identity"]:
        raise ValueError("This method definition changed after it was displayed. Review the current definition and select it again.")
    if method["status"] not in ("active", "proposed"):
        raise ValueError(f"This method is {method['status']}; it must be active in the P2 catalog before selection.")
    registry = _registry(project_dir)
    branch = next((key for key, value in registry["branches"].items()
                   if value.get("method_id") == method_id), method_id)
    selected = {"method_id": method_id, "identity": method["identity"],
                "selected_at": datetime.now(timezone.utc).isoformat()}
    if method["status"] == "proposed":
        selected["activation"] = {"action_type": "activate_method", "authorized_by": "researcher",
                                  "expected_method": method["source_ref"], "target_lifecycle_state": "active",
                                  "reason": "Researcher selected this proposed definition for development.",
                                  "activated_at": selected["selected_at"]}
    previous = registry["branches"].get(branch)
    if previous and previous.get("identity") == method["identity"] and "activation" not in selected:
        return {**method, "branch_id": branch, "registered": True, "aligned": True}
    registry["branches"][branch] = selected
    (project_dir / "branches" / branch / "phases").mkdir(parents=True, exist_ok=True)
    write_json_atomic(project_dir / "researcher" / "methods.json", registry)
    append_jsonl(project_dir / "researcher" / "method-selections.jsonl", {"branch_id": branch, **selected})
    return {**method, "status": "active", "branch_id": branch, "registered": True, "aligned": True}
