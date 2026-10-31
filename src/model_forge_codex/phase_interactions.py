"""Exact issue references and researcher drafts, separate from scientific records."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .records import ArtifactError, committed_packages, current_records, read_generation
from .storage import read_json, write_json_atomic


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def preparation_path(project_dir, branch, phase):
    if phase not in ("P1", "P2", "P3", "P4", "P5") or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", branch):
        raise ValueError("Invalid research phase or method")
    if not (project_dir / "project.json").is_file():
        raise ValueError("Unknown project")
    if branch != "trunk":
        from .methods import _catalog_methods, get_method
        if branch not in _catalog_methods(project_dir) and not get_method(project_dir, branch):
            raise ValueError("Unknown proposed method")
    return project_dir / "researcher" / "preparation" / phase / (branch + ".json")


def _legacy_preparation(path):
    """Only common trunk P2 drafts can read the old shared preparation."""
    if path.name == "trunk.json" and path.parent.name == "P2" and path.parent.parent.name == "preparation":
        return path.parent.parent.parent / "p2_preparation.json"
    return None


def _read_preparation(path):
    if path.exists():
        return read_json(path)
    legacy = _legacy_preparation(path)
    return read_json(legacy) if legacy else None


def load_preparation(project_dir, branch, phase):
    """Read without migrating or merging drafts; the common file wins."""
    return _read_preparation(preparation_path(project_dir, branch, phase)) or {
        "instructions": "", "updated_at": None, "revision": 0,
    }


def save_preparation(path, instructions, *, input_ids=None):
    previous = _read_preparation(path) or {}
    selection = previous.get("input_ids", []) if input_ids is None else input_ids
    if path.is_file() and previous.get("instructions") == instructions and previous.get("input_ids", []) == selection:
        return previous
    result = {"instructions": instructions, "updated_at": datetime.now(timezone.utc).isoformat(),
              "revision": previous.get("revision", 0) + 1}
    if selection or input_ids is not None or "input_ids" in previous:
        result["input_ids"] = selection
    write_json_atomic(path, result)
    return result


def _entries(document, family):
    """Enumerate contracted issue containers, never guessed concerns in prose."""
    if not isinstance(document, (dict, list)):
        return
    suffix = family.split(".", 1)[-1]
    if suffix == "attention_items":
        values = document if isinstance(document, list) else document.get("items", [])
        for i, item in enumerate(values):
            yield item, f"/{i}" if isinstance(document, list) else f"/items/{i}", None
    if suffix in ("review_issues", "review_issue_ledger"):
        values = document if isinstance(document, list) else document.get("issues", document.get("items", []))
        key = "issues" if isinstance(document, dict) and "issues" in document else "items"
        for i, item in enumerate(values):
            yield item, f"/{i}" if isinstance(document, list) else f"/{key}/{i}", None
    if isinstance(document, dict):
        for key in ("prioritized_issues", "findings", "issues"):
            if suffix in ("review_issues", "review_issue_ledger"):
                continue
            if key == "findings" and suffix not in ("theory_review", "empirical_review", "theory_audit", "empirical_audit"):
                continue
            for i, item in enumerate(document.get(key, []) or []):
                yield item, f"/{key}/{i}", None
        for i, assessment in enumerate(document.get("assessments", []) or []):
            if not isinstance(assessment, dict):
                continue
            for j, item in enumerate(assessment.get("findings", []) or []):
                yield item, f"/assessments/{i}/findings/{j}", assessment.get("proposal_id")


def issue_projection(document, meta):
    from .research import record_url
    ref = meta["generation_ref"]
    family = ref["family"]
    suffix = family.split(".", 1)[-1]
    default_role = ("outside_reviewer" if suffix == "outside_review" else
                    "theorist" if suffix in ("theory_review", "theory_audit", "theory_proposal_audit") else
                    "data_analyst" if suffix in ("empirical_review", "empirical_audit", "analyst_synthesis", "empirical_proposal_audit") else "research_lead")
    for item, pointer, proposal in _entries(document, family):
        if not isinstance(item, dict):
            continue
        object_id = item.get("attention_id") or item.get("issue_id") or item.get("finding_id")
        if not object_id:
            continue
        role = item.get("raised_by") or item.get("requested_by") or item.get("responsible_role") or default_role
        if role not in ("research_lead", "theorist", "data_analyst", "outside_reviewer"):
            role = default_role
        target = {key: ref.get(key) for key in ("branch", "phase", "family", "generation_id", "sha256", "run_id", "package_id")}
        target.update(kind="phase_issue", entry_pointer=pointer, object_id=object_id)
        identity = ({"branch": ref["branch"], "phase": ref["phase"], "object_id": object_id,
                     "issue_version_id": item["issue_version_id"]} if item.get("issue_version_id") else target)
        issue_id = item.get("attention_id") or "issue." + digest(identity)[:32]
        exact = {**ref, "entry_pointer": pointer}
        title = item.get("title") or item.get("question") or item.get("issue") or item.get("statement") or item.get("statement_reference") or object_id
        yield {**item, **meta, "issue_id": issue_id, "object_id": object_id,
               "title": title, "summary_markdown": item.get("reasoning_markdown") or item.get("issue") or item.get("reason") or item.get("question") or item.get("statement", ""),
               "consequence_markdown": item.get("consequence_markdown") or item.get("scientific_consequence") or item.get("likely_consequence") or item.get("consequence", ""),
               "recommendation": item.get("recommendation") or item.get("requested_resolution") or "",
               "kind": item.get("kind") or "scientific_issue", "original_role": role,
               "proposal_id": proposal,
               "responsible_role": "research_lead" if role == "outside_reviewer" else role,
               "affected_record_ids": item.get("affected_record_ids") or ([proposal] if proposal else []),
               "generation_ref": exact, "entry_ref": exact, "source_url": record_url(meta.get("project_id", ""), exact),
               "explanation_target": target}


def published_issues(project_dir, branch=None):
    from .research import source_ref
    from .cumulative_attention import open_attention_items
    result = []
    for branch_dir in sorted((project_dir / "branches").glob("*")):
        if branch is not None and branch_dir.name != branch:
            continue
        for phase_dir in sorted((branch_dir / "phases").glob("p[1-5]")):
            try:
                pointers = current_records(phase_dir)
            except ArtifactError:
                continue
            for family, pointer in pointers.items():
                if family.split(".", 1)[-1] == "attention_items":
                    continue
                try:
                    document = read_generation(phase_dir, family, pointer)
                except ArtifactError:
                    continue
                meta = {"project_id": project_dir.name, "phase": phase_dir.name.upper(), "branch": branch_dir.name,
                        "family": family, "generation_ref": source_ref(branch_dir.name, phase_dir.name.upper(), family, pointer)}
                result.extend(_method_scope(project_dir, item) for item in issue_projection(document, meta))
    # Attention is cumulative, including unresolved questions from older runs.
    try:
        attention_items = open_attention_items(project_dir, {})
    except ArtifactError:
        attention_items = []
    for attention in attention_items:
        if branch is not None and attention["branch"] != branch:
            continue
        ref = attention["generation_ref"]
        target = {key: ref.get(key) for key in ("branch", "phase", "family", "generation_id", "sha256", "run_id", "package_id", "entry_pointer")}
        target.update(kind="phase_issue", object_id=attention["attention_id"])
        role = attention.get("raised_by") or "research_lead"
        result.append({**attention, "issue_id": attention["attention_id"], "title": attention.get("question", ""),
                       "summary_markdown": attention.get("question", ""), "original_role": role,
                       "responsible_role": "research_lead" if role == "outside_reviewer" else role,
                       "explanation_target": target})
    # P5's reports and lead dispositions share explicit issue IDs. Retain one
    # response form, preferring the current disposition with its original text.
    review_entries = {}
    other = []
    priority = {"review_issue_ledger": 3, "review_issues": 2, "outside_review": 1}
    for issue in result:
        if issue.get("phase") != "P5" or not issue.get("object_id") or issue.get("kind") != "scientific_issue":
            other.append(issue)
            continue
        key = (issue["branch"], issue["object_id"])
        previous = review_entries.get(key)
        if previous is None or priority.get(issue.get("family"), 0) > priority.get(previous.get("family"), 0):
            review_entries[key] = issue
    result = other + list(review_entries.values())
    answers = answers_with_usage(project_dir)
    from .cumulative_attention import answer_for_question
    for issue in result:
        issue["researcher_answer"] = answer_for_question(project_dir, issue, answers)
    return result


def resolve_issue(project_dir, target):
    """Resolve a permitted historical entry, with exact source and entry identity."""
    if target.get("kind") == "notation_entry":
        from .notation_interactions import notation_issue
        return notation_issue(project_dir, target)
    if target.get("kind") != "phase_issue":
        raise ValueError("Select an identified scientific issue")
    branch, phase, family = (target.get(key, "") for key in ("branch", "phase", "family"))
    if not all(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) for value in (branch, family)) or phase not in ("P1", "P2", "P3", "P4", "P5"):
        raise ValueError("Invalid issue source")
    phase_dir = project_dir / "branches" / branch / "phases" / phase.lower()
    pointer = next((package["records"][family] for package in committed_packages(phase_dir)
                    if family in package["records"]
                    and package["records"][family].get("generation_id") == target.get("generation_id")
                    and package["records"][family].get("content_sha256") == target.get("sha256")
                    and package["records"][family].get("run_id") == target.get("run_id")
                    and package["records"][family].get("package_id") == target.get("package_id")), None)
    if not pointer:
        raise ValueError("The issue source does not match its committed publication")
    document = read_generation(phase_dir, family, pointer)
    meta = {"project_id": project_dir.name, "branch": branch, "phase": phase, "family": family,
            "generation_ref": {key: target.get(key) for key in ("branch", "phase", "family", "generation_id", "sha256", "run_id", "stage_id", "package_id")}}
    match = next((item for item in issue_projection(document, meta)
                  if item["object_id"] == target.get("object_id") and item["entry_ref"]["entry_pointer"] == target.get("entry_pointer")), None)
    if not match:
        raise ValueError("The issue is absent from its exact source version")
    return _method_scope(project_dir, match)


def _method_scope(project_dir, issue):
    """A P2 finding targets a proposal; method scope comes from that exact run."""
    if issue.get("phase") != "P2" or not issue.get("proposal_id"):
        return issue
    ref = issue["generation_ref"]
    phase_dir = project_dir / "branches" / ref["branch"] / "phases" / "p2"
    for package in committed_packages(phase_dir):
        for family, pointer in package["records"].items():
            if family.split(".", 1)[-1] not in ("lead_proposal", "theory_proposal", "empirical_proposal") or pointer.get("run_id") != ref.get("run_id"):
                continue
            try:
                document = read_generation(phase_dir, family, pointer)
            except ArtifactError:
                continue
            if isinstance(document, dict) and document.get("proposal_id") == issue["proposal_id"]:
                identity = (document.get("method") or {}).get("identity") or {}
                if identity.get("stable_id"):
                    issue.update(method_id=identity["stable_id"], affected_record_ids=[identity["stable_id"]])
                    return issue
    return issue


def pause_target(record, request):
    return {"kind": "p4_pause", "phase": "P4", "branch": record.branch_id, "run_id": record.run_id,
            "request_id": request["request_id"], "object_id": request["request_id"],
            "revision": request["revision"], "sha256": digest(request)}


def issue_source_identity(question):
    """Identity of an editable response's original question, including old attention."""
    target = question.get("explanation_target")
    if not isinstance(target, dict):
        ref = question.get("generation_ref") or {}
        if not isinstance(ref, dict) or not ref.get("generation_id"):
            return None
        target = {**ref, "kind": "phase_issue",
                  "entry_pointer": question.get("entry_pointer") or ref.get("entry_pointer"),
                  "object_id": question.get("object_id") or question.get("attention_id")}
    if target.get("kind") == "project_context":
        return {key: target.get(key) for key in ("kind", "project_id", "context_revision", "brief_revision", "sha256", "object_id")}
    if target.get("kind") in ("researcher_pause", "p4_pause"):
        return {key: target.get(key) for key in ("kind", "project_id", "branch", "phase", "run_id", "stage_id",
                                                "request_id", "object_id", "revision", "sha256")}
    identity = {key: target.get(key) for key in ("kind", "branch", "phase", "family", "generation_id", "sha256",
                                                "run_id", "package_id", "entry_pointer", "object_id")}
    return identity


