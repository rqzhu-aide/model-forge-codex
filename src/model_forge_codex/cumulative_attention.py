"""Research attention survives phase updates until explicitly dispositioned."""
from __future__ import annotations

from pathlib import Path

from .records import ArtifactError, committed_packages, read_generation
from .storage import read_json


def attention_scope_applies(item: dict, branch_id: str, model_ref: dict | None = None) -> bool:
    """Keep a published P2 model question with its exact eventual method branch.

    Original P2 questions can name trunk before their model is activated. The
    generation reference is stamped by the verified publication projection;
    target_phase and authored source fragments do not establish that origin.
    The stored scope remains unchanged, and ordinary context scope stays strict.
    """
    from .problem_context import scope_applies

    scope = item.get("scope")
    if scope_applies(scope, branch_id, model_ref):
        return True
    source = item.get("generation_ref") or {}
    if (not isinstance(scope, dict) or scope.get("kind") != "model" or scope.get("branch") != "trunk"
            or not isinstance(source, dict)
            or item.get("branch") != "trunk" or item.get("phase") != "P2"
            or source.get("branch") != "trunk" or source.get("phase") != "P2"
            or source.get("family") != "attention_items"
            or not all(isinstance(source.get(key), str) and source[key].strip()
                       for key in ("generation_id", "sha256", "run_id", "package_id"))):
        return False
    expected = scope.get("model_ref") or {}
    identity = expected.get("identity") or expected
    if (not isinstance(identity.get("stable_id"), str) or not identity["stable_id"]
            or type(identity.get("version")) is not int or identity["version"] < 1
            or not isinstance(identity.get("definition_sha256"), str) or not identity["definition_sha256"]
            or branch_id != identity["stable_id"]):
        return False
    return scope_applies({**scope, "branch": branch_id}, branch_id, model_ref)


def attention_applies_to_branch(item: dict, branch_id: str, method_id: str | None, model_ref: dict | None = None) -> bool:
    """Route authored method scopes without turning trunk publication into sharing.

    P2 is published on trunk, but its nonempty affected_record_ids identify
    method stable IDs. Empty scopes and P1 setting questions remain shared.
    A historical P2 reference that does not name the selected method is not
    silently treated as an instruction for every method.
    """
    if item.get("scope") is not None:
        return attention_scope_applies(item, branch_id, model_ref)
    origin = item.get("branch", "trunk")
    if origin != "trunk":
        return origin == branch_id
    if branch_id == "trunk":
        return True
    affected = item.get("affected_record_ids") or []
    phase = item.get("phase") or (item.get("generation_ref") or {}).get("phase")
    if phase == "P2" and affected:
        return bool(method_id and method_id in affected)
    return True


def current_researcher_answers(project_dir: Path) -> list[dict]:
    """Deliver the latest answers; earlier edits stay in researcher history."""
    resolutions = read_json(project_dir / "researcher" / "attention_resolutions.json")
    if not isinstance(resolutions, dict):
        return []
    return [
        {**{key: value for key, value in answer.items() if key != "history"},
         "attention_id": attention_id}
        for attention_id, answer in sorted(resolutions.items())
        if isinstance(answer, dict) and isinstance(answer.get("note"), str) and answer["note"].strip()
        and ("attention" not in answer or isinstance(answer["attention"], dict))
    ]


def versioned_question(question):
    """Old unscoped attention retains its pinned stable-ID behavior."""
    return bool(question.get("scope") or question.get("question_version_id")
                or question.get("schema_version") == "1.2.0"
                or (question.get("explanation_target") or {}).get("kind") == "project_context")


