"""Verified, read-only file and claim links for researcher-facing records."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from pathlib import Path
from urllib.parse import quote, urlencode

from .records import ArtifactError, read_generation, source_artifact_path
from .storage import read_json, sha256_bytes, sha256_file


def walk_objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_objects(child)


def authored_pointer(pointer):
    """Keep the source identity, never accept authored verification/UI fields."""
    return {key: pointer[key] for key in ("artifact_id", "uri", "path", "artifact_path", "authored_path", "sha256", "artifact_sha256",
                                         "media_type", "locator", "label", "title") if key in pointer}


def file_media(path: Path) -> str:
    return {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg", ".webp": "image/webp", ".csv": "text/csv",
            ".json": "application/json", ".jsonl": "application/x-ndjson",
            ".md": "text/markdown", ".pdf": "application/pdf", ".tex": "application/x-tex",
            ".txt": "text/plain", ".py": "text/plain", ".r": "text/plain",
            ".jl": "text/plain", ".toml": "text/plain", ".yaml": "text/plain",
            ".yml": "text/plain"}.get(path.suffix.lower(), "application/octet-stream")


def frozen_artifact(project_dir: Path, run_id: str, digest: str, artifact_id: str = "") -> Path:
    """Only a declared, digest-matching input inside this run can be opened."""
    run_dir = project_dir / "runs" / run_id
    basis = read_json(run_dir / "basis.json") or {}
    matches = set()
    for item in basis.get("artifacts", []):
        if (not isinstance(item, dict) or item.get("content_sha256") != digest
                or artifact_id and item.get("artifact_id") != artifact_id):
            continue
        path = Path(item.get("path") or "").resolve()
        if path.is_relative_to((run_dir / "inputs").resolve()) and path.is_file() and sha256_file(path) == digest:
            matches.add(path)
    if len(matches) != 1:
        raise ArtifactError("The exact retained input is missing, ambiguous, or no longer matches its digest.")
    return next(iter(matches))


def artifact_link(project_dir: Path, ref: dict, pointer: dict) -> dict:
    """Resolve a declared file, never a filename inferred from a caption."""
    run_id = ref.get("run_id") or ref.get("source_run_id")
    if not run_id:
        return {"source_error": "The producing run was not recorded for this file."}
    run_dir = project_dir / "runs" / run_id
    run = read_json(run_dir / "run.json") or {}
    if (run.get("state") != "published" or run.get("branch_id") != ref.get("branch")
            or run.get("phase") != ref.get("phase")):
        return {"source_error": "This file cannot be linked to the published method and phase."}
    try:
        path = source_artifact_path(project_dir, {**ref, "run_id": run_id}, pointer)
        relative = path.relative_to((run_dir / "outputs").resolve())
        query = urlencode({"path": Path(*relative.parts[1:]).as_posix(),
                           "sha256": pointer.get("sha256") or pointer.get("artifact_sha256")})
        return {"artifact_url": f"/api/v1/projects/{quote(project_dir.name)}/runs/{quote(run_id)}/outputs/{quote(relative.parts[0])}/artifact?{query}",
                "source_verified": True, "source_kind": "output", "media_type": file_media(path)}
    except (ArtifactError, ValueError):
        # Reused code can be retained as an exact frozen input. It is not
        # replaced by a similarly named file from a later evaluation.
        basis = read_json(run_dir / "basis.json") or {}
        digest = pointer.get("sha256") or pointer.get("artifact_sha256")
        matches = [item for item in basis.get("artifacts", []) if isinstance(item, dict)
                   and digest and item.get("content_sha256") == digest
                   and (item.get("artifact_id") == pointer.get("artifact_id") and pointer.get("artifact_id")
                        or item.get("original_path") == pointer.get("path") and pointer.get("path"))]
        if matches:
            try:
                item = matches[0]
                path = frozen_artifact(project_dir, run_id, digest, item.get("artifact_id") or "")
                query = urlencode({"sha256": digest, "artifact_id": item.get("artifact_id") or ""})
                return {"artifact_url": f"/api/v1/projects/{quote(project_dir.name)}/runs/{quote(run_id)}/inputs/artifact?{query}",
                        "source_verified": True, "source_kind": "retained_input", "media_type": file_media(path)}
            except ArtifactError:
                pass
        return {"source_error": "The exact retained file is missing or its bytes no longer match the recorded digest."}


def empirical_run_sources(project_dir: Path, document: dict, meta: dict, records: dict) -> list[dict]:
    """Bind narrative run locators only to this publication's declared bytes."""
    from .records import _segment
    from .research import _same_evaluation

    requested = set(re.findall(r"run://[A-Za-z0-9._-]+/[^\s)\"<>\\#]+", json.dumps(document)))
    ref = meta["generation_ref"]
    if not requested or not ref.get("run_id"):
        return []
    run_dir = project_dir / "runs" / _segment(ref["run_id"])
    run = read_json(run_dir / "run.json") or {}
    if (run.get("state") != "published" or run.get("branch_id") != ref.get("branch")
            or run.get("phase") != "P4" or ref.get("phase") != "P4"):
        return []
    outputs = (run_dir / "outputs").resolve()
    links, seals = {}, {}

    def bind(target, digest, declared_uri=None):
        target = target.resolve()
        if not target.is_relative_to(outputs) or not target.is_file():
            return
        relative = target.relative_to(outputs)
        if len(relative.parts) < 2:
            return
        uris = {f"run://{ref['run_id']}/outputs/{relative.as_posix()}",
                f"run://{ref['run_id']}/{relative.as_posix()}"}
        # A declared working-file alias may omit its retained working/role
        # directories, but cannot select a different run or producing stage.
        if isinstance(declared_uri, str):
            alias = re.fullmatch(r"run://([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)/(.+)", declared_uri)
            if (alias and alias[1] == ref["run_id"] and alias[2] == relative.parts[0]
                    and "\\" not in alias[3] and all(part not in ("", ".", "..") for part in alias[3].split("/"))):
                uris.add(declared_uri)
        selected = uris & requested
        if not selected or sha256_file(target) != digest:
            return
        query = urlencode({"path": Path(*relative.parts[1:]).as_posix(), "sha256": digest})
        for uri in sorted(selected):
            links[uri] = {"uri": uri, "sha256": digest, "branch": ref["branch"], "producing_run_id": ref["run_id"],
                          "source_verified": True, "media_type": file_media(target),
                          "artifact_url": f"/api/v1/projects/{quote(project_dir.name)}/runs/{quote(ref['run_id'])}/outputs/{quote(relative.parts[0])}/artifact?{query}"}

    for source, source_meta in records.values():
        if not _same_evaluation(meta, source_meta):
            continue
        source_ref = source_meta["generation_ref"]
        stage_id = source_ref.get("stage_id")
        if stage_id:
            stage = outputs / _segment(stage_id)
            if stage_id not in seals:
                seals[stage_id] = (read_json(stage / "seal.json") or {}).get("outputs", {})
            for name, sealed in seals[stage_id].items():
                if not isinstance(sealed, dict) or sealed.get("sha256") != source_ref.get("sha256"):
                    continue
                target = (stage / name).resolve()
                if target.is_relative_to(stage):
                    bind(target, source_ref["sha256"])
        if not isinstance(source, dict):
            continue
        declared = {key: source.get(key) for key in ("representations", "source_registry", "source_artifacts", "reproduction")}
        for pointer in walk_objects(declared):
            digest = pointer.get("sha256") or pointer.get("artifact_sha256")
            if not digest:
                continue
            # Audit registries declare exact run locators with a filename and
            # digest, rather than an artifact-relative path. Keep that locator
            # authoritative instead of searching other roles for its filename.
            uri = pointer.get("uri")
            locator = re.fullmatch(r"run://([A-Za-z0-9._-]+)/outputs/(.+)", uri) if isinstance(uri, str) else None
            if pointer.get("filename") and locator and locator[1] == ref["run_id"]:
                parts = locator[2].split("/")
                if "\\" not in locator[2] and all(part not in ("", ".", "..") for part in parts):
                    bind(outputs.joinpath(*parts), digest)
            if not (pointer.get("path") or pointer.get("artifact_path")):
                continue
            try:
                target = source_artifact_path(project_dir, source_ref, pointer)
                bind(target, digest, pointer.get("uri"))
            except (ArtifactError, OSError, ValueError):
                continue
    # Upstream links are eligible only when their exact generation was frozen
    # into this evaluation. A later publication never supplies a substitute.
    from .research import source_ref
    from .technical_reports import resolve_report_source
    basis = read_json(run_dir / "basis.json") or {}
    for uri in sorted(requested - links.keys()):
        locator = re.fullmatch(r"run://([A-Za-z0-9._-]+)/(?:outputs/)?([A-Za-z0-9._-]+)/([^/]+)", uri)
        family_locator = re.fullmatch(r"run://([A-Za-z0-9._-]+)/(p[1-5])\.([A-Za-z0-9._-]+)", uri)
        if not locator and not family_locator:
            continue
        candidates = []
        for source in basis.get("records", []):
            if not isinstance(source, dict) or source.get("run_id") != (locator or family_locator)[1]:
                continue
            if locator:
                if source.get("stage_id") != locator[2]:
                    continue
                stage = project_dir / "runs" / source["run_id"] / "outputs" / locator[2]
                sealed = (read_json(stage / "seal.json") or {}).get("outputs", {}).get(locator[3]) or {}
                if sealed.get("sha256") != source.get("content_sha256"):
                    continue
            elif source.get("phase", "").lower() != family_locator[2] or source.get("family") != family_locator[3]:
                continue
            candidates.append(source)
        if locator:
            # Publication can retain both complete_theory and its promoted
            # theory_record alias with identical bytes. The explicit filename
            # selects the original family, not whichever alias is current.
            named = [source for source in candidates
                     if locator[3] == source.get("family", "") + (".jsonl" if source.get("format") == "jsonl" else ".json")]
            if named:
                candidates = named
        if len(candidates) != 1:
            continue
        source = candidates[0]
        try:
            snapshot = Path(source.get("snapshot_path") or "").resolve()
            if not snapshot.is_relative_to((run_dir / "inputs").resolve()):
                continue
            source_run = read_json(project_dir / "runs" / _segment(source["run_id"]) / "run.json") or {}
            if (source_run.get("state") != "published" or source_run.get("branch_id") != source.get("branch")
                    or source_run.get("phase") != source.get("phase")):
                continue
            resolve_report_source(source, basis)
            phase_dir = project_dir / "branches" / _segment(source["branch"]) / "phases" / _segment(source["phase"]).lower()
            read_generation(phase_dir, source["family"], source)
            reference = source_ref(source["branch"], source["phase"], source["family"], source)
            links[uri] = {"uri": uri, "sha256": reference["sha256"], "branch": ref["branch"],
                          "producing_run_id": source["run_id"], "source_verified": True,
                          "generation_ref": reference}
        except (ArtifactError, OSError, ValueError, KeyError):
            continue
    declared_digests = {}
    for source, source_meta in records.values():
        if not _same_evaluation(meta, source_meta) or not isinstance(source, dict):
            continue
        for pointer in walk_objects(source):
            uri, digest = pointer.get("uri"), pointer.get("sha256") or pointer.get("artifact_sha256")
            if isinstance(uri, str) and digest:
                declared_digests.setdefault(uri, set()).add(digest)
    return [link for uri, link in links.items()
            if not declared_digests.get(uri) or declared_digests[uri] == {link["sha256"]}]


