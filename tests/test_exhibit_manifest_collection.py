"""Exhibit relocation preserves the exact manifest cited by its author."""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.records import ArtifactError, source_artifact_path
from model_forge_codex.research_sources import artifact_link
from model_forge_codex.storage import read_json, sha256_bytes, sha256_file
from test_researcher_workbench_engine import script_scientific_run, workbench


async def test_cited_manifest_survives_collection_source_opening_and_p5_freezing(workbench, monkeypatch):
    engine, project, branch = workbench
    def cite_manifest(documents):
        manifest = json.dumps(documents["p4.exhibits"]).encode()
        documents["p4.analyst_synthesis"]["representations"] = [{
            "information_layer": "compact_decision_view", "artifact": {
                "artifact_id": "artifact.exhibits.manifest", "uri": "artifact://p4/exhibits.json",
                "path": "exhibits.json", "sha256": sha256_bytes(manifest), "media_type": "application/json"}}]
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary", transform=cite_manifest)
    record = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await engine._tasks[record.run_id]
    final = engine.load_run("project.test", record.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert not final.findings_history and final.mechanical_repair_attempts == {}

    directory = engine.run_dir(record.project_id, record.run_id)
    stage = engine._stages(record)[0]
    collected = directory / "outputs" / stage.stage_id
    workspace = engine.member_workspace(record, stage.stage_id, MemberRole.DATA_ANALYST)
    authored = workspace / "exhibits.json"
    retained = collected / "working/data_analyst/exhibits.json"
    pointer = read_json(collected / "analyst_synthesis.json")["representations"][0]["artifact"]
    assert retained.read_bytes() == authored.read_bytes()
    assert sha256_file(retained) == pointer["sha256"] != sha256_file(collected / "exhibits.json")
    assert read_json(collected / "exhibits.json")[0]["artifact_path"].startswith("exhibit-artifacts/")
    assert read_json(collected / "seal.json")["outputs"][str(retained.relative_to(collected))]["sha256"] == pointer["sha256"]
    reference = {"run_id": record.run_id, "stage_id": stage.stage_id, "branch": branch, "phase": "P4"}
    # The direct filename contains relocated bytes; resolution must select the
    # matching retained bytes rather than accepting that same-name collision.
    assert source_artifact_path(project, reference, pointer) == retained.resolve()
    link = artifact_link(project, reference, pointer)
    assert link["source_verified"]
    assert parse_qs(urlsplit(link["artifact_url"]).query)["path"] == ["working/data_analyst/exhibits.json"]
    findings = engine._validate_run_outputs(final, [stage])
    assert not [f for f in findings if f.blocks_publication], [(f.code, f.message) for f in findings]

    # Freeze real P5 inputs through authorization, without dispatching a turn.
    async def retain_only(*args):
        pass
    monkeypatch.setattr(engine, "_drive", retain_only)
    report = await engine.start_run("project.test", phase="P5", mode="p5.assembly", branch_id=branch)
    await engine._tasks[report.run_id]
    basis = read_json(engine.run_dir(report.project_id, report.run_id) / "basis.json")
    copied = next(item for item in basis["artifacts"] if item.get("artifact_id") == pointer["artifact_id"])
    assert copied["original_path"] == "exhibits.json" and copied["content_sha256"] == pointer["sha256"]
    assert Path(copied["path"]).read_bytes() == authored.read_bytes()

    retained.write_bytes(b"Changed retained bytes must not resolve by filename alone.")
    with pytest.raises(ArtifactError, match="could not be verified from the retained outputs"):
        source_artifact_path(project, reference, pointer)
    assert not artifact_link(project, reference, pointer).get("source_verified")
    assert "artifact.digest_mismatch" in {f.code for f in engine._validate_run_outputs(final, [stage])}
    assert sha256_file(Path(copied["path"])) == pointer["sha256"]
