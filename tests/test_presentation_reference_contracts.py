"""Presentation additions preserve old record shapes and scientific ownership."""

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from model_forge_codex.catalog import Catalog


CATALOG = Path(__file__).resolve().parents[1] / "contracts"


def read(relative):
    return json.loads((CATALOG / relative).read_text(encoding="utf-8"))


def validator(name):
    schemas = [json.loads(path.read_text(encoding="utf-8"))
               for path in (CATALOG / "schemas").glob("*.schema.json")]
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas)
    return Draft202012Validator(read("schemas/" + name), registry=registry)


def test_authored_recap_and_notation_are_optional_for_existing_p4_records():
    validate = validator("p4-lead-synthesis.schema.json")
    legacy = read("examples/p4-lead-synthesis.example.json")
    assert not list(validate.iter_errors(legacy))
    authored = copy.deepcopy(legacy)
    authored["decision_summary"].update(
        method_recap_markdown="The rule estimates the retained mean from the supplied observations.",
        notation_markdown="| Symbol | Meaning | Unit |\n| --- | --- | --- |\n| $n$ | Observations | Count |")
    assert not list(validate.iter_errors(authored))
    for field in ("method_recap_markdown", "notation_markdown"):
        invalid = copy.deepcopy(authored)
        invalid["decision_summary"][field] = "  "
        assert list(validate.iter_errors(invalid))


def test_recommendation_pointer_is_optional_and_cannot_describe_a_study_fact():
    validate = validator("contextual-attention-item.schema.json")
    old = read("examples/attention-setting-decision.example.json")
    assert not list(validate.iter_errors(old))
    choice = copy.deepcopy(old)
    choice["recommended_option_id"] = choice["options"][0]["id"]
    assert not list(validate.iter_errors(choice))
    fact = copy.deepcopy(choice)
    fact["response_kind"] = "study_fact"
    assert list(validate.iter_errors(fact))
    for field in ("recommendation", "options"):
        invalid = copy.deepcopy(choice)
        del invalid[field]
        assert list(validate.iter_errors(invalid))


def test_unranked_choice_still_explains_why_no_recommendation_is_justified():
    catalog = Catalog(CATALOG)
    choice = read("examples/attention-setting-decision.example.json")
    choice["recommendation"] = "The intended population is unspecified, so neither target is preferred yet."
    assert "recommended_option_id" not in choice
    assert not catalog.validate_output("p3.attention_items", [choice])
    del choice["recommendation"]
    assert any(finding.code == "attention.recommendation"
               for finding in catalog.validate_output("p3.attention_items", [choice]))


def test_p2_authors_descriptive_framework_names_while_old_titles_remain_readable():
    title = read("schemas/method.schema.json")["properties"]["title"]
    description = title["description"]
    assert "framework, estimator or algorithm actually defined" in description
    assert "canonical definition and supplied sources" in description
    assert "do not coin a brand name or acronym" in description
    assert "historical records" in description

    p2 = read("contracts/phases/P2.json")
    stages = {stage["stage_id"]: stage for stage in p2["role_stages"]}
    for stage_id in ("p2.independent_proposals", "p2.supplied_method_proposals"):
        objective = stages[stage_id]["objective"]
        assert "In method.title, use a complete descriptive name" in objective
        assert "supported by method.mathematical_definition and the supplied literature" in objective
        assert "Do not coin a brand name or acronym" in objective
        assert "name an intended benefit as the mechanism" in objective
        assert "method identity and historical records" in objective

    # Naming is authoring guidance. It cannot reject or rewrite a retained title.
    validate = Draft202012Validator(title)
    for display_name in ("Existing method (OLD)", "Generalized additive model with a group-lasso penalty"):
        assert not list(validate.iter_errors(display_name))
    assert not list(validator("method.schema.json").iter_errors(read("examples/method.example.json")))


def test_scientific_workflow_and_report_permissions_survive_presentation_changes():
    p4 = read("contracts/phases/P4.json")
    assert [stage["roles"] for stage in p4["role_stages"]] == [
        ["data_analyst"], ["theorist"], ["research_lead"]]
    assert [len(stage["writes"]) for stage in p4["role_stages"]] == [8, 2, 5]
    analyst, theorist, lead = [stage["objective"] for stage in p4["role_stages"]]
    positions = [analyst.index(f"{step}. ") for step in range(1, 7)]
    assert positions == sorted(positions)
    assert "save_plan before the first numerical batch" in analyst
    assert "Bootstrap draws from one dataset are not independent simulation datasets" in analyst
    assert "Only a genuinely blocking missing researcher fact or choice" in theorist
    assert "do not alias or merge tests" in lead
    assert "cannot invent a denominator, calculate an interval or new contrast" in lead
    assert "Remove the All data/Synthetic/Checks selector" not in lead

    p5 = read("contracts/phases/P5.json")
    for stage in (p5["role_stages"][0], p5["role_stages"][2]):
        assert "Checked local expansions of supplied algebra or conditional reasoning are allowed" in stage["objective"]
        assert "p5.attention_items may be empty" in stage["objective"]
        assert "indispensable editorial choices" in stage["objective"]
    review = p5["role_stages"][1]["objective"]
    assert "Do not create attention_items.json or researcher-question.json" in review


def test_catalog_references_cover_distinct_functions_without_new_phase_outputs():
    folder = CATALOG / "references/research-presentation"
    assert {path.name for path in folder.glob("*.md")} == {
        "scientific-explanation.md", "claims-and-evidence.md", "summary.md",
        "tables-and-figures.md", "user-inquiry.md"}
    for n in range(1, 6):
        phase = read(f"contracts/phases/P{n}.json")
        assert "research_presentation_v1" in phase["capabilities"]
        for stage in phase["role_stages"]:
            assert "No rigid word cap" not in stage["objective"]
    inquiry = (folder / "user-inquiry.md").read_text(encoding="utf-8")
    assert "same answer settles both without reinterpretation" in inquiry
    assert "Entire choice inquiry | 180" in inquiry
    assert "Entire study-fact inquiry | 80" in inquiry
    assert "historical records have no inquiry word cap" in inquiry
    assert "Every choice supplies `recommendation`" in inquiry
    assert "otherwise omit the pointer" in inquiry
    assert "retain essential definitions and decisive conditions first" in inquiry
    assert "do not republish an unchanged question merely to add a marker or reorder it" in inquiry