def scientific_document_sources(project_dir: Path, document: dict, meta: dict, text: str) -> list[dict]:
    """Bind P3 narrative links to this publication's sealed or frozen bytes."""
    from .records import _segment
    from .research import source_ref
    from .technical_reports import resolve_report_source

    ref = meta["generation_ref"]
    if ref.get("phase") != "P3" or not ref.get("run_id"):
        return []
    run_id = _segment(ref["run_id"])
    run_dir = project_dir / "runs" / run_id
    run = read_json(run_dir / "run.json") or {}
    if (run.get("state") != "published" or run.get("branch_id") != ref.get("branch")
            or run.get("phase") != ref["phase"]):
        return []
    requested = {source.split("#", 1)[0] for source in re.findall(
        r"(?<!!)\[[^\]\n]+\]\(([^\s)]+)\)", text + "\n" + json.dumps(document))}
    if not requested:
        return []
    basis = read_json(run_dir / "basis.json") or {}

    def relative_path(value):
        if not isinstance(value, str) or not value or re.match(r"(?:[a-z][a-z\d+.-]*:|[/\\])", value, re.I) or "\\" in value:
            return None
        parts = value.split("/")
        if ".." in parts or "" in parts:
            return None
        return "/".join(part for part in parts if part != ".") or None

    # Repeated declarations of the same bytes are harmless. Conflicting aliases
    # remain ambiguous even if one of their declared files is now unavailable.
    aliases = {}
    for pointer in walk_objects(document):
        path = pointer.get("path") or pointer.get("artifact_path")
        digest = pointer.get("sha256") or pointer.get("artifact_sha256")
        if not relative_path(path) or not re.fullmatch(r"[a-f0-9]{64}", digest or ""):
            continue
        authored = authored_pointer(pointer)
        for alias in {pointer.get("uri"), relative_path(path)} - {None}:
            aliases.setdefault(alias, {})[(path, digest)] = authored

    links = []
    for uri in sorted(requested):
        match = re.fullmatch(r"run://([A-Za-z0-9][A-Za-z0-9._-]*)/outputs/([A-Za-z0-9][A-Za-z0-9._-]*)/(.+)", uri)
        if match:
            source_run, stage_id, name = match.groups()
            if source_run != run_id or relative_path(name) != name:
                continue
            stage = (run_dir / "outputs" / stage_id).resolve()
            if not stage.is_relative_to((run_dir / "outputs").resolve()):
                continue
            seal = read_json(stage / "seal.json") or {}
            sealed = seal.get("outputs", {}).get(name) or {}
            digest = sealed.get("sha256")
            target = (stage / name).resolve()
            if (seal.get("stage_id") != stage_id or not re.fullmatch(r"[a-f0-9]{64}", digest or "")
                    or not target.is_relative_to(stage.resolve()) or not target.is_file() or sha256_file(target) != digest):
                continue
            query = urlencode({"path": name, "sha256": digest})
            links.append({"uri": uri, "sha256": digest, "source_verified": True, "media_type": file_media(target),
                          "artifact_url": f"/api/v1/projects/{quote(project_dir.name)}/runs/{quote(run_id)}/outputs/{quote(stage_id)}/artifact?{query}"})
        elif uri.startswith("generation://"):
            generation = uri[len("generation://"):]
            candidates = [row for row in basis.get("records", []) if row.get("generation_id") == generation]
            if len(candidates) != 1:
                continue
            source = candidates[0]
            try:
                snapshot = Path(source.get("snapshot_path") or "").resolve()
                if not snapshot.is_relative_to((run_dir / "inputs").resolve()):
                    continue
                resolve_report_source(source, basis)
                phase_dir = project_dir / "branches" / _segment(source["branch"]) / "phases" / _segment(source["phase"]).lower()
                read_generation(phase_dir, source["family"], source)
                links.append({"uri": uri, "source_verified": True,
                              "generation_ref": source_ref(source["branch"], source["phase"], source["family"], source)})
            except (ArtifactError, OSError, ValueError, KeyError):
                continue
        else:
            alias = uri if uri.startswith("artifact://") else relative_path(uri)
            if uri.startswith("run://"):
                # Stage-form run URIs need an exact declared alias, not a
                # guessed filename or a source from another producing run.
                declared = re.fullmatch(r"run://([A-Za-z0-9][A-Za-z0-9._-]*)/([A-Za-z0-9][A-Za-z0-9._-]*)/(.+)", uri)
                if (not declared or declared[1] != run_id or declared[2] == "outputs"
                        or relative_path(declared[3]) != declared[3]):
                    continue
                alias = uri
            candidates = aliases.get(alias, {})
            if len(candidates) != 1:
                continue
            pointer = next(iter(candidates.values()))
            action = artifact_link(project_dir, ref, pointer)
            if action.get("source_verified"):
                links.append({**pointer, **action, "uri": uri})
    return links


