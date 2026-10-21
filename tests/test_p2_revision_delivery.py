"""Supported P2 seeds retain exact sources and preserve proposer independence."""
import copy
import json
from pathlib import Path

import pytest

from model_forge_codex.domain import MemberRole
from model_forge_codex.methods import list_methods
from model_forge_codex.records import current_records, generation_path, publish_package, read_generation
from model_forge_codex.research import artifacts_view, source_ref
from model_forge_codex.run_progress import project_run_progress
from model_forge_codex.runs import RunError
from model_forge_codex.storage import read_json
from test_direct_workflow import PID, SEED, complete, direct_engine, p1_documents, p2_documents, script
from test_researcher_workbench_engine import publish


async def published_seed(engine, project):
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    original, files = p2_documents(True)
    original["p2.lead_proposal"]["researcher_origin"]["source_reference"] = "HISTORICAL_RAW_RESEARCHER_ORIGIN"
    first_seed = {**SEED, "source_reference": "HISTORICAL_RAW_RESEARCHER_ORIGIN"}
    script(engine, "P2", "p2.researcher_proposal", original, files)
    first = await complete(engine, "P2", "p2.researcher_proposal", supplied_method=first_seed)
    store = project / "branches/trunk/phases/p2"
    refs = current_records(store)
    selected = next(method for method in list_methods(project) if method["method_id"] == "method.theory")
    source = {"kind": "p2_method_starting_point", "method_identity": selected["identity"],
              "catalog_ref": selected["source_ref"],
              "proposal_ref": source_ref("trunk", "P2", "theory_proposal", refs["theory_proposal"]),
              "proposal_id": "proposal.theory"}
    seed = {"title": selected["title"], "specification_markdown": "EDITED_SEED_DIRECTION_FOR_LEAD",
            "source_reference": json.dumps(source)}
    return first, original, seed


async def test_p2_actual_seeded_delivery_keeps_instructions_and_frozen_origin_lead_only(direct_engine):
    engine, project = direct_engine
    _, original, seed = await published_seed(engine, project)
    outputs, files = p2_documents(True)
    outputs["p2.lead_proposal"]["researcher_origin"] = copy.deepcopy(seed)
    script(engine, "P2", "p2.researcher_proposal", outputs, files)
    engine.bridge.turns.clear()
    note = "DISTINCTIVE_NEW_LEAD_ONLY_NOTE"
    run = await complete(engine, "P2", "p2.full_catalog", instructions=note, supplied_method=seed)
    assert run.mode == "p2.researcher_proposal" and run.branch_id == "trunk"
    assert len(engine.bridge.turns) == 6
    directory = engine.run_dir(PID, run.run_id)
    basis = read_json(directory / "basis.json")
    frozen = basis["p2_method_starting_point"]
    progress = project_run_progress(directory, read_json(directory / "run.json"))
    assert [stage["received_accounts"] for stage in progress["stages"]] == [3, 2, 1]
    assert frozen["method_identity"] == original["p2.theory_proposal"]["method"]["identity"]
    assert read_json(Path(frozen["sources"]["proposal"]["snapshot_path"])) == original["p2.theory_proposal"]
    for stage in engine._stages(run):
        for role in stage.roles:
            brief = (directory / "briefs" / f"{stage.stage_id}.{role.value}.md").read_text(encoding="utf-8")
            if role is MemberRole.RESEARCH_LEAD:
                assert note in brief and "EDITED_SEED_DIRECTION_FOR_LEAD" in brief
                assert "Frozen method starting point" in brief and "version 1" in brief
            else:
                assert note not in brief and "EDITED_SEED_DIRECTION_FOR_LEAD" not in brief
                assert "p2-starting-point" not in brief
    specialist_inputs = directory / "inputs/method-sources/specialist-views"
    views = list(specialist_inputs.glob("*/*.json"))
    assert views
    assert all("HISTORICAL_RAW_RESEARCHER_ORIGIN" not in path.read_text(encoding="utf-8") for path in views)
    assert (directory / "inputs/method-sources/method.lead.json").is_file()
    assert "HISTORICAL_RAW_RESEARCHER_ORIGIN" in (directory / "inputs/method-sources/method.lead.json").read_text(encoding="utf-8")
    # All six authored outputs publish in the ordinary seeded workflow.
    refs = current_records(project / "branches/trunk/phases/p2")
    for family in ("lead_proposal", "theory_proposal", "empirical_proposal", "theory_review", "empirical_review", "catalog_assessment"):
        assert refs[family]["run_id"] == run.run_id
    assert not (project / "researcher/methods.json").exists()


