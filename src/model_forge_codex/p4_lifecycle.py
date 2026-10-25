"""Phase 4 checkpoint lifecycle within the existing three member stages."""

from __future__ import annotations

import asyncio
import json
import math
import os
from dataclasses import asdict

from .domain import Finding, MemberRole, RunState, StageResult, TERMINAL_STATES
from .project_brief import project_instructions
from .storage import read_json, sha256_file, write_json_atomic


def default_experiment_budget() -> float:
    value = float(os.environ.get("MF_P4_BUDGET_SECONDS", "600"))
    if not math.isfinite(value) or value <= 0:
        raise ValueError("MF_P4_BUDGET_SECONDS must be a positive number")
    return value


def _work_progress(state):
    """Compare saved actions, excluding checkpoint traffic and JSON formatting."""
    pending = state.get("pending_batch") or {}
    return (json.dumps(state.get("plan"), sort_keys=True, separators=(",", ":")),
            (pending.get("attempt_id"), pending.get("status")),
            tuple((row.get("attempt_id"), row.get("status")) for row in state.get("ledger", [])),
            state.get("completed"), state.get("pause_request"))


class P4LifecycleMixin:
    def _progressive_p4(self, record) -> bool:
        if record.phase != "P4" or record.intent != "run":
            return False
        directory = self.run_dir(record.project_id, record.run_id) / "contracts"
        contract = read_json(directory / "contracts" / "phases" / "P4.json") or {}
        return "progressive_evaluation_v1" in contract.get("capabilities", [])

    def _p4_controller(self, record, stage=None, role=None):
        from .p4_execution import P4Controller
        directory = self.run_dir(record.project_id, record.run_id)
        if stage is None:
            saved = P4Controller.load_snapshot(directory) or {}
            stage = next((s for s in self._stages(record) if s.stage_id == saved.get("resume_stage")),
                         self._stages(record)[0])
            role = MemberRole(saved.get("resume_member") or stage.roles[0])
        role = role or stage.roles[0]
        return P4Controller(directory, self.member_workspace(record, stage.stage_id, role),
                            stage_id=stage.stage_id, member=role.value,
                            budget_seconds=record.experiment_budget_seconds or default_experiment_budget())

    def _dialogue_p4(self, record):
        from .problem_context import supports_problem_context
        return supports_problem_context(self.run_dir(record.project_id, record.run_id), "P4")

    def _p4_context_changes(self, record, accepted_context_items=(), accepted_answer_refs=(), current_basis=None) -> list[dict]:
        """Compare current context, while preserving every frozen input on resume."""
        directory = self.run_dir(record.project_id, record.run_id)
        frozen = read_json(directory / "basis.json") or {}
        current = current_basis or self.compute_basis(record.project_id, record.phase, record.branch_id, record.mode)
        if self._dialogue_p4(record):
            from .researcher_pause import continuation_context_changes
            from .problem_context import answer_reference
            from pathlib import Path
            from .p4_execution import P4Controller
            progress = P4Controller.load_snapshot(directory) or {}
            revisions = [row.get("answer_revision") or {} for row in progress.get("answer_revisions", [])]
            adopted = [*accepted_context_items, *(item for row in revisions for item in row.get("accepted_context_items", []))]
            allowed_answers = [*accepted_answer_refs, *(row["answer_ref"] for row in revisions if row.get("answer_ref"))]
            changes = continuation_context_changes(frozen, current, adopted)
            def researcher_answers(basis):
                ref = basis.get("cumulative_inputs", {}).get("researcher_answers", {})
                document = read_json(Path(ref["snapshot_path"])) if ref.get("snapshot_path") else ref.get("document")
                return [item for item in (document or {}).get("items", []) if answer_reference(item) not in allowed_answers]
            if researcher_answers(frozen) != researcher_answers(current):
                changes.append({"kind": "research_context", "family": "researcher_answers",
                                "message": "Other saved researcher responses have changed."})
            for name in sorted(set(frozen.get("cumulative_inputs", {})) | set(current.get("cumulative_inputs", {}))):
                if name == "researcher_answers":
                    continue
                if frozen.get("cumulative_inputs", {}).get(name, {}).get("sha256") != current.get("cumulative_inputs", {}).get(name, {}).get("sha256"):
                    changes.append({"kind": "research_context", "family": name, "message": f"Saved {name.replace('_', ' ')} have changed."})
            if frozen.get("catalog_sha256") != current.get("catalog_sha256"):
                changes.append({"kind": "catalog", "message": "The project adopted newer contracts; this run retains its frozen contracts."})
            return changes
        changes = []
        if project_instructions(frozen.get("project", {})) != project_instructions(current.get("project", {})):
            changes.append({"kind": "project_instructions", "message": "Project instructions have changed."})
        def refs(basis):
            return {(r.get("phase"), r.get("branch"), r.get("family")): r.get("content_sha256")
                    for r in basis.get("records", [])}
        before, after = refs(frozen), refs(current)
        for key in sorted(before.keys() | after.keys()):
            if before.get(key) != after.get(key):
                changes.append({"kind": "published_input", "phase": key[0], "family": key[2],
                                "message": f"{key[0]} {key[2]} has changed.",
                                "frozen_sha256": before.get(key), "current_sha256": after.get(key)})
        for name in sorted(set(frozen.get("cumulative_inputs", {})) | set(current.get("cumulative_inputs", {}))):
            old = frozen.get("cumulative_inputs", {}).get(name, {}).get("sha256")
            new = current.get("cumulative_inputs", {}).get(name, {}).get("sha256")
            if old != new:
                changes.append({"kind": "research_context", "family": name,
                                "message": f"Saved {name.replace('_', ' ')} have changed."})
        if frozen.get("catalog_sha256") != current.get("catalog_sha256"):
            changes.append({"kind": "catalog", "message": "The project adopted newer contracts; this run retains its frozen contracts."})
        return changes

    def p4_progress(self, record):
        if not self._progressive_p4(record):
            return None
        from .p4_execution import P4Controller, P4ExecutionError, setup_attention
        from pathlib import Path
        directory = self.run_dir(record.project_id, record.run_id)

        def classify_request(request):
            attention = setup_attention(progress, request)
            return {**request, "attention_kind": "setup"} if attention else request

        def technical_logs(attention):
            # Only host-owned attempt logs inside this run are readable here.
            boundary = (directory / "p4-execution" / "batches").resolve()
            output = Path(attention.get("output_dir", "")).resolve()
            logs = []
            if output.is_relative_to(boundary):
                for name in ("stderr.log", "stdout.log", "launch.json"):
                    path = output / name
                    if path.resolve().is_relative_to(boundary) and path.is_file():
                        try:
                            with path.open("rb") as stream:
                                value = stream.read(8193)
                            logs.append({"path": str(path.relative_to(directory)), "sha256": sha256_file(path),
                                         "text": value[:8192].decode("utf-8", errors="replace"),
                                         "truncated": len(value) > 8192})
                        except OSError:
                            continue
            return logs
        try:
            progress = P4Controller.load_snapshot(self.run_dir(record.project_id, record.run_id)) or {}
        except P4ExecutionError as exc:
            return {"capability": "progressive_evaluation_v1", "provisional": record.state != RunState.PUBLISHED,
                    "execution_state_error": str(exc), "continuation_blocked": str(exc)}
        result = {**progress, "capability": "progressive_evaluation_v1", "provisional": record.state != RunState.PUBLISHED}
        result["control_feedback"] = read_json(directory / "p4-control-feedback.json") or {}
        from .phase_interactions import pause_target
        saved = read_json(self.run_dir(record.project_id, record.run_id) / "p4-decision-answers.json") or []
        applied = {row.get("answer_revision", {}).get("saved_answer_revision") for row in progress.get("answer_revisions", [])}
        result["saved_answers"] = [{**answer, "applied_to": [record.run_id] if answer["revision"] in applied else []} for answer in saved]
        for row in progress.get("answer_revisions", []):
            revision = row.get("answer_revision") or {}
            request = row.get("request") or {}
            if revision.get("saved_answer_revision") is None and request.get("request_id"):
                result["saved_answers"].insert(0, {"request_id": request["request_id"], "request_revision": request["revision"],
                                                  "revision": 0, "note": revision.get("answer", row.get("note", "")),
                                                  "saved_at": revision.get("accepted_at"), "request": request,
                                                  "applied_to": [record.run_id]})
        from .phase_interactions import evaluation_answer_consumers
        consumers = evaluation_answer_consumers(self.project_dir(record.project_id), record.run_id) if saved else {}
        for answer in result["saved_answers"]:
            answer["applied_to"] = list(dict.fromkeys([*answer["applied_to"], *consumers.get(answer["revision"], [])]))
            request = answer.get("request")
            if request:
                answer["request"] = {**classify_request(request), "explanation_target": pause_target(record, request)}
        pending = progress.get("pause_request")
        if pending:
            result["pause_request"] = {**classify_request(pending), "explanation_target": pause_target(record, pending)}
            attention = setup_attention(progress)
            if attention:
                result["attention_kind"] = "setup"
                result["setup_attention"] = {**attention, "logs": technical_logs(attention)}
            result["saved_answer"] = next((answer for answer in reversed(result["saved_answers"])
                                            if answer["request_id"] == pending["request_id"] and answer["request_revision"] == pending["revision"]), None)
        if record.state == RunState.AWAITING_USER:
            try:
                self._assert_publication_current(record)
                result["continuation_blocked"] = None
            except Exception as exc:
                result["continuation_blocked"] = str(exc)
            try:
                # The exact current pause's saved response is the choice shown
                # for continuation, not an unrelated change to frozen context.
                # Every other answer and context change still compares strictly.
                answer_ref = (result.get("saved_answer") or {}).get("answer_ref")
                result["context_changes"] = self._p4_context_changes(
                    record, accepted_answer_refs=[answer_ref] if answer_ref else [])
            except Exception as exc:
                result["continuation_blocked"] = str(exc)
        return result

    def _p4_brief(self, record, stage, role) -> str:
        if not self._progressive_p4(record):
            return ""
        from .p4_execution import P4Controller, _declared_sources_enabled
        progress = P4Controller.load_snapshot(self.run_dir(record.project_id, record.run_id)) or {}
        declared_sources = _declared_sources_enabled(self.run_dir(record.project_id, record.run_id))
        runtime_instructions = (
            "Write Python or R scripts and submit one bounded batch through run_batch. Declare language (python or r), "
            "support_files as a list of relative helper/configuration paths, dependencies as Python import-module or R package names, "
            "and optional input_ids drawn from the work item's declared frozen data sources. The host captures the entrypoint and "
            "all support_files when accepting the request, then executes those bytes from a separate attempt directory. "
            "Every relative input needed by the script must be declared; the live workspace is not the execution directory. "
            "result_paths are relative to that directory; successful results are sealed and returned to the member workspace. "
            "Frozen researcher data stays outside the member workspace. Read its paths and variable mapping through the JSON file "
            "named by MODEL_FORGE_P4_INPUTS_PATH; never copy raw data into support files, published results, or portable examples. "
            "Use ordinary command-line data paths for portable examples; harness identifiers are optional metadata outside managed batches. "
            "A missing chosen runtime or required dependency is a setup need; do not substitute a different language or install privately. "
            if declared_sources else "Write Python scripts and submit one bounded batch through run_batch. ")
        feedback = read_json(self.run_dir(record.project_id, record.run_id) / "p4-control-feedback.json")
        # Repeating the full replicate grid, old checkpoints and launch commands
        # on every turn obscures the next decision. Keep those exact records
        # available by path while delivering current control facts inline.
        brief_progress = {key: value for key, value in progress.items()
                          if key not in {"plan", "plan_history", "ledger", "checkpoints"}}
        plan = progress.get("plan") or {}
        brief_progress["plan_summary"] = {key: plan[key] for key in
            ("protocol_id", "plan_revision_id", "decision_context", "work_items") if key in plan}
        if "amendments" in plan:
            amendments = plan["amendments"]
            brief_progress["plan_summary"]["amendments"] = [
                {**{key: value for key, value in amendment.items() if not key.startswith("added_")},
                 "added_counts": {key: len(value) for key, value in amendment.items() if key.startswith("added_")}}
                for amendment in amendments]
            # Added work remains actionable: retain its limits and dependencies
            # inline, without repeating each added case's scientific declarations.
            brief_progress["plan_summary"]["work_items"] = [*plan.get("work_items", []),
                *(item for amendment in amendments for item in amendment.get("added_work_items", []))]
        brief_progress["ledger"] = [{key: attempt[key] for key in
            ("batch_id", "attempt_id", "work_item_id", "plan_revision_id", "status", "elapsed_seconds",
             "diagnostic", "script_sha256", "output_dir", "runtime", "language", "source_directory", "code_path", "input_ids") if key in attempt}
            for attempt in progress.get("ledger", [])]
        brief_progress["saved_state_path"] = str(self.run_dir(record.project_id, record.run_id) / "p4-execution" / "state.json")
        return (
            "## Progressive evaluation control\n\n"
            "Use the `p4_checkpoint` member tool. Its requests are persisted by the host. "
            "When using the JavaScript exec wrapper, print the ENTIRE response with "
            "`text(await tools.p4_checkpoint({...}))`; this dynamic tool does not return the MCP content array. "
            "Inspect the entire accepted/error response and any field pointer and correction hint. "
            "accepted=false means this request was rejected; earlier pending work may still exist. "
            "An unknown execution state is not a rejection: inspect the saved controller state before any retry. "
            "Correct only the named fields. Do not repeat an unchanged rejected request. "
            "run_batch requires operation, a new batch_id, an exact declared work_item_id, script_path, "
            "args, timeout_seconds and result_paths. Execute only that work item's declared cases. "
            "Scripts must select that work item explicitly, rather than running the entire study on every invocation. "
            "In a detailed evaluation, keep the implementation/timing pilot and the subsequent scientific comparisons "
            "as separate work items so pilot results can inform the remaining schedule. "
            "Use the protocol's exact metric_id, case_id and replicate_id strings in every numerical row and diagnostic. "
            "Each case has one comparator identity. Represent selected-method and baseline measurements as separate "
            "cases using the same metric definitions; never label a mixed-method row as only the baseline. "
            "For paired comparisons, report the uncertainty of the paired difference being interpreted, "
            "not only each method's marginal uncertainty. "
            "For method-fit timing, generate the data before starting the timer; record data preparation, "
            "tuning and total experiment time separately. Label any broader timing boundary explicitly. "
            "Provide an analysis script that regenerates tables and figures from the saved numerical rows "
            "without running new experiments or changing those rows. Reviewers must compare quoted numbers "
            "with the final eligible rows and tables, and verify timing boundaries against the saved executed "
            "script. Expose any mismatch in the scientific account; do not silently rewrite recorded values. "
            "An accepted run_batch, request_decision or complete request ends this turn. "
            "Do not launch experiment processes through shell commands. "
            + runtime_instructions + "Inspect its actual host-recorded result on the next turn. "
            "Declare result_paths in run_batch, including its numerical JSONL and figure/table outputs. "
            "The runner seals these files on success. Each observed metrics row must include batch_id, "
            "attempt_id and plan_revision_id from the script environment MODEL_FORGE_P4_BATCH_ID, "
            "MODEL_FORGE_P4_ATTEMPT_ID and MODEL_FORGE_P4_PLAN_REVISION_ID. Keep raw batch rows unchanged "
            "when assembling metrics_long.jsonl. Invalidated rows retain their values and carry eligibility "
            "invalidated with a reason; missing planned cases use status not_run. "
            "Use shared installed runtimes/packages only, never local environments or installations. "
            "Before the first batch, save protocol.json and call save_plan with protocol_path. "
            "Record prospective amendments before changed work. Keep failed attempts and unfavorable results. "
            "After each batch, explain the observed results, time and next action using checkpoint. "
            'For a checkpoint, send `{"operation":"checkpoint","checkpoint":{"summary":"Observed results and next action",'
            '"evidence_refs":[{"path":"rows.jsonl","sha256":"<actual file SHA256>"}]}}`. '
            "Replace the example path and digest with the actual saved file path and SHA256. "
            "The analyst calls complete only after all final analyst outputs pass validate_artifacts. "
            "A pause uses request_decision with one concrete question, reason, options and evidence_refs. "
            "Ask for an unresolved researcher preference or unavailable study fact only when its answer materially changes interpretation, "
            "inferential validity, data applicability or an unavoidable resource compromise. "
            "Do not manufacture alternatives for a study fact or ask the researcher to resolve a proof or implementation defect; "
            "report the defect and, if progress is blocked, the consequential scope or continuation choice. "
            "Nonblocking unknowns permit explicitly conditional work and need no question. "
            "Missing final artifacts at a pause are expected. Theorist and lead can also request_decision "
            "on a severe issue; otherwise save and validate their normal owned outputs and end their turn. "
            "Reviewers must not call complete or run_batch; those operations are analyst-only. "
            "Never rescue an ambiguous or defective mathematical method. A routine code correction must "
            "record a new script revision, invalidate affected attempts and recompute. "
            "If finish_requested is true, perform no further experiments. Complete a partial account from "
            "the available evidence for the remaining theorist and lead review. "
            "Researcher answers below are immutable authorization for this continuation, not permission "
            "to change the frozen method. New context is not incorporated automatically.\n\n"
            + "Current controller state (host facts; saved_state_path contains the exact complete plan, "
              "sealed artifact paths, earlier checkpoints and history when needed). "
              "Amendments below retain their reasons, inferential consequences, ordering and deferrals; added_counts "
              "reports declaration counts, and work_items includes added work. Before executing or interpreting affected work, "
              "read the full saved plan at saved_state_path for exact cases, metrics, repetitions, thresholds, baselines "
              "and data-source declarations; these counts do not replace those definitions.\n```json\n"
            + json.dumps(brief_progress, ensure_ascii=False, indent=1) + "\n```\n\n"
            + ("Latest control-tool feedback:\n```json\n" + json.dumps(feedback, ensure_ascii=False) + "\n```\n\n" if feedback else "")
        )

    def _validate_p4_execution(self, record, documents):
        """Bind reported observations to host-sealed completed computation."""
        if not self._progressive_p4(record):
            return []
        from pathlib import Path
        from .p4_execution import P4Controller, _declared_sources_enabled
        progress = P4Controller.load_snapshot(self.run_dir(record.project_id, record.run_id)) or {}
        findings = []
        def problem(code, text, family, pointer=""):
            findings.append(Finding("execution." + code, text, family, pointer))
        protocol = documents.get("p4.protocol")
        if protocol is not None and protocol != progress.get("plan"):
            problem("unsaved_plan", "The protocol must match the plan saved before computation, including its prospective amendments.", "p4.protocol")
        by_attempt = {attempt.get("attempt_id"): attempt for attempt in progress.get("ledger", [])}
        from .empirical_targets import effective_protocol
        effective = effective_protocol(progress.get("plan") or {})
        work_items = {item["work_item_id"]: item for item in effective.get("work_items", [])}
        cases = {item["case_id"]: item for item in effective.get("cases", [])}
        sources = {item["data_source_id"]: item for item in effective.get("data_sources", [])}
        declared_sources = _declared_sources_enabled(self.run_dir(record.project_id, record.run_id))
        sealed_rows = {}
        def normalized(row):
            return {key: value for key, value in row.items() if key not in ("eligibility", "invalidation_reason")}

        def observation(row, attempt_id):
            return (isinstance(row, dict) and row.get("attempt_id") == attempt_id
                    and all(isinstance(row.get(key), str) and row[key] for key in ("case_id", "replicate_id"))
                    and row.get("status") in {"completed", "failed"} and isinstance(row.get("metrics"), dict))

        # Read every completed attempt, including attempts omitted entirely
        # from the current report. Invalidation preserves the original values.
        boundary = (self.run_dir(record.project_id, record.run_id) / "p4-execution" / "batches").resolve()
        for attempt_id, attempt in by_attempt.items():
            for source in attempt.get("source_files", []):
                path = Path(source.get("snapshot_path", ""))
                try:
                    intact = (path.resolve().is_relative_to(boundary) and path.is_file()
                              and sha256_file(path) == source.get("sha256"))
                except OSError:
                    intact = False
                if not intact:
                    problem("source_changed", "A managed attempt's declared code or configuration snapshot is missing or changed.", "p4.protocol")
            if attempt.get("status") != "completed":
                continue
            sealed_rows[attempt_id] = []
            for artifact in attempt.get("artifacts", []):
                path = Path(artifact.get("path", ""))
                try:
                    intact = (path.resolve().is_relative_to(boundary) and path.is_file()
                              and sha256_file(path) == artifact.get("sha256"))
                except OSError:
                    intact = False
                if not intact:
                    problem("artifact_changed", "A managed batch artifact is missing or changed.", "p4.metrics_long")
                    continue
                try:
                    if path.suffix.lower() == ".jsonl":
                        values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                    elif path.suffix.lower() == ".json":
                        values = read_json(path)
                        if observation(values, attempt_id):
                            values = [values]
                        elif isinstance(values, dict):
                            values = values.get("rows", [])
                    else:
                        continue
                    if isinstance(values, list):
                        sealed_rows[attempt_id].extend(normalized(item) for item in values if observation(item, attempt_id))
                except (OSError, ValueError):
                    continue

        reported = {}
        for index, row in enumerate(documents.get("p4.metrics_long", [])):
            if row.get("status") == "not_run":
                continue
            attempt_id = row.get("attempt_id")
            key = (attempt_id, row.get("case_id"), row.get("replicate_id"), row.get("status"))
            reported.setdefault(key, []).append(normalized(row))
            attempt = by_attempt.get(attempt_id)
            retained_failure = (attempt and attempt.get("status") == "failed"
                                and row.get("eligibility") == "invalidated"
                                and isinstance(row.get("invalidation_reason"), str)
                                and bool(row["invalidation_reason"].strip()))
            if (not attempt or attempt.get("status") != "completed" and not retained_failure
                    or row.get("batch_id") != attempt.get("batch_id")
                    or row.get("plan_revision_id") != attempt.get("plan_revision_id")):
                problem("unverified_attempt", "An eligible observed row must name its completed managed batch, attempt and plan revision; "
                        "failed-batch history requires explicit invalidation and its original execution identity.",
                        "p4.metrics_long", f"/{index}")
                continue
            work_item = work_items.get(attempt.get("work_item_id"), {})
            if row.get("case_id") not in work_item.get("case_ids", []):
                problem("unscheduled_case", "The observed case was not authorized for its managed batch's work item.",
                        "p4.metrics_long", f"/{index}")
            if declared_sources and row.get("eligibility") != "invalidated":
                required_inputs = {input_id for source_id in cases.get(row.get("case_id"), {}).get("data_source_ids", [])
                                   for input_id in sources.get(source_id, {}).get("input_ids", [])}
                if not required_inputs <= set(attempt.get("input_ids", [])):
                    problem("unavailable_case_input", "An eligible observation requires its case's frozen data inputs to have been available to the producing managed attempt.",
                            "p4.metrics_long", f"/{index}")
            # Failed batches have no accepted artifact seal. Keep their
            # explicitly excluded history without promoting it to evidence.
            if not retained_failure and normalized(row) not in sealed_rows[attempt_id]:
                problem("unsealed_observation", "The reported row differs from the managed batch's sealed numerical output.",
                        "p4.metrics_long", f"/{index}")
        if "p4.metrics_long" in documents:
            for attempt_id, rows in sealed_rows.items():
                missing = [row for row in rows if row not in reported.get(
                    (attempt_id, row["case_id"], row["replicate_id"], row["status"]), [])]
                if missing:
                    examples = ", ".join(f"{row['case_id']}/{row['replicate_id']}" for row in missing[:3])
                    problem("omitted_observation", f"Retain all sealed observations from completed attempt {attempt_id}; "
                            f"{len(missing)} unchanged rows are missing ({examples}). Mark invalid results with eligibility "
                            "invalidated and an invalidation_reason instead of deleting or rewriting them.", "p4.metrics_long")
        sealed_exhibits = {artifact.get("sha256") for attempt in by_attempt.values() if attempt.get("status") == "completed"
                           for artifact in attempt.get("artifacts", [])}
        for index, exhibit in enumerate(documents.get("p4.exhibits", [])):
            if exhibit.get("artifact_sha256") not in sealed_exhibits:
                problem("unsealed_exhibit", "A result figure or table must be produced and sealed by a completed managed batch; include it in result_paths.",
                        "p4.exhibits", f"/{index}")
        return findings

    def _record_p4_usage(self, record, stage, result):
        usage = result.usage
        for key in ("input_tokens", "output_tokens"):
            delta = usage.get("turn_" + key, usage.get(key, 0)) or 0
            record.usage[key] = record.usage.get(key, 0) + delta
        if usage.get("model_context_window"):
            record.usage["model_context_window"] = max(record.usage.get("model_context_window", 0), usage["model_context_window"])
        self._save_run(record)

    async def _settle_p4_wait(self, record):
        from .runs import RunError
        record = self.load_run(record.project_id, record.run_id)
        if record.run_id in self._cancellation_failures:
            raise RunError(self._cancellation_failures.pop(record.run_id))
        if self._active_turns.get(record.run_id):
            raise RunError("Cannot settle the pause until the active member turn has stopped")
        progress = self._p4_controller(record).snapshot()
        if not progress.get("pause_request"):
            raise RunError("A waiting run needs a saved decision request")
        record.stage_states[progress["resume_stage"]] = "awaiting_user"
        record.terminal_reason = None
        self._save_run(record)
        return await self._transition(record, RunState.AWAITING_USER, "Waiting for your direction. No experimental or model work is running.")

    async def _execute_p4_stage(self, record, stage) -> StageResult:
        role = stage.roles[0]
        directory = self.run_dir(record.project_id, record.run_id)
        controller = self._p4_controller(record, stage, role)
        record.stage_states[stage.stage_id] = "running"
        self._save_run(record)
        self._event(record, "stage.running", f"Stage {stage.stage_id} running.")
        contract = read_json(directory / "contracts" / "contracts" / "phases" / "P4.json") or {}
        if ("native_tool_preflight_v1" in contract.get("capabilities", [])
                and callable(getattr(self.bridge, "check_native_tools", None))):
            try:
                # The native report does not bind the current profile. Check
                # again on resume, once outside the ordinary checkpoint loop.
                prepared = await self._drive_member_turn(record, stage, role, directory, prepare_only=True)
                record = self.load_run(record.project_id, record.run_id)
                if not prepared.succeeded:
                    raise RuntimeError(prepared.diagnostic)
            except Exception as error:
                record = self.load_run(record.project_id, record.run_id)
                record.stage_states[stage.stage_id] = "failed"
                record.findings_history.append([asdict(Finding("runtime.native_tools_unavailable", str(error), stage.stage_id, ""))])
                self._save_run(record)
                return StageResult(stage.stage_id, False, diagnostic=str(error))
            if controller.snapshot().get("pause_request"):
                await self._settle_p4_wait(record)
                return StageResult(stage.stage_id, False, diagnostic="Waiting for researcher direction")
        idle_turns = 0
        # Each ordinary turn remains separately attributed and billed. The
        # controller, never the model's prose, decides whether a batch runs.
        for _ in range(40):
            before = _work_progress(controller.snapshot())
            result = await self._drive_member_turn(record, stage, role, directory)
            record = self.load_run(record.project_id, record.run_id)
            self._record_p4_usage(record, stage, result)
            progress = controller.snapshot()
            if progress.get("pause_request"):
                await self._settle_p4_wait(record)
                return StageResult(stage.stage_id, False, diagnostic="Waiting for researcher direction")
            if not result.succeeded:
                return result
            feedback = read_json(directory / "p4-control-feedback.json") or {}
            if feedback.get("execution_state") == "unknown":
                pending = progress.get("pending_batch") or {}
                controller.request({"operation": "request_decision",
                    "question": "Check the saved experiment state before continuing.",
                    "reason": feedback.get("error") or "The last operation's outcome could not be confirmed. Saved work must be inspected before another request.",
                    "evidence_refs": [{"description": "The saved tool result needs inspection before another operation.",
                                       "control_feedback": feedback,
                                       **{key: pending[key] for key in ("attempt_id", "batch_id") if key in pending}}],
                    "options": [{"label": "Inspect saved work", "consequence": "Confirm the pending or completed operation before authorizing continuation."}]})
                await self._settle_p4_wait(record)
                return StageResult(stage.stage_id, False, diagnostic="Waiting for researcher direction")
            if progress.get("pending_batch"):
                await controller.execute_pending(heartbeat=lambda message: self._event(
                    record, "experiment.progress", message, stage=stage.stage_id, role=role.value))
                progress = controller.snapshot()
                if progress.get("pause_request"):
                    await self._settle_p4_wait(record)
                    return StageResult(stage.stage_id, False, diagnostic="Waiting for researcher direction")
                idle_turns = 0
                continue
            if role != MemberRole.DATA_ANALYST or progress.get("completed"):
                ok, diagnostic = await self._check_stage_delivery(record, stage)
                record = self.load_run(record.project_id, record.run_id)
                # A review or mechanical repair can discover a severe issue.
                if controller.snapshot().get("pause_request"):
                    await self._settle_p4_wait(record)
                    return StageResult(stage.stage_id, False, diagnostic="Waiting for researcher direction")
                record.stage_states[stage.stage_id] = "succeeded" if ok else "failed"
                self._save_run(record)
                self._event(record, "stage.finished", f"Stage {stage.stage_id} {'succeeded' if ok else 'failed'}.")
                return StageResult(stage.stage_id, ok, diagnostic=diagnostic)
            if _work_progress(progress) == before:
                idle_turns += 1
                if idle_turns <= 2:
                    controller.request({"operation": "checkpoint", "checkpoint": {
                        "host_feedback": True,
                        "summary": "No new plan or experiment was accepted in this turn. "
                                   "A checkpoint alone does not advance the evaluation. "
                                   + (feedback.get("hint") or "Inspect the saved plan and latest tool response, then submit a valid next action or request researcher direction."),
                        "latest_control_feedback": feedback}})
                    continue
                controller.request({"operation": "request_decision",
                    "question": "Continue preparing this evaluation or finish with its available evidence?",
                    "reason": "The analyst made no further progress after two feedback turns. " + feedback.get("error", "No further computation was dispatched."),
                    "options": [{"label": "Continue", "consequence": "Provide direction for another bounded attempt."},
                                {"label": "Finish", "consequence": "Review available evidence and explicitly report incomplete work."}]})
                await self._settle_p4_wait(record)
                return StageResult(stage.stage_id, False, diagnostic="Waiting for researcher direction")
            idle_turns = 0
        controller.request({"operation": "request_decision", "question": "Continue planning this evaluation or finish with the available evidence?",
                            "reason": "Forty planning and experiment turns completed without finishing the stage.",
                            "options": [{"label": "Continue", "consequence": "Authorize another bounded sequence of checkpoints."},
                                        {"label": "Finish", "consequence": "Review the available evidence and unanswered questions."}]})
        await self._settle_p4_wait(record)
        return StageResult(stage.stage_id, False, diagnostic="Waiting for researcher direction")

    async def pause_p4(self, project_id, run_id):
        from .runs import RunError
        record = self.load_run(project_id, run_id)
        if not self._progressive_p4(record):
            raise RunError("This frozen run does not support progressive evaluation")
        if record.state == RunState.AWAITING_USER:
            return record
        if record.state in TERMINAL_STATES:
            raise RunError(f"run is already {record.state}")
        controller = self._p4_controller(record)
        if not controller.snapshot().get("pause_request"):
            active_batch = controller.snapshot().get("pending_batch") or {}
            controller.request({"operation": "request_decision", "question": "How would you like this evaluation to continue?",
                                "reason": "You requested a pause. Completed work is retained and unfinished work will need your direction.",
                                "evidence_refs": [{"attempt_id": active_batch["attempt_id"], "batch_id": active_batch["batch_id"]}] if active_batch else [],
                                "options": [{"label": "Continue", "consequence": "Continue within the frozen method and remaining budget."},
                                            {"label": "Finish", "consequence": "Review and summarize only the available evidence."}]})
        record = await self._transition(record, RunState.STOPPING, "Stopping the owned experiment and member turn before waiting.")
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        current = self.load_run(project_id, run_id)
        if current.state == RunState.STOPPING:
            return await self._settle_p4_wait(current)
        return current

    async def save_p4_answer(self, project_id, run_id, *, request_id, expected_revision, note, expected_answer_revision=None,
                             context_refs=None, scope_change=False, save_to_context=False, origin="researcher_reported",
                             context_expected_revision=None):
        from .runs import RunError, _now
        async with self._lock(f"continue:{run_id}"):
            record = self.load_run(project_id, run_id)
            if not self._progressive_p4(record):
                raise RunError("This run does not support saved evaluation answers")
            progress = self._p4_controller(record).snapshot()
            requests = [progress.get("pause_request"), *(row.get("request") for row in progress.get("answer_revisions", []))]
            request = next((item for item in requests if item and item.get("request_id") == request_id and item.get("revision") == expected_revision), None)
            if not request:
                raise RunError("The evaluation question has changed; reopen it before saving")
            path = self.run_dir(project_id, run_id) / "p4-decision-answers.json"
            saved = read_json(path) or []
            previous = next((item for item in reversed(saved) if item["request_id"] == request_id and item["request_revision"] == expected_revision), {})
            if expected_answer_revision is not None and expected_answer_revision != previous.get("revision", 0):
                raise RunError("Your saved response changed; reload it before saving this edit")
            dialogue = self._dialogue_p4(record)
            if dialogue and (not isinstance(note, str) or not note.strip()):
                raise RunError("Record your response before saving")
            if dialogue and origin not in ("researcher_reported", "unknown"):
                raise RunError("A direct researcher response records a report or uncertainty")
            unchanged = previous.get("note") == note
            if dialogue:
                unchanged = unchanged and (previous.get("save_to_context", False), previous.get("scope_change", False)) == (save_to_context, scope_change)
                unchanged = unchanged and previous.get("origin", "researcher_reported") == origin
                unchanged = unchanged and all(ref in previous.get("context_refs", []) for ref in context_refs or [])
            if unchanged:
                return next(item for item in self.p4_progress(record)["saved_answers"] if item["revision"] == previous["revision"])
            answer = {"request_id": request_id, "request_revision": expected_revision, "revision": len(saved) + 1,
                      "note": note, "saved_at": _now(), "request": request}
            if dialogue:
                from .phase_interactions import pause_target, save_scoped_answer
                from .problem_context import answer_reference
                basis = read_json(self.run_dir(project_id, run_id) / "basis.json") or {}
                scope = request.get("scope") or {"kind": "model", "branch": record.branch_id,
                                                 "model_ref": (basis.get("method") or {}).get("identity") or {}}
                question = {**request, "attention_id": "pause." + run_id + "." + request_id,
                            "kind": "researcher_decision", "phase": "P4", "branch": record.branch_id,
                            "responsible_role": request.get("member") or "data_analyst",
                            "scope": scope, "audience": [request.get("member") or "data_analyst"],
                            "explanation_target": pause_target(record, request)}
                try:
                    shared = save_scoped_answer(self.project_dir(project_id), question, note,
                        expected_revision=(previous.get("answer_ref") or {}).get("answer_revision", 0),
                        save_to_context=save_to_context, origin=origin, context_expected_revision=context_expected_revision)
                except ValueError as exc:
                    raise RunError(str(exc)) from exc
                refs = list(context_refs or [])
                if shared.get("context_ref"):
                    ref = {key: shared["context_ref"][key] for key in ("item_id", "revision")}
                    if ref not in refs:
                        refs.append(ref)
                answer.update(answer_ref=answer_reference(shared), context_refs=refs, scope_change=scope_change,
                              save_to_context=save_to_context, origin=origin)
                if shared.get("topic"):
                    answer["topic"] = shared["topic"]
            write_json_atomic(path, [*saved, answer])
            return {**answer, "applied_to": []}

    async def continue_p4(self, project_id, run_id, *, request_id, expected_revision, answer="", action="continue",
                          context_choice=None, idempotency_key=None, additional_budget_seconds=0, answer_revision=None):
        from .runs import RunError, _now
        if self.shutting_down:
            raise RunError("The local service is shutting down")
        async with self._lock(f"continue:{run_id}"):
            record = self.load_run(project_id, run_id)
            if not self._progressive_p4(record):
                raise RunError("This frozen run does not support progressive evaluation")
            accepted = self.run_dir(project_id, run_id) / "p4-continuations.json"
            controller = self._p4_controller(record)
            # The controller atomically consumes the pending question together
            # with its immutable answer and budget. This is the command's sole
            # authority; the convenience audit file is only a projection.
            revisions = [item["answer_revision"] for item in controller.snapshot().get("answer_revisions", [])]
            chosen = None
            if answer_revision is not None:
                saved = read_json(self.run_dir(project_id, run_id) / "p4-decision-answers.json") or []
                chosen = next((item for item in saved if item["revision"] == answer_revision
                               and item["request_id"] == request_id and item["request_revision"] == expected_revision), None)
                if not chosen:
                    raise RunError("The selected saved response does not belong to this evaluation question")
                if answer and answer != chosen["note"]:
                    raise RunError("The supplied answer differs from the chosen saved response")
                answer = chosen["note"]
            payload = {"request_id": request_id, "expected_revision": expected_revision, "answer": answer,
                       "action": action, "context_choice": context_choice, "additional_budget_seconds": additional_budget_seconds}
            if answer_revision is not None:
                payload["saved_answer_revision"] = answer_revision
            previous = next((r for r in revisions if idempotency_key and r.get("idempotency_key") == idempotency_key), None)
            if previous:
                if previous["payload"] != payload:
                    raise RunError("This continuation key already identifies different instructions")
                return record
            if record.state != RunState.AWAITING_USER:
                raise RunError("The run is not waiting for a continuation")
            if action not in ("continue", "finish") or (action == "continue" and not answer.strip()):
                raise RunError("Supply instructions for continuing, or explicitly finish with the available evidence")
            if action == "finish" and not controller.snapshot().get("plan"):
                raise RunError("No valid evaluation plan has been saved. Continue to resolve the open question, or end this run with its notes preserved.")
            if not math.isfinite(additional_budget_seconds) or additional_budget_seconds < 0:
                raise RunError("Additional experiment time must be a nonnegative number")
            pending = controller.snapshot().get("pause_request") or {}
            if pending.get("request_id") != request_id or pending.get("revision") != expected_revision:
                raise RunError("The pending question has changed; reopen it before continuing")
            self._assert_phase_available(project_id, record.phase, record.branch_id, excluding=run_id)
            self._assert_publication_current(record)
            accepted_items = []
            answer_ref = None
            if self._dialogue_p4(record):
                from .researcher_pause import adopted_context_items
                if pending.get("scope_change") or (chosen or {}).get("scope_change"):
                    raise RunError("This response changes the authorized scientific scope; prepare a new linked run")
                current = self.compute_basis(record.project_id, record.phase, record.branch_id, record.mode)
                if chosen:
                    try:
                        frozen = read_json(self.run_dir(project_id, run_id) / "basis.json") or {}
                        accepted_items = adopted_context_items(chosen, current, record.branch_id, frozen.get("method"))
                    except ValueError as exc:
                        raise RunError(str(exc)) from exc
                    answer_ref = chosen.get("answer_ref")
                changes = self._p4_context_changes(record, accepted_items, [answer_ref] if answer_ref else [], current)
                if any(row.get("kind") == "model_changed" for row in changes):
                    raise RunError("The model changed; prepare a new linked run")
            else:
                changes = self._p4_context_changes(record)
            if changes and context_choice != "frozen":
                raise RunError("Research context changed. Explicitly choose the displayed frozen basis or start a new linked run")
            revision = {**payload, "revision": len(revisions) + 1, "accepted_at": _now(),
                        "idempotency_key": idempotency_key, "context_changes": changes, "payload": payload}
            if self._dialogue_p4(record):
                revision.update(accepted_context_items=accepted_items, answer_ref=answer_ref,
                                conditional_scope=pending.get("conditional_scope"))
            controller.resume(answer, revision, additional_budget_seconds=additional_budget_seconds)
            write_json_atomic(accepted, [*revisions, revision])
            record.terminal_reason = None
            record.state = RunState.REQUESTED
            record.updated_at = _now()
            self._save_run(record)
            self._event(record, "run.continued", "Researcher explicitly authorized this continuation.", answer_revision=revision["revision"], action=action)
            task = asyncio.create_task(self._drive(record, self._stages(record)))
            self._tasks[run_id] = task
            self._task_projects[run_id] = project_id
            return record
