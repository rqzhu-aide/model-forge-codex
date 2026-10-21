"""Member configuration: both provider modes (ADR-001 openai / ADR-008
custom), config.toml rendering, partial-update overlay via the API."""

import tomllib

import pytest

from model_forge_codex.domain import MemberConfig, MemberRole
from model_forge_codex.members import codex_home, provision_member, provision_team, render_config_toml
from model_forge_codex.storage import read_json
from model_forge_codex.execution import capture_execution


def test_new_team_and_missing_execution_settings_use_sol_61_xhigh(tmp_path):
    team = provision_team(tmp_path)
    assert len(team) == len(MemberRole)
    for member in team:
        assert (member["model"], member["reasoning_effort"]) == ("gpt-6.1-sol", "xhigh")
        home = codex_home(tmp_path, MemberRole(member["role"]))
        settings = tomllib.loads((home / "config.toml").read_text())
        assert (settings["model"], settings["model_reasoning_effort"]) == ("gpt-6.1-sol", "xhigh")
        execution = capture_execution({}, home)
        assert (execution["model"], execution["reasoning_effort"]) == ("gpt-6.1-sol", "xhigh")
    explicit = capture_execution({"model": "chosen-model", "reasoning_effort": "medium"}, home)
    assert (explicit["model"], explicit["reasoning_effort"]) == ("chosen-model", "medium")


def test_openai_mode_config_has_no_provider_block(tmp_path):
    cfg = MemberConfig(role=MemberRole.THEORIST, model="gpt-5.6-codex")
    toml = render_config_toml(cfg)
    assert 'model = "gpt-5.6-codex"' in toml
    assert "model_providers" not in toml
    assert "model_provider" not in toml


def test_custom_mode_renders_provider_block(tmp_path):
    cfg = MemberConfig(
        role=MemberRole.DATA_ANALYST,
        model="glm-5.3",
        provider="custom",
        provider_id="shim",
        provider_base_url="http://127.0.0.1:8780/v1",
        provider_env_key="SHIM_KEY",
    )
    toml = render_config_toml(cfg)
    assert 'model_provider = "shim"' in toml
    assert 'base_url = "http://127.0.0.1:8780/v1"' in toml
    assert 'env_key = "SHIM_KEY"' in toml
    assert 'wire_api = "responses"' in toml
    assert 'preferred_auth_method = "apikey"' in toml


def test_custom_mode_requires_all_fields():
    cfg = MemberConfig(
        role=MemberRole.DATA_ANALYST, provider="custom", model="glm-5.3"
    )
    with pytest.raises(ValueError, match="custom provider mode requires"):
        render_config_toml(cfg)


def test_provision_stores_provider_and_auth_visibility(tmp_path):
    cfg = MemberConfig(
        role=MemberRole.RESEARCH_LEAD,
        provider="custom",
        provider_id="shim",
        provider_base_url="http://127.0.0.1:8780/v1",
        provider_env_key="SHIM_KEY",
    )
    record = provision_member(tmp_path, cfg)
    assert record["provider"] == "custom"
    assert record["provider_base_url"] == "http://127.0.0.1:8780/v1"
    assert record["openai_auth_present"] is False
    assert (tmp_path / "members" / "research_lead" / "codex-home" / "AGENTS.md").is_file()
    # And the config.toml on disk is the custom one.
    toml = (tmp_path / "members" / "research_lead" / "codex-home" / "config.toml").read_text()
    assert 'model_provider = "shim"' in toml


async def test_member_update_overlays_without_wiping(engine):
    """PUT with only a model change must keep soul + provider settings."""
    from httpx import ASGITransport, AsyncClient

    from model_forge_codex.service import create_app

    eng, bridge, project_id = engine
    app = create_app(data_root=eng.data_root, bridge=bridge)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        # Set a custom provider + soul on the analyst.
        resp = await client.put(
            f"/api/v1/projects/{project_id}/members/data_analyst",
            json={
                "provider": "custom",
                "provider_id": "shim",
                "provider_base_url": "http://127.0.0.1:8780/v1",
                "provider_env_key": "SHIM_KEY",
                "soul": "# Analyst\n\nCustom soul text.",
            },
        )
        assert resp.status_code == 200, resp.text
        # Now only change the model.
        resp = await client.put(
            f"/api/v1/projects/{project_id}/members/data_analyst",
            json={"model": "glm-5.3"},
        )
        assert resp.status_code == 200, resp.text
        doc = resp.json()
        assert doc["model"] == "glm-5.3"
        assert doc["provider"] == "custom"  # preserved, not wiped
        assert doc["soul"] == "# Analyst\n\nCustom soul text."
        # Invalid custom config is a 400 with the reason.
        resp = await client.put(
            f"/api/v1/projects/{project_id}/members/theorist",
            json={"provider": "custom"},
        )
        assert resp.status_code == 400
        # Provider options endpoint feeds the config page.
        resp = await client.get("/api/v1/provider-options")
        assert resp.status_code == 200
        assert "gpt-5.6" in resp.json()["openai_models"]
        assert resp.json()["openai_models"][0] == "gpt-6.1-sol"
