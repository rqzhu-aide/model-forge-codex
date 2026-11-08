"""Overview citations use their own published proof, including summary fallback."""
import copy
import json

import pytest

from model_forge_codex.records import publish_package, read_generation
from model_forge_codex.research import artifacts_view, current_decisions_view, scientific_document_view, source_ref
from model_forge_codex.research_sources import scientific_account_sources
from model_forge_codex.storage import sha256_bytes, sha256_file, write_json_atomic


def overview_publication(project, *, run_id="run.original", branch="method.a", proof=True, method_version=1, nested=False,
                         short_run_alias=False):
    run = project / "runs" / run_id
    manuscript = run / "outputs/p3.lead/working/research_lead/argument.md"
    manuscript.parent.mkdir(parents=True)
    text = f"# Complete argument\n\nRetained proof from {run_id}.\n"
    if nested:
        text += "[Decision](decision.json) [Canonical record](published-theory-object.json) [Audit](artifact://audit) [Unsealed](unsealed.json) [Guessed](theory_record.json)\n"
    manuscript.write_text(text, encoding="utf-8")
    identity = {"stable_id": branch, "version": method_version, "definition_sha256": str(method_version) * 64}
    uri = f"run://{run_id}/argument.md" if short_run_alias else "artifact://artifact.arbitrary-proof-identity"
    conclusion = f"The bound holds under the stated assumptions. See the [full proof and interpretation]({uri})."
    document = {"method_identity": identity, "statements": [], "assumptions": [], "primary_artifact": {
        "uri": uri, "path": "argument.md", "sha256": sha256_file(manuscript)}}
    account = {"method_identity": identity, "current_conclusion": conclusion,
               "inline_sources": [{"uri": uri, "source_verified": True, "artifact_url": "/api/forged"}]}
    summary = {"method_identity": identity, "evaluation_markdown": conclusion}
    write_json_atomic(run / "run.json", {"state": "published", "branch_id": branch, "phase": "P3"})
    write_json_atomic(run / "basis.json", {})
    records = {"decision": account, "phase_summary": summary}
    if proof:
        records["theory_record"] = document
    if nested:
        audit = {"method_identity": identity, "overall_assessment": "The stated assumptions remain necessary."}
        records["analyst_audit"] = audit
        records["analyst_handoff"] = {"method_identity": identity, "reviewed_sources": [{
            "uri": "artifact://audit", "path": "audit-output.json", "sha256": sha256_bytes(json.dumps(audit).encode())}]}
    encoded = {family: json.dumps(value).encode() for family, value in records.items()}
    stage_ids = {family: "p3.analyst" if family.startswith("analyst_") else "p3.lead" for family in records}
    filenames = {"theory_record": "published-theory-object.json", "analyst_audit": "audit-output.json"}
    seals = {}
    for family, data in encoded.items():
        stage = run / "outputs" / stage_ids[family]
        stage.mkdir(parents=True, exist_ok=True)
        name = filenames.get(family, family + ".json")
        (stage / name).write_bytes(data)
        seals.setdefault(stage_ids[family], {})[name] = {"sha256": sha256_bytes(data)}
    for stage, outputs in seals.items():
        write_json_atomic(run / "outputs" / stage / "seal.json", {"stage_id": stage, "outputs": outputs})
    (run / "outputs/p3.lead/unsealed.json").write_text("{}", encoding="utf-8")
    package = publish_package(project / "branches" / branch / "phases/p3",
                              encoded,
                              run_id=run_id, branch_id=branch, phase="P3",
                              metadata={"stage_ids": stage_ids})
    meta = {"phase": "P3", "generation_ref": source_ref(branch, "P3", "decision", package["records"]["decision"])}
    return package, account, meta, manuscript, text


@pytest.mark.parametrize("short_run_alias", [False, True])
def test_decision_and_published_summary_bind_same_package_proof_in_readable_source_viewer(tmp_path, short_run_alias):
    package, account, meta, manuscript, text = overview_publication(tmp_path, short_run_alias=short_run_alias)
    before = copy.deepcopy(account)
    view = artifacts_view(tmp_path)
    expected = source_ref("method.a", "P3", "theory_record", package["records"]["theory_record"])
    for surface in (view["decisions"][0], view["summaries"][0], current_decisions_view(tmp_path)[0]):
        assert len(surface["inline_sources"]) == 1
        link = surface["inline_sources"][0]
        assert link["source_verified"] is True and link["generation_ref"] == expected
        assert link["sha256"] == sha256_file(manuscript)
        assert "/api/forged" not in json.dumps(link)
    opened = scientific_document_view(tmp_path, "method.a", "P3", "theory_record", expected["generation_id"])
    assert opened["body_md"] == text
    assert opened["generation_ref"] == expected
    assert account == before


