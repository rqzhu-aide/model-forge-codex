"""Six-card content is authored, exact and shared through real publication paths."""
from copy import deepcopy
from pathlib import Path
import json
import runpy

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole
from model_forge_codex.p1_science import entry_reference, literature_entries, validate_p1_science
from model_forge_codex.research import artifacts_view
from model_forge_codex.storage import read_json
from test_direct_workflow import PID, complete, direct_engine, p1_documents, script
from test_draft_validation import draft_engine, run as draft_run, write_outputs, check as draft_check
from test_p1_framework_context import navigation_indexes
from test_p1_science import RUN, correction, library_for, with_correction
from test_literature_projection import publish

ROOT = Path(__file__).resolve().parents[1]


def upgrade(document):
    document["schema_version"] = "1.2.0"
    document["research_setting"].update(component_interpretations=[], research_goal_markdown="Develop a constrained model and technical report.")
    document["landscape"].update(overview_item_ids=[], common_assumptions=[], citation_refs=[])
    return document


@pytest.mark.parametrize("field", ["research_goal_markdown", "component_interpretations"])
def test_new_shape_requires_authored_setting_fields_but_old_records_remain_readable(field):
    catalog = Catalog(ROOT / "contracts")
    document = p1_documents()["p1.research_basis"]
    del document["research_setting"][field]
    assert catalog.validate_output("p1.research_basis", document)
    document["schema_version"] = "1.1.0"
    assert not catalog.validate_output("p1.research_basis", document)


def test_new_run_rejects_downgraded_basis_in_immediate_member_check(draft_engine):
    record, stages, _ = draft_run(draft_engine, "P1", "p1.literature_update")
    document = p1_documents()["p1.research_basis"]
    document["schema_version"] = "1.1.0"
    workspace = draft_engine.member_workspace(record, stages[1].stage_id, MemberRole.RESEARCH_LEAD)
    write_outputs(workspace, {"p1.research_basis": document})
    result = draft_check(draft_engine, record, stages[1], MemberRole.RESEARCH_LEAD)
    assert result["status"] == "failed"
    assert any(item["code"] == "schema.const" and item["json_pointer"] == "/schema_version" for item in result["findings"])


@pytest.mark.parametrize("damage", [None, "digest", "source", "unbound", "overview", "assumption"])
def test_citations_and_overview_are_exact_not_guessed(damage):
    docs, _ = with_correction()
    basis = upgrade(docs["research_basis"])
    entry = next(item for item in literature_entries(docs, None, run_id=RUN) if item["role"] == "theorist")
    source_id = entry["entry"]["source"]["source_id"]
    basis["landscape"].update(summary_markdown=f"Related work [Author, year](#cite:{source_id}).", citation_refs=[{"source_id": source_id, "entry_ref": entry_reference(entry)}])
    if damage == "digest":
        basis["landscape"]["citation_refs"][0]["entry_ref"]["entry_sha256"] = "0" * 64
    elif damage == "source":
        basis["landscape"]["citation_refs"][0]["source_id"] = "citation.different"
    elif damage == "unbound":
        basis["landscape"]["citation_refs"] = []
    elif damage == "overview":
        basis["landscape"]["overview_item_ids"] = ["framework.unavailable"]
    elif damage == "assumption":
        basis["landscape"]["common_assumptions"] = [{"assumption_id": "assumption.a", "landscape_item_ids": [], "citation_ids": ["citation.unavailable"]}]
    findings = validate_p1_science(docs, run_id=RUN)
    assert bool(findings) == (damage is not None)