def exact_saved_answer(project_dir, question):
    """Read the latest response to this exact item, without stable-ID fallback."""
    from .cumulative_attention import retained_researcher_answers
    identity = issue_source_identity(question)
    if identity is None:
        return None
    saved = max((answer for answer in retained_researcher_answers(project_dir)
                 if (answer.get("question_ref") or issue_source_identity(answer.get("attention") or {})) == identity),
                key=lambda answer: answer.get("revision", 0), default=None)
    if saved is not None:
        return saved
    # Older evaluation pauses stored responses only beside their source run.
    if identity.get("kind") == "p4_pause" and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", identity.get("run_id") or ""):
        answers = read_json(project_dir / "runs" / identity["run_id"] / "p4-decision-answers.json") or []
        saved = max((answer for answer in answers if answer.get("request_id") == identity.get("request_id")
                     and answer.get("request_revision") == identity.get("revision")
                     and digest(answer.get("request")) == identity.get("sha256")),
                    key=lambda answer: answer.get("revision", 0), default=None)
        if saved is not None:
            return {**saved, "question_ref": identity}
    return None


def selected_response(question, selection, *, origin="researcher_reported"):
    """Resolve a choice against its exact authored question, never client prose."""
    if not isinstance(selection, dict) or set(selection) - {"option_id", "note"}:
        raise ValueError("Select an option from this question and add an optional note")
    if question.get("response_kind") != "choice" or origin != "researcher_reported":
        raise ValueError("A selected choice cannot also be recorded as unknown study information")
    option_id, extra = selection.get("option_id"), selection.get("note", "")
    if not isinstance(option_id, str) or not isinstance(extra, str):
        raise ValueError("The selected option and optional note must be text")
    options = question.get("options")
    if (not isinstance(options, list) or not options
            or any(not isinstance(option, dict)
                   or any(not isinstance(option.get(key), str) or not option[key].strip()
                          for key in ("id", "label", "consequence")) for option in options)
            or len({option["id"] for option in options}) != len(options)):
        raise ValueError("This question does not contain identifiable selectable options")
    option = next((option for option in options if option["id"] == option_id), None)
    if option is None:
        raise ValueError("This option is not part of the exact question you are answering")
    extra = extra.strip()
    snapshot = {"option_id": option_id, "label": option["label"],
                "consequence": option["consequence"], "note": extra}
    note = f"Selected option: {option['label']}\n\n{option['consequence']}"
    if extra:
        note += f"\n\nYour note: {extra}"
    return note, snapshot


