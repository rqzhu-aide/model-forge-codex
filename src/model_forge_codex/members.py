"""Member home provisioning (design/04 §2, ADR-004/005).

Each member gets members/<role>/codex-home/ with:
- AGENTS.md   — the soul (Codex global-scope instructions)
- config.toml — model, reasoning effort, approval never, sandbox policy
Auth (ADR-001) is the selected account's auth.json, connected explicitly
through the account service or provisioned by the operator, never written
by this module.
"""

from __future__ import annotations

from pathlib import Path

from .domain import MemberConfig, MemberRole
from .storage import sha256_file, write_json_atomic

DEFAULT_SOULS = {
    MemberRole.RESEARCH_LEAD: (
        "# Research lead\n\nYou are the team's research lead. Synthesize; bound "
        "contributions; present decision options. Every claim links to a "
        "supporting record or is recorded as a limitation.\n"
    ),
    MemberRole.THEORIST: (
        "# Theorist\n\nYou are the team's theorist. Formal definitions, explicit "
        "assumptions, proofs, validity boundaries. No unaudited claims.\n"
    ),
    MemberRole.DATA_ANALYST: (
        "# Data analyst\n\nYou are the team's data analyst. Implementation "
        "fidelity, empirical design, reproducibility. Record seeds; execute only "
        "the sealed protocol; append deviations without rewriting it.\n"
    ),
    MemberRole.OUTSIDE_REVIEWER: (
        "# Outside reviewer\n\nYou are an independent reviewer of one model "
        "branch's technical report. Assess whether its model, assumptions, numerical "
        "analysis and mathematical justification support its conclusions for the stated problem.\n"
    ),
}

_CONFIG_OPENAI = """# Managed by Model Forge (Codex edition). Hand edits are overwritten.
model = "{model}"
model_reasoning_effort = "{reasoning_effort}"
approval_policy = "never"
sandbox_mode = "workspace-write"
"""

_CONFIG_CUSTOM = """# Managed by Model Forge (Codex edition). Hand edits are overwritten.
model = "{model}"
model_provider = "{provider_id}"
model_reasoning_effort = "{reasoning_effort}"
approval_policy = "never"
sandbox_mode = "workspace-write"
preferred_auth_method = "apikey"

[model_providers.{provider_id}]
name = "{provider_id}"
base_url = "{provider_base_url}"
env_key = "{provider_env_key}"
wire_api = "responses"
"""

#: Models offered by the OpenAI-account mode (design/04 §5 default).
OPENAI_MODELS = ("gpt-6.1-sol", "gpt-5.6", "gpt-5.6-codex", "gpt-5.6-codex-mini")


def render_config_toml(config: MemberConfig) -> str:
    if config.provider == "custom":
        if not (config.provider_base_url and config.provider_env_key and config.provider_id):
            raise ValueError(
                "custom provider mode requires provider_id, provider_base_url, provider_env_key"
            )
        return _CONFIG_CUSTOM.format(
            model=config.model,
            reasoning_effort=config.reasoning_effort,
            provider_id=config.provider_id,
            provider_base_url=config.provider_base_url,
            provider_env_key=config.provider_env_key,
        )
    return _CONFIG_OPENAI.format(
        model=config.model, reasoning_effort=config.reasoning_effort
    )


def member_dir(project_dir: Path, role: MemberRole) -> Path:
    return project_dir / "members" / role.value


def codex_home(project_dir: Path, role: MemberRole) -> Path:
    return member_dir(project_dir, role) / "codex-home"


def provision_member(project_dir: Path, config: MemberConfig) -> dict:
    """Create/refresh the member's home. Returns the stored config record."""
    home = codex_home(project_dir, config.role)
    home.mkdir(parents=True, exist_ok=True)
    soul = config.soul or DEFAULT_SOULS[config.role]
    (home / "AGENTS.md").write_text(soul, encoding="utf-8")
    (home / "config.toml").write_text(render_config_toml(config), encoding="utf-8")
    record = {
        "role": config.role.value,
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "provider": config.provider,
        "provider_base_url": config.provider_base_url,
        "provider_env_key": config.provider_env_key,
        "provider_id": config.provider_id,
        "auto_compact_tokens": config.auto_compact_tokens,
        "max_turn_input_tokens": config.max_turn_input_tokens,
        "soul_sha256": sha256_file(home / "AGENTS.md"),
        "soul": soul,
        "skill_pins": config.skill_pins,
        "memory_policy": config.memory_policy,
        # Auth visibility for the UI: the shared OpenAI login must be
        # provisioned by the operator into this home (ADR-001).
        "openai_auth_present": (home / "auth.json").is_file(),
    }
    write_json_atomic(member_dir(project_dir, config.role) / "config.json", record)
    return record


def provision_team(project_dir: Path, configs: list[MemberConfig] | None = None) -> list[dict]:
    if configs is None:
        configs = [MemberConfig(role=role) for role in MemberRole]
    return [provision_member(project_dir, config) for config in configs]