def retained_researcher_answers(project_dir: Path) -> list[dict]:
    """Latest response to each exact target, including superseded questions."""
    from .phase_interactions import digest, issue_source_identity
    resolutions = read_json(project_dir / "researcher" / "attention_resolutions.json") or {}
    result = []
    for attention_id, current in sorted(resolutions.items()):
        if not isinstance(current, dict):
            continue
        latest = {}
        for answer in [*(current.get("history") or []), current]:
            if not isinstance(answer, dict) or not isinstance(answer.get("note"), str) or not answer["note"].strip():
                continue
            question = answer.get("attention") or {}
            if not isinstance(question, dict):
                continue
            ref = answer.get("question_ref") or issue_source_identity(question)
            latest[digest(ref)] = {**{key: value for key, value in answer.items() if key != "history"},
                                   "attention_id": attention_id}
        result.extend(latest.values())
    return result


def answer_matches_question(answer, question):
    """Carry-forward is authored and exact, never inferred from similar prose."""
    from .phase_interactions import issue_source_identity
    source = answer.get("question_ref") or issue_source_identity(answer.get("attention") or {})
    if source is not None and source == issue_source_identity(question):
        return True
    for ref in question.get("answer_applicability_refs", []) or []:
        if (ref.get("attention_id") == answer.get("attention_id")
                and ref.get("answer_revision") == answer.get("revision", 0)
                and ref.get("question_ref") == source
                and isinstance(ref.get("reason"), str) and ref["reason"].strip()):
            # A candidate answer cannot be carried into a different model
            # merely by referring to its response revision.
            saved_scope = answer.get("scope") or (answer.get("attention") or {}).get("scope")
            if not saved_scope or saved_scope.get("kind") == "project" or saved_scope == question.get("scope"):
                return True
    return False


def answer_for_question(project_dir, question, answers=None):
    identifier = question.get("attention_id") or question.get("issue_id")
    candidates = [row for row in (answers if answers is not None else retained_researcher_answers(project_dir))
                  if row.get("attention_id") == identifier]
    if not versioned_question(question):
        return max(candidates, key=lambda row: row.get("revision", 0), default=None)
    return max((row for row in candidates if answer_matches_question(row, question)),
               key=lambda row: row.get("revision", 0), default=None)


def applicable_researcher_answers(project_dir, branch_id, model_ref=None, *, questions=None,
                                  role=None, phase=None, context=None):
    """Route scoped responses, retaining exact originals and incorporation links."""
    from .problem_context import answer_reference
    # Answered items leave the inbox, but their latest published versions
    # remain the authority for applicability. Supplement with durable early
    # context questions or unpublished sequential requests when provided.
    indexed = {row.get("attention_id") or row.get("issue_id"): row
               for row in open_attention_items(project_dir, {}, include_closed=True)}
    for row in questions or []:
        indexed.setdefault(row.get("attention_id") or row.get("issue_id"), row)
    incorporated = (context or {}).get("effective_account", {}).get("incorporated_answer_refs", [])
    result = []
    answers = retained_researcher_answers(project_dir)
    for answer in answers:
        saved = answer.get("attention") or {}
        current = indexed.get(answer["attention_id"], saved)
        if versioned_question(current) and not answer_matches_question(answer, current):
            continue
        if versioned_question(current):
            current_ref = issue_source_identity_for_routing(current)
            exact_answer = next((row for row in answers if row["attention_id"] == answer["attention_id"]
                                 and (row.get("question_ref") or issue_source_identity_for_routing(row.get("attention") or {})) == current_ref), None)
            if exact_answer is not None and answer is not exact_answer:
                # The researcher's own current instruction replaces a carried
                # predecessor; that original remains available in history.
                continue
        scope = answer.get("scope") or saved.get("scope")
        if scope is not None:
            if not attention_scope_applies({**saved, "scope": scope}, branch_id, model_ref):
                continue
        elif not attention_applies_to_branch(saved, branch_id,
                ((model_ref or {}).get("identity") or model_ref or {}).get("stable_id") or (model_ref or {}).get("method_id")):
            continue
        audience = answer.get("audience") or saved.get("audience")
        if audience is None and (saved.get("phase") == "P2" or saved.get("target_phase") == "P2"):
            audience = ["research_lead"]
        if role and audience and role not in audience:
            continue
        delivered = dict(answer)
        if audience is not None:
            delivered["audience"] = list(audience)
        if answer_reference(answer) in incorporated:
            delivered["incorporated_into_context"] = True
        if current is not saved and issue_source_identity_for_routing(current) != issue_source_identity_for_routing(saved):
            delivered["applicability"] = [dict(ref) for ref in current.get("answer_applicability_refs", [])
                                         if ref.get("attention_id") == answer["attention_id"]
                                         and ref.get("answer_revision") == answer.get("revision", 0)]
        result.append(delivered)
    return result


