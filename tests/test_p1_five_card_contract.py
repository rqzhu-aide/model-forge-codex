"""P1 brief settings and source-specific papers reach frozen briefs unchanged."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.p1_science import validate_p1_science
from model_forge_codex.storage import read_json, write_json_atomic
from test_direct_workflow import p1_documents
from test_draft_validation import draft_engine, run


ROOT = Path(__file__).resolve().parents[1]


def without_descriptions(value):
    if isinstance(value, dict):
        return {key: without_descriptions(item) for key, item in value.items()
                if key != "description"}
    if isinstance(value, list):
        return [without_descriptions(item) for item in value]
    return value


@pytest.mark.parametrize("schema,expected", [
    ("research-basis.schema.json", "7ff1eeb514c34e096fcdd440d7e3b775e5993a15b1379e767a9276b61a3ed88a"),
    ("literature-findings.schema.json", "2dbced4b4a6f9e677ddb7bfaa31e97f08ec1fcd4265b499c4e492ae37ddcc1a6"),
    ("attention-item.schema.json", "b9d974db8d86bfac39d37c80a07b131f0d2feaf7d081236d8d2fee039e4e1823"),
])
def test_five_card_fields_survive_explicit_decision_contract_extensions(schema, expected):
    document = without_descriptions(read_json(ROOT / "contracts/schemas" / schema))
    if schema == "research-basis.schema.json":
        # Shared notation extends the existing Lead record, retaining every
        # prior scientific field and keeping both new fields optional on read.
        for field in ("notation_updates", "notation_snapshot"):
            assert field not in document["required"]
            del document["properties"][field]
    elif schema == "attention-item.schema.json":
        properties = document["properties"]
        additions = {"decision_priority", "response_kind", "options", "recommendation", "recommended_option_id"}
        assert not additions.intersection(document["required"])
        assert properties["decision_priority"]["enum"] == ["interpretation", "inference", "data", "resources"]
        assert properties["response_kind"]["enum"] == ["choice", "study_fact"]
        assert properties["options"]["type"] == "array"
        assert properties["recommendation"]["type"] == "string"
        assert properties["recommended_option_id"]["type"] == "string"
        recommendation_rule = document["allOf"].pop()
        assert recommendation_rule == {
            "if": {"required": ["recommended_option_id"]},
            "then": {"required": ["response_kind", "options", "recommendation"],
                     "properties": {"response_kind": {"const": "choice"}}}}
        for field in additions:
            del properties[field]
    elif schema == "literature-findings.schema.json":
        questions = document["properties"]["proposed_questions"]["items"]
        assert questions["required"] == ["question", "context_markdown", "answer_consequences_markdown", "source_refs"]
        # The old rationale remains readable, but new questions need not repeat it.
        assert questions["properties"]["why_it_matters_markdown"]["type"] == "string"
        questions["required"].insert(2, "why_it_matters_markdown")
    # Keep the prior five-card structure exactly, apart from the changes above.
    shape = json.dumps(document, sort_keys=True).encode()
    assert hashlib.sha256(shape).hexdigest() == expected


def test_frozen_p1_briefs_deliver_field_ownership_and_preserve_independent_roles(draft_engine):
    engine = draft_engine
    candidate, stages, _ = run(engine, "P1", "p1.literature_update")
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    shutil.copytree(engine.project_dir(candidate.project_id) / "contracts", directory / "contracts")
    phase = read_json(directory / "contracts/contracts/phases/P1.json")
    assert phase["contract_version"] == "3.9.1"
    assert [(stage.execution, len(stage.roles)) for stage in stages] == [("parallel", 3), ("serial", 1)]
    assert set(phase["role_stages"][0]["writes"]) == {
        "p1.lead_literature", "p1.theory_literature", "p1.empirical_literature",
    }
    assert phase["role_stages"][1]["writes"] == ["p1.research_basis"]

    # A later project edit must not replace any of the four frozen responsibilities.
    later = deepcopy(phase)
    for stage in later["role_stages"]:
        stage["objective"] = "LATER_PROJECT_OBJECTIVE"
        stage["role_objectives"] = {role: "LATER_ROLE_DUTY" for role in stage["roles"]}
    write_json_atomic(engine.project_dir(candidate.project_id) / "contracts/contracts/phases/P1.json", later)
    frozen_stages = engine._stages(candidate)
    assert len(frozen_stages) == 2
    discovery_briefs = []
    for stage in frozen_stages:
        for role in stage.roles:
            brief = engine._render_brief(candidate, stage, role,
                                        engine.member_workspace(candidate, stage.stage_id, role))
            assert stage.objective in brief
            assert phase["role_stages"][stage.sequence - 1]["role_objectives"][role.value] in brief
            assert "LATER_PROJECT_OBJECTIVE" not in brief and "LATER_ROLE_DUTY" not in brief
            assert "six P1 sections" not in brief
            assert "The research setting and landscape.summary_markdown explain" not in brief
            if stage.stage_id == "p1.discovery":
                assert "Produce exactly your owned literature collection" in brief
                assert "Do not author the setting, cross-paper findings or run history" in brief
                assert "honest reading_extent" in brief
                assert "concise, connected methodology-style prose" in brief
                assert "central mechanism or estimation procedure" in brief
                assert "this source's actual model, formulation or method" in brief
                assert "visible summary must be understandable without opening formulation details" in brief
                assert "must not be the only place containing the method's defining mathematics" in brief
                assert "Completeness takes priority over brevity" in brief
                discovery_briefs.append(brief)
            else:
                assert "brief, connected description of the study problem" in brief
                assert "notation needed to understand them" in brief
                assert "Detailed formulation of each proposed project method belongs in Phase 2" in brief
                assert "do not require a full model specification" in brief
                assert "rather than a generic family account or notation list" in brief
                assert "Avoiding a particular model family does not justify omitting" not in brief
                assert "without a word, sentence, paragraph or equation quota" in brief
                assert "Distinguish the target from a particular estimating procedure" in brief
                assert "A conditional predictive quantity, association and intervention effect are different targets" in brief
                assert "methodological synthesis across papers" in brief
                assert "central mechanism or estimation strategy" in brief
                assert "visible account must remain methodologically understandable without opening details" in brief
                assert "Preserve an unresolved consequential target preference symbolically" in brief
                assert "do not silently narrow the target or pretend an identification assumption is established" in brief
                assert "The Lead selects routine details determined by the stated goal and scientific judgment" in brief
                inquiry = (directory / "contracts/references/research-presentation/user-inquiry.md").read_text(encoding="utf-8")
                assert inquiry in brief
                assert "Routine methodology, proofs, implementation, diagnostics and presentation belong to the team" in inquiry
                assert "one paragraph per brief field" not in brief
                assert "Default common_assumptions to empty" in brief
                assert "No additional P2-specific preparation is identified." in brief
                assert "exact original role/family/run/entry/entry_sha256" in brief
                assert "effective whole-entry digest" in brief
    assert len(discovery_briefs) == 3
    assert "Locate relevant formulations" in discovery_briefs[0]
    assert "source-reported guarantees" in discovery_briefs[1]
    assert "computational demands" in discovery_briefs[2]
    assert engine.bridge.turns == []


def test_required_containers_may_be_empty_without_inventing_a_landscape():
    catalog = Catalog(ROOT / "contracts")
    documents = p1_documents()
    basis = documents["p1.research_basis"]
    basis["notation_updates"] = {"incoming_sources": [], "entries": [], "retirements": [], "correction_dispositions": []}
    basis["research_setting"]["component_interpretations"] = []
    for field in ("topics", "frameworks", "variants", "relationships", "algorithm_families",
                  "overview_item_ids", "common_assumptions", "citation_refs"):
        basis["landscape"][field] = []
    basis["landscape"]["summary_markdown"] = "No supported cross-paper formulation is established by this fixture."
    basis["coverage_limits"] = []
    basis["entry_corrections"] = []
    basis["scientific_review"] = {"scope_markdown": "Structural fixture; no primary-source checks claimed.",
                                  "findings": [], "limitations": []}
    basis["phase2_preparation"]["instructions_markdown"] = "No additional P2-specific preparation is identified."
    assert catalog.validate_output("p1.research_basis", basis) == []
    assert validate_p1_science({key.removeprefix("p1."): value for key, value in documents.items()},
                               run_id="run.concise.fixture") == []
    for field in ("topics", "frameworks", "variants", "relationships", "algorithm_families",
                  "overview_item_ids", "common_assumptions", "citation_refs"):
        missing = deepcopy(basis)
        del missing["landscape"][field]
        assert catalog.validate_output("p1.research_basis", missing)
    blank = deepcopy(basis)
    blank["phase2_preparation"]["instructions_markdown"] = ""
    assert catalog.validate_output("p1.research_basis", blank)


def test_concise_examples_retain_original_and_effective_reference_digests():
    collection = read_json(ROOT / "contracts/examples/literature-findings.example.json")
    basis = read_json(ROOT / "contracts/examples/research-basis.example.json")
    entry = collection["papers"][0]

    def digest(document):
        return hashlib.sha256(json.dumps(document, ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":")).encode("utf-8")).hexdigest()

    correction = basis["entry_corrections"][0]
    assert correction["target"]["entry_sha256"] == digest(entry)
    assert basis["scientific_review"]["findings"][0]["target"] == correction["target"]
    effective = {**entry, **correction["changes"]}
    assert basis["landscape"]["citation_refs"][0]["entry_ref"]["entry_sha256"] == digest(effective)
    assert basis["landscape"]["common_assumptions"] == []
    assert basis["phase2_preparation"]["instructions_markdown"] == "No additional P2-specific preparation is identified."
