"""Durable, run-local control and bounded sandboxed computation for Phase 4.

Member callbacks only commit requests. The async host executes an accepted batch
after the member turn has stopped. Nothing in this module publishes research.
"""
from __future__ import annotations

import asyncio
import csv
import copy
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import site
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4
from functools import lru_cache

from .accounts import find_codex
from .storage import read_json, write_json_atomic
from .windows_runtime import P4WindowsSetupError, runtime_settings

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()
_SANDBOX_SETUP_DIAGNOSTIC = "The sandbox could not start the shared Python runtime; inspect the saved stderr.log and configure MF_P4_PYTHON for an accessible shared installation."


@lru_cache(maxsize=1)
def _process_user_sid():
    # Query the actual process identity, never an agent-supplied account name.
    tool = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/whoami.exe"
    completed = subprocess.run([str(tool), "/user", "/fo", "csv", "/nh"],
                               capture_output=True, text=True, check=True, timeout=10, stdin=subprocess.DEVNULL,
                               creationflags=0x08000000)
    row = next(csv.reader(completed.stdout.splitlines()))
    if len(row) != 2 or not re.fullmatch(r"S-\d+(?:-\d+)+", row[1]):
        raise P4ExecutionError("The app's Windows account could not be identified")
    return row[1]


def ensure_workspace_owner_access(workspace: Path, *, owned_root: Path):
    """Keep host-created workspace outputs readable by this app on Windows.

    Call only for an engine-owned stage directory, never a tool-supplied path.
    Temp folders can inherit OWNER RIGHTS rather than an explicit user ACE;
    sandbox-created files otherwise become unreadable to their host app. This
    adds the app user's inheritable ACE without changing the sandbox policy or
    any other account's permissions, and without traversing unrelated folders.
    """
    if os.name != "nt":
        return
    workspace, owned_root = Path(workspace).resolve(), Path(owned_root).resolve()
    if workspace == owned_root or not workspace.is_relative_to(owned_root) or not workspace.is_dir():
        raise P4ExecutionError("Workspace ownership can be prepared only inside its engine-owned root")
    tool = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/icacls.exe"
    subprocess.run([str(tool), str(workspace), "/grant", f"*{_process_user_sid()}:(OI)(CI)F"],
                   capture_output=True, check=True, timeout=10, creationflags=0x08000000, stdin=subprocess.DEVNULL)


def _ensure_owned_read_access(directory: Path, *, owned_root: Path):
    """Give the installed sandbox group read access to engine-owned frozen files.

    The Windows managed sandbox uses a separate low-privilege account. Its read
    roots still need an OS read ACE when a parent has owner-only inheritance.
    No machine installation or unrelated directory ACL is changed.
    """
    if os.name != "nt":
        return
    directory, owned_root = Path(directory).resolve(), Path(owned_root).resolve()
    if not directory.is_relative_to(owned_root) or not directory.is_dir():
        raise P4ExecutionError("Frozen-file access can be prepared only inside its engine-owned root")
    tool = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/icacls.exe"
    subprocess.run([str(tool), str(directory), "/grant", f"*{_process_user_sid()}:(OI)(CI)RX",
                    "CodexSandboxUsers:(OI)(CI)RX"],
                   capture_output=True, check=True, timeout=10, creationflags=0x08000000, stdin=subprocess.DEVNULL)


class P4ExecutionError(ValueError):
    """An execution failure does not establish whether a request was committed."""

    def __init__(self, message, *, code="execution_outcome_unknown", json_pointer="", hint=None, findings=()):
        super().__init__(message)
        self.code, self.json_pointer, self.hint = code, json_pointer, hint
        self.findings = tuple(findings)

    def feedback(self, operation):
        from dataclasses import asdict
        from .member_tools import tool_failure_feedback
        rejected = isinstance(self, P4RequestRejected)
        report = tool_failure_feedback(operation, self, code=self.code, json_pointer=self.json_pointer,
            hint=self.hint or (_request_hint(operation) if rejected else None),
            execution_state="not_accepted" if rejected else "unknown", accepted=False if rejected else None)
        if self.findings:
            report["findings"] = [asdict(finding) for finding in self.findings]
            report["object_id"] = self.findings[0].object_id
        return report


class P4RequestRejected(P4ExecutionError):
    """A validated refusal before request persistence, safe to report as rejected."""

    def __init__(self, message, *, code="state_refused", **kwargs):
        super().__init__(message, code=code, **kwargs)


class P4CleanupError(P4ExecutionError):
    """Stopping was not confirmed; the host must not present an idle pause."""


class P4InfrastructureError(P4ExecutionError):
    """Preparing host access failed without evidence of damaged inputs."""


async def _prepare_owned_read_access(directory: Path, *, owned_root: Path):
    try:
        await asyncio.to_thread(_ensure_owned_read_access, directory, owned_root=owned_root)
    except Exception as exc:
        raise P4InfrastructureError(
            f"Windows sandbox access to retained experiment files could not be prepared: {exc}. "
            "Repair the shared sandbox setup and host file access before continuing P4."
        ) from exc


def _now():
    return datetime.now(timezone.utc).isoformat()


def _request_hint(operation):
    return {
        "save_plan": "Correct the indicated protocol field using this run's frozen contract and sources, then save the same protocol path again.",
        "checkpoint": "Supply a checkpoint object with a nonempty summary of the current evidence and next action.",
        "run_batch": "Correct the indicated batch field using the saved plan's declared work item and a bounded workspace script, then submit the corrected request once.",
        "request_decision": "Provide the researcher's question and its reason, with a label and consequence for each supplied option.",
        "complete": "Inspect the saved plan and available evidence before requesting stage completion again.",
    }.get(operation if isinstance(operation, str) else None,
          "Choose a declared Phase 4 operation and supply its required fields.")


def _validate_request_arguments(arguments):
    from jsonschema import Draft202012Validator
    from .member_tools import p4_checkpoint_tool_spec
    schema = p4_checkpoint_tool_spec()["inputSchema"]
    branches = schema.pop("oneOf")
    operation = arguments.get("operation") if isinstance(arguments, dict) else None
    # Selecting the declared operation first preserves exact missing-field paths
    # instead of returning a generic oneOf failure for the whole request.
    branch = next((item for item in branches if item["properties"]["operation"]["const"] == operation), {})
    schema["required"] = [*schema["required"], *branch.get("required", [])]
    error = next(Draft202012Validator(schema).iter_errors(arguments), None)
    if error is None:
        return
    parts = list(error.absolute_path)
    if error.validator == "required":
        parts.append(next(key for key in error.validator_value if key not in error.instance))
    elif error.validator == "additionalProperties" and isinstance(error.instance, dict):
        parts.append(next(key for key in error.instance if key not in error.schema.get("properties", {})))
    pointer = "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)
    raise P4RequestRejected(error.message, code="invalid_arguments", json_pointer=pointer)


