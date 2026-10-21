"""Later phases can open source bytes retained only by an earlier P1 run."""
import asyncio
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.direct_artifacts import apply_direct_literature, derive_direct_records
from model_forge_codex.domain import MemberRole
from model_forge_codex.literature import build_library
from model_forge_codex.members import provision_team
from model_forge_codex.methods import activate_method
from model_forge_codex.records import current_records, publish_package, read_generation
from model_forge_codex.runs import RunEngine
from model_forge_codex.storage import read_json, write_json_atomic
from test_literature import source
from test_direct_workflow import PID, complete, direct_engine, p1_documents, p2_documents, script


@pytest.mark.parametrize("legacy_registry", [False, True])
async def test_downstream_authorization_copies_old_source_fulltext_from_its_producing_run(tmp_path, monkeypatch, legacy_registry):
    project = tmp_path / "data" / "projects" / "project.sources"
    project.mkdir(parents=True)
    write_json_atomic(project / "project.json", {"project_id": "project.sources", "research_instructions": "Study interacting Langevin particles."})
    shutil.copytree(Path(__file__).resolve().parents[1] / "contracts", project / "contracts")
    provision_team(project)
    engine = RunEngine(tmp_path / "data", FakeCodexBridge())
    phase_dir = project / "branches" / "trunk" / "phases" / "p1"

    # Opaque retained PDF bytes: this test verifies provenance/copying, not PDF
    # rendering or scientific content. Only the first run has the right bytes.
    pdf_bytes = b"%PDF-1.4\n% Original retained source fixture\n%%EOF\n"
    pdf_digest = hashlib.sha256(pdf_bytes).hexdigest()
    original = project / "runs" / "run.original" / "outputs" / "p1.discovery" / "paper.pdf"
    original.parent.mkdir(parents=True)
    original.write_bytes(pdf_bytes)
    first_source = source(run_id="run.original", source_artifact={"artifact_id": "artifact.paper", "path": "paper.pdf", "sha256": pdf_digest, "media_type": "application/pdf"})
    initial_records = {key.split(".", 1)[1]: value for key, value in p1_documents((first_source["source_id"],)).items()}
    initial_records["lead_literature"]["papers"][0]["source"] = first_source
    first_formulation = initial_records["lead_literature"]["papers"][0]["formulation_markdown"]
    first_library = apply_direct_literature(build_library(None, [first_source], run_id="run.original"), initial_records, run_id="run.original")
    initial_records.update(derive_direct_records("P1", initial_records, run_id="run.original"))
    if not legacy_registry:
        initial_records["literature_library"] = first_library
    publish_package(phase_dir, {key: json.dumps(doc).encode() for key, doc in initial_records.items()},
                    run_id="run.original", phase="P1", branch_id="trunk")

    newer_source = source("citation.newer", locator="10.1234/newer", run_id="run.newer")
    latest_records = {key.split(".", 1)[1]: value for key, value in p1_documents((newer_source["source_id"],)).items()}
    latest_records["lead_literature"]["papers"][0]["source"] = newer_source
    latest_library = apply_direct_literature(build_library(first_library, [newer_source], run_id="run.newer"), latest_records, run_id="run.newer")
    latest_records.update(derive_direct_records("P1", latest_records, run_id="run.newer", previous_library=first_library))
    if not legacy_registry:
        latest_records["literature_library"] = latest_library
    latest = publish_package(phase_dir, {key: json.dumps(doc).encode() for key, doc in latest_records.items()},
                             run_id="run.newer", phase="P1", branch_id="trunk")
    unrelated = project / "runs" / "run.newer" / "outputs" / "p1.discovery" / "paper.pdf"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_bytes(b"Different bytes under the same filename in the later run")

    async def hold(_record, _stages):
        await asyncio.Event().wait()
    monkeypatch.setattr(engine, "_drive", hold)
    run = await engine.start_run("project.sources", phase="P2", mode="p2.full_catalog", branch_id="trunk")
    try:
        basis = read_json(engine.run_dir("project.sources", run.run_id) / "basis.json")
        frozen_library = read_json(Path(basis["cumulative_inputs"]["literature_library"]["snapshot_path"]))
        assert frozen_library["total_sources"] == 2
        assert frozen_library["sources"][0]["revisions"][0]["run_id"] == "run.original"
        retained_finding = frozen_library["sources"][0]["assessments"][0]
        assert retained_finding["run_id"] == "run.original"
        assert retained_finding["family"] == "lead_literature"
        assert retained_finding["entry"]["formulation_markdown"] == first_formulation
        copies = [entry for entry in basis["artifacts"] if entry["content_sha256"] == pdf_digest]
        assert len(copies) == 1
        retained = copies[0]
        assert retained["producing_run_id"] == "run.original"
        assert retained["family"] == "literature_library"
        assert retained["phase"] == "P1"
        assert retained["original_path"] == "paper.pdf"
        assert Path(retained["path"]).read_bytes() == pdf_bytes
        assert retained["generation_id"] == (None if legacy_registry else latest["records"]["literature_library"]["generation_id"])
        assert not basis["unavailable_artifacts"]

        # After authorization the original file can change without changing the
        # next role's scientific context. The legacy auxiliary record needs no
        # invented generation ID to expose the exact copied source path/digest.
        original.write_bytes(b"Changed after authorization")
        stage = engine._stages(run)[0]
        brief = engine._render_brief(run, stage, MemberRole.THEORIST, engine.member_workspace(run, stage.stage_id, MemberRole.THEORIST))
        assert retained["path"] in brief
        assert pdf_digest in brief
        assert "Unavailable referenced material" not in brief
        assert Path(retained["path"]).read_bytes() == pdf_bytes
        assert engine.bridge.turns == []
    finally:
        await engine.cancel("project.sources", run.run_id)


