"""Partial corrections reuse prerequisites without validating stale later outputs."""
import copy
import json

from model_forge_codex.domain import RunState
from model_forge_codex.records import current_records, read_generation, source_artifact_path
from test_direct_workflow import PID, complete, direct_engine, p1_documents, p2_documents, script


def files_under(directory):
    return {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob("*") if path.is_file()}


def response(**documents):
    return "ok", {family + ".json": json.dumps(document) for family, document in documents.items()}


async def failed_run(engine, phase, mode):
    engine._MAX_MECHANICAL_REPAIRS = 0  # Preserve the manual partial-correction scenario.
    record = await engine.start_run(PID, phase=phase, mode=mode, branch_id="trunk")
    await engine._tasks[record.run_id]
    result = engine.load_run(PID, record.run_id)
    assert result.state is RunState.FAILED
    return result


async def correct_and_publish(engine, record):
    await engine.correct(PID, record.run_id, "Correct only the identified artifact; preserve earlier submissions.")
    await engine._tasks[record.run_id]
    result = engine.load_run(PID, record.run_id)
    assert result.state is RunState.PUBLISHED, (result.terminal_reason, result.findings_history)
    return result


async def test_p1_synthesis_correction_keeps_discovery_sources_and_seals(direct_engine):
    engine, project = direct_engine
    documents = p1_documents()
    alias = copy.deepcopy(documents["p1.lead_literature"]["papers"][0])
    alias["entry_id"] = "entry.alias"
    alias["source"].update(source_id="citation.alias", record_id="record.citation.alias")
    documents["p1.theory_literature"]["papers"] = [alias]
    original = documents["p1.research_basis"]
    original["source_dispositions"] = [
        {"source_id": "citation.first", "status": "retain", "reason": "Relevant evidence."},
        {"source_id": "citation.alias", "status": "exclude", "reason": "Duplicate member alias."},
    ]
    script(engine, "P1", "p1.literature_update", documents)
    record = await failed_run(engine, "P1", "p1.literature_update")
    assert {finding["code"] for finding in record.findings_history[-1]} == {"output.cumulative_conflict"}
    directory = engine.run_dir(PID, record.run_id)
    discovery_before = files_under(directory / "outputs/p1.discovery")
    synthesis_before = files_under(directory / "outputs/p1.lead_synthesis")
    turns_before = len(engine.bridge.turns)
    corrected = copy.deepcopy(original)
    corrected["source_dispositions"] = corrected["source_dispositions"][:1]
    engine.bridge.script_thread("research_lead:PROJECT:trunk", [response(research_basis=corrected)])
    final = await correct_and_publish(engine, record)
    assert final.correction_scope == ["p1.research_basis"]
    assert len(engine.bridge.turns) == turns_before + 1
    assert files_under(directory / "outputs/p1.discovery") == discovery_before
    assert files_under(directory / "attempts/original/outputs/p1.discovery") == discovery_before
    assert files_under(directory / "attempts/original/outputs/p1.lead_synthesis") == synthesis_before
    phase = project / "branches/trunk/phases/p1"
    records = current_records(phase)
    published = read_generation(phase, "research_basis", records["research_basis"])
    assert set(published) == set(corrected) | {"notation_snapshot"}
    assert {key: value for key, value in published.items() if key != "notation_snapshot"} == corrected
    notation = published["notation_snapshot"]
    for artifact, name in ((notation, "notation.json"), (notation["markdown"], "notation.md")):
        assert source_artifact_path(project, records["research_basis"], artifact) == (
            directory / "outputs/p1.lead_synthesis" / name).resolve()
    library = read_generation(phase, "literature_library", records["literature_library"])
    assert len(library["sources"]) == 1
    assert len(library["sources"][0]["assessments"]) == 2


async def test_p2_catalog_correction_uses_unchanged_proposals_and_cross_audits(direct_engine):
    engine, project = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    documents, files = p2_documents(False)
    corrected = copy.deepcopy(documents["p2.catalog_assessment"])
    documents["p2.catalog_assessment"]["method_dispositions"].pop()
    script(engine, "P2", "p2.full_catalog", documents, files)
    record = await failed_run(engine, "P2", "p2.full_catalog")
    assert {finding["object_id"] for finding in record.findings_history[-1]} == {"p2.catalog_assessment"}
    stages = engine._stages(record)
    prior_stages = [stage for stage in stages if "p2.catalog_assessment" not in stage.writes]
    directory = engine.run_dir(PID, record.run_id)
    prior_bytes = {stage.stage_id: files_under(directory / "outputs" / stage.stage_id) for stage in prior_stages}
    turns_before = len(engine.bridge.turns)
    engine.bridge.script_thread("research_lead:PROJECT:trunk", [response(catalog_assessment=corrected)])
    final = await correct_and_publish(engine, record)
    assert final.correction_scope == ["p2.catalog_assessment"]
    assert len(engine.bridge.turns) == turns_before + 1
    for stage_id, original in prior_bytes.items():
        assert files_under(directory / "outputs" / stage_id) == original
    phase = project / "branches/trunk/phases/p2"
    records = current_records(phase)
    catalog = read_generation(phase, "method_catalog", records["method_catalog"])
    assert len(catalog["methods"]) == 3


async def test_p2_upstream_correction_refreshes_reviews_before_cross_artifact_validation(direct_engine):
    engine, project = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    documents, files = p2_documents(False)
    corrected = copy.deepcopy(documents)
    documents["p2.theory_proposal"].pop("proposed_evaluation_markdown")
    script(engine, "P2", "p2.full_catalog", documents, files)
    record = await failed_run(engine, "P2", "p2.full_catalog")
    assert {finding["object_id"] for finding in record.findings_history[-1]} == {"p2.theory_proposal"}
    revised_id = "proposal.theory.revised"
    corrected["p2.theory_proposal"]["proposal_id"] = revised_id
    corrected["p2.empirical_review"]["assessments"][0]["proposal_id"] = revised_id
    corrected["p2.catalog_assessment"]["method_dispositions"][0]["proposal_id"] = revised_id
    option = corrected["p2.catalog_assessment"]["modification_options"][0]
    option["applies_to"] = revised_id
    option["option_id"] = "mod." + revised_id + ".refinement"
    engine.bridge.script_thread("theorist:P2:trunk", [
        response(theory_proposal=corrected["p2.theory_proposal"]),
        response(theory_review=corrected["p2.theory_review"]),
    ])
    engine.bridge.script_thread("data_analyst:P2:trunk", [response(empirical_review=corrected["p2.empirical_review"])])
    engine.bridge.script_thread("research_lead:PROJECT:trunk", [response(catalog_assessment=corrected["p2.catalog_assessment"])])
    turns_before = len(engine.bridge.turns)
    final = await correct_and_publish(engine, record)
    assert final.correction_scope == ["p2.theory_proposal"]
    assert len(engine.bridge.turns) == turns_before + 4
    phase = project / "branches/trunk/phases/p2"
    records = current_records(phase)
    review = read_generation(phase, "empirical_review", records["empirical_review"])
    assert review["assessments"][0]["proposal_id"] == revised_id
