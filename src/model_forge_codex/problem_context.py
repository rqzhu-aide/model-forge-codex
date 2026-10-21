"""Versioned researcher-owned context, with explicit authority and provenance.

No facts are extracted from prose. Reading or adopting context is deterministic;
team interpretations remain proposals until the researcher saves them.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import re

from .project_brief import project_instructions
from .storage import read_json, write_json_atomic

CAPABILITY = "researcher_dialogue_v1"
ORIGINS = {"researcher_reported", "evidence_supported", "proposed_assumption", "unknown"}
_IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
RESEARCH_GOAL_POINTER = "/research_setting/research_goal_markdown"


def supports_problem_context(project_or_catalog, phase="P1"):
    root = (project_or_catalog.root if hasattr(project_or_catalog, "version")
            else Path(project_or_catalog) / "contracts")
    contract = read_json(Path(root) / "contracts" / "phases" / (phase + ".json")) or {}
    return CAPABILITY in contract.get("capabilities", [])


def _digest(value):
    from .phase_interactions import digest
    return digest(value)


def _path(project_dir):
    return Path(project_dir) / "researcher" / "problem_context.json"


def _project(project_dir):
    project = read_json(Path(project_dir) / "project.json")
    if not isinstance(project, dict):
        raise ValueError("Unknown project")
    return project


def _brief(project, project_id, revision=1):
    instructions = project_instructions(project)
    return {"kind": "project_brief", "project_id": project_id, "revision": revision,
            "sha256": _digest({"instructions": instructions}), "instructions": instructions}


def validate_scope(scope):
    if not isinstance(scope, dict) or scope.get("kind") not in ("project", "model"):
        raise ValueError("Choose project scope or an exact model scope")
    if scope["kind"] == "project":
        return {"kind": "project"}
    branch, model = scope.get("branch"), scope.get("model_ref")
    if not isinstance(branch, str) or not _IDENT.fullmatch(branch) or not isinstance(model, dict):
        raise ValueError("Model context needs its branch and exact model reference")
    identity = model.get("identity") or model
    exact_identity = (identity.get("stable_id") and identity.get("version") is not None
                      and identity.get("definition_sha256"))
    exact_source = model.get("generation_id") and (model.get("sha256") or model.get("content_sha256"))
    if not exact_identity and not exact_source:
        raise ValueError("A stable model ID alone does not identify a model version")
    return deepcopy(scope)


def scope_applies(scope, branch_id, model_ref=None):
    if not isinstance(scope, dict):
        return False
    if scope.get("kind") == "project":
        return True
    if scope.get("kind") != "model" or scope.get("branch") != branch_id or not model_ref:
        return False
    expected = scope.get("model_ref") or {}
    identity = expected.get("identity") or expected
    actual = model_ref.get("identity") or model_ref
    keys = ("stable_id", "version", "definition_sha256")
    if all(identity.get(key) is not None for key in keys):
        return all(identity.get(key) == actual.get(key) for key in keys)
    return (expected.get("generation_id") == model_ref.get("generation_id")
            and (expected.get("sha256") or expected.get("content_sha256"))
            == (model_ref.get("sha256") or model_ref.get("content_sha256")))


def resolve_context_model(project_dir, scope):
    """Read the exact model named by context, including retained definitions.

    Committed P2 ancestry is the only historical source. A newer definition,
    unfinished run, or orphan publication cannot replace the named version.
    """
    from .methods import _entry_error, _method_documents, get_method
    from .records import committed_packages, read_generation

    scope = validate_scope(scope)
    if scope["kind"] != "model":
        raise ValueError("This context item does not name an exact model")
    project_dir = Path(project_dir)
    reference = scope["model_ref"]
    expected = reference.get("identity") or reference
    identity_keys = ("stable_id", "version", "definition_sha256")
    exact_identity = all(expected.get(key) is not None for key in identity_keys)
    selected = get_method(project_dir, scope["branch"])

    def sourced(model, source):
        result = {**deepcopy(model), "branch_id": scope["branch"], "source_ref": deepcopy(source)}
        result.update({key: source[key] for key in ("generation_id", "sha256", "content_sha256") if source.get(key)})
        return result

    if selected:
        current = sourced(selected, selected.get("source_ref") or {})
        if scope_applies(scope, scope["branch"], current):
            return current
        if exact_identity and selected["method_id"] != expected["stable_id"]:
            raise ValueError("The model context belongs to a different branch definition")
    store = project_dir / "branches" / "trunk" / "phases" / "p2"
    seen = set()
    for package in committed_packages(store):
        for family, pointer in package["records"].items():
            suffix = family.split(".", 1)[-1]
            if "method" not in suffix and suffix != "catalog":
                continue
            key = (family, pointer.get("generation_id"), pointer.get("content_sha256") or pointer.get("sha256"))
            if key in seen:
                continue
            seen.add(key)
            source = {"branch": "trunk", "phase": "P2", "family": family,
                      "generation_id": pointer.get("generation_id"),
                      "sha256": pointer.get("content_sha256") or pointer.get("sha256"),
                      "content_sha256": pointer.get("content_sha256") or pointer.get("sha256"),
                      "run_id": pointer.get("run_id") or pointer.get("source_run_id") or package.get("run_id"),
                      **({"stage_id": pointer["stage_id"]} if pointer.get("stage_id") else {})}
            if not exact_identity and (reference.get("generation_id") != source["generation_id"]
                    or (reference.get("sha256") or reference.get("content_sha256")) != source["sha256"]
                    or reference.get("family", family) != family):
                continue
            matches = []
            for definition in _method_documents(read_generation(store, family, pointer)):
                if _entry_error(definition):
                    continue
                identity = definition.get("identity") or definition.get("method_identity")
                if exact_identity:
                    if any(identity.get(field) != expected[field] for field in identity_keys):
                        continue
                elif reference.get("object_id") and reference["object_id"] != identity["stable_id"]:
                    continue
                elif selected and identity["stable_id"] != selected["method_id"]:
                    continue
                matches.append(definition)
            if len(matches) > 1:
                raise ValueError("The retained model source names several definitions; select its exact model identity")
            if matches:
                definition = matches[0]
                identity = definition.get("identity") or definition.get("method_identity")
                title = definition.get("title") or identity["stable_id"]
                return sourced({"method_id": identity["stable_id"], "identity": identity,
                    "definition": definition, "version": identity["version"],
                    "definition_sha256": identity["definition_sha256"], "name": title, "title": title,
                    "status": definition.get("lifecycle_state", "proposed"), "historical": True,
                    "registered": bool(selected), "selected_identity": identity,
                    "current_identity": (selected or {}).get("current_identity"), "aligned": False}, source)
    raise ValueError("The context's exact model definition is not available in committed P2 history")


def answer_reference(answer):
    from .phase_interactions import issue_source_identity
    return {"kind": "researcher_answer", "attention_id": answer["attention_id"],
            "answer_revision": answer.get("revision", 0),
            "question_ref": deepcopy(answer.get("question_ref") or issue_source_identity(answer.get("attention") or {}))}


def _initial_context(project_dir):
    from .cumulative_attention import current_researcher_answers
    project = _project(project_dir)
    project_id = project.get("project_id") or Path(project_dir).name
    context = {"schema_version": "1.0.0", "project_id": project_id, "revision": 1,
               "brief": _brief(project, project_id), "items": [], "proposals": [],
               "retained_answers": [], "history": []}
    for index, amendment in enumerate(project.get("setting_amendments") or []):
        if not isinstance(amendment, dict) or not isinstance(amendment.get("text"), str) or not amendment["text"].strip():
            continue
        context["items"].append({"item_id": "context.setting." + str(index + 1), "revision": 1,
            "statement": amendment["text"], "origin": "researcher_reported", "scope": {"kind": "project"},
            "status": "confirmed", "answer_refs": [],
            "source_refs": [{"kind": "setting_amendment", "project_id": project_id, "index": index,
                             "sha256": _digest(amendment), **deepcopy(amendment)}], "amends": []})
    for answer in current_researcher_answers(Path(project_dir)):
        question = answer.get("attention") or {}
        # Preserve an old answer's original audience, without interpreting it
        # as a collection fact or widening a P2 preference into shared context.
        audience = answer.get("audience") or question.get("audience")
        if audience is None:
            audience = (["research_lead"] if question.get("phase") == "P2" or question.get("target_phase") == "P2" else
                        ["research_lead", "theorist", "data_analyst"])
        scope = deepcopy(answer.get("scope") or question.get("scope"))
        retained = {"note": answer["note"], "answer_ref": answer_reference(answer),
                    "scope": scope, "audience": deepcopy(audience)}
        context["retained_answers"].append(retained)
        if scope == {"kind": "project"} and answer.get("save_to_context"):
            context["items"].append({"item_id": "context.answer." + _digest(retained["answer_ref"])[:24],
                "revision": 1, "statement": answer["note"], "origin": answer.get("origin", "researcher_reported"),
                "scope": scope, "status": "confirmed", "answer_refs": [retained["answer_ref"]],
                "source_refs": [], "amends": []})
    return context


def load_problem_context(project_dir):
    """Read a saved record or a deterministic adoption preview, without writes."""
    path = _path(project_dir)
    context = read_json(path)
    if path.exists() and (not isinstance(context, dict) or not isinstance(context.get("revision"), int)):
        raise ValueError("The saved problem context is unreadable")
    return deepcopy(context) if context is not None else _initial_context(project_dir)


def initialize_problem_context(project_dir):
    context = load_problem_context(project_dir)
    if not _path(project_dir).exists():
        write_json_atomic(_path(project_dir), context)
    return context


def context_snapshot(context):
    return deepcopy({key: value for key, value in context.items() if key != "history"})


def _save(project_dir, previous, updated):
    if context_snapshot(previous) == context_snapshot(updated):
        return previous
    updated["revision"] = previous["revision"] + 1
    updated["updated_at"] = datetime.now(timezone.utc).isoformat()
    updated["history"] = [*deepcopy(previous.get("history") or []), context_snapshot(previous)]
    write_json_atomic(_path(project_dir), updated)
    return updated


def _expected(context, expected_revision):
    if expected_revision != context["revision"]:
        raise ValueError("The problem context changed; reload it before saving")


def refresh_problem_context_brief(project_dir):
    """Record an explicit brief edit as provenance; confirmed items keep authority."""
    previous = load_problem_context(project_dir)
    brief = _brief(_project(project_dir), previous["project_id"], previous["brief"]["revision"] + 1)
    if brief["sha256"] == previous["brief"]["sha256"]:
        return previous
    updated = deepcopy(previous)
    updated["brief"] = brief
    return _save(project_dir, previous, updated)


def _item(statement, *, item_id, origin, scope, revision, answer_refs=None, source_refs=None, amends=None, topic=None):
    if not isinstance(statement, str) or not statement.strip():
        raise ValueError("A context statement must not be blank")
    if origin not in ORIGINS:
        raise ValueError("Invalid context origin")
    if not isinstance(item_id, str) or not _IDENT.fullmatch(item_id):
        raise ValueError("Invalid context item identity")
    for values in (answer_refs, source_refs, amends):
        if values is not None and (not isinstance(values, list) or any(not isinstance(ref, dict) for ref in values)):
            raise ValueError("Context references must be a list of explicit references")
    if topic is not None and (not isinstance(topic, str) or not topic.strip()):
        raise ValueError("An authored context topic must not be blank")
    return {"item_id": item_id, "statement": statement, "origin": origin, "scope": validate_scope(scope),
            "revision": revision, "status": "confirmed", "answer_refs": deepcopy(answer_refs or []),
            "source_refs": deepcopy(source_refs or []), "amends": deepcopy(amends or []),
            **({"topic": topic} if topic is not None else {})}


def _validate_amendments(project_dir, context, item):
    versions = [context_snapshot(context), *context.get("history", [])]
    for ref in item.get("amends", []):
        if ref.get("kind") == "project_brief":
            briefs = [version["brief"] for version in versions
                      if ref.get("project_id", context["project_id"]) == context["project_id"]
                      and ref.get("revision") == version["brief"]["revision"]
                      and ref.get("sha256") == version["brief"]["sha256"]]
            if not briefs or (ref.get("text") is not None and (not isinstance(ref["text"], str)
                                                              or not ref["text"] or not any(ref["text"] in row["instructions"] for row in briefs))):
                raise ValueError("A brief amendment must identify the exact retained brief and excerpt")
        elif ref.get("kind") == "context_item":
            amended = next((row for version in versions for row in version.get("items", [])
                            if row.get("item_id") == ref.get("item_id") and row.get("revision") == ref.get("revision")), None)
            if amended is None:
                raise ValueError("A context amendment must identify an exact retained item revision")
            if amended.get("scope") != {"kind": "project"} and amended.get("scope") != item.get("scope"):
                raise ValueError("A context amendment cannot widen an exact model's scope")
        elif ref.get("kind") == "researcher_answer":
            if not ref.get("attention_id") or ref.get("answer_revision") is None or not isinstance(ref.get("question_ref"), dict):
                raise ValueError("An answer amendment must identify its exact response and question revision")
            answers = read_json(Path(project_dir) / "researcher" / "attention_resolutions.json") or {}
            current = answers.get(ref["attention_id"]) or {}
            if not isinstance(current, dict) or not any(
                    answer_reference({**row, "attention_id": ref["attention_id"]}) == ref
                    for row in [*(current.get("history") or []), current] if isinstance(row, dict)):
                raise ValueError("The amended researcher answer does not match its retained revision")
        else:
            raise ValueError("An amendment must identify a brief, context item or researcher answer")


def resolve_research_goal(project_dir, reference):
    """Read a goal only from an exact retained, committed P1 basis."""
    from .records import committed_packages, read_generation
    from .research import source_ref

    project_dir = Path(project_dir)
    project_id = _project(project_dir).get("project_id") or project_dir.name
    if (not isinstance(reference, dict) or reference.get("kind") != "research_goal"
            or reference.get("branch") != "trunk" or reference.get("phase") != "P1"
            or reference.get("family") != "research_basis"
            or reference.get("entry_pointer") != RESEARCH_GOAL_POINTER
            or reference.get("project_id", project_id) != project_id):
        raise ValueError("Select this project's exact published P1 research goal")
    generation, digest = reference.get("generation_id"), reference.get("sha256") or reference.get("content_sha256")
    if not generation or not digest or any(reference.get(key) not in (None, digest)
                                           for key in ("sha256", "content_sha256")):
        raise ValueError("The research goal needs its exact generation and digest")
    store = project_dir / "branches" / "trunk" / "phases" / "p1"
    for package in committed_packages(store):
        pointer = package["records"].get("research_basis") or {}
        if (pointer.get("generation_id") != generation
                or (pointer.get("content_sha256") or pointer.get("sha256")) != digest):
            continue
        if package.get("phase", "P1") != "P1" or package.get("branch_id", "trunk") != "trunk":
            raise ValueError("The research goal's committed package belongs to another phase or branch")
        exact = source_ref("trunk", "P1", "research_basis", pointer)
        if any(reference.get(key) is not None and reference[key] != exact.get(key)
               for key in ("run_id", "stage_id", "package_id")):
            continue
        document = read_generation(store, "research_basis", pointer)
        setting = document.get("research_setting") if isinstance(document, dict) else None
        goal = setting.get("research_goal_markdown") if isinstance(setting, dict) else None
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("This published research basis has no research goal")
        return {"goal_source_ref": deepcopy(reference), "research_goal_markdown": goal}
    raise ValueError("The research goal source is not available in committed P1 history")


def _context_source_refs(source_refs, old):
    """Generic edits may not erase or rebind a correction's exact goal."""
    old_goals = [ref for ref in (old or {}).get("source_refs", []) if ref.get("kind") == "research_goal"]
    if not old_goals or source_refs is not None and not isinstance(source_refs, list):
        return source_refs
    supplied = deepcopy(source_refs or [])
    new_goals = [ref for ref in supplied if isinstance(ref, dict) and ref.get("kind") == "research_goal"]
    if new_goals and new_goals != old_goals:
        raise ValueError("A saved goal correction must retain its original research goal source")
    return [*supplied, *[deepcopy(ref) for ref in old["source_refs"] if ref not in supplied]]