def scientific_account_sources(project_dir: Path, document: dict, meta: dict, text: str = "") -> list[dict]:
    """Resolve account and document citations through their producing publication."""
    from .records import _segment, committed_packages
    from .research import _primary_document, _primary_document_pointer, source_ref

    ref = meta["generation_ref"]
    if ref.get("phase") != "P3":
        return []
    sources = []
    if ref.get("package_id"):
        try:
            phase_dir = project_dir / "branches" / _segment(ref["branch"]) / "phases" / "p3"
            package = next((item for item in committed_packages(phase_dir)
                            if item.get("package_id") == ref["package_id"]), {})
            original = package.get("records", {}).get(ref["family"])
            if (original and source_ref(ref["branch"], "P3", ref["family"], original) == ref
                    and package.get("run_id") == ref.get("run_id")
                    and package.get("branch_id") == ref["branch"] and package.get("phase") == "P3"):
                for family, pointer in package["records"].items():
                    if pointer.get("package_id") != ref["package_id"] or pointer.get("run_id") != ref["run_id"]:
                        continue
                    try:
                        source = read_generation(phase_dir, family, pointer)
                    except ArtifactError:
                        continue
                    if not isinstance(source, dict):
                        continue
                    if (document.get("method_identity") and source.get("method_identity")
                            and document["method_identity"] != source["method_identity"]):
                        continue
                    sources.append((source, source_ref(ref["branch"], "P3", family, pointer)))
        except (ArtifactError, OSError, ValueError, KeyError):
            pass
    # A relative record filename is authoritative only when its sealed bytes
    # equal a generation in this package. Family names do not supply filenames.
    publication_files, file_references = [], {}
    for _, reference in sources:
        if not reference.get("stage_id"):
            continue
        try:
            stage = project_dir / "runs" / _segment(reference["run_id"]) / "outputs" / _segment(reference["stage_id"])
            seal = read_json(stage / "seal.json") or {}
            if seal.get("stage_id") != reference["stage_id"]:
                continue
            for name, sealed in seal.get("outputs", {}).items():
                if not isinstance(sealed, dict) or sealed.get("sha256") != reference["sha256"]:
                    continue
                target = (stage / name).resolve()
                if not target.is_relative_to(stage.resolve()) or not target.is_file() or sha256_file(target) != reference["sha256"]:
                    continue
                pointer = {"path": name, "sha256": reference["sha256"]}
                action = artifact_link(project_dir, reference, pointer)
                if action.get("source_verified"):
                    publication_files.append(pointer)
                    file_references.setdefault((action["artifact_url"], reference["sha256"]), reference)
        except (ArtifactError, OSError, ValueError):
            continue
    # Sibling declarations belong to this package, never to today's current
    # theory or another publication from the same run.
    requested = {source.split("#", 1)[0] for source in re.findall(
        r"(?<!!)\[[^\]\n]+\]\(([^\s)]+)\)", text + "\n" + json.dumps(document))}
    declarations = {"account": document, "publication_sources": [source for source, _ in sources],
                    "publication_files": publication_files}
    links = scientific_document_sources(project_dir, declarations, meta, text)
    result = []
    for link in links:
        if link["uri"] not in requested:
            continue
        record_reference = file_references.get((link.get("artifact_url"), link.get("sha256")))
        if record_reference:
            # A link to this record's own JSON means its canonical bytes, not
            # its primary manuscript rendered again through the document view.
            same_record_bytes = record_reference["sha256"] == ref.get("sha256")
            result.append(link if same_record_bytes else {**link, "generation_ref": record_reference})
            continue
        for source, reference in sources:
            primary = _primary_document_pointer(source)
            if (isinstance(primary, dict) and primary.get("sha256") == link.get("sha256")
                    and link.get("artifact_url") and _primary_document(project_dir, reference, source).get("primary_artifact_url") == link["artifact_url"]):
                link = {**link, "generation_ref": reference}
                break
        result.append(link)
    return result


