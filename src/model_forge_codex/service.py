"""FastAPI service shell (design/07). REST only in the skeleton; SSE run
activity lands with the UI increment.

Run:  uvicorn model_forge_codex.service:app --port 8766
Data root: env MF_CODEX_HOME (default ~/.model-forge-codex).
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .bridge import CodexBridge, SdkCodexBridge
from .domain import MemberConfig, MemberRole
from .members import provision_member, provision_team
from .runs import RunEngine, RunError
from .p4_execution import P4ExecutionError
from .storage import read_json, write_json_atomic
from .records import ArtifactError, current_records, read_generation
from .research import artifacts_view
from .accounts import AccountError, AccountService
from .project_brief import normalize_project
from .problem_context import (supports_problem_context, load_problem_context,
    initialize_problem_context, refresh_problem_context_brief, save_context_item,
    confirm_context_amendment, save_scoped_answer)
from .probe import run_provider_probe
from .providers import CONTROLLED_FIELDS, ProviderConfigConflict, ProviderConfigError, editor_view, load_provider_config, write_provider_config


def default_data_root() -> Path:
    return Path(os.environ.get("MF_CODEX_HOME", Path.home() / ".model-forge-codex"))


class CreateProject(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    research_question: str = ""
    research_instructions: str = ""
    venue_length: str = ""  # Retained for legacy clients; reports have no venue quota.

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Project name must not be blank")
        return value.strip()


class UpdateProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    research_instructions: str | None = None
    setting_amendment: str | None = None
    setting_amends: list[dict] | None = None

    @model_validator(mode="after")
    def valid_edit(self):
        if not self.model_fields_set:
            raise ValueError("Send at least one project brief field")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Project brief fields must be strings; use an empty string to clear optional text")
        if "name" in self.model_fields_set:
            if not self.name.strip():
                raise ValueError("Project name must not be blank")
            self.name = self.name.strip()
        if "setting_amendment" in self.model_fields_set and not self.setting_amendment.strip():
            raise ValueError("A setting amendment must not be blank")
        if "setting_amends" in self.model_fields_set and "setting_amendment" not in self.model_fields_set:
            raise ValueError("Explicit setting targets accompany a setting amendment")
        return self


class PhaseTwoPreparation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instructions: str
    input_ids: list[str] | None = None


class ImportResearcherInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=160)
    role: str
    content_base64: str = Field(min_length=1, max_length=89478488)
    description: str = Field(default="", max_length=4000)
    mapping: dict = Field(default_factory=dict)


class ContextEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    statement: str = Field(min_length=1)
    item_id: str | None = None
    origin: str = "researcher_reported"
    scope: dict | None = None
    answer_refs: list[dict] = Field(default_factory=list)
    source_refs: list[dict] = Field(default_factory=list)
    amends: list[dict] = Field(default_factory=list)
    topic: str | None = None


class ContextConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    statement: str | None = None


class MemberUpdate(BaseModel):
    model: str | None = None
    reasoning_effort: str | None = None
    soul: str | None = None
    provider: str | None = None          # "openai" | "custom"
    provider_base_url: str | None = None
    provider_env_key: str | None = None
    provider_id: str | None = None
    auto_compact_tokens: int | None = None
    max_turn_input_tokens: int | None = None


class SuppliedMethod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    specification_markdown: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)

    @field_validator("title", "specification_markdown", "source_reference")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Supplied method fields must not be blank")
        return value  # Preserve the researcher's text exactly.


class StartRun(BaseModel):
    phase: str
    mode: str
    branch_id: str = "trunk"
    basis_sha256: str = ""
    instructions: str = ""
    idempotency_key: str | None = None
    intent: str = "run"
    target: dict | None = None
    assessment_id: str | None = None
    assessment_purpose: str = "assessment"
    researcher_note_draft: str | None = None
    retry_run_id: str | None = None
    supplied_method: SuppliedMethod | None = None
    budget_seconds: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    context_refs: list[dict] = Field(default_factory=list)
    input_ids: list[str] = Field(default_factory=list, max_length=32)


class ContinueEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=1)
    answer: str = ""
    action: str = "continue"
    context_choice: str | None = None
    idempotency_key: str = Field(min_length=1)
    additional_budget_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)
    answer_revision: int | None = Field(default=None, ge=1)


class SavedDecisionAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=1)
    note: str
    expected_answer_revision: int | None = Field(default=None, ge=0)
    context_refs: list[dict] = Field(default_factory=list)
    scope_change: bool = False
    save_to_context: bool = False
    origin: str = "researcher_reported"
    context_expected_revision: int | None = Field(default=None, ge=1)


class AssessmentMessage(BaseModel):
    instructions: str = Field(min_length=1)
    researcher_note_draft: str | None = None
    idempotency_key: str | None = None
    retry_run_id: str | None = None


class ReportSectionComment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: dict
    note: str
    expected_revision: int = Field(ge=0, strict=True)


class MethodSelection(BaseModel):
    method_id: str
    title: str | None = None
    expected_identity: dict | None = None


class CorrectRun(BaseModel):
    note: str = ""


class MemoryAppend(BaseModel):
    text: str


def make_bridge() -> CodexBridge:
    if os.environ.get("MF_CODEX_FAKE_BRIDGE"):
        from .bridge import FakeCodexBridge

        return FakeCodexBridge()
    # Members configured for the ADR-008 shim carry provider_env_key
    # "SHIM_DUMMY" (the shim holds the real keys host-side). The live
    # scripts set it; a bare service process must not crash without it
    # (found 2026-09-08: UI-started run died on theorist turn).
    os.environ.setdefault("SHIM_DUMMY", "x")
    return SdkCodexBridge()


def _researcher_store(project_dir: Path) -> Path:
    d = project_dir / "researcher"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _attention_resolutions(project_dir: Path) -> dict:
    f = _researcher_store(project_dir) / "attention_resolutions.json"
    if f.is_file():
        try:
            value = json.loads(f.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}
    return {}


def _open_attention_items(project_dir: Path) -> list[dict]:
    """Open attention items across all branches/phases, minus researcher-resolved
    (D15: resolution is a human act, recorded in the researcher store — never a
    write into sealed member records)."""
    from .cumulative_attention import open_attention_items

    return open_attention_items(project_dir, _attention_resolutions(project_dir))


def create_app(data_root: Path | None = None, bridge: CodexBridge | None = None,
               account_service: AccountService | None = None, frontend_dir: Path | None = None) -> FastAPI:
    root = (data_root or default_data_root()).resolve()
    accounts = account_service or AccountService(root)
    engine = RunEngine(root, bridge or make_bridge(), account_service=accounts)

    from contextlib import asynccontextmanager, ExitStack
    from .instance_lock import writable_instance

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Boot reconciliation runs at SERVE time, not import time — importing
        # this module (tests, tooling) must not mutate the real data root.
        # Skip entirely when MF_CODEX_READ_ONLY=1: a viewer service sharing a
        # data root with a live driver must not mark the driver's in-flight
        # runs as interrupted (learned the hard way, 2026-09-07).
        read_only = os.environ.get("MF_CODEX_READ_ONLY") == "1"
        with ExitStack() as lifetime:
            try:
                if not read_only:
                    lifetime.enter_context(writable_instance(root))
                app.state.reconciled_runs = [] if read_only else engine.reconcile_on_boot()
                yield
            finally:
                try:
                    try:
                        await engine.shutdown()
                    finally:
                        await accounts.close()
                finally:
                    cleanup = app.state.after_service_cleanup
                    if cleanup is not None:
                        cleanup()

    app = FastAPI(title="Model Forge (Codex edition)", lifespan=lifespan)
    app.state.engine = engine
    app.state.accounts = accounts
    app.state.reconciled_runs = []
    # Local launcher metadata is removed after clients close and before the
    # writer lock is released, so a restarting process cannot lose its marker.
    app.state.after_service_cleanup = None
    app.state.frontend_dir = Path(frontend_dir).resolve() if frontend_dir is not None else None

    @app.exception_handler(RunError)
    async def run_error(_request: Request, exc: RunError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ArtifactError)
    async def artifact_error(_request: Request, exc: ArtifactError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(P4ExecutionError)
    async def p4_execution_error(_request: Request, exc: P4ExecutionError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(AccountError)
    async def account_error(_request: Request, exc: AccountError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.middleware("http")
    async def read_only_mode(request: Request, call_next):
        if os.environ.get("MF_CODEX_READ_ONLY") == "1" and request.method not in ("GET", "HEAD", "OPTIONS"):
            return JSONResponse(status_code=403, content={"detail": "This viewer is read-only."})
        return await call_next(request)

    async def require_same_origin_json(request: Request, noun: str) -> None:
        # Cross-site pages must not read secrets or trigger mutations. The
        # local UI uses JSON and the same origin (also preserved by the dev
        # proxy); the content-type requirement forces a CORS preflight that
        # cross-origin readers cannot pass.
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(415, f"{noun} require application/json.")
        origin = request.headers.get("origin")
        if origin is not None and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            raise HTTPException(403, f"{noun} must come from this workspace origin.")

    async def account_mutation(request: Request) -> None:
        # Cross-site forms cannot initiate login or copy credentials.
        await require_same_origin_json(request, "Account actions")
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "Account actions require a JSON object.") from None
        if not isinstance(body, dict):
            raise HTTPException(400, "Account actions require a JSON object.")

    @app.get("/api/v1/account")
    async def account_status() -> dict:
        return await accounts.status()

    @app.post("/api/v1/account/login")
    async def account_login(request: Request) -> dict:
        await account_mutation(request)
        return await accounts.start_login()

    @app.delete("/api/v1/account/login")
    async def account_cancel(request: Request) -> dict:
        await account_mutation(request)
        return await accounts.cancel_login()

    @app.post("/api/v1/account/connect")
    async def account_connect(request: Request) -> dict:
        await account_mutation(request)
        return await accounts.connect()

    def sync_catalog(project_dir: Path) -> None:
        """Pin-sync the universal catalog into a new project (ADR-007)."""
        import shutil

        repo_catalog = Path(__file__).resolve().parents[2] / "contracts"
        target = project_dir / "contracts"
        if repo_catalog.is_dir() and not target.exists():
            shutil.copytree(repo_catalog, target)

    # -------------------------------------------------------------- #
    # Projects
    # -------------------------------------------------------------- #

    @app.post("/api/v1/projects")
    async def create_project(body: CreateProject) -> dict:
        from .domain import new_id

        import re
        slug = re.sub(r"[^a-z0-9._-]+", "_", body.name.strip().lower()).strip("._-") or "research"
        project_id = new_id(f"project.{slug}")
        project_dir = engine.project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(
            project_dir / "project.json",
            normalize_project({
                "project_id": project_id,
                "name": body.name,
                "research_question": body.research_question,
                "research_instructions": body.research_instructions,
                "venue_length": body.venue_length,
            }),
        )
        sync_catalog(project_dir)
        if supports_problem_context(project_dir):
            initialize_problem_context(project_dir)
        provision_team(project_dir)
        accounts.provision_project(project_dir)
        return {"project_id": project_id}

    @app.get("/api/v1/projects")
    async def list_projects() -> dict:
        projects = []
        root_dir = root / "projects"
        if root_dir.is_dir():
            for child in sorted(root_dir.iterdir()):
                doc = read_json(child / "project.json")
                if doc:
                    projects.append(normalize_project(doc))
        return {"projects": projects}

    @app.get("/api/v1/projects/{project_id}")
    async def get_project(project_id: str) -> dict:
        doc = read_json(engine.project_dir(project_id) / "project.json")
        if doc is None:
            raise HTTPException(404, "unknown project")
        members = {}
        provider_config = load_provider_config(root)
        members_dir = engine.project_dir(project_id) / "members"
        if members_dir.is_dir():
            for role_dir in sorted(members_dir.iterdir()):
                config = read_json(role_dir / "config.json")
                if config:
                    config["openai_auth_present"] = (role_dir / "codex-home" / "auth.json").is_file()
                    members[role_dir.name] = provider_config.effective_member(config, role_dir.name, role_dir / "codex-home")
        from .migration import preview_catalog_upgrade
        dialogue = supports_problem_context(engine.project_dir(project_id))
        from .problem_context import project_context_target
        from .technical_reports import technical_report_enabled
        from .catalog import Catalog
        return {"project": normalize_project(doc), "members": members,
                "problem_context": {**load_problem_context(engine.project_dir(project_id)),
                    "dialogue_target": project_context_target(engine.project_dir(project_id))} if dialogue else None,
                "workflow_capabilities": {"researcher_dialogue": dialogue,
                    "technical_report": technical_report_enabled(Catalog(engine.project_dir(project_id) / "contracts"))},
                "provider_config": provider_config.status(),
                "catalog": preview_catalog_upgrade(engine.project_dir(project_id), Path(__file__).resolve().parents[2] / "contracts")}

    @app.patch("/api/v1/projects/{project_id}")
    async def update_project(project_id: str, body: UpdateProject) -> dict:
        path = engine.project_dir(project_id) / "project.json"
        doc = read_json(path)
        if doc is None:
            raise HTTPException(404, "unknown project")
        changes = body.model_dump(exclude_unset=True)
        amendment = changes.pop("setting_amendment", None)
        setting_targets = changes.pop("setting_amends", None)
        updated = {**normalize_project(doc), **changes}
        revised = supports_problem_context(engine.project_dir(project_id))
        if amendment is not None and revised:
            context = load_problem_context(engine.project_dir(project_id))
            if not setting_targets:
                raise HTTPException(422, "Choose the context item or exact brief excerpt this setting correction replaces, or edit the saved understanding directly.")
            save_context_item(engine.project_dir(project_id), amendment,
                              expected_revision=context["revision"], origin="researcher_reported", amends=setting_targets)
            amendment = None
        if amendment is not None:
            amendments = list(updated.get("setting_amendments") or [])
            if not amendments or amendments[-1].get("text") != amendment:
                amendments.append({"text": amendment, "created_at": datetime.now(timezone.utc).isoformat()})
                updated["research_instructions"] = (updated.get("research_instructions", "").rstrip()
                    + "\n\n## Researcher amendment to the setting\n\n" + amendment)
            updated["setting_amendments"] = amendments
        write_json_atomic(path, updated)
        if revised and "research_instructions" in changes:
            refresh_problem_context_brief(engine.project_dir(project_id))
        return {"project": updated}

    @app.get("/api/v1/projects/{project_id}/problem-context")
    async def problem_context(project_id: str) -> dict:
        try:
            from .problem_context import project_context_target
            return {**load_problem_context(engine.project_dir(project_id)),
                    "dialogue_target": project_context_target(engine.project_dir(project_id))}
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.put("/api/v1/projects/{project_id}/problem-context")
    async def edit_problem_context(project_id: str, body: ContextEdit) -> dict:
        if not supports_problem_context(engine.project_dir(project_id)):
            raise HTTPException(409, "Adopt the model-development workflow before saving shared context.")
        try:
            return save_context_item(engine.project_dir(project_id), **body.model_dump())
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/v1/projects/{project_id}/problem-context/proposals/{proposal_id}/confirm")
    async def confirm_context(project_id: str, proposal_id: str, body: ContextConfirmation) -> dict:
        try:
            return confirm_context_amendment(engine.project_dir(project_id), proposal_id, **body.model_dump())
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/v1/projects/{project_id}/phase2-preparation")
    async def get_phase_two_preparation(project_id: str) -> dict:
        project_dir = engine.project_dir(project_id)
        if not (project_dir / "project.json").is_file():
            raise HTTPException(404, "unknown project")
        from .phase_interactions import load_preparation
        return load_preparation(project_dir, "trunk", "P2")

    @app.put("/api/v1/projects/{project_id}/phase2-preparation")
    async def save_phase_two_preparation(project_id: str, body: PhaseTwoPreparation) -> dict:
        project_dir = engine.project_dir(project_id)
        if not (project_dir / "project.json").is_file():
            raise HTTPException(404, "unknown project")
        from .phase_interactions import preparation_path, save_preparation
        path = preparation_path(project_dir, "trunk", "P2")
        if body.input_ids is not None:
            raise HTTPException(400, "Local analysis inputs belong to Phase 4 preparation")
        return save_preparation(path, body.instructions)

    @app.get("/api/v1/projects/{project_id}/inputs")
    async def researcher_inputs(project_id: str):
        from .researcher_inputs import list_inputs
        try:
            return {"inputs": list_inputs(engine.project_dir(project_id))}
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/v1/projects/{project_id}/inputs")
    async def import_researcher_input(project_id: str, body: ImportResearcherInput):
        from .researcher_inputs import import_input
        try:
            return import_input(engine.project_dir(project_id), **body.model_dump())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/v1/projects/{project_id}/catalog-upgrade")
    async def adopt_catalog(project_id: str) -> dict:
        from .migration import upgrade_catalog
        if not (engine.project_dir(project_id) / "project.json").is_file():
            raise HTTPException(404, "unknown project")
        try:
            return upgrade_catalog(engine.project_dir(project_id), Path(__file__).resolve().parents[2] / "contracts")
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/v1/projects/{project_id}/branches/{branch}/phases/{phase}/preparation")
    async def get_phase_preparation(project_id: str, branch: str, phase: str) -> dict:
        from .phase_interactions import load_preparation
        try:
            return load_preparation(engine.project_dir(project_id), branch, phase)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.put("/api/v1/projects/{project_id}/branches/{branch}/phases/{phase}/preparation")
    async def save_phase_preparation(project_id: str, branch: str, phase: str, body: PhaseTwoPreparation) -> dict:
        from .phase_interactions import preparation_path, save_preparation
        try:
            path = preparation_path(engine.project_dir(project_id), branch, phase)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        if body.input_ids is not None:
            if phase != "P4":
                raise HTTPException(400, "Local analysis inputs belong to Phase 4 preparation")
            from .researcher_inputs import selected_inputs
            try:
                selected_inputs(engine.project_dir(project_id), body.input_ids)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        return save_preparation(path, body.instructions, input_ids=body.input_ids)

    @app.get("/api/v1/projects/{project_id}/methods")
    async def methods(project_id: str) -> dict:
        from .methods import catalog_diagnostics, list_methods
        return {"methods": list_methods(engine.project_dir(project_id)),
                "diagnostics": catalog_diagnostics(engine.project_dir(project_id))}

    @app.post("/api/v1/projects/{project_id}/methods")
    @app.post("/api/v1/projects/{project_id}/methods/activate")
    async def select_method(project_id: str, body: MethodSelection) -> dict:
        from .methods import activate_method
        try:
            return activate_method(engine.project_dir(project_id), body.method_id, body.expected_identity)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    # -------------------------------------------------------------- #
    # Team
    # -------------------------------------------------------------- #

    @app.put("/api/v1/projects/{project_id}/members/{role}")
    async def update_member(project_id: str, role: str, body: MemberUpdate) -> dict:
        try:
            member_role = MemberRole(role)
        except ValueError:
            raise HTTPException(404, f"unknown role {role}")
        # Overlay onto the stored config — partial updates must not wipe
        # the soul or provider settings.
        stored = read_json(
            engine.project_dir(project_id) / "members" / role / "config.json"
        ) or {}
        update = {k: v for k, v in body.model_dump().items() if v is not None}
        provider_config = load_provider_config(root)
        member_home = engine.project_dir(project_id) / "members" / role / "codex-home"
        effective = provider_config.effective_member(stored, role, member_home)
        controlled = set(update) & CONTROLLED_FIELDS
        if provider_config.error and controlled:
            raise HTTPException(409, "Fix the provider configuration file before editing provider settings.")
        if provider_config.governs(role):
            if any(update[key] != effective.get(key) for key in controlled):
                raise HTTPException(409, "This member's provider, model and reasoning settings are controlled by the shared provider configuration file. Edit that file directly or use Edit provider file in Team Settings.")
            update = {key: value for key, value in update.items() if key not in CONTROLLED_FIELDS}
        merged = {**stored, **update}
        config = MemberConfig(
            role=member_role,
            model=merged.get("model", "gpt-6.1-sol"),
            reasoning_effort=merged.get("reasoning_effort", "xhigh"),
            soul=merged.get("soul", ""),
            provider=merged.get("provider", "openai"),
            provider_base_url=merged.get("provider_base_url", ""),
            provider_env_key=merged.get("provider_env_key", ""),
            provider_id=merged.get("provider_id", ""),
            auto_compact_tokens=int(merged.get("auto_compact_tokens") or 0),
            max_turn_input_tokens=int(merged.get("max_turn_input_tokens") or 0),
        )
        try:
            record = provision_member(engine.project_dir(project_id), config)
            accounts.provision_project(engine.project_dir(project_id))
            record["openai_auth_present"] = (engine.project_dir(project_id) / "members" / role / "codex-home" / "auth.json").is_file()
            return provider_config.effective_member(record, role, member_home)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @app.get("/api/v1/provider-options")
    async def provider_options() -> dict:
        """OpenAI-account model choices and required manual provider fields."""
        from .members import OPENAI_MODELS
        from openai_codex.generated.v2_all import ReasoningEffort

        return {
            "openai_models": list(OPENAI_MODELS),
            "reasoning_efforts": [effort.value for effort in ReasoningEffort],
            "modes": ["openai", "custom"],
            "custom_requires": ["provider_id", "provider_base_url", "provider_env_key", "model"],
            "provider_config": load_provider_config(root).status(),
        }

    @app.get("/api/v1/provider-config/editor")
    async def provider_config_editor(request: Request) -> dict:
        """Editable view of the shared provider file. Unlike every other
        endpoint this one returns stored api_key values (deliberate, single-
        user localhost tool), so it sits behind the same-origin JSON guard."""
        await require_same_origin_json(request, "Provider configuration")
        return editor_view(root)

    @app.put("/api/v1/provider-config")
    async def save_provider_config(request: Request) -> dict:
        """Validate and atomically rewrite the shared provider file. The file
        stays the single source of truth; the freshness token is checked
        against the file's bytes inside the guarded write, so a hand edit made
        after the editor loaded conflicts instead of being overwritten."""
        await require_same_origin_json(request, "Provider configuration")
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "Provider configuration saves require a JSON object.") from None
        if not isinstance(body, dict):
            raise HTTPException(400, "Provider configuration saves require a JSON object.")
        token, document = body.get("token"), body.get("document")
        if not isinstance(token, str) or not token:
            raise HTTPException(400, "Provider configuration saves require the freshness token from the editor view.")
        if not isinstance(document, dict):
            raise HTTPException(400, "Provider configuration saves require a document object.")
        path = load_provider_config(root).path
        try:
            new_token = write_provider_config(path, document, expected_token=token)
        except ProviderConfigConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except ProviderConfigError as exc:
            raise HTTPException(400, str(exc)) from exc
        except OSError:
            raise HTTPException(500, "The provider file could not be written. Check the file and its permissions.") from None
        refreshed = load_provider_config(root)
        return {"ok": True, "token": new_token, "provider_config": refreshed.status()}

    @app.post("/api/v1/projects/{project_id}/members/{role}/provider-probe")
    async def probe_provider(project_id: str, role: str, request: Request) -> dict:
        """Test one member's effective provider settings with one bounded live
        exchange (connection, model response, tool round trip, final response).
        With a document body the unsaved editor draft is tested exactly as it
        would behave after saving; nothing is written either way."""
        await require_same_origin_json(request, "Provider connection tests")
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "Provider connection tests require a JSON object.") from None
        if not isinstance(body, dict):
            raise HTTPException(400, "Provider connection tests require a JSON object.")
        document = body.get("document")
        if document is not None and not isinstance(document, dict):
            raise HTTPException(400, "Provider connection tests require a document object when one is given.")
        try:
            return await run_provider_probe(root, engine, project_id=project_id, role=role, draft_document=document)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    # -------------------------------------------------------------- #
    # Runs
    # -------------------------------------------------------------- #

    @app.post("/api/v1/projects/{project_id}/runs")
    async def start_run(project_id: str, body: StartRun) -> dict:
        try:
            record = await engine.start_run(
                project_id,
                phase=body.phase,
                mode=body.mode,
                branch_id=body.branch_id,
                basis_sha256=body.basis_sha256,
                instructions=body.instructions,
                idempotency_key=body.idempotency_key,
                intent=body.intent,
                target=body.target,
                assessment_id=body.assessment_id,
                assessment_purpose=body.assessment_purpose,
                researcher_note_draft=body.researcher_note_draft,
                retry_run_id=body.retry_run_id,
                supplied_method=body.supplied_method.model_dump() if body.supplied_method else None,
                budget_seconds=body.budget_seconds,
                context_refs=body.context_refs,
                input_ids=body.input_ids,
            )
        except RunError as exc:
            raise HTTPException(409, str(exc))
        return {"run_id": record.run_id, "state": record.state.value, "assessment_id": record.assessment_id}

    @app.get("/api/v1/projects/{project_id}/assessments")
    async def assessments(project_id: str, branch: str | None = None) -> dict:
        return {"assessments": engine.list_assessments(project_id, branch=branch)}

    @app.get("/api/v1/projects/{project_id}/report-section-comment")
    async def report_section_comment(project_id: str, target: str) -> dict:
        from .report_sections import load_section_comment
        try:
            return {"comment": load_section_comment(engine.project_dir(project_id), json.loads(target))}
        except (ValueError, TypeError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.put("/api/v1/projects/{project_id}/report-section-comment")
    async def save_report_section_comment(project_id: str, body: ReportSectionComment) -> dict:
        from .report_sections import save_section_comment
        try:
            return {"comment": save_section_comment(engine.project_dir(project_id), body.target, body.note, body.expected_revision)}
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/v1/projects/{project_id}/assessments/{assessment_id}/messages")
    async def assessment_message(project_id: str, assessment_id: str, body: AssessmentMessage) -> dict:
        existing = await assessments(project_id)
        item = next((value for value in existing["assessments"] if value["assessment_id"] == assessment_id), None)
        if item is None:
            raise HTTPException(404, "unknown assessment")
        target = item["target"]
        record = await engine.start_run(project_id, phase=target.get("phase", "P3"), mode="p3.assessment",
                                        branch_id=target.get("branch", target.get("branch_id", "trunk")),
                                        instructions=body.instructions, idempotency_key=body.idempotency_key,
                                        intent="assessment", assessment_id=assessment_id,
                                        assessment_purpose=item.get("assessment_purpose", "assessment"),
                                        researcher_note_draft=body.researcher_note_draft,
                                        retry_run_id=body.retry_run_id)
        return {"run_id": record.run_id, "state": record.state.value, "assessment_id": record.assessment_id}

    @app.get("/api/v1/projects/{project_id}/runs/{run_id}")
    async def get_run(project_id: str, run_id: str) -> dict:
        try:
            record = engine.load_run(project_id, run_id)
        except RunError:
            raise HTTPException(404, "unknown run")
        events, skipped = engine.run_events(project_id, run_id)
        from dataclasses import asdict

        doc = asdict(record)
        doc["state"] = record.state.value
        doc["events"] = events[-50:]
        doc["events_skipped_bad_lines"] = skipped
        doc["p4_progress"] = engine.p4_progress(record)
        doc["researcher_pause"] = engine.researcher_pause(record)
        doc["provider_retry"] = engine.provider_retry_preview(record)
        from .run_progress import project_run_progress
        doc["progress"] = project_run_progress(engine.run_dir(project_id, run_id), doc)
        return doc

    @app.post("/api/v1/projects/{project_id}/runs/{run_id}/pause")
    async def pause_evaluation(project_id: str, run_id: str) -> dict:
        record = await engine.pause_p4(project_id, run_id)
        return {"run_id": record.run_id, "state": record.state.value}

    @app.post("/api/v1/projects/{project_id}/runs/{run_id}/continue")
    async def continue_evaluation(project_id: str, run_id: str, body: ContinueEvaluation) -> dict:
        current = engine.load_run(project_id, run_id)
        handler = engine.continue_p4 if engine._progressive_p4(current) else engine.continue_researcher_work
        record = await handler(project_id, run_id, **body.model_dump())
        return {"run_id": record.run_id, "state": record.state.value}

    @app.put("/api/v1/projects/{project_id}/runs/{run_id}/decision-answer")
    async def save_evaluation_answer(project_id: str, run_id: str, body: SavedDecisionAnswer) -> dict:
        current = engine.load_run(project_id, run_id)
        fields = body.model_dump()
        if engine._progressive_p4(current):
            return await engine.save_p4_answer(project_id, run_id, **fields)
        return await engine.save_researcher_answer(project_id, run_id, **fields)

    @app.post("/api/v1/projects/{project_id}/runs/{run_id}/retry-provider")
    async def retry_provider_run(project_id: str, run_id: str) -> dict:
        try:
            record = await engine.retry_provider(project_id, run_id)
        except (RunError, ArtifactError, ValueError) as exc:
            raise HTTPException(409, str(exc))
        return {"run_id": record.run_id, "state": record.state.value}

    @app.post("/api/v1/projects/{project_id}/runs/{run_id}/corrections")
    async def correct_run(project_id: str, run_id: str, body: CorrectRun) -> dict:
        try:
            record = await engine.correct(project_id, run_id, body.note)
        except RunError as exc:
            raise HTTPException(409, str(exc))
        return {"run_id": record.run_id, "state": record.state.value}

    @app.post("/api/v1/projects/{project_id}/runs/{run_id}/cancel")
    async def cancel_run(project_id: str, run_id: str) -> dict:
        try:
            record = await engine.cancel(project_id, run_id)
        except RunError as exc:
            raise HTTPException(409, str(exc))
        return {"run_id": record.run_id, "state": record.state.value}

    # -------------------------------------------------------------- #
    # Phase C: browse, memory, correction preview, activity stream
    # -------------------------------------------------------------- #
    @app.get("/api/v1/projects/{project_id}/branches")
    async def branches(project_id: str) -> dict:
        from . import browse

        return {"branches": browse.list_branches(engine.project_dir(project_id))}

    @app.get("/api/v1/projects/{project_id}/branches/{branch_id}/phases/{phase}/readiness")
    async def readiness(project_id: str, branch_id: str, phase: str, mode: str | None = None) -> dict:
        """Gate state + the current basis digest. The UI stamps this digest
        onto the Run command (design/07 §2): if anything publishes in
        between, the service refuses with a stale-basis re-open message."""
        from .domain import PHASES
        if phase not in PHASES:
            raise HTTPException(400, "unknown phase")
        contract = read_json(
            engine.project_dir(project_id) / "contracts" / "contracts" / "phases" / f"{phase}.json"
        ) or {}
        declared = contract.get("run_modes") or [{"mode_id": value} for value in sorted({
            value for stage in contract.get("role_stages", []) for value in stage.get("applicable_modes", [])})]
        modes = []
        if phase == "P3" and not any(item.get("mode_id") == "p3.assessment" for item in declared):
            declared = [*declared, {"mode_id": "p3.assessment", "label": "Take another look", "purpose": "Assess the selected component and possible next steps without modifying it."}]
        labels = {"p4.preliminary": "Feasibility check", "p4.comprehensive": "Detailed evaluation"}
        progressive = phase == "P4" and "progressive_evaluation_v1" in contract.get("capabilities", [])
        from .p4_lifecycle import default_experiment_budget
        for item in declared:
            value = item["mode_id"]
            reasons = engine.check_readiness(project_id, phase, branch_id, value)
            basis = engine.compute_basis(project_id, phase, branch_id, value)
            modes.append({"mode": value, "mode_id": value, "label": labels.get(value, item.get("label", value)),
                          "purpose": item.get("purpose", ""), "ready": not reasons, "reasons": reasons, "basis": basis,
                          **({"progressive_evaluation": True, "budget_seconds": default_experiment_budget(),
                              "local_inputs": "p4.workflow_templates.v1" in contract.get("capabilities", [])} if progressive else {})})
        selected = next((item for item in modes if item["mode"] == mode), None) if mode else next(iter(modes), None)
        if mode and selected is None:
            raise HTTPException(400, "unknown mode")
        return {"ready": selected["ready"] if selected else False,
                "reasons": selected["reasons"] if selected else ["No applicable run modes"],
                "basis": selected["basis"] if selected else {}, "modes": modes}

    @app.get("/api/v1/projects/{project_id}/runs")
    async def list_runs(project_id: str) -> dict:
        from . import browse

        return {"runs": browse.list_runs(engine.project_dir(project_id))}

    @app.get("/api/v1/projects/{project_id}/branches/{branch_id}/phases/{phase}/records")
    async def records(project_id: str, branch_id: str, phase: str) -> dict:
        from . import browse

        try:
            return {
                "records": browse.list_records(engine.project_dir(project_id), branch_id, phase)
            }
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @app.get(
        "/api/v1/projects/{project_id}/branches/{branch_id}/phases/{phase}"
        "/records/{family}/{generation_id}"
    )
    async def record_body(
        project_id: str, branch_id: str, phase: str, family: str, generation_id: str,
        view: str | None = None, download: bool = False,
    ):
        from . import browse

        try:
            if view == "portable":
                if family not in ("technical_report", "technical_report_candidate"):
                    raise HTTPException(400, "Only a technical report has a portable report view")
                from .technical_reports import export_technical_report, completed_report_review_packets
                from .records import generation_path, committed_packages
                from .storage import sha256_file
                doc = browse.get_record(engine.project_dir(project_id), branch_id, phase, family, generation_id)
                if not doc:
                    raise HTTPException(404, "unknown record generation")
                phase_dir = engine.project_dir(project_id) / "branches" / branch_id / "phases" / phase.lower()
                meta = next((package["records"][family] for package in committed_packages(phase_dir)
                             if package.get("records", {}).get(family, {}).get("generation_id") == generation_id), {})
                if not meta:
                    raise HTTPException(409, "Only a committed report generation can be exported")
                source = generation_path(phase_dir, family, meta)
                run_id = meta.get("run_id")
                if not run_id:
                    raise HTTPException(409, "This report's retained run source is unavailable")
                run_dir = engine.run_dir(project_id, run_id)
                basis = read_json(run_dir / "basis.json") or {}
                review_packets = completed_report_review_packets(engine.project_dir(project_id))
                payload = export_technical_report(doc, basis,
                    generation_ref={"phase": phase, "branch": branch_id, "family": family,
                        "generation_id": generation_id, "content_sha256": sha256_file(source)},
                    artifact_roots={family: run_dir / "outputs" / str(meta.get("stage_id", "p5.assembly"))},
                    exported_at=datetime.now(timezone.utc).isoformat(), review_packets=review_packets)
                return Response(payload, media_type="text/html", headers={
                    "Content-Disposition": ('attachment' if download else 'inline') + '; filename="technical-report.html"',
                    "X-Content-Type-Options": "nosniff",
                    "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; base-uri 'none'; form-action 'none'"})
            elif view == "document":
                from .research import scientific_document_view
                doc = scientific_document_view(engine.project_dir(project_id), branch_id, phase, family, generation_id)
            elif view is None:
                doc = browse.get_record(
                    engine.project_dir(project_id), branch_id, phase, family, generation_id
                )
            else:
                raise HTTPException(400, "unknown record view")
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        if doc is None:
            raise HTTPException(404, "unknown record generation")
        return doc

    @app.get("/api/v1/projects/{project_id}/artifacts")
    async def artifacts(project_id: str, branch: str | None = None) -> dict:
        """One exact, source-linked research view per requested branch."""
        from .browse import _check_ident
        if branch is not None:
            try:
                _check_ident(branch)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        return artifacts_view(engine.project_dir(project_id), branch)

    @app.get("/api/v1/projects/{project_id}/decisions-pending")
    async def decisions_pending(project_id: str) -> dict:
        """The global 'needs your decision' aggregate (design/14 §3): open
        attention items, failed runs with correction budget left, and phases
        published whose next phase hasn't started (your call)."""
        from . import browse
        from .cumulative_attention import current_researcher_answers
        from .phase_interactions import answers_with_usage

        project_dir = engine.project_dir(project_id)
        attention = _open_attention_items(project_dir)
        runs = browse.list_runs(project_dir)
        needs_correction = []
        for run in runs:
            details = read_json(engine.run_dir(project_id, run["run_id"]) / "run.json") or {}
            if (details.get("assessment_purpose") not in ("explanation", "issue_explanation", "issue_suggestions", "project_context", "model_dialogue") and run["state"] == "failed"
                    and run.get("correction_attempts", 0) < 1 and details.get("findings_history")):
                needs_correction.append(run)
        calls: list[dict] = []
        for decision in artifacts_view(project_dir)["decisions"]:
            for action in decision.get("available_actions", []):
                if isinstance(action, dict):
                    calls.append({**action, "branch": decision["branch"], "phase": decision["phase"],
                                  "next_phase": action.get("phase", action.get("target_phase", decision["phase"])),
                                  "generation_ref": decision["generation_ref"]})
        return {
            "attention": attention,
            "researcher_answers": answers_with_usage(project_dir),
            "runs_needing_correction": needs_correction,
            "runs_awaiting_direction": [{**run, "p4_progress": engine.p4_progress(engine.load_run(project_id, run["run_id"])),
                "researcher_pause": engine.researcher_pause(engine.load_run(project_id, run["run_id"]))}
                                       for run in runs if run["state"] == "awaiting_user"],
            "your_call": calls,
        }

    @app.post("/api/v1/projects/{project_id}/attention/{attention_id}/resolve")
    async def resolve_attention(project_id: str, attention_id: str, body: dict | None = None) -> dict:
        """Save or edit an answer without changing the original research request."""
        project_dir = engine.project_dir(project_id)
        from .phase_interactions import answers_with_usage
        def response(answer):
            projected = next((item for item in answers_with_usage(project_dir)
                              if item["attention_id"] == attention_id and item.get("revision") == answer.get("revision")), None)
            return {"resolved": attention_id, "answer": projected or {
                **{key: value for key, value in answer.items() if key != "history"}, "attention_id": attention_id,
                "applied_to": [], "previously_applied_to": []}}
        res = _attention_resolutions(project_dir)
        previous = res.get(attention_id)
        previous = previous if isinstance(previous, dict) else {}
        # An answered request leaves the open inbox, but its original question
        # and source remain attached to the editable researcher answer.
        question = next((item for item in _open_attention_items(project_dir) if item.get("attention_id") == attention_id), None)
        if question is None:
            question = previous.get("attention")
        expected_source = (body or {}).get("expected_source")
        selection = (body or {}).get("selection")
        if selection is not None and not isinstance(expected_source, dict):
            raise HTTPException(409, "Reopen the exact question before saving a selected choice.")
        if isinstance(expected_source, dict) and expected_source.get("kind") == "project_context":
            if "goal_source_ref" in expected_source:
                raise HTTPException(409, "Save a research goal correction through the project context editor.")
            from .problem_context import resolve_project_context_target
            try:
                question = resolve_project_context_target(project_dir, expected_source)
                question["attention_id"] = attention_id
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
        if question is None:
            from .phase_interactions import published_issues
            question = next((item for item in published_issues(project_dir) if item["issue_id"] == attention_id), None)
        if question is None:
            raise HTTPException(status_code=404, detail="This research request is unavailable or has no saved question context.")
        if expected_source is not None:
            from .phase_interactions import exact_saved_answer, issue_source_identity
            expected_identity = issue_source_identity({"explanation_target": expected_source}) if isinstance(expected_source, dict) else None
            if expected_identity is not None and expected_identity != issue_source_identity(question):
                from .phase_interactions import published_issues
                published = next((item for item in published_issues(project_dir)
                                  if item["issue_id"] == attention_id and issue_source_identity(item) == expected_identity), None)
                if published is not None:
                    # An authored carry-forward can hide the current question
                    # from the open inbox before it has its own saved answer.
                    question = published
                else:
                    saved = exact_saved_answer(project_dir, {"explanation_target": expected_source})
                    if saved is not None and saved.get("attention_id") == attention_id:
                        # A successor does not prevent editing its saved original.
                        # Unsaved stale sources still fail below.
                        question = saved["attention"]
            if expected_identity is None or expected_identity != issue_source_identity(question):
                raise HTTPException(409, "This question's source version changed; reopen the original question before saving your response.")
        if question.get("kind") == "research_task":
            raise HTTPException(status_code=409, detail="Team research tasks need a recorded research disposition from the responsible phase.")
        note = (body or {}).get("note", "")
        if not isinstance(note, str):
            raise HTTPException(422, "Your response must be text.")
        expected = (body or {}).get("expected_revision")
        if supports_problem_context(project_dir):
            if not note.strip() and selection is None:
                raise HTTPException(422, "Record your response before saving.")
            try:
                answer = save_scoped_answer(project_dir, question, note, expected_revision=expected,
                    save_to_context=bool((body or {}).get("save_to_context", False)),
                    origin=(body or {}).get("origin", "researcher_reported"),
                    context_item_id=(body or {}).get("context_item_id"),
                    context_expected_revision=(body or {}).get("context_expected_revision"),
                    amends=(body or {}).get("amends"), conflicts_with=(body or {}).get("conflicts_with"),
                    selection=selection)
                return response(answer)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
        if expected is not None and expected != previous.get("revision", 0):
            raise HTTPException(409, "Your saved response changed; reload it before saving this edit.")
        selected = None
        origin = (body or {}).get("origin", "researcher_reported")
        if origin not in ("researcher_reported", "unknown"):
            raise HTTPException(409, "A direct researcher response records a report or uncertainty.")
        if selection is not None:
            from .phase_interactions import selected_response
            try:
                note, selected = selected_response(question, selection, origin=origin)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
        if question.get("kind") in ("researcher_decision", "scientific_issue") and (not isinstance(note, str) or not note.strip()):
            raise HTTPException(status_code=422, detail="Record your decision before submitting this clarification.")
        if (previous.get("note") == note and previous.get("selection") == selected
                and previous.get("origin", "researcher_reported") == origin):
            return response(previous)
        history = list(previous.get("history") or [])
        if previous:
            history.append({key: value for key, value in previous.items() if key != "history"})
        res[attention_id] = {
            "note": note,
            "origin": origin,
            "revision": previous.get("revision", 0) + 1,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "attention": {key: value for key, value in question.items() if key != "researcher_answer"},
            **({"selection": selected} if selected is not None else {}),
            **({"history": history} if history else {}),
        }
        write_json_atomic(_researcher_store(project_dir) / "attention_resolutions.json", res)
        return response(res[attention_id])

    @app.get("/api/v1/projects/{project_id}/runs/{run_id}/outputs/{stage_id}/artifact")
    async def exhibit_artifact(project_id: str, run_id: str, stage_id: str, path: str, sha256: str | None = None, download: bool = False):
        """Serve a sealed exhibit artifact (figure/table file) from the run
        folder, read-only. Path must stay inside the stage's output dir."""
        from fastapi.responses import FileResponse

        from .browse import _check_ident
        from .storage import sha256_file
        try:
            _check_ident(stage_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if ".." in Path(path).parts or Path(path).is_absolute():
            raise HTTPException(400, "invalid artifact path")
        base = (engine.run_dir(project_id, run_id) / "outputs" / stage_id).resolve()
        target = (base / path).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            raise HTTPException(404, "artifact not found")
        if sha256 and sha256_file(target) != sha256:
            raise HTTPException(409, "Artifact bytes no longer match the published source")
        return research_file_response(target, download=download)

    def research_file_response(target, *, download=False):
        from .research_sources import file_media
        media = file_media(target)
        headers = {"X-Content-Type-Options": "nosniff"}
        if media == "image/svg+xml":
            # Image embedding disables scripts, but original navigation does
            # not. Sandbox the response itself without an application origin.
            headers["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"
        return FileResponse(target, media_type=media, headers=headers, filename=target.name,
                            content_disposition_type="attachment" if download else "inline")

    @app.get("/api/v1/projects/{project_id}/branches/{branch}/phases/P4/records/{family}/{generation}/implementation-bundle")
    async def implementation_bundle(project_id: str, branch: str, family: str, generation: str):
        from .records import committed_packages
        from .browse import _check_ident
        from .implementation_export import export_implementation
        try:
            for value in (branch, family, generation):
                _check_ident(value)
            if family != "implementation_record":
                raise ValueError("Select a published implementation record")
            project = engine.project_dir(project_id)
            phase_dir = project / "branches" / branch / "phases" / "p4"
            meta = next((package["records"][family] for package in committed_packages(phase_dir)
                         if package.get("records", {}).get(family, {}).get("generation_id") == generation), None)
            if not meta:
                raise ArtifactError("This implementation generation is not published")
            document = read_generation(phase_dir, family, meta)
            content = export_implementation(project, meta, document)
        except (ArtifactError, ValueError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc
        return Response(content, media_type="application/zip", headers={
            "Content-Disposition": 'attachment; filename="model-and-example.zip"',
            "X-Content-Type-Options": "nosniff"})

    @app.get("/api/v1/projects/{project_id}/runs/{run_id}/review-packet/instructions")
    async def review_instructions(project_id: str, run_id: str, sha256: str):
        from .p5_review_packet import read_review_packet
        try:
            engine.load_run(project_id, run_id)
            packet = read_review_packet(engine.run_dir(project_id, run_id) / "review-packet")
        except (RunError, ArtifactError) as exc:
            raise HTTPException(404, str(exc)) from exc
        instruction = packet["instructions"]
        if instruction["content_sha256"] != sha256:
            raise HTTPException(409, "Review directions do not match the requested frozen source")
        return research_file_response(Path(instruction["path"]))

    @app.get("/api/v1/projects/{project_id}/runs/{run_id}/inputs/artifact")
    async def input_artifact(project_id: str, run_id: str, sha256: str, artifact_id: str = "", download: bool = False):
        from .research_sources import frozen_artifact
        run_dir = engine.run_dir(project_id, run_id)
        run = read_json(run_dir / "run.json") or {}
        if run.get("state") != "published":
            raise HTTPException(404, "published source run not found")
        try:
            target = frozen_artifact(engine.project_dir(project_id), run_id, sha256, artifact_id)
        except ArtifactError as error:
            raise HTTPException(404, str(error)) from error
        return research_file_response(target, download=download)

    @app.get("/api/v1/projects/{project_id}/runs/{run_id}/outputs/{stage_id}/table")
    async def exhibit_table(project_id: str, run_id: str, stage_id: str, path: str,
                            sha256: str, exhibit_id: str, offset: int = 0):
        from urllib.parse import quote, urlencode
        from .browse import _check_ident
        from .storage import sha256_file
        from .table_exhibits import table_preview, MAX_PREVIEW_ROWS
        try:
            _check_ident(stage_id)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        run_dir = engine.run_dir(project_id, run_id)
        if (read_json(run_dir / "run.json") or {}).get("state") != "published":
            raise HTTPException(404, "published table source not found")
        base = (run_dir / "outputs" / stage_id).resolve()
        target = (base / path).resolve()
        if Path(path).is_absolute() or ".." in Path(path).parts or not target.is_relative_to(base) or not target.is_file():
            raise HTTPException(404, "table source not found")
        manifest = read_json(base / "exhibits.json") or []
        entries = [item for item in manifest if isinstance(item, dict) and item.get("exhibit_id") == exhibit_id
                   and item.get("kind") == "table" and item.get("artifact_path") == path and item.get("artifact_sha256") == sha256]
        if len(entries) != 1:
            raise HTTPException(404, "exact table declaration not found")
        if sha256_file(target) != sha256:
            raise HTTPException(409, "Table bytes no longer match the published source")
        try:
            table = table_preview(target, entries[0], offset=offset)
        except (OSError, ValueError, UnicodeError) as error:
            raise HTTPException(400, str(error)) from error
        query = urlencode({"path": path, "sha256": sha256, "exhibit_id": exhibit_id})
        url = f"/api/v1/projects/{quote(project_id)}/runs/{quote(run_id)}/outputs/{quote(stage_id)}/table?{query}"
        if table["truncated"]:
            table["next_page_url"] = url + f"&offset={offset + MAX_PREVIEW_ROWS}"
        if offset:
            table["previous_page_url"] = url + f"&offset={max(0, offset - MAX_PREVIEW_ROWS)}"
        return table

    @app.get("/api/v1/projects/{project_id}/journal")
    async def authority_journal(project_id: str) -> dict:
        from . import browse

        return {"journal": browse.journal(engine.project_dir(project_id))}

    @app.get("/api/v1/projects/{project_id}/receipts")
    async def authority_receipts(project_id: str) -> dict:
        from . import browse

        return {"receipts": browse.receipts(engine.project_dir(project_id))}

    @app.get("/api/v1/projects/{project_id}/members/{role}/memory/{kind}")
    async def get_memory(project_id: str, role: str, kind: str) -> dict:
        from . import browse

        try:
            text = browse.member_memory(engine.project_dir(project_id), role, kind)
        except ValueError as exc:
            raise HTTPException(404, str(exc))
        return {"role": role, "kind": kind, "text": text}

    @app.post("/api/v1/projects/{project_id}/members/{role}/memory/{kind}")
    async def post_memory(project_id: str, role: str, kind: str, body: MemoryAppend) -> dict:
        from . import browse

        try:
            browse.append_member_memory(engine.project_dir(project_id), role, kind, body.text)
        except ValueError as exc:
            raise HTTPException(404, str(exc))
        return {"ok": True}

    @app.get("/api/v1/projects/{project_id}/runs/{run_id}/correction-preview")
    async def get_correction_preview(project_id: str, run_id: str) -> dict:
        from . import browse

        try:
            record = engine.load_run(project_id, run_id)
        except RunError:
            raise HTTPException(404, "unknown run")
        from dataclasses import asdict

        preview = browse.correction_preview(
            engine.project_dir(project_id),
            engine.run_dir(project_id, run_id),
            asdict(record),
        )
        reason = engine.correction_block_reason(record)
        preview.update(eligible=reason is None, reason=reason)
        return preview

    @app.get("/api/v1/projects/{project_id}/runs/{run_id}/activity")
    async def activity_stream(project_id: str, run_id: str):
        from starlette.responses import StreamingResponse

        from . import browse

        try:
            engine.load_run(project_id, run_id)
        except RunError:
            raise HTTPException(404, "unknown run")

        def state_reader() -> str:
            try:
                return engine.load_run(project_id, run_id).state.value
            except RunError:
                return "failed"

        return StreamingResponse(
            browse.stream_activity(engine.run_dir(project_id, run_id), state_reader,
                                  stop_requested=lambda: engine.shutting_down),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    if app.state.frontend_dir is not None:
        frontend = app.state.frontend_dir
        index = frontend / "index.html"
        assets = frontend / "assets"
        if not index.is_file() or not index.resolve().is_relative_to(frontend):
            raise ValueError("The frontend directory must contain a built index.html.")
        if assets.exists() and (not assets.is_dir() or not assets.resolve().is_relative_to(frontend)):
            raise ValueError("Frontend assets must stay inside the built frontend directory.")

        @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
        @app.api_route("/index.html", methods=["GET", "HEAD"], include_in_schema=False)
        async def frontend_index():
            return FileResponse(index, headers={"Cache-Control": "no-cache"})

        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    return app


app = create_app()