def _positive(value, label, *, json_pointer=""):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise P4RequestRejected(f"{label} must be a finite positive number", code="invalid_arguments", json_pointer=json_pointer)
    return float(value)


def _text(value, label, *, json_pointer=""):
    if not isinstance(value, str) or not value.strip():
        raise P4RequestRejected(f"{label} is required", code="invalid_arguments", json_pointer=json_pointer)
    return value.strip()


def _identifier(value, label):
    value = _text(value, label, json_pointer="/" + label)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", value):
        raise P4RequestRejected(f"{label} is not a valid identifier", code="invalid_arguments", json_pointer="/" + label)
    return value


def _safe_file(workspace: Path, value, suffix=None, *, json_pointer=""):
    name = _text(value, "A workspace-relative file path", json_pointer=json_pointer)
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise P4RequestRejected("Files must stay inside the active member workspace", code="invalid_arguments", json_pointer=json_pointer)
    path = (workspace / relative).resolve()
    if not path.is_relative_to(workspace.resolve()) or not path.is_file():
        raise P4RequestRejected("The requested workspace file is unavailable", code="invalid_arguments", json_pointer=json_pointer)
    if suffix and path.suffix.lower() != suffix:
        raise P4RequestRejected(f"The managed runner requires a {suffix} script", code="invalid_arguments", json_pointer=json_pointer)
    return path


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _process_directory(path):
    value = str(Path(path).resolve())
    if os.name == "nt" and len(value) >= 248 and not value.startswith("\\\\?\\"):
        # CreateProcess's working-directory limit remains even for long-path
        # aware Python. A filesystem short name identifies the same directory.
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        target = ctypes.create_unicode_buffer(32768)
        if api.GetShortPathNameW(value, target, len(target)) and len(target.value) < 248:
            return target.value
        return "\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value
    return value


def _declared_sources_enabled(run_dir):
    contract = read_json(Path(run_dir) / "contracts/contracts/phases/P4.json") or {}
    return "p4.declared_source_snapshots.v1" in contract.get("capabilities", [])


def _raw_dataset_digests(run_dir):
    basis = read_json(Path(run_dir) / "basis.json") or {}
    return {item.get("sha256") for item in (basis.get("p4_inputs") or {}).get("inputs", [])
            if item.get("role") == "dataset" and item.get("sha256")}