@pytest.mark.parametrize("short_run_alias", [False, True])
def test_old_overview_keeps_exact_proof_after_later_same_alias_publication(tmp_path, short_run_alias):
    package, account, meta, _, text = overview_publication(tmp_path, short_run_alias=short_run_alias)
    before = scientific_account_sources(tmp_path, account, meta)
    overview_publication(tmp_path, run_id="run.later", method_version=2, short_run_alias=short_run_alias)
    after = scientific_account_sources(tmp_path, account, meta)
    assert after == before
    ref = after[0]["generation_ref"]
    assert ref["package_id"] == package["package_id"] and ref["run_id"] == "run.original"
    assert scientific_document_view(tmp_path, "method.a", "P3", "theory_record", ref["generation_id"])["body_md"] == text


def test_proof_document_links_use_package_declarations_and_actual_sealed_record_filenames(tmp_path):
    package, _, _, _, text = overview_publication(tmp_path, nested=True)
    ref = source_ref("method.a", "P3", "theory_record", package["records"]["theory_record"])
    opened = scientific_document_view(tmp_path, "method.a", "P3", "theory_record", ref["generation_id"])
    links = {link["uri"]: link for link in opened["inline_sources"]}
    assert set(links) == {"decision.json", "published-theory-object.json", "artifact://audit"}
    for uri, family in (("decision.json", "decision"), ("artifact://audit", "analyst_audit")):
        assert links[uri]["generation_ref"] == source_ref("method.a", "P3", family, package["records"][family])
    canonical = links["published-theory-object.json"]
    assert "generation_ref" not in canonical
    assert canonical["sha256"] == ref["sha256"]
    assert "path=published-theory-object.json&sha256=" + ref["sha256"] in canonical["artifact_url"]
    # The overview's proof citation still opens the readable primary manuscript.
    account = artifacts_view(tmp_path)["decisions"][0]
    assert account["inline_sources"][0]["generation_ref"] == ref
    assert opened["body_md"] == text


def test_nested_proof_citation_rejects_a_later_package_from_the_same_run(tmp_path):
    package, _, _, manuscript, _ = overview_publication(tmp_path)
    # Add a citation before publication without any audit declaration in that
    # package, then publish that audit separately from the same run.
    manuscript.write_text("# Proof\n\n[Audit](artifact://audit) [Audit record](audit-output.json)", encoding="utf-8")
    phase_dir = tmp_path / "branches/method.a/phases/p3"
    document = {"primary_artifact": {"path": "argument.md", "sha256": sha256_file(manuscript)}}
    original = publish_package(phase_dir, {"theory_record": json.dumps(document).encode()},
                               run_id="run.original", branch_id="method.a", phase="P3")
    audit = {"overall_assessment": "Later separate review."}
    data = json.dumps(audit).encode()
    output = manuscript.parents[2] / "audit-output.json"
    output.write_bytes(data)
    write_json_atomic(output.parent / "seal.json", {"stage_id": "p3.lead", "outputs": {"audit-output.json": {"sha256": sha256_bytes(data)}}})
    publish_package(phase_dir, {"analyst_audit": data, "analyst_handoff": json.dumps({"sources": [{
        "uri": "artifact://audit", "path": "audit-output.json", "sha256": sha256_bytes(data)}]}).encode()},
        run_id="run.original", branch_id="method.a", phase="P3", metadata={"stage_ids": {"analyst_audit": "p3.lead", "analyst_handoff": "p3.lead"}})
    opened = scientific_document_view(tmp_path, "method.a", "P3", "theory_record", original["records"]["theory_record"]["generation_id"])
    assert opened["inline_sources"] == []