def _validate_goal_references(project_dir, item):
    goals = [ref for ref in item.get("source_refs", []) if ref.get("kind") == "research_goal"
             or ref.get("entry_pointer") == RESEARCH_GOAL_POINTER]
    for reference in goals:
        resolve_research_goal(project_dir, reference)
    if goals:
        if item["scope"] != {"kind": "project"}:
            raise ValueError("A research goal correction must use project scope")
        if item.get("topic", "research_goal") != "research_goal":
            raise ValueError("A research goal correction must retain the research_goal topic")
        item["topic"] = "research_goal"


def save_context_item(project_dir, statement, *, expected_revision, item_id=None,
                      origin="researcher_reported", scope=None, answer_refs=None, source_refs=None, amends=None, topic=None):
    previous = load_problem_context(project_dir)
    _expected(previous, expected_revision)
    updated = deepcopy(previous)
    item_id = item_id or "context.item." + str(previous["revision"] + 1)
    old = next((item for item in previous["items"] if item["item_id"] == item_id), None)
    item = _item(statement, item_id=item_id, origin=origin, scope=scope or (old or {}).get("scope") or {"kind": "project"},
                 revision=(old or {}).get("revision", 0) + 1, answer_refs=answer_refs,
                 source_refs=_context_source_refs(source_refs, old), amends=amends if amends is not None else (old or {}).get("amends"),
                 topic=topic if topic is not None else (old or {}).get("topic"))
    _validate_amendments(project_dir, previous, item)
    _validate_goal_references(project_dir, item)
    if old and {**old, "revision": item["revision"]} == item:
        return previous
    # Same identity is an explicit amendment to its prior statement. Retain
    # that exact original in the context history, rather than keeping two accounts.
    updated["items"] = [item if row["item_id"] == item_id else row for row in updated["items"]]
    if old is None:
        updated["items"].append(item)
    for proposal in updated["proposals"]:
        if proposal["status"] == "pending" and proposal["item"]["item_id"] == item_id:
            proposal["status"] = "resolved_by_direct_edit"
            proposal["resolved_item_revision"] = item["revision"]
    return _save(project_dir, previous, updated)