def normalize_response_draft(question, draft):
    """Bind discussion-only input to its resolved question without saving it.

    The caller resolves the exact target first. Choice prose comes only from
    that source, while custom text and uncertainty remain researcher input.
    """
    if not isinstance(draft, dict) or set(draft) - {"kind", "option_id", "note"}:
        raise ValueError("A response draft needs its response kind and optional note")
    kind, note = draft.get("kind"), draft.get("note", "")
    if kind not in ("choice", "custom", "unknown") or not isinstance(note, str):
        raise ValueError("A response draft must be a choice, custom response or unknown")
    if question.get("kind") in ("research_task", "scientific_issue"):
        raise ValueError("A researcher response draft belongs to a researcher question")
    if issue_source_identity(question) is None:
        raise ValueError("A response draft needs its exact original question target")
    if kind == "choice":
        _, snapshot = selected_response(question, {"option_id": draft.get("option_id"), "note": note})
        return {"kind": kind, **snapshot}
    if "option_id" in draft:
        raise ValueError("Only a selected choice can name an option")
    if kind == "custom" and not note.strip():
        raise ValueError("Write your alternative response before including it in discussion")
    return {"kind": kind, "note": note.strip()}


def save_scoped_answer(project_dir, question, note, *, expected_revision=None, save_to_context=False,
                       origin="researcher_reported", context_item_id=None, context_expected_revision=None,
                       amends=None, conflicts_with=None, topic=None, selection=None):
    """Save exact researcher words; optional project-scope context is one action.

    A successor question keeps the stable attention ID, starts with no response,
    and retains its predecessor in the same existing answer history.
    """
    from .problem_context import (answer_reference, initialize_problem_context, load_problem_context,
                                  resolve_project_context_target, save_context_item, validate_scope)
    selected = None
    if selection is not None:
        note, selected = selected_response(question, selection, origin=origin)
    if not isinstance(note, str) or not note.strip():
        raise ValueError("Record your response before saving")
    if origin not in ("researcher_reported", "unknown"):
        raise ValueError("A direct researcher response records a report or uncertainty")
    if question.get("kind") == "research_task":
        raise ValueError("Team research tasks need a scientific disposition")
    identifier = question.get("attention_id") or question.get("issue_id")
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", identifier):
        raise ValueError("Select an identified researcher question")
    question_ref = issue_source_identity(question)
    if question_ref is None:
        raise ValueError("The response needs its exact original question target")
    if question_ref["kind"] == "project_context":
        resolve_project_context_target(project_dir, question_ref)
        # Saving makes an early target durable even without a context amendment.
        initialize_problem_context(project_dir)
    scope = validate_scope(question["scope"]) if question.get("scope") is not None else None
    audience = question.get("audience")
    if audience is None and (question.get("phase") == "P2" or question.get("target_phase") == "P2"):
        audience = ["research_lead"]
    elif audience is None and scope is not None:
        audience = [question.get("responsible_role") or question.get("raised_by") or "research_lead"]
    if audience is not None and (not isinstance(audience, list) or not audience
            or any(role not in ("research_lead", "theorist", "data_analyst") for role in audience)):
        raise ValueError("The response needs an explicit responsible audience")
    if save_to_context and question.get("scope") != {"kind": "project"}:
        raise ValueError("Only an explicitly project-scope response can be saved as shared context")
    path = project_dir / "researcher" / "attention_resolutions.json"
    stored = read_json(path) or {}
    previous = stored.get(identifier) or {}
    if not isinstance(previous, dict):
        raise ValueError("The saved response is unreadable")
    # optimistic revision is per exact question, while stored response
    # revisions remain monotonic under the stable ID for unambiguous references.
    def stored_source(row):
        return row.get("question_ref") or issue_source_identity(row.get("attention") or {})
    exact_previous = previous if stored_source(previous) == question_ref else next(
        (row for row in reversed(previous.get("history") or [])
         if stored_source(row) == question_ref), {})
    if expected_revision is not None and expected_revision != exact_previous.get("revision", 0):
        raise ValueError("Your saved response changed; reload it before saving")
    topic = topic if topic is not None else question.get("topic", exact_previous.get("topic"))
    if topic is not None and (not isinstance(topic, str) or not topic.strip()):
        raise ValueError("An authored context topic must not be blank")
    if (exact_previous.get("note") == note and exact_previous.get("save_to_context", False) == save_to_context
            and exact_previous.get("selection") == selected
            and exact_previous.get("origin", "researcher_reported") == origin
            and exact_previous.get("topic") == topic
            and exact_previous.get("amends") == (amends or None)
            and exact_previous.get("conflicts_with") == (conflicts_with or None)):
        return {**{key: value for key, value in exact_previous.items() if key != "history"}, "attention_id": identifier}
    context = load_problem_context(project_dir) if save_to_context else None
    if context is not None:
        if context_expected_revision is not None and context_expected_revision != context["revision"]:
            raise ValueError("The problem context changed; reload it before saving")
        if origin not in ("researcher_reported", "unknown"):
            raise ValueError("A direct researcher response records a report or uncertainty")
    history = list(previous.get("history") or [])
    if previous:
        history.append({key: value for key, value in previous.items() if key != "history"})
    answer = {"note": note, "revision": previous.get("revision", 0) + 1,
              "resolved_at": datetime.now(timezone.utc).isoformat(),
              "attention": deepcopy_question(question), "question_ref": question_ref,
              "scope": scope, **({"audience": list(audience)} if audience is not None else {}), "save_to_context": save_to_context,
              "origin": origin, **({"conflicts_with": conflicts_with} if conflicts_with else {}),
              **({"selection": selected} if selected is not None else {}),
              **({"topic": topic} if topic is not None else {}), **({"amends": amends} if amends else {}),
              **({"history": history} if history else {})}
    result = {**{key: value for key, value in answer.items() if key != "history"}, "attention_id": identifier}
    if context is not None:
        reference = answer_reference(result)
        item_id = context_item_id or "context.answer." + digest({"attention_id": identifier, "question_ref": question_ref})[:24]
        if context_item_id is None:
            # Reuse only this exact question's mirror. Adopted answers and
            # explicit custom IDs need not use the current default identity.
            versions = [row for row in [previous, *reversed(previous.get("history") or [])]
                        if stored_source(row) == question_ref]
            prior_refs = [answer_reference({**row, "attention_id": identifier}) for row in versions]
            items = {row["item_id"]: row for row in context["items"]}
            linked_ids = [(row.get("context_ref") or {}).get("item_id") for row in versions]
            mirror = next((items[key] for key in linked_ids if key in items
                           and (not items[key].get("answer_refs") or any(ref in prior_refs for ref in items[key]["answer_refs"]))), None)
            if mirror is None:
                mirror = next((row for row in context["items"] if row["item_id"].startswith("context.answer.")
                               and any(ref in prior_refs for ref in row.get("answer_refs", []))), None)
            if mirror is not None:
                item_id = mirror["item_id"]
            elif item_id in items:
                raise ValueError("This context item belongs to a different answer. Edit your answer at its original question.")
        existing_item = next((row for row in context["items"] if row["item_id"] == item_id), {})
        context_amends = list(amends if amends is not None else existing_item.get("amends") or [])
        for link in question.get("answer_applicability_refs", []) or []:
            if (link.get("attention_id") != identifier or link.get("question_ref") == question_ref
                    or not isinstance(link.get("reason"), str) or not link["reason"].strip()):
                continue
            predecessor = {"kind": "researcher_answer", **{key: link.get(key)
                           for key in ("attention_id", "answer_revision", "question_ref")}}
            for item in context["items"]:
                if item["item_id"] != item_id and item.get("scope") == scope and item.get("answer_refs") == [predecessor]:
                    amendment = {"kind": "context_item", "item_id": item["item_id"], "revision": item["revision"]}
                    if amendment not in context_amends:
                        context_amends.append(amendment)
        # Validate the context write before retaining the answer. The two
        # stores link exact revisions. Replacing an explicitly carried answer
        # supersedes its original mirror without removing its context history.
        context = save_context_item(project_dir, note, expected_revision=context["revision"], item_id=item_id,
                                    origin=origin, scope=scope, answer_refs=[reference], amends=context_amends, topic=topic,
                                    _answer_sync=True)
        answer["context_ref"] = {"item_id": item_id, "revision": next(row["revision"] for row in context["items"] if row["item_id"] == item_id),
                                 "context_revision": context["revision"]}
        result["context_ref"] = answer["context_ref"]
    stored[identifier] = answer
    write_json_atomic(path, stored)
    return result