def theory_statement_projection(project_dir: Path, ref: dict, statement: dict) -> dict:
    """Link retained arguments in a display copy of the exact theory component."""
    result = deepcopy(statement)
    for key in ("assessment_context", "theorist_account", "original_justification_retained", "assessment_source_error"):
        result.pop(key, None)
    proof = result.get("justification")
    if isinstance(proof, dict) and isinstance(proof.get("artifacts"), list):
        proof["artifacts"] = [{**authored_pointer(pointer),
                               **artifact_link(project_dir, ref, authored_pointer(pointer))}
                              for pointer in proof["artifacts"] if isinstance(pointer, dict)]
    return result


def producing_role(project_dir: Path, reference: dict) -> str | None:
    """Recover authorship from the producing run's frozen stage, never today's catalog."""
    run_id, stage_id = reference.get("run_id"), reference.get("stage_id")
    if not run_id or not stage_id:
        return None
    try:
        plan = read_json(project_dir / "runs" / run_id / "stage-plan.json") or []
    except (OSError, ValueError):
        return None
    stages = plan.get("stages", []) if isinstance(plan, dict) else plan
    if not isinstance(stages, list):
        return None
    for stage in stages:
        if not isinstance(stage, dict) or stage.get("stage_id") != stage_id:
            continue
        roles = stage.get("roles", [])
        if len(roles) == 1 and roles[0] in {"research_lead", "theorist", "data_analyst", "outside_reviewer"}:
            return roles[0]
    return None