def propose_context_amendment(project_dir, statement, *, expected_revision, item_id=None,
                               origin="proposed_assumption", scope=None, reason="", conflicts_with=None,
                               answer_refs=None, source_refs=None, amends=None, topic=None):
    previous = load_problem_context(project_dir)
    _expected(previous, expected_revision)
    updated = deepcopy(previous)
    item_id = item_id or "context.item." + str(previous["revision"] + 1)
    old = next((row for row in previous["items"] if row["item_id"] == item_id), None)
    item = _item(statement, item_id=item_id, origin=origin, scope=scope or (old or {}).get("scope") or {"kind": "project"},
                 revision=(old or {}).get("revision", 0) + 1, answer_refs=answer_refs,
                 source_refs=_context_source_refs(source_refs, old), amends=amends,
                 topic=topic if topic is not None else (old or {}).get("topic"))
    _validate_amendments(project_dir, previous, item)
    _validate_goal_references(project_dir, item)
    item["status"] = "proposed"
    proposal = {"amendment_id": "amendment." + _digest({"revision": previous["revision"], "item": item})[:24],
                "status": "pending", "item": item, "reason": reason, "conflicts_with": deepcopy(conflicts_with or [])}
    updated["proposals"].append(proposal)
    return _save(project_dir, previous, updated)


