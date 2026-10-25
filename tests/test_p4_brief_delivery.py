"""Large P4 inputs remain complete files rather than repeated inline payloads."""
import json
from types import SimpleNamespace

import pytest

from model_forge_codex.domain import MemberRole, StageSpec
from model_forge_codex.records import ArtifactError
from model_forge_codex.runs import RunEngine
from model_forge_codex.storage import sha256_file, write_json_atomic


FAMILIES = ["diagnostics", "protocol", "case_manifest", "metrics_long"]


@pytest.mark.parametrize("family", FAMILIES)
def test_large_same_run_p4_inputs_keep_full_sources_attachments_and_reader_scope(tmp_path, family):
    project = tmp_path / "project.test"
    run_dir = project / "runs/run.test"
    folder = run_dir / "outputs/p4.analyst"
    attachment = folder / "working/data_analyst/account.md"
    attachment.parent.mkdir(parents=True)
    attachment.write_bytes(b"Complete retained account and qualifications.")
    pointer = {"path": attachment.name, "sha256": sha256_file(attachment)}
    large = folder / RunEngine._output_filename("p4." + family)
    # The cap applies to bytes, including non-ASCII scientific prose.
    write_json_atomic(large, {"body": "LARGE_P4_BODY" + "界" * 16000, "primary_artifact": pointer})
    small = folder / "analyst_synthesis.json"
    write_json_atomic(small, {"body": "SMALL_P4_BODY", "primary_artifact": pointer})
    narrative = folder / "analyst_handoff.json"
    write_json_atomic(narrative, {"body": "AUTHORED_P4_ACCOUNT" + "界" * 16000})
    private = folder / "private_account.json"
    write_json_atomic(private, {"body": "PRIVATE_P4_BODY" + "界" * 16000})
    contracts = {
        "p4." + family: {"delivery": "inline", "audience": ["theorist"]},
        "p4.analyst_synthesis": {"delivery": "inline", "audience": ["theorist"]},
        "p4.analyst_handoff": {"delivery": "inline", "audience": ["theorist"]},
        "p4.private_account": {"delivery": "inline", "audience": ["research_lead"]},
    }
    prior = StageSpec("p4.analyst", 1, "serial", (MemberRole.DATA_ANALYST,), tuple(contracts),
                      artifact_contracts=contracts)
    reviewer = StageSpec("p4.theorist", 2, "serial", (MemberRole.THEORIST,), ("p4.theory_audit",))
    record = SimpleNamespace(project_id=project.name, run_id=run_dir.name, phase="P4")
    renderer = SimpleNamespace(run_dir=lambda *_: run_dir, project_dir=lambda *_: project,
        _stages=lambda _: [prior, reviewer], _p2_specialist_content=lambda *_: None,
        _artifact_pointers=RunEngine._artifact_pointers, _SIZE_CAPS=RunEngine._SIZE_CAPS)
    before = {path: path.read_bytes() for path in (large, small, narrative, private, attachment)}

    sections = RunEngine._same_run_sections(renderer, record, reviewer, MemberRole.THEORIST)

    packets, instructed = "\n".join(sections["packets"]), "\n".join(sections["instructed"])
    assert large.stat().st_size > 32768 and len(large.read_text(encoding="utf-8")) < 32768
    assert "LARGE_P4_BODY" not in str(sections)
    assert "SMALL_P4_BODY" in packets
    assert narrative.stat().st_size > 32768 and "AUTHORED_P4_ACCOUNT" in packets
    assert str(large) in instructed and sha256_file(large) in instructed
    assert f"{large.stat().st_size:,} B" in instructed and "open and read fully" in instructed
    assert instructed.count(str(attachment.resolve())) == 1 and pointer["sha256"] in instructed
    assert "PRIVATE_P4_BODY" not in str(sections) and str(private) not in instructed
    assert {path: path.read_bytes() for path in before} == before
    outsider = RunEngine._same_run_sections(renderer, record, reviewer, MemberRole.OUTSIDE_REVIEWER)
    assert not outsider["packets"] and not outsider["instructed"]


@pytest.mark.parametrize("family", FAMILIES)
def test_large_prior_p4_inputs_use_exact_frozen_sources_without_inline_flood(tmp_path, family):
    run_dir = tmp_path / "runs/run.test"
    frozen = run_dir / "inputs/p4" / (family + ".json")
    write_json_atomic(frozen, {"body": "FROZEN_P4_BODY" + "界" * 16000})
    small = frozen.with_name("analyst_synthesis.json")
    write_json_atomic(small, {"body": "SMALL_FROZEN_P4_BODY"})
    narrative = frozen.with_name("analyst_handoff.json")
    write_json_atomic(narrative, {"body": "AUTHORED_FROZEN_P4_ACCOUNT" + "界" * 16000})
    records = [{"phase": "P4", "family": path.stem, "branch": "method.test", "family_dir": path.parent / path.stem,
                "current": {"snapshot_path": str(path), "content_sha256": sha256_file(path)}}
               for path in (frozen, small, narrative)]
    contracts = {"p4." + row["family"]: {"delivery": "inline", "audience": ["theorist"]} for row in records}
    record = SimpleNamespace(project_id="project.test", run_id=run_dir.name, phase="P4")
    renderer = SimpleNamespace(run_dir=lambda *_: run_dir, _upstream_records=lambda _: records,
        _p2_specialist_content=lambda *_: None, _SIZE_CAPS=RunEngine._SIZE_CAPS,
        _generation_text=lambda *args: RunEngine._generation_text(None, *args))
    renderer._mention_line = lambda *args: RunEngine._mention_line(renderer, *args)
    catalog = SimpleNamespace(artifact_contracts=lambda: contracts)
    before = {path: path.read_bytes() for path in (frozen, small, narrative)}

    sections = RunEngine._classify_upstream(renderer, record, MemberRole.THEORIST, catalog)

    packets, instructed = "\n".join(sections["packets"]), "\n".join(sections["instructed"])
    assert "FROZEN_P4_BODY界" not in str(sections)
    assert "SMALL_FROZEN_P4_BODY" in packets
    assert narrative.stat().st_size > 32768 and "AUTHORED_FROZEN_P4_ACCOUNT" in packets
    assert str(frozen) in instructed and sha256_file(frozen) in instructed
    assert f"{frozen.stat().st_size:,} B" in instructed and "Open and read fully" in instructed
    assert {path: path.read_bytes() for path in before} == before
    outsider = RunEngine._classify_upstream(renderer, record, MemberRole.OUTSIDE_REVIEWER, catalog)
    assert not outsider["packets"] and not outsider["instructed"]
    frozen.write_text(json.dumps({"body": "Changed after authorization"}), encoding="utf-8")
    with pytest.raises(ArtifactError, match="missing or changed"):
        RunEngine._classify_upstream(renderer, record, MemberRole.THEORIST, catalog)
