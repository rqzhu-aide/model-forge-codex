"""Inline P4 run locators bind to declared bytes in their exact publication."""
import copy
import json

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.records import publish_package
from model_forge_codex.research import artifacts_view, source_ref
from model_forge_codex.research_sources import empirical_run_sources
from model_forge_codex.service import create_app
from model_forge_codex.storage import sha256_file, write_json_atomic
from test_researcher_workbench_engine import workbench


def retained_sources(project, branch="method.a", *, reproduction=False, registry=False):
    run_id = "run.p4.current"
    run = project / "runs" / run_id
    primary = run / "outputs/p4.analyst/working/data_analyst/analyst_text.json"
    primary.parent.mkdir(parents=True)
    primary.write_bytes(b'{"title":"Full account","conclusion":"Qualified full result."}')
    paths = {"protocol": "p4.analyst/protocol.json", "theory_audit": "p4.theorist/theory_audit.json",
             "analyst_synthesis": "p4.analyst/analyst_synthesis.json", "empirical_synthesis": "p4.lead/empirical_synthesis_candidate.json"}
    uris = [f"run://{run_id}/outputs/{path}" for path in [paths["protocol"], paths["theory_audit"],
            "p4.analyst/working/data_analyst/analyst_text.json"]]
    lead = {"decision_summary": {"implementation_markdown": " ".join(f"[source {i}]({uri})" for i, uri in enumerate(uris))}}
    docs = {"protocol": {"claim_tests": [{"test_id": "question.one", "hypothesis": "A question"}]},
            "theory_audit": {"assessment_markdown": "Independent qualification."},
            "analyst_synthesis": {"question_results": [{"question_id": "question.one", "answer_markdown": "Full Q4."}],
                "representations": [{"information_layer": "primary_artifact", "artifact": {
                    "path": "analyst_text.json", "sha256": sha256_file(primary), "uri": "artifact://full-account"}}]},
            "empirical_synthesis": lead}
    if reproduction:
        readme = primary.with_name("README_context.md")
        readme.write_text("Run the retained ordinary example.\n", encoding="utf-8")
        reports = primary.with_name("README_reports_v4.md")
        reports.write_text("Regenerate from the retained rows.\n", encoding="utf-8")
        paths["implementation_record"] = "p4.analyst/implementation_record.json"
        docs["implementation_record"] = {"reproduction": {
            "readme": {"artifact": {"path": readme.name, "sha256": sha256_file(readme), "uri": "artifact://readme"}},
            "support_files": [{"artifact": {"path": reports.name, "sha256": sha256_file(reports), "uri": "artifact://reports"}}]}}
        uris.extend(f"run://{run_id}/outputs/p4.analyst/working/data_analyst/{path.name}" for path in (readme, reports))
        lead["decision_summary"]["implementation_markdown"] = " ".join(f"[source {i}]({uri})" for i, uri in enumerate(uris))
    if registry:
        details = primary.with_name("pilot_detail.json")
        details.write_bytes(b'{"checks":"Retained controlled results."}')
        uris.append(f"run://{run_id}/outputs/p4.analyst/working/data_analyst/{details.name}")
        docs["theory_audit"]["source_registry"] = [{"filename": f"working/data_analyst/{details.name}",
            "uri": uris[-1], "sha256": sha256_file(details)}]
        lead["decision_summary"]["implementation_markdown"] = " ".join(f"[source {i}]({uri})" for i, uri in enumerate(uris))
    raw = {family: json.dumps(doc).encode() for family, doc in docs.items()}
    seals = {}
    for family, path in paths.items():
        target = run / "outputs" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw[family])
        stage, filename = path.split("/", 1)
        seals.setdefault(stage, {})[filename] = {"sha256": sha256_file(target)}
    for stage, outputs in seals.items():
        write_json_atomic(run / "outputs" / stage / "seal.json", {"outputs": outputs})
    write_json_atomic(run / "run.json", {"state": "published", "branch_id": branch, "phase": "P4"})
    package = publish_package(project / "branches" / branch / "phases/p4", raw,
        run_id=run_id, phase="P4", branch_id=branch, metadata={"stage_ids": {family: path.split("/", 1)[0] for family, path in paths.items()}})
    records = {family: (doc, {"generation_ref": source_ref(branch, "P4", family, package["records"][family])}) for family, doc in docs.items()}
    return run, docs, records, uris, primary