def _batch_inputs(run_dir, effective, work, requested):
    """Resolve only frozen input IDs, never member-supplied local file paths."""
    basis = read_json(Path(run_dir) / "basis.json") or {}
    manifest = basis.get("p4_inputs") or {}
    frozen = {item["input_id"]: item for item in manifest.get("inputs", [])}
    case_ids = set(work.get("case_ids", []))
    sources = {source_id for case in effective.get("cases", []) if case.get("case_id") in case_ids
               for source_id in case.get("data_source_ids", [])}
    declared = {input_id for source in effective.get("data_sources", []) if source.get("data_source_id") in sources
                for input_id in source.get("input_ids", [])}
    selected = declared if requested is None else set(requested)
    if not selected <= frozen.keys():
        raise P4RequestRejected("The batch refers to an input that was not frozen for this run", json_pointer="/input_ids")
    if requested is not None and not selected <= declared:
        raise P4RequestRejected("The batch input IDs must belong to its declared data sources", json_pointer="/input_ids")
    inputs = []
    root = (Path(run_dir) / "inputs/researcher").resolve()
    for input_id in sorted(selected):
        item = copy.deepcopy(frozen[input_id])
        path = Path(item["snapshot_path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file() or _digest(path) != item["sha256"]:
            raise P4RequestRejected("A frozen run input is unavailable or changed; restore it before computation", json_pointer="/input_ids")
        inputs.append(item)
    return {"inputs": inputs, "variable_mapping": copy.deepcopy(manifest.get("variable_mapping", {}))}


def _snapshot_sources(workspace, destination, script, support_files, *, raw_dataset_digests=()):
    paths = [script.relative_to(workspace).as_posix(), *support_files]
    files = []
    for index, relative in enumerate(dict.fromkeys(paths)):
        source = _safe_file(workspace, relative, json_pointer="/support_files" if index else "/script_path")
        # Names are preserved so ordinary relative imports and configuration work.
        target = destination / source.relative_to(workspace)
        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest in raw_dataset_digests:
            raise P4RequestRejected("Raw researcher datasets cannot be declared as code or support files; use their frozen input IDs",
                                    code="raw_dataset_as_source", json_pointer="/support_files" if index else "/script_path")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files.append({"path": source.relative_to(workspace).as_posix(), "snapshot_path": str(target),
                      "sha256": digest, "size_bytes": len(data)})
    return files


def _validate_new_source_files(workspace, plan, previous):
    entries = []
    if previous is None:
        entries.extend((source, f"/data_sources/{index}") for index, source in enumerate(plan.get("data_sources", [])))
    prior_count = len((previous or {}).get("amendments", []))
    for index, amendment in enumerate(plan.get("amendments", [])):
        if index >= prior_count:
            entries.extend((source, f"/amendments/{index}/added_data_sources/{position}")
                           for position, source in enumerate(amendment.get("added_data_sources", [])))
    for source, prefix in entries:
        for index, support in enumerate(source.get("support_files", [])):
            pointer = f"{prefix}/support_files/{index}/artifact"
            artifact = support["artifact"]
            path = _safe_file(workspace, artifact.get("path"), json_pointer=pointer + "/path")
            if _digest(path) != artifact["sha256"]:
                raise P4RequestRejected("A new data source's retained file digest does not match its workspace bytes",
                                        code="source_artifact_digest", json_pointer=pointer + "/sha256")


def _effective_plan(plan):
    from .empirical_targets import effective_protocol
    return effective_protocol(plan)


def setup_attention(progress, request=None):
    """Project a recorded runtime start failure, never infer one from status alone.

    Match the pause's recorded attempt rather than a stale failure elsewhere in
    the ledger. Historical pause readers can pass their own saved request.
    """
    request = request if request is not None else progress.get("pause_request")
    if not isinstance(request, dict):
        return None
    referenced = {item.get("attempt_id") for item in request.get("evidence_refs", [])
                  if isinstance(item, dict) and item.get("attempt_id")}
    attempt = next((item for item in reversed(progress.get("ledger", []))
                    if item.get("attempt_id") in referenced and item.get("status") == "infrastructure_error"), None)
    if not attempt:
        return None
    runtime = attempt.get("runtime")
    if (attempt.get("computation_started") is True or attempt.get("computation_started") is not False
            and (attempt.get("exit_code") == 0 or isinstance(runtime, dict)
                 and runtime.get("python_executable") and not runtime.get("test_launcher"))):
        return None
    # Older collection exceptions discarded the completed process metadata and
    # kept only infrastructure_error. The runner's own start-failure diagnostic
    # is a supported legacy signal; a generic error does not prove Python failed.
    if (attempt.get("computation_started") is not False
            and attempt.get("diagnostic") != _SANDBOX_SETUP_DIAGNOSTIC):
        return None
    language = attempt.get("language", "python")
    configuration = "MF_P4_RSCRIPT" if language == "r" else "MF_P4_PYTHON"
    guidance = ("Complete or repair the selected elevated Windows sandbox setup in Codex and restore host access to the retained experiment files, then explicitly continue P4. Keep the managed read, denied-read and write boundaries enabled."
                if attempt.get("setup_kind") == "windows_sandbox" else
                f"Check the saved technical log, required packages and shared runtime access. Set {configuration} to an accessible user-wide or machine-wide installation when needed, then explicitly continue. Keep the managed sandbox enabled.")
    return {"message": "The managed computation could not run. This is a setup failure and supplies no finding about the method.",
            "guidance": guidance,
            **{key: attempt[key] for key in ("attempt_id", "batch_id", "output_dir", "diagnostic") if key in attempt}}


class P4Controller:
    def __init__(self, run_dir: Path, workspace: Path, *, stage_id: str, member: str,
                 budget_seconds: float = 600, runner=None):
        self.run_dir, self.workspace = Path(run_dir), Path(workspace).resolve()
        self.stage_id, self.member = stage_id, str(member)
        self.directory = self.run_dir / "p4-execution"
        self.path = self.directory / "state.json"
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(str(self.path.resolve()), threading.RLock())
        self.runner = runner or ManagedPythonRunner()
        self.directory.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._enter_stage(budget_seconds)

    def _enter_stage(self, budget_seconds):
        stage_id = self.stage_id
        state = self.load_snapshot(self.run_dir)
        changed = state is None
        if state is None:
            limit = _positive(budget_seconds, "Experiment budget")
            state = {"schema_version": 1, "plan": None, "ledger": [], "plan_history": [],
                     "budget": {"limit_seconds": limit, "used_seconds": 0, "remaining_seconds": limit},
                     "pause_request": None, "checkpoint": None, "checkpoints": [], "pending_batch": None,
                     "completed": False, "finish_requested": False, "answer_revisions": [], "action": None, "control_sequence": 0,
                     "resume_stage": stage_id, "resume_member": self.member, "updated_at": _now()}
        elif (state.get("resume_stage"), state.get("resume_member")) != (stage_id, self.member):
            if state.get("pending_batch") or state.get("pause_request"):
                raise P4ExecutionError("Resolve the existing Phase 4 checkpoint before changing stages")
            state.update(resume_stage=stage_id, resume_member=self.member, completed=False, action=None)
            changed = True
        if changed:
            self._save(state)

    def _save(self, state):
        state["updated_at"] = _now()
        state["control_sequence"] = state.get("control_sequence", 0) + 1
        write_json_atomic(self.path, state)

    @staticmethod
    def load_snapshot(run_dir):
        path = Path(run_dir) / "p4-execution" / "state.json"
        state = read_json(path)
        if path.exists() and (not isinstance(state, dict) or state.get("schema_version") != 1):
            raise P4ExecutionError("The saved Phase 4 execution state is unreadable; preserve it for recovery")
        return state

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self.load_snapshot(self.run_dir))

    def request(self, arguments: dict):
        """Validate and persist a tool request without launching or awaiting work."""
        _validate_request_arguments(arguments)
        operation = arguments.get("operation")
        with self._lock:
            state = self.snapshot()
            if state.get("pause_request"):
                raise P4RequestRejected("This evaluation is waiting for researcher direction",
                    hint="End this turn and wait for the researcher to answer the saved decision request.")
            if state.get("pending_batch") and operation != "request_decision":
                raise P4RequestRejected("A batch is already queued; finish this turn",
                    hint="Keep the saved pending batch and finish this turn so the host can handle it; do not submit another batch.")
            if state.get("completed") and operation not in {"request_decision", "checkpoint", "complete"}:
                raise P4RequestRejected("This stage is already complete", hint="End this turn; the completed stage does not authorize further experiments.")
            if self.member != "data_analyst" and operation not in {"request_decision", "checkpoint"}:
                raise P4RequestRejected("Review members may record a checkpoint or request a decision",
                    hint="Use checkpoint for the review account or request_decision for a researcher question.")
            if operation == "save_plan":
                path = _safe_file(self.workspace, arguments.get("protocol_path"), ".json", json_pointer="/protocol_path")
                plan_bytes = path.read_bytes()
                try:
                    plan = json.loads(plan_bytes)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise P4RequestRejected("The protocol is not readable JSON: " + str(exc),
                        code="invalid_arguments", json_pointer="/protocol_path") from exc
                if not isinstance(plan, dict):
                    raise P4RequestRejected("The protocol must be an object", code="invalid_arguments", json_pointer="/protocol_path")
                basis_path, run_path = self.run_dir / "basis.json", self.run_dir / "run.json"
                if basis_path.exists():
                    basis = read_json(basis_path) or {}
                    method = basis.get("method") or {}
                    identity = method.get("identity") or method.get("method_identity")
                    if not identity or plan.get("method_identity") != identity:
                        raise P4RequestRejected("protocol.method_identity must exactly match this run's frozen method identity",
                            json_pointer="/method_identity", hint="Use the exact method identity in the run's frozen basis; do not guess or substitute an identifier.")
                if run_path.exists():
                    run = read_json(run_path) or {}
                    for field, host_field in (("source_run_id", "run_id"), ("mode", "mode")):
                        if not run.get(host_field) or plan.get(field) != run[host_field]:
                            raise P4RequestRejected(f"protocol.{field} must match this evaluation's {host_field}: {run.get(host_field)}",
                                json_pointer=f"/{field}")
                frozen_catalog = self.run_dir / "contracts"
                if (frozen_catalog / "catalog-pin.json").is_file():
                    from .catalog import Catalog
                    from .p4_validation import check_progressive_evaluation
                    try:
                        catalog = Catalog(frozen_catalog)
                        problems = catalog.validate_output("p4.protocol", plan)
                        schema_failed = bool(problems)
                        if not schema_failed:
                            contract = read_json(catalog.root / "contracts" / "phases" / "P4.json") or {}
                            capabilities = contract.get("capabilities", [])
                            check_progressive_evaluation({"p4.protocol": plan}, problems,
                                question_appropriate="p4.question_appropriate_numerics.v1" in capabilities,
                                workflow_templates="p4.workflow_templates.v1" in capabilities,
                                frozen_inputs=(read_json(basis_path) or {}).get("p4_inputs", {"inputs": []})
                                    if "p4.workflow_templates.v1" in capabilities else None)
                    except Exception as exc:
                        raise P4RequestRejected("Protocol validation could not complete: " + str(exc),
                            code="validation_unavailable", hint="Preserve the scientific protocol and restore the frozen validation setup before saving again; this failure is not a scientific finding.") from exc
                    rejected = problems if schema_failed else [problem for problem in problems if problem.blocks_publication]
                    if rejected:
                        prefix = ("The saved protocol does not meet this run's contract: " if schema_failed
                                  else "Fix the protocol's declared references before saving: ")
                        raise P4RequestRejected(prefix + "; ".join(problem.message for problem in rejected[:3]),
                            code=rejected[0].code, json_pointer=rejected[0].json_pointer, findings=rejected)
                revision = _identifier(plan.get("plan_revision_id"), "plan_revision_id")
                _positive(plan.get("budget_seconds"), "Protocol budget", json_pointer="/budget_seconds")
                if plan["budget_seconds"] > state["budget"]["limit_seconds"]:
                    raise P4RequestRejected("The protocol exceeds the researcher-authorized budget", json_pointer="/budget_seconds",
                        hint="Keep the plan within the remaining authorized scope or request a researcher decision about additional budget.")
                effective = _effective_plan(plan)
                if not effective.get("work_items"):
                    raise P4RequestRejected("The plan must declare its ordered work items", json_pointer="/work_items")
                previous = state.get("plan")
                if previous:
                    # Original scientific fields never change. Amendments are append-only.
                    original = {k: v for k, v in previous.items() if k not in {"amendments", "deviations"}}
                    current = {k: v for k, v in plan.items() if k not in {"amendments", "deviations"}}
                    changed_history = any(plan.get(key, [])[:len(previous.get(key, []))] != previous.get(key, []) for key in ("amendments", "deviations"))
                    if original != current or changed_history:
                        raise P4RequestRejected("Keep the initial protocol unchanged and append prospective amendments",
                            hint="Restore the saved original protocol and existing amendments, then append a prospective amendment for new work.")
                if _declared_sources_enabled(self.run_dir):
                    _validate_new_source_files(self.workspace, plan, previous)
                amendments = plan.get("amendments", [])
                effective_revision = amendments[-1]["revision_id"] if amendments else revision
                digest = hashlib.sha256(plan_bytes).hexdigest()
                if state.get("plan_history") and state["plan_history"][-1]["sha256"] == digest:
                    return {"accepted": True, "operation": operation, "stop_turn": False, "revision_id": effective_revision}
                target = self.directory / "plans" / f"{len(state['plan_history']) + 1:04d}.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(".tmp")
                temporary.write_bytes(plan_bytes)
                os.replace(temporary, target)
                state["plan_history"].append({"revision_id": effective_revision, "sha256": digest,
                                               "saved_at": _now(), "path": str(target)})
                state["plan"] = plan
            elif operation == "checkpoint":
                checkpoint = arguments.get("checkpoint")
                if not isinstance(checkpoint, dict):
                    raise P4RequestRejected("checkpoint must be an object", code="invalid_arguments", json_pointer="/checkpoint")
                _text(checkpoint.get("summary"), "Checkpoint summary", json_pointer="/checkpoint/summary")
                state["checkpoint"] = {**copy.deepcopy(checkpoint), "saved_at": _now(),
                                       "stage_id": self.stage_id, "member": self.member}
                state.setdefault("checkpoints", []).append(state["checkpoint"])
            elif operation == "run_batch":
                if state.get("finish_requested"):
                    raise P4RequestRejected("The researcher requested completion with existing evidence; further computation is not authorized",
                        hint="Complete the account using the retained evidence and its limitations, then request complete.")
                if not state.get("plan"):
                    raise P4RequestRejected("Save the initial plan before running an experiment",
                        hint="Use save_plan with the declared protocol_path before submitting a batch.")
                batch_id = _identifier(arguments.get("batch_id"), "batch_id")
                if any(item["batch_id"] == batch_id for item in state["ledger"]):
                    raise P4RequestRejected("This batch ID already has an attempt; use a new ID for a retry", json_pointer="/batch_id",
                        hint="Inspect this batch's saved attempt before deciding whether another experiment is needed. Use a fresh batch ID only for an authorized new attempt.")
                work_id = _identifier(arguments.get("work_item_id"), "work_item_id")
                effective = _effective_plan(state["plan"])
                work = next((item for item in effective["work_items"] if item["work_item_id"] == work_id), None)
                if work is None:
                    raise P4RequestRejected("The batch must refer to a declared work item", json_pointer="/work_item_id",
                        hint="Use the exact work_item_id from the effective saved plan; do not invent or guess one.")
                complete = {item["work_item_id"] for item in state["ledger"] if item["status"] == "completed"}
                if set(work.get("depends_on", [])) - complete:
                    raise P4RequestRejected("Complete the declared dependencies before this batch", json_pointer="/work_item_id",
                        hint="Inspect the saved plan and ledger, and complete the work item's declared dependencies first.")
                deferred = {item for amendment in state["plan"].get("amendments", []) for item in amendment.get("deferred_work_item_ids", [])}
                if work_id in deferred:
                    raise P4RequestRejected("This work item was deferred by a recorded amendment", json_pointer="/work_item_id",
                        hint="Follow the effective saved plan's prospective schedule; a deferred work item is not currently authorized.")
                path = _safe_file(self.workspace, arguments.get("script_path"), json_pointer="/script_path")
                language = arguments.get("language") or ("r" if path.suffix.lower() == ".r" else "python")
                if language not in {"python", "r"} or path.suffix.lower() != {"python": ".py", "r": ".r"}[language]:
                    raise P4RequestRejected("The script extension must match the declared Python or R language", json_pointer="/language")
                support_files = arguments.get("support_files", [])
                dependencies = arguments.get("dependencies", [])
                if (not isinstance(support_files, list) or len(support_files) > 256
                        or any(not isinstance(value, str) for value in support_files)):
                    raise P4RequestRejected("support_files must be a bounded list of workspace-relative files", json_pointer="/support_files")
                if (not isinstance(dependencies, list) or len(dependencies) > 64
                        or any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]*", value) for value in dependencies)):
                    raise P4RequestRejected("dependencies must list bounded Python module or R package names", json_pointer="/dependencies")
                args = arguments.get("args", [])
                if not isinstance(args, list) or len(args) > 100 or any(not isinstance(item, str) or len(item) > 4000 for item in args):
                    raise P4RequestRejected("args must be a bounded list of strings", code="invalid_arguments", json_pointer="/args")
                result_paths = arguments.get("result_paths", [])
                if not isinstance(result_paths, list) or len(result_paths) > 100:
                    raise P4RequestRejected("result_paths must be a bounded list of workspace files", code="invalid_arguments", json_pointer="/result_paths")
                for index, result_path in enumerate(result_paths):
                    pointer = f"/result_paths/{index}"
                    value = Path(_text(result_path, "Result path", json_pointer=pointer))
                    if value.is_absolute() or ".." in value.parts or not (self.workspace / value).resolve().is_relative_to(self.workspace):
                        raise P4RequestRejected("Result paths must remain inside the workspace", code="invalid_arguments", json_pointer=pointer)
                timeout = _positive(arguments.get("timeout_seconds"), "Batch time limit", json_pointer="/timeout_seconds")
                remaining = state["budget"]["remaining_seconds"]
                if remaining <= 0:
                    self._pause(state, {"question": "How should this evaluation proceed after its time budget?",
                                       "reason": "The authorized experiment budget is exhausted."})
                    self._save(state)
                    return {"accepted": True, "operation": "request_decision", "stop_turn": True}
                attempt_id = f"attempt.{uuid4().hex}"
                batch = {"batch_id": batch_id, "attempt_id": attempt_id,
                    "work_item_id": work_id, "script_path": str(path), "script_sha256": _digest(path),
                    "args": args, "result_paths": result_paths, "timeout_seconds": min(timeout, remaining),
                    "plan_revision_id": state["plan_history"][-1]["revision_id"],
                    "queued_at": _now(), "status": "queued", "workspace": str(self.workspace)}
                snapshots = language == "r" or _declared_sources_enabled(self.run_dir) or any(key in arguments for key in ("support_files", "language", "dependencies", "input_ids"))
                if snapshots:
                    output = self.directory / "batches" / attempt_id
                    source_dir = output / "source"
                    inputs = _batch_inputs(self.run_dir, effective, work, arguments.get("input_ids"))
                    files = _snapshot_sources(self.workspace, source_dir, path, support_files,
                                              raw_dataset_digests=_raw_dataset_digests(self.run_dir))
                    input_manifest = output / "inputs.json"
                    write_json_atomic(input_manifest, inputs)
                    batch.update(language=language, dependencies=dependencies, source_files=files, script_sha256=files[0]["sha256"],
                                 source_directory=str(source_dir), code_path=str(source_dir / path.relative_to(self.workspace)),
                                 input_ids=[item["input_id"] for item in inputs["inputs"]], input_manifest_path=str(input_manifest))
                    write_json_atomic(output / "source-manifest.json", {"language": language, "entrypoint": path.relative_to(self.workspace).as_posix(), "files": files})
                state["pending_batch"] = batch
            elif operation == "request_decision":
                self._pause(state, arguments)
            elif operation == "complete":
                if not state.get("plan"):
                    raise P4RequestRejected("Save an evaluation plan before completing the analyst stage",
                        hint="Save the evaluation protocol and prepare the available evidence before requesting complete.")
                state["completed"] = True
            else:
                raise P4RequestRejected("Unknown Phase 4 control operation", code="invalid_arguments", json_pointer="/operation")
            state["action"] = operation
            self._save(state)
            return {"accepted": True, "operation": operation,
                    "stop_turn": operation in {"run_batch", "request_decision", "complete"},
                    "message": "Request saved. End this turn; the host controls subsequent execution."}

    def _pause(self, state, request):
        options = request.get("options", [{"label": "Finish with the evidence so far", "consequence": "Review the partial findings without further computation."},
                                          {"label": "Continue with instructions", "consequence": "Record the changed direction or budget before more work."}])
        if not isinstance(options, list) or any(not isinstance(item, dict) or not item.get("label") or not item.get("consequence") for item in options):
            raise P4RequestRejected("Decision options require a label and consequence", code="invalid_arguments", json_pointer="/options")
        context_fields = {}
        for field in ("scope", "scope_change", "conditional_scope"):
            if field in request:
                context_fields[field] = copy.deepcopy(request[field])
        if "scope" in context_fields:
            from .problem_context import validate_scope
            try:
                context_fields["scope"] = validate_scope(context_fields["scope"])
            except ValueError as exc:
                raise P4RequestRejected(str(exc), code="invalid_arguments", json_pointer="/scope") from exc
        state["pause_request"] = {"request_id": f"decision.{uuid4().hex}", "revision": 1,
            "question": _text(request.get("question"), "Researcher question", json_pointer="/question"),
            "reason": _text(request.get("reason"), "Reason for pausing", json_pointer="/reason"), "options": copy.deepcopy(options),
            "recommendation": request.get("recommendation", ""), "evidence_refs": copy.deepcopy(request.get("evidence_refs", [])),
            "stage_id": self.stage_id, "member": self.member, "created_at": _now(), **context_fields}
        pending = state.get("pending_batch")
        if pending and pending.get("status") == "queued":
            state["ledger"].append({**pending, "status": "not_started", "finished_at": _now(),
                                    "diagnostic": "The evaluation paused before this batch started."})
            state["pending_batch"] = None

    def resume(self, note, answer_revision, additional_budget_seconds=0):
        with self._lock:
            state = self.snapshot()
            if not state.get("pause_request"):
                raise P4ExecutionError("This evaluation has no pending decision")
            if isinstance(answer_revision, dict) and answer_revision.get("action") == "finish" and not note:
                note = "Finish and review the evidence collected so far."
            _text(note, "Researcher instruction")
            if additional_budget_seconds:
                extra = _positive(additional_budget_seconds, "Additional budget")
                state["budget"]["limit_seconds"] += extra
                state["budget"]["remaining_seconds"] += extra
            state["answer_revisions"].append({"request": state["pause_request"], "answer_revision": copy.deepcopy(answer_revision),
                                               "note": note, "consumed_at": _now()})
            state.update(pause_request=None, action="resumed", finish_requested=isinstance(answer_revision, dict) and answer_revision.get("action") == "finish")
            self._save(state)
            return self.snapshot()

    def recover_interrupted(self):
        with self._lock:
            state = self.snapshot()
            pending = state.get("pending_batch")
            if pending:
                if pending.get("status") == "running" and os.name != "nt":
                    raise P4ExecutionError("An interrupted experiment's process cleanup cannot be confirmed on this host")
                pending.update(status="interrupted", finished_at=_now(), diagnostic="Service stopped before this batch completed; partial output is provisional.")
                state["ledger"].append(pending)
                state["pending_batch"] = None
                if not state.get("pause_request"):
                    self._pause(state, {"question": "How should the interrupted experiment continue?", "reason": pending["diagnostic"]})
                self._save(state)
            return self.snapshot()

    async def execute_pending(self, heartbeat=None):
        with self._lock:
            state = self.snapshot()
            batch = state.get("pending_batch")
            if not batch or state.get("pause_request"):
                raise P4ExecutionError("No authorized experiment is queued")
            if batch["status"] != "queued":
                raise P4ExecutionError("This experiment has already started")
            batch.update(status="running", started_at=_now())
            state["pending_batch"] = batch
            self._save(state)
        output = self.directory / "batches" / batch["attempt_id"]
        output.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        cancelled = False
        cleanup_error = None
        execution_step = "setup"
        result = None
        execution_workspace = None
        try:
            check_setup = getattr(self.runner, "check_setup", None)
            if callable(check_setup):
                await check_setup(self.workspace)
            execution_step = "inputs"
            execution_workspace = Path(batch["workspace"])
            execution_options = {}
            if batch.get("source_directory"):
                source = Path(batch["source_directory"])
                # Source records may have long project/run names. Executable
                # cwd stays beside the engine's existing hashed stage workspace.
                execution_workspace = self.workspace.parent / (".p4-" + batch["attempt_id"].split(".", 1)[-1][:16])
                batch["execution_workspace"] = str(execution_workspace)
                execution_workspace.mkdir()
                for file in batch["source_files"]:
                    frozen = Path(file["snapshot_path"])
                    if _digest(frozen) != file["sha256"]:
                        raise P4ExecutionError("A queued source snapshot changed before execution")
                    target = execution_workspace / file["path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(frozen, target)
                path = execution_workspace / Path(batch["code_path"]).relative_to(source)
                batch["executed_path"] = str(path)
                inputs = read_json(Path(batch["input_manifest_path"]))
                await _prepare_owned_read_access(output, owned_root=self.directory)
                for item in inputs["inputs"]:
                    if _digest(Path(item["snapshot_path"])) != item["sha256"]:
                        raise P4ExecutionError("A frozen run input changed before execution")
                    await _prepare_owned_read_access(Path(item["snapshot_path"]).parent,
                                                     owned_root=self.run_dir / "inputs/researcher")
                execution_options = {"language": batch["language"], "dependencies": batch.get("dependencies", []),
                                     "read_paths": [Path(batch["input_manifest_path"]), *[Path(item["snapshot_path"]) for item in inputs["inputs"]]]}
            else:
                # Historical contracts retain their original Python-only behavior.
                path = Path(batch["script_path"])
                if _digest(path) != batch["script_sha256"]:
                    raise P4ExecutionError("The queued script changed before execution")
                shutil.copyfile(path, output / "code.py")
                batch["code_path"] = str(output / "code.py")
            execution_step = "runtime"
            result = await self.runner.execute(path, batch["args"], workspace=execution_workspace,
                                               timeout=batch["timeout_seconds"], output_dir=output,
                                               heartbeat=heartbeat, context={
                                                   "MODEL_FORGE_P4_BATCH_ID": batch["batch_id"],
                                                   "MODEL_FORGE_P4_ATTEMPT_ID": batch["attempt_id"],
                                                   "MODEL_FORGE_P4_PLAN_REVISION_ID": batch["plan_revision_id"],
                                                   **({"MODEL_FORGE_P4_INPUTS_PATH": batch["input_manifest_path"]} if batch.get("input_manifest_path") else {})}, **execution_options)
            result["artifacts"] = []
            if result["status"] == "completed":
                execution_step = "outputs"
                for relative in batch.get("result_paths", []):
                    source = _safe_file(execution_workspace, relative)
                    if _digest(source) in _raw_dataset_digests(self.run_dir):
                        source.unlink()
                        raise P4ExecutionError("Raw researcher datasets cannot be retained as result artifacts; report aggregates and keep the frozen input separate")
                    target = output / "artifacts" / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    result["artifacts"].append({"path": str(target), "source_path": relative,
                                                 "sha256": _digest(target), "size_bytes": target.stat().st_size})
                    if batch.get("source_directory"):
                        workspace_target = Path(batch["workspace"]) / relative
                        workspace_target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(target, workspace_target)
        except asyncio.CancelledError:
            diagnostic = ("Computation completed, but retaining its outputs was interrupted; retained evidence is provisional."
                          if execution_step == "outputs" else "Computation was interrupted; partial outputs are provisional and cannot establish completed results.")
            result = {**(result or {}), "status": "interrupted", "diagnostic": diagnostic}
            cancelled = True
        except P4CleanupError as exc:
            result = {"status": "cleanup_unconfirmed", "diagnostic": str(exc), "cleanup_confirmed": False}
            cleanup_error = exc
        except Exception as exc:
            if execution_step == "outputs":
                result = {**result, "status": "output_error",
                          "diagnostic": f"The computation finished successfully, but its declared output {relative!r} could not be retained: {exc}. Check the script's output path and the saved logs before explicitly continuing."}
            elif execution_step == "inputs" and not isinstance(exc, P4InfrastructureError):
                result = {"status": "input_error",
                          "diagnostic": f"The experiment inputs could not be prepared, so computation did not start: {exc}. Check the queued script and retained input paths before explicitly continuing."}
            else:
                result = {"status": "infrastructure_error", "diagnostic": str(exc)}
                if execution_step in {"setup", "inputs"}:
                    result["computation_started"] = False
                if isinstance(exc, (P4WindowsSetupError, P4InfrastructureError)):
                    result["setup_kind"] = "windows_sandbox"
                (output / "stderr.log").write_text(str(exc) + "\n", encoding="utf-8")
        if (batch.get("source_directory") and execution_workspace is not None and execution_workspace.exists()
                and result["status"] != "cleanup_unconfirmed"):
            # The runner has stopped its process tree before reaching here.
            # Retain failure outputs without leaving a second live working area.
            try:
                if (execution_workspace.parent.resolve() != self.workspace.parent.resolve()
                        or not execution_workspace.name.startswith(".p4-")):
                    raise P4ExecutionError("The execution scratch directory is outside its engine-owned root")
                retained = (output / "work").resolve()
                if not retained.is_relative_to(self.directory.resolve()):
                    raise P4ExecutionError("The retained execution directory is outside its engine-owned root")
                shutil.move(str(execution_workspace), str(retained))
                batch["retained_work_path"] = str(retained)
            except (OSError, P4ExecutionError) as exc:
                batch["work_retention_diagnostic"] = str(exc)
        elapsed = time.monotonic() - started
        with self._lock:
            state = self.snapshot()
            finished = {**batch, **result, "elapsed_seconds": elapsed, "finished_at": _now(), "output_dir": str(output)}
            state["ledger"].append(finished)
            state["pending_batch"] = None
            state["budget"]["used_seconds"] += elapsed
            state["budget"]["remaining_seconds"] = max(0, state["budget"]["limit_seconds"] - state["budget"]["used_seconds"])
            repeated_failures = sum(item["work_item_id"] == batch["work_item_id"] and item["status"] == "failed" for item in state["ledger"]) >= 2
            must_pause = result["status"] not in {"completed", "failed"} or repeated_failures or state["budget"]["remaining_seconds"] <= 0
            if not state.get("pause_request") and must_pause:
                question = {"infrastructure_error": "Restore the experiment setup before continuing.",
                            "input_error": "Repair the experiment inputs before continuing.",
                            "output_error": "Repair the declared experiment outputs before continuing."}.get(result["status"], "How should the evaluation proceed from this experiment?")
                self._pause(state, {"question": question,
                    "reason": result.get("diagnostic") or "The authorized computation budget is exhausted.",
                    "evidence_refs": [{"batch_id": batch["batch_id"], "attempt_id": batch["attempt_id"]}]})
            self._save(state)
        if cancelled:
            raise asyncio.CancelledError
        if cleanup_error:
            raise cleanup_error
        return finished


_GATED_LAUNCHER = "import json,subprocess,sys; command=json.loads(sys.argv[1]); gate=sys.stdin.readline(); sys.exit(subprocess.call(command) if gate == 'start\\n' else 125)"
_SANDBOX_ENTRY = """import importlib,json,os,pathlib,runpy,sys
marker=pathlib.Path(os.environ['MODEL_FORGE_P4_STARTED_PATH'])
runtime={'language':'python','python_executable':sys.executable,'python_version':sys.version,'computation_started':False}
marker.write_text(json.dumps(runtime),encoding='utf-8')
sys.argv=sys.argv[1:]
sys.path.insert(0,str(pathlib.Path(sys.argv[0]).parent))
for name in json.loads(os.environ.get('MODEL_FORGE_P4_DEPENDENCIES','[]')):
    try:
        importlib.import_module(name)
    except Exception as error:
        print('Required shared Python dependency '+name+' is unavailable: '+str(error)+'. Install or repair it in the shared runtime.',file=sys.stderr)
        sys.exit(78)
runtime['computation_started']=True
marker.write_text(json.dumps(runtime),encoding='utf-8')
runpy.run_path(sys.argv[0],run_name='__main__')
"""
_R_SANDBOX_ENTRY = """args <- commandArgs(trailingOnly=TRUE)
marker <- Sys.getenv('MODEL_FORGE_P4_STARTED_PATH')
record <- function(started) writeLines(paste0('{"language":"r","r_executable":',encodeString(Sys.getenv('MODEL_FORGE_P4_RUNTIME_PATH'),quote='"'),',"r_version":',encodeString(R.version.string,quote='"'),',"computation_started":',if(started) 'true' else 'false','}'),marker)
record(FALSE)
dependencies <- strsplit(Sys.getenv('MODEL_FORGE_P4_R_DEPENDENCIES'),',',fixed=TRUE)[[1]]
for (name in dependencies[nzchar(dependencies)]) {
  if (!requireNamespace(name,quietly=TRUE)) {
    message('Required shared R package ',name,' is unavailable. Install or repair it in a shared R library.')
    quit(save='no',status=78)
  }
}
script <- args[[1]]
script_args <- args[-1]
commandArgs <- function(trailingOnly=FALSE) if(trailingOnly) script_args else base::commandArgs(FALSE)
record(TRUE)
source(script,local=.GlobalEnv,chdir=FALSE)
"""


def shared_python_executable():
    """Honor configuration, then reuse the app's installed shared Windows runtime.

    The desktop runtime is shared across projects and prepared for managed
    sandbox access. An ordinary per-user Python can launch on the host while
    its interpreter ACL prevents the sandbox account from launching it.
    Nothing is installed, copied or granted additional permissions here.
    """
    if "MF_P4_PYTHON" in os.environ:
        return Path(os.environ["MF_P4_PYTHON"]).resolve()
    if os.name == "nt":
        shared = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
        if shared.is_file():
            return shared.resolve()
    return Path(sys.executable).resolve()


def shared_rscript_executable():
    """Locate an existing shared R installation, without downloading a runtime."""
    if "MF_P4_RSCRIPT" in os.environ:
        return Path(os.environ["MF_P4_RSCRIPT"]).resolve()
    on_path = shutil.which("Rscript")
    if on_path:
        return Path(on_path).resolve()
    if os.name == "nt":
        root = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "R"
        candidates = sorted(root.glob("R-*/bin/Rscript.exe"), reverse=True) if root.is_dir() else []
        if candidates:
            return candidates[0].resolve()
    return None


class _WindowsJob:
    """Kill-on-close ownership covers descendants, including detached children."""
    def __init__(self, pid):
        from ctypes import wintypes
        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "Cannot create experiment process group")
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000
        process = self.api.OpenProcess(0x0100 | 0x0001, False, pid)
        try:
            if not process or not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)) or not self.api.AssignProcessToJobObject(self.handle, process):
                raise OSError(ctypes.get_last_error(), "Cannot own the experiment process tree")
        except Exception:
            self.close()
            raise
        finally:
            if process:
                self.api.CloseHandle(process)

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

    async def stop(self):
        from ctypes import wintypes
        class Accounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_longlong) for name in ("TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")] + [(name, wintypes.DWORD) for name in ("TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")]
        if not self.handle:
            return
        try:
            if not self.api.TerminateJobObject(self.handle, 125):
                raise P4CleanupError("The experiment process tree could not be stopped")
            deadline = time.monotonic() + 5
            while True:
                accounting = Accounting()
                if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
                    raise P4CleanupError("The experiment process tree could not be inspected after stopping")
                if accounting.ActiveProcesses == 0:
                    return
                if time.monotonic() >= deadline:
                    raise P4CleanupError("The experiment still has active child processes after its stop deadline")
                await asyncio.sleep(0.02)
        finally:
            self.close()