def confirm_context_amendment(project_dir, amendment_id, *, expected_revision, statement=None):
    previous = load_problem_context(project_dir)
    _expected(previous, expected_revision)
    updated = deepcopy(previous)
    proposal = next((row for row in updated["proposals"] if row["amendment_id"] == amendment_id), None)
    if not proposal or proposal["status"] != "pending":
        raise ValueError("This context amendment is unavailable or has already been dispositioned")
    item = deepcopy(proposal["item"])
    if statement is not None:
        if not isinstance(statement, str) or not statement.strip():
            raise ValueError("A confirmed context statement must not be blank")
        item["statement"] = statement
    old = next((row for row in updated["items"] if row["item_id"] == item["item_id"]), None)
    item["source_refs"] = _context_source_refs(item.get("source_refs"), old) or []
    _validate_goal_references(project_dir, item)
    item["revision"] = (old or {}).get("revision", 0) + 1
    item["status"] = "confirmed"
    updated["items"] = [item if row["item_id"] == item["item_id"] else row for row in updated["items"]]
    if old is None:
        updated["items"].append(item)
    proposal.update(status="confirmed", confirmed_item_revision=item["revision"])
    return _save(project_dir, previous, updated)


def effective_account(context, branch_id="trunk", model_ref=None):
    items = [deepcopy(item) for item in context["items"]
             if item.get("status") == "confirmed" and scope_applies(item.get("scope"), branch_id, model_ref)]
    # Only explicit exact excerpts are removed. A general amendment retains
    # the unclassified narrative and states authority for its declared subject.
    unamended = context["brief"]["instructions"]
    for item in items:
        for ref in item.get("amends", []):
            if ref.get("kind") == "project_brief" and isinstance(ref.get("text"), str) and ref["text"]:
                unamended = unamended.replace(ref["text"], "")
    superseded = {ref.get("item_id") for item in items for ref in item.get("amends", [])
                  if ref.get("kind") == "context_item" and ref.get("item_id") != item["item_id"]}
    items = [item for item in items if item["item_id"] not in superseded]
    return {"unamended_instructions": unamended, "items": items,
            "incorporated_answer_refs": [deepcopy(ref) for item in items for ref in item.get("answer_refs", [])],
            "pending_amendments": [deepcopy(row) for row in context["proposals"] if row["status"] == "pending"
                                   and scope_applies(row["item"].get("scope"), branch_id, model_ref)],
            "authority_note": "Confirmed items govern only their explicit amendments. Retain unamended brief instructions. "
                              "Pending amendments and researcher uncertainty are unresolved; they do not establish a scientific assumption."}


