"""New decisions are consequential and compact without upgrading historical reads."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from jsonschema import Draft202012Validator
import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.researcher_pause import pause_brief
from model_forge_codex.storage import read_json


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def test_legacy_attention_remains_readable_without_invented_priority():
    catalog = Catalog(CONTRACTS)
    item = read_json(CONTRACTS / "examples/attention-setting-decision.example.json")
    item.pop("decision_priority")
    item.pop("response_kind")
    item["options"] = ["Enrolled cohort", {"label": "Wider population"}]
    before = deepcopy(item)
    validator = Draft202012Validator(catalog.schema_doc("attention-item.schema.json"),
                                    registry=catalog._registry)
    assert not list(validator.iter_errors(item))
    assert item == before


def test_specialist_fact_proposal_needs_no_repeated_rationale():
    catalog = Catalog(CONTRACTS)
    document = read_json(CONTRACTS / "examples/literature-findings.example.json")
    document["proposed_questions"] = [{
        "question": "How many eligible patients and outcome events are available?",
        "context_markdown": "No patient data or dictionary has been supplied. The encoded feature dimension and event support remain unknown.",
        "answer_consequences_markdown": "The team can review conditional formulations now; actual-data feasibility remains unestablished until these counts and dimensions are known.",
        "source_refs": [],
    }]
    assert not catalog.validate_output("p1.empirical_literature", document)


@pytest.mark.parametrize("phase", ["P1", "P2", "P3", "P4", "P5"])
def test_executable_lead_instructions_author_compact_decisions(phase):
    source = read_json(CONTRACTS / "contracts/phases.json")
    expected = next(contract for contract in source["contracts"] if contract["phase_id"] == phase)
    contract = read_json(CONTRACTS / f"contracts/phases/{phase}.json")
    assert contract == expected
    assert "consequential_researcher_decisions_v1" in contract["capabilities"]
    for stage in contract["role_stages"]:
        if stage["execution"] == "serial" and stage["roles"] == ["research_lead"]:
            objective = stage["objective"]
            assert all(field in objective for field in ("decision_priority", "response_kind", "{id,label,consequence}", "recommendation"))
            assert "Empty attention output is valid" in objective or "attention_items may be empty" in objective
            if phase != "P5":
                assert "Different mathematical definitions or defensible alternatives alone do not create a researcher decision" in objective
                assert "counting all attempted developments" in objective
                assert "Preserve the intended inferential claim" in objective


def test_nonblocking_pause_guidance_does_not_manufacture_a_question():
    stage = SimpleNamespace(execution="serial", roles=["research_lead"])
    brief = pause_brief(SimpleNamespace(phase="P2", intent="run"), stage, "research_lead")
    assert "Attention may be empty; do not manufacture a question" in brief
    assert "Otherwise continue justified work with explicit conditions" in brief
    assert "author an informational attention question" not in brief
    editorial = pause_brief(SimpleNamespace(phase="P5", intent="run"), stage, "research_lead")
    assert "indispensable editorial choice" in editorial
    assert "Do not reopen problem, collection, method or study-design questions" in editorial