@pytest.mark.parametrize("damage", ["other_package_same_run", "other_method", "changed_proof", "missing_proof", "conflicting_alias", "wrong_account_generation"])
@pytest.mark.parametrize("short_run_alias", [False, True])
def test_overview_cannot_substitute_another_publication_or_changed_evidence(tmp_path, damage, short_run_alias):
    package, account, meta, manuscript, _ = overview_publication(
        tmp_path, proof=damage != "other_package_same_run", short_run_alias=short_run_alias)
    phase_dir = tmp_path / "branches/method.a/phases/p3"
    if damage == "other_package_same_run":
        # A real declaration in a later package, even from the same run, is not
        # evidence for the original decision that lacked that declaration.
        publish_package(phase_dir, {"theory_record": json.dumps({"primary_artifact": {
            "uri": "run://run.original/argument.md" if short_run_alias else "artifact://artifact.arbitrary-proof-identity",
            "path": "argument.md", "sha256": sha256_file(manuscript)}}).encode()},
            run_id="run.original", branch_id="method.a", phase="P3")
    elif damage in {"other_method", "conflicting_alias"}:
        pointer = package["records"]["theory_record"]
        path = phase_dir / "theory_record/generations" / (pointer["generation_id"] + ".json")
        document = json.loads(path.read_text())
        if damage == "other_method":
            document["method_identity"]["version"] = 2
        else:
            document["source_artifacts"] = [{"uri": document["primary_artifact"]["uri"], "path": "missing.md", "sha256": "f" * 64}]
        replacement = publish_package(phase_dir, {"decision": json.dumps(account).encode(), "theory_record": json.dumps(document).encode()},
                                      run_id="run.original", branch_id="method.a", phase="P3")
        meta["generation_ref"] = source_ref("method.a", "P3", "decision", replacement["records"]["decision"])
    elif damage == "changed_proof":
        manuscript.write_text("Changed bytes", encoding="utf-8")
    elif damage == "missing_proof":
        manuscript.unlink()
    else:
        meta["generation_ref"]["generation_id"] = "generation.unrelated"
    assert scientific_account_sources(tmp_path, account, meta) == []


def auxiliary_publication(project, run_id="run.proofs"):
    run = project / "runs" / run_id
    proof = run / "outputs/p3.theorist/working/theorist/proofs.md"
    proof.parent.mkdir(parents=True)
    proof.write_text("# Retained proofs\n\n## P6. Output guarantee\n\nThe conditions remain necessary.\n", encoding="utf-8")
    pointer = {"uri": "artifact://theorist/proofs.md", "path": "proofs.md", "sha256": sha256_file(proof), "media_type": "text/markdown"}
    identity = {"stable_id": "method.a", "version": 2, "definition_sha256": "2" * 64}
    candidate = {"method_identity": identity, "statements": [{"justification": {"artifacts": [pointer]}}]}
    audit = {"method_identity": identity, "overall_assessment": "The conditional guarantee is supported."}
    audit_path = run / "outputs/p3.analyst/audit.json"
    account = {"method_identity": identity, "current_conclusion": f"The conditional guarantee is supported. [Retained proofs](<{proof.as_posix()}>) and [independent audit](<{audit_path.as_posix()}>)."}
    records = {"theory_candidate": candidate, "theory_record": candidate, "analyst_audit": audit, "decision": account}
    stages = {"theory_candidate": "p3.theorist", "theory_record": "p3.lead", "analyst_audit": "p3.analyst", "decision": "p3.lead"}
    encoded, seals = {}, {}
    for family, document in records.items():
        data = json.dumps(document).encode()
        name = "audit.json" if family == "analyst_audit" else family + ".json"
        target = run / "outputs" / stages[family] / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        encoded[family] = data
        seals.setdefault(stages[family], {})[name] = {"sha256": sha256_bytes(data)}
    for stage, outputs in seals.items():
        write_json_atomic(run / "outputs" / stage / "seal.json", {"stage_id": stage, "outputs": outputs})
    write_json_atomic(run / "run.json", {"state": "published", "branch_id": "method.a", "phase": "P3"})
    write_json_atomic(run / "basis.json", {})
    package = publish_package(project / "branches/method.a/phases/p3", encoded,
                              run_id=run_id, branch_id="method.a", phase="P3", metadata={"stage_ids": stages})
    meta = {"phase": "P3", "generation_ref": source_ref("method.a", "P3", "decision", package["records"]["decision"])}
    return package, account, meta, pointer, proof, audit_path