def evaluated_method_projection(project_dir: Path, document: dict, reference: dict, metadata=None) -> dict | None:
    """Read this evaluation's frozen definition, never the currently selected model."""
    from .records import _segment

    identity = document.get("method_identity")
    if not isinstance(identity, dict) or not identity.get("definition_sha256"):
        return None
    snapshots = []
    if isinstance(metadata, dict):
        snapshots.append(metadata.get("method"))
    elif reference.get("package_id"):
        try:
            package = read_json(project_dir / "branches" / _segment(reference["branch"])
                                / "phases" / "p4" / "packages" / (_segment(reference["package_id"]) + ".json")) or {}
            if package.get("run_id") == reference.get("run_id"):
                snapshots.append((package.get("metadata") or {}).get("method"))
        except (ArtifactError, OSError, ValueError, KeyError):
            pass
    if reference.get("run_id"):
        try:
            basis = read_json(project_dir / "runs" / _segment(reference["run_id"]) / "basis.json") or {}
            snapshots.append(basis.get("method"))
        except (ArtifactError, OSError, ValueError):
            pass
    for snapshot in snapshots:
        if not isinstance(snapshot, dict) or snapshot.get("identity") != identity:
            continue
        definition = snapshot.get("definition") or {}
        if not isinstance(definition, dict) or definition.get("identity") != identity:
            continue
        mathematical = definition.get("mathematical_definition") or {}
        canonical = mathematical.get("canonical_definition", {}) if isinstance(mathematical, dict) else {}
        def named_definition(key):
            value = canonical.get(key) if isinstance(canonical, dict) else None
            return value.get("definition", "") if isinstance(value, dict) else ""
        return {"identity": deepcopy(identity), "name": definition.get("title") or snapshot.get("name"),
                "summary": definition.get("summary", ""),
                "objective_markdown": named_definition("objective_or_estimating_equation"),
                "target_markdown": named_definition("target_or_estimand"),
                "source_ref": deepcopy(snapshot.get("source_ref")),
                "source_label": "Method definition frozen for this evaluation"}
    return None