def frozen_problem_context(project_dir, branch_id="trunk", model_ref=None):
    context = load_problem_context(project_dir)
    snapshot = context_snapshot(context)
    return {**snapshot, "sha256": _digest(snapshot), "effective_account": effective_account(context, branch_id, model_ref),
            "answer_routes": _frozen_context_answer_routes(project_dir, context)}


def _frozen_context_answer_routes(project_dir, context):
    """Freeze routing for exact mirrored answers, including earlier edits.

    Current applicable answers need not contain a mirror's original revision
    or model scope. Retain only its routing metadata, without changing the
    researcher-owned statement or reading live answers when rendering briefs.
    """
    refs = [ref for item in [*context.get("items", []),
                             *(row["item"] for row in context.get("proposals", []))]
            for ref in item.get("answer_refs", [])]
    stored = read_json(Path(project_dir) / "researcher" / "attention_resolutions.json") or {}
    routes = []
    for attention_id, current in stored.items():
        if not isinstance(current, dict):
            continue
        for answer in [*current.get("history", []), current]:
            if not isinstance(answer, dict):
                continue
            ref = answer_reference({**answer, "attention_id": attention_id})
            if ref not in refs:
                continue
            question = answer.get("attention") or {}
            routes.append({"answer_ref": ref,
                "scope": deepcopy(answer.get("scope") or question.get("scope")),
                "audience": deepcopy(answer.get("audience") or question.get("audience")),
                "attention": {key: deepcopy(question[key]) for key in
                              ("kind", "phase", "target_phase", "generation_ref") if key in question}})
    return routes


