"""Durable researcher questions for single-member sequential scientific work.

The run engine owns transitions and scheduling. This store owns exact requests,
saved response revisions and immutable continuation amendments; it runs no model.
P4 retains its existing computation controller.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .phase_interactions import digest
from .problem_context import effective_account, scope_applies, validate_scope
from .storage import read_json, write_json_atomic


def _value(value, key, default=None):
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


def _role(role):
    return getattr(role, "value", role)


def eligible_stage(record, stage):
    roles = _value(stage, "roles", ())
    return (_value(record, "intent", "run") == "run" and _value(record, "phase") != "P4"
            and _value(stage, "execution") == "serial" and len(roles) == 1
            and _role(roles[0]) in ("research_lead", "theorist", "data_analyst"))


def researcher_pause_target(record, request):
    return {"kind": "researcher_pause", "project_id": _value(record, "project_id"),
            "branch": _value(record, "branch_id"), "phase": _value(record, "phase"),
            "run_id": _value(record, "run_id"), "stage_id": request["stage_id"],
            "request_id": request["request_id"], "object_id": request["request_id"],
            "revision": request["revision"], "sha256": digest(request)}


def pause_brief(record, stage, role):
    if not eligible_stage(record, stage) or _role(role) != _role(_value(stage, "roles")[0]):
        return ""
    if _value(record, "phase") == "P5":
        return ("## Consequential researcher input\n\n"
                "Ask only for an indispensable editorial choice needed to write this exact report. "
                "Do not reopen problem, collection, method or study-design questions from P1-P4. "
                "Keep scientific gaps in the report's source records or review ledger, qualify the affected claims and route resolving work upstream. "
                "Do not choose between conflicting statistical definitions; state the conflict and route it upstream. "
                "attention_items may be empty. If a missing editorial choice makes the next authorized reporting action unjustified, "
                "write researcher-question.json with question, reason, blocking=true, "
                "scope ({kind: project}, or {kind: model, branch, model_ref} naming the exact model), "
                "source_refs, and optional options and conditional_scope. Retain partial work before stopping. "
                "Otherwise continue justified conditional or interim reporting. A saved response does not launch work; "
                "an explicit continuation supplies its exact revision and only context items accepted from that response.\n")
    return ("## Consequential researcher input\n\n"
            "Ask only when an unresolved researcher preference or unavailable study fact materially changes the target or interpretation, "
            "validity of the intended claim, data applicability or a meaningful resource compromise. "
            "Different mathematical alternatives alone are not a researcher decision; scientific justification and routine choices belong to the team. "
            "When input is consequential and useful now, the Lead consolidates and invites it through the existing owned attention output at its designated stage even if conditional work can proceed; "
            "members propose it in their existing owned outputs for consolidation. "
            "Explain the proposed conditional direction, plausible alternatives and what the answer would change, keeping any proposed default provisional until adopted. "
            "An intended use, claim to support first or reference standard for judging success can warrant this nonblocking invitation. "
            "Do not omit such an invitation merely because it is not a blocker. "
            "If that missing input makes the next authorized action unjustified, write "
            "researcher-question.json in your workspace with question, reason, blocking=true, "
            "scope ({kind: project}, or {kind: model, branch, model_ref} naming the exact model), "
            "source_refs, and optional options and conditional_scope. Explain the concrete decision needed. "
            "Stop this turn after retaining your partial work. Do not publish conditional work as established. "
            "Set scope_change=true if resolving the question requires a changed model, scientific target, "
            "or computation scope outside this authorized run; that prepares new work. "
            "Otherwise continue justified work with explicit conditions. Attention may be empty; do not manufacture a question. "
            "There is no question quota. Reuse exact applicable saved answers; do not repeat answered questions unless their premise materially changes. "
            "Retain unknown facts with their applicability limits. Defer questions without a useful current consequence, and do not repeatedly request unavailable facts. "
            "Unknown and no-data responses remain legitimate; a researcher cannot certify assumptions by preference. "
            "A saved response does not launch work. An explicit continuation supplies its exact revision "
            "and only context items accepted from that response.\n")


def validate_authored_question(record, stage, authored_question, basis):
    """Validate a possible pause without creating or altering durable state."""
    if not eligible_stage(record, stage):
        raise ValueError("Only a single-member sequential scientific stage can wait for researcher input")
    if not isinstance(authored_question, dict) or authored_question.get("blocking") is not True:
        raise ValueError("A durable pause needs an authored blocking question")
    for field in ("question", "reason"):
        if not isinstance(authored_question.get(field), str) or not authored_question[field].strip():
            raise ValueError("Explain the question and why work needs its answer")
    scope = validate_scope(authored_question.get("scope"))
    if "topic" in authored_question and (not isinstance(authored_question["topic"], str) or not authored_question["topic"].strip()):
        raise ValueError("An authored context topic must not be blank")
    if not scope_applies(scope, _value(record, "branch_id"), basis.get("method")):
        raise ValueError("The blocking question targets a different model version")
    return {**deepcopy(authored_question), "scope": scope}


def _record_identity(ref):
    return {key: ref.get(key) for key in ("branch", "phase", "family", "generation_id", "run_id", "package_id")} | {
        "sha256": ref.get("content_sha256") or ref.get("sha256")}


def continuation_context_changes(frozen_basis, current_basis, accepted_context_items=()):
    """Compare source identity, ignoring relocated frozen snapshot files."""
    changes = []
    original = [_record_identity(ref) for ref in frozen_basis.get("records", [])]
    current = [_record_identity(ref) for ref in current_basis.get("records", [])]
    if sorted(original, key=digest) != sorted(current, key=digest):
        changes.append({"kind": "scientific_sources_changed"})
    from .project_brief import project_instructions
    if project_instructions(frozen_basis.get("project") or {}) != project_instructions(current_basis.get("project") or {}):
        changes.append({"kind": "project_brief_changed"})
    before = frozen_basis.get("problem_context") or {}
    after = current_basis.get("problem_context") or {}
    old_items = {row["item_id"]: row for row in before.get("items", [])}
    new_items = {row["item_id"]: row for row in after.get("items", [])}
    allowed = {(row["item_id"], row["revision"]) for row in accepted_context_items}
    for item_id in sorted(set(old_items) | set(new_items)):
        old, new = old_items.get(item_id), new_items.get(item_id)
        if old != new and (item_id, (new or {}).get("revision")) not in allowed:
            changes.append({"kind": "problem_context_changed", "item_id": item_id,
                            "previous_revision": (old or {}).get("revision"), "revision": (new or {}).get("revision")})
    if before.get("brief", {}).get("sha256") != after.get("brief", {}).get("sha256") and not any(
            row["kind"] == "project_brief_changed" for row in changes):
        changes.append({"kind": "project_brief_changed"})
    # A pending disagreement is consequential context too. Confirming the
    # selected answer's own proposal is allowed through its exact adopted item.
    old_pending = {row["amendment_id"]: row for row in before.get("proposals", []) if row.get("status") == "pending"}
    new_pending = {row["amendment_id"]: row for row in after.get("proposals", []) if row.get("status") == "pending"}
    for amendment_id in sorted(set(old_pending) | set(new_pending)):
        old, new = old_pending.get(amendment_id), new_pending.get(amendment_id)
        item = (new or old or {}).get("item") or {}
        final = new_items.get(item.get("item_id")) or {}
        if old != new and (final.get("item_id"), final.get("revision")) not in allowed:
            changes.append({"kind": "pending_context_amendment_changed", "amendment_id": amendment_id})
    frozen_model = (frozen_basis.get("method") or {}).get("identity")
    current_model = (current_basis.get("method") or {}).get("identity")
    if frozen_model != current_model:
        changes.append({"kind": "model_changed", "previous": frozen_model, "current": current_model})
    return changes


def adopted_context_items(answer, current_basis, branch_id, model_ref=None):
    """Resolve only confirmed items linked to the exact selected response."""
    accepted = []
    for ref in answer.get("context_refs", []):
        item = next((row for row in (current_basis.get("problem_context") or {}).get("items", [])
                     if row.get("item_id") == ref.get("item_id") and row.get("revision") == ref.get("revision")), None)
        if (item is None or not answer.get("answer_ref") or answer["answer_ref"] not in item.get("answer_refs", [])
                or item.get("status") != "confirmed" or not scope_applies(item.get("scope"), branch_id, model_ref)):
            raise ValueError("Continuation context must name only exact applicable items adopted from this saved response")
        accepted.append(deepcopy(item))
    return accepted


class ResearcherPauseStore:
    def __init__(self, run_dir):
        self.run_dir = Path(run_dir)
        self.path = self.run_dir / "researcher-pause.json"

    def snapshot(self):
        saved = read_json(self.path)
        if self.path.exists() and not isinstance(saved, dict):
            raise ValueError("The saved researcher question is unreadable")
        return deepcopy(saved) if saved else {"pending_request": None, "requests": [], "saved_answers": [], "continuations": []}

    def accepted_context_items(self, record):
        """The applicable item snapshots already authorized in this run."""
        basis = read_json(self.run_dir / "basis.json") or {}
        items = {}
        for continuation in self.snapshot()["continuations"]:
            for item in continuation.get("accepted_context_items", []):
                if scope_applies(item.get("scope"), _value(record, "branch_id"), basis.get("method")):
                    items[item["item_id"]] = deepcopy(item)
        return list(items.values())

    def context_basis(self, record, basis=None):
        """Read the frozen basis with only explicitly accepted context applied.

        The original document, revision and digest remain its provenance. The
        effective account and annotated snapshots describe the exact additional
        context accepted by this run, without reading current project context.
        """
        retained = read_json(self.run_dir / "basis.json") if basis is None else basis
        if not isinstance(retained, dict):
            raise ValueError("The run's frozen basis is unavailable")
        result = deepcopy(retained)
        context = result.get("problem_context")
        if not isinstance(context, dict):
            return result
        context["frozen_effective_account"] = deepcopy(
            context.get("frozen_effective_account", context.get("effective_account")))
        accepted = [item for item in self.accepted_context_items(record)
                    if scope_applies(item.get("scope"), _value(record, "branch_id"), result.get("method"))]
        context["authorized_context_items"] = deepcopy(accepted)
        context["authorized_context_refs"] = [
            {"item_id": item["item_id"], "revision": item["revision"],
             "answer_refs": deepcopy(item.get("answer_refs", []))} for item in accepted]
        if accepted:
            document = deepcopy(context.get("document", context))
            items = {item["item_id"]: item for item in document.get("items", [])}
            items.update({item["item_id"]: deepcopy(item) for item in accepted})
            document["items"] = list(items.values())
            context["effective_account"] = effective_account(
                document, _value(record, "branch_id"), result.get("method"))
        return result

    def request(self, record, stage, authored_question, basis):
        authored_question = validate_authored_question(record, stage, authored_question, basis)
        scope = authored_question["scope"]
        state = self.snapshot()
        stage_id = _value(stage, "stage_id")
        member = _role(_value(stage, "roles")[0])
        previous = state.get("pending_request")
        content = {key: deepcopy(authored_question[key]) for key in
                   ("question", "reason", "options", "conditional_scope", "scope_change", "source_refs", "context_refs", "topic")
                   if key in authored_question}
        content.update(scope=scope, stage_id=stage_id, member=member, blocking=True,
                       run_id=_value(record, "run_id"), phase=_value(record, "phase"), branch=_value(record, "branch_id"))
        if previous and all(previous.get(key) == value for key, value in content.items()):
            return previous
        if previous and (previous["stage_id"], previous["member"]) != (stage_id, member):
            raise ValueError("This run is already waiting for a different member's question")
        revision = (previous or {}).get("revision", 0) + 1
        request_id = (previous or {}).get("request_id") or "request." + digest({"run": _value(record, "run_id"), "stage": stage_id,
                                                                              "number": len(state["requests"]), "question": content})[:24]
        request = {**content, "request_id": request_id, "revision": revision,
                   "basis_sha256": basis.get("sha256"),
                   "context_revision": (basis.get("problem_context") or {}).get("revision"),
                   "created_at": datetime.now(timezone.utc).isoformat()}
        state["pending_request"] = request
        state["requests"].append(deepcopy(request))
        write_json_atomic(self.path, state)
        return request

    def save_answer(self, request_id, expected_revision, note, *, expected_answer_revision=None,
                    answer_ref=None, context_refs=None, scope_change=False, origin="researcher_reported", topic=None):
        if not isinstance(note, str) or not note.strip():
            raise ValueError("Record your response before saving")
        if origin not in ("researcher_reported", "unknown"):
            raise ValueError("A direct researcher response records a report or uncertainty")
        state = self.snapshot()
        request = next((row for row in reversed(state["requests"]) if row["request_id"] == request_id
                        and row["revision"] == expected_revision), None)
        if request is None:
            raise ValueError("The researcher question changed; reopen its exact revision")
        previous = next((row for row in reversed(state["saved_answers"]) if row["request_id"] == request_id
                         and row["request_revision"] == expected_revision), {})
        if expected_answer_revision is not None and expected_answer_revision != previous.get("revision", 0):
            raise ValueError("Your saved response changed; reload it before saving")
        topic = topic if topic is not None else request.get("topic", previous.get("topic"))
        if topic is not None and (not isinstance(topic, str) or not topic.strip()):
            raise ValueError("An authored context topic must not be blank")
        if previous and all(previous.get(key) == value for key, value in {"note": note, "answer_ref": answer_ref,
                              "context_refs": context_refs or [], "scope_change": scope_change,
                              "origin": origin, "topic": topic}.items()):
            return previous
        answer = {"request_id": request_id, "request_revision": expected_revision,
                  "revision": len(state["saved_answers"]) + 1, "note": note, "request": deepcopy(request),
                  "answer_ref": deepcopy(answer_ref), "context_refs": deepcopy(context_refs or []),
                  "origin": origin, **({"topic": topic} if topic is not None else {}),
                  "scope_change": scope_change, "saved_at": datetime.now(timezone.utc).isoformat()}
        state["saved_answers"].append(answer)
        write_json_atomic(self.path, state)
        return answer

    def continue_work(self, request_id, expected_revision, answer_revision, *, current_basis,
                      context_choice=None, idempotency_key=None):
        state = self.snapshot()
        payload = {"request_id": request_id, "request_revision": expected_revision, "answer_revision": answer_revision,
                   "context_choice": context_choice}
        previous = next((row for row in state["continuations"] if idempotency_key
                         and row.get("idempotency_key") == idempotency_key), None)
        if previous:
            if previous["payload"] != payload:
                raise ValueError("This continuation key already names a different response")
            return previous
        request = state.get("pending_request")
        if not request or (request["request_id"], request["revision"]) != (request_id, expected_revision):
            raise ValueError("The run is not waiting for this exact researcher question")
        answer = next((row for row in state["saved_answers"] if row["revision"] == answer_revision
                       and row["request_id"] == request_id and row["request_revision"] == expected_revision), None)
        if answer is None:
            raise ValueError("Choose a saved response to this exact question")
        if request.get("scope_change") or answer.get("scope_change"):
            raise ValueError("This response changes the authorized scientific scope; prepare a new linked run")
        frozen_basis = read_json(self.run_dir / "basis.json")
        if not isinstance(frozen_basis, dict):
            raise ValueError("The run's frozen basis is unavailable")
        accepted = adopted_context_items(answer, current_basis, request["branch"], frozen_basis.get("method"))
        previous_items = self.accepted_context_items({"branch_id": request["branch"]})
        changes = continuation_context_changes(frozen_basis, current_basis, [*previous_items, *accepted])
        if any(row["kind"] == "model_changed" for row in changes):
            raise ValueError("The model changed; prepare a new linked run")
        if changes and context_choice != "frozen":
            raise ValueError("Research context changed. Choose the displayed frozen basis or prepare a new linked run")
        continuation = {**payload, "revision": len(state["continuations"]) + 1, "request": deepcopy(request),
                        "answer": deepcopy(answer), "accepted_context_items": accepted, "context_changes": changes,
                        "resume_stage": request["stage_id"], "resume_member": request["member"],
                        "conditional_scope": request.get("conditional_scope"), "payload": payload,
                        "idempotency_key": idempotency_key, "accepted_at": datetime.now(timezone.utc).isoformat()}
        state["continuations"].append(continuation)
        state["pending_request"] = None
        write_json_atomic(self.path, state)
        return continuation

    def brief(self, record, stage, role):
        result = pause_brief(record, stage, role)
        if _value(record, "intent", "run") != "run" or _role(role) == "outside_reviewer":
            return result
        applicable = [row for row in self.snapshot()["continuations"]
                      if row["resume_stage"] == _value(stage, "stage_id") and row["resume_member"] == _role(role)]
        import json
        items = self.accepted_context_items(record)
        if items:
            result += "\n## Previously authorized context amendments\n\n" + json.dumps(items, ensure_ascii=False, indent=2) + "\n"
            result += "These exact item snapshots were accepted during explicit continuations of this run. Apply their recorded scope and explicit amendments to the original frozen account; preserve unamended instructions.\n"
        if applicable:
            result += "\n## Explicit continuation amendment\n\n" + json.dumps(applicable[-1], ensure_ascii=False, indent=2) + "\n"
            result += "Use the original frozen basis with the previously authorized context amendments and this selected response. Completed stages stay unchanged.\n"
        return result

    def resolve_target(self, record, target):
        request = next((row for row in self.snapshot()["requests"] if researcher_pause_target(record, row) == target), None)
        if not request:
            raise ValueError("The selected researcher question has changed or is unavailable")
        return {**deepcopy(request), "issue_id": request["request_id"], "title": request["question"],
                "kind": "researcher_decision", "responsible_role": request["member"],
                "explanation_target": deepcopy(target)}