def implementation_projection(project_dir: Path, doc: dict, meta: dict, audit=None) -> dict:
    from .research import _authored_markdown
    def outcome_sections(document):
        outcome = document.get("scientific_outcome") or {}
        entries = []
        for key, title in (("conclusion", "Assessment"), ("scope", "Scope of the assessment"),
                           ("assumptions", "Conditions of this assessment"), ("material_disagreement", "Remaining disagreement")):
            value = outcome.get(key) if isinstance(outcome, dict) else None
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                value = "\n\n".join(value)
            if isinstance(value, str) and value.strip():
                entries.append({"key": "outcome_" + key, "title": title, "body_md": value})
        return entries
    labels = {"rule": "Implemented rule", "correspondence": "How the code follows the method",
              "configuration": "Configuration", "environment": "Environment", "verification": "Implementation checks",
              "choices": "Implementation choices", "departures": "Departures from the method", "limitations": "Limitations"}
    summary = doc.get("implementation_summary") or {}
    sections = outcome_sections(doc) + [{"key": key, "title": title, "body_md": summary[key]}
                for key, title in labels.items() if isinstance(summary, dict) and isinstance(summary.get(key), str) and summary[key].strip()]
    history = doc.get("execution_history") or {}
    if isinstance(history, dict) and isinstance(history.get("interpretation"), str):
        sections.append({"key": "execution_history", "title": "Included and excluded attempts", "body_md": history["interpretation"]})
    files, seen = [], set()
    # Explicit scientific artifact pointers only; arbitrary path strings are
    # not made into links or treated as executable instructions.
    for pointer in walk_objects(doc):
        if not (pointer.get("path") or pointer.get("artifact_path")) or not (pointer.get("sha256") or pointer.get("artifact_sha256")):
            continue
        key = pointer.get("path") or pointer.get("artifact_path"), pointer.get("sha256") or pointer.get("artifact_sha256")
        if key in seen:
            continue
        seen.add(key)
        files.append({**authored_pointer(pointer), "label": pointer.get("label") or pointer.get("title") or Path(key[0]).name,
                      **artifact_link(project_dir, meta["generation_ref"], pointer)})
    result = {**meta, "structured": doc, "body_md": _authored_markdown(doc), "sections": sections, "files": files,
              "producer_role": producing_role(project_dir, meta.get("generation_ref", {}))}
    for entry in files:
        if entry.get("source_verified") and entry.get("artifact_url"):
            entry["download_url"] = entry["artifact_url"] + "&download=true"
    reproduction = doc.get("reproduction")
    if isinstance(reproduction, dict):
        result["reproduction"] = deepcopy(reproduction)
        if reproduction.get("status") == "available":
            from .implementation_export import verified_implementation_files
            ref = meta["generation_ref"]
            try:
                verified_implementation_files(project_dir, ref, doc)
                if ref.get("family") == "implementation_record":
                    result["bundle_url"] = (f"/api/v1/projects/{quote(project_dir.name)}/branches/{quote(ref['branch'])}"
                        f"/phases/P4/records/implementation_record/{quote(ref['generation_id'])}/implementation-bundle")
            except (ArtifactError, OSError, ValueError, KeyError) as exc:
                result["bundle_error"] = str(exc)
    if audit:
        account, audit_meta = audit
        labels = {"mathematical_fidelity": "Mathematical fidelity", "definition_to_code_correspondence": "Method-to-code correspondence",
                  "protocol_adherence": "Adherence to the planned study", "comparison_and_thresholds": "Comparisons and thresholds",
                  "uncertainty_and_interpretation": "Uncertainty and interpretation", "selection_and_stopping": "Selection and stopping",
                  "theory_consistency": "Consistency with theory", "validity_boundary": "Scope of the assessment"}
        details = account.get("audit") or {}
        entries = outcome_sections(account)
        for key, title in labels.items():
            value = details.get(key) if isinstance(details, dict) else None
            body = value.get("assessment") if isinstance(value, dict) else value
            if isinstance(body, str) and body.strip():
                entries.append({"key": key, "title": title, "body_md": body,
                                "status": value.get("status") if isinstance(value, dict) else None})
        result["theorist_review"] = {**audit_meta, "structured": account, "body_md": _authored_markdown(account), "sections": entries}
    return result