def test_lead_without_source_artifacts_resolves_exact_records_and_declared_primary(tmp_path):
    run, docs, records, uris, primary = retained_sources(tmp_path)
    before = copy.deepcopy(docs)
    links = empirical_run_sources(tmp_path, docs["empirical_synthesis"], records["empirical_synthesis"][1], records)
    assert {item["uri"] for item in links} == set(uris)
    assert all(item["source_verified"] and item["producing_run_id"] == run.name and item["branch"] == "method.a" for item in links)
    assert all(item["sha256"] in item["artifact_url"] for item in links)
    primary_link = next(item for item in links if item["uri"].endswith("analyst_text.json"))
    assert primary_link["sha256"] == sha256_file(primary)
    assert primary_link["sha256"] != records["analyst_synthesis"][1]["generation_ref"]["sha256"]
    view = artifacts_view(tmp_path, "method.a")
    assert view["empirical_summaries"][0]["run_sources"] == links
    assert "primary_content" not in json.dumps(view)
    assert docs == before and "source_artifacts" not in docs["empirical_synthesis"]


@pytest.mark.parametrize("damage", [None, "tampered_readme", "other_package"])
def test_run_locators_resolve_declared_reproduction_files_without_artifact_uri_substitution(tmp_path, damage):
    run, docs, records, uris, primary = retained_sources(tmp_path, reproduction=True)
    before = copy.deepcopy(docs)
    if damage == "tampered_readme":
        primary.with_name("README_context.md").write_text("Changed instructions.\n", encoding="utf-8")
    elif damage == "other_package":
        records["implementation_record"][1]["generation_ref"]["package_id"] = "package.other"
    links = empirical_run_sources(tmp_path, docs["empirical_synthesis"], records["empirical_synthesis"][1], records)
    expected = set(uris)
    if damage == "tampered_readme":
        expected.remove(uris[-2])
    elif damage == "other_package":
        expected.difference_update(uris[-2:])
    assert {item["uri"] for item in links} == expected
    assert all(item["source_verified"] and item["producing_run_id"] == run.name for item in links)
    assert all(item["sha256"] in item["artifact_url"] for item in links)
    assert docs == before


@pytest.mark.parametrize("damage", [None, "tampered_file", "other_package", "other_run", "only_other_role_copy", "traversal", "missing_digest"])
def test_run_locators_resolve_exact_filename_registry_declarations(tmp_path, damage):
    run, docs, records, uris, primary = retained_sources(tmp_path, registry=True)
    pointer = docs["theory_audit"]["source_registry"][0]
    details = primary.with_name("pilot_detail.json")
    if damage == "tampered_file":
        details.write_bytes(b'{"changed":true}')
    elif damage == "other_package":
        records["theory_audit"][1]["generation_ref"]["package_id"] = "package.other"
    elif damage == "other_run":
        pointer["uri"] = pointer["uri"].replace(run.name, "run.other")
    elif damage == "only_other_role_copy":
        other = run / "outputs/p4.theorist/working/data_analyst/pilot_detail.json"
        other.parent.mkdir(parents=True)
        other.write_bytes(details.read_bytes())
        details.unlink()
    elif damage == "traversal":
        pointer["uri"] = pointer["uri"].replace("p4.analyst/", "p4.analyst/../p4.analyst/")
        docs["empirical_synthesis"]["decision_summary"]["implementation_markdown"] += f" [unsafe]({pointer['uri']})"
    elif damage == "missing_digest":
        pointer.pop("sha256")
    before = copy.deepcopy(docs)
    links = empirical_run_sources(tmp_path, docs["empirical_synthesis"], records["empirical_synthesis"][1], records)
    expected = set(uris)
    if damage:
        expected.remove(uris[-1])
    if damage == "other_package":
        expected.remove(uris[1])
    assert {item["uri"] for item in links} == expected
    assert all(item["source_verified"] and item["producing_run_id"] == run.name for item in links)
    assert all(item["sha256"] in item["artifact_url"] for item in links)
    assert docs == before


@pytest.mark.parametrize("damage", ["unpublished", "other_branch", "other_phase"])
def test_run_sources_require_the_published_method_and_phase(tmp_path, damage):
    run, docs, records, _, _ = retained_sources(tmp_path)
    state = {"state": "published", "branch_id": "method.a", "phase": "P4"}
    state.update({"state": "running"} if damage == "unpublished" else {"branch_id": "method.other"} if damage == "other_branch" else {"phase": "P3"})
    write_json_atomic(run / "run.json", state)
    assert empirical_run_sources(tmp_path, docs["empirical_synthesis"], records["empirical_synthesis"][1], records) == []


