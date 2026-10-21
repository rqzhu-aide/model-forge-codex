"""P1 lead context stays selective and corrected science reaches the same readers."""
from copy import deepcopy
import json
from pathlib import Path

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.literature import _digest, build_library
from model_forge_codex.literature_context import write_literature_context
from model_forge_codex.p1_science import literature_entries
from model_forge_codex.records import current_records, read_generation
from model_forge_codex.research import artifacts_view
from model_forge_codex.storage import read_json
from test_direct_workflow import PID, complete, direct_engine, p1_documents, p2_documents, script
from test_draft_validation import draft_engine, run as draft_run, write_outputs, check as draft_check


def indexed_entries(index_path):
    index = read_json(index_path)
    return [entry for page in index["pages"]
            for entry in read_json(index_path.parent / page["path"])["entries"]]


def navigation_indexes(directory):
    return list((directory / "inputs/literature-context").glob("*/*/*/index.json"))


def test_new_p1_rejects_legacy_output_in_immediate_member_check(draft_engine):
    record, stages, _ = draft_run(draft_engine, "P1", "p1.literature_update")
    document = p1_documents()["p1.lead_literature"]
    document["schema_version"] = "1.0.0"
    for entry in document["papers"]:
        entry.pop("reading_extent")
    workspace = draft_engine.member_workspace(record, stages[0].stage_id, MemberRole.RESEARCH_LEAD)
    write_outputs(workspace, {"p1.lead_literature": document})
    result = draft_check(draft_engine, record, stages[0], MemberRole.RESEARCH_LEAD)
    assert result["status"] == "failed"
    assert any(item["code"] == "schema.const" and item["json_pointer"] == "/schema_version"
               for item in result["findings"])
    assert draft_engine.bridge.turns == []


def test_navigation_pages_keep_exact_entry_math_and_deduplicate_sources(tmp_path):
    documents = {key.removeprefix("p1."): value for key, value in p1_documents(tuple(f"citation.{i}" for i in range(45))).items()}
    documents.pop("research_basis")
    documents["theory_literature"]["papers"] = [deepcopy(documents["lead_literature"]["papers"][0])]
    sources = [entry["source"] for collection in documents.values() for entry in collection["papers"]]
    library = build_library(None, sources, run_id="run.index")
    assessments = literature_entries(documents, None, run_id="run.index")
    original = deepcopy(documents)
    index_path = write_literature_context(tmp_path, library, assessments, documents, run_id="run.index")
    index = read_json(index_path)
    assert index["unique_source_count"] == 45 and index["assessment_count"] == 46
    assert len(index["pages"]) == 2
    rows = indexed_entries(index_path)
    assert all("formulation_markdown" not in row for row in rows)
    assert len({row["entry_path"] for row in rows}) == 46
    for row in rows:
        detail = read_json(index_path.parent / row["entry_path"])
        assert detail["reference"]["entry_sha256"] == _digest(detail["entry"])
        assert detail["entry"]["formulation_markdown"] == documents["lead_literature"]["papers"][0]["formulation_markdown"]
    assert documents == original
    assert write_literature_context(tmp_path, library, assessments, documents, run_id="run.index") == index_path


def test_navigation_retains_current_source_status_separately_from_original_citation(tmp_path):
    from test_p1_science import with_correction, library_for
    from test_literature import source

    documents, _ = with_correction()
    documents["research_basis"]["source_dispositions"] = [
        {"source_id": "citation.first", "status": "exclude", "reason": "Outside the selected setting."}]
    library = library_for(documents)
    library = build_library(library, [source(run_id="run.withdrawal", source_status="retracted",
                                            status_reason="Recorded publisher retraction.")], run_id="run.withdrawal")
    assessments = literature_entries({}, library, run_id="run.consumer")
    index = write_literature_context(tmp_path, library, assessments, {}, run_id="run.consumer")
    for row in indexed_entries(index):
        assert row["source_status"] == "retracted"
        assert row["status_reason"] == "Recorded publisher retraction."
        assert row["landscape_status"] == "exclude"
        detail = read_json(index.parent / row["entry_path"])
        assert detail["current_source"]["landscape_reason"] == "Outside the selected setting."
        assert detail["entry"]["source"]["source_status"] == "active"


def test_navigation_history_preserves_earlier_lead_revision_attribution(tmp_path):
    from test_p1_science import with_correction, library_for, correction
    from test_direct_artifacts import basis
    from model_forge_codex.p1_science import entry_reference

    documents, original = with_correction()
    first = library_for(documents)
    retained = next(item for item in literature_entries({}, first, run_id="run.second") if item["role"] == "theorist")
    second_change = correction(entry_reference(retained), "correction.second")
    second_change["changes"] = {"reading_extent": "Read the source's complete problem definition."}
    second = library_for({"research_basis": basis(entry_corrections=[second_change])}, first, "run.second")
    assessments = literature_entries({}, second, run_id="run.consumer")
    index = write_literature_context(tmp_path, second, assessments, {}, run_id="run.consumer")
    row = next(item for item in indexed_entries(index) if item["reference"]["role"] == "theorist")
    current = read_json(index.parent / row["entry_path"])
    previous = read_json(index.parent / current["earlier_versions"][0]["entry_path"])
    assert previous["lead_revision"]["role"] == "research_lead"
    assert previous["lead_revision"]["correction_id"] == "correction.budget"
    assert previous["lead_revision"]["reason_markdown"] == documents["research_basis"]["entry_corrections"][0]["reason_markdown"]
    assert previous["entry"] == retained["entry"]
    assert read_json(index.parent / current["earlier_versions"][1]["entry_path"])["entry"] == original["entry"]


