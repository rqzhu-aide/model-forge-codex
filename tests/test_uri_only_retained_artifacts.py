"""Historical frozen inputs remain exact report dependencies across retries."""
from copy import deepcopy
from pathlib import Path

import pytest

from model_forge_codex.domain import RunState
from model_forge_codex.methods import get_method
from model_forge_codex.records import ArtifactError, source_artifact_path
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from model_forge_codex.technical_reports import derive_report_completion, validate_technical_report
from test_researcher_workbench_engine import publish, workbench
from test_technical_reports import report_case


@pytest.mark.parametrize("location", ["inputs/artifacts/source.json", "outputs/p4.analyst/code.py", "p4.analyst/code.py"])
def test_uri_only_source_resolves_the_exact_retained_location(tmp_path, location):
    relative = location if location.startswith(("inputs/", "outputs/")) else "outputs/" + location
    source = tmp_path / "runs/run.original" / relative
    source.parent.mkdir(parents=True)
    source.write_bytes(b"Exact historical bytes.")
    pointer = {"uri": "run://run.original/" + location, "sha256": sha256_file(source)}
    assert source_artifact_path(tmp_path, {"run_id": "run.original"}, pointer) == source.resolve()
    source.write_bytes(b"Changed historical bytes.")
    with pytest.raises(ArtifactError):
        source_artifact_path(tmp_path, {"run_id": "run.original"}, pointer)


@pytest.mark.parametrize("location", [
    "inputs/artifacts/../source.json", "inputs/artifacts/./source.json", "inputs/artifacts//source.json",
    "inputs/notation.json", "inputs/artifacts/nested/source.json", "outputs/p4.analyst/../p4.lead/code.py",
])
def test_uri_only_sources_reject_unsafe_or_nonartifact_inputs(tmp_path, location):
    with pytest.raises(ArtifactError):
        source_artifact_path(tmp_path, {"run_id": "run.original"},
                             {"uri": "run://run.original/" + location, "sha256": "a" * 64})


