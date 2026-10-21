"""Mechanical tools bound to one active member turn, without path arguments."""
from __future__ import annotations

from dataclasses import dataclass
import json
from threading import Condition
from typing import Callable

from .execution import redact_execution_text


ArtifactValidator = Callable[[], dict]
P4Checkpoint = Callable[[dict], dict]
_VALIDATION_SETUP_HINT = "Preserve the scientific artifacts. Restore validation setup or the authorized active turn before checking again; this failure is not a finding about the science."


def tool_failure_feedback(operation, error, *, code="execution_outcome_unknown", json_pointer="",
                          hint=None, execution_state="unknown", accepted=None) -> dict:
    """Describe one failed exchange without inferring whether side effects occurred."""
    report = {"error": str(error), "code": code, "operation": operation,
              "json_pointer": json_pointer, "execution_state": execution_state,
              "hint": hint or "Inspect the saved request, pending batch, and attempt ledger before any retry; this response does not establish whether the request was saved."}
    if accepted is not None:
        report["accepted"] = accepted
    return report


def member_tools_marker(execution=None) -> dict:
    managed = bool(execution and execution.get("p4_managed_execution"))
    return {"version": 2 if managed else 1,
            "tools": ["validate_artifacts", *(["p4_checkpoint"] if managed else [])]}


def p4_checkpoint_tool_spec() -> dict:
    return {"type": "function", "name": "p4_checkpoint",
            "description": "Save a Phase 4 plan or checkpoint, queue exactly one bounded Python or R experiment, request a researcher decision, or complete the analyst stage. In code mode print the entire returned value with text(await tools.p4_checkpoint({...})); do not extract result.content. Check the returned accepted flag or error before proceeding. accepted:false rejects only this request; earlier work may remain pending. If accepted is absent or execution_state is unknown, inspect saved control state before any retry. save_plan requires protocol_path; finalize all protocol metadata, including hashes, before saving. run_batch requires a fresh batch_id, declared work_item_id, script_path and timeout_seconds; include result_paths to seal numerical results and exhibits. Declare language, support_files and dependencies so the host snapshots every source before execution. Select input_ids from the frozen local-input manifest for actual-data analysis. After an accepted run_batch, request_decision, or complete, end this turn. The host persists and controls execution. Never run experimental scripts outside this tool. Reviewers may only checkpoint or request a decision.",
            "inputSchema": {"type": "object", "properties": {
                "operation": {"enum": ["save_plan", "checkpoint", "run_batch", "request_decision", "complete"]},
                "protocol_path": {"type": "string"},
                "checkpoint": {"type": "object", "properties": {"summary": {"type": "string", "minLength": 1}},
                               "required": ["summary"], "additionalProperties": True},
                "batch_id": {"type": "string"}, "work_item_id": {"type": "string"},
                "script_path": {"type": "string"}, "args": {"type": "array", "items": {"type": "string"}},
                "language": {"enum": ["python", "r"]},
                "support_files": {"type": "array", "maxItems": 256, "items": {"type": "string"}},
                "dependencies": {"type": "array", "maxItems": 64, "items": {"type": "string"}},
                "input_ids": {"type": "array", "maxItems": 32, "items": {"type": "string"}},
                "result_paths": {"type": "array", "items": {"type": "string"}},
                "timeout_seconds": {"type": "number", "exclusiveMinimum": 0},
                "question": {"type": "string"}, "reason": {"type": "string"},
                "scope": {"type": "object"}, "scope_change": {"type": "boolean"},
                "conditional_scope": {"type": "string"},
                "options": {"type": "array", "items": {"type": "object", "properties": {"label": {"type": "string"}, "consequence": {"type": "string"}}, "required": ["label", "consequence"], "additionalProperties": False}},
                "recommendation": {"type": "string"}, "evidence_refs": {"type": "array", "items": {"type": "object"}}},
                "required": ["operation"], "additionalProperties": False,
                "oneOf": [
                    {"properties": {"operation": {"const": "save_plan"}}, "required": ["protocol_path"]},
                    {"properties": {"operation": {"const": "checkpoint"}}, "required": ["checkpoint"]},
                    {"properties": {"operation": {"const": "run_batch"}},
                     "required": ["batch_id", "work_item_id", "script_path", "timeout_seconds"]},
                    {"properties": {"operation": {"const": "request_decision"}}, "required": ["question", "reason"]},
                    {"properties": {"operation": {"const": "complete"}}},
                ]}}