def test_run_locators_cannot_bind_unknown_wrong_role_or_other_run_files(tmp_path):
    run, docs, records, uris, _ = retained_sources(tmp_path)
    known = run / "outputs/p4.analyst/protocol.json"
    wrong_role = run / "outputs/p4.theorist/protocol.json"
    wrong_role.write_bytes(known.read_bytes())
    unknown = run / "outputs/p4.analyst/private.json"
    unknown.write_bytes(b'{"private":"unbound support file"}')
    bad = [f"run://{run.name}/outputs/p4.theorist/protocol.json", f"run://{run.name}/outputs/p4.analyst/private.json",
           f"run://{run.name}/outputs/p4.analyst/../p4.theorist/protocol.json", uris[0].replace(run.name, "run.other")]
    lead = {"decision_summary": {"implementation_markdown": " ".join(f"[unknown]({uri})" for uri in bad)}}
    assert empirical_run_sources(tmp_path, lead, records["empirical_synthesis"][1], records) == []


@pytest.mark.parametrize("damage", ["tampered_record", "tampered_primary", "missing_seal", "other_package"])
def test_run_sources_do_not_substitute_changed_or_unbound_scientific_sources(tmp_path, damage):
    run, docs, records, uris, primary = retained_sources(tmp_path)
    if damage == "tampered_record":
        (run / "outputs/p4.analyst/protocol.json").write_bytes(b'{"changed":true}')
    elif damage == "tampered_primary":
        primary.write_bytes(b'{"conclusion":"Changed"}')
    elif damage == "missing_seal":
        (run / "outputs/p4.analyst/seal.json").unlink()
    else:
        records["protocol"][1]["generation_ref"]["package_id"] = "package.other"
    links = empirical_run_sources(tmp_path, docs["empirical_synthesis"], records["empirical_synthesis"][1], records)
    missing = uris[2] if damage == "tampered_primary" else uris[0]
    assert missing not in {item["uri"] for item in links}