async def test_catalog_rerun_keeps_old_method_files_bound_to_the_original_proposal(direct_engine, monkeypatch):
    engine, project = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    initial, initial_files = p2_documents(False)
    initial_artifact = initial["p2.theory_proposal"]["method"]["mathematical_definition"]["canonical_artifact"]
    original_digest = initial_artifact["sha256"]
    original_bytes = initial_files[initial_artifact["path"]].encode()
    script(engine, "P2", "p2.full_catalog", initial, initial_files)
    original_run = await complete(engine, "P2", "p2.full_catalog")

    # The next catalog keeps the first proposals and adds three new ones. The
    # same relative file names now contain different bytes in the new run.
    following, following_files = p2_documents(False)
    following_files = {path: content + "A later proposal's source file.\n" for path, content in following_files.items()}
    for role in ("theory", "empirical", "lead"):
        method = following[f"p2.{role}_proposal"]["method"]
        method["identity"]["stable_id"] += ".new"
        method["record_id"] += ".new"
        artifact = method["mathematical_definition"]["canonical_artifact"]
        artifact["sha256"] = hashlib.sha256(following_files[artifact["path"]].encode()).hexdigest()
    script(engine, "P2", "p2.full_catalog", following, following_files)
    await complete(engine, "P2", "p2.full_catalog")
    phase_dir = project / "branches/trunk/phases/p2"
    pointer = current_records(phase_dir)["method_catalog"]
    catalog = read_generation(phase_dir, "method_catalog", pointer)
    assert len(catalog["methods"]) == 6
    assert catalog["method_sources"]["method.theory"]["run_id"] == original_run.run_id
    chosen = activate_method(project, "method.theory")

    async def hold(_record, _stages):
        await asyncio.Event().wait()
    monkeypatch.setattr(engine, "_drive", hold)
    run = await engine.start_run(PID, phase="P3", mode="p3.theory_establishment", branch_id=chosen["branch_id"])
    try:
        basis = read_json(engine.run_dir(PID, run.run_id) / "basis.json")
        copied = [entry for entry in basis["artifacts"] if entry["content_sha256"] == original_digest]
        assert len(copied) == 1
        assert copied[0]["family"] == "method_catalog"
        assert copied[0]["producing_run_id"] == original_run.run_id
        assert copied[0]["generation_id"] == pointer["generation_id"]
        assert Path(copied[0]["path"]).read_bytes() == original_bytes
        assert not [item for item in basis["unavailable_artifacts"] if item.get("artifact", {}).get("sha256") == original_digest]
    finally:
        await engine.cancel(PID, run.run_id)
