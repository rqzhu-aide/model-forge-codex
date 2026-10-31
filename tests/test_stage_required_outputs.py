"""A completed SDK turn must deliver its outputs before the next stage starts."""
import json

import pytest

from model_forge_codex.domain import RunState
from model_forge_codex.records import current_records, read_generation, source_artifact_path
from model_forge_codex.runs import RunError
from model_forge_codex.storage import read_json
from test_direct_workflow import PID, direct_engine, p1_documents, script


LEAD_KEY = "research_lead:PROJECT:trunk"


def response(**documents):
    return "ok", {name + ".json": json.dumps(document) for name, document in documents.items()}


async def incomplete_discovery(engine, documents):
    engine._MAX_MECHANICAL_REPAIRS = 0  # Isolate the explicitly authorized correction path.
    script(engine, "P1", "p1.literature_update", documents)
    # The provider reports a completed turn, but the lead writes no deliverable.
    engine.bridge.script_thread(LEAD_KEY, [("ok", {})])
    record = await engine.start_run(PID, phase="P1", mode="p1.literature_update", branch_id="trunk")
    await engine._tasks[record.run_id]
    return engine.load_run(PID, record.run_id)


async def test_missing_discovery_output_stops_synthesis_and_correction_preserves_siblings(direct_engine):
    engine, project = direct_engine
    documents = p1_documents()
    failed = await incomplete_discovery(engine, documents)
    directory = engine.run_dir(PID, failed.run_id)
    discovery = directory / "outputs/p1.discovery"

    assert failed.state is RunState.FAILED
    assert failed.stage_states == {"p1.discovery": "failed", "p1.lead_synthesis": "pending"}
    assert [(item["code"], item["object_id"]) for item in failed.findings_history[-1]] == [
        ("output.required_missing", "p1.lead_literature")
    ]
    assert "p1.lead_literature" in failed.terminal_reason
    assert failed.usage["input_tokens"] == 300
    assert failed.usage["output_tokens"] == 150
    assert len(engine.bridge.turns) == 3
    assert not (directory / "briefs/p1.lead_synthesis.research_lead.md").exists()
    assert not (discovery / "lead_literature.json").exists()
    siblings = {name: (discovery / name).read_bytes()
                for name in ("theory_literature.json", "empirical_literature.json")}
    assert engine.correction_block_reason(failed) is None

    engine.bridge.script_thread(LEAD_KEY, [
        response(lead_literature=documents["p1.lead_literature"]),
        response(research_basis=documents["p1.research_basis"]),
    ])
    await engine.correct(PID, failed.run_id, "Finish the missing lead collection; preserve the other submissions.")
    await engine._tasks[failed.run_id]
    final = engine.load_run(PID, failed.run_id)

    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert final.correction_attempts == 1
    assert final.correction_scope == ["p1.lead_literature"]
    assert final.stage_states == {"p1.discovery": "succeeded", "p1.lead_synthesis": "succeeded"}
    assert len(engine.bridge.turns) == 5
    for name, original in siblings.items():
        assert (discovery / name).read_bytes() == original
        assert (directory / "attempts/original/outputs/p1.discovery" / name).read_bytes() == original
    synthesis = read_json(directory / "outputs/p1.lead_synthesis/research_basis.json")
    authored = documents["p1.research_basis"]
    assert set(synthesis) == set(authored) | {"notation_snapshot"}
    assert {key: value for key, value in synthesis.items() if key != "notation_snapshot"} == authored
    phase = project / "branches/trunk/phases/p1"
    records = current_records(phase)
    assert read_generation(phase, "research_basis", records["research_basis"]) == synthesis
    notation = synthesis["notation_snapshot"]
    for artifact, name in ((notation, "notation.json"), (notation["markdown"], "notation.md")):
        assert source_artifact_path(project, records["research_basis"], artifact) == (
            directory / "outputs/p1.lead_synthesis" / name).resolve()


async def test_correction_that_still_omits_output_never_starts_synthesis(direct_engine):
    engine, _ = direct_engine
    failed = await incomplete_discovery(engine, p1_documents())
    engine.bridge.script_thread(LEAD_KEY, [("ok", {})])
    await engine.correct(PID, failed.run_id, "Produce the missing collection.")
    await engine._tasks[failed.run_id]
    final = engine.load_run(PID, failed.run_id)

    assert final.state is RunState.FAILED
    assert final.stage_states == {"p1.discovery": "failed", "p1.lead_synthesis": "pending"}
    assert [(item["code"], item["object_id"]) for item in final.findings_history[-1]] == [
        ("output.required_missing", "p1.lead_literature")
    ]
    assert len(engine.bridge.turns) == 4
    directory = engine.run_dir(PID, failed.run_id)
    assert not (directory / "briefs/p1.lead_synthesis.research_lead.md").exists()
    with pytest.raises(RunError, match="already spent"):
        await engine.correct(PID, failed.run_id)
