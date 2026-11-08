"""Notation enrichment retains the exact scientific source authored by the Lead."""
from dataclasses import asdict
import json
from urllib.parse import parse_qs, urlsplit

from httpx import ASGITransport, AsyncClient
import pytest

from model_forge_codex.domain import MemberRole, RunState, StageSpec
from model_forge_codex.notation import LEAD_FAMILIES
from model_forge_codex.records import ArtifactError, source_artifact_path
from model_forge_codex.research_sources import artifact_link
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, sha256_bytes, sha256_file, write_json_atomic
from model_forge_codex.validation import _check_artifacts
from test_notation_lifecycle import updates
from test_researcher_workbench_engine import record, script_scientific_run, workbench


@pytest.mark.parametrize("phase,family", [
    (phase, family) for phase, families in LEAD_FAMILIES.items() for family in families
])
async def test_shared_collector_preserves_authored_account_for_every_notation_family(workbench, monkeypatch, phase, family):
    engine, project, branch = workbench
    current = record(engine, branch, "run.authored-account", phase, "collection.fixture")
    directory = engine.run_dir(current.project_id, current.run_id)
    output_id = phase.lower() + "." + family
    index_id = phase.lower() + ".source_index"
    stage = StageSpec(stage_id=phase.lower() + ".source_collection", sequence=1, execution="serial",
                      roles=(MemberRole.RESEARCH_LEAD,), writes=(output_id, index_id))
    write_json_atomic(directory / "stage-plan.json", [asdict(stage)])
    write_json_atomic(directory / "basis.json", {})
    # This bounded seam tests the shared collector, including retained aliases,
    # rather than constructing eight unrelated scientific output envelopes.
    monkeypatch.setattr(engine, "_render_brief", lambda *args: "Collect the authored fixture account.")
    monkeypatch.setattr(engine, "_progressive_p4", lambda *args: False)
    account = {"scientific_definition": "The stated target and its qualifications remain unchanged.",
               "notation_updates": updates()}
    raw = json.dumps(account, ensure_ascii=False, indent=3).encode("utf-8") + b"\n"
    pointer = {"artifact_id": "artifact.authored-account", "uri": "artifact://authored-account",
               "path": family + ".json", "sha256": sha256_bytes(raw), "media_type": "application/json"}
    index = {"representations": [{"information_layer": "primary_artifact", "artifact": pointer}]}
    engine.bridge.script_thread("research_lead:PROJECT:trunk", [("ok", {
        family + ".json": raw.decode("utf-8"), "source_index.json": json.dumps(index)})])
    result = await engine._drive_member_turn(current, stage, MemberRole.RESEARCH_LEAD, directory)
    assert result.succeeded, result.diagnostic
    collected = directory / "outputs" / stage.stage_id
    authored = engine.member_workspace(current, stage.stage_id, MemberRole.RESEARCH_LEAD) / (family + ".json")
    retained = collected / "working/research_lead" / (family + ".json")
    formal = collected / (family + ".json")
    assert authored.read_bytes() == retained.read_bytes() == raw
    assert read_json(formal)["notation_snapshot"]["sha256"] == sha256_file(collected / "notation.json")
    assert sha256_file(formal) != pointer["sha256"] == sha256_file(retained)
    assert read_json(collected / "source_index.json") == index
    assert retained in result.output_paths
    seal = read_json(collected / "seal.json")["outputs"]
    assert seal[str(retained.relative_to(collected))]["sha256"] == pointer["sha256"]
    assert seal[formal.name]["sha256"] == sha256_file(formal)
    # The P5 candidate is also rewritten before notation retention. Preserve
    # original workspace bytes, not that intermediate derived report record.
    if family == "technical_report_candidate":
        assert "completion" in read_json(formal) and "completion" not in read_json(retained)

    findings = []
    _check_artifacts({index_id: index}, {index_id: collected}, findings)
    assert not findings
    current.state = RunState.PUBLISHED
    engine._save_run(current)
    reference = {"run_id": current.run_id, "stage_id": stage.stage_id, "branch": branch, "phase": phase}
    assert source_artifact_path(project, reference, pointer) == retained.resolve()
    link = artifact_link(project, reference, pointer)
    assert link["source_verified"]
    assert parse_qs(urlsplit(link["artifact_url"]).query)["path"] == ["working/research_lead/" + family + ".json"]

    retained.write_bytes(b"Changed scientific source bytes must not pass by filename.")
    findings = []
    _check_artifacts({index_id: index}, {index_id: collected}, findings)
    assert {finding.code for finding in findings} == {"artifact.digest_mismatch"}
    with pytest.raises(ArtifactError, match="could not be verified from the retained outputs"):
        source_artifact_path(project, reference, pointer)
    assert not artifact_link(project, reference, pointer).get("source_verified")


async def test_p4_authored_synthesis_reference_publishes_and_opens_without_mechanical_repair(workbench):
    engine, project, branch = workbench
    def cite_authored_synthesis(documents):
        raw = json.dumps(documents["p4.empirical_synthesis_candidate"]).encode("utf-8")
        documents["p4.empirical_index_candidate"]["representations"] = [{
            "information_layer": "primary_artifact", "artifact": {
                "artifact_id": "artifact.authored-synthesis", "uri": "artifact://p4/authored-synthesis",
                "path": "empirical_synthesis_candidate.json", "sha256": sha256_bytes(raw),
                "media_type": "application/json"}}]
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary", transform=cite_authored_synthesis)
    current = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await engine._tasks[current.run_id]
    final = engine.load_run(current.project_id, current.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert not final.findings_history and final.mechanical_repair_attempts == {}
    stage = engine._stages(current)[-1]
    collected = engine.run_dir(current.project_id, current.run_id) / "outputs" / stage.stage_id
    pointer = read_json(collected / "empirical_index_candidate.json")["representations"][0]["artifact"]
    reference = {"run_id": current.run_id, "stage_id": stage.stage_id, "branch": branch, "phase": "P4"}
    link = artifact_link(project, reference, pointer)
    retained = source_artifact_path(project, reference, pointer)
    authored = engine.member_workspace(current, stage.stage_id, MemberRole.RESEARCH_LEAD) / pointer["path"]
    assert retained.read_bytes() == authored.read_bytes()
    assert "notation_snapshot" not in read_json(retained)
    assert "notation_snapshot" in read_json(collected / pointer["path"])
    # Exercise the exact source URL that the researcher opens, including the
    # digest check after the original retained bytes are changed.
    app = create_app(data_root=engine.data_root, bridge=engine.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get(link["artifact_url"])
        assert response.status_code == 200 and response.content == authored.read_bytes()
        retained.write_bytes(b"Tampered retained synthesis.")
        assert (await client.get(link["artifact_url"])).status_code == 409
    findings = engine._validate_run_outputs(final, [stage])
    assert "artifact.digest_mismatch" in {finding.code for finding in findings}