def deepcopy_question(question):
    from copy import deepcopy
    return deepcopy({key: value for key, value in question.items() if key != "researcher_answer"})


def answers_with_usage(project_dir):
    """UI answers, including minimal retained links to their context copies."""
    from copy import deepcopy
    from .cumulative_attention import current_researcher_answers, retained_researcher_answers, versioned_question
    answers = current_researcher_answers(project_dir)
    if any(versioned_question(row.get("attention") or {}) for row in answers):
        answers = sorted(retained_researcher_answers(project_dir), key=lambda row: (row["attention_id"], -row.get("revision", 0)))
    stored = read_json(Path(project_dir) / "researcher" / "attention_resolutions.json") or {}
    for answer in answers:
        # Keep ownership visible after a later edit stops saving context.
        # These links belong only to the UI projection, not routed research
        # inputs, and retain no earlier answer text or question content.
        current = stored.get(answer["attention_id"]) or {}
        source = answer.get("question_ref") or issue_source_identity(answer.get("attention") or {})
        ownership = [{"revision": row.get("revision", 0), "question_ref": deepcopy(source),
                      "context_ref": deepcopy(row["context_ref"])}
                     for row in current.get("history", []) if isinstance(row, dict)
                     and isinstance(row.get("context_ref"), dict) and row["context_ref"].get("item_id")
                     and row.get("revision", 0) != answer.get("revision", 0)
                     and (row.get("question_ref") or issue_source_identity(row.get("attention") or {})) == source]
        if ownership:
            answer["history"] = ownership
        answer["applied_to"] = []
        answer["previously_applied_to"] = []
    for basis_path in (project_dir / "runs").glob("*/basis.json"):
        run = read_json(basis_path.parent / "run.json") or {}
        if run.get("intent") == "assessment":
            continue
        basis = read_json(basis_path) or {}
        ref = basis.get("cumulative_inputs", {}).get("researcher_answers", {})
        document = read_json(Path(ref["snapshot_path"])) if ref.get("snapshot_path") else ref.get("document")
        if document and digest(document) != ref.get("sha256"):
            continue
        for used in (document or {}).get("items", []):
            answer = next((a for a in answers if a["attention_id"] == used.get("attention_id")
                           and (a.get("question_ref") is None or a.get("question_ref") == used.get("question_ref"))
                           and a.get("revision", 0) == used.get("revision", 0)), None)
            if answer is None:
                answer = next((a for a in answers if a["attention_id"] == used.get("attention_id")
                               and (a.get("question_ref") is None or a.get("question_ref") == used.get("question_ref"))), None)
            if answer is not None:
                key = "applied_to" if answer.get("resolved_at") == used.get("resolved_at") else "previously_applied_to"
                answer[key].append(run["run_id"])
    return answers


