"""Run engine (design/02).

Drives a phase run: stage plan from the pinned phase contract, turns in
member threads, immediate artifact checks, bounded mechanical repairs and one explicit correction,
cancellation, atomic publication with journal + receipt.

Concurrency uses process-local locks. Publication checks its authorized current
package before replacing the phase pointer; cross-process coordination is not
implemented.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .bridge import CodexBridge
from .catalog import Catalog, CatalogError
from .domain import (
    BRANCH_PHASE_MEMBER,
    PHASES,
    TERMINAL_STATES,
    Finding,
    MemberConfig,
    MemberRole,
    RunRecord,
    RunState,
    StageResult,
    StageSpec,
    ThreadKey,
    new_id,
)
from .members import codex_home
from .project_brief import project_instructions
from .p4_lifecycle import P4LifecycleMixin, default_experiment_budget
from .problem_context import (supports_problem_context, frozen_problem_context,
                              applicable_researcher_answers, resolve_project_context_target, role_effective_account)
from .technical_reports import (technical_report_enabled, report_assembly_readiness,
                                technical_report_scope_brief, derive_report_completion)
from .researcher_pause import ResearcherPauseStore, eligible_stage, researcher_pause_target
from .p5_review_packet import (frozen_review_packet_enabled, prepare_review_packet,
                               review_packet_brief, manuscript_scope_brief,
                               validate_review_packet_outputs, validate_manuscript_scope)
from .records import ArtifactError, current_records, current_package_token, generation_path, read_generation, publish_package, source_artifact_path
from .threads import ThreadRegistry
from .storage import (
    append_jsonl,
    read_json,
    read_jsonl,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


#: Role aliases used to infer per-member output ownership in parallel
#: stages (the phase contract declares stage-level writes only).
ROLE_OUTPUT_ALIASES = {
    MemberRole.RESEARCH_LEAD: ("lead",),
    MemberRole.THEORIST: ("theory", "theorist"),
    MemberRole.DATA_ANALYST: ("empirical", "analyst", "data"),
    MemberRole.OUTSIDE_REVIEWER: ("review",),
}


def owned_writes(stage: StageSpec, role: MemberRole) -> tuple[str, ...]:
    """Which of the stage's writes this member owns. Single-role stages:
    everything. Parallel stages: outputs whose name carries a role alias;
    if nothing matches, the member owns nothing (and is told so)."""
    if len(stage.roles) == 1:
        return stage.writes
    aliases = ROLE_OUTPUT_ALIASES.get(role, ())
    return tuple(
        w for w in stage.writes
        if any(alias in w.split(".", 1)[-1] for alias in aliases)
    )


class RunError(RuntimeError):
    pass


#: Whitelist for identifiers that become path segments (belt-and-braces —
#: the HTTP layer already rejects encoded slashes).
import re as _re

_IDENT_RE = _re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class RunEngine(P4LifecycleMixin):
    _MAX_MECHANICAL_REPAIRS = 2

    def __init__(self, data_root: Path, bridge: CodexBridge, account_service=None) -> None:
        self.data_root = data_root
        self.bridge = bridge
        self.account_service = account_service
        self._locks: dict[str, asyncio.Lock] = {}
        self._reg_locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._task_projects: dict[str, str] = {}
        self.shutting_down = False
        self._shutdown_lock = asyncio.Lock()
        self._shutdown_complete = False
        self._thread_locks: dict[str, asyncio.Lock] = {}
        self._active_turns: dict[str, set[str]] = {}
        self._cancellation_failures: dict[str, str] = {}
        self._mechanical_repairs: dict[tuple[str, str, str], dict] = {}

    # ------------------------------------------------------------------ #
    # Paths
    # ------------------------------------------------------------------ #

    def project_dir(self, project_id: str) -> Path:
        if not _IDENT_RE.fullmatch(project_id):
            raise RunError("Invalid project identifier")
        return self.data_root / "projects" / project_id

    def run_dir(self, project_id: str, run_id: str) -> Path:
        if not _IDENT_RE.fullmatch(run_id):
            raise RunError("Invalid run identifier")
        return self.project_dir(project_id) / "runs" / run_id

    def _member_home(self, record: RunRecord, role: MemberRole) -> Path:
        if record.intent == "assessment" or role == MemberRole.OUTSIDE_REVIEWER:
            return self.run_dir(record.project_id, record.run_id) / "isolated" / role.value / "codex-home"
        return codex_home(self.project_dir(record.project_id), role)

    def workspace_root(self, member_home: Path) -> Path:
        """Keep executable working directories short without moving records or auth."""
        return (self.data_root / "work" / sha256_bytes(str(member_home.resolve()).encode())[:24]).resolve()

    def member_workspace(self, record: RunRecord, stage_id: str, role: MemberRole) -> Path:
        if not _IDENT_RE.fullmatch(stage_id):
            raise RunError("Invalid stage identifier")
        return self.workspace_root(self._member_home(record, role)) / sha256_bytes(record.run_id.encode())[:24] / stage_id

    def _apply_saved_provider_account(self, provider_config, project_dir: Path, role: MemberRole):
        if provider_config.governs(role.value) and provider_config.settings_for(role.value)["provider"] == "openai":
            if self.account_service is None:
                from .accounts import AccountService
                self.account_service = AccountService(self.data_root)
            # Apply only an already authorized connection, filling empty homes.
            # No login and no replacement of existing credentials occurs here.
            self.account_service.provision_project(project_dir)

    # ------------------------------------------------------------------ #
    # Run record IO + transitions (CAS-shaped: lock + read-modify-write)
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Locks
    # ------------------------------------------------------------------ #

    def _lock(self, run_id: str) -> asyncio.Lock:
        return self._locks.setdefault(run_id, asyncio.Lock())

    def _registry_lock(self, project_id: str, branch_id: str) -> asyncio.Lock:
        """Serializes threads.json mutations per branch (parallel stage
        members race otherwise — verified lost-update 10/10 pre-fix)."""
        k = (project_id, branch_id)
        return self._reg_locks.setdefault(k, asyncio.Lock())

    def _registry(self, project_id: str, branch_id: str) -> ThreadRegistry:
        return ThreadRegistry(self.project_dir(project_id) / "branches" / branch_id)

    def load_run(self, project_id: str, run_id: str) -> RunRecord:
        doc = read_json(self.run_dir(project_id, run_id) / "run.json")
        if doc is None:
            raise RunError(f"unknown run {run_id}")
        doc = dict(doc)
        doc["state"] = RunState(doc["state"])
        doc["thread_ids"] = dict(doc.get("thread_ids") or {})
        return RunRecord(**doc)

    def _save_run(self, record: RunRecord) -> None:
        doc = asdict(record)
        doc["state"] = record.state.value
        write_json_atomic(self.run_dir(record.project_id, record.run_id) / "run.json", doc)

    def _event(self, record: RunRecord, event_type: str, message: str, **extra) -> None:
        append_jsonl(
            self.run_dir(record.project_id, record.run_id) / "events.jsonl",
            {"at": _now(), "type": event_type, "message": message, **extra},
        )

    def researcher_pause(self, record: RunRecord) -> dict | None:
        store = ResearcherPauseStore(self.run_dir(record.project_id, record.run_id))
        state = store.snapshot()
        request = state.get("pending_request")
        if request:
            state["pending_request"] = {**request, "explanation_target": researcher_pause_target(record, request)}
            current = self.compute_basis(record.project_id, record.phase, record.branch_id, record.mode)
            from .researcher_pause import continuation_context_changes, adopted_context_items
            basis = read_json(store.run_dir / "basis.json") or {}
            latest = next((row for row in reversed(state["saved_answers"])
                           if row["request_id"] == request["request_id"] and row["request_revision"] == request["revision"]), {})
            try:
                accepted = adopted_context_items(latest, current, record.branch_id, basis.get("method"))
            except ValueError:
                accepted = []
            state["context_changes"] = continuation_context_changes(
                basis, current, [*store.accepted_context_items(record), *accepted])
            if request.get("scope_change") or latest.get("scope_change") or any(
                    row["kind"] == "model_changed" for row in state["context_changes"]):
                state["continuation_blocked"] = "The model or authorized scientific scope changed. Prepare a new linked request."
        return state if request or state.get("continuations") else None

    def _authored_researcher_question(self, record, stage, workspace):
        path = Path(workspace) / "researcher-question.json"
        if not path.is_file():
            return None
        if not supports_problem_context(self._catalog(record)) or not eligible_stage(record, stage):
            raise RunError("This stage submits conditional work and an attention question; it cannot pause for dialogue")
        authored = read_json(path)
        from .researcher_pause import validate_authored_question
        validate_authored_question(record, stage, authored,
            read_json(self.run_dir(record.project_id, record.run_id) / "basis.json") or {})
        return authored

    async def save_researcher_answer(self, project_id, run_id, *, request_id, expected_revision, note,
                                    expected_answer_revision=None, **extra):
        async with self._lock(run_id):
            record = self.load_run(project_id, run_id)
            store = ResearcherPauseStore(self.run_dir(project_id, run_id))
            request = store.snapshot().get("pending_request")
            if not request or record.state != RunState.AWAITING_USER:
                raise RunError("This run is not waiting for a researcher response")
            if (request["request_id"], request["revision"]) != (request_id, expected_revision):
                raise RunError("The researcher question changed; reopen its exact revision")
            previous = next((row for row in reversed(store.snapshot()["saved_answers"])
                             if row["request_id"] == request_id and row["request_revision"] == expected_revision), {})
            if expected_answer_revision is not None and previous.get("revision", 0) != expected_answer_revision:
                raise RunError("Your saved response changed; reload it before saving")
            try:
                from .phase_interactions import save_scoped_answer
                from .problem_context import answer_reference
                question = store.resolve_target(record, researcher_pause_target(record, request))
                question.update(attention_id=request_id, audience=[request["member"]], question_version_id=str(expected_revision))
                shared = save_scoped_answer(self.project_dir(project_id), question, note,
                    expected_revision=(previous.get("answer_ref") or {}).get("answer_revision", 0),
                    save_to_context=extra.get("save_to_context", False),
                    origin=extra.get("origin", "researcher_reported"),
                    context_expected_revision=extra.get("context_expected_revision"))
                refs = list(extra.get("context_refs", []))
                if shared.get("context_ref"):
                    refs.append(shared["context_ref"])
                answer = store.save_answer(request_id, expected_revision, note,
                    expected_answer_revision=expected_answer_revision, answer_ref=answer_reference(shared),
                    context_refs=refs, scope_change=extra.get("scope_change", False),
                    origin=shared["origin"], topic=shared.get("topic"))
                return {"answer": answer, "researcher_pause": self.researcher_pause(record)}
            except ValueError as exc:
                raise RunError(str(exc)) from exc

    async def continue_researcher_work(self, project_id, run_id, *, request_id, expected_revision,
                                      answer_revision=None, answer="", action="continue", context_choice=None,
                                      idempotency_key=None, **extra):
        if action != "continue":
            raise RunError("Prepare a new linked run when the scientific target or scope changes")
        # Retry the accepted command even if resumed work asks a new question.
        prior_store = ResearcherPauseStore(self.run_dir(project_id, run_id))
        prior = next((row for row in prior_store.snapshot()["continuations"]
                      if idempotency_key and row.get("idempotency_key") == idempotency_key), None)
        if prior:
            same_response = (prior["answer"].get("note") == answer if answer.strip()
                             else prior["payload"].get("answer_revision") == answer_revision)
            if (same_response and prior["payload"].get("request_id") == request_id
                    and prior["payload"].get("request_revision") == expected_revision
                    and prior["payload"].get("context_choice") == context_choice):
                return self.load_run(project_id, run_id)
            raise RunError("This continuation key already names different instructions")
        if answer.strip():
            saved = await self.save_researcher_answer(project_id, run_id, request_id=request_id,
                expected_revision=expected_revision, note=answer, **extra)
            answer_revision = saved["answer"]["revision"]
        async with self._lock(run_id):
            record = self.load_run(project_id, run_id)
            store = ResearcherPauseStore(self.run_dir(project_id, run_id))
            if record.state != RunState.AWAITING_USER:
                duplicate = next((row for row in store.snapshot()["continuations"]
                                  if idempotency_key and row.get("idempotency_key") == idempotency_key), None)
                if duplicate and all(duplicate["payload"].get(key) == value for key, value in {
                    "request_id": request_id, "request_revision": expected_revision,
                    "answer_revision": answer_revision, "context_choice": context_choice}.items()):
                    return record
                raise RunError("This run is no longer waiting")
            self._assert_phase_available(project_id, record.phase, record.branch_id, excluding=run_id)
            self._assert_publication_current(record)
            try:
                continuation = store.continue_work(request_id, expected_revision, answer_revision,
                    current_basis=self.compute_basis(project_id, record.phase, record.branch_id, record.mode),
                    context_choice=context_choice, idempotency_key=idempotency_key)
            except ValueError as exc:
                raise RunError(str(exc)) from exc
            stage_id = continuation["resume_stage"]
            workspace = self.member_workspace(record, stage_id, MemberRole(continuation["resume_member"]))
            question_file = workspace / "researcher-question.json"
            if question_file.is_file():
                question_file.rename(workspace / ("researcher-question.accepted." + str(continuation["revision"]) + ".json"))
            record.stage_states[stage_id] = "pending"
            record.terminal_reason = None
            record.state = RunState.REQUESTED
            record.updated_at = _now()
            self._save_run(record)
            self._event(record, "run.continued", "Researcher continuation accepted.")
            task = asyncio.create_task(self._drive(record, self._stages(record)))
            self._tasks[run_id] = task
            self._task_projects[run_id] = project_id
            return record

    async def _transition(self, record: RunRecord, to: RunState, message: str) -> RunRecord:
        async with self._lock(record.run_id):
            current = self.load_run(record.project_id, record.run_id)
            if current.state in TERMINAL_STATES:
                raise RunError(f"run is already {current.state}")
            current.state = to
            if to in (RunState.CANCELLED, RunState.FAILED):
                for stage_id, status in current.stage_states.items():
                    if status in ("running", "correcting"):
                        current.stage_states[stage_id] = to.value
            current.updated_at = _now()
            self._save_run(current)
            self._event(current, f"run.{to}", message)
            return current

    # ------------------------------------------------------------------ #
    # Stage plan from the pinned phase contract
    # ------------------------------------------------------------------ #

    def stage_plan(self, project_id: str, phase: str, mode: str) -> list[StageSpec]:
        if mode == "p3.assessment" and phase == "P3":
            return [StageSpec(
                stage_id="p3.assessment", sequence=1, execution="serial",
                roles=(MemberRole.THEORIST,), writes=("p3.assessment",),
                objective="Assess the exact selected component. Explain what was checked, evidence, limitations, and options. Do not repair or change the scientific work.",
            )]
        contract_path = (
            self.project_dir(project_id) / "contracts" / "contracts" / "phases" / f"{phase}.json"
        )
        contract = read_json(contract_path)
        if contract is None:
            raise RunError(f"phase contract {phase} not found under the pinned catalog")
        stages = []
        for stage in contract.get("role_stages", []):
            modes = stage.get("applicable_modes") or []
            if modes and mode not in modes:
                continue
            stages.append(
                StageSpec(
                    stage_id=stage["stage_id"],
                    sequence=stage["sequence"],
                    execution=stage["execution"],
                    roles=tuple(MemberRole(r) for r in stage["roles"]),
                    writes=tuple(stage.get("writes", ())),
                    objective=stage.get("objective", ""),
                    isolation_rule=stage.get("isolation_rule", ""),
                    artifact_contracts=stage.get("artifact_contracts", {}),
                    reads=tuple(stage.get("reads", ())),
                    role_reads={r["role"]: tuple(r.get("input_ids", ())) for r in stage.get("role_reads", [])},
                    role_objectives=dict(stage.get("role_objectives", {})),
                )
            )
        if not stages:
            raise RunError(f"phase {phase} has no stages applicable to mode {mode}")
        return sorted(stages, key=lambda s: s.sequence)

    def _stages(self, record: RunRecord) -> list[StageSpec]:
        saved = read_json(self.run_dir(record.project_id, record.run_id) / "stage-plan.json")
        if saved is None:
            return self.stage_plan(record.project_id, record.phase, record.mode)
        return [StageSpec(**{**s, "roles": tuple(MemberRole(r) for r in s["roles"]),
                             "writes": tuple(s["writes"]), "reads": tuple(s.get("reads", ())),
                             "role_reads": {role: tuple(reads) for role, reads in s.get("role_reads", {}).items()}})
                for s in saved]

    def _catalog(self, record: RunRecord) -> Catalog:
        frozen = self.run_dir(record.project_id, record.run_id) / "contracts"
        catalog = Catalog(frozen if frozen.is_dir() else self.project_dir(record.project_id) / "contracts")
        basis = read_json(self.run_dir(record.project_id, record.run_id) / "basis.json") or {}
        if frozen.is_dir() and basis.get("catalog_sha256") and catalog.snapshot_sha256 != basis["catalog_sha256"]:
            raise RunError("The run's frozen catalog bytes changed")
        return catalog

    # ------------------------------------------------------------------ #
    # Readiness gates (design/02 §7)
    # ------------------------------------------------------------------ #

    def check_readiness(self, project_id: str, phase: str, branch_id: str, mode: str | None = None) -> list[str]:
        """Check scientific prerequisites, not the previous numbered phase."""
        project_dir = self.project_dir(project_id)
        reasons: list[str] = []
        from .providers import ProviderConfigError, load_provider_config
        try:
            load_provider_config(self.data_root).require_ready()
        except ProviderConfigError as exc:
            reasons.append(str(exc))
        if not _IDENT_RE.fullmatch(branch_id):
            return ["Invalid branch identifier"]
        if phase not in PHASES:
            return [f"Unknown phase {phase}"]
        if phase in ("P1", "P2") and branch_id != "trunk":
            reasons.append(f"{phase} runs on the project trunk")
        required = {"P1": (), "P2": ("P1",), "P3": ("P1", "P2"),
                    "P4": ("P1", "P2"), "P5": ("P1", "P2", "P3", "P4")}[phase]
        try:
            catalog = Catalog(project_dir / "contracts")
        except (OSError, ValueError) as exc:
            return [f"Pinned catalog integrity check failed: {exc}"]
        report_workflow = phase == "P5" and technical_report_enabled(catalog)
        if report_workflow:
            required = ("P1", "P2")
        if mode == "p3.assessment" and not catalog.output_schema("p3.assessment"):
            reasons.append("Adopt the current workflow contracts before assessing components")
        if mode == "p2.focused_method":
            reasons.append("Focused method work needs an exact selected baseline. This launch does not yet support that selection; use full catalog work with focus instructions.")
        canonical = {"P1": (("literature_synthesis", "synthesis_candidate"),), "P2": (("method_catalog", "method_changes"),),
                     "P3": (("theory_record", "complete_theory"),),
                     "P4": (("empirical_evidence_index", "empirical_index_candidate"),
                            ("empirical_synthesis", "empirical_synthesis_candidate"),
                            ("implementation_record", "implementation_record_candidate"))}
        for needed in required:
            source = "trunk" if needed in ("P1", "P2") else branch_id
            directory = project_dir / "branches" / source / "phases" / needed.lower()
            try:
                records = current_records(directory)
                if not records:
                    reasons.append(f"{needed} has no published records on {source}")
                elif catalog.scientific_validation_enabled:
                    for alternatives in canonical.get(needed, ()):
                        family = next((f for f in alternatives if f in records), None)
                        if family is None:
                            reasons.append(f"{needed} needs its complete current {alternatives[0]} record")
                        else:
                            read_generation(directory, family, records[family])
                else:
                    for family, pointer in records.items():
                        read_generation(directory, family, pointer)
            except ArtifactError as exc:
                reasons.append(str(exc))
        if phase in ("P3", "P4", "P5"):
            from .methods import get_method
            method = get_method(project_dir, branch_id)
            if not method or method.get("status") != "active":
                reasons.append("Select an active registered method")
            elif method.get("aligned") is False:
                reasons.append("The selected method changed; select its current definition before running")
        if mode in ("p3.theory_revision", "p3.assessment"):
            directory = project_dir / "branches" / branch_id / "phases" / "p3"
            try:
                records = current_records(directory)
                family = next((f for f in ("theory_record", "complete_theory") if f in records), None)
                if not records or (catalog.scientific_validation_enabled and family is None):
                    reasons.append("A complete current theory package is required for this action")
                elif family:
                    read_generation(directory, family, records[family])
            except ArtifactError as exc:
                reasons.append(str(exc))
        if mode == "p5.review_revision":
            records = current_records(project_dir / "branches" / branch_id / "phases" / "p5")
            families = ("technical_report", "technical_report_candidate") if report_workflow else ("manuscript", "manuscript_candidate")
            if not any(f in records for f in families):
                reasons.append("A current technical report is required for review" if report_workflow else "A current manuscript is required for review")
        if phase in ("P3", "P4", "P5") and catalog.scientific_validation_enabled:
            try:
                basis = self.compute_basis(project_id, phase, branch_id, mode)
                reasons.extend(basis.get("alignment_reasons", []))
                if report_workflow:
                    reasons.extend(report_assembly_readiness(basis))
            except (OSError, ValueError) as exc:
                reasons.append(f"Scientific input alignment could not be checked: {exc}")
        return list(dict.fromkeys(reasons))

    @staticmethod
    def _phase_published(project_dir: Path, branch_id: str, phase: str) -> bool:
        store = project_dir / "branches" / branch_id / "phases" / phase.lower()
        return bool(current_records(store))

    def compute_basis(self, project_id: str, phase: str, branch_id: str, mode: str | None = None,
                      *, model_override: dict | None = None) -> dict:
        """Snapshot references include current-phase revision and sibling evidence."""
        project_dir = self.project_dir(project_id)
        if not _IDENT_RE.fullmatch(branch_id):
            raise RunError("Invalid branch identifier")
        records: list[dict] = []
        phases = ("P1",) if phase == "P1" else (("P1", "P2") if phase == "P2" else ("P1", "P2", "P3", "P4") + (("P5",) if phase == "P5" else ()))
        for p in phases:
            source = "trunk" if p in ("P1", "P2") else branch_id
            store = project_dir / "branches" / source / "phases" / p.lower()
            for family, pointer in sorted(current_records(store).items()):
                records.append({"phase": p, "family": family, "branch": source,
                                **pointer, "sha256": pointer.get("content_sha256", "")})
        method = model_override
        if method is None and branch_id != "trunk":
            from .methods import get_method
            method = get_method(project_dir, branch_id)
        catalog = Catalog(project_dir / "contracts")
        from .alignment import filter_method_inputs
        records, excluded, alignment_reasons = filter_method_inputs(project_dir, records, method, phase, mode, catalog)
        payload = {"records": records, "method": method,
                   "excluded_method_inputs": excluded, "alignment_reasons": alignment_reasons,
                   "project": read_json(project_dir / "project.json") or {},
                   "catalog_pin": read_json(project_dir / "contracts" / "catalog-pin.json") or {},
                   "catalog_sha256": catalog.snapshot_sha256}
        if supports_problem_context(catalog):
            payload["problem_context"] = frozen_problem_context(project_dir, branch_id, method)
            if phase == "P5" and technical_report_enabled(catalog):
                payload["absent_scientific_inputs"] = [p for p in ("P3", "P4") if not any(r["phase"] == p for r in records)]
        # Freeze accumulated state at authorization, including committed legacy
        # history that cannot be represented by the latest family's pointer.
        cumulative = {}
        from .cumulative_attention import attention_applies_to_branch, open_attention_items
        attention = open_attention_items(project_dir, read_json(project_dir / "researcher" / "attention_resolutions.json") or {})
        method_id = (method or {}).get("method_id")
        attention = [item for item in attention if attention_applies_to_branch(item, branch_id, method_id, method)]
        if attention:
            cumulative["open_attention"] = {"items": attention}
        from .cumulative_attention import current_researcher_answers
        answered = [answer for answer in current_researcher_answers(project_dir)
                    if attention_applies_to_branch(answer.get("attention") or {}, branch_id, method_id)]
        if supports_problem_context(catalog):
            answered = applicable_researcher_answers(project_dir, branch_id, method, questions=attention,
                                                     phase=phase, context=payload["problem_context"])
        if phase in ("P4", "P5"):
            from .phase_interactions import completed_evaluation_answers
            answered.extend(completed_evaluation_answers(project_dir, branch_id))
        if answered:
            cumulative["researcher_answers"] = {"items": answered}
        if any(r["phase"] == "P1" and r["family"] in ("source_changes", "literature_library", "research_basis", "lead_literature", "theory_literature", "empirical_literature") for r in records):
            from .literature import load_committed_library
            cumulative["literature_library"] = load_committed_library(project_dir)
        elif phase == "P1":
            from .literature import build_library
            cumulative["literature_library"] = build_library(None, [], run_id="literature.empty")
        if phase == "P2":
            from .method_provenance import current_method_catalog
            cumulative["method_catalog"] = current_method_catalog(project_dir)
        if phase == "P5":
            from .review_ledger import load_review_ledger
            cumulative["review_issue_ledger"] = load_review_ledger(project_dir / "branches" / branch_id / "phases" / "p5")
        # Exact method-origin material is frozen alongside, not inside, the
        # filtered scientific inputs: it is provenance, never method input.
        provenance_scope: list[str] = []
        provenance_catalog: dict | None = None
        if phase == "P2":
            from .methods import _method_documents
            provenance_catalog = cumulative["method_catalog"]
            provenance_scope = [(m.get("identity") or m.get("method_identity"))["stable_id"]
                                for m in _method_documents(provenance_catalog)]
        elif method:
            from .method_provenance import current_method_catalog
            provenance_catalog = current_method_catalog(project_dir)
            provenance_scope = [method["method_id"]]
        if provenance_scope:
            from .method_provenance import resolve_method_provenance
            payload["method_provenance"] = resolve_method_provenance(project_dir, provenance_catalog, provenance_scope)
        # A revised method arms the next run on this branch with the phase's
        # prior package as digest-verified historical predecessor material —
        # separate from the admitted records above, never current support.
        if phase in ("P3", "P4", "P5") and method:
            from .methods import predecessor_material
            predecessor = predecessor_material(project_dir, branch_id, phase, method)
            if predecessor:
                payload["predecessor_material"] = predecessor
        payload["cumulative_inputs"] = {
            family: {"document": document, "sha256": self._cumulative_digest(document)}
            for family, document in cumulative.items()
        }
        digest = sha256_bytes(json.dumps(payload, sort_keys=True).encode())
        return {**payload, "sha256": digest, "basis_phase": phase, "basis_branch": branch_id}

    @staticmethod
    def _cumulative_digest(document) -> str:
        return sha256_bytes(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())

    def _cumulative_input(self, record: RunRecord, family: str):
        basis = read_json(self.run_dir(record.project_id, record.run_id) / "basis.json") or {}
        ref = basis.get("cumulative_inputs", {}).get(family)
        if ref is None:
            return None  # Pre-upgrade runs did not capture a cumulative index.
        document = read_json(Path(ref["snapshot_path"])) if ref.get("snapshot_path") else ref.get("document")
        if document is None or self._cumulative_digest(document) != ref.get("sha256"):
            raise ArtifactError(f"The frozen {family} changed or disappeared")
        return document

    # ------------------------------------------------------------------ #
    # Restart reconciliation (design/02 §8) — never auto-restarts
    # ------------------------------------------------------------------ #

    def reconcile_on_boot(self) -> list[str]:
        """Recover committed outcomes and make interrupted work visibly terminal."""
        recovered: list[str] = []
        projects = self.data_root / "projects"
        if not projects.is_dir():
            return recovered
        terminal = {s.value for s in TERMINAL_STATES}
        for run_json in sorted(projects.glob("*/runs/*/run.json")):
            doc = read_json(run_json)
            if not doc or doc.get("state") in terminal:
                continue
            record = self.load_run(doc["project_id"], doc["run_id"])
            phase_dir = self.project_dir(record.project_id) / "branches" / record.branch_id / "phases" / record.phase.lower()
            package = read_json(phase_dir / "current-package.json") or {}
            assessment = read_json(self.run_dir(record.project_id, record.run_id) / "assessment.json") or {}
            if package.get("run_id") == record.run_id:
                record.state = RunState.PUBLISHED
                record.terminal_reason = "publication_recovered_after_restart"
            elif record.intent == "assessment" and assessment.get("state") == "assessed":
                record.state = RunState.ASSESSED
                record.terminal_reason = "assessment_recovered_after_restart"
            elif ResearcherPauseStore(self.run_dir(record.project_id, record.run_id)).snapshot().get("pending_request"):
                request = ResearcherPauseStore(self.run_dir(record.project_id, record.run_id)).snapshot()["pending_request"]
                record.state = RunState.AWAITING_USER
                record.stage_states[request["stage_id"]] = "awaiting_user"
                record.terminal_reason = None
                self._save_run(record)
                continue  # A durable question never starts work on boot.
            elif self._progressive_p4(record):
                try:
                    controller = self._p4_controller(record)
                    progress = controller.snapshot()
                    if record.state == RunState.AWAITING_USER and progress.get("pause_request") and not progress.get("pending_batch"):
                        continue
                    controller.recover_interrupted()
                except Exception as exc:
                    record.state = RunState.FAILED
                    record.terminal_reason = f"Restart could not confirm experiment cleanup: {exc}"
                    record.updated_at = _now()
                    self._save_run(record)
                    self._event(record, "run.failed", record.terminal_reason)
                    recovered.append(record.run_id)
                    continue
                progress = controller.snapshot()
                if not progress.get("pause_request"):
                    controller.request({"operation": "request_decision",
                        "question": "Resume from the saved checkpoint or finish with the evidence so far?",
                        "reason": "The service restarted during this evaluation. No work was automatically repeated.",
                        "options": [{"label": "Resume", "consequence": "Explicitly authorize remaining work from this checkpoint."},
                                    {"label": "Finish", "consequence": "Review the available evidence and incomplete coverage."}]})
                record.state = RunState.AWAITING_USER
                record.terminal_reason = None
                record.stage_states[controller.snapshot()["resume_stage"]] = "awaiting_user"
            else:
                record.state = RunState.FAILED
                record.terminal_reason = "interrupted_by_restart"
                for stage_id, status in record.stage_states.items():
                    if status in ("running", "correcting"):
                        record.stage_states[stage_id] = "failed"
            record.updated_at = _now()
            self._save_run(record)
            self._event(
                record,
                f"run.{record.state.value}",
                f"Service restarted; {record.terminal_reason}.",
            )
            recovered.append(record.run_id)
        return recovered

    # ------------------------------------------------------------------ #
    # Run lifecycle
    # ------------------------------------------------------------------ #

    async def start_run(
        self, project_id: str, *, phase: str, mode: str, branch_id: str,
        basis_sha256: str = "", instructions: str = "", idempotency_key: str | None = None,
        intent: str = "run", target: dict | None = None, assessment_id: str | None = None,
        assessment_purpose: str = "assessment", retry_run_id: str | None = None,
        researcher_note_draft: str | None = None,
        supplied_method: dict | None = None,
        budget_seconds: float | None = None,
        context_refs: list[dict] | None = None,
        input_ids: list[str] | None = None,
    ) -> RunRecord:
        if self.shutting_down:
            raise RunError("The local service is shutting down; start the run after it restarts.")
        async with self._lock(f"phase:{project_id}:{branch_id}:{phase}"):
            return await self._start_run_locked(
                project_id, phase=phase, mode=mode, branch_id=branch_id,
                basis_sha256=basis_sha256, instructions=instructions, idempotency_key=idempotency_key,
                intent=intent, target=target, assessment_id=assessment_id, supplied_method=supplied_method,
                assessment_purpose=assessment_purpose, retry_run_id=retry_run_id,
                researcher_note_draft=researcher_note_draft,
                budget_seconds=budget_seconds,
                context_refs=context_refs,
                input_ids=input_ids,
            )

    def _assert_phase_available(self, project_id: str, phase: str, branch_id: str, *, excluding: str | None = None) -> None:
        for path in sorted((self.project_dir(project_id) / "runs").glob("*/run.json")):
            doc = read_json(path)
            if (doc and doc.get("run_id") != excluding
                    and doc.get("assessment_purpose") not in ("issue_explanation", "issue_suggestions", "project_context", "model_dialogue")
                    and doc.get("state") not in {s.value for s in TERMINAL_STATES}
                    and doc.get("phase") == phase and doc.get("branch_id") == branch_id):
                raise RunError(f"a {phase} run is already active on branch {branch_id} ({doc['run_id']}); cancel it or wait")

    def _assert_publication_current(self, record: RunRecord) -> str | None:
        if record.intent == "assessment":
            return None
        saved = read_json(self.run_dir(record.project_id, record.run_id) / "publication-base.json")
        if not isinstance(saved, dict) or saved.get("phase") != record.phase or saved.get("branch_id") != record.branch_id or not saved.get("token"):
            raise RunError("This run did not capture its publication base; start a new run against current evidence")
        phase_dir = self.project_dir(record.project_id) / "branches" / record.branch_id / "phases" / record.phase.lower()
        if current_package_token(phase_dir) != saved["token"]:
            raise RunError("Current research changed after this run was authorized; start a new revision against the current evidence")
        basis = read_json(self.run_dir(record.project_id, record.run_id) / "basis.json") or {}
        if basis.get("method"):
            from .methods import get_method
            method = get_method(self.project_dir(record.project_id), record.branch_id)
            if not method or method.get("identity") != basis["method"].get("identity") or method.get("status") != "active":
                raise RunError("The method changed during this run; its results are retained but cannot replace current work")
        from .alignment import validate_frozen_basis_alignment
        reasons = validate_frozen_basis_alignment(self.project_dir(record.project_id), basis, record.phase, record.mode, catalog=self._catalog(record))
        if reasons:
            raise RunError("The frozen research inputs cannot support publication: " + "; ".join(reasons))
        return saved["token"]

    async def _start_run_locked(
        self,
        project_id: str,
        *,
        phase: str,
        mode: str,
        branch_id: str,
        basis_sha256: str = "",
        instructions: str = "",
        idempotency_key: str | None = None,
        intent: str = "run",
        target: dict | None = None,
        assessment_id: str | None = None,
        assessment_purpose: str = "assessment",
        researcher_note_draft: str | None = None,
        retry_run_id: str | None = None,
        supplied_method: dict | None = None,
        budget_seconds: float | None = None,
        context_refs: list[dict] | None = None,
        input_ids: list[str] | None = None,
    ) -> RunRecord:
        if self.shutting_down:
            raise RunError("The local service is shutting down; start the run after it restarts.")
        if phase not in PHASES:
            raise RunError(f"unknown phase {phase}")
        if not _IDENT_RE.fullmatch(branch_id):
            raise RunError(f"invalid branch id {branch_id!r}")
        project_dir = self.project_dir(project_id)
        if not (project_dir / "project.json").is_file():
            raise RunError(f"unknown project {project_id}")
        if intent not in ("run", "assessment"):
            raise RunError("Unknown request intent")
        if assessment_purpose not in ("assessment", "explanation", "issue_explanation", "issue_suggestions", "project_context", "model_dialogue"):
            raise RunError("Unknown assessment purpose")
        if intent != "assessment" and (assessment_purpose != "assessment" or retry_run_id):
            raise RunError("Explanation conversations require assessment intent")
        if assessment_purpose == "project_context":
            if not supports_problem_context(project_dir):
                raise RunError("Adopt the model-development workflow before discussing problem context")
            try:
                initial_context_issue = resolve_project_context_target(project_dir, target) if target else None
            except ValueError as exc:
                raise RunError(str(exc)) from exc
            context_scope = (initial_context_issue or {}).get("scope") or {"kind": "project"}
            phase, branch_id = ("P3", context_scope["branch"]) if context_scope["kind"] == "model" else ("P1", "trunk")
        # A duplicate delivery is the same accepted command, even if that
        # attempt has already completed or newer research is now available.
        if idempotency_key:
            index = read_json(project_dir / "runs" / "_index.json") or {}
            existing = index.get(idempotency_key)
            if existing:
                return self.load_run(project_id, existing)
        if phase == "P2" and mode == "p2.focused_method":
            raise RunError("Focused method revision is not yet available; choose a proposal and comparison run")
        previous_assessment = self._find_assessment(project_id, assessment_id) if assessment_id else None
        conversation = None
        if intent == "assessment" and assessment_id:
            conversation = next((item for item in self.list_assessments(project_id)
                                 if item["assessment_id"] == assessment_id), None)
            if conversation is None:
                raise RunError("Unknown assessment")
            if conversation.get("assessment_purpose") in ("issue_explanation", "issue_suggestions", "project_context", "model_dialogue") and any(
                    turn.get("state") not in {state.value for state in TERMINAL_STATES} for turn in conversation.get("turns", [])):
                raise RunError("A reply is already being prepared in this conversation")
            saved_target = conversation["target"]
            if saved_target.get("kind") != "project_context" and saved_target.get("branch", saved_target.get("branch_id")) != branch_id:
                raise RunError("Assessment discussion belongs to a different method")
            if target is not None and target != saved_target:
                raise RunError("Assessment discussion must remain linked to its original target")
            target = saved_target
            assessment_purpose = conversation.get("assessment_purpose", "assessment")
            if assessment_purpose == "project_context":
                context_scope = conversation.get("scope") or {"kind": "project"}
                phase, branch_id = ("P3", context_scope["branch"]) if context_scope["kind"] == "model" else ("P1", "trunk")
            if retry_run_id:
                latest = conversation.get("turns", [])[-1:]
                if (assessment_purpose not in ("explanation", "issue_explanation", "issue_suggestions", "project_context", "model_dialogue") or not latest or latest[0]["run_id"] != retry_run_id
                        or latest[0]["state"] not in ("failed", "cancelled")):
                    raise RunError("Only the latest failed conversation question can be retried")
                retry = self.load_run(project_id, retry_run_id)
                instructions = retry.instructions
                researcher_note_draft = retry.researcher_note_draft
                previous_assessment = read_json(self.run_dir(project_id, retry_run_id) / "previous-assessment.json") or {}
                previous_assessment = {**previous_assessment, "run_id": retry_run_id, "target": target,
                                       "assessment_purpose": assessment_purpose, "created_at": conversation["created_at"]}
            elif previous_assessment is None:
                raise RunError("The first question has not completed; retry its failed attempt before asking a follow-up")
        elif retry_run_id:
            raise RunError("Retry requires its saved conversation identity")
        if intent == "assessment":
            if not target or (phase != "P3" and assessment_purpose not in ("issue_explanation", "issue_suggestions", "project_context", "model_dialogue")):
                raise RunError("An assessment requires an exact theory component target")
            mode = "p3.assessment"
        elif mode == "p3.assessment":
            raise RunError("Assessment mode requires assessment intent")
        if assessment_id and not previous_assessment:
            raise RunError("Unknown assessment")
        discussion = intent == "assessment" and previous_assessment is not None
        context_dialogue = assessment_purpose == "project_context"
        issue_explanation = assessment_purpose in ("issue_explanation", "issue_suggestions", "model_dialogue")
        report_section = bool(target and target.get("kind") == "report_section")
        if report_section and (intent != "assessment" or assessment_purpose != "model_dialogue"):
            raise RunError("Discuss a report section through its read-only conversation")
        readonly_dialogue = context_dialogue or issue_explanation
        if researcher_note_draft is not None and (not isinstance(researcher_note_draft, str) or not readonly_dialogue):
            raise RunError("A response note draft belongs to an item discussion or suggestion request")
        if assessment_purpose in ("explanation", "issue_explanation", "issue_suggestions", "project_context", "model_dialogue") and not instructions.strip():
            raise RunError("Enter your question about the selected scientific item")
        from .providers import ProviderConfigError, load_provider_config
        try:
            load_provider_config(self.data_root).require_ready()
        except ProviderConfigError as exc:
            raise RunError(str(exc)) from None
        lead_input_mode = (phase == "P2" and Catalog(project_dir / "contracts").schema_for_output("p2.lead_proposal") == "lead-proposal.schema.json")
        if phase == "P2" and intent == "run" and instructions.strip() and not lead_input_mode:
            raise RunError("Update the workflow contracts before sending additional Phase 2 instructions or ideas to the lead")
        method_starting_point = None
        if supplied_method is not None:
            if phase != "P2" or intent != "run":
                raise RunError("A supplied method belongs to a Phase 2 method run")
            fields = ("title", "specification_markdown", "source_reference")
            if (not isinstance(supplied_method, dict) or set(supplied_method) != set(fields)
                    or any(not isinstance(supplied_method.get(key), str) or not supplied_method[key].strip() for key in fields)):
                raise RunError("A supplied method requires its title, exact specification and source reference")
            if "p2.lead_proposal" not in Catalog(project_dir / "contracts").output_definitions("P2"):
                raise RunError("Update the workflow contracts before proposing and cross-auditing a supplied method")
            supplied_method = dict(supplied_method)
            from .p2_delivery import resolve_method_starting_point
            try:
                method_starting_point = resolve_method_starting_point(project_dir, supplied_method)
            except ValueError as exc:
                raise RunError(str(exc)) from exc
            mode = "p2.researcher_proposal"
        elif lead_input_mode and instructions.strip() and mode in ("p2.full_catalog", "p2.researcher_proposal"):
            mode = "p2.researcher_proposal"
        elif phase == "P2" and mode == "p2.researcher_proposal" and "p2.lead_proposal" in Catalog(project_dir / "contracts").output_definitions("P2"):
            raise RunError("Select or enter the supplied method before starting this Phase 2 run")
        if not readonly_dialogue:
            self._assert_phase_available(project_id, phase, branch_id)
        # A3: readiness gates (design/02 §7) — refuse with reasons.
        reasons = [] if discussion or readonly_dialogue else self.check_readiness(project_id, phase, branch_id, mode)
        if reasons:
            raise RunError("not ready: " + "; ".join(reasons))
        # Pinned basis (design/00 §3, design/02 §1): record the exact basis
        # digests; a researcher-pinned digest that no longer matches refuses
        # before any agent work starts (stale UI render → re-open message).
        previous_run = self.run_dir(project_id, previous_assessment["run_id"]) if previous_assessment else None
        initial_issue = self._resolve_explanation_issue(project_id, target) if issue_explanation and not discussion else None
        context_model = None
        if context_dialogue and not discussion and initial_context_issue["scope"]["kind"] == "model":
            from .problem_context import resolve_context_model
            try:
                context_model = resolve_context_model(project_dir, initial_context_issue["scope"])
            except ValueError as exc:
                raise RunError(str(exc)) from exc
        basis = (read_json(previous_run / "basis.json") if discussion else
                 self.compute_basis(project_id, phase, branch_id, mode, model_override=context_model))
        if context_dialogue and not discussion:
            from .problem_context import initialize_problem_context
            initialize_problem_context(project_dir)
            try:
                context_issue = resolve_project_context_target(project_dir, target)
            except ValueError as exc:
                raise RunError(str(exc)) from exc
            from .problem_context import effective_account
            snapshot = context_issue["problem_context"]
            if context_model:
                source = context_model.get("source_ref")
                if source and not any(ref.get("generation_id") == source.get("generation_id")
                                      and ref.get("family") == source.get("family") for ref in basis["records"]):
                    basis["records"].append(source)
                # The exact retained definition supplies this conversation's
                # provenance. A newer catalog's model lineage is not its source.
                basis.pop("method_provenance", None)
            basis["problem_context"] = {**snapshot, "sha256": target["sha256"],
                "effective_account": effective_account(snapshot, branch_id, basis.get("method"))}
            basis["context_dialogue"] = context_issue
            basis["project"]["research_instructions"] = snapshot["brief"]["instructions"]
            payload = {key: value for key, value in basis.items() if key not in ("sha256", "basis_phase", "basis_branch")}
            basis["sha256"] = sha256_bytes(json.dumps(payload, sort_keys=True).encode())
        issue_source_run = None
        if issue_explanation and not discussion:
            source_run_id = initial_issue.get("source_run_id") or target.get("run_id") or "missing"
            if not isinstance(source_run_id, str) or not _IDENT_RE.fullmatch(source_run_id):
                raise RunError("The issue's original run identity is invalid")
            candidate = self.run_dir(project_id, source_run_id)
            original_basis = read_json(candidate / "basis.json")
            if original_basis and (candidate / "contracts").is_dir():
                issue_source_run = candidate
                basis = original_basis
            elif report_section:
                raise RunError("This report's original frozen scientific context is unavailable")
        frozen_context = discussion or issue_source_run is not None
        if not basis:
            raise RunError("The assessment's original frozen context is unavailable")
        if basis_sha256 and basis["sha256"] != basis_sha256:
            raise RunError(
                "basis is stale: the project brief or published records changed since this "
                "run was rendered — re-open the phase view and run again"
            )
        if context_dialogue:
            stages = [StageSpec(stage_id="p3.assessment", sequence=1, execution="serial",
                roles=(MemberRole.RESEARCH_LEAD,), writes=("p3.assessment",),
                objective="Discuss exact problem context without publishing or changing scientific work.")]
        elif issue_explanation:
            if discussion:
                issue = basis.get("explanation_issue")
                if not issue or issue.get("explanation_target") != target:
                    raise RunError("The conversation's original issue is unavailable")
                if report_section and not retry_run_id:
                    from .report_sections import load_section_comment
                    issue["researcher_comment"] = load_section_comment(project_dir, target, verify_source=False)
            else:
                issue = initial_issue
                if report_section:
                    from .report_sections import load_section_comment, section_source_records
                    issue["researcher_comment"] = load_section_comment(project_dir, issue["explanation_target"], verify_source=False)
                    basis["records"] = section_source_records(issue, basis)
                    basis["cumulative_inputs"] = {}
                    basis.pop("predecessor_material", None)
                else:
                    from .phase_interactions import exact_saved_answer
                    issue["researcher_answer"] = exact_saved_answer(project_dir, issue)
                if target.get("branch") != branch_id or target.get("phase") != phase:
                    raise RunError("The issue belongs to a different phase or method")
                # Exact source records may be historical or excluded from a
                # new study's current-method inputs. Explanation is read-only.
                if target.get("kind") == "phase_issue" and not any(r.get("generation_id") == target.get("generation_id") and r.get("family") == target.get("family") for r in basis["records"]):
                    basis["records"].append({**target, "content_sha256": target["sha256"]})
                basis["explanation_issue"] = issue
                basis["explanation_context_note"] = ("Relevant sources retain the original producing run's frozen context."
                    if issue_source_run else "The original run context is unavailable. The exact issue is retained; other sources were frozen when this question was asked and may reflect later revisions.")
                target = issue["explanation_target"]
            stages = [StageSpec(stage_id="p3.assessment", sequence=1, execution="serial",
                                roles=(MemberRole.RESEARCH_LEAD if assessment_purpose == "issue_suggestions" else MemberRole(issue["responsible_role"]),),
                                writes=("p3.assessment",),
                                objective=("Suggest how to respond to the selected issue without changing scientific work."
                                           if assessment_purpose == "issue_suggestions" else "Explain the selected issue without changing scientific work."))]
        else:
            stages = self.stage_plan(project_id, phase, mode)
        if readonly_dialogue and (not frozen_context or (report_section and not retry_run_id)):
            payload = {key: value for key, value in basis.items() if key not in ("sha256", "basis_phase", "basis_branch")}
            basis["sha256"] = sha256_bytes(json.dumps(payload, sort_keys=True).encode())
        if context_refs and intent != "run":
            raise RunError("Further-work references belong to an explicitly started research run")
        if context_refs:
            selected = [self._resolve_explanation_issue(project_id, ref) for ref in context_refs]
            if any(item.get("branch") not in ("trunk", branch_id) for item in selected) and phase != "P2":
                raise RunError("A selected issue belongs to a different method")
            basis["selected_issues"] = selected
            payload = {key: value for key, value in basis.items() if key not in ("sha256", "basis_phase", "basis_branch")}
            basis["sha256"] = sha256_bytes(json.dumps(payload, sort_keys=True).encode())
        source_catalog = previous_run / "contracts" if discussion else (issue_source_run / "contracts" if issue_source_run else project_dir / "contracts")
        catalog = Catalog(source_catalog)
        contract = read_json(source_catalog / "contracts" / "phases" / "P4.json") or {}
        progressive = phase == "P4" and intent == "run" and "progressive_evaluation_v1" in contract.get("capabilities", [])
        selected_input_ids = list(input_ids or [])
        if selected_input_ids:
            if not progressive or "p4.workflow_templates.v1" not in contract.get("capabilities", []):
                raise RunError("Adopt the revised Phase 4 workflow before supplying local analysis files")
            from .researcher_inputs import selected_inputs
            try:
                selected_inputs(project_dir, selected_input_ids)
            except ValueError as exc:
                raise RunError(str(exc)) from exc
        if budget_seconds is not None:
            import math
            if not progressive or not math.isfinite(budget_seconds) or budget_seconds <= 0:
                raise RunError("Experiment budget requires a progressive Phase 4 run and a positive number of seconds")
        if catalog.scientific_validation_enabled:
            problems = catalog.verify_manifest()
            if problems:
                raise RunError("Pinned catalog integrity check failed: " + "; ".join(f.message for f in problems))
        if target and not readonly_dialogue:
            if phase == "P3" and (str(target.get("phase", "")).upper() != "P3" or target.get("family") not in ("theory_record", "complete_theory")):
                raise RunError("Select a component from the complete current theory record")
            if phase == "P4":
                from .empirical_targets import resolve_empirical_target
                try:
                    target, _, _ = resolve_empirical_target(project_dir, branch_id, target)
                except ArtifactError as exc:
                    raise RunError(str(exc)) from exc
            elif assessment_purpose == "explanation":
                target = self._validate_explanation_target(project_id, branch_id, target, basis=basis if discussion else None)
            else:
                target = self._validate_target(project_id, branch_id, target, allow_historical=discussion)
        if previous_assessment and previous_assessment.get("target") != target:
            raise RunError("Assessment discussion must remain linked to its original target")
        record = RunRecord(
            run_id=new_id(f"run.{phase.lower()}.{mode}"),
            project_id=project_id,
            phase=phase,
            mode=mode,
            branch_id=branch_id,
            basis_sha256=basis["sha256"] or "",
            instructions=instructions,
            supplied_method=supplied_method,
            created_at=_now(),
            updated_at=_now(),
            stage_states={s.stage_id: "pending" for s in stages},
            intent=intent, target=target,
            assessment_id=(assessment_id or new_id("assessment")) if intent == "assessment" else assessment_id,
            assessment_purpose=assessment_purpose, retry_run_id=retry_run_id,
            researcher_note_draft=researcher_note_draft,
            assessment_turn_index=len(conversation.get("turns", [])) if conversation else 0,
            responsible_role=stages[0].roles[0].value if intent == "assessment" else None,
            catalog_pin=basis.get("catalog_pin", {}),
            experiment_budget_seconds=(budget_seconds or default_experiment_budget()) if progressive else None,
            input_ids=selected_input_ids,
        )
        run_dir = self.run_dir(project_id, record.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        if progressive and "p4.workflow_templates.v1" in contract.get("capabilities", []):
            from .researcher_inputs import freeze_inputs
            try:
                basis["p4_inputs"] = freeze_inputs(project_dir, run_dir, selected_input_ids)
            except ValueError as exc:
                raise RunError(str(exc)) from exc
            if selected_input_ids:
                basis["sha256"] = sha256_bytes(json.dumps({"research_basis": basis["sha256"],
                    "inputs": [(row["input_id"], row["sha256"], row["mapping"]) for row in basis["p4_inputs"]["inputs"]]},
                    sort_keys=True, ensure_ascii=False).encode())
                record.basis_sha256 = basis["sha256"]
        if method_starting_point:
            from .p2_delivery import freeze_method_starting_point
            basis["p2_method_starting_point"] = freeze_method_starting_point(run_dir, method_starting_point)
        # Independent of filtered scientific inputs: a new method still must
        # not overwrite work published after this authorization.
        if intent != "assessment":
            write_json_atomic(run_dir / "publication-base.json", {
                "phase": phase, "branch_id": branch_id,
                "token": current_package_token(project_dir / "branches" / branch_id / "phases" / phase.lower()),
            })
        if phase == "P4" and target and not issue_explanation:
            from .empirical_targets import freeze_empirical_target
            freeze_empirical_target(project_dir, run_dir, branch_id, target)
        original_artifacts = basis.get("artifacts", []) if frozen_context else []
        basis["artifacts"] = []
        basis["unavailable_artifacts"] = []
        copied_artifacts = set()
        artifact_sources = []
        for family, ref in basis.get("cumulative_inputs", {}).items():
            document = read_json(Path(ref["snapshot_path"])) if frozen_context and ref.get("snapshot_path") else ref.get("document")
            if document is None or self._cumulative_digest(document) != ref.get("sha256"):
                raise ArtifactError(f"The cumulative {family} changed while preparing this run")
            snapshot = run_dir / "inputs" / "cumulative" / (family + ".json")
            write_json_atomic(snapshot, document)
            ref.pop("document", None)
            ref["snapshot_path"] = str(snapshot)
            if family in ("literature_library", "method_catalog"):
                library_ref = next((r for r in basis["records"] if r["family"] == family), {})
                artifact_sources.append(({**library_ref, "family": family, "phase": "P1" if family == "literature_library" else "P2", "branch": "trunk"}, document))
        for ref in basis["records"]:
            phase_dir = project_dir / "branches" / ref["branch"] / "phases" / ref["phase"].lower()
            source = Path(ref["snapshot_path"]) if frozen_context and ref.get("snapshot_path") else generation_path(phase_dir, ref["family"], ref)
            if not source.is_file() or sha256_file(source) != ref.get("content_sha256"):
                raise ArtifactError("The assessment's frozen source changed or disappeared")
            snapshot = run_dir / "inputs" / ref["branch"] / ref["phase"].lower() / source.name
            # Include family to avoid collisions in legacy generation IDs.
            snapshot = snapshot.parent / ref["family"] / snapshot.name
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(source.read_bytes())
            ref["snapshot_path"] = str(snapshot)
            if ref.get("format") != "jsonl":
                artifact_sources.append((ref, json.loads(snapshot.read_text(encoding="utf-8"))))
        for ref, document in artifact_sources:
            for origin, artifact in self._record_artifact_pointers(ref, document):
                identity = (origin.get("run_id"), artifact.get("sha256") or artifact.get("artifact_sha256"))
                if identity in copied_artifacts:
                    continue
                try:
                    frozen = next((a for a in original_artifacts if a["content_sha256"] == identity[1]), None)
                    if frozen_context and frozen is None:
                        raise ArtifactError("Source was unavailable in the original assessment context")
                    original = Path(frozen["path"]) if frozen else source_artifact_path(project_dir, origin, artifact)
                    if not original.is_file() or sha256_file(original) != identity[1]:
                        raise ArtifactError("The assessment's frozen source file changed or disappeared")
                except ArtifactError as exc:
                    basis["unavailable_artifacts"].append({"family": ref["family"], "artifact": artifact, "reason": str(exc)})
                    continue
                destination = run_dir / "inputs" / "artifacts" / (sha256_file(original) + "-" + original.name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(original.read_bytes())
                copied_artifacts.add(identity)
                basis["artifacts"].append({"family": ref["family"], "phase": ref["phase"],
                    "generation_id": ref.get("generation_id"), "producing_run_id": origin.get("run_id"), "artifact_id": artifact.get("artifact_id"),
                    "content_sha256": sha256_file(destination), "path": str(destination),
                    "original_path": artifact.get("path") or artifact.get("artifact_path")})
        # Historical predecessor material is frozen and digest-verified the same
        # way, under its own clearly labeled directory — never into records.
        for ref in (basis.get("predecessor_material") or {}).get("materials", {}).values():
            phase_dir = project_dir / "branches" / ref["branch"] / "phases" / ref["phase"].lower()
            source = Path(ref["snapshot_path"]) if frozen_context and ref.get("snapshot_path") else generation_path(phase_dir, ref["family"], ref)
            if not source.is_file() or sha256_file(source) != ref.get("content_sha256"):
                raise ArtifactError("The predecessor package changed or disappeared while preparing this run")
            snapshot = run_dir / "inputs" / "predecessor" / ref["phase"].lower() / ref["family"] / source.name
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(source.read_bytes())
            ref["snapshot_path"] = str(snapshot)
        shutil.copytree(source_catalog, run_dir / "contracts")
        if Catalog(run_dir / "contracts").snapshot_sha256 != basis.get("catalog_sha256"):
            raise RunError("Catalog changed while preparing the run; reopen and request the run again")
        write_json_atomic(run_dir / "stage-plan.json", [asdict(s) for s in stages])
        if previous_assessment:
            write_json_atomic(run_dir / "previous-assessment.json", previous_assessment)
        write_json_atomic(run_dir / "basis.json", basis)
        self._save_run(record)
        if progressive:
            self._p4_controller(record, stages[0], stages[0].roles[0])
        if idempotency_key:
            index = read_json(project_dir / "runs" / "_index.json") or {}
            index[idempotency_key] = record.run_id
            write_json_atomic(project_dir / "runs" / "_index.json", index)
        self._event(record, "run.requested", "Run command accepted.")
        if self.shutting_down:
            raise RunError("The local service is shutting down; start the run after it restarts.")
        task = asyncio.create_task(self._drive(record, stages))
        self._tasks[record.run_id] = task
        self._task_projects[record.run_id] = record.project_id
        return record

    def _resolve_explanation_issue(self, project_id, target):
        from .phase_interactions import resolve_issue, pause_target
        try:
            if target.get("kind") == "report_section":
                from .report_sections import resolve_report_section
                return resolve_report_section(self.project_dir(project_id), target)
            if target.get("kind") == "researcher_pause":
                record = self.load_run(project_id, target.get("run_id", ""))
                return ResearcherPauseStore(self.run_dir(project_id, record.run_id)).resolve_target(record, target)
            if target.get("kind") != "p4_pause":
                return resolve_issue(self.project_dir(project_id), target)
            if not isinstance(target.get("run_id"), str):
                raise ValueError("Select an evaluation question with its exact run identity")
            source = self.load_run(project_id, target["run_id"])
            if not self._progressive_p4(source):
                raise ValueError("This run has no progressive evaluation question")
            from .p4_execution import P4Controller
            progress = P4Controller.load_snapshot(self.run_dir(project_id, source.run_id)) or {}
            requests = [progress.get("pause_request"), *(row.get("request") for row in progress.get("answer_revisions", []))]
            request = next((item for item in requests if item and pause_target(source, item) == target), None)
            if not request:
                raise ValueError("The selected evaluation question has changed or is unavailable")
            role = request.get("member") or "data_analyst"
            return {**request, "issue_id": request["request_id"], "title": request.get("question", ""),
                    "branch": source.branch_id, "phase": "P4", "responsible_role": role,
                    "explanation_target": target,
                    "evaluation_context": {"plan": progress.get("plan"), "budget": progress.get("budget"),
                                           "last_checkpoint": (progress.get("checkpoints") or [None])[-1],
                                           "experiments": [{key: row.get(key) for key in ("work_item_id", "batch_id", "status", "elapsed_seconds", "diagnostic")}
                                                           for row in progress.get("ledger", [])]}}
        except (ValueError, ArtifactError) as exc:
            raise RunError(str(exc)) from exc

    @staticmethod
    def _record_artifact_pointers(ref: dict, document):
        # A cumulative source's full text still belongs to the run that saved
        # that source revision, not the run that rebuilt the library index.
        if ref.get("family") == "method_catalog" and isinstance(document, dict) and "method_sources" in document:
            from .methods import _method_documents
            for method in _method_documents(document):
                identity = method.get("identity") or method.get("method_identity") or {}
                source = document["method_sources"].get(identity.get("stable_id"), {})
                origin = {**ref, "run_id": source.get("run_id") or "unknown", "stage_id": source.get("stage_id")}
                for artifact in RunEngine._artifact_pointers(method):
                    yield origin, artifact
        elif ref.get("family") == "literature_library":
            for source in document.get("sources", []):
                for revision in source.get("revisions", []):
                    origin = {**ref, "run_id": revision["run_id"], "stage_id": None}
                    for artifact in RunEngine._artifact_pointers(revision["document"]):
                        yield origin, artifact
        else:
            for artifact in RunEngine._artifact_pointers(document):
                yield ref, artifact

    @staticmethod
    def _artifact_pointers(document):
        if isinstance(document, dict):
            if (document.get("path") or document.get("artifact_path")) and (document.get("sha256") or document.get("artifact_sha256")):
                yield document
            for value in document.values():
                yield from RunEngine._artifact_pointers(value)
        elif isinstance(document, list):
            for value in document:
                yield from RunEngine._artifact_pointers(value)

    @staticmethod
    def _component(document, object_id: str):
        if isinstance(document, dict):
            if any(document.get(k) == object_id for k in ("id", "statement_id", "assumption_id", "object_id", "proof_id", "probe_id", "definition_id")):
                return document
            for value in document.values():
                found = RunEngine._component(value, object_id)
                if found is not None:
                    return found
        elif isinstance(document, list):
            for value in document:
                found = RunEngine._component(value, object_id)
                if found is not None:
                    return found
        return None

    def _validate_target(self, project_id: str, branch_id: str, target: dict, *, allow_historical: bool = False) -> dict:
        target = dict(target)
        if target.get("branch", target.get("branch_id")) != branch_id:
            raise RunError("Target belongs to a different method")
        phase = str(target.get("phase", "")).upper()
        if phase not in PHASES:
            raise RunError("Invalid target phase")
        directory = self.project_dir(project_id) / "branches" / branch_id / "phases" / phase.lower()
        family = str(target.get("family", ""))
        pointer = current_records(directory).get(family)
        if not pointer or pointer.get("generation_id") != target.get("generation_id"):
            if not allow_historical:
                raise RunError("Target is stale: reopen the current component before requesting work")
            pointer = {"generation_id": target.get("generation_id"), "content_sha256": target.get("sha256"), "run_id": target.get("run_id")}
        expected = target.get("sha256") or target.get("content_sha256")
        if expected and expected != pointer.get("content_sha256"):
            raise RunError("Target digest does not match its current generation")
        document = read_generation(directory, family, pointer)
        if not allow_historical and Catalog(self.project_dir(project_id) / "contracts").scientific_validation_enabled:
            from .alignment import method_identity
            from .methods import get_method
            selected = get_method(self.project_dir(project_id), branch_id)
            if not method_identity(document) or method_identity(document) != method_identity(selected):
                raise RunError("Target theory belongs to a different method version; establish theory for the selected method before requesting work")
        object_id = str(target.get("object_id", ""))
        if object_id and self._component(document, object_id) is None:
            raise RunError(f"Target component {object_id} is absent from its exact artifact")
        return {**target, "branch": branch_id, "phase": phase, "sha256": pointer["content_sha256"],
                "run_id": pointer.get("run_id"), "generation_id": pointer["generation_id"]}

    def _find_assessment(self, project_id: str, assessment_id: str | None) -> dict | None:
        if not assessment_id:
            return None
        found = []
        for path in self.project_dir(project_id).glob("runs/*/assessment.json"):
            document = read_json(path)
            if document and document.get("assessment_id") == assessment_id:
                found.append(document)
        return max(found, key=lambda d: (d.get("updated_at", ""), d.get("assessment_turn_index", 0))) if found else None

    def _validate_explanation_target(self, project_id: str, branch_id: str, target: dict, *, basis: dict | None = None) -> dict:
        """An explanation names a real assumption, never a relabeled statement."""
        if (target.get("kind") != "assumption" or not target.get("object_id")
                or not target.get("generation_id") or not (target.get("sha256") or target.get("content_sha256"))):
            raise RunError("Select a source-linked assumption with its exact generation and digest")
        if basis is None:
            target = self._validate_target(project_id, branch_id, target)
            phase_dir = self.project_dir(project_id) / "branches" / branch_id / "phases" / "p3"
            document = read_generation(phase_dir, target["family"], {
                "generation_id": target["generation_id"], "content_sha256": target["sha256"], "run_id": target.get("run_id"),
            })
        else:
            refs = [ref for ref in basis.get("records", [])
                    if ref.get("branch") == branch_id and ref.get("phase") == "P3"
                    and ref.get("family") == target.get("family")
                    and ref.get("generation_id") == target.get("generation_id")
                    and ref.get("content_sha256") == target.get("sha256")]
            if len(refs) != 1 or not refs[0].get("snapshot_path"):
                raise RunError("The assumption is unavailable in this conversation's frozen context")
            source = Path(refs[0]["snapshot_path"])
            if not source.is_file() or sha256_file(source) != target["sha256"]:
                raise RunError("The conversation's frozen assumption source changed or disappeared")
            document = read_json(source)
        assumptions = document.get("assumptions", []) if isinstance(document, dict) else []
        if not any(isinstance(item, dict) and item.get("assumption_id") == target["object_id"] for item in assumptions):
            raise RunError("The selected item is not in the source document's assumptions collection")
        return target

    def list_assessments(self, project_id: str, branch: str | None = None) -> list[dict]:
        """Project saved results plus every durable explanation attempt, without model calls."""
        from .research import source_ref, record_url

        def linked_refs(evidence_refs, basis):
            linked = []
            for evidence in evidence_refs:
                matches = [ref for ref in basis.get("records", [])
                           if ref.get("family") == evidence.get("family")
                           and ref.get("generation_id") == evidence.get("generation_id")]
                if len(matches) == 1:
                    ref = matches[0]
                    reference = source_ref(ref["branch"], ref["phase"], ref["family"], ref)
                    linked.append({**evidence, "generation_ref": reference, "source_url": record_url(project_id, reference)})
                else:
                    linked.append({**evidence, "source_error": "This evidence reference is not uniquely linked to the assessment's frozen inputs."})
            return linked

        latest, attempts = {}, {}
        for directory in self.project_dir(project_id).glob("runs/*"):
            if not directory.is_dir():
                continue
            item = read_json(directory / "assessment.json")
            run = read_json(directory / "run.json") or {}
            if not isinstance(item, dict) and not (run.get("intent") == "assessment" and run.get("assessment_purpose") in ("explanation", "issue_explanation", "issue_suggestions", "project_context", "model_dialogue")):
                continue
            basis = read_json(directory / "basis.json") or {}
            if isinstance(item, dict) and item.get("assessment_id"):
                item["assessment_purpose"] = item.get("assessment_purpose", "assessment")
                item["evidence_refs"] = linked_refs(item.get("evidence_refs", []), basis)
                item["messages"] = [{**message, "evidence_refs": linked_refs(message.get("evidence_refs", []), basis)}
                                    if message.get("role") == "assistant" else message for message in item.get("messages", [])]
                aid = item["assessment_id"]
                if ((item.get("updated_at", ""), item.get("assessment_turn_index", 0))
                        >= (latest.get(aid, {}).get("updated_at", ""), latest.get(aid, {}).get("assessment_turn_index", 0))):
                    latest[aid] = item
            if run.get("intent") == "assessment" and run.get("assessment_purpose") in ("explanation", "issue_explanation", "issue_suggestions", "project_context", "model_dialogue") and run.get("assessment_id"):
                aid = run["assessment_id"]
                turn = {key: run.get(key) for key in ("run_id", "instructions", "researcher_note_draft", "state", "terminal_reason", "created_at", "updated_at", "retry_run_id")}
                turn["assessment_turn_index"] = run.get("assessment_turn_index", 0)
                if isinstance(item, dict):
                    turn["assessment_markdown"] = item.get("assessment_markdown") or item.get("summary", "")
                    turn["evidence_refs"] = item["evidence_refs"]
                    turn["followup_questions"] = item.get("followup_questions", [])
                attempts.setdefault(aid, []).append((turn, run, basis))
        for aid, rows in attempts.items():
            rows.sort(key=lambda row: (row[0]["assessment_turn_index"], row[0].get("created_at") or "", row[0]["run_id"]))
            _, first, basis = rows[0]
            last_turn, last, _ = rows[-1]
            target = first.get("target") or {}
            item = latest.get(aid, {"messages": [], "findings": [], "options": [], "evidence_refs": []})
            item.update({"assessment_id": aid, "assessment_purpose": first.get("assessment_purpose", "explanation"), "target": target,
                         "researcher_note_draft": first.get("researcher_note_draft"),
                         "turns": [row[0] for row in rows], "run_id": last["run_id"], "state": last["state"],
                         "terminal_reason": last.get("terminal_reason"), "first_question": first.get("instructions", ""),
                         "created_at": first.get("created_at", ""), "updated_at": last_turn.get("updated_at") or last.get("created_at", "")})
            method = basis.get("method") or {}
            identity = method.get("identity") or {}
            item["method_label"] = method.get("name") or method.get("title") or identity.get("stable_id", "")
            item["method_version"] = identity.get("version", "")
            if basis.get("explanation_issue"):
                issue = basis["explanation_issue"]
                item.update(target_label=issue.get("title", ""), target_statement=issue.get("summary_markdown") or issue.get("question", ""),
                            responsible_role="research_lead" if first.get("assessment_purpose") == "issue_suggestions" else issue.get("responsible_role"),
                            original_role=issue.get("original_role"), source_url=issue.get("source_url"),
                            researcher_answer=issue.get("researcher_answer"))
            if basis.get("context_dialogue"):
                issue = basis["context_dialogue"]
                item.update(target_label=issue["title"], target_statement=issue["summary_markdown"],
                            responsible_role=issue["responsible_role"], scope=issue["scope"])
            refs = [ref for ref in basis.get("records", [])
                    if ref.get("branch") == target.get("branch") and ref.get("phase") == target.get("phase")
                    and ref.get("family") == target.get("family") and ref.get("generation_id") == target.get("generation_id")]
            if len(refs) == 1:
                ref = refs[0]
                path = Path(ref["snapshot_path"]) if ref.get("snapshot_path") else None
                if path and path.is_file() and sha256_file(path) == ref.get("content_sha256"):
                    document = read_json(path) or {}
                    assumptions = document.get("assumptions", []) if isinstance(document, dict) else []
                    component = next((value for value in assumptions
                                      if isinstance(value, dict) and value.get("assumption_id") == target.get("object_id")), {})
                    if not basis.get("explanation_issue"):
                        item["target_label"] = component.get("label") or component.get("title") or target.get("object_id", "")
                        item["target_statement"] = component.get("statement") or component.get("statement_markdown") or component.get("text", "")
                reference = source_ref(ref["branch"], ref["phase"], ref["family"], ref)
                item["source_url"] = record_url(project_id, reference)
            latest[aid] = item
        return sorted((item for item in latest.values()
                       if branch is None or ((item.get("target") or {}).get("kind") == "project_context" and item.get("scope", {}).get("kind") == "project")
                       or item.get("scope", {}).get("branch") == branch
                       or (item.get("target") or {}).get("branch", (item.get("target") or {}).get("branch_id")) == branch),
                      key=lambda item: item.get("updated_at", ""), reverse=True)

    async def _drive(self, record: RunRecord, stages: list[StageSpec]) -> None:
        try:
            record = await self._transition(record, RunState.RUNNING, "Stage plan starting.")
            for stage in stages:
                record = self.load_run(record.project_id, record.run_id)
                if record.stage_states.get(stage.stage_id) == "succeeded":
                    continue
                result = await self._execute_stage(record, stage)
                if self.load_run(record.project_id, record.run_id).state == RunState.AWAITING_USER:
                    return
                if not result.succeeded:
                    record = self.load_run(record.project_id, record.run_id)
                    record.terminal_reason = result.diagnostic or f"stage {stage.stage_id} failed"
                    self._save_run(record)
                    await self._transition(
                        record, RunState.FAILED, f"Stage {stage.stage_id} failed."
                    )
                    return
            record = await self._transition(record, RunState.VALIDATING, "Validating outputs.")
            findings = self._validate_run_outputs(record, stages)
            if findings or record.findings_history:
                record.findings_history.append([asdict(f) for f in findings])
                self._save_run(record)
            if any(f.blocks_publication for f in findings):
                await self._transition(
                    record, RunState.FAILED, f"Validation failed with {len(findings)} findings."
                )
                return
            if record.intent == "assessment":
                self._save_assessment(record)
                await self._transition(record, RunState.ASSESSED, "Assessment complete; scientific records unchanged.")
                return
            self._publish(record, stages)
            await self._transition(record, RunState.PUBLISHED, "Run published.")
        except asyncio.CancelledError:
            try:
                current = self.load_run(record.project_id, record.run_id)
                if (self._progressive_p4(current) and current.terminal_reason != "cancelled_by_researcher"
                        and self._p4_controller(current).snapshot().get("pause_request")):
                    await self._settle_p4_wait(current)
                    return
                await self._transition(record, RunState.CANCELLED, "Run cancelled by researcher.")
            except RunError as exc:
                current = self.load_run(record.project_id, record.run_id)
                if current.state not in TERMINAL_STATES:
                    await self._fail(current, str(exc))
        except Exception as exc:  # noqa: BLE001 - fail loud, record the reason
            await self._fail(record, str(exc))

    async def _fail(self, record: RunRecord, reason: str) -> None:
        current = self.load_run(record.project_id, record.run_id)
        if current.state in TERMINAL_STATES:
            return
        current.terminal_reason = reason
        self._save_run(current)
        await self._transition(current, RunState.FAILED, f"Run failed: {reason}")

    def _provider_retry_stage(self, record):
        """Recognize a stopped capacity failure, not a scientific correction."""
        from .bridge import is_capacity_failure
        from .p4_execution import P4Controller
        from .providers import load_provider_config
        from .execution import capture_execution, public_execution

        if (record.state != RunState.FAILED or not self._progressive_p4(record)
                or not is_capacity_failure(record.terminal_reason)):
            raise RunError("Retry is available for a capacity-interrupted evaluation step.")
        task = self._tasks.get(record.run_id)
        if (task and not task.done()) or self._active_turns.get(record.run_id):
            raise RunError("The interrupted work has not finished stopping.")
        directory = self.run_dir(record.project_id, record.run_id)
        progress = P4Controller.load_snapshot(directory) or {}
        feedback = read_json(directory / "p4-control-feedback.json") or {}
        if (not progress or progress.get("pending_batch") or progress.get("pause_request")
                or feedback.get("execution_state") == "unknown"):
            raise RunError("Inspect the pending evaluation action before retrying.")
        stage = next((s for s in self._stages(record) if record.stage_states.get(s.stage_id) != "succeeded"), None)
        entries = [read_json(path) for path in (directory / "execution").glob("*/execution.json")]
        entry = max((e for e in entries if e), key=lambda e: e.get("started_at", ""), default={})
        if (not stage or entry.get("purpose") != "scientific" or entry.get("state") != "failed"
                or not entry.get("finished_at") or entry.get("stage_id") != stage.stage_id
                or entry.get("role") != stage.roles[0].value
                or progress.get("resume_stage") != stage.stage_id
                or progress.get("resume_member") != stage.roles[0].value
                or entry.get("failure_code") not in (None, "provider.capacity", "provider.turn_failed")):
            raise RunError("The interrupted member step cannot be identified for retry.")
        # Older receipts classified the compaction wrapper as a generic failure.
        # Like untyped receipts, they need the exact stopped turn read below.
        if entry.get("failure_code") != "provider.capacity" and (not (entry.get("acknowledgement") or {}).get("turn_id")
                or not callable(getattr(self.bridge, "confirm_capacity_failure", None))):
            raise RunError("The previous member turn needs an exact terminal-state check before retrying.")
        if entry.get("failure_code") == "provider.capacity" and entry.get("thread_id") in getattr(self.bridge, "_quarantined", set()):
            raise RunError("The previous member turn has not been confirmed stopped. Restart the local service before retrying.")
        if not (directory / "contracts").is_dir() or not (directory / "stage-plan.json").is_file():
            raise RunError("This run did not retain its frozen inputs; start a new evaluation.")
        if self._catalog(record).verify_manifest():
            raise RunError("The run's frozen catalog is damaged.")
        basis = read_json(directory / "basis.json") or {}
        if basis.get("sha256") != record.basis_sha256:
            raise RunError("The run's frozen basis identity changed.")
        for ref in [*basis.get("records", []), *basis.get("artifacts", [])]:
            source = Path(ref.get("snapshot_path") or ref.get("path") or "")
            if not source.is_file() or sha256_file(source) != ref.get("content_sha256"):
                raise RunError("A frozen research source is unavailable or changed.")
        for ref in basis.get("cumulative_inputs", {}).values():
            source = Path(ref.get("snapshot_path") or "")
            if not source.is_file() or self._cumulative_digest(read_json(source)) != ref.get("sha256"):
                raise RunError("A frozen cumulative source is unavailable or changed.")
        self._assert_phase_available(record.project_id, record.phase, record.branch_id, excluding=record.run_id)
        self._assert_publication_current(record)
        if self._p4_context_changes(record):
            raise RunError("Research context changed; start a new evaluation against the current context.")
        role = stage.roles[0]
        provider = load_provider_config(self.data_root)
        provider.require_ready(role.value)
        config = read_json(self.project_dir(record.project_id) / "members" / role.value / "config.json") or {}
        home = codex_home(self.project_dir(record.project_id), role)
        resolved = provider.resolve_member(config, role.value, home)
        selected = public_execution(capture_execution(resolved.config, home, resolved.environment, resolved.strip_keys))
        keys = ("model", "reasoning_effort", "provider", "provider_id", "provider_base_url", "provider_env_key")
        if any(selected.get(key) != entry.get("submitted", {}).get(key) for key in keys):
            raise RunError("Member model or provider settings changed; restore them or start a new evaluation.")
        return stage, entry

    def provider_retry_preview(self, record):
        from .bridge import is_capacity_failure
        kind = "provider.capacity" if record.phase == "P4" and is_capacity_failure(record.terminal_reason) else None
        try:
            self._provider_retry_stage(record)
        except (RunError, CatalogError, ArtifactError, ValueError, OSError) as exc:
            return {"eligible": False, "reason": str(exc), "failure_code": kind}
        return {"eligible": True, "reason": None, "failure_code": kind}

    async def retry_provider(self, project_id, run_id):
        if self.shutting_down:
            raise RunError("The local service is shutting down.")
        async with self._lock(f"continue:{run_id}"):
            record = self.load_run(project_id, run_id)
            stage, entry = self._provider_retry_stage(record)
            confirmation = None
            if entry.get("failure_code") != "provider.capacity":
                from .providers import load_provider_config
                from .execution import capture_execution
                role = stage.roles[0]
                home = codex_home(self.project_dir(project_id), role)
                config = read_json(self.project_dir(project_id) / "members" / role.value / "config.json") or {}
                resolved = load_provider_config(self.data_root).resolve_member(config, role.value, home)
                execution = capture_execution(resolved.config, home, resolved.environment, resolved.strip_keys)
                try:
                    confirmation = await self.bridge.confirm_capacity_failure(entry["thread_id"], entry["acknowledgement"]["turn_id"],
                        member_home=home, execution=execution, workspace_root=self.workspace_root(home))
                except Exception as exc:
                    raise RunError("Retry did not start: " + str(exc)) from exc
                # A source or another run can change while the read awaits.
                record = self.load_run(project_id, run_id)
                stage, entry = self._provider_retry_stage(record)
            self._event(record, "run.provider_retry", "Retrying the interrupted member step with saved work and remaining budget.",
                        stage=stage.stage_id, previous_reason=record.terminal_reason,
                        previous_execution_id=entry["execution_id"], terminal_confirmation=confirmation)
            record.stage_states[stage.stage_id] = "pending"
            record.terminal_reason = None
            record.state = RunState.REQUESTED
            record.updated_at = _now()
            self._save_run(record)
            self._tasks[run_id] = asyncio.create_task(self._drive(record, self._stages(record)))
            self._task_projects[run_id] = project_id
            return record

    def _save_assessment(self, record: RunRecord) -> None:
        run_dir = self.run_dir(record.project_id, record.run_id)
        doc = read_json(run_dir / "outputs" / "p3.assessment" / "assessment.json")
        previous = read_json(run_dir / "previous-assessment.json") or {}
        summary = doc.get("summary") or doc.get("headline") or "Assessment complete"
        content = doc.get("assessment_markdown") or doc.get("summary") or json.dumps(doc, ensure_ascii=False)
        if record.assessment_purpose in ("project_context", "model_dialogue") and (record.target or {}).get("kind") != "report_section":
            from .problem_context import propose_context_amendment, load_problem_context
            basis = read_json(run_dir / "basis.json") or {}
            issue = basis.get("context_dialogue") or basis.get("explanation_issue") or {}
            default_scope = issue.get("scope") or ({"kind": "project"} if record.assessment_purpose == "project_context"
                else {"kind": "model", "branch": record.branch_id, "model_ref": (basis.get("method") or {}).get("identity", {})})
            proposals = []
            for proposal in doc.get("proposed_context_amendments", []):
                current = load_problem_context(self.project_dir(record.project_id))
                if proposal.get("statement"):
                    # Confirming a paraphrase cannot widen a model-specific
                    # response. Researchers add shared requirements directly.
                    proposal_scope = (default_scope if default_scope.get("kind") == "model"
                                      else proposal.get("scope") or default_scope)
                    goal_ref = issue.get("goal_source_ref")
                    proposal_sources = proposal.get("source_refs", [])
                    if goal_ref and goal_ref not in proposal_sources:
                        proposal_sources = [*proposal_sources, goal_ref]
                    saved = propose_context_amendment(self.project_dir(record.project_id), proposal["statement"],
                        expected_revision=current["revision"], item_id=proposal.get("item_id"),
                        origin=proposal.get("origin", "proposed_assumption"), scope=proposal_scope,
                        source_refs=[{"kind": "discussion", "run_id": record.run_id, "target": record.target}, *proposal_sources],
                        answer_refs=proposal.get("answer_refs", []), amends=proposal.get("amends", []),
                        reason=proposal.get("reason", ""), conflicts_with=proposal.get("conflicts_with"),
                        topic="research_goal" if goal_ref else proposal.get("topic"))
                    proposals.append(saved["proposals"][-1])
            doc["context_proposals"] = proposals
        messages = list(previous.get("messages", [])) + [
            {"role": "user", "content": record.instructions, "run_id": record.run_id,
             **({"researcher_note_draft": record.researcher_note_draft} if record.researcher_note_draft is not None else {})},
            {"role": "assistant", "content": content, "run_id": record.run_id, "evidence_refs": doc.get("evidence_refs", [])},
        ]
        write_json_atomic(run_dir / "assessment.json", {
            **doc, "assessment_id": record.assessment_id, "target": record.target,
            "assessment_purpose": record.assessment_purpose,
            "assessment_turn_index": record.assessment_turn_index,
            "messages": messages, "summary": summary,
            "findings": doc.get("findings", []),
            "options": doc.get("options", doc.get("suggested_actions", [])),
            "created_at": previous.get("created_at", record.created_at), "updated_at": _now(),
            "run_id": record.run_id, "state": "assessed",
        })

    async def _execute_stage(self, record: RunRecord, stage: StageSpec) -> StageResult:
        if self._progressive_p4(record):
            return await self._execute_p4_stage(record, stage)
        record.stage_states[stage.stage_id] = "running"
        self._save_run(record)
        self._event(record, "stage.running", f"Stage {stage.stage_id} running.")
        run_dir = self.run_dir(record.project_id, record.run_id)
        from .p1_science import reconciliation_enabled
        catalog = self._catalog(record)
        phase_contract = read_json(catalog.root / "contracts" / "phases" / f"{record.phase}.json") or {}
        native_preflight = ((record.phase == "P1" and reconciliation_enabled(catalog=catalog))
                            or "native_tool_preflight_v1" in phase_contract.get("capabilities", []))
        if native_preflight and callable(getattr(self.bridge, "check_native_tools", None)):
            checks = await asyncio.gather(*[self._drive_member_turn(record, stage, role, run_dir, prepare_only=True)
                                            for role in stage.roles], return_exceptions=True)
            failed = [str(check) if isinstance(check, BaseException) else check.diagnostic for check in checks
                      if isinstance(check, BaseException) or not check.succeeded]
            if failed:
                record = self.load_run(record.project_id, record.run_id)
                record.stage_states[stage.stage_id] = "failed"
                record.findings_history.append([asdict(Finding("runtime.native_tools_unavailable", message, stage.stage_id, "")) for message in failed])
                self._save_run(record)
                return StageResult(stage_id=stage.stage_id, succeeded=False, diagnostic="; ".join(failed))
        if (stage.stage_id == "p5.parallel_reviews"
                and frozen_review_packet_enabled(self._catalog(record))):
            prepare_review_packet(run_dir, basis=read_json(run_dir / "basis.json") or {},
                                  instructions=record.instructions, run_id=record.run_id,
                                  project_dir=self.project_dir(record.project_id))
        results = await asyncio.gather(
            *[
                self._drive_member_turn(record, stage, role, run_dir)
                for role in stage.roles
            ],
            return_exceptions=True,  # one member's crash must not orphan siblings
        )
        clean: list[StageResult] = []
        for role, r in zip(stage.roles, results):
            if isinstance(r, BaseException):
                self._event(
                    record, "member.crashed",
                    f"{role.value} turn raised: {r}",
                    stage=stage.stage_id, role=role.value,
                )
                clean.append(StageResult(
                    stage_id=stage.stage_id, succeeded=False, diagnostic=str(r),
                ))
            else:
                clean.append(r)
        results = clean
        ok = all(r.succeeded for r in results)
        record = self.load_run(record.project_id, record.run_id)
        # Do not hand off missing outputs after a failed SDK turn. Successful
        # turns additionally pass the same applicable checks as publication.
        missing = self._validate_required_outputs(record, [stage])
        if missing and not ok:
            record.findings_history.append([asdict(f) for f in missing])
        # A5: usage capture (design/05 §5) — per-role usage per stage,
        # summed into the run total for the rate-pool panel.
        per_role = {role.value: r.usage for role, r in zip(stage.roles, results) if r.usage}
        if per_role:
            write_json_atomic(run_dir / "workspaces" / stage.stage_id / "usage.json", per_role)
            for usage in per_role.values():
                # Spend = per-turn DELTAS. The `input_tokens`/`output_tokens`
                # keys are cumulative per-thread snapshots (rotation thresholds
                # use those); summing them would double count shared threads.
                in_delta = usage.get("turn_input_tokens", usage.get("input_tokens")) or 0
                out_delta = usage.get("turn_output_tokens", usage.get("output_tokens")) or 0
                record.usage["input_tokens"] = record.usage.get("input_tokens", 0) + in_delta
                record.usage["output_tokens"] = record.usage.get("output_tokens", 0) + out_delta
                window = usage.get("model_context_window")
                if isinstance(window, (int, float)):
                    record.usage["model_context_window"] = max(
                        record.usage.get("model_context_window", 0), window
                    )
                cumulative = usage.get("input_tokens")
                if isinstance(cumulative, (int, float)):
                    record.usage["thread_cumulative_input_max"] = max(
                        record.usage.get("thread_cumulative_input_max", 0), cumulative
                    )
        self._save_run(record)
        if ok:
            if supports_problem_context(self._catalog(record)) and eligible_stage(record, stage):
                workspace = self.member_workspace(record, stage.stage_id, stage.roles[0])
                authored = self._authored_researcher_question(record, stage, workspace)
                if authored:
                    ResearcherPauseStore(run_dir).request(record, stage, authored, read_json(run_dir / "basis.json") or {})
                    record.stage_states[stage.stage_id] = "awaiting_user"
                    self._save_run(record)
                    await self._transition(record, RunState.AWAITING_USER, "Work is waiting for your response.")
                    return StageResult(stage_id=stage.stage_id, succeeded=True, diagnostic="Waiting for researcher input")
            ok, diagnostic = await self._check_stage_delivery(record, stage)
            record = self.load_run(record.project_id, record.run_id)
        else:
            diagnostic = next((r.diagnostic for r in results if not r.succeeded), "")
        record.stage_states[stage.stage_id] = "succeeded" if ok else "failed"
        self._save_run(record)
        self._event(
            record,
            "stage.finished",
            f"Stage {stage.stage_id} {'succeeded' if ok else 'failed'}.",
        )
        return StageResult(
            stage_id=stage.stage_id,
            succeeded=ok,
            diagnostic=diagnostic or ("; ".join(f.message for f in missing) if not ok else ""),
        )

    async def _check_stage_delivery(self, record: RunRecord, stage: StageSpec) -> tuple[bool, str]:
        """Check handoffs and return bounded mechanical feedback to authors."""
        directory = self.run_dir(record.project_id, record.run_id)
        prerequisites = [s for s in self._stages(record) if s.sequence < stage.sequence
                         and record.stage_states.get(s.stage_id) == "succeeded"]
        preceding = None
        while True:
            if self._progressive_p4(record) and self._p4_controller(record).snapshot().get("pause_request"):
                return False, "Waiting for researcher direction"
            findings = self._validate_run_outputs(record, [stage], prerequisites)
            blockers = [f for f in findings if f.blocks_publication]
            record = self.load_run(record.project_id, record.run_id)
            if findings or record.findings_history:
                record.findings_history.append([asdict(f) for f in findings])
            self._save_run(record)
            self._event(record, "stage.validation",
                        f"Artifact checks {'passed' if not blockers else 'found ' + str(len(blockers)) + ' issues'} before handoff.",
                        stage=stage.stage_id, findings=[asdict(f) for f in findings])
            state = self._artifact_check_state(record, stage, stage.writes,
                                              directory / "outputs" / stage.stage_id, findings)
            previous_result = None
            if preceding is not None:
                previous_result = self._repair_result(preceding["state"], state, preceding["attempt"])
                write_json_atomic(preceding["archive"] / "result.json", previous_result)
            if not blockers:
                return True, ""
            if previous_result and previous_result["unchanged"]:
                message = "Automatic repair stopped because the affected files, findings, and frozen evidence are unchanged."
                self._event(record, "stage.mechanical_repair_stopped", message,
                            stage=stage.stage_id, attempt=preceding["attempt"], reason="unchanged_failure")
                return False, message + " " + "; ".join(f.message for f in blockers)
            scope = {f.object_id for f in blockers}
            owners = [role for role in stage.roles if scope.intersection(owned_writes(stage, role))]
            attempts = record.mechanical_repair_attempts.get(stage.stage_id, 0)
            if (not scope.issubset(set(stage.writes)) or not owners
                    or attempts >= self._MAX_MECHANICAL_REPAIRS):
                return False, "; ".join(f.message for f in blockers)
            attempt = attempts + 1
            archive = directory / "mechanical-repairs" / stage.stage_id / f"attempt-{attempt}"
            archive.mkdir(parents=True, exist_ok=False)
            out_dir = directory / "outputs" / stage.stage_id
            if out_dir.is_dir():
                shutil.copytree(out_dir, archive / "outputs", symlinks=True)
            for role in stage.roles:
                brief = directory / "briefs" / f"{stage.stage_id}.{role.value}.md"
                if brief.is_file():
                    shutil.copyfile(brief, archive / brief.name)
            write_json_atomic(archive / "findings.json", {"attempt": attempt, "scope": sorted(scope),
                              "findings": [asdict(f) for f in findings]})
            before = {}
            for output_id in stage.writes:
                suffix = output_id.split(".", 1)[-1]
                path = out_dir / (suffix + (".jsonl" if suffix == "metrics_long" else ".json"))
                before[output_id] = (path, path.read_bytes() if path.is_file() else None)
            record.mechanical_repair_attempts[stage.stage_id] = attempt
            record.stage_states[stage.stage_id] = "correcting"
            self._save_run(record)
            self._event(record, "stage.mechanical_repair",
                        f"The original authors are fixing artifact consistency before handoff (attempt {attempt} of {self._MAX_MECHANICAL_REPAIRS}).",
                        stage=stage.stage_id, outputs=sorted(scope), attempt=attempt)
            repair_tasks = []
            try:
                # Parallel authors remain independent. They receive exact
                # conflicting entries only after all initial submissions finish.
                for role in owners:
                    allowed = scope.intersection(owned_writes(stage, role))
                    self._mechanical_repairs[(record.run_id, stage.stage_id, role.value)] = {
                        "outputs": sorted(allowed),
                        "findings": [asdict(f) for f in findings if f.object_id in allowed],
                        "attempt": attempt,
                        "original_brief": str(directory / "mechanical-repairs" / stage.stage_id
                                              / "attempt-1" / f"{stage.stage_id}.{role.value}.md"),
                        "previous_attempt": self._member_repair_result(previous_result, stage, role),
                    }
                preceding = {"state": state, "attempt": attempt, "archive": archive}
                repair_tasks = [asyncio.create_task(self._drive_member_turn(record, stage, role, directory))
                                for role in owners]
                results = await asyncio.gather(*repair_tasks, return_exceptions=True)
            finally:
                for role in owners:
                    self._mechanical_repairs.pop((record.run_id, stage.stage_id, role.value), None)
                # Preserve completed siblings' spend even if another author is
                # interrupted. No downstream work starts until all have ended.
                record = self.load_run(record.project_id, record.run_id)
                for task in repair_tasks:
                    if task.done() and not task.cancelled() and task.exception() is None:
                        for name in ("input_tokens", "output_tokens"):
                            record.usage[name] = record.usage.get(name, 0) + task.result().usage.get("turn_" + name, 0)
                self._save_run(record)
            for output_id, (path, original) in before.items():
                if output_id not in scope and (path.read_bytes() if path.is_file() else None) != original:
                    raise RunError(f"Mechanical repair changed an out-of-scope output: {output_id}")
            failed = next((r for r in results if isinstance(r, BaseException) or not r.succeeded), None)
            if failed is not None:
                return False, str(failed) if isinstance(failed, BaseException) else failed.diagnostic or "Mechanical repair turn failed"

    @staticmethod
    def _referenced_paths(value):
        """Explicit file references only, never a workspace or cache scan."""
        if isinstance(value, dict):
            for name, item in value.items():
                if name in {"path", "artifact_path", "snapshot_path", "regenerated_by"} and isinstance(item, str) and item:
                    yield item
                elif isinstance(item, (dict, list)):
                    yield from RunEngine._referenced_paths(item)
        elif isinstance(value, list):
            for item in value:
                yield from RunEngine._referenced_paths(item)

    def _artifact_fingerprints(self, directory: Path, outputs, roles=()) -> dict:
        files = {}
        root = directory.resolve()
        for output in sorted(outputs):
            path = directory / self._output_filename(output)
            if not path.resolve().is_relative_to(root):
                files[path.name] = None
                continue
            files[path.name] = sha256_file(path) if path.is_file() else None
            if not path.is_file():
                continue
            try:
                documents = ([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                             if path.suffix == ".jsonl" else [read_json(path)])
            except (OSError, ValueError):
                continue
            for reference in self._referenced_paths(documents):
                relative = Path(reference)
                if relative.is_absolute() or ".." in relative.parts:
                    continue
                candidates = [directory / relative] + [directory / "working" / role.value / relative for role in roles]
                for source in candidates:
                    if source.resolve().is_relative_to(root):
                        files[source.relative_to(directory).as_posix()] = sha256_file(source) if source.is_file() else None
        return files

    def _artifact_check_state(self, record, stage, outputs, directory, findings, role=None) -> dict:
        run_dir = self.run_dir(record.project_id, record.run_id)
        # The manifest and its explicit references are frozen for this run.
        # A reviewer has only its submission packet, even during recovery.
        manifest = run_dir / ("review-packet/manifest.json" if role is MemberRole.OUTSIDE_REVIEWER else "basis.json")
        evidence = {str(manifest): sha256_file(manifest) if manifest.is_file() else None}
        document = read_json(manifest) or {}
        for reference in self._referenced_paths(document):
            path = Path(reference)
            if not path.is_absolute():
                path = manifest.parent / path
            if path.resolve().is_relative_to(run_dir.resolve()):
                evidence[str(path)] = sha256_file(path) if path.is_file() else None
        readable = set(stage.role_reads.get(role.value, stage.reads)) if role else None
        for prior in self._stages(record):
            if prior.sequence >= stage.sequence or record.stage_states.get(prior.stage_id) != "succeeded":
                continue
            permitted = [output for output in prior.writes if readable is None or output in readable]
            if role is MemberRole.OUTSIDE_REVIEWER:
                permitted = []
            for name, digest in self._artifact_fingerprints(run_dir / "outputs" / prior.stage_id, permitted, prior.roles).items():
                evidence[f"{prior.stage_id}/{name}"] = digest
        details = [asdict(f) if isinstance(f, Finding) else f for f in findings]
        return {"files": self._artifact_fingerprints(directory, outputs, stage.roles if role is None else ()),
                "findings": sorted(details, key=lambda f: json.dumps(f, sort_keys=True)),
                "evidence_sha256": sha256_bytes(json.dumps(evidence, sort_keys=True).encode("utf-8"))}

    @staticmethod
    def _repair_result(before, after, attempt):
        old = {json.dumps(f, sort_keys=True): f for f in before["findings"]}
        new = {json.dumps(f, sort_keys=True): f for f in after["findings"]}
        return {"attempt": attempt, "unchanged": before == after,
                "changed_files": [{"path": name, "before_sha256": before["files"].get(name),
                                   "after_sha256": after["files"].get(name)}
                                  for name in sorted(before["files"].keys() | after["files"].keys())
                                  if before["files"].get(name) != after["files"].get(name)],
                "resolved_findings": [old[key] for key in sorted(old.keys() - new.keys())],
                "remaining_findings": [new[key] for key in sorted(old.keys() & new.keys())],
                "new_findings": [new[key] for key in sorted(new.keys() - old.keys())],
                "evidence_changed": before["evidence_sha256"] != after["evidence_sha256"]}

    def _member_repair_result(self, result, stage, role):
        if result is None:
            return None
        owned = set(owned_writes(stage, role))
        filenames = {self._output_filename(output) for output in owned}
        return {**result,
                "changed_files": [change for change in result["changed_files"]
                                  if change["path"] in filenames or change["path"].startswith(f"working/{role.value}/")],
                **{name: [finding for finding in result[name] if finding.get("object_id") in owned]
                   for name in ("resolved_findings", "remaining_findings", "new_findings")}}

    async def _drive_member_turn(
        self, record: RunRecord, stage: StageSpec, role: MemberRole, run_dir: Path, *, prepare_only=False
    ) -> StageResult:
        identity = (record.project_id, role.value,
                    "PROJECT" if role == MemberRole.RESEARCH_LEAD else record.phase,
                    "trunk" if role == MemberRole.RESEARCH_LEAD else record.branch_id)
        if record.intent == "assessment" or role == MemberRole.OUTSIDE_REVIEWER:
            identity += (record.run_id,)
        async with self._thread_locks.setdefault(":".join(identity), asyncio.Lock()):
            return await self._drive_member_turn_locked(record, stage, role, run_dir, prepare_only=prepare_only)

    def _matching_thread_web_tools(self, thread_id, execution, registration=None, run_dir=None) -> bool:
        """App-server tool declarations persist for the lifetime of a thread."""
        from .kimi_web import uses_kimi_web
        from .member_tools import member_tools_marker
        if registration is not None and registration.thread_id == thread_id:
            previous = registration.execution
        else:
            getter = getattr(self.bridge, "execution_configuration", None)
            previous = getter(thread_id) if getter else {}
            # Corrections can refer to an older thread than the current registry.
            if not previous and run_dir is not None:
                entries = [read_json(path) for path in (run_dir / "execution").glob("*/execution.json")]
                matching = [entry for entry in entries if entry and entry.get("thread_id") == thread_id]
                previous = max(matching, key=lambda entry: entry.get("started_at", ""), default={}).get("acknowledgement", {})
        installed = (previous.get("web_retrieval") or {}).get("transport") == "kimi_code_search_fetch"
        member_tools = previous.get("member_tools") or {}
        expected = member_tools_marker(execution) if execution.get("p4_managed_execution") else member_tools_marker()
        return installed == uses_kimi_web(execution) and member_tools == expected

    async def _drive_member_turn_locked(
        self, record: RunRecord, stage: StageSpec, role: MemberRole, run_dir: Path, *, prepare_only=False
    ) -> StageResult:
        branch = record.branch_id
        key = ThreadKey(member=role, phase=record.phase, branch_id=branch)
        if role == MemberRole.RESEARCH_LEAD:
            key = ThreadKey(member=role, phase="PROJECT", branch_id="trunk")
        project_dir = self.project_dir(record.project_id)
        config_doc = read_json(project_dir / "members" / role.value / "config.json") or {}
        from .providers import load_provider_config
        provider_config = load_provider_config(self.data_root)
        provider_config.require_ready(role.value)
        self._apply_saved_provider_account(provider_config, project_dir, role)
        resolved = provider_config.resolve_member(config_doc, role.value, codex_home(project_dir, role))
        config_doc = resolved.config
        isolated = record.intent == "assessment" or role == MemberRole.OUTSIDE_REVIEWER
        member_home = self._member_home(record, role)
        if isolated:
            key = ThreadKey(member=role, phase=f"{record.phase}.{record.run_id}", branch_id=branch)
            member_home.mkdir(parents=True, exist_ok=True)
            for name in ("config.toml", "AGENTS.md", "auth.json"):
                source = codex_home(project_dir, role) / name
                if source.is_file():
                    shutil.copyfile(source, member_home / name)
            config_doc = {**config_doc, "auto_compact_tokens": 0, "max_turn_input_tokens": 0}
        from .execution import capture_execution, public_execution
        execution = capture_execution(config_doc, member_home, resolved.environment, resolved.strip_keys)
        if self._progressive_p4(record):
            execution["p4_managed_execution"] = True
        workspace_root = self.workspace_root(member_home)
        workspace = self.member_workspace(record, stage.stage_id, role)
        workspace.mkdir(parents=True, exist_ok=True)
        if self._progressive_p4(record):
            from .p4_execution import ensure_workspace_owner_access
            ensure_workspace_owner_access(workspace, owned_root=workspace_root)
        thread_id = record.thread_ids.get(key.as_string())
        if thread_id is not None:
            # A correction reuses its run's thread, but settings still apply to
            # this next turn, including a changed member soul or provider.
            registration = self._registry(record.project_id, key.branch_id).lookup(key)
            if (not self._matching_thread_web_tools(thread_id, execution, registration, run_dir)
                    or not await self.bridge.resume_thread(thread_id, member_home=member_home, execution=execution, workspace_root=workspace_root)):
                thread_id = None
        if thread_id is None:
            # A1: persistent threads (design/04 §4) — resume the registered
            # thread if the harness still knows it; otherwise mint + register.
            # The member ownership lock protects this key while native setup
            # awaits. Keep the branch lock limited to registry reads/mutations
            # so a slow member does not hold up other members' startup.
            async with self._registry_lock(record.project_id, key.branch_id):
                registry = self._registry(record.project_id, key.branch_id)
                registry.reload()
                reg = registry.lookup(key) if not isolated else None
            compatible = reg is None or self._matching_thread_web_tools(reg.thread_id, execution, reg, run_dir)
            if reg is not None and compatible and await self.bridge.resume_thread(reg.thread_id, member_home=member_home, execution=execution, workspace_root=workspace_root):
                thread_id = reg.thread_id
                self._event(
                    record,
                    "thread.resumed",
                    f"Resumed {role.value} thread ({reg.turns} prior turns).",
                    stage=stage.stage_id,
                    role=role.value,
                )
            else:
                if reg is not None and not compatible:
                    self._event(record, "thread.tools_changed", f"Started a fresh {role.value} thread because its research tools changed.",
                                stage=stage.stage_id, role=role.value)
                thread_id = await self.bridge.ensure_thread(
                    key,
                    member_home=member_home,
                    model=config_doc.get("model", "gpt-6.1-sol"),
                    reasoning_effort=config_doc.get("reasoning_effort", "xhigh"),
                    execution=execution,
                    workspace_root=workspace_root,
                )
                async with self._registry_lock(record.project_id, key.branch_id):
                    registry.reload()
                    registry.register(key, thread_id)
            record.thread_ids[key.as_string()] = thread_id
            self._save_run(record)
        if prepare_only:
            try:
                report = await self.bridge.check_native_tools(thread_id, workspace)
                if not isinstance(report, dict) or report.get("status") != "passed":
                    raise RuntimeError("The native command/write check did not confirm availability.")
            except Exception as error:
                report = {"status": "failed", "coverage": "sandboxed-command-write-read-delete", "native_editing": "unverified",
                          "workspace": str(workspace), "model_turns": 0, "diagnostic": str(error)}
                write_json_atomic(run_dir / "native-checks" / stage.stage_id / (role.value + ".json"), report)
                return StageResult(stage_id=stage.stage_id, succeeded=False, diagnostic=f"{role.value}: {report['diagnostic']}")
            write_json_atomic(run_dir / "native-checks" / stage.stage_id / (role.value + ".json"), report)
            self._event(record, "member.native_check", f"{role.value} native command/write check passed before research.", stage=stage.stage_id, role=role.value)
            return StageResult(stage_id=stage.stage_id, succeeded=True)
        brief = run_dir / "briefs" / f"{stage.stage_id}.{role.value}.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text(
            self._render_brief(record, stage, role, workspace), encoding="utf-8"
        )
        # Advisory only (D8): report the assembled size, never refuse.
        self._event(
            record,
            "brief.assembled",
            f"Brief for {role.value}: {brief.stat().st_size:,} B.",
            stage=stage.stage_id,
            role=role.value,
        )

        def heartbeat(activity: str) -> None:
            self._event(record, "heartbeat", activity, stage=stage.stage_id, role=role.value)

        async def configured_turn(brief_path, turn_workspace, purpose, turn_execution):
            # This entire helper runs while the shared thread's ownership lock
            # remains held, including SDK interruption and terminal confirmation.
            entry_id = new_id("execution")
            entry_dir = run_dir / "execution" / entry_id
            entry_dir.mkdir(parents=True, exist_ok=True)
            (entry_dir / "instructions.md").write_bytes(turn_execution["instructions"].encode("utf-8"))
            getter = getattr(self.bridge, "execution_configuration", None)
            acknowledgement = getter(thread_id) if getter else {}
            entry = {"execution_id": entry_id, "run_id": record.run_id, "thread_id": thread_id,
                     "stage_id": stage.stage_id, "role": role.value, "purpose": purpose,
                     "correction_attempt": record.correction_attempts, "started_at": _now(),
                     "workspace": str(turn_workspace), "workspace_root": str(workspace_root),
                     "brief_sha256": sha256_file(brief_path), "instructions_path": "instructions.md",
                     "submitted": public_execution(turn_execution), "acknowledgement": acknowledgement,
                     "state": "running"}
            write_json_atomic(entry_dir / "execution.json", entry)
            async with self._registry_lock(record.project_id, key.branch_id):
                registry = self._registry(record.project_id, key.branch_id)
                registry.reload()
                registry.note_execution(key, acknowledgement)
            self._event(record, "turn.configured", f"Applied {role.value} settings for this turn.",
                        stage=stage.stage_id, role=role.value, execution_id=entry_id)
            self._active_turns.setdefault(record.run_id, set()).add(thread_id)
            try:
                previous_check = None
                def validate_artifacts():
                    nonlocal previous_check
                    report = self.validate_member_artifacts(record, stage, role, turn_workspace)
                    if report["status"] == "failed":
                        state = self._artifact_check_state(record, stage, report["checked_outputs"],
                                                           turn_workspace, report["findings"], role)
                        if state == previous_check:
                            report["recovery"] = {
                                "code": "artifact_check.unchanged_failure", "unchanged": True,
                                "stop_requested": True,
                                "message": "The same failing artifacts were checked again without changed files or evidence. "
                                           "End this turn and retain the findings for scoped repair or researcher direction.",
                            }
                        previous_check = state
                    else:
                        previous_check = None
                    self._event(record, "member.artifact_check",
                                f"{role.value} checked its draft artifacts: {report['status']}.",
                                stage=stage.stage_id, role=role.value,
                                status=report["status"], finding_count=len(report.get("findings", [])),
                                recovery=report.get("recovery"))
                    return report

                control = {}
                if self._progressive_p4(record) and purpose != "handoff":
                    from .p4_execution import P4ExecutionError, P4RequestRejected
                    from .member_tools import tool_failure_feedback
                    from .p4_lifecycle import _work_progress
                    from .execution import redact_execution_text
                    controller = self._p4_controller(record, stage, role)
                    previous_control = None
                    unknown_feedback = None
                    def save_feedback(report):
                        nonlocal unknown_feedback
                        safe = json.loads(redact_execution_text(turn_execution, json.dumps(report, ensure_ascii=False)))
                        # A later result from this turn cannot establish the
                        # outcome of an earlier request whose response failed.
                        if unknown_feedback is None and safe.get("execution_state") == "unknown":
                            unknown_feedback = safe
                        write_json_atomic(run_dir / "p4-control-feedback.json", unknown_feedback or safe)
                        return safe
                    def checkpoint(arguments):
                        operation = arguments.get("operation") if isinstance(arguments, dict) else None
                        try:
                            if unknown_feedback is not None:
                                raise P4RequestRejected("An earlier operation in this turn has an unconfirmed outcome.",
                                    code="prior_execution_outcome_unknown",
                                    hint="End this turn and inspect the saved request, pending batch and ledger before authorizing another operation.")
                            if (operation == "complete" and role is MemberRole.DATA_ANALYST
                                    and self._catalog(record).schema_for_output("p4.implementation_record_candidate")
                                    == "implementation-record.schema.json"):
                                draft = validate_artifacts()
                                if draft["status"] != "passed":
                                    if draft["status"] == "unavailable":
                                        raise P4RequestRejected("Artifact validation could not complete. No completion request was accepted.",
                                            code="validation_unavailable", hint="Restore validation access and check the saved artifacts again; do not rewrite scientific content to fix this setup problem.")
                                    blockers = [Finding(**finding) for finding in draft.get("findings", [])
                                                if finding.get("blocks_publication", True)]
                                    messages = "; ".join(finding.message for finding in blockers[:5])
                                    raise P4RequestRejected("Complete requires accepted analyst draft artifacts. " + messages,
                                        code="draft_invalid", json_pointer=blockers[0].json_pointer if blockers else "",
                                        findings=blockers,
                                        hint="Correct the named artifact findings, validate again, then request completion.")
                            report = controller.request(arguments)
                        except Exception as exc:
                            report = exc.feedback(operation) if isinstance(exc, P4ExecutionError) else tool_failure_feedback(operation, exc)
                        report = save_feedback(report)
                        if report.get("accepted") is True:
                            self._event(record, "p4.control_accepted", f"Saved {operation} request.", stage=stage.stage_id, role=role.value, operation=operation)
                        else:
                            self._event(record, "p4.control_rejected" if report.get("accepted") is False else "p4.control_unknown",
                                        report.get("error", "The operation outcome needs inspection."), stage=stage.stage_id, role=role.value, operation=operation)
                        return report
                    def tool_feedback(tool, arguments, report):
                        nonlocal previous_control
                        if tool != "p4_checkpoint":
                            return None
                        # This also records dispatcher-level argument failures,
                        # which never entered the controller callback.
                        report = save_feedback(report)
                        if unknown_feedback is not None:
                            return {"code": "execution_outcome_unknown", "stop_requested": True, "message": unknown_feedback.get("error")}
                        checkpoint_only = report.get("accepted") is True and report.get("operation") == "checkpoint"
                        if report.get("accepted") is not False and not checkpoint_only:
                            previous_control = None
                            return None
                        files = {}
                        if isinstance(arguments, dict):
                            for field in ("protocol_path", "script_path"):
                                value = arguments.get(field)
                                if isinstance(value, str):
                                    path = (turn_workspace / value).resolve()
                                    if path.is_relative_to(turn_workspace.resolve()) and path.is_file():
                                        files[field] = sha256_file(path)
                        draft_state = (self._artifact_check_state(record, stage, owned_writes(stage, role),
                                                                 turn_workspace, report.get("findings", []), role)
                                       if report.get("operation") == "complete" and report.get("code") == "draft_invalid" else None)
                        state = (_work_progress(controller.snapshot()), files, draft_state,
                                 None if checkpoint_only else json.dumps(arguments, sort_keys=True),
                                 None if checkpoint_only else (report.get("code"), report.get("json_pointer"), report.get("error")))
                        repeated = previous_control == state
                        previous_control = state
                        if repeated:
                            recovery = {"code": "control.unchanged_request", "stop_requested": True,
                                        "message": "The same control request made no progress. End this turn and use the saved feedback before another attempt."}
                            save_feedback({**report, "recovery": recovery})
                            return recovery
                        return None
                    control["p4_checkpoint"] = checkpoint
                    control["tool_feedback"] = tool_feedback
                result = await self.bridge.run_turn(thread_id, brief_path=brief_path, workspace=turn_workspace,
                                                    heartbeat=heartbeat, execution=turn_execution,
                                                    validate_artifacts=validate_artifacts if purpose != "handoff" else None,
                                                    **control)
                entry["state"] = "completed" if result.succeeded else "failed"
                return result
            except asyncio.CancelledError:
                entry["state"] = "cancelled"
                raise
            except Exception as exc:
                entry["state"] = "failed"
                from .bridge import TerminalTurnFailure
                if isinstance(exc, TerminalTurnFailure):
                    entry["failure_code"] = exc.code
                if asyncio.current_task().cancelling():
                    self._cancellation_failures[record.run_id] = str(exc)
                raise
            finally:
                entry["finished_at"] = _now()
                entry["acknowledgement"] = getter(thread_id) if getter else acknowledgement
                write_json_atomic(entry_dir / "execution.json", entry)
                self._active_turns.get(record.run_id, set()).discard(thread_id)

        # Cumulative thread totals BEFORE this turn (for exact delta spend).
        async with self._registry_lock(record.project_id, key.branch_id):
            registry = self._registry(record.project_id, key.branch_id)
            registry.reload()
            prior_reg = registry.lookup(key)
            prev_in = int(prior_reg.input_tokens if prior_reg else 0)
            prev_out = int(prior_reg.output_tokens if prior_reg else 0)

        purpose = ("mechanical_repair" if (record.run_id, stage.stage_id, role.value) in self._mechanical_repairs
                   else "isolated" if isolated else "scientific")
        outcome = await configured_turn(brief, workspace, purpose, execution)
        # Auto-compact via THREAD ROTATION (provider-agnostic): Codex-native
        # thread.compact() hangs against the ADR-008 shim, so when a member's
        # configured input-token threshold is crossed we ask the thread for a
        # handoff summary, archive it, and let the next turn mint a fresh
        # thread whose brief carries the handoff.
        total_in = int(outcome.usage.get("input_tokens") or 0)
        threshold = int(config_doc.get("auto_compact_tokens") or 0)
        do_rotate = outcome.succeeded and threshold > 0 and total_in >= threshold
        # Optional user-set per-turn ceiling (D9): enforced post-turn
        # (mid-turn usage is not observable through the shim).
        ceiling = int(config_doc.get("max_turn_input_tokens") or 0)
        ceiling_hit = outcome.succeeded and ceiling > 0 and total_in >= ceiling
        if ceiling_hit:
            do_rotate = True
        if self._progressive_p4(record) and self._p4_controller(record, stage, role).snapshot().get("pause_request"):
            do_rotate = False
        if supports_problem_context(self._catalog(record)) and (workspace / "researcher-question.json").is_file():
            self._authored_researcher_question(record, stage, workspace)
            do_rotate = False
        # Notebook collection (D1): the member's per-branch persistent
        # memory — written by the member in its workspace, carried into its
        # own future briefs, never shown to others.
        if outcome.succeeded and not isolated:
            nb = workspace / "notebook.md"
            if nb.is_file():
                nb_dir = project_dir / "members" / role.value / "notebooks"
                nb_dir.mkdir(parents=True, exist_ok=True)
                (nb_dir / f"{branch}.md").write_text(
                    nb.read_text(encoding="utf-8"), encoding="utf-8"
                )
        # True per-turn spend. The SDK reports CUMULATIVE thread totals in
        # `input_tokens`/`output_tokens` and only the LAST REQUEST in
        # `last_*` (undercounts multi-request turns). The exact turn spend
        # is the delta of the thread's cumulative total across this turn.
        if "last_input_tokens" in outcome.usage:
            turn_in = max(0, total_in - prev_in)
            turn_out = max(0, int(outcome.usage.get("output_tokens") or 0) - prev_out)
        else:
            # Fake bridge semantics: usage dict is already per-turn.
            turn_in = int(outcome.usage.get("input_tokens") or 0)
            turn_out = int(outcome.usage.get("output_tokens") or 0)
        async with self._registry_lock(record.project_id, key.branch_id):
            registry = self._registry(record.project_id, key.branch_id)
            registry.reload()
            registry.note_turn(key)
            registry.note_usage(key, total_in, int(outcome.usage.get("output_tokens") or 0))
        if do_rotate:
            handoff_dir = run_dir / "handoffs" / stage.stage_id / role.value
            handoff_dir.mkdir(parents=True, exist_ok=True)
            handoff_workspace = workspace / "handoff"
            handoff_workspace.mkdir(parents=True, exist_ok=True)
            handoff_brief = handoff_dir / "handoff-brief.md"
            handoff_brief.write_text(
                "# Context rotation (auto-compact)\n\n"
                + self._workspace_mechanics(handoff_workspace)
                + "This thread's context is being rotated to control token cost. "
                "Write `handoff.md` capturing what a fresh continuation of your "
                "work needs: current task, decisions made, files produced (with "
                "paths), key data, and what remains. Be compact and factual.\n",
                encoding="utf-8",
            )
            handoff_config = read_json(project_dir / "members" / role.value / "config.json") or {}
            handoff_provider = load_provider_config(self.data_root)
            handoff_provider.require_ready(role.value)
            self._apply_saved_provider_account(handoff_provider, project_dir, role)
            handoff_member = handoff_provider.resolve_member(handoff_config, role.value, codex_home(project_dir, role))
            handoff_execution = capture_execution(handoff_member.config, member_home, handoff_member.environment,
                                                  handoff_member.strip_keys)
            if not self._matching_thread_web_tools(thread_id, handoff_execution, run_dir=run_dir):
                from .bridge import TurnOutcome
                hb = TurnOutcome(succeeded=False)
                self._event(record, "thread.tools_changed", "Web retrieval tools changed; the next member turn will use a fresh thread.",
                            stage=stage.stage_id, role=role.value)
            else:
                if not await self.bridge.resume_thread(thread_id, member_home=member_home, execution=handoff_execution, workspace_root=workspace_root):
                    raise RunError("The member thread became unavailable before its handoff turn")
                hb = await configured_turn(handoff_brief, handoff_workspace, "handoff", handoff_execution)
            # The handoff turn spends tokens too — count its spend. Under
            # SDK semantics it runs on the SAME thread, so its spend is the
            # cumulative growth during that turn.
            if "last_input_tokens" in hb.usage:
                turn_in += max(0, int(hb.usage.get("input_tokens") or 0) - total_in)
                turn_out += max(
                    0,
                    int(hb.usage.get("output_tokens") or 0)
                    - int(outcome.usage.get("output_tokens") or 0),
                )
            else:
                turn_in += int(hb.usage.get("input_tokens") or 0)
                turn_out += int(hb.usage.get("output_tokens") or 0)
            handoff_file = handoff_workspace / "handoff.md"
            if hb.succeeded and handoff_file.is_file():
                (handoff_dir / "handoff.md").write_bytes(handoff_file.read_bytes())
                store = project_dir / "branches" / key.branch_id / "handoffs"
                store.mkdir(parents=True, exist_ok=True)
                (store / f"{key.as_string().replace(':', '_')}.md").write_text(
                    handoff_file.read_text(encoding="utf-8"), encoding="utf-8"
                )
                async with self._registry_lock(record.project_id, key.branch_id):
                    registry = self._registry(record.project_id, key.branch_id)
                    registry.reload()
                    registry.archive(key)
                    registry.reset_tokens(key)
                record.thread_ids.pop(key.as_string(), None)
                self._save_run(record)
                if ceiling_hit:
                    self._event(
                        record,
                        "member.rotated_midturn",
                        f"Per-turn ceiling {ceiling:,} input tokens reached "
                        f"({total_in:,}); thread force-rotated after the turn.",
                        stage=stage.stage_id,
                        role=role.value,
                    )
                self._event(
                    record,
                    "thread.rotated",
                    f"Auto-compacted via thread rotation at {total_in:,} input tokens "
                    f"(threshold {threshold:,}); handoff saved.",
                    stage=stage.stage_id,
                    role=role.value,
                )
        # Collect declared outputs from the workspace into outputs/<stage>/.
        out_dir = run_dir / "outputs" / stage.stage_id
        out_dir.mkdir(parents=True, exist_ok=True)
        collected = []
        if outcome.succeeded:
            owned = owned_writes(stage, role)
            owned_names = {o.split(".", 1)[-1] + (".jsonl" if o.endswith("metrics_long") else ".json") for o in owned}
            other_names = {o.split(".", 1)[-1] + (".jsonl" if o.endswith("metrics_long") else ".json") for o in stage.writes if o not in owned}
            unexpected = [p.name for p in workspace.iterdir() if p.is_file() and p.name in other_names]
            if unexpected:
                return StageResult(stage_id=stage.stage_id, succeeded=False,
                                   diagnostic=f"{role.value} wrote another member's owned output: {', '.join(unexpected)}")
            # Working files remain attached to their producing member. Only
            # owned declared outputs enter the shared stage's formal namespace.
            working_dir = out_dir / "working" / role.value
            working_dir.mkdir(parents=True, exist_ok=True)
            local_inputs = (read_json(run_dir / "basis.json") or {}).get("p4_inputs")
            if local_inputs is not None:
                from .researcher_inputs import retain_support_files
                excluded = retain_support_files(workspace, working_dir, owned_names, local_inputs)
                if excluded:
                    self._event(record, "input.retention", "Raw researcher data were excluded from published support files.", count=len(excluded))
            else:
                for source in workspace.iterdir():
                    if source.is_file() and source.name not in owned_names:
                        (working_dir / source.name).write_bytes(source.read_bytes())
                    elif source.is_dir():
                        shutil.copytree(source, working_dir / source.name, dirs_exist_ok=True, symlinks=True)
            for filename in sorted(owned_names):
                if not (workspace / filename).is_file():
                    continue
                target = out_dir / filename
                target.write_bytes((workspace / filename).read_bytes())
                collected.append(target)
            report_file = out_dir / "technical_report_candidate.json"
            if "technical_report_candidate.json" in owned_names and report_file.is_file():
                report = read_json(report_file)
                if isinstance(report, dict):
                    report_basis = ResearcherPauseStore(run_dir).context_basis(record, read_json(run_dir / "basis.json") or {})
                    authorized_items = report_basis.get("problem_context", {}).get("authorized_context_items", [])
                    if authorized_items:
                        report["authorized_context_items"] = authorized_items
                    else:
                        report.pop("authorized_context_items", None)
                    for pointer in list(self._artifact_pointers(report)):
                        field = "path" if pointer.get("path") else "artifact_path"
                        relative = str(pointer.get(field, ""))
                        local = (workspace / relative).resolve()
                        if relative and local.is_relative_to(workspace.resolve()) and local.is_file():
                            if Path(relative).parent == Path(".") and Path(relative).name in owned_names:
                                # A declared scientific supplement keeps the original
                                # bytes even when its formal record is rewritten below.
                                (working_dir / local.name).write_bytes(local.read_bytes())
                            aliases = report.setdefault("artifact_authored_paths", {})
                            alias_key = pointer.get("artifact_id") or pointer.get("sha256")
                            if not isinstance(aliases.get(alias_key), str) or not aliases[alias_key]:
                                aliases[alias_key] = relative.replace("\\", "/")
                            pointer[field] = "working/" + role.value + "/" + relative.replace("\\", "/")
                    report["completion"] = derive_report_completion(report, report_basis,
                        artifact_roots={"p5.technical_report_candidate": out_dir})
                    write_json_atomic(report_file, report)
            diagnostics_file = out_dir / "diagnostics.json"
            if "diagnostics.json" in owned_names and diagnostics_file.is_file() and not self._progressive_p4(record):
                try:
                    diagnostic_doc = read_json(diagnostics_file)
                except (OSError, ValueError):
                    diagnostic_doc = None  # Preserve invalid bytes for the author-facing validator.
                if isinstance(diagnostic_doc, dict):
                    script = str(diagnostic_doc.get("regenerated_by", ""))
                    if script and not Path(script).is_absolute() and ".." not in Path(script).parts:
                        diagnostic_doc["regenerated_by"] = f"working/{role.value}/{script}"
                        write_json_atomic(diagnostics_file, diagnostic_doc)
            # Exhibits (design/15): copy each exhibit's T3w artifact from the
            # workspace into the run folder and rewrite artifact_path so the
            # run folder is self-contained (Tez: each run keeps its own files).
            exhibits_file = out_dir / "exhibits.json"
            if "exhibits.json" in owned_names and exhibits_file.is_file():
                try:
                    exhibits = json.loads(exhibits_file.read_text(encoding="utf-8"))
                except Exception:  # noqa: BLE001 - schema layer reports it
                    exhibits = None
                if isinstance(exhibits, list):
                    dest_dir = out_dir / "exhibit-artifacts"
                    changed = False
                    for ex in exhibits:
                        if not isinstance(ex, dict):
                            continue
                        rel = str(ex.get("artifact_path", ""))
                        src = (workspace / rel).resolve() if rel else None
                        if not rel or src is None or not src.is_relative_to(workspace.resolve()) or not src.is_file():
                            continue
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest = dest_dir / (sha256_file(src)[:16] + "-" + src.name)
                        dest.write_bytes(src.read_bytes())
                        ex["artifact_path"] = f"exhibit-artifacts/{dest.name}"
                        collected.append(dest)
                        changed = True
                    if changed:
                        # Records can cite the authored manifest's exact bytes.
                        # Keep them beside retained support files before the
                        # display manifest's artifact paths are relocated.
                        authored_manifest = working_dir / exhibits_file.name
                        authored_manifest.write_bytes(exhibits_file.read_bytes())
                        collected.append(authored_manifest)
                        exhibits_file.write_text(
                            json.dumps(exhibits, indent=1), encoding="utf-8"
                        )
            # A6: harness-owned stamping (design/05 §6) — digest-seal the
            # collected bytes BEFORE validation; validation reads these.
            seal = {
                "stage_id": stage.stage_id,
                "role": role.value,
                "sealed_at": _now(),
                "outputs": {
                    str(p.relative_to(out_dir)): {
                        "sha256": sha256_file(p), "size_bytes": p.stat().st_size
                    }
                    for p in collected
                },
            }
            write_json_atomic(out_dir / "seals" / f"{role.value}.json", seal)
            seals = {p.stem: read_json(p) for p in (out_dir / "seals").glob("*.json")}
            write_json_atomic(out_dir / "seal.json", {"stage_id": stage.stage_id, "members": seals,
                "outputs": {name: meta for member in seals.values() for name, meta in member.get("outputs", {}).items()}})
        usage = dict(outcome.usage)
        usage["turn_input_tokens"] = turn_in
        usage["turn_output_tokens"] = turn_out
        return StageResult(
            stage_id=stage.stage_id,
            succeeded=outcome.succeeded and not outcome.interrupted,
            output_paths=tuple(collected),
            diagnostic=outcome.diagnostic,
            usage=usage,
        )

    # -------------------------------------------------------------- #
    # Brief rendering (SPEC-context-and-artifacts.md §3)
    # -------------------------------------------------------------- #

    # D6: lead T2s summaries inline only where the next phase must
    # operationalize the verdict (P1→P2, P3→P4); lead always carries own.
    _T2S_INLINE_NEXT = {"P1": {"P2"}, "P3": {"P4"}}

    def _upstream_records(self, record: RunRecord) -> list[dict]:
        """Use the exact authorization snapshot, never moving current slots."""
        project_dir = self.project_dir(record.project_id)
        basis = read_json(self.run_dir(record.project_id, record.run_id) / "basis.json")
        if basis is None:
            basis = self.compute_basis(record.project_id, record.phase, record.branch_id, record.mode)
        out: list[dict] = []
        for ref in basis.get("records", []):
            phase = ref.get("phase")
            if not phase:
                raise RunError("This run predates frozen input manifests; start a new run")
            family = project_dir / "branches" / ref["branch"] / "phases" / phase.lower() / ref["family"]
            out.append({"branch": ref["branch"], "phase": phase, "family": ref["family"],
                        "family_dir": family, "current": ref})
        return out

    def _generation_text(self, family_dir: Path, current: dict):
        """(text, size_bytes, path) of the current generation, or None."""
        if current.get("snapshot_path"):
            gen_path = Path(current["snapshot_path"])
            if not gen_path.is_file() or sha256_file(gen_path) != current.get("content_sha256"):
                raise ArtifactError(f"Frozen input for {family_dir.name} is missing or changed")
        else:
            gen_path = generation_path(family_dir.parent, family_dir.name, current)
        text = gen_path.read_text(encoding="utf-8")
        return text, len(text.encode("utf-8")), gen_path

    def _t2s_delivery(self, summary_phase: str, record: RunRecord, role: MemberRole,
                      stage: StageSpec | None = None) -> str:
        if role is MemberRole.OUTSIDE_REVIEWER:
            return "never"
        if role is MemberRole.RESEARCH_LEAD:
            return "inline"  # self-synthesis exception (D6)
        # The same specialist can author in one stage and review in another.
        # Reviewers inspect the science without an inline lead verdict (D6).
        if stage and any("review" in output or "audit" in output for output in owned_writes(stage, role)):
            return "mention"
        if summary_phase == "P3" and record.phase == "P4":
            return "inline" if role is MemberRole.DATA_ANALYST else "mention"
        return "inline" if record.phase in self._T2S_INLINE_NEXT.get(summary_phase, set()) else "mention"

    def _mention_line(self, rec: dict, meta: dict, size: int | None, path: Path | None) -> str:
        digest = str(rec["current"].get("content_sha256", ""))[:12]
        label = meta.get("artifact_type", "record")
        size_txt = f"{size:,} B" if size is not None else "? B"
        title = ""
        doc = self._generation_text(rec["family_dir"], rec["current"])
        if doc:
            try:
                head = json.loads(doc[0])
                title = str(head.get("headline") or head.get("title") or "")[:100]
                if isinstance(head, list) and head:
                    title = str(head[0].get("title", ""))[:100]
            except Exception:  # noqa: BLE001 - title is best-effort
                title = ""
        line = (f"- `{rec['branch']}` {rec['phase']} **{rec['family']}** [{label}]"
                + (f" — {title}" if title else "")
                + f" · {size_txt} · sha256:{digest}… · `{path}`")
        return line

    def _classify_upstream(self, record: RunRecord, role: MemberRole, catalog: Catalog,
                           stage: StageSpec | None = None) -> dict:
        """Split upstream records into delivery classes for this member
        (SPEC §3 steps 3–6)."""
        meta_all = catalog.artifact_contracts()
        sections: dict[str, list[str]] = {
            "titles": [], "decisions": [], "t2s": [], "packets": [],
            "instructed": [], "mentions": [], "literature": [],
        }
        upstream = self._upstream_records(record)
        canonical_sources = {"complete_theory": "theory_record", "manuscript_candidate": "manuscript",
                             "empirical_index_candidate": "empirical_evidence_index", "empirical_synthesis_candidate": "empirical_synthesis",
                             "implementation_record_candidate": "implementation_record",
                             "synthesis_candidate": "literature_synthesis", "coverage_candidate": "literature_coverage"}
        present = {(r["branch"], r["phase"], r["family"]) for r in upstream}
        basis = read_json(self.run_dir(record.project_id, record.run_id) / "basis.json") or {}
        literature = self._literature_context(record, role, stage, catalog) if stage else None
        if literature:
            sections["literature"].append(literature)
        for family, ref in basis.get("cumulative_inputs", {}).items():
            document = self._cumulative_input(record, family)
            if family == "researcher_answers" and basis.get("problem_context"):
                document = {**document, "items": [row for row in document.get("items", [])
                    if not (row.get("audience") or (row.get("attention") or {}).get("audience"))
                    or role.value in (row.get("audience") or (row.get("attention") or {}).get("audience"))]}
                scoped = self.run_dir(record.project_id, record.run_id) / "inputs" / "answer-views" / role.value / "researcher_answers.json"
                write_json_atomic(scoped, document)
                ref = {**ref, "snapshot_path": str(scoped)}
            if family == "literature_library" and literature:
                continue
            if not ref.get("snapshot_path"):
                continue
            view = self._p2_specialist_content(record, role, record.phase, family,
                                               json.dumps(document, ensure_ascii=False))
            source_path = view[1] if view else ref["snapshot_path"]
            explanation = {
                "literature_library": "The cumulative sources, revisions and directly authored scientific assessments. Preserve earlier sources, deduplicate rediscoveries, and distinguish corrections or retractions. Legacy T1 display-only cards are not scientific input.",
                "method_catalog": "All retained method proposals at their latest authored versions. Change only the methods this run revises; omission does not retire a proposal.",
                "review_issue_ledger": "Prior review issues and their latest explicit dispositions. Each issue retains its original manuscript basis; it is not a review verdict on a newer manuscript. Omission does not resolve an issue.",
                "open_attention": "Applicable unresolved researcher choices, unavailable study facts and team tasks with their exact sources. Read the affected point and only the supporting context needed for your work. A research_task belongs to the team in its target_phase. Preserve scope, identifiers and sources; omission does not close an item. Do not repeat an unchanged question or reconstruct its full history. Historical untyped items retain their original meaning without an inferred assignment.",
                "researcher_answers": "Applicable saved answers with exact question revisions and sources. Use only the current answers in this frozen role-specific index. Method-scoped answers stay with their exact model/version; P1 setting clarifications remain shared inherited instructions. Shared facts reach their named audiences and P2 Lead-only directions remain Lead-only, including older P2 answers without an explicit audience. Keep researcher reports and unknowns distinct from verified evidence. Closing a question does not discard its answer.",
            }[family]
            sections["instructed"].append(f"- **{family}**: {explanation} Open the exact frozen index prepared for your role: `{source_path}`")
        for rec in upstream:
            family, phase = rec["family"], rec["phase"]
            if family.split(".", 1)[-1] == "attention_items":
                continue  # The scoped cumulative inbox supersedes raw historical attention.
            if literature and phase == "P1" and family in ("lead_literature", "theory_literature", "empirical_literature"):
                continue  # Current entries are delivered once through their effective library view.
            if role in (MemberRole.THEORIST, MemberRole.DATA_ANALYST) and phase == "P1" and family == "phase2_handoff":
                continue  # Historical P2 directions belong to the lead as well.
            if family in basis.get("cumulative_inputs", {}):
                continue  # The frozen cumulative view includes legacy history.
            if phase == "P1" and family in ("literature_synthesis", "decision") and (rec["branch"], phase, "research_basis") in present:
                continue  # These compatibility views repeat the direct research basis.
            if phase == "P2" and family == "decision" and (rec["branch"], phase, "catalog_assessment") in present:
                continue
            canonical = canonical_sources.get(family)
            if canonical and (rec["branch"], phase, canonical) in present:
                continue
            if family == "theory_candidate" and (rec["branch"], phase, "theory_record") in present:
                continue  # Final reviewed theory is authoritative for future runs.
            meta = meta_all.get(f"{phase.lower()}.{family}") or {}
            atype = meta.get("artifact_type", "record")
            audience = meta.get("audience", [])
            delivery = meta.get("delivery", "mention")
            addressed = role.value in audience or record.phase.lower() in audience
            if atype == "t1_card":  # UI-only: never delivered to members (SPEC §2.6)
                continue
            suffix = family.split(".", 1)[-1]
            doc = self._generation_text(rec["family_dir"], rec["current"])
            size = doc[1] if doc else None
            path = doc[2] if doc else None
            view = self._p2_specialist_content(record, role, phase, family, doc[0]) if doc else None
            if view:
                sections["instructed"].append(
                    f"- **{family}** ({phase}, `{rec['branch']}`): read the scientific content prepared for your role: `{view[1]}`. "
                    "Its mathematical fields are unchanged; Phase 2 instructions addressed to the lead are omitted."
                )
                continue
            if family in ("theory_record", "manuscript", "empirical_evidence_index", "empirical_synthesis", "implementation_record",
                          "literature_library", "literature_synthesis", "literature_coverage", "method_catalog", "review_issue_ledger", "research_basis", "catalog_assessment") and doc:
                sections["instructed"].append(
                    f"- **{family}** ({phase}, `{rec['branch']}`), the complete current account for this frozen basis. "
                    f"Open and read the applicable scientific content: `{path}` ({size:,} B)"
                )
                continue
            if suffix in ("theory_method_cards", "empirical_method_cards") and doc:
                try:
                    for card in json.loads(doc[0]):
                        sections["titles"].append(
                            f"- **{card.get('title', '?')}** (`{card.get('subject_ref', '?')}`): "
                            f"{str(card.get('definition', ''))[:200]}"
                        )
                except Exception:  # noqa: BLE001
                    pass
                continue
            if suffix == "decision" and doc:
                try:
                    d = json.loads(doc[0])
                    so = d.get("scientific_outcome") or {}
                    sections["decisions"].append(
                        f"### Decision {phase} (`{rec['branch']}`)\n\n"
                        f"**{d.get('headline', '')}**\n\n"
                        f"Conclusion: {d.get('current_conclusion', '')}\n\n"
                        f"Outcome: {so.get('state', '?')}\n\n"
                        f"Full record: `{path}`\n"
                    )
                except Exception:  # noqa: BLE001
                    sections["mentions"].append(self._mention_line(rec, meta, size, path))
                continue
            if (atype == "t2s" or suffix in ("phase_summary", "revision_account")) and doc:
                mode = self._t2s_delivery(phase.upper(), record, role, stage)
                if mode == "inline":
                    try:
                        d = json.loads(doc[0])
                        sections["t2s"].append(
                            f"### Lead summary of {phase} (`{rec['branch']}`)\n\n"
                            f"**{d.get('headline', '')}**\n\n{d.get('evaluation_markdown', '')}\n"
                        )
                    except Exception:  # noqa: BLE001
                        sections["t2s"].append(f"### Lead summary of {phase}\n\n{doc[0]}\n")
                elif mode == "mention":
                    sections["mentions"].append(self._mention_line(rec, meta, size, path))
                continue
            if delivery == "inline" and addressed and doc:
                sections["packets"].append(
                    f"### `{family}` ({phase}, `{rec['branch']}`)\n\n{doc[0]}\n"
                )
            elif delivery == "instructed_open" and addressed and doc:
                sections["instructed"].append(
                    f"- **{family}** ({phase}, `{rec['branch']}`) — your stage's work depends on "
                    f"its exact content. Open and read fully: `{path}` ({size:,} B)"
                )
            else:
                sections["mentions"].append(self._mention_line(rec, meta, size, path))
        return sections

    def _p2_specialist_content(self, record: RunRecord, role: MemberRole, phase: str, family: str, text: str):
        if role not in (MemberRole.THEORIST, MemberRole.DATA_ANALYST):
            return None
        from .p2_delivery import specialist_view
        try:
            view = specialist_view(phase, family, json.loads(text), role=role.value)
        except ValueError:
            return None  # Keep malformed output available for normal validation.
        if view is None:
            return None
        digest = sha256_bytes(text.encode("utf-8"))
        path = self.run_dir(record.project_id, record.run_id) / "inputs" / "specialist-views" / role.value / phase.lower() / (family + "-" + digest + ".json")
        write_json_atomic(path, view)
        return json.dumps(view, ensure_ascii=False, indent=1), path

    def _same_run_sections(self, record: RunRecord, stage: StageSpec, role: MemberRole,
                           *, indexed_literature: bool = False) -> dict:
        """Prior stages of THIS run, delivered per artifact contracts
        (SPEC §3 step 4 applied intra-run)."""
        run_dir = self.run_dir(record.project_id, record.run_id)
        sections: dict[str, list[str]] = {"packets": [], "instructed": [], "mentions": []}
        delivered_artifacts = set()
        for stage_spec in self._stages(record):
            st = asdict(stage_spec)
            if int(st.get("sequence", 0)) >= stage.sequence:
                continue
            out_dir = run_dir / "outputs" / st["stage_id"]
            if not out_dir.is_dir():
                continue
            ac = st.get("artifact_contracts", {})
            for fam in st.get("writes", []):
                if (record.phase == "P1" and indexed_literature
                        and fam in {"p1.lead_literature", "p1.theory_literature", "p1.empirical_literature"}):
                    continue  # The lead receives indexed entries, not complete collections inline.
                suffix = fam.split(".", 1)[-1]
                path = out_dir / (suffix + (".jsonl" if suffix == "metrics_long" else ".json"))
                if not path.is_file():
                    continue
                meta = ac.get(fam) or {}
                if meta.get("artifact_type") == "t1_card" or meta.get("delivery") == "ui_only":
                    continue
                addressed = role.value in (meta.get("audience") or [])
                required_read = fam in stage.role_reads.get(role.value, stage.reads)
                text = path.read_text(encoding="utf-8", errors="replace")
                view = self._p2_specialist_content(record, role, record.phase, suffix, text)
                if view:
                    text, path = view
                delivery = meta.get("delivery")
                if meta.get("artifact_type") == "t2s" or suffix in ("phase_summary", "revision_account"):
                    delivery = self._t2s_delivery(record.phase, record, role, stage)
                    addressed = delivery == "inline"
                    required_read = False
                if delivery == "never":
                    continue
                large_diagnostics = (fam == "p4.diagnostics"
                                     and len(text.encode("utf-8")) > self._SIZE_CAPS["t2p_packet"][0])
                if large_diagnostics and delivery == "inline":
                    delivery = "instructed_open"
                delivered = False
                if delivery == "inline" and (addressed or required_read):
                    delivered = True
                    sections["packets"].append(
                        f"### `{fam}` (this run, stage {st['stage_id']})\n\n{text}\n"
                    )
                elif (delivery == "instructed_open" and addressed) or required_read:
                    delivered = True
                    source_hash = f", sha256 {sha256_file(path)}" if large_diagnostics else ""
                    sections["instructed"].append(
                        f"- **{fam}** (this run, stage {st['stage_id']}) — open and read fully: "
                        f"`{path}` ({len(text.encode('utf-8')):,} B{source_hash})"
                    )
                else:
                    sections["mentions"].append(
                        f"- `{fam}` (this run, {st['stage_id']}) · {len(text.encode('utf-8')):,} B · `{path}`"
                    )
                if delivered and suffix != "metrics_long":
                    try:
                        document = json.loads(text)
                    except ValueError:
                        continue
                    # Authored paths remain relative to the member workspace;
                    # collection retains attachments under working/<role>/.
                    for artifact in self._artifact_pointers(document):
                        try:
                            source = source_artifact_path(self.project_dir(record.project_id),
                                {"run_id": record.run_id, "stage_id": st["stage_id"]}, artifact)
                        except ArtifactError:
                            continue
                        if not source.is_relative_to(out_dir.resolve()) or source in delivered_artifacts:
                            continue
                        delivered_artifacts.add(source)
                        digest = artifact.get("sha256") or artifact.get("artifact_sha256")
                        sections["instructed"].append(
                            f"- **{fam}** referenced file `{artifact.get('path') or artifact.get('artifact_path')}`: "
                            f"open the exact retained file `{source}` (sha256 {digest})."
                        )
        return sections

    @staticmethod
    def _framework_p1(catalog: Catalog) -> bool:
        try:
            return tuple(int(part) for part in catalog.version.split(".")[:3]) >= (1, 7, 0)
        except ValueError:
            return False

    def _literature_context(self, record: RunRecord, role: MemberRole,
                            stage: StageSpec, catalog: Catalog) -> str | None:
        """Deliver selected current entries without exposing live peer drafts."""
        if role is MemberRole.OUTSIDE_REVIEWER or record.intent == "assessment":
            return None
        previous = self._cumulative_input(record, "literature_library")
        if previous is None:
            return None
        if (not any(source.get("assessments") for source in previous.get("sources", []))
                and any(item["family"] in {"lead_literature", "theory_literature", "empirical_literature"}
                        for item in self._upstream_records(record))):
            return None  # Historical libraries without attached assessments keep their source collections.
        # Legacy runs retain their delivery contract. A corrected current
        # library must nevertheless be the single source for future consumers.
        has_revisions = any(item.get("lead_revision") for source in previous.get("sources", [])
                            for item in source.get("assessments", []))
        if not self._framework_p1(catalog) and not has_revisions:
            return None
        from .direct_artifacts import LITERATURE_ROLES, direct_literature_sources
        from .literature import build_library
        from .p1_science import literature_entries, reconciliation_enabled
        from .literature_context import write_literature_context
        documents = {}
        if record.phase == "P1":
            readable = set(stage.role_reads.get(role.value, stage.reads))
            for prior in self._stages(record):
                if prior.sequence >= stage.sequence or record.stage_states.get(prior.stage_id) != "succeeded":
                    continue
                for output in prior.writes:
                    family = output.split(".", 1)[-1]
                    if family not in LITERATURE_ROLES or output not in readable:
                        continue
                    path = self.run_dir(record.project_id, record.run_id) / "outputs" / prior.stage_id / self._output_filename(output)
                    document = read_json(path)
                    if document is None:
                        raise ArtifactError("A completed literature collection is unavailable")
                    documents[family] = document
        assessments = literature_entries(documents, previous, run_id=record.run_id, apply_corrections=False)
        # Old packages may contain only citation records with no retained
        # mathematical assessments. Keep their original delivery available.
        if not assessments and any(source.get("assessments") for source in previous.get("sources", [])):
            raise ArtifactError("The current literature assessments could not be resolved")
        modern = reconciliation_enabled(catalog=self._catalog(record))
        library = build_library(previous, direct_literature_sources(documents), run_id=record.run_id,
                                allow_metadata_conflicts=modern, normalize_authors=modern, strict_identifiers=modern)
        directory = self.run_dir(record.project_id, record.run_id) / "inputs" / "literature-context" / stage.stage_id / role.value
        index = write_literature_context(directory, library, assessments, documents, run_id=record.run_id)
        return (
            f"- **Literature navigation**: {len(library['sources'])} unique sources and {len(assessments)} current member assessments. "
            f"Open `{index}` for the collection search scopes, coverage and paged entry index. "
            "Entry paths are relative to that index directory. Read selected entry files for exact mathematics and citation/source locations; "
            "their earlier_versions links preserve original submissions for reference, not as eligible correction targets. "
            "The current_source fields retain canonical citation status, exclusions and reasons separately from the author's original citation. "
            "follow the primary sources needed for scientific checking. These are current records, including any published lead corrections. "
            "Review the index for coverage, then inspect the entries supporting each framework and comparison. "
            "Do not concatenate all entry files into the prompt or claim to have verified entries from their index labels alone. "
            "Use the supplied entry reference for review targets and corrections; leave identities unchanged."
        )

    @staticmethod
    def _workspace_mechanics(workspace: Path) -> str:
        return (
            "## Workspace mechanics\n\n"
            f"Keep every shell command's working directory set to `{workspace}`. "
            "Use relative filenames for outputs in this directory. Write files with "
            "the file-editing tool when available, or PowerShell `Set-Content -LiteralPath` "
            "with small chunks. On Windows, keep shell commands short; do not embed a "
            "large JSON document in one process command line. "
            "JSON outputs must be complete valid JSON files.\n\n"
        )

    def _render_brief(
        self, record: RunRecord, stage: StageSpec, role: MemberRole, workspace: Path
    ) -> str:
        """Situation brief assembled per SPEC-context-and-artifacts.md §3:
        fixed sections → self-memory → binding upstream → addressed packets →
        instructed opens → ambient mentions. T1 cards never delivered."""
        run_dir = self.run_dir(record.project_id, record.run_id)
        catalog = self._catalog(record)
        repair = self._mechanical_repairs.get((record.run_id, stage.stage_id, role.value))
        if repair:
            return self._render_mechanical_repair_brief(record, stage, role, workspace, catalog, repair)
        artifact_check = self._artifact_check_brief(record, stage, role)
        if role == MemberRole.OUTSIDE_REVIEWER and frozen_review_packet_enabled(catalog):
            # The prepared submission is this role's entire scientific basis.
            # Corrections must not depend on unrelated internal input files.
            return self._review_brief(record, stage, workspace, catalog) + artifact_check
        basis = ResearcherPauseStore(run_dir).context_basis(record, read_json(run_dir / "basis.json") or {})
        for artifact in basis.get("artifacts", []):
            path = Path(artifact["path"])
            if not path.is_file() or sha256_file(path) != artifact["content_sha256"]:
                raise ArtifactError("A frozen scientific source file changed or disappeared")
        project_doc = (basis["project"] if "project" in basis else
                       read_json(self.project_dir(record.project_id) / "project.json")) or {}
        instructions = project_instructions(project_doc)
        context = basis.get("problem_context")
        context_section = ""
        if context:
            answers = self._cumulative_input(record, "researcher_answers") or {}
            account = role_effective_account(context, role.value, answers=answers.get("items", []),
                                             branch_id=record.branch_id, model_ref=basis.get("method"))
            instructions = account.get("unamended_instructions", instructions)
            context_dependence = (
                "In assessment_markdown and other reader-facing text, refer to relevant saved statements or unknowns by their meaning and explain how they affect the answer. "
                "Keep internal item IDs and revision metadata out of that prose. "
                if record.intent == "assessment" else
                "Cite item_id and revision in context_dependencies when a result depends on an item. "
            )
            context_section = ("## Frozen problem context\n\n"
                + json.dumps({"revision": context["revision"], "effective_account": account}, ensure_ascii=False, indent=1)
                + "\n\nResearcher reports and confirmed paraphrases are premises with provenance, not statistical validation. "
                + context_dependence
                + "Use only the applicable statements and exact answers needed for this stage, with their sources. "
                  "Preserve the researcher's intended claim, including requested inferential evidence; a prediction goal does not waive valid uncertainty or censoring justification. "
                  "A researcher preference cannot establish a statistical assumption. Unknown and no-data answers remain legitimate; "
                  "synthetic settings do not become study facts. Keep interpretations proposed until adopted.\n\n")
        project_instruction_section = f"## Project instructions (verbatim)\n\n{instructions}\n\n" if instructions else ""
        if record.phase == "P4" and "p4_inputs" in basis:
            from .researcher_inputs import input_brief
            context_section += input_brief(basis["p4_inputs"])
        owned = owned_writes(stage, role)
        branch = record.branch_id
        if role == MemberRole.OUTSIDE_REVIEWER:
            return self._review_brief(record, stage, workspace, catalog) + artifact_check
        target_context = self._target_context(record)
        if record.intent == "assessment":
            schema = catalog.output_schema("p3.assessment") or {"type": "object", "required": ["summary", "findings", "options"]}
            prior = read_json(run_dir / "previous-assessment.json") or {}
            sources = []
            for ref in self._upstream_records(record):
                if role != MemberRole.RESEARCH_LEAD and ref["phase"] == "P1" and ref["family"] == "phase2_handoff":
                    continue
                text, size, path = self._generation_text(ref["family_dir"], ref["current"])
                view = self._p2_specialist_content(record, role, ref["phase"], ref["family"], text)
                if view:
                    path = view[1]
                sources.append(f"- {ref['phase']} {ref['family']}: `{path}`")
            sources.extend(f"- Source artifact {a.get('artifact_id') or a['original_path']}: `{a['path']}`" for a in basis.get("artifacts", []))
            explanation = record.assessment_purpose == "explanation"
            objective = (
                "Answer the researcher's exact question about this assumption, using the frozen method, available notation, theory and proof sources. "
                "Start assessment_markdown with a direct answer in one or two sentences, then give the supporting reasoning. Do not substitute a generic explanation of the assumption's role for the answer. "
                "When the question asks what happens without the assumption, or if it is violated or weakened, identify which guarantee is no longer justified by the saved argument and which proof step loses its justification, if any. "
                "Distinguish an argument that no longer applies from a result or method that actually fails. Describe established failure, surviving results or valid weaker assumptions only when supported; otherwise state what remains unknown. "
                "For other questions, follow the requested focus rather than imposing this removal-of-assumption structure. "
                "Identify the specific proof step or claim that uses the assumption when the recorded work supports that connection. "
                "A simple example or failure case may help. Distinguish recorded results from illustrative arguments and possible relaxations. "
                "If the supplied proof does not establish necessity, say so; do not invent a necessity argument. "
                "Write a natural mathematical explanation in assessment_markdown, with structured evidence_refs only for sources actually used. "
                "Use Markdown with LaTeX compatible with the interface. Empty limitations and suggested_actions arrays are allowed; do not impose a review checklist. "
                if explanation else
                "Examine the component without presuming an error. Return reasoning, evidence, limitations and possible next steps. "
            )
            if record.assessment_purpose in ("issue_explanation", "model_dialogue"):
                objective = ("Answer the researcher's exact question directly, then explain the recorded concern, consequences, options and uncertainty using its frozen source. "
                             "If asked what happens without a condition or decision, first state the supported consequence, the guarantee or step that loses justification, and what remains unknown. Loss of an argument is not evidence of method failure. "
                             "Distinguish the author's finding from a researcher preference and from unresolved scientific work. "
                             "An explanation does not resolve the issue or authorize a change. Label any illustrative example. "
                             "If the original author is the outside reviewer, explicitly identify this as the lead's interpretation of the independent review; do not speak on that reviewer's behalf. "
                             "Use assessment_markdown and exact evidence_refs for sources actually used. ")
            if record.assessment_purpose == "issue_suggestions":
                objective = ("As Research Lead, suggest how the researcher could respond to this exact item using the frozen issue, method and relevant component sources. "
                    "Start with a concise recommendation, then explain plausible options, reasons, tradeoffs and what remains unknown. "
                    "Distinguish a researcher choice from a factual claim or scientific task that needs evidence. "
                    "Do not invent the researcher's preferences, available data or established results. Preserve uncertainty in their saved response or draft. "
                    "If the evidence does not justify a recommendation, say what would change the choice. "
                    "Suggestions are advice only: do not save or resolve a response, amend problem context, or claim a scientific change was made. "
                    "If this item originated with the outside reviewer, identify your advice as the lead's interpretation, not the reviewer's view. "
                    "Use assessment_markdown and exact evidence_refs for sources actually used. ")
            if record.assessment_purpose == "project_context":
                objective = ("Answer the researcher's question about their problem, data collection, goals or constraints. "
                    "Explain plausible existing model families and how collection, dependence, selection, missingness or intended use affect applicability. "
                    "Label literature claims tentative unless you inspected the supporting sources, and distinguish those sources from illustrative reasoning. "
                    "Explain the assumptions or performance expectations worth checking and what data cannot establish. "
                    "Do not impose a universal questionnaire. Keep no-data and unknown responses useful. "
                    "A proposed paraphrase is not validation. Return any interpretation in proposed_context_amendments with exact source refs; it takes effect only if the researcher confirms it. "
                    "Use assessment_markdown with exact evidence_refs for sources actually inspected. ")
                if (basis.get("context_dialogue") or {}).get("goal_source_ref"):
                    objective += ("Discuss the exact published research_goal_markdown passage and goal_source_ref in the frozen context. "
                        "Distinguish that Lead interpretation from the researcher's correction and retained project instructions. "
                        "Do not substitute a newer goal or treat this discussion as a saved correction. "
                        "Goal amendment proposals use project scope, topic research_goal and that exact source reference. ")
            if (record.target or {}).get("kind") == "report_section":
                objective = ("As Research Lead, answer the researcher's exact question about the selected technical report section. "
                    "Start with a direct answer, then explain its mathematics, evidence, assumptions or limitations as relevant. "
                    "Use the exact section text and frozen supporting sources; read only sources needed for this question. "
                    "Distinguish the report's claims, illustrative reasoning, researcher comments and unresolved work. "
                    "A saved section comment is user-authored discussion context, not a validated scientific fact or an instruction to change the report. "
                    "Do not save comments, propose context amendments, resolve issues, change the report or launch further work. "
                    "Return assessment_markdown and exact evidence_refs for sources actually used. ")
            draft_context = ("Researcher response note draft (verbatim, unsaved):\n" + record.researcher_note_draft
                + "\n\nThis is an editable researcher draft, not a saved answer or validated fact. Discuss it as provisional input; do not save or adopt it.\n\n"
                if record.researcher_note_draft is not None else "")
            if any(message.get("researcher_note_draft") is not None for message in prior.get("messages", [])):
                draft_context += "Researcher note drafts retained in the previous discussion remain unsaved provisional input, not adopted answers.\n\n"
            return (
                f"# {'Report section discussion' if (record.target or {}).get('kind') == 'report_section' else 'Lead suggestions' if record.assessment_purpose == 'issue_suggestions' else 'Issue explanation' if record.assessment_purpose == 'issue_explanation' else 'Assumption explanation' if explanation else 'Component assessment'}\n\n"
                f"{self._workspace_mechanics(workspace)}"
                f"{artifact_check}"
                f"{project_instruction_section}"
                f"{context_section}"
                f"Researcher note (verbatim):\n{record.instructions}\n\n{target_context}\n"
                f"{draft_context}"
                f"{objective}"
                "Do not change the theory, proofs, method, implementation, or existing scientific files. "
                "Do not launch repairs or experiments, or update the scientific member's continuing memory. "
                "Your writable workspace is isolated from all scientific sources.\n\n"
                f"Frozen method definition:\n{json.dumps(basis.get('method'), ensure_ascii=False)}\n\n"
                f"Previous discussion:\n{json.dumps(prior.get('messages', []), ensure_ascii=False)}\n\n"
                "Frozen scientific sources, open only what the assessment needs:\n" + "\n".join(sources) +
                f"\n\nWrite only `{workspace / 'assessment.json'}` as your result, following this schema:\n"
                f"```json\n{json.dumps(schema, indent=1)}\n```\n"
            )

        # --- Self-memory (SPEC §3 step 2): rotation handoff + notebook ----
        key = ThreadKey(member=role, phase=record.phase, branch_id=branch)
        if role is MemberRole.RESEARCH_LEAD:
            key = ThreadKey(member=role, phase="PROJECT", branch_id="trunk")
        handoff_path = (
            self.project_dir(record.project_id)
            / "branches" / key.branch_id / "handoffs"
            / f"{key.as_string().replace(':', '_')}.md"
        )
        handoff_text = ""
        if handoff_path.is_file():
            handoff_text = handoff_path.read_text(encoding="utf-8")
            handoff_path.unlink()  # consumed — handed to exactly one thread
        notebook_path = (
            self.project_dir(record.project_id) / "members" / role.value
            / "notebooks" / f"{branch}.md"
        )
        notebook_text = (
            notebook_path.read_text(encoding="utf-8") if notebook_path.is_file() else ""
        )

        # --- Output schemas (fixed) ----------------------------------------
        schema_blocks = []
        for output_id in owned:
            schema = catalog.output_schema(output_id)
            filename = output_id.split(".", 1)[-1] + (".jsonl" if output_id.endswith("metrics_long") else ".json")
            if schema:
                source_version_note = (
                    "Each `papers[i].source` follows its own linked source `schema_version` requirement; "
                    "do not inherit the collection version. Read "
                    f"`{catalog.root / 'schemas' / 'literature-source.schema.json'}` and its definitions in "
                    f"`{catalog.root / 'schemas' / 'common-definitions.schema.json'}`.\n\n"
                    if catalog.schema_for_output(output_id) == "literature-findings.schema.json" else ""
                )
                schema_blocks.append(
                    f"### `{filename}` (output `{output_id}`)\n\n"
                    + ("Write one JSON object per line; the schema applies to each row.\n\n" if filename.endswith(".jsonl") else "Must validate against this JSON Schema:\n\n")
                    + f"Resolve referenced schemas from `{catalog.root / 'schemas'}`.\n\n"
                    + source_version_note
                    + f"```json\n{json.dumps(schema, indent=1)}\n```"
                )
            else:
                schema_blocks.append(
                    f"### `{filename}` (output `{output_id}`)\n\n"
                    f"Free-form JSON; follow the pinned phase contract semantics."
                )
        if not owned:
            schema_blocks.append(
                "You own no declared outputs in this parallel stage — contribute "
                "analysis in your reply only."
            )
        schemas_text = "\n\n".join(schema_blocks)

        # --- Variable payload (SPEC §3 steps 3–6) ---------------------------
        up = self._classify_upstream(record, role, catalog, stage)
        same = self._same_run_sections(record, stage, role, indexed_literature=bool(up["literature"]))
        packets = up["packets"] + same["packets"]
        instructed = up["literature"] + up["instructed"] + same["instructed"]
        mentions = up["mentions"] + same["mentions"]

        def sec(title: str, items: list[str], empty: str = "") -> str:
            if not items:
                return empty
            return f"## {title}\n\n" + "\n".join(items) + "\n\n"

        binding = ""
        if up["titles"]:
            binding += sec("Method titles registered (T0)", up["titles"])
        binding += sec("Binding upstream decisions", up["decisions"])
        binding += sec("Lead phase summaries (T2s)", up["t2s"])
        if record.phase == "P1":
            try:
                run_date = datetime.fromisoformat(record.created_at.replace("Z", "+00:00")).date()
                date_scope = (f"Run date: {run_date.isoformat()}. Prioritize developments from more recent years, including "
                              f"current-year work through {run_date:%Y-%m}. ")
            except ValueError:
                date_scope = "The run start date is unavailable; state this dating limitation before claiming recent coverage. "
            binding += (
                "## Phase 1 literature search priorities\n\n"
                + date_scope
                + "Prioritize relevant recent research and substantive developments, checking publication and revision dates in primary sources. "
                "Use reliable sources, prioritizing primary research papers and authoritative publication sources. "
                "Verify citation details and identify preprints and publication status accurately. "
                "During discovery, follow keywords, references and citing papers around recent work. This is a priority, not a cutoff. "
                "Retain older classical and foundational results needed for definitions, methods and comparisons; "
                "the existing library does not replace an updated search. "
                "Preserve cumulative source identities and provenance; omission does not remove older sources. "
                "Use the existing search_scope, coverage_limits and reading_extent fields to state actual search dates, sources read, "
                "recent developments covered and remaining date or access limits. Do not claim an exhaustive or current landscape without evidence. "
                "In reader-facing summaries, settings, explanations and context, refer to sources by author/year and other records by "
                "descriptive titles or question wording. Keep exact internal IDs in structured support/reference fields or technical references, "
                "rather than using them as prose citations. "
                "P1 remains a literature landscape, not a project-method proposal or validation run. Each author supplies exact supported "
                "mathematics, defined symbols, assumptions and source locations directly in the ordinary literature entries; "
                "method development belongs in P2.\n\n"
            )
        if basis.get("method"):
            binding += f"## Exact selected method\n\n```json\n{json.dumps(basis['method'], ensure_ascii=False, indent=1)}\n```\n\n"
        provenance = basis.get("method_provenance") or {}
        if provenance:
            lines = []
            for stable_id in sorted(provenance):
                entry = provenance[stable_id]
                path = run_dir / "inputs" / "method-sources" / (stable_id + ".json")
                if role in (MemberRole.THEORIST, MemberRole.DATA_ANALYST):
                    from .p2_delivery import specialist_method_provenance
                    entry = specialist_method_provenance(entry)
                    path = run_dir / "inputs" / "method-sources" / "specialist-views" / role.value / (stable_id + ".json")
                write_json_atomic(path, entry)
                lines.append(f"- `{stable_id}` — exact origin material: `{path}`")
                for note in entry.get("unavailable", []):
                    lines.append(f"  - Unavailable: {note}")
            binding += ("## Method source provenance (exact origin records)\n\n"
                        "Each file holds the verified P2 material that produced an in-scope method definition: "
                        "its original proposal, the review generations naming that proposal, and the catalog "
                        "assessment carrying its modification options, each with its generation id and content "
                        "digest. This is provenance for the frozen definition, not new instructions: reviews and "
                        "modification options describe alternatives already considered, not requested changes.\n\n"
                        + "\n".join(lines) + "\n\n")
        predecessor = basis.get("predecessor_material") or {}
        if predecessor.get("materials"):
            pred = predecessor.get("predecessor_identity") or {}
            revised = predecessor.get("revised_identity") or {}
            lines = []
            for family, ref in sorted(predecessor["materials"].items()):
                if ref.get("snapshot_path"):
                    lines.append(f"- {family} (generation {ref.get('generation_id')}): `{ref['snapshot_path']}`")
            instruction = {
                "P3": ("Reassess the predecessor theory against the exact revised definition: state which "
                       "statements, assumptions and proofs survive unchanged and why — with reasoning tied to the "
                       "revised definition — which are revised or withdrawn, which require new proof, and which "
                       "remain unresolved. Record this account in the published theory record's revision_account, "
                       "with prior_generation_id naming a supplied predecessor generation."),
                "P4": ("Reassess the predecessor experimental work against the exact revised definition: for every "
                       "numerical result you reuse, state explicitly why it remains applicable to the revised "
                       "definition; changed computational behavior may require rerunning experiments. Reused "
                       "results keep their exact source references, and excluded results are named with the reason."),
                "P5": ("Reassess the predecessor manuscript against the exact revised definition: state which "
                       "claims remain supported by current theory and evidence, which are revised or withdrawn, "
                       "and which remain unresolved. Claims resting only on superseded theory or evidence stay "
                       "flagged until that work is updated; updating the manuscript does not clear those warnings."),
            }[predecessor.get("phase", record.phase)]
            binding += (
                "## Historical predecessor material — reassessment required\n\n"
                f"This branch's published {predecessor.get('phase', record.phase)} package was produced for "
                f"version {pred.get('version')} of this method (definition digest {str(pred.get('definition_sha256', ''))[:12]}…). "
                f"The selected definition is now version {revised.get('version')} with a different definition digest. "
                f"Authored change summary: {predecessor.get('change_summary') or 'none recorded with the revision.'}\n\n"
                "The files below are the verified predecessor generations, frozen as historical material for "
                "reassessment. They are not admitted as current scientific support, and copying a result while "
                "changing only the version is not acceptable.\n\n"
                + ("\n".join(lines) + "\n\n" if lines else "")
                + instruction + " "
                "If the revision changes the premise of a saved researcher answer, identify that answer for "
                "reconfirmation rather than silently reusing or deleting it.\n\n"
            )
        if record.supplied_method and role is MemberRole.RESEARCH_LEAD:
            binding += ("## Researcher-supplied method for Phase 2 (verbatim)\n\n"
                        + json.dumps(record.supplied_method, ensure_ascii=False, indent=1)
                        + "\n\nThe lead develops this specific supplied idea. Preserve its source and original specification in researcher_origin, "
                        "and distinguish any proposed extensions. The theorist and analyst each propose one independent alternative, "
                        "then audit one another's proposal and the lead's proposal.\n\n")
            from .p2_delivery import method_starting_point_brief
            binding += method_starting_point_brief(basis.get("p2_method_starting_point"))
        if record.phase == "P2" and role in (MemberRole.THEORIST, MemberRole.DATA_ANALYST):
            from .p2_delivery import requires_three_proposals
            lead_audit = (
                "After all three proposals are submitted, audit the other specialist's method and the lead's method exactly once each. "
                "Each proposer contributes exactly one method; your review is not a second proposal.\n\n"
                if requires_three_proposals(catalog) else
                "After proposal submission, audit the other specialist's method and any actual lead method proposal. "
                "A no_method_proposed lead response is not a method and needs no proposal assessment.\n\n"
            )
            binding += ("## Independent Phase 2 work\n\n"
                        "The Research Lead receives the researcher's additional Phase 2 instructions and ideas. "
                        "Propose your method independently from the shared research setting and literature. "
                        + lead_audit)
        if basis.get("artifacts"):
            binding += "## Frozen scientific source files\n\nThe record metadata retains its original relative references. Use these exact copied files when opening those referenced proofs, implementations, manuscripts, and data:\n"
            binding += "\n".join(f"- {a['family']} / {a['original_path']}: `{a['path']}` (sha256 {a['content_sha256']})" for a in basis["artifacts"]) + "\n\n"
        if basis.get("unavailable_artifacts"):
            binding += "## Unavailable referenced material\n\nThese older references have no verified retained file. Do not claim to have inspected or reproduced them:\n"
            binding += "\n".join(f"- {a['family']}: {a['reason']}" for a in basis["unavailable_artifacts"]) + "\n\n"
        binding += target_context
        previous_assessment = read_json(run_dir / "previous-assessment.json")
        if previous_assessment:
            binding += f"## Researcher-selected assessment\n\n{json.dumps(previous_assessment, ensure_ascii=False)}\n\n"
        if record.state == RunState.CORRECTING and record.correction_scope:
            scoped = [f for f in record.findings_history[-1] if f.get("object_id") in record.correction_scope]
            binding += (
                f"## Authorized validation correction\n\nNote (verbatim): {record.correction_note}\n\n"
                f"Allowed changed outputs: {json.dumps(record.correction_scope)}\n\n"
                f"Exact findings:\n```json\n{json.dumps(scoped, indent=1)}\n```\n"
                "Change only these outputs. Leave every other declared output byte-for-byte unchanged.\n\n"
            )
        elif record.correction_attempts:
            relevant = [f for f in record.findings_history[-1] if f.get("object_id") in owned]
            binding += (
                "## Review after corrected inputs\n\nProduce fresh complete outputs using the corrected earlier stages.\n"
                f"Researcher's correction note (verbatim): {record.correction_note}\n"
                f"Resolve these earlier findings in your outputs: {json.dumps(relevant, ensure_ascii=False)}\n\n"
            )
        if record.phase == "P4":
            scope = ("Proof of concept: answer the focused feasibility question with proportionate cases and computation. Do not invent a comprehensive suite or minimum repetition count."
                     if record.mode == "p4.preliminary" else "Full evaluation: execute the prespecified applicable comparisons, sensitivity checks and uncertainty assessment.")
            has_theory = any(r.get("phase") == "P3" for r in basis.get("records", []))
            binding += f"## Empirical scope\n\n{scope}\n"
            binding += ("Current theory is included with its limitations; test only claims whose stated conditions apply.\n\n" if has_theory else
                        "No current theory package exists. Evaluate the exact method definition and empirical question; theoretical claims remain unassessed.\n\n")
            binding += "Preserve applicable prior evidence in the current index with exact source references and explicit exclusions. Generate diagnostics from the recorded cases and repetitions, and report omitted or inapplicable checks honestly.\n\n"
        if record.phase == "P5" and not technical_report_enabled(catalog):
            binding += (
                "## Manuscript source references\n\n"
                f"Read the exact input manifest at `{run_dir / 'basis.json'}`. For upstream basis entries use its publisher-assigned generation_id and content_sha256, "
                "together with the record_id and record_type from that saved source. Do not substitute a candidate's authored generation or claimed content hash. "
                "Map each central claim in claim_support_index to one claim_traceability statement. Resolve declared support and counterevidence IDs against frozen P1 through P4 objects, "
                "and include their exact source generations in upstream_basis_manifest. Source locations must identify retained verified upstream files or locate the claim in this manuscript. "
                "A previous manuscript or a newly written interpretation cannot establish upstream scientific support. Keep unchecked or inconclusive claims explicit.\n\n"
            )

        objective = f"## Stage objective\n\n{stage.objective}\n\n" if stage.objective else ""
        if stage.role_objectives.get(role.value):
            objective += f"## Your scientific responsibility\n\n{stage.role_objectives[role.value]}\n\n"
        isolation = (
            f"## Isolation rule\n\n{stage.isolation_rule}\n\n" if stage.isolation_rule else ""
        )

        parallel_note = (
            f"You are one of {len(stage.roles)} members working this stage in "
            f"parallel; write ONLY your owned outputs — other members produce "
            f"theirs concurrently.\n\n" if len(stage.roles) > 1 else ""
        )
        notebook_section = (
            f"## Your notebook (persistent memory on this branch)\n\n{notebook_text}\n\n"
            if notebook_text else ""
        )
        mechanics_notebook = (
            " You may also maintain `notebook.md` in this directory — your "
            "persistent per-branch memory: it is carried into your own future "
            "briefs (never shown to other members). Update it before you finish."
        )
        return (
            f"# Situation brief — {stage.stage_id} ({role.value})\n\n"
            f"{self._workspace_mechanics(workspace)}{mechanics_notebook}\n\n"
            + artifact_check
            + self._p4_brief(record, stage, role)
            + project_instruction_section
            + context_section
            + (ResearcherPauseStore(run_dir).brief(record, stage, role)
               if supports_problem_context(catalog) and record.intent != "assessment" else "")
            + (technical_report_scope_brief(basis)
               if record.phase == "P5" and role is MemberRole.RESEARCH_LEAD and technical_report_enabled(catalog) else "")
            + (manuscript_scope_brief(basis)
               if record.phase == "P5" and role is MemberRole.RESEARCH_LEAD
               and frozen_review_packet_enabled(catalog) and not technical_report_enabled(catalog) else "")
            + (review_packet_brief(run_dir / "review-packet")
               if record.phase == "P5" and record.mode == "p5.review_revision"
               and frozen_review_packet_enabled(catalog) else "")
            + (
                f"## Researcher instructions for this run (verbatim)\n\n{record.instructions}\n\n"
                if record.instructions and (record.phase != "P2" or role is MemberRole.RESEARCH_LEAD)
                and not (record.phase == "P5" and record.mode == "p5.review_revision"
                         and frozen_review_packet_enabled(catalog)) else ""
            )
            + ("## Researcher-selected issues for this work\n\n" + json.dumps(basis["selected_issues"], ensure_ascii=False, indent=1) + "\n\n"
               if basis.get("selected_issues") and (record.phase != "P2" or role is MemberRole.RESEARCH_LEAD) else "")
            + notebook_section
            + (
                f"## Thread handoff (context rotation)\n\n{handoff_text}\n\n"
                if handoff_text else ""
            )
            + binding
            + f"{objective}"
            f"## Context\n\nPhase {record.phase}, mode {record.mode}, "
            f"branch `{record.branch_id}`, run `{record.run_id}`.\n\n"
            f"{parallel_note}"
            f"## Output directory\n\nWrite each owned output as a JSON file "
            f"in this exact directory (create it if needed):\n\n"
            f"`{workspace}`\n\n"
            f"## Your output contracts\n\n{schemas_text}\n\n"
            + sec("Packets addressed to you", packets)
            + sec("Required reading (open these files)", instructed)
            + sec("Other published records (mentions — open only if needed)",
                  mentions or [],
                  "- (no published upstream records yet)\n\n" if not (packets or instructed or binding) else "")
            + f"{isolation}"
            f"## Execution boundary\n\nProduce only your owned outputs. Do "
            f"not expand phase scope or change the selected method. Fail "
            f"loudly rather than fabricating.\n"
        )

    def _render_mechanical_repair_brief(self, record, stage, role, workspace, catalog, repair) -> str:
        original = Path(repair["original_brief"])
        if not original.is_file():
            raise RunError("The original member brief is unavailable for scoped mechanical repair")
        blocks = []
        for output in repair["outputs"]:
            filename = self._output_filename(output)
            path = workspace / filename
            content = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else "(not produced)"
            schema = catalog.output_schema(output)
            blocks.append(f"### `{filename}` (output `{output}`)\n\n"
                          f"Current submitted draft:\n```text\n{content}\n```\n\n"
                          + (f"Required schema{' for each JSONL row' if filename.endswith('.jsonl') else ''}:\n"
                             f"```json\n{json.dumps(schema, ensure_ascii=False, indent=1)}\n```\n\n"
                             f"Resolve referenced schemas from `{catalog.root / 'schemas'}`.\n"
                             if schema else "Follow the pinned output contract retained in the original brief.\n"))
        previous = repair.get("previous_attempt")
        return (
            f"# Mechanical repair before handoff ({stage.stage_id}, {role.value})\n\n"
            + self._workspace_mechanics(workspace)
            + f"Attempt {repair['attempt']} of {self._MAX_MECHANICAL_REPAIRS}. Correct only the listed findings in the affected outputs. "
            "Keep the research setting, scientific scope and unrelated content unchanged. "
            "Change only these declared outputs and their necessary supporting files. Preserve every other declared output byte-for-byte. "
            "Do not edit the validator, weaken a check, or start experiments. Verify citation identities against the permitted exact sources; "
            "the harness does not decide which record is correct. Do not guess or substitute a nearby identifier.\n\n"
            f"## Original frozen context\n\nYour original member brief is retained at `{original}` "
            f"(sha256 {sha256_file(original)}). Its scientific inputs, exact source paths and role-specific reading restrictions still apply. "
            "If this is a recreated thread, open that brief for the context needed to resolve the findings. "
            "Use only its permitted sources and exact frozen file paths; current project files, peer drafts and broader project history are not additional inputs. "
            "Its original authoring objective is background; the task in this turn is limited to this repair.\n\n"
            "## Exact findings\n\n```json\n" + json.dumps(repair["findings"], ensure_ascii=False, indent=1) + "\n```\n\n"
            + ("## Previous repair result\n\nFile changes alone do not establish scientific progress. "
               "Address the remaining and new findings using the permitted evidence.\n\n```json\n"
               + json.dumps(previous, ensure_ascii=False, indent=1) + "\n```\n\n" if previous else "")
            + "## Affected outputs and contracts\n\n" + "\n\n".join(blocks)
            + "\n\nCall `validate_artifacts` after saving the correction. Use its exact findings; a mechanical pass does not "
            "establish scientific correctness. If a finding cannot be resolved from permitted evidence, leave that limitation explicit and finish.\n"
        )

    def _artifact_check_brief(self, record: RunRecord, stage: StageSpec, role: MemberRole) -> str:
        text = (
            "## Check your artifacts while working\n\n"
            "Call `validate_artifacts` with no arguments after saving a usable draft and again after your final changes. "
            "The tool reads your declared files and permitted completed inputs, and returns exact structural and "
            "mechanical findings. Fix reported issues in your own outputs and call it again before finishing. "
            "It never modifies or publishes files. Checks needing other members or later stages are explicitly deferred; "
            "do not invent their missing outputs. A pass covers only the reported checks and does not certify scientific "
            "correctness. Continue checking sources, assumptions and reasoning as part of your ordinary task.\n\n"
            "In Markdown prose, use $...$ for short inline symbols and $$...$$ or \\[...\\] "
            "for the main objectives, constraints and comparisons so major equations are centered. Split long display equations "
            "with an aligned environment. Fields named `symbol` or `latex` instead contain raw TeX without math delimiters; "
            "the renderer supplies their math context. Use KaTeX-supported commands and one literal TeX backslash after JSON decoding "
            "(escape it once when writing JSON); preserve genuine aligned/matrix row breaks. The same UI KaTeX parser "
            "checks authored equations during validate_artifacts and at the stage boundary. Correct reported LaTeX in your own "
            "draft before finishing; a syntax pass does not assess the equation's scientific correctness.\n\n"
        )
        return text

    def _target_context(self, record: RunRecord) -> str:
        if not record.target:
            return ""
        if record.assessment_purpose == "project_context":
            basis = read_json(self.run_dir(record.project_id, record.run_id) / "basis.json") or {}
            issue = basis.get("context_dialogue")
            if not issue or issue.get("explanation_target") != record.target:
                raise RunError("The conversation's exact problem context is unavailable")
            return "## Exact problem context\n\n" + json.dumps({key: value for key, value in issue.items()
                if key != "problem_context"}, ensure_ascii=False, indent=1) + "\n\n"
        if record.assessment_purpose in ("issue_explanation", "issue_suggestions", "model_dialogue"):
            basis = read_json(self.run_dir(record.project_id, record.run_id) / "basis.json") or {}
            issue = basis.get("explanation_issue")
            if not issue or issue.get("explanation_target") != record.target:
                raise RunError("The conversation's exact issue context is unavailable")
            if record.target.get("kind") == "report_section":
                comment = issue.get("researcher_comment")
                return ("## Exact technical report section\n\n"
                    + json.dumps({key: value for key, value in issue.items() if key != "researcher_comment"}, ensure_ascii=False, indent=1)
                    + "\n\n## Saved researcher section comment at this question\n\n"
                    + (json.dumps(comment, ensure_ascii=False, indent=1) if comment else "No saved comment for this exact section version.")
                    + "\n\nThis comment is user-authored discussion context, not a validated fact or an adopted research instruction. "
                      "Later edits belong to later questions and do not change this turn's snapshot.\n\n")
            saved_answer = issue.get("researcher_answer")
            answer_context = ("## Saved researcher response note at conversation start\n\n"
                + json.dumps(saved_answer, ensure_ascii=False, indent=1) + "\n\n"
                + "This is the researcher's saved response to this exact item, with its recorded revision and source. "
                  "Use this snapshot for the item's response instead of any older answer in the frozen scientific sources. "
                  "A report or preference is not independent scientific validation. Later note edits are not part of this frozen conversation.\n\n"
                if saved_answer else "No saved researcher response to this exact item was included at conversation start. "
                    "Do not treat an answer to an earlier item or source version as this item's response.\n\n")
            return ("## Exact issue and original context\n\n" + basis.get("explanation_context_note", "") + "\n\n"
                    + json.dumps({key: value for key, value in issue.items() if key != "researcher_answer"}, ensure_ascii=False, indent=1)
                    + "\n\n" + answer_context)
        if record.phase == "P4":
            from .empirical_targets import empirical_target_context
            return empirical_target_context(self.run_dir(record.project_id, record.run_id), record.target)
        target = record.target
        for ref in self._upstream_records(record):
            if ref["family"] == target["family"] and ref["current"]["generation_id"] == target["generation_id"]:
                text, _, path = self._generation_text(ref["family_dir"], ref["current"])
                document = json.loads(text)
                component = self._component(document, target.get("object_id", ""))
                scope = ""
                if record.intent != "assessment":
                    allowed = self._repair_scope(document, target.get("object_id", ""))
                    scope = (
                        f"Existing mathematical components permitted to change: {json.dumps(sorted(allowed))}. "
                        "Preserve every other existing statement's text, quantifiers, regime and dependencies, and every other assumption's text and scope. "
                        "Existing upstream assumptions stay fixed unless selected; add explicit supporting assumptions or lemmas when needed. "
                        "Assessment/status fields may be updated. Identify affected empirical interpretations. "
                        "A scientific repair produces a complete reviewed replacement package.\n\n"
                    )
                return (f"## Exact researcher-selected component\n\nReference: {json.dumps(target)}\n\n"
                        f"Component:\n```json\n{json.dumps(component or document, ensure_ascii=False, indent=1)}\n```\n\n"
                        f"Read its complete frozen context at `{path}`.\n\n" + scope)
        raise RunError("Selected component is missing from the run's frozen inputs")

    @staticmethod
    def _repair_scope(document: dict, object_id: str) -> set[str]:
        statements = document.get("statements", [])
        allowed = {object_id}
        for item in [*statements, *document.get("assumptions", [])]:
            if RunEngine._component(item, object_id) is not None:
                allowed.add(item.get("statement_id") or item.get("assumption_id"))
        while True:
            affected = {s.get("statement_id") for s in statements
                        if set(s.get("depends_on_statement_ids", []) + s.get("assumption_ids", [])) & allowed}
            if affected <= allowed:
                return {item for item in allowed if item}
            allowed.update(affected)

    def _validate_repair_scope(self, record: RunRecord, documents: dict) -> list[Finding]:
        if record.phase != "P3" or not record.target or record.intent == "assessment":
            return []
        target = record.target
        source = next((ref for ref in self._upstream_records(record)
                       if ref["family"] == target["family"] and ref["current"]["generation_id"] == target["generation_id"]), None)
        if source is None:
            raise RunError("The repair target is absent from its frozen basis")
        original = json.loads(self._generation_text(source["family_dir"], source["current"])[0])
        allowed = self._repair_scope(original, target.get("object_id", ""))
        findings = []
        sections = (
            ("statements", "statement_id", ("statement_type", "text", "quantifiers", "regime", "assumption_ids", "depends_on_statement_ids")),
            ("assumptions", "assumption_id", ("text", "scope")),
            ("empirical_implications", "implication_id", ("text", "statement_ids", "conditions", "observable_or_metric", "expected_pattern", "falsifying_result")),
        )
        for output in ("p3.theory_candidate", "p3.complete_theory"):
            final = documents.get(output)
            if not isinstance(final, dict):
                continue
            for section, key, fields in sections:
                current = {item.get(key): item for item in final.get(section, []) if isinstance(item, dict)}
                for item in original.get(section, []):
                    identity = item.get(key)
                    if identity in allowed or (section == "empirical_implications" and set(item.get("statement_ids", [])) & allowed):
                        continue
                    if identity not in current or any(item.get(field) != current[identity].get(field) for field in fields):
                        findings.append(Finding("theory.repair_out_of_scope", f"Targeted repair removed or changed unrelated component {identity}.",
                                                output, f"/{section}/{identity}"))
        return findings

    def _review_brief(self, record: RunRecord, stage: StageSpec, workspace: Path, catalog: Catalog) -> str:
        """First-reader packet contains the exact manuscript, never team verdicts."""
        if frozen_review_packet_enabled(catalog):
            correction = ""
            if record.state == RunState.CORRECTING:
                findings = [f for f in record.findings_history[-1] if f.get("object_id") == "p5.outside_review"]
                correction = f"\n\nValidation correction note (verbatim): {record.correction_note}\nFindings: {json.dumps(findings)}\nChange only outside_review.json."
            return (
                ("# Independent technical report review\n\n" if technical_report_enabled(catalog)
                 else "# Independent manuscript review\n\n") + self._workspace_mechanics(workspace)
                + "You are a fresh first-time reader. The frozen submission packet is your only project-specific context. "
                "Do not search local project histories, team deliberations or specialist audits. "
                "Controlled public scholarly search is allowed; report its scope.\n\n"
                + (f"## Stage objective\n\n{stage.objective}\n\n" if stage.objective else "")
                + (f"## Your scientific responsibility\n\n{stage.role_objectives[MemberRole.OUTSIDE_REVIEWER.value]}\n\n"
                   if stage.role_objectives.get(MemberRole.OUTSIDE_REVIEWER.value) else "")
                + review_packet_brief(self.run_dir(record.project_id, record.run_id) / "review-packet")
                + f"\n\nWrite `{workspace / 'outside_review.json'}` using:\n```json\n{json.dumps(catalog.output_schema('p5.outside_review'), indent=1)}\n```\n"
                + correction
            )
        packet_dir = self.run_dir(record.project_id, record.run_id) / "review-packet"
        packet_dir.mkdir(parents=True, exist_ok=True)
        basis = read_json(packet_dir.parent / "basis.json")
        refs = []
        for ref in self._upstream_records(record):
            if ref["phase"] != "P5" or ref["family"] not in ("manuscript", "manuscript_candidate") or refs:
                continue
            text, _, source = self._generation_text(ref["family_dir"], ref["current"])
            document = json.loads(text)
            manuscript_artifact = document.get("manuscript_artifact")
            if manuscript_artifact:
                for index, artifact in enumerate([manuscript_artifact] + document.get("supplementary_artifacts", [])):
                    expected = artifact.get("sha256") or artifact.get("artifact_sha256")
                    frozen = next((a for a in (basis or {}).get("artifacts", [])
                                   if a["content_sha256"] == expected), None)
                    if basis is not None and frozen is None:
                        raise RunError("The selected manuscript file was unavailable when review was requested")
                    original = Path(frozen["path"]) if frozen else source_artifact_path(self.project_dir(record.project_id), ref["current"], artifact)
                    if not original.is_file() or sha256_file(original) != expected:
                        raise ArtifactError("The frozen manuscript file changed or disappeared")
                    target = packet_dir / (f"manuscript-{index}" + original.suffix)
                    target.write_bytes(original.read_bytes())
                    refs.append({"family": ref["family"] if index == 0 else "supplement",
                                 "generation_id": ref["current"]["generation_id"],
                                 "content_sha256": sha256_file(target), "path": str(target)})
            elif document.get("text") or document.get("markdown"):
                # Explicit inline legacy manuscripts remain reviewable.
                target = packet_dir / (ref["family"] + ".json")
                target.write_text(json.dumps({"text": document.get("text") or document["markdown"]}), encoding="utf-8")
                refs.append({"family": ref["family"], "generation_id": ref["current"]["generation_id"],
                             "content_sha256": sha256_file(target), "path": str(target)})
            else:
                raise RunError("The selected manuscript has no readable manuscript artifact")
        if not any(r["family"] in ("manuscript", "manuscript_candidate") for r in refs):
            raise RunError("Independent review requires an exact frozen manuscript")
        write_json_atomic(packet_dir / "manifest.json", {"records": refs})
        schema = catalog.output_schema("p5.outside_review")
        correction = ""
        if record.state == RunState.CORRECTING:
            findings = [f for f in record.findings_history[-1] if f.get("object_id") == "p5.outside_review"]
            correction = f"\n\nValidation correction note (verbatim): {record.correction_note}\nFindings: {json.dumps(findings)}\nChange only outside_review.json."
        return (
            "# Independent manuscript review\n\n"
            + self._workspace_mechanics(workspace)
            + "You are a fresh first-time reader. The following frozen packet is your only "
            "project-specific context. Do not search local project histories, team deliberations, or specialist audits. "
            "Controlled public scholarly search is allowed; report its scope.\n\n"
            + (f"## Stage objective\n\n{stage.objective}\n\n" if stage.objective else "")
            + (f"## Your scientific responsibility\n\n{stage.role_objectives[MemberRole.OUTSIDE_REVIEWER.value]}\n\n"
               if stage.role_objectives.get(MemberRole.OUTSIDE_REVIEWER.value) else "")
            + "\n".join(f"- {r['family']}: `{r['path']}` (sha256 {r['content_sha256']})" for r in refs)
            + f"\n\nReview the manuscript's clarity, validity, significance, limitations and missing evidence. "
            f"Write `{workspace / 'outside_review.json'}` using:\n```json\n{json.dumps(schema, indent=1)}\n```\n"
            + correction
        )
    # ------------------------------------------------------------------ #
    # Validation and correction (design/02 §4–5)
    # ------------------------------------------------------------------ #

    # Size caps per artifact type (SPEC §7): (bytes, hard?)
    _SIZE_CAPS = {
        "t1_card": (2048, True),
        "t2p_packet": (32768, True),
        "t2s_summary": (32768, True),
        "t3m_manuscript": (131072, False),  # advisory (D4: P5 assembly uncapped)
        "t3m_report": (131072, False),
    }

    @staticmethod
    def _output_filename(output_id: str) -> str:
        suffix = output_id.split(".", 1)[-1]
        return suffix + (".jsonl" if suffix == "metrics_long" else ".json")

    def validate_member_artifacts(self, record: RunRecord, stage: StageSpec,
                                  role: MemberRole, workspace: Path) -> dict:
        """Read-only checks over one author's drafts and permitted sealed inputs.

        The caller supplies a bound member workspace, never a model-selected
        path. A successful check is provisional until the complete stage and
        publication checks run; no scientific claim is assessed here.
        """
        checked = list(owned_writes(stage, role)) if role in stage.roles else []
        deferred = ["Scientific correctness, proof validity, and adequacy of the research are not assessed.",
                    "Publication against the current project basis is checked at publication."]
        findings = []
        try:
            plan = self._stages(record)
            if stage not in plan or role not in stage.roles:
                raise RunError("The member and stage do not belong to this run's frozen plan")
            expected = self.member_workspace(record, stage.stage_id, role).resolve()
            if Path(workspace).resolve() != expected:
                raise RunError("Draft validation requires this member's bound workspace")
            if self._authored_researcher_question(record, stage, workspace):
                return {"status": "passed", "checked_outputs": [], "findings": [],
                        "deferred_checks": ["Declared outputs remain partial while this stage waits for researcher input."]}
            readable = set(stage.role_reads.get(role.value, stage.reads))
            prerequisites = [prior for prior in plan if prior.sequence < stage.sequence
                             and record.stage_states.get(prior.stage_id) == "succeeded"]
            available = set(checked) | {output for prior in prerequisites for output in prior.writes
                                        if output in readable}
            omitted = sorted({output for item in plan for output in item.writes} - available)
            if omitted:
                deferred.append("Checks requiring other members' drafts, unreadable inputs, or later stages: "
                                + ", ".join(omitted) + ".")
            isolated_review = role is MemberRole.OUTSIDE_REVIEWER
            if isolated_review:
                prerequisites = []
                deferred.append("Checks needing internal project records are deferred; the independent review uses only its submitted artifacts and frozen review packet.")
            findings = self._validate_run_outputs(
                record, [stage], prerequisites, output_dirs={stage.stage_id: expected},
                scoped_outputs=set(checked), prerequisite_outputs=readable,
                isolated_review=isolated_review,
            )
            if any(f.code.startswith("schema.") or f.code in {
                "output.invalid_json", "output.jsonl_malformed", "output.schema_violation",
                "output.required_missing", "output.prerequisite_unavailable",
            } for f in findings):
                deferred.append("Consistency checks requiring missing, unreadable, or malformed documents await valid files.")
            status = "failed" if any(f.blocks_publication for f in findings) else "passed"
        except (OSError, ValueError, CatalogError, RunError, ArtifactError) as exc:
            status = "unavailable"
            findings.append(Finding("draft.validation_unavailable", str(exc), checked[0] if checked else "", ""))
            deferred.append("Draft validation could not finish; no successful validation is established.")
        return {"status": status, "checked_outputs": checked,
                "findings": [asdict(finding) for finding in findings],
                "deferred_checks": deferred, "scientific_correctness": "not_assessed"}

    def _validate_required_outputs(self, record: RunRecord, stages: list[StageSpec], *,
                                   output_dirs: dict[str, Path] | None = None,
                                   scoped_outputs: set[str] | None = None) -> list[Finding]:
        """Check delivery only, without requiring later stages' artifacts."""
        findings = []
        run_dir = self.run_dir(record.project_id, record.run_id)
        for stage in stages:
            for output_id in stage.writes:
                if scoped_outputs is not None and output_id not in scoped_outputs:
                    continue
                out_dir = Path((output_dirs or {}).get(stage.stage_id, run_dir / "outputs" / stage.stage_id))
                path = out_dir / self._output_filename(output_id)
                if not path.resolve().is_relative_to(out_dir.resolve()):
                    findings.append(Finding("output.path_outside_workspace", "Output resolves outside its assigned artifact folder.", output_id, ""))
                elif not path.is_file():
                    findings.append(Finding(
                        code="output.required_missing",
                        message=f"Required output '{output_id}' was not produced.",
                        object_id=output_id,
                        json_pointer="",
                    ))
        return findings

    def _validate_run_outputs(self, record: RunRecord, stages: list[StageSpec],
                              prerequisite_stages: list[StageSpec] | None = None, *,
                              output_dirs: dict[str, Path] | None = None,
                              scoped_outputs: set[str] | None = None,
                              prerequisite_outputs: set[str] | None = None,
                              isolated_review: bool = False):
        catalog = self._catalog(record)
        findings = self._validate_required_outputs(record, stages, output_dirs=output_dirs,
                                                   scoped_outputs=scoped_outputs)
        documents = {}
        roots = {}
        run_dir = self.run_dir(record.project_id, record.run_id)
        for stage in stages:
            out_dir = Path((output_dirs or {}).get(stage.stage_id, run_dir / "outputs" / stage.stage_id))
            for output_id in stage.writes:
                if scoped_outputs is not None and output_id not in scoped_outputs:
                    continue
                suffix = output_id.split(".", 1)[-1]
                # metrics_long is JSONL (one schema-validated row per line);
                # everything else is a single JSON document.
                filename = suffix + (".jsonl" if suffix == "metrics_long" else ".json")
                path = out_dir / filename
                if not path.resolve().is_relative_to(out_dir.resolve()) or not path.is_file():
                    continue
                # Artifact-type size caps (SPEC §7). For T1 card
                # COLLECTIONS the 2 KB cap binds each card, not the file
                # (a 13-card collection is naturally > 2 KB); the file
                # itself is bounded at 32 KB as a sanity cap.
                meta = stage.artifact_contracts.get(output_id) or {}
                atype = meta.get("artifact_type")
                cap = self._SIZE_CAPS.get(atype)
                if cap:
                    limit, hard = cap
                    if output_id == "p4.diagnostics":
                        # Exhaustive case/metric coverage is structured evidence,
                        # not a concise summary that can fit a fixed packet cap.
                        hard = False
                    size = path.stat().st_size
                    over = size > limit
                    if atype == "t1_card":
                        try:
                            items = json.loads(path.read_text(encoding="utf-8"))
                            if isinstance(items, list):
                                over = size > 32768 or any(
                                    len(json.dumps(c).encode("utf-8")) > limit
                                    for c in items
                                )
                        except Exception:  # noqa: BLE001 - schema layer catches parse errors
                            over = size > 32768
                    if over:
                        findings.append(
                            Finding(
                                code="output.size_cap_exceeded",
                                message=(
                                    f"Output '{output_id}' is {size:,} B; "
                                    f"{meta['artifact_type']} cap is {limit:,} B."
                                ),
                                object_id=output_id,
                                json_pointer="",
                                blocks_publication=hard,
                            )
                        )
                if suffix == "metrics_long":
                    row_findings = self._validate_jsonl_rows(catalog, output_id, path)
                    findings.extend(row_findings)
                    if any(f.blocks_publication for f in row_findings):
                        continue
                    try:
                        documents[output_id] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                        roots[output_id] = out_dir
                    except ValueError:
                        pass
                    continue
                try:
                    document = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    findings.append(Finding(code="output.invalid_json", message=str(exc), object_id=output_id, json_pointer=""))
                    continue
                schema_findings = catalog.validate_output(output_id, document)
                if (record.phase == "P1" and self._framework_p1(catalog)
                        and output_id in {"p1.lead_literature", "p1.theory_literature", "p1.empirical_literature", "p1.research_basis"}
                        and isinstance(document, dict)):
                    from .p1_science import required_p1_version
                    expected_version = required_p1_version(catalog, output_id)
                    if document.get("schema_version") != expected_version:
                        schema_findings.append(Finding("schema.const", f"This P1 output requires artifact schema_version {expected_version}.",
                                                       output_id, "/schema_version"))
                findings.extend(schema_findings)
                if any(f.blocks_publication for f in schema_findings):
                    continue  # Semantic checks require the declared document shape.
                documents[output_id] = document
                roots[output_id] = out_dir
                if suffix == "exhibits" and isinstance(document, list):
                    findings.extend(self._validate_exhibits(output_id, document, out_dir))
                if suffix == "diagnostics" and isinstance(document, dict):
                    findings.extend(
                        self._validate_diagnostics(record, stage, output_id, document, out_dir=out_dir)
                    )
        from .math_validation import validate_authored_math
        findings.extend(validate_authored_math(documents, artifact_roots=roots))
        if record.intent != "assessment":
            # A partial correction still depends on the unchanged earlier
            # submissions. Load them for reference checks without broadening
            # the schema/correction scope or reading stale downstream reviews.
            for stage in prerequisite_stages or []:
                out_dir = run_dir / "outputs" / stage.stage_id
                for output_id in stage.writes:
                    if prerequisite_outputs is not None and output_id not in prerequisite_outputs:
                        continue
                    suffix = output_id.split(".", 1)[-1]
                    path = out_dir / (suffix + (".jsonl" if suffix == "metrics_long" else ".json"))
                    try:
                        if not path.resolve().is_relative_to(out_dir.resolve()):
                            raise ValueError("Prerequisite output resolves outside its sealed artifact folder")
                        text = path.read_text(encoding="utf-8")
                        document = ([json.loads(line) for line in text.splitlines() if line.strip()]
                                    if suffix == "metrics_long" else json.loads(text))
                        invalid = (self._validate_jsonl_rows(catalog, output_id, path) if suffix == "metrics_long"
                                   else catalog.validate_output(output_id, document))
                        if any(f.blocks_publication for f in invalid):
                            findings.extend(invalid)
                            continue
                        documents[output_id] = document
                        roots[output_id] = out_dir
                    except (OSError, ValueError) as exc:
                        findings.append(Finding(code="output.prerequisite_unavailable", message=str(exc),
                                                object_id=output_id, json_pointer=""))
            from .validation import validate_scientific_outputs
            basis = {} if isolated_review else ResearcherPauseStore(run_dir).context_basis(record, read_json(run_dir / "basis.json") or {})
            if isolated_review:
                roots["review_packet"] = run_dir / "review-packet"
            if record.phase == "P5" and frozen_review_packet_enabled(catalog):
                findings.extend(validate_review_packet_outputs(run_dir / "review-packet", documents))
                if not technical_report_enabled(catalog):
                    findings.extend(validate_manuscript_scope(catalog, documents, basis))
            frozen_method = basis.get("method") or {}
            findings.extend(validate_scientific_outputs(catalog, record.phase, documents,
                            artifact_roots=roots, frozen_method=frozen_method.get("identity") or frozen_method,
                            frozen_basis=basis))
            findings.extend(self._validate_p4_execution(record, documents))
            findings.extend(self._validate_repair_scope(record, documents))
            from .direct_validation import validate_direct_outputs
            findings.extend(validate_direct_outputs(record.phase, documents, supplied_method=record.supplied_method,
                            lead_instructions=record.instructions,
                            previous_library=self._cumulative_input(record, "literature_library") if record.phase == "P1" else None,
                            mode=record.mode, frozen_method=frozen_method,
                            previous_catalog=self._cumulative_input(record, "method_catalog") if record.phase == "P2" else None,
                            run_id=record.run_id, catalog=catalog))
            deferred_discovery = (record.phase == "P1" and "p1.research_basis" not in documents
                                  and any(f.code == "literature.metadata_reconciliation_pending" for f in findings))
            if not isolated_review and catalog.scientific_validation_enabled and not any(f.blocks_publication for f in findings) and not deferred_discovery:
                try:
                    self._cumulative_outputs(record, {key.split(".", 1)[-1]: value for key, value in documents.items()})
                except ArtifactError as exc:
                    if any(f.code == "literature.source_identity_conflict" for f in findings):
                        # The exact conflicting entries and producing outputs
                        # are already reported; do not misroute them to the lead.
                        return findings
                    output_id = ({"P1": "p1.research_basis", "P2": "p2.catalog_assessment"}.get(record.phase)
                                 if any(key in documents for key in ("p1.research_basis", "p2.catalog_assessment")) else
                                 {"P1": "p1.source_changes", "P2": "p2.method_changes", "P5": "p5.review_issues"}.get(record.phase))
                    if output_id not in documents:
                        output_id = next((key for key in documents if key.startswith(record.phase.lower() + ".")), output_id)
                    findings.append(Finding(code="output.cumulative_conflict", message=str(exc), object_id=output_id, json_pointer=""))
        elif "p3.assessment" in documents:
            basis = read_json(run_dir / "basis.json") or {}
            available = {(r["family"], r["generation_id"]) for r in basis.get("records", [])}
            for ref in documents["p3.assessment"].get("evidence_refs", []):
                if (ref.get("family"), ref.get("generation_id")) not in available:
                    findings.append(Finding(code="assessment.unknown_source", message="Assessment cites a source outside its frozen basis",
                                            object_id="p3.assessment", json_pointer="/evidence_refs"))
        return findings

    def _validate_jsonl_rows(self, catalog: Catalog, output_id: str, path: Path):
        """Line-wise validation of a JSONL diagnostic substrate (design/15 §3)."""
        findings = []
        schema_name = catalog.schema_for_output(output_id)
        if not schema_name:
            return findings
        schema = catalog.schema_doc(schema_name)
        import jsonschema

        validator = jsonschema.Draft202012Validator(schema)
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                findings.append(Finding(
                    code="output.jsonl_malformed",
                    message=f"'{output_id}' line {lineno} is not valid JSON: {exc.msg}.",
                    object_id=output_id, json_pointer=f"/line/{lineno}",
                ))
                continue
            for err in validator.iter_errors(row):
                findings.append(Finding(
                    code="output.schema_violation",
                    message=f"'{output_id}' line {lineno}: {err.message}",
                    object_id=output_id, json_pointer=f"/line/{lineno}",
                ))
        return findings

    def _validate_exhibits(self, output_id: str, exhibits: list, out_dir: Path):
        """Every exhibit's artifact must exist in the run folder and match its
        sealed sha256 (design/15: the card is the display layer, the file is
        the evidence)."""
        findings = []
        for ex in exhibits:
            if not isinstance(ex, dict):
                continue
            eid = ex.get("exhibit_id", "?")
            rel = str(ex.get("artifact_path", ""))
            target = (out_dir / rel).resolve()
            if not rel or not target.is_relative_to(out_dir.resolve()) or not target.is_file():
                findings.append(Finding(
                    code="exhibit.artifact_missing",
                    message=f"Exhibit '{eid}' artifact '{rel}' was not found in the run folder.",
                    object_id=output_id, json_pointer=f"/{eid}",
                ))
                continue
            import hashlib as _hl
            actual = _hl.sha256(target.read_bytes()).hexdigest()
            if actual != str(ex.get("artifact_sha256", "")):
                findings.append(Finding(
                    code="exhibit.digest_mismatch",
                    message=f"Exhibit '{eid}' artifact sha256 does not match the sealed digest.",
                    object_id=output_id, json_pointer=f"/{eid}/artifact_sha256",
                ))
        return findings

    def _validate_diagnostics(self, record: RunRecord, stage: StageSpec, output_id: str, doc: dict, *,
                              out_dir: Path | None = None):
        """D22: the regeneration script named in regenerated_by must exist in
        the member's workspace — diagnostics must be recomputable from
        metrics_long, never hand-edited."""
        script = str(doc.get("regenerated_by", ""))
        if not script or Path(script).is_absolute() or ".." in Path(script).parts:
            return [Finding(
                code="diagnostics.script_missing",
                message=f"'{output_id}' must name a regeneration script in regenerated_by.",
                object_id=output_id, json_pointer="/regenerated_by",
            )]
        role = stage.roles[0]
        workspace = self.member_workspace(record, stage.stage_id, role)
        sealed_root = out_dir or self.run_dir(record.project_id, record.run_id) / "outputs" / stage.stage_id
        sealed_scripts = [sealed_root / script]
        if self._progressive_p4(record):
            # Preserve the authored diagnostic bytes and resolve the collector's
            # working-file location without changing the cited source digest.
            sealed_scripts.append(sealed_root / "working" / role.value / script)
        found = any(path.resolve().is_relative_to(sealed_root.resolve()) and path.is_file() for path in sealed_scripts)
        if not found and (out_dir is not None or not (workspace / script).is_file()):
            return [Finding(
                code="diagnostics.script_missing",
                message=(
                    f"Regeneration script '{script}' was not found in the "
                    f"{role.value} workspace for this run."
                ),
                object_id=output_id, json_pointer="/regenerated_by",
            )]
        return []

    async def correct(self, project_id: str, run_id: str, note: str = "") -> RunRecord:
        """The single bounded correction (design/02 §5)."""
        if self.shutting_down:
            raise RunError("The local service is shutting down; request correction after it restarts.")
        record = self.load_run(project_id, run_id)
        async with self._lock(f"phase:{project_id}:{record.branch_id}:{record.phase}"):
            return await self._correct_locked(project_id, run_id, note)

    async def _correct_locked(self, project_id: str, run_id: str, note: str) -> RunRecord:
        if self.shutting_down:
            raise RunError("The local service is shutting down; request correction after it restarts.")
        async with self._lock(run_id):
            if self.shutting_down:
                raise RunError("The local service is shutting down; request correction after it restarts.")
            record = self.load_run(project_id, run_id)
            reason = self.correction_block_reason(record)
            if reason:
                raise RunError(reason)
            record.correction_attempts += 1
            record.state = RunState.CORRECTING
            record.correction_note = note
            declared = {o for s in self._stages(record) for o in s.writes}
            record.correction_scope = sorted({f["object_id"] for f in record.findings_history[-1]
                                             if f.get("blocks_publication", True) and f["object_id"] in declared})
            if not record.correction_scope:
                raise RunError("These findings have no bounded output correction; start a new scientific run")
            record.updated_at = _now()
            self._save_run(record)
        self._event(record, "run.correcting", "Correction turn authorized.")
        if self.shutting_down:
            raise RunError("The local service is shutting down; request correction after it restarts.")
        task = asyncio.create_task(self._drive_correction(record))
        self._tasks[run_id] = task
        self._task_projects[run_id] = project_id
        return record

    def correction_block_reason(self, record: RunRecord) -> str | None:
        """Use the same eligibility rules for the preview and authorization."""
        directory = self.run_dir(record.project_id, record.run_id)
        try:
            from .providers import load_provider_config
            provider_config = load_provider_config(self.data_root)
            if provider_config.error:
                return provider_config.error
            try:
                provider_config.require_ready()
            except ValueError as exc:
                return str(exc)
            if not (directory / "contracts").is_dir() or not (directory / "stage-plan.json").is_file():
                raise RunError("This historical run did not freeze its contracts and inputs; start a new run")
            catalog = self._catalog(record)
            if catalog.scientific_validation_enabled and catalog.verify_manifest():
                raise RunError("The run's frozen catalog is damaged; start a new run after checking its sources")
            if record.state is not RunState.FAILED or not record.findings_history:
                raise RunError("Correction applies to a failed run with validation findings")
            if record.correction_attempts >= 1:
                raise RunError("Correction attempt already spent; start a fresh run")
            self._assert_phase_available(record.project_id, record.phase, record.branch_id, excluding=record.run_id)
            self._assert_publication_current(record)
            declared = {o for s in self._stages(record) for o in s.writes}
            if not any(f.get("blocks_publication", True) and f.get("object_id") in declared for f in record.findings_history[-1]):
                raise RunError("These findings have no bounded output correction; start a new scientific run")
        except CatalogError:
            return "The run's frozen catalog is damaged; start a new run after checking its sources"
        except (RunError, ArtifactError) as exc:
            return str(exc)
        return None

    async def _drive_correction(self, record: RunRecord) -> None:
        try:
            stages = self._stages(record)
            run_dir = self.run_dir(record.project_id, record.run_id)
            for name in ("outputs", "briefs"):
                if (run_dir / name).is_dir():
                    shutil.copytree(run_dir / name, run_dir / "attempts" / "original" / name)
            scope = set(record.correction_scope)
            first_sequence = min(s.sequence for s in stages if scope.intersection(s.writes))
            for stage in stages:
                if scope.intersection(stage.writes) and stage.sequence == first_sequence:
                    record.stage_states[stage.stage_id] = "correcting"
                elif stage.sequence > first_sequence:
                    record.stage_states[stage.stage_id] = "pending"
            self._save_run(record)
            self._event(record, "stage.correcting", "Correcting the affected outputs before refreshing downstream reviews.")
            earliest = None
            for stage in stages:
                affected = scope.intersection(stage.writes)
                if not affected or stage.sequence != first_sequence:
                    continue
                before = {}
                for output in stage.writes:
                    filename = output.split(".", 1)[-1] + (".jsonl" if output.endswith("metrics_long") else ".json")
                    path = run_dir / "outputs" / stage.stage_id / filename
                    before[output] = path.read_bytes() if path.exists() else None
                for role in stage.roles:
                    if not affected.intersection(owned_writes(stage, role)):
                        continue
                    result = await self._drive_member_turn(record, stage, role, run_dir)
                    if self._progressive_p4(record) and self._p4_controller(record).snapshot().get("pause_request"):
                        await self._settle_p4_wait(record)
                        return
                    if not result.succeeded:
                        raise RunError(result.diagnostic or "Correction turn failed")
                    current = self.load_run(record.project_id, record.run_id)
                    for key in ("input_tokens", "output_tokens"):
                        current.usage[key] = current.usage.get(key, 0) + result.usage.get("turn_" + key, 0)
                    self._save_run(current)
                    record = current
                for output, old in before.items():
                    filename = output.split(".", 1)[-1] + (".jsonl" if output.endswith("metrics_long") else ".json")
                    path = run_dir / "outputs" / stage.stage_id / filename
                    new = path.read_bytes() if path.exists() else None
                    if new != old and output not in scope:
                        raise RunError(f"Correction changed an out-of-scope output: {output}")
                earliest = stage.sequence if earliest is None else min(earliest, stage.sequence)
            corrected_stages = [s for s in stages if s.sequence == first_sequence and scope.intersection(s.writes)]
            prerequisites = [s for s in stages if s.sequence < first_sequence
                             and record.stage_states.get(s.stage_id) == "succeeded"]
            corrected_findings = self._validate_run_outputs(record, corrected_stages, prerequisites)
            record = self.load_run(record.project_id, record.run_id)
            for stage in corrected_stages:
                if scope.intersection(stage.writes):
                    blocked = any(f.blocks_publication and f.object_id in stage.writes for f in corrected_findings)
                    record.stage_states[stage.stage_id] = "failed" if blocked else "succeeded"
            self._save_run(record)
            if any(f.blocks_publication for f in corrected_findings):
                record.findings_history.append([asdict(f) for f in corrected_findings])
                self._save_run(record)
                raise RunError("Correction did not resolve the blocking findings")
            # Changed upstream content invalidates prior downstream reviews.
            record = await self._transition(record, RunState.RUNNING, "Refreshing reviews affected by the correction.")
            for stage in stages:
                if earliest is None or stage.sequence <= earliest:
                    continue
                for role in stage.roles:
                    workspace = self.member_workspace(record, stage.stage_id, role)
                    for output in owned_writes(stage, role):
                        filename = output.split(".", 1)[-1] + (".jsonl" if output.endswith("metrics_long") else ".json")
                        for path in (workspace / filename, run_dir / "outputs" / stage.stage_id / filename):
                            if path.is_file():
                                path.unlink()
                result = await self._execute_stage(record, stage)
                if self.load_run(record.project_id, record.run_id).state == RunState.AWAITING_USER:
                    return
                if not result.succeeded:
                    raise RunError(result.diagnostic or f"Review stage {stage.stage_id} failed")
                record = self.load_run(record.project_id, record.run_id)
            record = await self._transition(record, RunState.VALIDATING, "Re-validating corrected outputs.")
            findings = self._validate_run_outputs(record, stages)
            record.findings_history.append([asdict(f) for f in findings])
            self._save_run(record)
            if any(f.blocks_publication for f in findings):
                raise RunError("Correction did not resolve the blocking findings")
            if record.intent == "assessment":
                self._save_assessment(record)
                await self._transition(record, RunState.ASSESSED, "Assessment complete after correction.")
            else:
                self._publish(record, stages)
                await self._transition(record, RunState.PUBLISHED, "Run published after correction.")
        except asyncio.CancelledError:
            current = self.load_run(record.project_id, record.run_id)
            if current.state not in TERMINAL_STATES:
                await self._transition(current, RunState.CANCELLED, "Correction cancelled.")
        except Exception as exc:
            current = self.load_run(record.project_id, record.run_id)
            for stage_id, status in current.stage_states.items():
                if status in ("correcting", "running"):
                    current.stage_states[stage_id] = "failed"
            self._save_run(current)
            await self._fail(record, str(exc))

    # ------------------------------------------------------------------ #
    # Cancellation
    # ------------------------------------------------------------------ #

    async def shutdown(self) -> None:
        """Stop this process's work before closing its provider connections."""
        self.shutting_down = True
        async with self._shutdown_lock:
            if self._shutdown_complete:
                return

            async def stop_owned(run_id, task):
                project_id = self._task_projects.get(run_id)
                cancellation_error = None
                if project_id is None:
                    # Support in-process drivers that register their own task.
                    paths = list(self.data_root.glob(f"projects/*/runs/{run_id}/run.json"))
                    if len(paths) == 1:
                        project_id = paths[0].parents[2].name
                if project_id is not None:
                    try:
                        await self.cancel(project_id, run_id)
                        return
                    except RunError:
                        if task.done():
                            return  # Publication won the race with shutdown.
                    except Exception as exc:
                        cancellation_error = exc
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                if cancellation_error is not None:
                    raise cancellation_error

            outcomes = await asyncio.gather(*(stop_owned(run_id, task)
                for run_id, task in list(self._tasks.items()) if not task.done()), return_exceptions=True)
            close = getattr(self.bridge, "close", None)
            if close is not None:
                await close()
            errors = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
            if errors:
                raise RunError("Local service could not finish stopping its active work: " + str(errors[0]))
            self._shutdown_complete = True

    async def cancel(self, project_id: str, run_id: str) -> RunRecord:
        record = self.load_run(project_id, run_id)
        if record.state in TERMINAL_STATES:
            raise RunError(f"run is already {record.state}")
        record.terminal_reason = "cancelled_by_researcher"
        self._save_run(record)
        task = self._tasks.get(run_id)
        if task is not None and not task.done():
            if not task.cancelling():
                task.cancel()
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                if not task.done():
                    raise
        current = self.load_run(project_id, run_id)
        if run_id in self._cancellation_failures:
            current.state = RunState.FAILED
            current.terminal_reason = self._cancellation_failures.pop(run_id)
            for stage_id, status in current.stage_states.items():
                if status in ("running", "correcting", "cancelled"):
                    current.stage_states[stage_id] = "failed"
            self._save_run(current)
            self._event(current, "run.failed", current.terminal_reason)
            return current
        if current.state in TERMINAL_STATES:
            return current
        return await self._transition(current, RunState.CANCELLED, "Run cancelled by researcher.")

    # ------------------------------------------------------------------ #
    # Publication (design/03 §4): atomic package visibility after preparation
    # ------------------------------------------------------------------ #

    def _cumulative_outputs(self, record: RunRecord, documents: dict) -> dict:
        """Deterministic indexes over the run's authorized accumulated state."""
        from .direct_artifacts import derive_direct_records
        derived = derive_direct_records(record.phase, documents, run_id=record.run_id,
                                        previous_library=self._cumulative_input(record, "literature_library"))
        documents = {**documents, **derived}
        family = {"P1": "literature_library", "P2": "method_catalog", "P5": "review_issue_ledger"}.get(record.phase)
        if not family:
            return derived
        previous = self._cumulative_input(record, family)
        if previous is None:
            raise ArtifactError(f"This run has no frozen {family}; start a new run against the current research")
        if record.phase == "P1" and "source_changes" in documents:
            from .p1_science import reconciliation_enabled, reconciled_library
            if reconciliation_enabled(documents):
                derived[family] = reconciled_library(documents, previous, run_id=record.run_id)
                return derived
            from .literature import build_library
            derived[family] = build_library(previous, documents["source_changes"], run_id=record.run_id)
            if "research_basis" in documents:
                from .direct_artifacts import apply_direct_literature
                derived[family] = apply_direct_literature(derived[family], documents, run_id=record.run_id)
        elif record.phase == "P2" and "method_changes" in documents:
            if "catalog_assessment" in documents:
                from .direct_artifacts import build_direct_method_catalog
                derived[family] = build_direct_method_catalog(previous, documents["method_changes"], run_id=record.run_id, documents=documents)
                return derived
            from .direct_artifacts import build_incremental_method_catalog
            stage_id = next((s.stage_id for s in self._stages(record) if "p2.method_changes" in s.writes), None)
            derived[family] = build_incremental_method_catalog(previous, documents["method_changes"],
                                                               run_id=record.run_id, stage_id=stage_id)
        elif record.phase == "P5":
            from .review_ledger import build_review_ledger
            derived[family] = build_review_ledger(previous, documents.get("review_issues", []), record.run_id)
        return derived

    def _publish(self, record: RunRecord, stages: list[StageSpec]) -> None:
        project_dir = self.project_dir(record.project_id)
        run_dir = self.run_dir(record.project_id, record.run_id)
        if record.intent == "assessment":
            raise RunError("Assessments cannot publish scientific records")
        basis = read_json(run_dir / "basis.json") or {}
        expected_current = self._assert_publication_current(record)
        if record.phase == "P4" and record.target:
            from .empirical_targets import empirical_target_context
            empirical_target_context(run_dir, record.target)
        receipt_id = new_id("receipt")
        data_records = {}
        formats = {}
        stage_ids = {}
        for stage in stages:
            out_dir = run_dir / "outputs" / stage.stage_id
            for output in stage.writes:
                family = output.split(".", 1)[-1]
                fmt = "jsonl" if family == "metrics_long" else "json"
                path = out_dir / (family + "." + fmt)
                if not path.is_file():
                    raise RunError(f"Validated output disappeared before publication: {output}")
                data_records[family] = path.read_bytes()
                formats[family] = fmt
                stage_ids[family] = stage.stage_id
        aliases = {
            "P1": {"literature_synthesis": "synthesis_candidate", "literature_coverage": "coverage_candidate"},
            "P3": {"theory_record": "complete_theory"},
            "P4": {"empirical_evidence_index": "empirical_index_candidate", "empirical_synthesis": "empirical_synthesis_candidate",
                   "implementation_record": "implementation_record_candidate"},
            "P5": {"manuscript": "manuscript_candidate"},
        }.get(record.phase, {})
        if record.phase == "P5" and technical_report_enabled(self._catalog(record)):
            aliases = {"technical_report": "technical_report_candidate"}
        for alias, source in aliases.items():
            if source in data_records:
                data_records[alias] = data_records[source]
                stage_ids[alias] = stage_ids[source]
        if self._catalog(record).scientific_validation_enabled:
            derived = self._cumulative_outputs(record, {family: json.loads(raw) for family, raw in data_records.items() if formats.get(family) != "jsonl"})
            for family, document in derived.items():
                data_records[family] = json.dumps(document, ensure_ascii=False).encode()
                formats[family] = "json"
        rollout_digests = {}
        for key, thread_id in record.thread_ids.items():
            role = MemberRole(key.split(":", 1)[0])
            home = codex_home(project_dir, role)
            if role == MemberRole.OUTSIDE_REVIEWER:
                home = run_dir / "isolated" / role.value / "codex-home"
            matches = list((home / "sessions").rglob(f"*{thread_id}.jsonl")) if (home / "sessions").is_dir() else []
            rollout_digests[key] = {"thread_id": thread_id,
                                    "sha256": sha256_file(matches[0]) if len(matches) == 1 else None,
                                    "available": len(matches) == 1}
        write_json_atomic(run_dir / "rollout-digests.json", rollout_digests)
        # Freeze process counts with this publication. Later readers must not
        # infer successful repairs from an in-progress or failed run record.
        publication_history = ({
            "mechanical_repair_rounds": sum(record.mechanical_repair_attempts.values()),
            "researcher_correction_attempts": record.correction_attempts,
        } if record.phase == "P2" else None)
        def prepare_receipt(package):
            receipt = {
                "receipt_id": receipt_id, "run_id": record.run_id,
                "phase": record.phase, "branch_id": record.branch_id,
                "package_id": package["package_id"],
                "generations": [{"family": f, **pointer} for f, pointer in package["records"].items()],
                "thread_rollouts": rollout_digests, "catalog_pin": record.catalog_pin,
                "basis_sha256": record.basis_sha256,
                "authorizing_command": {"mode": record.mode, "instructions": record.instructions,
                                         "target": record.target, "intent": record.intent,
                                         "supplied_method": record.supplied_method},
                "committed_at": package["published_at"],
            }
            if publication_history is not None:
                receipt["publication_history"] = publication_history
            receipt["receipt_sha256"] = sha256_bytes(json.dumps(receipt, ensure_ascii=False, sort_keys=True).encode())
            write_json_atomic(project_dir / "authority" / "receipts" / f"{receipt_id}.json", receipt)
            append_jsonl(project_dir / "authority" / "journal.jsonl", {
                "at": package["published_at"], "type": "publication_prepared", "receipt_id": receipt_id,
                "run_id": record.run_id, "package_id": package["package_id"],
                "receipt_sha256": receipt["receipt_sha256"],
                "authority": "committed only when referenced by current-package.json or later committed package history",
            })
            self._event(record, "run.promoting", f"Prepared complete package {package['package_id']}.")
        publish_package(
            project_dir / "branches" / record.branch_id / "phases" / record.phase.lower(), data_records,
            run_id=record.run_id, phase=record.phase, branch_id=record.branch_id,
            metadata={"receipt_id": receipt_id, "catalog_pin": record.catalog_pin,
                      "basis_sha256": record.basis_sha256, "method": basis.get("method"),
                      **({"publication_history": publication_history} if publication_history is not None else {}),
                      "prior_evidence": [r for r in basis.get("records", []) if r.get("phase") == "P4"],
                      "formats": formats, "stage_ids": stage_ids},
            before_commit=prepare_receipt,
            expected_current=expected_current,
        )

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def run_events(self, project_id: str, run_id: str) -> tuple[list[dict], int]:
        return read_jsonl(self.run_dir(project_id, run_id) / "events.jsonl")