def test_absolute_angle_citations_and_auxiliary_proof_open_the_exact_retained_source(tmp_path):
    package, account, meta, pointer, proof, audit = auxiliary_publication(tmp_path)
    before = copy.deepcopy(account)
    links = {link["uri"]: link for link in scientific_account_sources(tmp_path, account, meta)}
    assert set(links) == {proof.as_posix(), audit.as_posix()}
    retained = links[proof.as_posix()]
    expected = source_ref("method.a", "P3", "theory_candidate", package["records"]["theory_candidate"])
    assert retained["generation_ref"] == {**expected, "artifact_ref": {"uri": pointer["uri"], "sha256": pointer["sha256"]}}
    assert links[audit.as_posix()]["generation_ref"]["family"] == "analyst_audit"
    opened = scientific_document_view(tmp_path, "method.a", "P3", "theory_candidate", expected["generation_id"], artifact_ref=retained["generation_ref"]["artifact_ref"])
    assert opened["body_md"] == proof.read_text(encoding="utf-8")
    assert opened["primary_source_verified"] is True
    assert opened["primary_artifact_url"] == retained["artifact_url"]
    assert opened["source_artifact"] == pointer
    # Claim proof controls use the canonical authored alias, not the overview's absolute alias.
    current = artifacts_view(tmp_path)["documents"][0]
    canonical = next(link for link in current["inline_sources"] if link["uri"] == pointer["uri"])
    assert canonical["generation_ref"] == retained["generation_ref"]
    auxiliary_publication(tmp_path, "run.newer")
    assert scientific_account_sources(tmp_path, account, meta) == list(links.values())
    assert account == before


@pytest.mark.parametrize("damage", ["undeclared", "changed", "wrong_digest", "wrong_uri", "other_generation", "ambiguous"])
def test_auxiliary_reader_rejects_unbound_or_changed_sources(tmp_path, damage):
    package, _, _, pointer, proof, _ = auxiliary_publication(tmp_path)
    ref = source_ref("method.a", "P3", "theory_candidate", package["records"]["theory_candidate"])
    selector = {"uri": pointer["uri"], "sha256": pointer["sha256"]}
    if damage == "changed":
        proof.write_text("Changed source", encoding="utf-8")
    elif damage == "wrong_digest":
        selector["sha256"] = "f" * 64
    elif damage == "wrong_uri":
        selector["uri"] = proof.as_posix()
    elif damage == "other_generation":
        ref = source_ref("method.a", "P3", "analyst_audit", package["records"]["analyst_audit"])
    else:
        declared = [] if damage == "undeclared" else [pointer, {**pointer, "path": "missing.md"}]
        replacement = publish_package(tmp_path / "branches/method.a/phases/p3", {"theory_candidate": json.dumps({"artifacts": declared}).encode()},
                                      run_id="run.proofs", branch_id="method.a", phase="P3")
        ref = source_ref("method.a", "P3", "theory_candidate", replacement["records"]["theory_candidate"])
    with pytest.raises(ValueError, match="source"):
        scientific_document_view(tmp_path, "method.a", "P3", ref["family"], ref["generation_id"], artifact_ref=selector)


def test_absolute_citation_does_not_open_an_undeclared_existing_file(tmp_path):
    _, account, meta, _, proof, _ = auxiliary_publication(tmp_path)
    private = proof.with_name("private.md")
    private.write_text("Unpublished file", encoding="utf-8")
    account = {**account, "current_conclusion": f"[Unavailable](<{private.as_posix()}>)"}
    assert scientific_account_sources(tmp_path, account, meta) == []


@pytest.mark.parametrize("damage", [None, "changed", "undeclared", "traversal", "other_run", "outside_project", "wrong_drive", "double_slash"])
def test_windows_rooted_citation_is_only_an_alias_of_exact_retained_bytes(tmp_path, damage):
    if not tmp_path.drive:
        pytest.skip("A drive-rooted Windows artifact path is required")
    _, account, meta, _, proof, _ = auxiliary_publication(tmp_path)
    uri = "/" + proof.as_posix()
    if damage == "changed":
        proof.write_text("Changed source", encoding="utf-8")
    elif damage == "undeclared":
        private = proof.with_name("private.md")
        private.write_bytes(proof.read_bytes())
        uri = "/" + private.as_posix()
    elif damage == "traversal":
        uri = uri.replace("/working/", "/working/../working/")
    elif damage == "other_run":
        uri = uri.replace("/run.proofs/", "/run.unrelated/")
    elif damage == "outside_project":
        private = tmp_path / "private.md"
        private.write_bytes(proof.read_bytes())
        uri = "/" + private.as_posix()
    elif damage == "wrong_drive":
        uri = "/" + ("Z" if proof.drive[0].upper() != "Z" else "Y") + uri[2:]
    elif damage == "double_slash":
        uri = "/" + uri
    account = {**account, "current_conclusion": f"Conditions remain necessary. [Retained argument](<{uri}#p6>)"}
    before = copy.deepcopy(account)
    links = scientific_account_sources(tmp_path, account, meta)
    if damage:
        assert links == []
    else:
        assert len(links) == 1 and links[0]["uri"] == uri
        link = links[0]
        assert link["source_verified"] and link["sha256"] == sha256_file(proof)
        reference = link["generation_ref"]
        opened = scientific_document_view(tmp_path, "method.a", "P3", reference["family"], reference["generation_id"],
                                          artifact_ref=reference["artifact_ref"])
        assert opened["body_md"] == proof.read_text(encoding="utf-8")
        assert opened["primary_artifact_url"] == link["artifact_url"]
    assert account == before