async def test_projected_run_source_url_rechecks_bytes_when_opened(workbench):
    engine, project, branch = workbench
    run, docs, records, uris, _ = retained_sources(project, branch)
    link = next(item for item in empirical_run_sources(project, docs["empirical_synthesis"], records["empirical_synthesis"][1], records) if item["uri"] == uris[0])
    app = create_app(data_root=engine.data_root, bridge=engine.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(link["artifact_url"])
        assert response.status_code == 200
        assert response.content == (run / "outputs/p4.analyst/protocol.json").read_bytes()
        (run / "outputs/p4.analyst/protocol.json").write_bytes(b'{"changed":true}')
        assert (await client.get(link["artifact_url"])).status_code == 409


def test_stage_form_run_locators_keep_exact_published_records_and_declared_working_aliases(tmp_path):
    run, docs, records, uris, primary = retained_sources(tmp_path)
    audit_uri = uris[1].replace("/outputs/", "/")
    working_uri = f"run://{run.name}/p4.analyst/analyst_text.json"
    docs["analyst_synthesis"]["representations"][0]["artifact"]["uri"] = working_uri
    lead = {"body_md": f"[Audit]({audit_uri}#/question_results/0) [Full account]({working_uri})"}
    links = empirical_run_sources(tmp_path, lead, records["empirical_synthesis"][1], records)
    assert {link["uri"] for link in links} == {audit_uri, working_uri}
    assert next(link for link in links if link["uri"] == audit_uri)["sha256"] == records["theory_audit"][1]["generation_ref"]["sha256"]
    assert "path=working%2Fdata_analyst%2Fanalyst_text.json" in next(link for link in links if link["uri"] == working_uri)["artifact_url"]
    docs["analyst_synthesis"]["source_artifacts"] = [{"uri": working_uri, "path": "missing.json", "sha256": "f" * 64}]
    assert working_uri not in {link["uri"] for link in empirical_run_sources(tmp_path, lead, records["empirical_synthesis"][1], records)}
    docs["analyst_synthesis"]["source_artifacts"] = [{"uri": audit_uri, "path": "missing.json", "sha256": "f" * 64}]
    assert audit_uri not in {link["uri"] for link in empirical_run_sources(tmp_path, lead, records["empirical_synthesis"][1], records)}


def frozen_upstream_sources(project, run):
    frozen = []
    uris = []
    for phase, branch, family, stage in (("P3", "method.a", "complete_theory", "p3.lead"),
                                         ("P2", "trunk", "lead_proposal", "p2.independent_proposals")):
        source_run = f"run.{phase.lower()}.origin"
        raw = json.dumps({"body_md": "Exact upstream account.", "method": {"mathematical_definition": {"canonical_definition": {"objective": "Frozen definition."}}}}).encode()
        store = project / "branches" / branch / "phases" / phase.lower()
        package = publish_package(store, {family: raw}, run_id=source_run, phase=phase, branch_id=branch,
                                  metadata={"stage_ids": {family: stage}})
        output = project / "runs" / source_run / "outputs" / stage / f"{family}.json"
        output.parent.mkdir(parents=True)
        output.write_bytes(raw)
        write_json_atomic(output.parent / "seal.json", {"outputs": {output.name: {"sha256": sha256_file(output)}}})
        write_json_atomic(project / "runs" / source_run / "run.json", {"state": "published", "branch_id": branch, "phase": phase})
        snapshot = run / "inputs" / f"{family}.json"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(raw)
        frozen.append({**package["records"][family], "branch": branch, "phase": phase, "family": family, "snapshot_path": str(snapshot)})
        uris.append(f"run://{source_run}/{stage}/{family}.json" if phase == "P3" else f"run://{source_run}/p2.{family}")
    write_json_atomic(run / "basis.json", {"records": frozen})
    return frozen, uris


@pytest.mark.parametrize("damage", [None, "changed_snapshot", "changed_generation", "not_frozen", "ambiguous", "unpublished", "foreign_run"])
def test_upstream_run_links_resolve_only_exact_frozen_published_generations(tmp_path, damage):
    from pathlib import Path
    from model_forge_codex.records import generation_path

    run, docs, records, _, _ = retained_sources(tmp_path)
    frozen, uris = frozen_upstream_sources(tmp_path, run)
    before = copy.deepcopy(frozen)
    if damage == "changed_snapshot":
        Path(frozen[0]["snapshot_path"]).write_bytes(b"{}")
    elif damage == "changed_generation":
        generation_path(tmp_path / "branches/method.a/phases/p3", "complete_theory", frozen[0]).write_bytes(b"{}")
    elif damage == "not_frozen":
        write_json_atomic(run / "basis.json", {"records": frozen[1:]})
    elif damage == "ambiguous":
        write_json_atomic(run / "basis.json", {"records": [*frozen, {**frozen[0], "generation_id": "generation.other"}]})
    elif damage == "unpublished":
        write_json_atomic(tmp_path / "runs/run.p3.origin/run.json", {"state": "running", "branch_id": "method.a", "phase": "P3"})
    elif damage == "foreign_run":
        uris[0] = uris[0].replace("run.p3.origin", "run.foreign")
    lead = {"body_md": f"[Theory]({uris[0]}) [Frozen definition]({uris[1]}#/method/mathematical_definition/canonical_definition)"}
    links = empirical_run_sources(tmp_path, lead, records["empirical_synthesis"][1], records)
    assert {link["uri"] for link in links} == set(uris if damage is None else uris[1:])
    assert all(link["source_verified"] and link["branch"] == "method.a" for link in links)
    definition = next(link for link in links if link["uri"] == uris[1])
    assert definition["generation_ref"] == source_ref("trunk", "P2", "lead_proposal", frozen[1])
    # A new current publication cannot replace the frozen historical source.
    publish_package(tmp_path / "branches/trunk/phases/p2", {"lead_proposal": b'{"new":"current"}'},
                    run_id="run.new", phase="P2", branch_id="trunk")
    assert empirical_run_sources(tmp_path, lead, records["empirical_synthesis"][1], records) == links
    assert frozen == before


def test_upstream_stage_filename_selects_original_family_among_identical_promoted_aliases(tmp_path):
    from pathlib import Path

    run, _, records, _, _ = retained_sources(tmp_path)
    frozen, uris = frozen_upstream_sources(tmp_path, run)
    raw = Path(frozen[0]["snapshot_path"]).read_bytes()
    package = publish_package(tmp_path / "branches/method.a/phases/p3", {"theory_record": raw},
                              run_id="run.p3.origin", phase="P3", branch_id="method.a",
                              metadata={"stage_ids": {"theory_record": "p3.lead"}})
    alias = {**package["records"]["theory_record"], "branch": "method.a", "phase": "P3",
             "family": "theory_record", "snapshot_path": frozen[0]["snapshot_path"]}
    write_json_atomic(run / "basis.json", {"records": [*frozen, alias]})
    links = empirical_run_sources(tmp_path, {"body_md": f"[Theory]({uris[0]})"}, records["empirical_synthesis"][1], records)
    assert len(links) == 1
    assert links[0]["generation_ref"] == source_ref("method.a", "P3", "complete_theory", frozen[0])
