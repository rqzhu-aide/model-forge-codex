"""A downstream index keeps an explicitly cited earlier run's source identity."""
from pathlib import Path

import pytest

from model_forge_codex.domain import MemberRole
from model_forge_codex.methods import get_method
from model_forge_codex.storage import read_json, sha256_bytes
from test_researcher_workbench_engine import publish, workbench


@pytest.mark.parametrize("uri_prefix", ["", "outputs/"])
@pytest.mark.parametrize("publish_theory", [False, True])
async def test_p5_freezes_cross_run_index_sources_without_false_missing_warnings(workbench, monkeypatch, uri_prefix, publish_theory):
    engine, project, branch = workbench
    theory_run = "run.p3.original"
    index_run = "run.p4.index"
    identity = get_method(project, branch)["identity"]
    contents = {"theory_manuscript.md": b"The original qualified theory manuscript.",
                "theory_compact.json": b'{"scope": "bounded theory"}'}
    pointers = []
    for name, content in contents.items():
        retained = project / "runs" / theory_run / "outputs/p3.lead/working/research_lead" / name
        retained.parent.mkdir(parents=True, exist_ok=True)
        retained.write_bytes(content)
        pointers.append({"artifact_id": "artifact." + name, "path": name,
                         "sha256": sha256_bytes(content),
                         "uri": f"run://{theory_run}/{uri_prefix}p3.lead/{name}"})
        # A later index's same-name file cannot replace the cited source.
        decoy = project / "runs" / index_run / "outputs/p4.lead" / name
        decoy.parent.mkdir(parents=True, exist_ok=True)
        decoy.write_bytes(b"A different source under the same filename.")
    if publish_theory:
        publish(project, branch, "P3", {"complete_theory": {
            "method_identity": identity, "artifacts": pointers}}, theory_run)
    document = {"method_identity": identity, "source_artifacts": pointers}
    publish(project, branch, "P4", {family: document for family in
        ("empirical_evidence_index", "empirical_index_candidate")}, index_run)

    async def retain_only(*args):
        pass
    monkeypatch.setattr(engine, "_drive", retain_only)
    report = await engine.start_run("project.test", phase="P5", mode="p5.assembly", branch_id=branch)
    await engine._tasks[report.run_id]
    basis = read_json(engine.run_dir(report.project_id, report.run_id) / "basis.json")

    # The shared workbench seeds unrelated P2 pointers without their files.
    assert not [item for item in basis["unavailable_artifacts"] if item["family"] in
                ("complete_theory", "empirical_evidence_index", "empirical_index_candidate")]
    for pointer in pointers:
        copies = [entry for entry in basis["artifacts"] if entry["content_sha256"] == pointer["sha256"]]
        assert len(copies) == 1
        assert copies[0]["producing_run_id"] == theory_run
        assert Path(copies[0]["path"]).read_bytes() == contents[pointer["path"]]
    stage = engine._stages(report)[0]
    brief = engine._render_brief(report, stage, MemberRole.RESEARCH_LEAD,
                                 engine.member_workspace(report, stage.stage_id, MemberRole.RESEARCH_LEAD))
    assert not any(f"Artifact {name} is missing" in brief for name in contents)
    assert engine.bridge.turns == []


@pytest.mark.parametrize("source_state", ["missing", "changed"])
@pytest.mark.parametrize("uri_path", ["theory.md", "source-alias.md"])
async def test_p5_cross_run_source_still_requires_the_cited_runs_exact_bytes(workbench, monkeypatch, source_state, uri_path):
    engine, project, branch = workbench
    content = b"The original theory source."
    pointer = {"path": "theory.md", "sha256": sha256_bytes(content),
               "uri": f"run://run.p3.original/p3.lead/{uri_path}"}
    # Even an exact-byte copy in the index's run cannot stand in for a missing
    # or changed source in the run explicitly cited by the pointer.
    decoy = project / "runs/run.p4.index/outputs/p4.lead/theory.md"
    decoy.parent.mkdir(parents=True)
    decoy.write_bytes(content)
    original = project / "runs/run.p3.original/outputs/p3.lead/theory.md"
    original.parent.mkdir(parents=True)
    if source_state == "changed":
        original.write_bytes(b"Changed theory source.")
    publish(project, branch, "P4", {"empirical_evidence_index": {
        "method_identity": get_method(project, branch)["identity"], "source_artifact": pointer}}, "run.p4.index")

    async def retain_only(*args):
        pass
    monkeypatch.setattr(engine, "_drive", retain_only)
    report = await engine.start_run("project.test", phase="P5", mode="p5.assembly", branch_id=branch)
    await engine._tasks[report.run_id]
    basis = read_json(engine.run_dir(report.project_id, report.run_id) / "basis.json")

    assert not [item for item in basis["artifacts"] if item["content_sha256"] == pointer["sha256"]]
    unavailable = [item for item in basis["unavailable_artifacts"] if item["family"] == "empirical_evidence_index"]
    assert len(unavailable) == 1
    assert "source run run.p3.original" in unavailable[0]["reason"]
