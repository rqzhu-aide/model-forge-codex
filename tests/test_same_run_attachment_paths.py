"""Completed member attachments have exact downstream paths without exposing drafts."""
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from model_forge_codex.domain import MemberRole, StageSpec
from model_forge_codex.records import source_artifact_path
from model_forge_codex.research_sources import artifact_link
from model_forge_codex.runs import RunEngine
from model_forge_codex.storage import sha256_bytes, write_json_atomic


@pytest.mark.parametrize("delivery", ["inline", "instructed_open"])
def test_completed_attachment_path_reaches_only_its_permitted_reader(tmp_path, delivery):
    project = tmp_path / "project.test"
    run_dir = project / "runs/run.test"
    content = b"The retained argument with its qualifications."
    pointer = {"path": "proof.md", "sha256": sha256_bytes(content)}
    prior = StageSpec("p3.theorist", 1, "serial", (MemberRole.THEORIST,),
        ("p3.theory_candidate", "p3.private_account"), artifact_contracts={
            "p3.theory_candidate": {"delivery": delivery, "audience": ["data_analyst"]},
            "p3.private_account": {"delivery": "inline", "audience": ["research_lead"]}})
    reviewer = StageSpec("p3.analyst", 2, "serial", (MemberRole.DATA_ANALYST,),
        ("p3.theory_audit",), reads=("p3.theory_candidate",))
    folder = run_dir / "outputs" / prior.stage_id
    retained = folder / "working/theorist/proof.md"
    retained.parent.mkdir(parents=True)
    retained.write_bytes(content)
    write_json_atomic(folder / "theory_candidate.json", {
        "primary_artifact": pointer, "representations": [{"artifact": pointer}]})
    private = retained.with_name("private.md")
    private.write_bytes(b"A different member's private attachment.")
    write_json_atomic(folder / "private_account.json", {
        "primary_artifact": {"path": private.name, "sha256": sha256_bytes(private.read_bytes())}})
    current = run_dir / "outputs" / reviewer.stage_id / "working/data_analyst/proof.md"
    current.parent.mkdir(parents=True)
    current.write_bytes(content)
    write_json_atomic(current.parent.parent.parent / "theory_audit.json", {
        "primary_artifact": {"path": current.name, "sha256": sha256_bytes(current.read_bytes())}})
    record = SimpleNamespace(project_id=project.name, run_id=run_dir.name, phase="P3")
    renderer = SimpleNamespace(
        run_dir=lambda *_: run_dir, project_dir=lambda *_: project,
        _stages=lambda _: [prior, reviewer], _p2_specialist_content=lambda *_: None,
        _artifact_pointers=RunEngine._artifact_pointers)

    sections = RunEngine._same_run_sections(renderer, record, reviewer, MemberRole.DATA_ANALYST)

    instructed = "\n".join(sections["instructed"])
    assert str(retained.resolve()) in instructed
    assert instructed.count(str(retained.resolve())) == 1
    assert pointer["sha256"] in instructed
    assert str(private) not in instructed
    assert private.name not in instructed
    assert str(current) not in str(sections)
    # Published UI and later frozen-input resolution already follow this exact layout.
    reference = {"run_id": record.run_id, "stage_id": prior.stage_id, "branch": "method.test", "phase": "P3"}
    assert source_artifact_path(project, reference, pointer) == retained.resolve()
    write_json_atomic(run_dir / "run.json", {"state": "published", "branch_id": reference["branch"], "phase": "P3"})
    link = artifact_link(project, reference, pointer)
    assert link["source_verified"]
    assert parse_qs(urlsplit(link["artifact_url"]).query)["path"] == ["working/theorist/proof.md"]
    assert not (folder / pointer["path"]).exists()
    retained.write_bytes(b"Changed bytes cannot be delivered as the declared argument.")
    altered = RunEngine._same_run_sections(renderer, record, reviewer, MemberRole.DATA_ANALYST)
    assert str(retained.resolve()) not in "\n".join(altered["instructed"])
    assert str(current) not in str(altered)
