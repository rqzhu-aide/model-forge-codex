"""P3 narrative sources retain their sealed outputs and frozen generations."""
import copy
import json

import pytest

from model_forge_codex.records import publish_package
from model_forge_codex.research import scientific_document_view, source_ref
from model_forge_codex.research_sources import scientific_document_sources
from model_forge_codex.storage import sha256_file, write_json_atomic


def retained_sources(project):
    branch, run_id = "method.a", "run.p3.revision"
    run = project / "runs" / run_id
    old_bytes = b'{"conclusion":"Earlier bounded evaluation."}'
    old = publish_package(project / "branches" / branch / "phases/p4", {"decision": old_bytes},
                          run_id="run.p4.earlier", phase="P4", branch_id=branch)["records"]["decision"]
    snapshot = run / "inputs/method.a/p4/decision" / (old["generation_id"] + ".json")
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(old_bytes)
    frozen = {**old, "phase": "P4", "branch": branch, "family": "decision", "snapshot_path": str(snapshot)}
    manuscript = run / "inputs/artifacts/manuscript.md"
    manuscript.parent.mkdir(parents=True)
    manuscript.write_text("# Retained original proof\n", encoding="utf-8")
    revision = run / "outputs/p3.theorist/working/theorist/revision.md"
    revision.parent.mkdir(parents=True)
    revision.write_text("# Scoped revision\n", encoding="utf-8")
    pointers = [{"artifact_id": "artifact.proof", "uri": "artifact://artifact.proof", "path": "manuscript.md",
                 "sha256": sha256_file(manuscript), "source_verified": True, "artifact_url": "/api/forged"},
                {"artifact_id": "artifact.revision", "uri": "artifact://artifact.revision", "path": "revision.md",
                 "sha256": sha256_file(revision)}]
    uris = [f"run://{run_id}/outputs/p3.theorist/theory_candidate.json",
            f"run://{run_id}/outputs/p3.analyst/analyst_audit.json",
            "artifact://artifact.proof", "artifact://artifact.revision", "generation://" + old["generation_id"], "./revision.md"]
    text = "$$\\alpha \\leq 1$$\n\n" + " ".join(f"[Source {i}]({uri})" for i, uri in enumerate(uris))
    primary = run / "outputs/p3.lead/account.md"
    primary.parent.mkdir(parents=True)
    primary.write_text(text, encoding="utf-8")
    document = {"primary_artifact": {"path": "account.md", "sha256": sha256_file(primary)},
                "statements": [{"justification": {"artifacts": pointers}}]}
    for stage, filename in (("p3.theorist", "theory_candidate.json"), ("p3.analyst", "analyst_audit.json")):
        target = run / "outputs" / stage / filename
        write_json_atomic(target, {"account": stage})
        write_json_atomic(target.parent / "seal.json", {"stage_id": stage, "outputs": {filename: {"sha256": sha256_file(target)}}})
    write_json_atomic(run / "run.json", {"state": "published", "branch_id": branch, "phase": "P3"})
    write_json_atomic(run / "basis.json", {"records": [frozen], "artifacts": [{"artifact_id": "artifact.proof",
                      "content_sha256": sha256_file(manuscript), "path": str(manuscript), "original_path": "manuscript.md"}]})
    package = publish_package(project / "branches" / branch / "phases/p3", {"theory_record": json.dumps(document).encode()},
                              run_id=run_id, phase="P3", branch_id=branch, metadata={"stage_ids": {"theory_record": "p3.lead"}})
    meta = {"phase": "P3", "generation_ref": source_ref(branch, "P3", "theory_record", package["records"]["theory_record"])}
    return run, document, meta, text, uris, frozen


def test_p3_primary_sources_bind_sealed_candidate_declared_files_and_frozen_generation(tmp_path):
    run, document, meta, text, uris, frozen = retained_sources(tmp_path)
    before = copy.deepcopy(document)
    links = scientific_document_sources(tmp_path, document, meta, text)
    assert {link["uri"] for link in links} == set(uris)
    assert all(link["source_verified"] for link in links)
    assert next(link for link in links if link["uri"] == uris[4])["generation_ref"] == source_ref("method.a", "P4", "decision", frozen)
    assert all(link["sha256"] in link["artifact_url"] for link in links if "artifact_url" in link)
    assert "/api/forged" not in json.dumps(links)
    opened = scientific_document_view(tmp_path, "method.a", "P3", "theory_record", meta["generation_ref"]["generation_id"])
    assert opened["body_md"] == text and opened["inline_sources"] == links
    assert document == before


@pytest.mark.parametrize("damage", ["unpublished", "other_branch", "other_phase"])
def test_p3_sources_require_their_published_producing_run(tmp_path, damage):
    run, document, meta, text, _, _ = retained_sources(tmp_path)
    changes = {"unpublished": {"state": "running"}, "other_branch": {"branch_id": "method.other"}, "other_phase": {"phase": "P4"}}
    write_json_atomic(run / "run.json", {"state": "published", "branch_id": "method.a", "phase": "P3", **changes[damage]})
    assert scientific_document_sources(tmp_path, document, meta, text) == []


@pytest.mark.parametrize("damage", ["missing_seal", "changed_output", "changed_frozen", "ambiguous_alias"])
def test_p3_sources_reject_missing_changed_or_ambiguous_evidence(tmp_path, damage):
    run, document, meta, text, uris, frozen = retained_sources(tmp_path)
    missing = uris[0]
    if damage == "missing_seal":
        (run / "outputs/p3.theorist/seal.json").unlink()
    elif damage == "changed_output":
        (run / "outputs/p3.theorist/theory_candidate.json").write_text("{}")
    elif damage == "changed_frozen":
        from pathlib import Path
        Path(frozen["snapshot_path"]).write_text("{}")
        missing = uris[4]
    else:
        document["statements"][0]["justification"]["artifacts"].append(
            {"uri": uris[2], "path": "missing.md", "sha256": "f" * 64})
        missing = uris[2]
    assert missing not in {link["uri"] for link in scientific_document_sources(tmp_path, document, meta, text)}