@pytest.mark.parametrize("damage", [None, "missing_local", "changed_local", "missing_foreign", "local_conflict", "foreign_run_uri"])
def test_relative_citation_uses_its_own_stage_without_hiding_ambiguity(tmp_path, damage):
    package, account, _, manuscript, _ = overview_publication(tmp_path)
    phase = tmp_path / "branches/method.a/phases/p3"
    records = {family: read_generation(phase, family, pointer) for family, pointer in package["records"].items()}
    run = tmp_path / "runs/run.original"
    foreign = run / "outputs/p3.theorist/working/theorist/argument.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("# Original specialist argument\n", encoding="utf-8")
    records["theory_candidate"] = {"method_identity": records["theory_record"]["method_identity"], "primary_artifact": {
        "path": "argument.md", "uri": "run://run.original/p3.theorist/argument.md", "sha256": sha256_file(foreign)}}
    if damage == "local_conflict":
        alternate = run / "outputs/p3.lead/working/alternate/argument.md"
        alternate.parent.mkdir(parents=True)
        alternate.write_text("# Different local argument\n", encoding="utf-8")
        records["theory_record"]["artifacts"] = [{"path": "argument.md", "uri": "artifact://conflicting-local",
                                                  "sha256": sha256_file(alternate)}]
    elif damage == "foreign_run_uri":
        records["theory_record"]["primary_artifact"]["uri"] = "run://run.unrelated/p3.lead/argument.md"
    account = {**account, "current_conclusion": "Conditions remain necessary. [Full conditions](argument.md)."}
    records["decision"] = account
    stages = {family: "p3.theorist" if family == "theory_candidate" else "p3.lead" for family in records}
    package = publish_package(phase, {family: json.dumps(document).encode() for family, document in records.items()},
                              run_id="run.original", branch_id="method.a", phase="P3", metadata={"stage_ids": stages})
    meta = {"generation_ref": source_ref("method.a", "P3", "decision", package["records"]["decision"])}
    if damage == "missing_local":
        manuscript.unlink()
    elif damage == "changed_local":
        manuscript.write_text("Changed local bytes", encoding="utf-8")
    elif damage == "missing_foreign":
        foreign.unlink()
    before = copy.deepcopy(account)
    links = scientific_account_sources(tmp_path, account, meta)
    if damage:
        assert links == []
    else:
        assert len(links) == 1 and links[0]["uri"] == "argument.md"
        assert links[0]["sha256"] == sha256_file(manuscript)
        assert links[0]["sha256"] != sha256_file(foreign)
        assert links[0]["generation_ref"]["family"] == "theory_record"
        assert links[0]["generation_ref"]["stage_id"] == "p3.lead"
    assert account == before


def test_document_api_accepts_only_the_exact_declared_auxiliary_selector(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from model_forge_codex.bridge import FakeCodexBridge
    from model_forge_codex.service import create_app
    project = tmp_path / "projects/project.test"
    package, _, _, pointer, proof, _ = auxiliary_publication(project)
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    app = create_app(data_root=tmp_path, bridge=FakeCodexBridge())
    generation = package["records"]["theory_candidate"]["generation_id"]
    endpoint = next(route.endpoint for route in app.routes if getattr(route, "name", None) == "record_body")
    params = {"view": "document", "artifact_uri": pointer["uri"], "artifact_sha256": pointer["sha256"]}
    opened = endpoint("project.test", "method.a", "P3", "theory_candidate", generation, **params)
    assert opened["body_md"] == proof.read_text(encoding="utf-8")
    for changes in ({"artifact_sha256": "bad"}, {"artifact_uri": proof.as_posix()}, {"artifact_sha256": "f" * 64}):
        with pytest.raises(HTTPException) as rejected:
            endpoint("project.test", "method.a", "P3", "theory_candidate", generation, **{**params, **changes})
        assert rejected.value.status_code == 400