def validation_tool_spec() -> dict:
    return {"type": "function", "name": "validate_artifacts",
            "description": "Check the artifacts currently saved for your active scientific task. Returns mechanical schema, reference, and consistency findings for that task's fixed workspace. This does not judge scientific truth, change files, or publish anything. Call again after fixing reported issues.",
            "inputSchema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}}


@dataclass(frozen=True, repr=False)
class _Binding:
    callback: ArtifactValidator
    execution: dict | None
    feedback: Callable | None = None


class MemberToolDispatcher:
    """One instance per SDK client; no callback is retained after its turn."""

    def __init__(self, previous_handler):
        self._previous = previous_handler
        self._bindings: dict[tuple[str, str], _Binding] = {}
        self._extra_bindings: dict[tuple[str, str, str], _Binding] = {}
        self._pending_starts: set[str] = set()
        self._lock = Condition()

    def begin_start(self, thread_id: str) -> None:
        with self._lock:
            self._pending_starts.add(thread_id)

    def end_start(self, thread_id: str) -> None:
        with self._lock:
            self._pending_starts.discard(thread_id)
            self._lock.notify_all()

    def bind(self, thread_id: str, turn_id: str, callback: ArtifactValidator, execution=None) -> None:
        with self._lock:
            self._bindings[(thread_id, turn_id)] = _Binding(callback, execution)
            self._pending_starts.discard(thread_id)
            self._lock.notify_all()

    def unbind(self, thread_id: str, turn_id: str) -> None:
        with self._lock:
            self._bindings.pop((thread_id, turn_id), None)

    def bind_tool(self, thread_id: str, turn_id: str, tool: str, callback, execution=None, *, feedback=None) -> None:
        """Bind one extra tool (e.g. the provider probe) to an active turn.
        The callback receives the arguments object and returns a result dict."""
        with self._lock:
            self._extra_bindings[(thread_id, turn_id, tool)] = _Binding(callback, execution, feedback)
            self._pending_starts.discard(thread_id)
            self._lock.notify_all()

    def unbind_tool(self, thread_id: str, turn_id: str, tool: str) -> None:
        with self._lock:
            self._extra_bindings.pop((thread_id, turn_id, tool), None)

    @staticmethod
    def _result(document: dict, *, success: bool, execution=None) -> dict:
        text = redact_execution_text(execution, json.dumps(document, ensure_ascii=False))
        return {"contentItems": [{"type": "inputText", "text": text}], "success": success}

    def __call__(self, method, params):
        values = params if isinstance(params, dict) else {}
        if method != "item/tool/call":
            return self._previous(method, params)
        if values.get("tool") == "validate_artifacts":
            return self._validate_artifacts(values)
        tool = values.get("tool")
        if not isinstance(tool, str):
            return self._previous(method, params)
        arguments = values.get("arguments")
        operation = arguments.get("operation", tool) if isinstance(arguments, dict) else tool
        if not isinstance(operation, str):
            operation = tool
        key = (values.get("threadId"), values.get("turnId"), tool)
        if not all(isinstance(value, str) and value for value in key[:2]):
            if tool != "p4_checkpoint":
                return self._previous(method, params)
            return self._result(tool_failure_feedback(operation,
                "Phase 4 control is unavailable outside its active authorized turn.", code="inactive_turn",
                hint="Use Phase 4 control only from the currently authorized thread and turn.",
                execution_state="not_accepted", accepted=False), success=False)
        with self._lock:
            # Same start race as validate_artifacts: a tool request can arrive
            # before the awaiting coroutine binds its returned turn ID.
            if key not in self._extra_bindings and key[0] in self._pending_starts:
                self._lock.wait_for(lambda: key in self._extra_bindings or key[0] not in self._pending_starts,
                                    timeout=2)
            binding = self._extra_bindings.get(key)
        if binding is None:
            if tool == "p4_checkpoint":
                return self._result(tool_failure_feedback(operation,
                    "Phase 4 control is unavailable outside its active authorized turn.", code="inactive_turn",
                    hint="Use Phase 4 control only from the currently authorized thread and turn.",
                    execution_state="not_accepted", accepted=False), success=False)
            return self._previous(method, params)
        def finish(report, *, success):
            if binding.feedback is not None:
                recovery = binding.feedback(tool, arguments, report)
                if recovery:
                    report = {**report, "recovery": recovery}
            return self._result(report, success=success, execution=binding.execution)
        try:
            if not isinstance(arguments, dict) or values.get("namespace") not in (None, ""):
                report = tool_failure_feedback(operation, "The tool requires an arguments object in its declared namespace.",
                    code="invalid_arguments", hint=f"Call {tool} with a JSON object using its declared fields and no namespace override.",
                    execution_state="not_accepted", accepted=False)
                result = finish(report, success=False)
            else:
                report = binding.callback(arguments)
                if not isinstance(report, dict):
                    raise TypeError("The tool callback did not return a result object.")
                result = finish(report, success=True)
        except Exception as exc:
            from .p4_execution import P4ExecutionError
            report = (exc.feedback(operation) if tool == "p4_checkpoint" and isinstance(exc, P4ExecutionError)
                      else tool_failure_feedback(operation, "The tool call could not complete: " + str(exc)))
            try:
                result = finish(report, success=False)
            except Exception:
                result = self._result(report, success=False, execution=binding.execution)
        with self._lock:
            still_active = self._extra_bindings.get(key) is binding
        if not still_active:
            return self._result(tool_failure_feedback(operation, "The turn ended before the tool call completed."),
                                success=False, execution=binding.execution)
        return result

    def _validate_artifacts(self, values):
        key = (values.get("threadId"), values.get("turnId"))
        if not all(isinstance(value, str) and value for value in key):
            return self._validation_unavailable("Artifact validation is unavailable outside its active scientific turn.", code="inactive_turn")
        with self._lock:
            # The SDK reader can deliver a tool request immediately after the
            # start reply, before the awaiting coroutine binds its returned ID.
            # Wait only for that binding; a requested ID is never authoritative.
            if key not in self._bindings and key[0] in self._pending_starts:
                self._lock.wait_for(lambda: key in self._bindings or key[0] not in self._pending_starts,
                                    timeout=2)
            binding = self._bindings.get(key)
        if binding is None:
            return self._validation_unavailable("Artifact validation is unavailable outside its active scientific turn.", code="inactive_turn")
        if values.get("arguments") != {} or values.get("namespace") not in (None, ""):
            return self._result(tool_failure_feedback("validate_artifacts",
                "validate_artifacts takes no arguments and checks only the current task's fixed workspace.",
                code="invalid_arguments", hint="Call validate_artifacts with the empty object {} and no namespace override.",
                execution_state="not_accepted", accepted=False), success=False, execution=binding.execution)
        try:
            report = binding.callback()
            if not isinstance(report, dict):
                raise TypeError("Artifact validator did not return a report object.")
            if report.get("status") == "unavailable":
                report = {**tool_failure_feedback("validate_artifacts", "Artifact validation could not complete.",
                    code="validation_unavailable", hint=_VALIDATION_SETUP_HINT, execution_state="unavailable"), **report}
            result = self._result(report, success=True, execution=binding.execution)
        except Exception as exc:
            result = self._validation_unavailable("Artifact validation could not complete: " + str(exc), execution=binding.execution)
        with self._lock:
            still_active = self._bindings.get(key) is binding
        if not still_active:
            return self._validation_unavailable("The scientific turn ended before artifact validation completed.",
                                                code="inactive_turn", execution=binding.execution)
        return result

    def _validation_unavailable(self, error, *, code="validation_unavailable", execution=None):
        return self._result(tool_failure_feedback("validate_artifacts", error, code=code,
            hint=_VALIDATION_SETUP_HINT,
            execution_state="unavailable"), success=False, execution=execution)