async def test_p2_starting_point_retains_source_bytes_when_current_catalog_changes(direct_engine, monkeypatch):
    engine, project = direct_engine
    _, original, seed = await published_seed(engine, project)
    async def no_work(*args):
        pass
    monkeypatch.setattr(engine, "_drive", no_work)
    run = await engine.start_run(PID, phase="P2", mode="p2.full_catalog", branch_id="trunk", supplied_method=seed)
    await engine._tasks[run.run_id]
    directory = engine.run_dir(PID, run.run_id)
    frozen = read_json(directory / "basis.json")["p2_method_starting_point"]
    source = json.loads(seed["source_reference"])
    store = project / "branches/trunk/phases/p2"
    original_bytes = generation_path(store, "method_catalog", source["catalog_ref"]).read_bytes()
    changed = copy.deepcopy(original["p2.theory_proposal"]["method"])
    changed["identity"]["version"] = 2
    changed["identity"]["definition_sha256"] = "b" * 64
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [changed]}}, "run.later.catalog")
    assert list_methods(project)[0]["version"] == 2
    assert Path(frozen["sources"]["catalog"]["snapshot_path"]).read_bytes() == original_bytes
    generation_path(store, "method_catalog", source["catalog_ref"]).unlink()
    generation_path(store, "theory_proposal", source["proposal_ref"]).unlink()
    brief = engine._render_brief(run, engine._stages(run)[0], MemberRole.RESEARCH_LEAD, directory)
    assert "method.theory, version 1" in brief
    assert run.supplied_method == seed


async def test_p2_earlier_proposal_starts_from_its_own_catalog_after_same_identity_is_republished(direct_engine):
    engine, project = direct_engine
    first, original, seed = await published_seed(engine, project)
    outputs, files = p2_documents(False)
    script(engine, "P2", "p2.full_catalog", outputs, files)
    second = await complete(engine, "P2", "p2.full_catalog")
    proposals = [item for item in artifacts_view(project)["method_proposals"]
                 if item["proposal_id"] == "proposal.theory"]
    earlier = next(item for item in proposals if item["generation_ref"]["run_id"] == first.run_id)
    current = next(item for item in proposals if item["generation_ref"]["run_id"] == second.run_id)
    assert earlier["method"]["identity"] == current["method"]["identity"]
    selected = next(method for method in list_methods(project) if method["method_id"] == "method.theory")
    assert selected["source_ref"]["run_id"] == second.run_id
    source = json.loads(seed["source_reference"])
    source.update(catalog_ref=earlier["catalog_ref"], proposal_ref=earlier["generation_ref"],
                  proposal_id=earlier["proposal_id"])
    seed["source_reference"] = json.dumps(source)
    assert earlier["catalog_ref"]["run_id"] == first.run_id
    assert current["catalog_ref"]["run_id"] == second.run_id
    assert earlier["catalog_ref"]["package_id"] == earlier["package_id"]
    seeded, files = p2_documents(True)
    seeded["p2.lead_proposal"]["researcher_origin"] = copy.deepcopy(seed)
    script(engine, "P2", "p2.researcher_proposal", seeded, files)
    launched = await complete(engine, "P2", "p2.full_catalog", supplied_method=seed)
    frozen = read_json(engine.run_dir(PID, launched.run_id) / "basis.json")["p2_method_starting_point"]
    assert {item["reference"]["run_id"] for item in frozen["sources"].values()} == {first.run_id}
    assert read_json(Path(frozen["sources"]["proposal"]["snapshot_path"])) == original["p2.theory_proposal"]


@pytest.mark.parametrize("forgery", ["digest", "run", "package", "identity", "proposal", "missing_origin", "uncommitted"])
async def test_p2_forged_selected_sources_are_rejected_before_any_turn(direct_engine, forgery):
    engine, project = direct_engine
    _, _, seed = await published_seed(engine, project)
    source = json.loads(seed["source_reference"])
    if forgery == "digest":
        source["catalog_ref"]["sha256"] = "f" * 64
    elif forgery == "run":
        source["catalog_ref"]["run_id"] = "run.forged"
    elif forgery == "package":
        source["catalog_ref"]["package_id"] = "package.forged"
    elif forgery == "identity":
        source["method_identity"]["version"] = 9
    elif forgery == "proposal":
        source["proposal_id"] = "proposal.someone_else"
    elif forgery == "missing_origin":
        source.pop("proposal_ref")
    else:
        store = project / "branches/trunk/phases/p2"
        document = read_generation(store, "method_catalog", source["catalog_ref"])
        prepared = {}
        def interrupt_publication(package):
            prepared.update(package)
            raise RuntimeError("Interrupted before committing the prepared publication")
        with pytest.raises(RuntimeError, match="Interrupted"):
            publish_package(store, {"method_catalog": json.dumps(document).encode()}, run_id="run.uncommitted",
                            phase="P2", branch_id="trunk", before_commit=interrupt_publication)
        source["catalog_ref"] = source_ref("trunk", "P2", "method_catalog", prepared["records"]["method_catalog"])
    seed["source_reference"] = json.dumps(source)
    before = len(engine.bridge.turns)
    with pytest.raises(RunError, match="selected|proposal"):
        await engine.start_run(PID, phase="P2", mode="p2.full_catalog", branch_id="trunk", supplied_method=seed)
    assert len(engine.bridge.turns) == before


async def test_p2_focused_revision_remains_blocked(direct_engine):
    engine, project = direct_engine
    _, _, seed = await published_seed(engine, project)
    assert any("exact selected baseline" in reason for reason in
               engine.check_readiness(PID, "P2", "trunk", "p2.focused_method"))
    before = len(engine.bridge.turns)
    with pytest.raises(RunError, match="[Ff]ocused|selected baseline"):
        await engine.start_run(PID, phase="P2", mode="p2.focused_method", branch_id="trunk", supplied_method=seed)
    assert len(engine.bridge.turns) == before