@pytest.mark.parametrize("change", ["run", "path", "alternate_path", "symlink"])
def test_frozen_artifact_input_does_not_substitute_other_sources(tmp_path, change):
    source = tmp_path / "runs/run.original/inputs/artifacts/source.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"Exact historical bytes.")
    pointer = {"uri": "run://run.original/inputs/artifacts/source.json", "sha256": sha256_file(source)}
    if change == "run":
        pointer["uri"] = "run://run.other/inputs/artifacts/source.json"
    elif change == "path":
        pointer["path"] = "inputs/artifacts/other.json"
    elif change == "alternate_path":
        pointer.update(path="inputs/artifacts/source.json", artifact_path="inputs/artifacts/other.json")
    else:
        foreign = tmp_path / "foreign.json"
        foreign.write_bytes(source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(foreign)
        except OSError:
            pytest.skip("Symlinks are unavailable for this account")
    with pytest.raises(ArtifactError):
        source_artifact_path(tmp_path, {"run_id": "run.original"}, pointer)


async def test_report_capture_and_failed_conversation_retry_keep_historical_input_dependencies(workbench, report_case, monkeypatch):
    engine, project, branch = workbench
    identity = get_method(project, branch)["identity"]
    historical = project / "runs/run.p4.original/inputs/artifacts/prior.json"
    historical.parent.mkdir(parents=True)
    historical.write_bytes(b'{"scope":"Historical provenance, not new numerical evidence."}')
    prior = {"artifact_id": "artifact.prior", "uri": "run://run.p4.original/inputs/artifacts/prior.json",
             "sha256": sha256_file(historical), "media_type": "application/json"}
    code = project / "runs/run.p4.latest/outputs/p4.analyst/implementation.py"
    code.parent.mkdir(parents=True)
    code.write_bytes(b"def estimate(x):\n    return sum(x) / len(x)\n")
    implementation = {"record_type": "implementation_record", "method_identity": identity,
        "implementation_summary": {"environment": "Shared Python"}, "prior_source": prior,
        "code": {"artifact_id": "artifact.code", "uri": "run://run.p4.latest/outputs/p4.analyst/implementation.py",
                 "sha256": sha256_file(code), "media_type": "text/plain"}}
    evidence = {"evidence_kind": "simulation", "method_identity": identity,
                "applicability_at_creation": {"method_match": "exact"}, "metrics": {"estimate": 0.12}}
    publish(project, branch, "P4", {"implementation_record": implementation, "evidence": evidence}, "run.p4.latest")

    async def retain_only(*args):
        pass
    monkeypatch.setattr(engine, "_drive", retain_only)
    current = await engine.start_run("project.test", phase="P5", mode="p5.assembly", branch_id=branch)
    await engine._tasks[current.run_id]
    directory = engine.run_dir(current.project_id, current.run_id)
    basis = read_json(directory / "basis.json")
    frozen = next(row for row in basis["artifacts"] if row.get("artifact_id") == prior["artifact_id"])
    assert frozen["producing_run_id"] == "run.p4.original"
    assert Path(frozen["path"]).read_bytes() == historical.read_bytes()
    assert frozen["original_path"] == prior["uri"]
    assert not [row for row in basis["unavailable_artifacts"] if row["family"] == "implementation_record"]
    assert sha256_file(Path(frozen["path"])) == prior["sha256"]

    report, _, roots, _ = report_case
    report = deepcopy(report)
    report.update(method_identity=identity, problem_context_ref={key: basis["problem_context"][key] for key in ("revision", "sha256")})
    references = {row["family"]: {key: row[key] for key in ("phase", "branch", "family", "generation_id", "content_sha256")}
                  for row in basis["records"] if row["phase"] == "P4"}
    report["numerical_analysis"] = [{"question": "How stable is the estimator?", "scope": "Synthetic regime",
        "relevance": "Estimate stability", "data_origin": "synthetic_mechanism", "data_or_simulation_identity": "fixture.v1",
        "evidence_refs": [references["evidence"]], "implementation_refs": [references["implementation_record"]]}]
    report["completion"] = derive_report_completion(report, basis, artifact_roots=roots)
    assert report["completion"]["status"] == "complete"
    assert validate_technical_report({"p5.technical_report_candidate": report}, basis, artifact_roots=roots) == []

    # An explanation and its explicit retry must copy authorized frozen bytes,
    # even after their original producer changes. They cannot reopen live data.
    historical.write_bytes(b"Changed after the report was authorized.")
    target = {"kind": "fixture", "phase": "P5", "branch": branch, "run_id": current.run_id}
    issue = {"source_run_id": current.run_id, "explanation_target": target, "responsible_role": "research_lead"}
    monkeypatch.setattr(engine, "_resolve_explanation_issue", lambda *args: deepcopy(issue))
    conversation = await engine.start_run("project.test", phase="P5", mode="p5.assembly", branch_id=branch,
        intent="assessment", target=target, assessment_purpose="issue_explanation", instructions="Explain the retained source.")
    await engine._tasks[conversation.run_id]
    conversation.state = RunState.FAILED
    engine._save_run(conversation)
    retry = await engine.start_run("project.test", phase="P5", mode="p5.assembly", branch_id=branch,
        intent="assessment", assessment_id=conversation.assessment_id, retry_run_id=conversation.run_id)
    await engine._tasks[retry.run_id]
    retry_basis = read_json(engine.run_dir(retry.project_id, retry.run_id) / "basis.json")
    retained = next(row for row in retry_basis["artifacts"] if row.get("artifact_id") == prior["artifact_id"])
    assert retained["path"] != frozen["path"]
    assert Path(retained["path"]).name == Path(frozen["path"]).name
    assert Path(retained["path"]).read_bytes() == Path(frozen["path"]).read_bytes()
    assert sha256_file(Path(retained["path"])) == prior["sha256"]
    assert not [row for row in retry_basis["unavailable_artifacts"] if row["family"] == "implementation_record"]

    # A dependency absent from the authorized frozen context cannot be added
    # by a later retry merely because exact live source bytes are available.
    historical.write_bytes(Path(frozen["path"]).read_bytes())
    retry_basis["artifacts"] = [row for row in retry_basis["artifacts"] if row.get("artifact_id") != prior["artifact_id"]]
    write_json_atomic(engine.run_dir(retry.project_id, retry.run_id) / "basis.json", retry_basis)
    retry.state = RunState.FAILED
    engine._save_run(retry)
    unavailable_retry = await engine.start_run("project.test", phase="P5", mode="p5.assembly", branch_id=branch,
        intent="assessment", assessment_id=conversation.assessment_id, retry_run_id=retry.run_id)
    await engine._tasks[unavailable_retry.run_id]
    unavailable_basis = read_json(engine.run_dir(unavailable_retry.project_id, unavailable_retry.run_id) / "basis.json")
    assert not [row for row in unavailable_basis["artifacts"] if row.get("artifact_id") == prior["artifact_id"]]
    unavailable = [row for row in unavailable_basis["unavailable_artifacts"] if row["artifact"].get("artifact_id") == prior["artifact_id"]]
    assert unavailable and all(row["reason"] == "Source was unavailable in the original assessment context" for row in unavailable)
    assert engine.bridge.turns == []