async def test_discovery_is_independent_and_lead_opens_indexed_records(direct_engine):
    engine, project = direct_engine
    documents = p1_documents()
    marker = "SPECIFIC_PAPER_MATHEMATICS_" + ("x" * 25000)
    documents["p1.lead_literature"]["papers"][0]["explanation_markdown"] = marker
    script(engine, "P1", "p1.literature_update", documents)
    final = await complete(engine, "P1", "p1.literature_update")
    directory = engine.run_dir(PID, final.run_id)
    assert len(engine.bridge.turns) == 4
    briefs = {path.name: path.read_text(encoding="utf-8") for path in (directory / "briefs").glob("*.md")}
    for name, text in briefs.items():
        assert marker not in text
        if "discovery" in name:
            assert "Your scientific responsibility" in text
    assert "Literature navigation" in briefs["p1.lead_synthesis.research_lead.md"]
    indexes = navigation_indexes(directory)
    assert len(indexes) == 4
    for index_path in indexes:
        count = read_json(index_path)["assessment_count"]
        assert count == (1 if "p1.lead_synthesis" in index_path.parts else 0)
    lead_index = next(path for path in indexes if "p1.lead_synthesis" in path.parts)
    row = indexed_entries(lead_index)[0]
    assert read_json(lead_index.parent / row["entry_path"])["entry"]["explanation_markdown"] == marker


async def test_lead_corrects_theorist_in_one_turn_and_ui_and_p2_use_revision(direct_engine):
    engine, project = direct_engine
    documents = p1_documents()
    original = deepcopy(documents["p1.lead_literature"]["papers"][0])
    original["entry_id"] = "entry.theory"
    original["formulation_markdown"] = r"$$J(\pi)=\mathbb E_\pi[\sum_{t=0}^{T}R_t].$$"
    documents["p1.theory_literature"]["papers"] = [original]
    repaired_math = r"$$J_\gamma(\pi)=\mathbb E_\pi\!\left[\sum_{t=0}^{\infty}\gamma^tR_t\right],\quad 0<\gamma<1.$$"

    class ScientificLead(FakeCodexBridge):
        async def run_turn(self, thread_id, **kwargs):
            if kwargs["workspace"].name == "p1.lead_synthesis":
                run_id = kwargs["brief_path"].parent.parent.name
                target = {"role": "theorist", "family": "theory_literature", "run_id": run_id,
                          "entry_id": "entry.theory", "entry_sha256": _digest(original)}
                basis = deepcopy(documents["p1.research_basis"])
                basis["entry_corrections"] = [{"correction_id": "correction.discount", "target": target,
                                               "changes": {"formulation_markdown": repaired_math},
                                               "reason_markdown": "The source defines discounted infinite-horizon reward.",
                                               "evidence_locations": ["Definition 1"]}]
                basis["scientific_review"] = {"scope_markdown": "Checked the theorist's criterion against Definition 1.",
                    "findings": [{"finding_id": "finding.discount", "target": target, "status": "corrected",
                                  "assessment_markdown": "Restored the source's discount and infinite horizon.",
                                  "evidence_locations": ["Definition 1"]}], "limitations": ["No full proof verification."]}
                self.script[thread_id][0] = ("ok", {"research_basis.json": json.dumps(basis)})
            return await super().run_turn(thread_id, **kwargs)

    engine.bridge = ScientificLead()
    script(engine, "P1", "p1.literature_update", documents)
    final = await complete(engine, "P1", "p1.literature_update")
    assert len(engine.bridge.turns) == 4 and final.mechanical_repair_attempts == {}
    phase_dir = project / "branches/trunk/phases/p1"
    pointers = current_records(phase_dir)
    assert read_generation(phase_dir, "theory_literature", pointers["theory_literature"])["papers"][0] == original
    library = read_generation(phase_dir, "literature_library", pointers["literature_library"])
    entry = next(item for item in library["sources"][0]["assessments"] if item["role"] == "theorist")
    assert entry["entry"]["formulation_markdown"] == repaired_math
    assert entry["lead_revision"]["role"] == "research_lead"
    assert entry["assessment_history"][0]["entry"] == original
    ui_source = artifacts_view(project)["literature_libraries"][0]["sources"][0]
    ui_entry = next(item for item in ui_source["cards"] if item["role"] == "theorist")
    assert ui_entry["formulation_markdown"] == repaired_math
    assert len(ui_source["cards"]) == 2
    outputs, files = p2_documents(False)
    script(engine, "P2", "p2.full_catalog", outputs, files)
    p2 = await complete(engine, "P2", "p2.full_catalog")
    indexes = navigation_indexes(engine.run_dir(PID, p2.run_id))
    assert indexes
    for index_path in indexes:
        row = next(item for item in indexed_entries(index_path) if item["reference"]["role"] == "theorist")
        current = read_json(index_path.parent / row["entry_path"])
        assert current["entry"]["formulation_markdown"] == repaired_math
        historical = read_json(index_path.parent / current["earlier_versions"][0]["entry_path"])
        assert historical["entry"] == original
        assert historical["reference"]["entry_sha256"] == _digest(original)
    for path in (engine.run_dir(PID, p2.run_id) / "briefs").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "Literature navigation" in text
        assert str(phase_dir / "theory_literature") not in text