def issue_source_identity_for_routing(question):
    from .phase_interactions import issue_source_identity
    return issue_source_identity(question)


def _reference(branch: str, phase: str, family: str, pointer: dict) -> dict:
    return {
        "branch": branch, "phase": phase, "family": family,
        "generation_id": pointer.get("generation_id"),
        "sha256": pointer.get("content_sha256") or pointer.get("sha256"),
        "run_id": pointer.get("run_id") or pointer.get("source_run_id"),
        "package_id": pointer.get("package_id"),
    }


def _record_entries(document):
    """Only actual records, never record IDs mentioned inside source references."""
    if isinstance(document, dict) and document.get("record_id"):
        yield document, ""
    elif isinstance(document, list):
        for index, record in enumerate(document):
            if isinstance(record, dict) and record.get("record_id"):
                yield record, f"/{index}"
    elif isinstance(document, dict) and isinstance(document.get("items"), list):
        for index, record in enumerate(document["items"]):
            if isinstance(record, dict) and record.get("record_id"):
                yield record, f"/items/{index}"
    # P2 proposals and the cumulative catalog wrap method records. Only these
    # known containers are record locations; nested references are not records.
    if isinstance(document, dict):
        method = document.get("method")
        if isinstance(method, dict) and method.get("record_id") and method.get("identity", {}).get("stable_id"):
            yield method, "/method"
        for index, method in enumerate(document.get("methods", []) or []):
            if isinstance(method, dict) and method.get("record_id") and method.get("identity", {}).get("stable_id"):
                yield method, f"/methods/{index}"


def _related_sources(phase_dir: Path, branch: str, package: dict, attention_pointer: dict) -> dict:
    """Index exact sibling records from the attention's producing publication.

    Legacy pointers can mix runs, so those need matching recorded run IDs.
    A duplicated candidate and canonical record are distinguished only by the
    record's declared type matching the published family, never by prose.
    """
    matches = {}
    attention_run = attention_pointer.get("run_id") or attention_pointer.get("source_run_id")
    for family, pointer in package["records"].items():
        if family.split(".", 1)[-1] == "attention_items":
            continue
        source_run = pointer.get("run_id") or pointer.get("source_run_id")
        if package.get("legacy") and (not attention_run or source_run != attention_run):
            continue
        try:
            document = read_generation(phase_dir, family, pointer)
        except ArtifactError:
            # An optional related link must never substitute another generation.
            continue
        for record, entry_pointer in _record_entries(document):
            reference = {**_reference(branch, phase_dir.name.upper(), family, pointer),
                         "record_id": record["record_id"]}
            if entry_pointer:
                reference["entry_pointer"] = entry_pointer
            suffix = family.split(".", 1)[-1]
            stable_id = (record.get("identity") or {}).get("stable_id")
            canonical = record.get("record_type") == suffix or (stable_id and suffix == "method_catalog")
            for identifier in dict.fromkeys([record["record_id"]] + ([stable_id] if stable_id else [])):
                matches.setdefault(identifier, []).append((canonical, reference))
    result = {}
    for identifier, candidates in matches.items():
        canonical = [reference for matches_type, reference in candidates if matches_type]
        if len(canonical) == 1:
            result[identifier] = canonical[0]
        elif len(candidates) == 1:
            result[identifier] = candidates[0][1]
    return result