def test_p3_run_and_relative_locators_do_not_open_undeclared_files_or_other_runs(tmp_path):
    run, document, meta, _, uris, _ = retained_sources(tmp_path)
    write_json_atomic(run / "outputs/p3.theorist/private.json", {"unbound": True})
    write_json_atomic(run / "seal.json", {"stage_id": "..", "outputs": {"basis.json": {"sha256": sha256_file(run / "basis.json")}}})
    unknown = [uris[0].replace(run.name, "run.other"),
               f"run://{run.name}/outputs/p3.theorist/private.json",
               f"run://{run.name}/outputs/p3.theorist/../p3.analyst/analyst_audit.json",
               f"run://{run.name}/outputs/../basis.json",
               "private.json", "../revision.md", "artifact://missing", "generation://missing"]
    text = " ".join(f"[Unavailable]({uri})" for uri in unknown)
    assert scientific_document_sources(tmp_path, document, meta, text) == []


def test_p3_saved_document_keeps_original_bindings_after_new_publications(tmp_path):
    _, _, meta, _, _, _ = retained_sources(tmp_path)
    generation = meta["generation_ref"]["generation_id"]
    before = scientific_document_view(tmp_path, "method.a", "P3", "theory_record", generation)
    for phase, family in (("P3", "theory_record"), ("P4", "decision")):
        publish_package(tmp_path / "branches/method.a/phases" / phase.lower(), {family: b'{"new":"current"}'},
                        run_id="run.new", phase=phase, branch_id="method.a")
    reopened = scientific_document_view(tmp_path, "method.a", "P3", "theory_record", generation)
    assert reopened["inline_sources"] == before["inline_sources"]
    assert reopened["body_md"] == before["body_md"]


@pytest.mark.parametrize("structured_only", [False, True])
def test_p3_audit_binds_exact_declared_current_run_uri_alias(tmp_path, structured_only):
    run, _, _, _, _, _ = retained_sources(tmp_path)
    manuscript = run / "outputs/p3.theorist/working/theorist/revision.md"
    uri = f"run://{run.name}/p3.theorist/revision.md"
    text = " ".join(f"[{name}]({uri}#statement.{name})" for name in ("likelihood", "bellman", "tolerance", "knowledge"))
    document = {"reviewed_sources": [
        {"artifact_id": "artifact.revision", "uri": uri, "path": "revision.md", "sha256": sha256_file(manuscript),
         "source_verified": True, "artifact_url": "/api/forged"}]}
    if structured_only:
        document["sections"] = [{"question": "What do these arguments establish?", "reasoning_markdown": text}]
    else:
        document["body_md"] = text
    before = copy.deepcopy(document)
    package = publish_package(tmp_path / "branches/method.a/phases/p3", {"analyst_audit": json.dumps(document).encode()},
                              run_id=run.name, phase="P3", branch_id="method.a",
                              metadata={"stage_ids": {"analyst_audit": "p3.analyst"}})
    opened = scientific_document_view(tmp_path, "method.a", "P3", "analyst_audit",
                                      package["records"]["analyst_audit"]["generation_id"])
    assert opened["body_md"] == ("" if structured_only else text)
    assert len(opened["inline_sources"]) == 1
    linked = opened["inline_sources"][0]
    assert linked["uri"] == uri and linked["source_verified"]
    assert linked["sha256"] == sha256_file(manuscript)
    assert "/outputs/p3.theorist/artifact?path=working%2Ftheorist%2Frevision.md&sha256=" in linked["artifact_url"]
    assert "/api/forged" not in json.dumps(linked)
    assert document == before


@pytest.mark.parametrize("damage", ["cross_run", "undeclared", "ambiguous", "changed", "missing",
                                    "unsafe_stage", "unsafe_path", "unsealed_outputs", "malformed_outputs"])
def test_p3_declared_run_alias_preserves_exact_source_boundaries(tmp_path, damage):
    run, _, meta, _, _, _ = retained_sources(tmp_path)
    manuscript = run / "outputs/p3.theorist/working/theorist/revision.md"
    uri = f"run://{run.name}/p3.theorist/revision.md"
    if damage == "cross_run":
        uri = uri.replace(run.name, "run.other")
    elif damage == "unsafe_stage":
        uri = uri.replace("/p3.theorist/", "/../")
    elif damage == "unsafe_path":
        uri = uri.replace("/revision.md", "/../revision.md")
    elif damage == "unsealed_outputs":
        uri = uri.replace("/p3.theorist/", "/outputs/p3.theorist/")
    elif damage == "malformed_outputs":
        uri = uri.replace("/p3.theorist/", "/outputs/")
    pointer = {"artifact_id": "artifact.revision", "uri": uri, "path": "revision.md", "sha256": sha256_file(manuscript)}
    document = {"reviewed_sources": [pointer]}
    if damage == "undeclared":
        document["reviewed_sources"] = []
    elif damage == "ambiguous":
        document["reviewed_sources"].append({"uri": uri, "path": "missing.md", "sha256": "f" * 64})
    elif damage == "changed":
        manuscript.write_text("Changed bytes", encoding="utf-8")
    elif damage == "missing":
        manuscript.unlink()
    text = f"[Unavailable]({uri}#statement.bellman)"
    assert scientific_document_sources(tmp_path, document, meta, text) == []