def test_historical_citation_keeps_correction_provenance_even_when_digest_repeats(tmp_path):
    docs, _ = with_correction()
    basis = upgrade(docs["research_basis"])
    first = library_for(docs)
    entry = next(item for item in literature_entries({}, first, run_id="run.second") if item["role"] == "theorist")
    binding = {"source_id": entry["entry"]["source"]["source_id"], "entry_ref": entry_reference(entry)}
    basis["landscape"]["citation_refs"] = [binding]
    publish(tmp_path, {**docs, "literature_library": first}, RUN)
    next_basis = deepcopy(basis)
    next_basis["entry_corrections"] = [correction(entry_reference(entry), "correction.noop")]
    second_docs = {"research_basis": next_basis}
    second = library_for(second_docs, first, "run.second")
    publish(tmp_path, {**second_docs, "literature_library": second}, "run.second")
    view = artifacts_view(tmp_path)
    current, historical = view["research_bases"]
    assert current["citations"][0]["card"]["lead_revision"]["run_id"] == "run.second"
    assert historical["citations"][0]["card"]["lead_revision"]["run_id"] == RUN
    assert current["citations"][0]["entry_ref"] == historical["citations"][0]["entry_ref"]
    assert historical["citations"][0]["bibliography"] == entry["entry"]["source"]
    assert view["load_errors"] == []


async def test_actual_lead_navigation_receives_profile_without_discovery_peer_leak(direct_engine):
    engine, project = direct_engine
    documents = p1_documents()
    marker = "PROFILE_MARKER_observed_rows"
    documents["p1.empirical_literature"]["data_profiles"] = [{"source_identity": "data.test.csv", "source_sha256": "a" * 64,
        "inspection_scope": "Bounded descriptive inspection", "observed_structure_markdown": marker,
        "limitations_markdown": "Collection mechanism unknown", "runtime": "Shared Python"}]
    script(engine, "P1", "p1.literature_update", documents)
    final = await complete(engine, "P1", "p1.literature_update")
    directory = engine.run_dir(PID, final.run_id)
    indexes = navigation_indexes(directory)
    lead_index = next(path for path in indexes if "p1.lead_synthesis" in path.parts)
    assert marker in str(read_json(lead_index)["collections"])
    assert "entry_digest_instruction" in read_json(lead_index)
    for path in indexes:
        if "p1.discovery" in path.parts:
            assert marker not in path.read_text(encoding="utf-8")
    lead_brief = (directory / "briefs/p1.lead_synthesis.research_lead.md").read_text(encoding="utf-8")
    assert "research_goal_markdown" in lead_brief and "common_assumptions" in lead_brief
    assert len(engine.bridge.turns) == 4
    view = artifacts_view(project)
    assert marker in str(view["literature_collections"])
    assert view["research_bases"][0]["research_setting"]["research_goal_markdown"] == documents["p1.research_basis"]["research_setting"]["research_goal_markdown"]


async def test_frozen_116_p1_contract_still_publishes_its_original_11_basis(direct_engine):
    engine, project = direct_engine
    from model_forge_codex.storage import write_json_atomic
    catalog_root = project / "contracts"
    old_p1 = read_json(ROOT / "tests/fixtures/legacy-p1-contract.json")
    write_json_atomic(catalog_root / "contracts/phases/P1.json", old_p1)
    aggregate = read_json(catalog_root / "contracts/phases.json")
    aggregate["contracts"] = [old_p1 if item["phase_id"] == "P1" else item for item in aggregate["contracts"]]
    write_json_atomic(catalog_root / "contracts/phases.json", aggregate)
    for name in ("catalog-index.json", "catalog-pin.json"):
        metadata = read_json(catalog_root / name)
        metadata["catalog_version"] = "1.16.0"
        write_json_atomic(catalog_root / name, metadata)
    (catalog_root / "VERSION").write_text("1.16.0\n", encoding="utf-8")
    runpy.run_path(str(ROOT / "contracts/refresh_manifest.py"))["refresh"](catalog_root)
    docs = p1_documents()
    basis = docs["p1.research_basis"]
    for family, document in docs.items():
        if family != "p1.research_basis":
            document["schema_version"] = "1.1.0"
    basis["schema_version"] = "1.1.0"
    for field in ("component_interpretations", "research_goal_markdown"):
        basis["research_setting"].pop(field)
    for field in ("overview_item_ids", "common_assumptions", "citation_refs"):
        basis["landscape"].pop(field)
    script(engine, "P1", "p1.literature_update", docs)
    final = await complete(engine, "P1", "p1.literature_update")
    frozen = Catalog(engine.run_dir(PID, final.run_id) / "contracts")
    assert frozen.version == "1.16.0" and frozen.verify_manifest() == []
    assert artifacts_view(project)["research_bases"][0]["schema_version"] == "1.1.0"