def open_attention_items(project_dir: Path, resolved: dict, *, include_closed: bool = False) -> list[dict]:
    """Project the latest published version of each project-wide attention ID.

    A run emits newly raised or explicitly updated issues, not a replacement
    inbox. Only committed packages contribute; researcher resolutions remain
    separate from the immutable scientific records. Routing can include closed
    versions so their exact answer applicability still governs future work.
    """
    versions = []
    branches = project_dir / "branches"
    if not branches.is_dir():
        return []
    for branch in sorted(path for path in branches.iterdir() if path.is_dir()):
        for phase_dir in sorted((branch / "phases").glob("p[1-5]")):
            packages = list(committed_packages(phase_dir))
            by_id = {package["package_id"]: package for package in packages if package.get("package_id")}
            for order, package in enumerate(reversed(packages)):
                for family, pointer in package["records"].items():
                    if family.split(".", 1)[-1] != "attention_items":
                        continue
                    document = read_generation(phase_dir, family, pointer)
                    items = document if isinstance(document, list) else (document or {}).get("items", [])
                    reference = _reference(branch.name, phase_dir.name.upper(), family, pointer)
                    origin = by_id.get(pointer["package_id"]) if pointer.get("package_id") else package
                    published_at = pointer.get("published_at") or package.get("published_at") or ""
                    for index, item in enumerate(items or []):
                        if not isinstance(item, dict) or not item.get("attention_id"):
                            continue
                        entry_pointer = f"/{index}" if isinstance(document, list) else f"/items/{index}"
                        versions.append((published_at, branch.name, phase_dir.name, order,
                                         (phase_dir, origin, pointer), {
                            **item, "branch": branch.name, "phase": phase_dir.name.upper(),
                            "published_at": published_at, "generation_ref": {**reference, "entry_pointer": entry_pointer},
                            "entry_pointer": entry_pointer, "authored_order": index,
                        }))
    latest = {}
    for *_, context, item in sorted(versions, key=lambda entry: entry[:4]):
        latest[item["attention_id"]] = (context, item)
    result = []
    source_indexes = {}
    for key, ((phase_dir, origin, pointer), item) in latest.items():
        saved = resolved.get(key)
        answered = key in resolved
        if answered and versioned_question(item):
            candidates = [*(saved.get("history") or []), {**saved, "attention_id": key}] if isinstance(saved, dict) else []
            answered = any(answer_matches_question({**answer, "attention_id": key}, item)
                           for answer in candidates if isinstance(answer, dict))
        pending = (item.get("disposition", "open") == "open"
                   or (item.get("kind") == "research_task" and item.get("disposition") == "partially_fixed"))
        if (not include_closed and not pending) or answered:
            continue
        identifiers = item.get("affected_record_ids") or []
        related = {}
        if identifiers and origin:
            origin_key = (phase_dir, pointer.get("package_id") or id(origin), item["generation_ref"]["run_id"])
            if origin_key not in source_indexes:
                source_indexes[origin_key] = _related_sources(phase_dir, item["branch"], origin, pointer)
            related = source_indexes[origin_key]
        item["related_source_refs"] = [dict(related[identifier]) for identifier in dict.fromkeys(identifiers)
                                       if identifier in related]
        result.append(item)
    severity = {"blocking": 0, "reassessment_required": 1, "major": 2, "minor": 3}
    legacy_order = sorted(result, key=lambda item: (severity.get(item.get("severity"), 4),
                                                   item["branch"], item["phase"], item["attention_id"]))
    # Preserve original fallback ordering without guessing a historical priority.
    # Stable passes retain numeric authored order within each publication.
    priorities = {"interpretation": 0, "inference": 1, "data": 2, "resources": 3}
    ranked = [item for item in result if item.get("kind") == "researcher_decision"
              and isinstance(item.get("decision_priority"), str) and item["decision_priority"] in priorities]
    ranked.sort(key=lambda item: item["authored_order"])
    ranked.sort(key=lambda item: item.get("published_at", ""), reverse=True)
    ranked.sort(key=lambda item: priorities[item["decision_priority"]])
    return ranked + [item for item in legacy_order if item not in ranked]