def completed_evaluation_answers(project_dir, branch):
    """Past evaluation choices reach a new evaluation only at explicit launch."""
    result = []
    for path in (project_dir / "runs").glob("*/p4-decision-answers.json"):
        run = read_json(path.parent / "run.json") or {}
        if (run.get("phase") != "P4" or run.get("intent", "run") != "run" or run.get("branch_id") != branch
                or run.get("state") not in ("published", "failed", "cancelled")):
            continue
        latest = {}
        for answer in read_json(path) or []:
            latest[answer["request_id"]] = answer
        for answer in latest.values():
            if not answer.get("note", "").strip():
                continue
            if answer.get("answer_ref"):
                # Revised runs retain this response in the scoped shared
                # answer history. Deliver it once through that exact router.
                continue
            result.append({"attention_id": "pause." + run["run_id"] + "." + answer["request_id"],
                           "note": answer["note"], "revision": answer["revision"], "resolved_at": answer["saved_at"],
                           "attention": {**answer["request"], "phase": "P4", "target_phase": "P4", "branch": branch,
                                         "kind": "researcher_decision", "source_run_id": run["run_id"]}})
    return result


def evaluation_answer_consumers(project_dir, source_run_id):
    result = {}
    prefix = "pause." + source_run_id + "."
    saved = read_json(project_dir / "runs" / source_run_id / "p4-decision-answers.json") or []
    for path in (project_dir / "runs").glob("*/basis.json"):
        run = read_json(path.parent / "run.json") or {}
        if run.get("intent", "run") != "run":
            continue
        ref = (read_json(path) or {}).get("cumulative_inputs", {}).get("researcher_answers", {})
        document = read_json(Path(ref["snapshot_path"])) if ref.get("snapshot_path") else ref.get("document")
        if not document or digest(document) != ref.get("sha256"):
            continue
        for answer in document.get("items", []):
            if answer.get("attention_id", "").startswith(prefix):
                from .problem_context import answer_reference
                exact = next((row for row in saved if row.get("answer_ref") == answer_reference(answer)), None)
                revision = exact["revision"] if exact else answer.get("revision")
                result.setdefault(revision, []).append(run["run_id"])
    return result


