"""Domain model (design/01). Types only — no I/O."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class MemberRole(StrEnum):
    RESEARCH_LEAD = "research_lead"
    THEORIST = "theorist"
    DATA_ANALYST = "data_analyst"
    OUTSIDE_REVIEWER = "outside_reviewer"


class RunState(StrEnum):
    REQUESTED = "requested"
    RUNNING = "running"
    VALIDATING = "validating"
    CORRECTING = "correcting"
    STOPPING = "stopping"
    AWAITING_USER = "awaiting_user"
    PUBLISHED = "published"
    ASSESSED = "assessed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = {RunState.PUBLISHED, RunState.ASSESSED, RunState.FAILED, RunState.CANCELLED}

TRUNK = "trunk"
PHASES = ("P1", "P2", "P3", "P4", "P5")
#: Phases whose work happens on the project trunk (no method branches yet).
TRUNK_PHASES = ("P1", "P2")
#: Which member drives each branch phase (ADR-002).
BRANCH_PHASE_MEMBER = {"P3": MemberRole.THEORIST, "P4": MemberRole.DATA_ANALYST}


def new_id(prefix: str) -> str:
    return f"{prefix}.{secrets.token_hex(16)}"


@dataclass(frozen=True, slots=True)
class ThreadKey:
    """Logical conversation identity (ADR-002)."""

    member: MemberRole
    phase: str
    branch_id: str = TRUNK

    def as_string(self) -> str:
        return f"{self.member}:{self.phase}:{self.branch_id}"


@dataclass(slots=True)
class MemberConfig:
    role: MemberRole
    model: str = "gpt-6.1-sol"
    reasoning_effort: str = "xhigh"
    soul: str = ""  # rendered into the member home's AGENTS.md (ADR-004)
    skill_pins: dict[str, list[dict]] = field(default_factory=dict)  # phase -> pins
    memory_policy: str = "enabled"
    # Provider mode (ADR-001 / ADR-008):
    #   "openai" — host's shared OpenAI/ChatGPT account (codex login)
    #   "custom" — per-member OpenAI-Responses-compatible endpoint (shim,
    #              direct provider, local server); no OpenAI login needed
    provider: str = "openai"
    provider_base_url: str = ""   # custom: e.g. http://127.0.0.1:8780/v1
    provider_env_key: str = ""    # custom: NAME of env var holding the key
    provider_id: str = ""         # custom: provider id in config.toml
    # Auto-compact: compact the member's thread when its cumulative input
    # tokens cross this threshold (0 = never). Codex-native compaction.
    auto_compact_tokens: int = 0
    # Optional per-turn ceiling (D9): 0 = off. When set, a turn whose
    # cumulative thread input crosses it is force-rotated after completion
    # (post-turn enforcement — mid-turn usage is not observable via shim).
    max_turn_input_tokens: int = 0


@dataclass(frozen=True, slots=True)
class StageSpec:
    """One role stage from the pinned phase contract."""

    stage_id: str
    sequence: int
    execution: str  # "serial" | "parallel"
    roles: tuple[MemberRole, ...]
    writes: tuple[str, ...]  # contract output ids, e.g. "p4.protocol"
    objective: str = ""
    isolation_rule: str = ""
    # Per-output delivery metadata (contracts v1.2.0+, SPEC/D12):
    # family -> {artifact_type, audience, delivery}
    artifact_contracts: dict = field(default_factory=dict)
    reads: tuple[str, ...] = ()
    role_reads: dict[str, tuple[str, ...]] = field(default_factory=dict)
    role_objectives: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    message: str
    object_id: str
    json_pointer: str
    blocks_publication: bool = True
    details: dict = field(default_factory=dict)


@dataclass(slots=True)
class RunRecord:
    run_id: str
    project_id: str
    phase: str
    mode: str
    branch_id: str
    state: RunState = RunState.REQUESTED
    basis_sha256: str = ""
    thread_ids: dict[str, str] = field(default_factory=dict)  # thread_key str -> codex thread id
    correction_attempts: int = 0
    mechanical_repair_attempts: dict[str, int] = field(default_factory=dict)
    findings_history: list[list[dict]] = field(default_factory=list)
    stage_states: dict[str, str] = field(default_factory=dict)  # stage_id -> pending|running|correcting|succeeded|failed|cancelled
    usage: dict = field(default_factory=dict)
    instructions: str = ""  # researcher instructions, verbatim into briefs
    supplied_method: dict | None = None  # exact researcher seed frozen for this P2 run
    created_at: str = ""
    updated_at: str = ""
    terminal_reason: str | None = None
    intent: str = "run"
    target: dict | None = None
    assessment_id: str | None = None
    assessment_purpose: str = "assessment"
    researcher_note_draft: str | None = None
    researcher_response_draft: dict | None = None
    retry_run_id: str | None = None
    assessment_turn_index: int = 0
    responsible_role: str | None = None
    catalog_pin: dict = field(default_factory=dict)
    correction_note: str = ""
    correction_scope: list[str] = field(default_factory=list)
    experiment_budget_seconds: float | None = None
    input_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class StageResult:
    stage_id: str
    succeeded: bool
    output_paths: tuple[Path, ...] = ()
    diagnostic: str = ""
    usage: dict = field(default_factory=dict)  # summed numeric usage counters
