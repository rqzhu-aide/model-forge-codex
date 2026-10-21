"""Actual P1 delivery stays provider independent and scoped to its update."""
import json

import pytest

from model_forge_codex.phase_interactions import preparation_path, save_preparation
from model_forge_codex.records import current_records, read_generation
from model_forge_codex.research import artifacts_view
from model_forge_codex.run_progress import project_run_progress
from model_forge_codex.storage import read_json
from test_direct_workflow import PID, complete, direct_engine, p1_documents, script


@pytest.mark.parametrize("provider", ["openai", "custom", "mixed"])
async def test_p1_actual_discovery_briefs_and_owned_outputs_preserve_instructions(direct_engine, provider, monkeypatch):
    engine, project = direct_engine
    monkeypatch.delenv("MF_CODEX_PROVIDER_CONFIG", raising=False)
    if provider == "openai":
        config = '[provider]\ntype="openai"\nmodel="account-test"\n'
    else:
        config = '[provider]\ntype="custom"\nid="fixture"\nmodel="custom-test"\nbase_url="https://provider.example.test/v1"\napi_key="PRIVATE_P1_PROVIDER_KEY"\n'
        if provider == "mixed":
            config += '[members.theorist]\ntype="openai"\nmodel="account-theory-test"\n[members.data_analyst]\nmodel="custom-analyst-test"\n'
    (engine.data_root / "providers.toml").write_text(config, encoding="utf-8")
    save_preparation(preparation_path(project, "trunk", "P2"), "P2_PRIVATE_LEAD_DIRECTION")
    outputs = p1_documents()
    instruction = "P1_SEARCH_DIRECTION: investigate the constrained estimation setting."
    script(engine, "P1", "p1.literature_update", outputs)
    final = await complete(engine, "P1", "p1.literature_update", instructions=instruction)
    directory = engine.run_dir(PID, final.run_id)
    for role, family in [("research_lead", "lead_literature"), ("theorist", "theory_literature"), ("data_analyst", "empirical_literature")]:
        brief = (directory / "briefs" / f"p1.discovery.{role}.md").read_text(encoding="utf-8")
        assert instruction in brief
        assert "P2_PRIVATE_LEAD_DIRECTION" not in brief
        assert "PRIVATE_P1_PROVIDER_KEY" not in brief
        assert read_json(directory / "outputs/p1.discovery" / f"{family}.json") == outputs[f"p1.{family}"]
        pointer = current_records(project / "branches/trunk/phases/p1")[family]
        assert read_generation(project / "branches/trunk/phases/p1", family, pointer) == outputs[f"p1.{family}"]
    projection = project_run_progress(directory, read_json(directory / "run.json"))
    assert projection["stages"][0]["received_accounts"] == 3
    assert all(member["accepted"] for member in projection["stages"][0]["members"])
    assert "PRIVATE_P1_PROVIDER_KEY" not in json.dumps(artifacts_view(project))
    assert "PRIVATE_P1_PROVIDER_KEY" not in json.dumps(projection)


async def test_p1_two_updates_keep_cumulative_papers_and_current_scope_metadata(direct_engine):
    engine, project = direct_engine
    for update in ("first", "second"):
        outputs = p1_documents((f"citation.{update}",))
        for role in ("lead", "theory", "empirical"):
            outputs[f"p1.{role}_literature"]["search_scope"] = f"{update} update {role} scope"
        script(engine, "P1", "p1.literature_update", outputs)
        await complete(engine, "P1", "p1.literature_update")
    view = artifacts_view(project)
    current = [item for item in view["literature_collections"] if item["is_current_package"]]
    earlier = [item for item in view["literature_collections"] if not item["is_current_package"]]
    assert len(current) == len(earlier) == 3
    assert {item["role"] for item in current} == {"research_lead", "theorist", "data_analyst"}
    assert all(item["search_scope"].startswith("second update") for item in current)
    assert all(item["search_scope"].startswith("first update") for item in earlier)
    assert all(item["generation_ref"]["generation_id"] and item["generation_ref"]["sha256"] for item in current + earlier)
    assert all(item.get("published_at") and item.get("package_id") for item in current + earlier)
    assert {source["source_id"] for source in view["literature_libraries"][0]["sources"]} == {"citation.first", "citation.second"}