def manuscript_review_context(project_dir, loaded):
    """Identify the manuscript actually read, separately from the revised draft."""
    from .research import source_ref, record_url
    result = []
    for (branch, phase), records in loaded.items():
        if phase != "P5":
            continue
        manuscript = next((records[key] for key in ("manuscript", "manuscript_candidate") if key in records), None)
        if not manuscript:
            continue
        current = manuscript[1]["generation_ref"]
        review = records.get("outside_review")
        context = {"branch": branch, "phase": "P5", "current_manuscript_ref": current,
                   "status": "not_reviewed", "reviewed_manuscript_ref": None}
        if review:
            review_ref = review[1]["generation_ref"]
            run_id = review_ref.get("run_id")
            basis = read_json(project_dir / "runs" / (run_id or "missing") / "basis.json") or {}
            target = next((ref for ref in basis.get("records", []) if ref.get("phase") == "P5"
                           and ref.get("family") in ("manuscript", "manuscript_candidate")), None)
            context.update(review_run_id=run_id, review_ref=review_ref, status="reviewed_draft_unavailable")
            if target:
                exact = source_ref(branch, "P5", target["family"], target)
                status = ("reviewed" if exact["sha256"] == current["sha256"] else
                          "revised_after_review" if current.get("run_id") == run_id else "earlier_draft_review")
                context.update(status=status, reviewed_manuscript_ref=exact,
                               reviewed_source_url=record_url(project_dir.name, exact))
        result.append(context)
    return result