def role_effective_account(context, role, *, answers=(), branch_id="trunk", model_ref=None):
    """Project mirrored context using its exact frozen answer audiences."""
    if role not in ("theorist", "data_analyst"):
        return deepcopy(context.get("effective_account") or {})
    from .p2_delivery import specialist_view

    routes = [*context.get("answer_routes", []), *context.get("retained_answers", []),
              *({**answer, "answer_ref": answer_reference(answer)} for answer in answers)]

    def visible(item):
        authorized = {"item_id": item["item_id"], "revision": item["revision"],
                      "answer_refs": item.get("answer_refs", [])}
        if authorized in context.get("authorized_context_refs", []):
            # Explicit continuation acceptance shares this exact amendment
            # within its applicable scope, not the requester's raw response.
            return True
        for ref in item.get("answer_refs", []):
            if ref.get("kind") != "researcher_answer":
                continue
            route = next((row for row in routes if row.get("answer_ref") == ref), None)
            if route is None:
                # An old frozen basis may lack the exact answer. Do not infer
                # an audience from its topic or another revision. P2's legacy
                # default remains Lead-only; unrelated unknowns stay visible.
                if (ref.get("question_ref") or {}).get("phase") == "P2":
                    return False
                continue
            if route.get("scope") is not None and not scope_applies(route["scope"], branch_id, model_ref):
                return False
            view = specialist_view("P2", "researcher_answers",
                                   {"items": [{**route, "attention": route.get("attention") or {}}]}, role=role)
            if view is not None and not view["items"]:
                return False
        return True

    document = deepcopy(context.get("document", context))
    items = {item["item_id"]: item for item in document.get("items", [])}
    items.update({item["item_id"]: deepcopy(item) for item in context.get("authorized_context_items", [])})
    document["items"] = [item for item in items.values() if visible(item)]
    document["proposals"] = [row for row in document.get("proposals", []) if visible(row["item"])]
    # Rebuild from the original brief, not an account whose restricted
    # amendments already removed text or superseded a shared statement.
    return effective_account(document, branch_id, model_ref)