class ManagedPythonRunner:
    """Run shared Python or R with the same managed sandbox and process ownership.

    The historical name remains public for existing integrations.
    """
    def __init__(self, *, command_builder=None):
        # The injectable launcher is for tests of lifecycle ownership, not an app option.
        self.command_builder = command_builder or self.sandbox_command
        self.managed = command_builder is None

    async def check_setup(self, workspace):
        if self.managed and os.name == "nt":
            from .bridge import check_p4_windows_runtime
            return await check_p4_windows_runtime(workspace)

    @staticmethod
    def sandbox_command(script, args, workspace, *, language="python", read_paths=()):
        executable = find_codex()
        if not executable and os.name == "nt":
            candidate = Path.home() / "AppData/Local/Programs/OpenAI/Codex/bin/codex.exe"
            executable = str(candidate) if candidate.is_file() else None
        if not executable:
            raise P4ExecutionError("The shared Codex CLI is unavailable; install or repair the user-wide openai-codex Python package before running experiments")
        command = [executable, "sandbox"]
        if os.name != "nt":
            command.append("macos" if sys.platform == "darwin" else "linux")
        # Current CLI requires a named profile. Extend the standard workspace
        # boundary with network disabled, only for this child process. Managed
        # requirements remain in force; no global configuration is rewritten.
        runtime = shared_rscript_executable() if language == "r" else shared_python_executable()
        variable = "MF_P4_RSCRIPT" if language == "r" else "MF_P4_PYTHON"
        if runtime is None or not runtime.is_file():
            raise P4ExecutionError(f"The chosen shared {language} runtime is unavailable or inaccessible; verify the installed runtime and configure {variable}. No substitute runtime was used.")
        if (runtime.is_relative_to(Path(workspace).resolve())
                or any((directory / "pyvenv.cfg").is_file() or directory.name in {".venv", "venv", ".env", ".Rlib"}
                       for directory in (runtime.parent, runtime.parent.parent))):
            raise P4ExecutionError(f"{variable} must name a shared installation, not a project environment")
        if language == "r":
            runtime_dirs = [runtime.parent.parent, *[Path(value) for key in ("R_LIBS", "R_LIBS_USER", "R_LIBS_SITE")
                for value in os.environ.get(key, "").split(os.pathsep) if value]]
            # R's normal per-user package directories are shared across projects.
            if os.name == "nt":
                runtime_dirs += [Path.home() / "AppData/Local/R/win-library", Path.home() / "Documents/R/win-library"]
            else:
                runtime_dirs += [Path.home() / "R", Path.home() / "Library/R"]
        else:
            runtime_dirs = [runtime.parent, Path(sys.base_prefix), *map(Path, site.getsitepackages()), Path(site.getusersitepackages())]
        # Windows sandbox ACL preparation grants directory trees. File-only
        # entries do not make their containing directory traversable.
        readable = [str((Path(value).parent if Path(value).is_file() else Path(value)).resolve())
                    for value in [*runtime_dirs, *read_paths] if Path(value).exists()]
        reads = ", ".join(json.dumps(value) + '=\"read\"' for value in dict.fromkeys(readable))
        profile = 'permissions.model-forge-p4={extends=":workspace",network={enabled=false},filesystem={' + reads + '}}'
        command += ["-P", "model-forge-p4", "--include-managed-config", "-c", profile,
                    "-c", "approval_policy=\"never\""]
        if language == "r":
            # The Windows Rscript front-end drops multiline -e expressions.
            # An ordinary script file also keeps quoting independent of shell rules.
            bootstrap = Path(workspace) / ".p4-runner/entry.R"
            bootstrap.parent.mkdir(parents=True, exist_ok=True)
            bootstrap.write_text(_R_SANDBOX_ENTRY, encoding="utf-8")
            child = [str(runtime), "--vanilla", str(bootstrap), str(script), *args]
        else:
            child = [str(runtime), "-c", _SANDBOX_ENTRY, str(script), *args]
        command += ["-C", _process_directory(workspace), "--", *child]
        return command

    async def execute(self, script, args, *, workspace, timeout, output_dir, heartbeat=None, context=None,
                      language="python", dependencies=(), read_paths=()):
        # Create logs before discovery so unavailable runtimes still have a receipt.
        for filename in ("stdout.log", "stderr.log"):
            (output_dir / filename).touch()
        try:
            await self.check_setup(workspace)
            await asyncio.to_thread(ensure_workspace_owner_access, workspace, owned_root=workspace.parent)
            command = (self.sandbox_command(script, args, workspace, language=language, read_paths=read_paths)
                       if self.managed else self.command_builder(script, args, workspace))
        except Exception as exc:
            (output_dir / "stderr.log").write_text(str(exc) + "\n", encoding="utf-8")
            write_json_atomic(output_dir / "launch.json", {"language": language, "created_at": _now(), "diagnostic": str(exc), "computation_started": False})
            return {"status": "infrastructure_error", "language": language, "diagnostic": str(exc), "computation_started": False,
                    **({"setup_kind": "windows_sandbox"} if isinstance(exc, P4WindowsSetupError) else {})}
        # Persist the launch context even when cancellation prevents a normal
        # return value. The owning attempt already retains this output folder.
        write_json_atomic(output_dir / "launch.json", {"command": command, "created_at": _now(),
            "host_python_executable": sys.executable, "host_python_version": sys.version})
        allowed = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "USERPROFILE", "HOME", "APPDATA", "LOCALAPPDATA", "CODEX_HOME", "PATHEXT", "LANG", "LC_ALL", "PYTHONUTF8", "R_LIBS", "R_LIBS_USER", "R_LIBS_SITE"}
        environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
        if self.managed and os.name == "nt":
            # Keep the same resolved runtime home used by the setup check even
            # when the user's CODEX_HOME was relative to the app's launch cwd.
            environment["CODEX_HOME"] = str(runtime_settings(Path(workspace))[0])
        # Shared installed packages remain available; arbitrary provider credentials do not.
        environment["PYTHONUNBUFFERED"] = "1"
        environment.update({key: str(value) for key, value in (context or {}).items()
                            if key in {"MODEL_FORGE_P4_BATCH_ID", "MODEL_FORGE_P4_ATTEMPT_ID", "MODEL_FORGE_P4_PLAN_REVISION_ID", "MODEL_FORGE_P4_INPUTS_PATH"}})
        environment["MODEL_FORGE_P4_DEPENDENCIES"] = json.dumps(list(dependencies))
        environment["MODEL_FORGE_P4_R_DEPENDENCIES"] = ",".join(dependencies)
        if language == "r" and self.managed:
            environment["MODEL_FORGE_P4_RUNTIME_PATH"] = str(shared_rscript_executable())
        marker = workspace / ".p4-runner" / (uuid4().hex + ".json")
        marker.parent.mkdir(parents=True, exist_ok=True)
        environment["MODEL_FORGE_P4_STARTED_PATH"] = str(marker)
        kwargs = {"start_new_session": True} if os.name != "nt" else {"creationflags": 0x08000000}
        process = None
        job = None
        with (output_dir / "stdout.log").open("wb") as stdout, (output_dir / "stderr.log").open("wb") as stderr:
            try:
                process = await asyncio.create_subprocess_exec(sys.executable, "-c", _GATED_LAUNCHER, json.dumps(command),
                    cwd=_process_directory(workspace), env=environment, stdin=asyncio.subprocess.PIPE,
                    stdout=stdout, stderr=stderr, **kwargs)
                if os.name == "nt":
                    job = _WindowsJob(process.pid)
                process.stdin.write(b"start\n")
                await process.stdin.drain()
                process.stdin.close()
                if heartbeat:
                    heartbeat("Running the next bounded computational experiment.")
                try:
                    await asyncio.wait_for(process.wait(), timeout=timeout)
                except TimeoutError:
                    return {"status": "timed_out", "diagnostic": f"The batch reached its {timeout:g} second limit.",
                            "pid": process.pid, "command": command, "runtime": read_json(marker)}
                runtime = read_json(marker) if marker.is_file() else {"python_executable": sys.executable, "python_version": sys.version, "test_launcher": True}
                infrastructure = self.managed and (not marker.is_file() or not runtime.get("computation_started"))
                diagnostic = (f"The managed {language} setup or required dependencies could not start computation; inspect stderr.log and verify the shared installation."
                              if infrastructure else "" if process.returncode == 0 else "The experiment script exited unsuccessfully; inspect its saved logs before deciding whether a routine correction is justified.")
                return {"status": "infrastructure_error" if infrastructure else "completed" if process.returncode == 0 else "failed", "exit_code": process.returncode,
                        "computation_started": not infrastructure,
                        "pid": process.pid, "runtime": runtime, "command": command, "language": language,
                        "diagnostic": diagnostic}
            finally:
                if job:
                    await asyncio.shield(job.stop())
                elif process and os.name != "nt":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                elif process and process.returncode is None:
                    process.kill()
                if process:
                    await asyncio.shield(process.wait())