def literature_reference_links(project_dir: Path, ref: dict, identifiers: list[str]) -> list[dict]:
    """Resolve declared novelty references against the theory's saved P1 input."""
    if not identifiers:
        return []
    from .research import record_url, source_ref
    basis = read_json(project_dir / "runs" / (ref.get("run_id") or "missing") / "basis.json") or {}
    definitions = {}
    alias_entries = {}

    def paper_entries(value, pointer=""):
        if isinstance(value, dict):
            paper_source = value.get("source")
            if (isinstance(value.get("entry_id"), str) and isinstance(paper_source, dict)
                    and isinstance(paper_source.get("source_id"), str) and paper_source["source_id"].strip()
                    and isinstance(paper_source.get("title"), str) and paper_source["title"].strip()):
                yield pointer, value
            for key, child in value.items():
                yield from paper_entries(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from paper_entries(child, pointer + "/" + str(index))

    for source in basis.get("records", []):
        if not isinstance(source, dict) or source.get("phase") != "P1" or source.get("branch") != "trunk":
            continue
        try:
            document = read_generation(project_dir / "branches/trunk/phases/p1", source["family"], source)
        except (ArtifactError, KeyError):
            continue
        exact = source_ref("trunk", "P1", source["family"], source)
        for item in walk_objects(document):
            label = next((item[key] for key in ("title", "label", "text", "statement", "name", "key_contribution")
                          if isinstance(item.get(key), str) and item[key].strip()), None)
            for key in ("source_id", "subject_ref", "stable_id"):
                if isinstance(item.get(key), str) and len(item) > 1:
                    definitions.setdefault(item[key], []).append({"identifier": item[key], "label": label or item[key],
                        "generation_ref": exact, "source_url": record_url(project_dir.name, exact)})
        for pointer, item in paper_entries(document):
            paper_source = item["source"]
            content = sha256_bytes(json.dumps(item, ensure_ascii=False, sort_keys=True).encode())
            key = (item["entry_id"], content)
            previous = alias_entries.setdefault(key, [])
            # An identical cumulative copy adds no second assessment. Keep
            # the original report's exact entry; distinct content stays linked.
            if previous and source["family"] == "literature_library":
                continue
            previous[:] = [link for link in previous if link["generation_ref"]["family"] != "literature_library"]
            previous.append({"identifier": item["entry_id"], "label": paper_source["title"],
                "source_id": paper_source["source_id"], "generation_ref": {**exact, "entry_pointer": pointer},
                "source_url": record_url(project_dir.name, exact)})
    for entries in alias_entries.values():
        for item in entries:
            definitions.setdefault(item["identifier"], []).append(item)
    result = []
    for identifier in identifiers:
        matches = definitions.get(identifier, [])
        unique = {(item["source_url"], item["label"], item.get("source_id"),
                   item["generation_ref"].get("entry_pointer")): item for item in matches}
        result.extend(unique.values() if unique else [{"identifier": identifier, "label": identifier,
            "source_error": "This literature reference could not be resolved in the theory's saved research basis."}])
    return result


def traceability_projection(project_dir: Path, statements: list, meta: dict, manuscript_entry=None) -> dict:
    """Resolve claims only against this manuscript run's frozen upstream basis."""
    from .research import record_url, source_ref
    ref = meta["generation_ref"]
    run_id = ref.get("run_id") or "missing"
    basis = read_json(project_dir / "runs" / run_id / "basis.json") or {}
    if manuscript_entry and manuscript_entry[0].get("record_type") == "technical_report":
        from .technical_reports import resolve_report_source
        claims = []
        for claim in manuscript_entry[0].get("claims", []):
            links = []
            for source in claim.get("source_refs", []):
                link = {"relationship": "support", "identifier": source.get("pointer") or source["generation_id"],
                        "label": source.get("pointer") or source["family"], "family": source["family"]}
                try:
                    resolve_report_source(source, basis)
                    exact = source_ref(source["branch"], source["phase"], source["family"], source)
                    links.append({**link, "generation_ref": exact,
                                  "source_url": record_url(project_dir.name, exact)})
                except (ArtifactError, ValueError, OSError):
                    links.append({**link, "source_error": "This exact source is unavailable in the report's retained basis."})
            claims.append({**claim, "statement_id": claim.get("claim_id"), "evidence_links": links,
                           "source_links": []})
        return {**meta, "claims": claims, "report_generation_ref": manuscript_entry[1]["generation_ref"]}
    definitions, declared_files = {}, {}
    for source in basis.get("records", []):
        if not isinstance(source, dict) or source.get("phase") not in {"P1", "P2", "P3", "P4"}:
            continue
        try:
            # Read the exact retained generation; a new current generation
            # cannot repair an old manuscript's unresolved references.
            document = read_generation(project_dir / "branches" / source["branch"] / "phases" / source["phase"].lower(), source["family"], source)
        except (ArtifactError, KeyError):
            continue
        exact_ref = source_ref(source["branch"], source["phase"], source["family"], source)
        source_meta = {"phase": source["phase"], "generation_ref": exact_ref, "source_url": record_url(project_dir.name, exact_ref)}
        for item in walk_objects(document):
            label = next((item[key] for key in ("title", "label", "text", "statement", "question", "name")
                          if isinstance(item.get(key), str) and item[key].strip()), None)
            for key in ("evidence_id", "statement_id", "claim_id", "source_id", "assumption_id", "stable_id"):
                if isinstance(item.get(key), str) and len(item) > 1:
                    definitions.setdefault(item[key], []).append({**source_meta, "label": label or item[key]})
            if item.get("artifact_id") and item.get("sha256"):
                declared_files.setdefault((item["artifact_id"], item["sha256"]), []).append(source_meta)
    claims = []
    for statement in statements:
        if not isinstance(statement, dict):
            continue
        links = []
        outcome = statement.get("scientific_outcome") or {}
        for relationship, identifiers in (("support", statement.get("supporting_evidence_ids", [])),
                ("counterevidence", statement.get("counterevidence_ids", [])), ("assumption", statement.get("assumptions", [])),
                ("strongest_support", outcome.get("strongest_evidence_ids", [])),
                ("strongest_counterevidence", outcome.get("strongest_counterevidence_ids", []))):
            for identifier in identifiers:
                candidates = definitions.get(identifier, [])
                unique = {(item["source_url"], item["label"]): item for item in candidates}
                if unique:
                    links.extend({"relationship": relationship, "identifier": identifier, **item} for item in unique.values())
                else:
                    links.append({"relationship": relationship, "identifier": identifier, "label": identifier,
                                  "source_error": "This reference could not be resolved in the manuscript's saved upstream evidence."})
        source_links = []
        for pointer in statement.get("source_locations", []):
            if not isinstance(pointer, dict):
                continue
            key = pointer.get("artifact_id"), pointer.get("sha256")
            candidates = declared_files.get(key, [])
            if candidates:
                # Source pointers are retained in the producing manuscript's
                # frozen input manifest. Do not follow a new upstream run.
                phases = {item["phase"] for item in candidates}
                retained = [item for item in basis.get("artifacts", []) if isinstance(item, dict)
                            and item.get("content_sha256") == key[1] and item.get("phase") in phases]
                link = {"source_error": "This exact source file is unavailable in the manuscript's saved inputs."}
                for item in retained:
                    try:
                        path = frozen_artifact(project_dir, run_id, key[1], item.get("artifact_id") or "")
                        query = urlencode({"sha256": key[1], "artifact_id": item.get("artifact_id") or ""})
                        link = {"artifact_url": f"/api/v1/projects/{quote(project_dir.name)}/runs/{quote(run_id)}/inputs/artifact?{query}",
                                "source_verified": True, "source_kind": "retained_input", "media_type": file_media(path)}
                        break
                    except ArtifactError:
                        continue
                source_links.append({**authored_pointer(pointer), **candidates[0], **link})
            else:
                local = []
                if manuscript_entry:
                    manuscript = manuscript_entry[0]
                    local = [manuscript.get("primary_artifact"), manuscript.get("manuscript_artifact")]
                if any(isinstance(item, dict) and (item.get("artifact_id"), item.get("sha256")) == key for item in local):
                    source_links.append({**authored_pointer(pointer), **artifact_link(project_dir, ref, pointer), "source_kind": "manuscript_location"})
                else:
                    source_links.append({**authored_pointer(pointer), "source_error": "This exact source was not found in the manuscript's saved evidence."})
        claims.append({**statement, "evidence_links": links, "source_links": source_links})
    result = {**meta, "claims": claims}
    if manuscript_entry:
        result["manuscript_generation_ref"] = manuscript_entry[1]["generation_ref"]
    else:
        result["manuscript_source_error"] = "These saved claim references could not be matched to the displayed manuscript publication."
    return result