def project_context_target(project_dir, item_id=None, *, goal_source_ref=None):
    context = load_problem_context(project_dir)
    if item_id and not any(item["item_id"] == item_id for item in context["items"]):
        raise ValueError("Unknown problem context item")
    if goal_source_ref is not None:
        resolve_research_goal(project_dir, goal_source_ref)
    return {"kind": "project_context", "project_id": context["project_id"], "context_revision": context["revision"],
            "brief_revision": context["brief"]["revision"], "sha256": _digest(context_snapshot(context)),
            **({"object_id": item_id} if item_id else {}),
            **({"goal_source_ref": deepcopy(goal_source_ref)} if goal_source_ref is not None else {})}


def resolve_project_context_target(project_dir, target):
    context = load_problem_context(project_dir)
    if not isinstance(target, dict) or target.get("kind") != "project_context" or target.get("project_id") != context["project_id"]:
        raise ValueError("Select this project's exact problem context")
    version = next((row for row in [context_snapshot(context), *context.get("history", [])]
                    if row.get("revision") == target.get("context_revision")
                    and row.get("brief", {}).get("revision") == target.get("brief_revision")
                    and _digest(row) == target.get("sha256")), None)
    if version is None:
        raise ValueError("The problem context target does not match a retained revision")
    item = next((row for row in version["items"] if row["item_id"] == target.get("object_id")), None)
    if target.get("object_id") and item is None:
        raise ValueError("The context item is absent from this exact revision")
    goal = resolve_research_goal(project_dir, target["goal_source_ref"]) if "goal_source_ref" in target else {}
    if goal and item and (item.get("scope") != {"kind": "project"} or
            any(ref.get("kind") == "research_goal" and ref != goal["goal_source_ref"] for ref in item.get("source_refs", []))):
        raise ValueError("The context item belongs to a different research goal or scope")
    return {"issue_id": target.get("object_id") or "context." + str(version["revision"]),
            "title": "Discuss research goal" if goal else (item or {}).get("statement") or "Discuss your problem", "kind": "researcher_decision",
            "summary_markdown": goal.get("research_goal_markdown") or (item or {}).get("statement") or version["brief"]["instructions"],
            "responsible_role": "research_lead", "scope": (item or {}).get("scope") or {"kind": "project"},
            "audience": ["research_lead"], "explanation_target": deepcopy(target),
            "problem_context": deepcopy(version), **goal}


def context_change_notices(frozen_context, current_context, dependencies=None):
    """Only authored item relationships warrant a reassessment notice."""
    before = {row["item_id"]: row for row in frozen_context.get("items", [])}
    after = {row["item_id"]: row for row in current_context.get("items", [])}
    changed = [key for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)]
    cited = {ref["item_id"] for ref in dependencies or [] if ref.get("item_id") in before
             and ref.get("revision") == before[ref["item_id"]]["revision"]}
    return [{"item_id": key, "previous_revision": (before.get(key) or {}).get("revision"),
             "current_revision": (after.get(key) or {}).get("revision"),
             "status": "reassessment_required" if key in cited else "context_changed"} for key in changed]


def applicable_researcher_answers(*args, **kwargs):
    from .cumulative_attention import applicable_researcher_answers as route_answers
    return route_answers(*args, **kwargs)


def save_scoped_answer(*args, **kwargs):
    from .phase_interactions import save_scoped_answer as save_answer
    return save_answer(*args, **kwargs)
