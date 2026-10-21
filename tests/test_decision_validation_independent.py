"""Independent checks of the new authoring boundary and malformed output handling."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from model_forge_codex.catalog import Catalog


ROOT = Path(__file__).resolve().parents[1] / "contracts"
CAPABILITY = "consequential_researcher_decisions_v1"


def example(name):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def researcher_item(**changes):
    item = example("contextual-attention-item.example.json")
    item.update(kind="researcher_decision", severity="major", target_phase="P3",
                decision_priority="interpretation", response_kind="choice",
                options=[{"id": "cohort", "label": "All survivors",
                          "consequence": "Requires support for incomplete histories."},
                         {"id": "observed", "label": "Those under observation",
                          "consequence": "Limits the intended prediction population."}],
                recommendation="Retain the cohort target because cohort-wide use is requested.")
    item.update(changes)
    return item


@pytest.mark.parametrize("field", ["decision_priority", "response_kind"])
@pytest.mark.parametrize("value", [[], {}, ["choice"], {"choice": True}, None, 3, False])
def test_malformed_authored_enums_return_correctable_findings(field, value):
    item = researcher_item(**{field: value})
    findings = Catalog(ROOT).validate_output("p3.attention_items", [item])
    assert any(row.code == "attention." + field and row.json_pointer == "/0/" + field
               for row in findings)
    assert any(row.code.startswith("schema.") for row in findings)


@pytest.mark.parametrize("output_id,container", [
    ("p1.research_basis", "research-basis.example.json"),
    ("p2.catalog_assessment", "catalog-assessment.example.json"),
    ("p3.attention_items", None),
    ("p4.attention_items", None),
    ("p5.attention_items", None),
])
def test_authoring_requirement_reaches_each_published_question_surface(output_id, container):
    item = researcher_item()
    item.pop("decision_priority")
    item.pop("response_kind")
    document = example(container) if container else [item]
    if container:
        document["attention_items"] = [item]
    before = deepcopy(document)
    findings = Catalog(ROOT).validate_output(output_id, document)
    prefix = "/attention_items/0/" if container else "/0/"
    assert {(row.code, row.json_pointer) for row in findings} >= {
        ("attention.decision_priority", prefix + "decision_priority"),
        ("attention.response_kind", prefix + "response_kind"),
    }
    assert document == before


def test_legacy_capability_keeps_existing_question_and_prose_options_readable(tmp_path):
    target = tmp_path / "catalog"
    shutil.copytree(ROOT, target)
    phase_path = target / "contracts" / "phases" / "P3.json"
    phase = json.loads(phase_path.read_text(encoding="utf-8"))
    phase["capabilities"].remove(CAPABILITY)
    phase_path.write_text(json.dumps(phase), encoding="utf-8")
    item = researcher_item(options=["Keep the established target.", "Discuss a scope change."])
    for field in ("decision_priority", "response_kind", "recommendation"):
        item.pop(field)
    before = deepcopy(item)
    assert not Catalog(target).validate_output("p3.attention_items", [item])
    assert item == before
    assert {row.code for row in Catalog(ROOT).validate_output("p3.attention_items", [item])} >= {
        "attention.decision_priority", "attention.response_kind",
    }


@pytest.mark.parametrize("options", [["Prose alternative"], [{"label": "Incomplete"}],
                                     [{"id": [], "label": "A", "consequence": "B"}],
                                     [{"id": "a", "label": "A", "consequence": " "}],
                                     {"id": "a"}])
def test_new_authored_options_need_complete_structured_alternatives(options):
    findings = Catalog(ROOT).validate_output("p3.attention_items", [researcher_item(options=options)])
    assert any(row.code == "attention.options" and row.json_pointer == "/0/options" for row in findings)


def test_equal_option_ids_cannot_name_different_alternatives():
    item = researcher_item()
    item["options"][1]["id"] = item["options"][0]["id"]
    findings = Catalog(ROOT).validate_output("p3.attention_items", [item])
    assert any(row.code == "attention.option_ids" for row in findings)


@pytest.mark.parametrize("extra", [{"options": [{"id": "a", "label": "A", "consequence": "B"}]},
                                   {"recommendation": "Assume there are enough patients."}])
def test_study_information_is_not_authored_as_a_preferred_patient_fact(extra):
    item = researcher_item(response_kind="study_fact", options=[], recommendation="")
    item.update(extra)
    findings = Catalog(ROOT).validate_output("p3.attention_items", [item])
    assert any(row.code == "attention.study_fact" for row in findings)


def test_empty_attention_and_lead_owned_tasks_need_no_researcher_metadata():
    catalog = Catalog(ROOT)
    assert not catalog.validate_output("p3.attention_items", [])
    assert not catalog.validate_output("p3.attention_items", [example("contextual-attention-item.example.json")])
    item = researcher_item()
    item.pop("options")
    assert not catalog.validate_output("p3.attention_items", [item])
