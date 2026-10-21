"""Shared provider authority controls account provisioning, with fake credentials."""
import json

import pytest

from model_forge_codex.domain import MemberConfig, MemberRole
from model_forge_codex.members import provision_member
from model_forge_codex.storage import read_json
from test_accounts import Accounts, SECRET, auth, project


@pytest.fixture
def account_service(tmp_path, monkeypatch):
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    monkeypatch.delenv("MF_CODEX_PROVIDER_CONFIG", raising=False)
    return Accounts(tmp_path)


async def test_shared_openai_provisions_stored_custom_members_and_preserves_other_auth(account_service):
    service = account_service
    selected = auth(service.shared_home)
    directory = project(service)
    custom_role = MemberRole.DATA_ANALYST
    provision_member(directory, MemberConfig(role=custom_role, provider="custom", provider_id="local",
                                            provider_base_url="http://localhost/v1", provider_env_key="LOCAL_KEY"))
    preserved_home = directory / "members/theorist/codex-home"
    preserved = auth(preserved_home, "different-account")
    (service.data_root / "providers.toml").write_text('[provider]\ntype = "openai"\nmodel = "shared-model"\n')

    status = await service.connect()

    assert status["member_homes"] == {"connected": 3, "existing": 1, "total": 4}
    assert (directory / "members/data_analyst/codex-home/auth.json").read_bytes() == selected
    assert (preserved_home / "auth.json").read_bytes() == preserved
    assert read_json(directory / "members/data_analyst/config.json")["provider"] == "custom"
    assert SECRET not in json.dumps(status)

    # Removing shared authority restores manual account counting without
    # removing any previously connected credentials.
    (service.data_root / "providers.toml").unlink()
    restored = await service.status()
    assert restored["member_homes"] == {"connected": 2, "existing": 1, "total": 3}
    assert (directory / "members/data_analyst/codex-home/auth.json").read_bytes() == selected


async def test_shared_custom_does_not_copy_openai_credentials_or_count_manual_openai_members(account_service):
    service = account_service
    auth(service.shared_home)
    await service.connect()
    directory = project(service)
    preserved_home = directory / "members/theorist/codex-home"
    preserved = auth(preserved_home, "existing-account")
    (service.data_root / "providers.toml").write_text(
        '[provider]\ntype = "custom"\nid = "example"\nmodel = "shared-model"\n'
        'base_url = "https://provider.example/v1"\napi_key = "SIMULATED_PROVIDER_SECRET"\n'
    )

    service.provision_project(directory)
    status = await service.status()

    assert status["member_homes"] == {"connected": 0, "existing": 0, "total": 0}
    assert status["connected"]
    assert "custom provider" in status["message"]
    assert (preserved_home / "auth.json").read_bytes() == preserved
    assert len(list(directory.glob("members/*/codex-home/auth.json"))) == 1
    assert SECRET not in json.dumps(status)
    assert "SIMULATED_PROVIDER_SECRET" not in json.dumps(status)


async def test_invalid_shared_config_pauses_provisioning_with_sanitized_status(account_service):
    service = account_service
    auth(service.shared_home)
    await service.connect()
    directory = project(service)
    config = service.data_root / "providers.toml"
    config.write_text('[provider]\ntype = "SIMULATED_PRIVATE_VALUE"\nmodel = "shared-model"\n')

    service.provision_project(directory)
    status = await service.status()

    assert not list(directory.glob("members/*/codex-home/auth.json"))
    assert status["member_homes"] == {"connected": 0, "existing": 0, "total": 0}
    assert status["provider_config"]["error"]
    assert "provisioning is paused" in status["message"]
    assert "SIMULATED_PRIVATE_VALUE" not in json.dumps(status)
    assert SECRET not in json.dumps(status)

    config.write_text('[provider]\ntype = "openai"\nmodel = "shared-model"\n')
    service.provision_project(directory)
    assert len(list(directory.glob("members/*/codex-home/auth.json"))) == 4
    assert not (await service.status())["provider_config"]["error"]


async def test_provider_path_override_controls_account_provisioning(account_service, monkeypatch):
    service = account_service
    auth(service.shared_home)
    directory = project(service)
    # The default file is invalid, but an explicit shared path has authority.
    (service.data_root / "providers.toml").write_text('not valid TOML')
    configured = service.data_root / "selected-providers.toml"
    configured.write_text('[provider]\ntype = "openai"\nmodel = "shared-model"\n')
    monkeypatch.setenv("MF_CODEX_PROVIDER_CONFIG", str(configured))

    status = await service.connect()

    assert status["provider_config"]["path"] == str(configured.resolve())
    assert status["member_homes"]["connected"] == 4
    assert len(list(directory.glob("members/*/codex-home/auth.json"))) == 4


@pytest.mark.parametrize(("configuration", "account_roles"), [
    (
        '[provider]\ntype = "custom"\nid = "default_provider"\nmodel = "default-model"\n'
        'base_url = "https://provider.example/v1"\napi_key_env = "UNSET_TEST_PROVIDER_KEY"\n'
        '[members.data_analyst]\ntype = "openai"\nmodel = "account-model"\n',
        {"data_analyst"},
    ),
    (
        '[provider]\ntype = "openai"\nmodel = "account-model"\n'
        '[members.research_lead]\ntype = "custom"\nid = "lead_provider"\n'
        'base_url = "https://provider.example/v1"\napi_key = "SIMULATED_PROVIDER_SECRET"\n'
        'model = "lead-model"\n',
        {"theorist", "data_analyst", "outside_reviewer"},
    ),
])
async def test_mixed_providers_copy_only_effective_openai_credentials(
    account_service, monkeypatch, configuration, account_roles
):
    service = account_service
    monkeypatch.delenv("UNSET_TEST_PROVIDER_KEY", raising=False)
    selected = auth(service.shared_home)
    await service.connect()
    directory = project(service)
    # A custom role's earlier account credentials must survive, but must not
    # cause that role to be counted as account-backed under current settings.
    preserved_home = directory / "members/research_lead/codex-home"
    preserved = auth(preserved_home, "previous-account")
    (service.data_root / "providers.toml").write_text(configuration)

    service.provision_project(directory)
    status = await service.status()

    assert status["provider_config"]["active"], status["provider_config"]
    assert status["member_homes"] == {"connected": len(account_roles), "existing": 0, "total": len(account_roles)}
    assert "Other team members use custom providers" in status["message"]
    for role in MemberRole:
        path = directory / "members" / role.value / "codex-home/auth.json"
        if role.value in account_roles:
            assert path.read_bytes() == selected
        elif role == MemberRole.RESEARCH_LEAD:
            assert path.read_bytes() == preserved
        else:
            assert not path.exists()
    assert SECRET not in json.dumps(status)
    assert "SIMULATED_PROVIDER_SECRET" not in json.dumps(status)
