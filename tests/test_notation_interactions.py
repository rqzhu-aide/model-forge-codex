"""Source-bound notes stay editable without becoming duplicate questions."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.notation import digest
from model_forge_codex.notation_interactions import (correction_owner, freeze_context, load_correction,
                                                    public_notation, save_correction)
from model_forge_codex.problem_context import (frozen_problem_context, initialize_problem_context,
                                              load_problem_context, save_context_item)
from model_forge_codex.research import artifacts_view, source_ref
from model_forge_codex.service import create_app
from model_forge_codex.storage import write_json_atomic
from test_notation_lifecycle import account, entry, local, METHOD


@pytest.fixture
def notation_case(tmp_path):
    project = tmp_path / "projects/project.test"
    write_json_atomic(project / "project.json", {"project_id": "project.test", "research_instructions": "Estimate the donor mean."})
    shutil.copytree(Path(__file__).resolve().parents[1] / "contracts", project / "contracts")
    initialize_problem_context(project)
    ref, snapshot, document = account(project)
    target = {**source_ref("trunk", "P1", "research_basis", ref), "kind": "notation_entry",
              "snapshot_sha256": document["notation_snapshot"]["sha256"],
              "entry_id": snapshot["entries"][0]["entry_id"]}
    return project, ref, snapshot, target


def test_note_edits_one_owner_and_generic_edits_cannot_duplicate_or_remove_source(notation_case):
    project, _, snapshot, target = notation_case
    loaded = load_correction(project, target)
    assert loaded["item"] is None and loaded["disposition"] is None
    saved = save_correction(project, target, "Please clarify the averaging unit.", expected_revision=loaded["context_revision"])
    first = saved["item"]
    edited = save_correction(project, target, "Each donor should have equal weight.", expected_revision=saved["context_revision"])
    assert edited["item"]["item_id"] == first["item_id"] == correction_owner(snapshot["entries"][0])
    assert edited["item"]["revision"] == 2
    context = load_problem_context(project)
    assert len(context["items"]) == 1
    assert any({key: value for key, value in first.items() if key != "history"} in prior["items"] for prior in context["history"])
    with pytest.raises(ValueError, match="changed"):
        save_correction(project, target, "Outdated editor", expected_revision=saved["context_revision"])
    with pytest.raises(ValueError, match="duplicate"):
        save_context_item(project, "Another copy", expected_revision=context["revision"],
                          topic="notation_correction", source_refs=[target])
    modified = save_context_item(project, "Clarify the population.", item_id=first["item_id"],
                                expected_revision=context["revision"])
    assert modified["items"][0]["source_refs"][0]["entry_id"] == target["entry_id"]


def test_inherited_lookup_reopens_same_owner_and_retains_each_saved_source(notation_case):
    project, ref, snapshot, target = notation_case
    saved = save_correction(project, target, "Keep equal donor weights.", expected_revision=load_problem_context(project)["revision"])
    later_ref, later, document = account(project, phase="P3", family="complete_theory", branch="method.one",
        run_id="run.p3", incoming={**snapshot, "sources": []}, additions=[], method=METHOD)
    mirror = {**later_ref, "kind": "notation_entry", "entry_id": later["entries"][0]["entry_id"],
              "snapshot_sha256": document["notation_snapshot"]["sha256"]}
    assert load_correction(project, mirror)["item"] == saved["item"]
    revised = save_correction(project, mirror, "Retain this target in the theoretical account.", expected_revision=saved["context_revision"])
    assert revised["item"]["source_refs"][0]["phase"] == "P3"
    assert len(load_problem_context(project)["items"]) == 1


def test_local_correction_owner_separates_unrelated_accounts_and_follows_explicit_clarification(notation_case):
    project, _, _, _ = notation_case
    first_ref, first, document = account(project, phase="P3", family="complete_theory", branch="method.one",
        run_id="run.p3.first", additions=[local("P3", "constant", "C")], method=METHOD)
    target = {**first_ref, "kind": "notation_entry", "entry_id": first["entries"][0]["entry_id"],
              "snapshot_sha256": document["notation_snapshot"]["sha256"]}
    saved = save_correction(project, target, "Clarify this bound's conditions.",
                            expected_revision=load_problem_context(project)["revision"])
    _, unrelated, _ = account(project, phase="P3", family="complete_theory", branch="method.one",
        run_id="run.p3.other", additions=[local("P3", "constant", "B")], method=METHOD)
    assert correction_owner(unrelated["entries"][0]) != saved["item"]["item_id"]
    from model_forge_codex.notation import collect_notation_inputs
    incoming = collect_notation_inputs(project, [first_ref], METHOD, "P3")
    clarification = local("P3", "constant", "D")
    clarification["replaces"] = {"snapshot_sha256": document["notation_snapshot"]["sha256"],
                                 "entry_id": first["entries"][0]["entry_id"]}
    revised_ref, revised, revised_doc = account(project, phase="P3", family="complete_theory", branch="method.one",
        run_id="run.p3.revised", incoming=incoming, additions=[clarification], method=METHOD)
    revised_target = {**revised_ref, "kind": "notation_entry", "entry_id": revised["entries"][-1]["entry_id"],
                      "snapshot_sha256": revised_doc["notation_snapshot"]["sha256"]}
    assert load_correction(project, revised_target)["item"] == saved["item"]
    # The fallback for an earlier generated view still uses its exact adoption.
    historical = deepcopy(first["entries"][0])
    historical.pop("account_scope_ref")
    assert correction_owner(historical) == saved["item"]["item_id"]


def test_source_note_cannot_smuggle_p4_into_p2_or_another_method(notation_case):
    project, core, snapshot, _ = notation_case
    p4, numerical, document = account(project, phase="P4", family="empirical_synthesis_candidate", branch="method.one",
        run_id="run.p4", incoming=snapshot, additions=[local("P4", "bandwidth")], method=METHOD)
    target = {**p4, "kind": "notation_entry", "entry_id": numerical["entries"][-1]["entry_id"],
              "snapshot_sha256": document["notation_snapshot"]["sha256"]}
    save_correction(project, target, "Explain the kernel bandwidth.", expected_revision=load_problem_context(project)["revision"])
    frozen = frozen_problem_context(project)
    excluded = freeze_context(frozen, [core])
    assert excluded["items"] == [] and excluded["effective_account"]["items"] == []
    assert "kernel bandwidth" not in json.dumps(excluded)
    admitted = freeze_context(frozen, [core, p4], branch_id="method.one", model_ref=METHOD)
    assert len(admitted["items"]) == len(admitted["notation_correction_refs"]) == 1
    assert admitted["notation_correction_refs"][0]["sha256"] == digest(admitted["items"][0])
    other = {"identity": {**METHOD["identity"], "definition_sha256": "b" * 64}}
    assert freeze_context(frozen, [p4], branch_id="method.one", model_ref=other)["items"] == []


def test_inherited_definition_keeps_correction_without_admitting_later_phase_or_other_branch(notation_case):
    project, core, snapshot, target = notation_case
    save_correction(project, target, "Clarify the averaging unit.", expected_revision=load_problem_context(project)["revision"])
    later_ref, later, _ = account(project, run_id="run.p1.later", incoming=snapshot, additions=[])
    frozen = frozen_problem_context(project)
    admitted = freeze_context(frozen, [later_ref], notation=later, phase="P1")
    assert len(admitted["items"]) == 1
    assert admitted["notation_correction_refs"][0]["sha256"] == digest(load_problem_context(project)["items"][0])
    assert freeze_context(frozen, [later_ref], notation={"entries": []}, phase="P1")["items"] == []
    p4_ref, p4, doc = account(project, phase="P4", family="empirical_synthesis_candidate", branch="method.one",
        run_id="run.p4.inherited", incoming=snapshot, additions=[], method=METHOD)
    mirror = {**p4_ref, "kind": "notation_entry", "entry_id": target["entry_id"],
              "snapshot_sha256": doc["notation_snapshot"]["sha256"]}
    save_correction(project, mirror, "Please interpret the donor target in this evaluation.",
                    expected_revision=load_problem_context(project)["revision"])
    frozen = frozen_problem_context(project)
    assert freeze_context(frozen, [later_ref], notation=later, phase="P2")["items"] == []
    assert freeze_context(frozen, [later_ref], notation=later, phase="P4", branch_id="method.other")["items"] == []
    assert len(freeze_context(frozen, [later_ref], notation=later, phase="P4", branch_id="method.one")["items"]) == 1


@pytest.mark.asyncio
async def test_api_binds_lookup_and_correction_to_exact_historical_account(notation_case):
    project, ref, _, target = notation_case
    app = create_app(project.parent.parent)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        url = "/api/v1/projects/project.test/notation"
        response = await client.get(url, params={"source": json.dumps(target)})
        assert response.status_code == 200, response.text
        assert response.json()["notation"]["snapshot_sha256"] == target["snapshot_sha256"]
        loaded = (await client.get(url + "/correction", params={"target": json.dumps(target)})).json()
        save = await client.put(url + "/correction", json={"target": target, "statement": "Explain the population.",
                                  "expected_revision": loaded["context_revision"]})
        assert save.status_code == 200, save.text
        forged = {**target, "snapshot_sha256": "0" * 64}
        assert (await client.get(url + "/correction", params={"target": json.dumps(forged)})).status_code == 422
        account(project, run_id="run.new", additions=[entry("new", "n")])
        old = await client.get(url, params={"source": json.dumps(target)})
        assert old.status_code == 200 and old.json()["notation"]["entries"][0]["quantity_key"] == "target"


def test_projection_uses_own_package_and_leaves_old_records_unchanged(notation_case):
    project, ref, _, _ = notation_case
    from model_forge_codex.research import _attach_notation_views
    doc = {"notation_snapshot": {"path": "notation.json", "sha256": "a" * 64}}
    exact = source_ref("trunk", "P1", "research_basis", ref)
    rows = {"documents": [{"generation_ref": exact}, {"generation_ref": {**exact, "package_id": "older"}}]}
    _attach_notation_views(rows, {("trunk", "P1"): {"research_basis": (doc, {"generation_ref": exact})}})
    assert rows["documents"][0]["notation_source_ref"] == exact
    assert "notation_snapshot" not in rows["documents"][1]


def test_same_run_definition_sources_get_exact_clickable_generation(notation_case):
    project, reference, snapshot, _ = notation_case
    public = public_notation(project, reference)["notation"]
    links = public["entries"][0]["ui_source_refs"]
    assert any(link["generation_ref"]["generation_id"] == reference["generation_id"]
               and link["entry_pointer"] == "/scientific_definition" for link in links)
    assert links[0]["source_role"] == "definition" and links[1]["source_role"] == "adoption"
    assert "ui_source_refs" not in snapshot["entries"][0]


def test_published_correction_outcome_survives_later_omission_but_not_answer_edit(notation_case):
    project, reference, _, target = notation_case
    save_correction(project, target, "Clarify the unit.", expected_revision=load_problem_context(project)["revision"])
    stored = load_problem_context(project)["items"][0]
    correction_ref = {"context_id": stored["item_id"], "revision": stored["revision"], "sha256": digest(stored)}
    from model_forge_codex.records import publish_package
    result = {"notation_updates": {"correction_dispositions": [{"correction_ref": correction_ref,
              "disposition": "unchanged", "reason_markdown": "The measurement unit is not available."}]}}
    directory = project / "branches/trunk/phases/p1"
    publish_package(directory, {"research_basis": json.dumps(result).encode()}, run_id="run.considered", phase="P1", branch_id="trunk")
    publish_package(directory, {"research_basis": b'{"notation_updates":{"correction_dispositions":[]}}'}, run_id="run.later", phase="P1", branch_id="trunk")
    assert load_correction(project, target)["disposition"]["disposition"] == "unchanged"
    edited = save_correction(project, target, "Now the unit is specified in the source data.", expected_revision=load_problem_context(project)["revision"])
    assert edited["disposition"] is None


def test_saved_correction_digest_round_trips_through_frozen_lead_publication(notation_case):
    from model_forge_codex.notation import collect_notation_inputs, retain_account_notation
    from model_forge_codex.records import publish_package
    from test_notation_lifecycle import basis, updates
    project, reference, _, target = notation_case
    save_correction(project, target, "Retain unknown measurement units.", expected_revision=load_problem_context(project)["revision"])
    frozen = freeze_context(frozen_problem_context(project), [reference])
    correction = frozen["notation_correction_refs"][0]
    document = {"scientific_definition": "The averaging unit and unknown measurement units remain unchanged.", "notation_updates": updates()}
    disposition = {"correction_ref": correction, "disposition": "unchanged", "reason_markdown": "The retained account already records that units remain unknown."}
    document["notation_updates"]["correction_dispositions"] = [disposition]
    incoming = basis(collect_notation_inputs(project, [reference], None, "P1"), refs=[reference])
    incoming["problem_context"] = frozen
    run = project / "runs/run.p1.considered"
    generated, _ = retain_account_notation(project, run, "P1", "trunk", "p1.synthesis", document, "research_basis", incoming,
        {"p1.research_basis": (document, "p1.synthesis")})
    publish_package(project / "branches/trunk/phases/p1", {"research_basis": json.dumps(generated).encode()},
        run_id=run.name, phase="P1", branch_id="trunk", metadata={"stage_ids": {"research_basis": "p1.synthesis"}})
    outcome = load_correction(project, target)["disposition"]
    assert outcome["correction_ref"] == correction
    assert outcome["disposition"] == "unchanged"


from test_technical_reports import report_case


def test_offline_html_retains_distinct_report_and_proof_notation(report_case):
    report, basis, roots, _ = report_case
    from model_forge_codex.notation import render_notation
    from model_forge_codex.storage import sha256_file
    from model_forge_codex.technical_reports import export_technical_report, report_required_artifacts
    root = next(iter(roots.values()))
    entries = []
    for number, (section, definition) in enumerate((("main", "$\\kappa$ is the kernel bandwidth."),
                                                 ("proof-1", "$\\kappa$ bounds the stated moment."))):
        entries.append({**entry(str(number), r"\kappa"), "entry_id": f"notation.{number}",
            "scope": {"kind": "account", "phase": "P5", "section": section},
            "definition_markdown": definition})
    snapshot = {"schema_version": "1.0.0", "entries": entries}
    write_json_atomic(root / "notation.json", snapshot)
    (root / "notation.md").write_text(render_notation(snapshot), encoding="utf-8")
    report["notation_snapshot"] = {"path": "notation.json", "sha256": sha256_file(root / "notation.json"), "media_type": "application/json",
        "markdown": {"path": "notation.md", "sha256": sha256_file(root / "notation.md"), "media_type": "text/markdown"}}
    materials = report_required_artifacts(report, basis)
    assert any(row.get("path") == "notation.json" for row in materials)
    assert any(row.get("path") == "notation.md" for row in materials)
    rendered = export_technical_report(report, basis, generation_ref={}, artifact_roots=roots, exported_at="").decode()
    assert 'id="report-notation"' in rendered and "kernel bandwidth" in rendered and "stated moment" in rendered
    assert "Report: main" in rendered and "Report: proof-1" in rendered and "<math" in rendered
    assert '<a id="notation.0"></a>' in rendered and '<a id="notation.1"></a>' in rendered
    assert '&lt;a id="notation.' not in rendered
    assert '"snapshot_sha256"' in rendered and '"entries"' in rendered


def test_report_proof_lookup_uses_its_declared_earlier_theory_account(notation_case):
    project, _, snapshot, _ = notation_case
    from model_forge_codex.records import generation_path
    from model_forge_codex.technical_reports import report_material_notation_source
    material = {"path": "proof.md", "sha256": "e" * 64, "media_type": "text/markdown"}
    ref, _, _ = account(project, phase="P3", family="complete_theory", branch="method.one",
                       run_id="run.proof", incoming=snapshot, additions=[local("P3", "moment_bound")],
                       method=METHOD, extra={"proof_artifact": material})
    directory = project / "branches/method.one/phases/p3"
    frozen = {**ref, "snapshot_path": str(generation_path(directory, ref["family"], ref))}
    report = {"claims": [{"source_refs": [{key: ref[key] for key in
               ("phase", "branch", "family", "generation_id", "content_sha256")} | {"pointer": "/scientific_definition"}]}]}
    account(project, phase="P3", family="complete_theory", branch="method.one", run_id="run.proof.new",
            additions=[local("P3", "different")], method=METHOD)
    view = report_material_notation_source(project, report, material, {"records": [frozen]})
    assert view["notation_source_ref"]["generation_id"] == ref["generation_id"]
    assert view["notation_source_ref"]["sha256"] == ref["content_sha256"]
    assert report_material_notation_source(project, {"claims": []}, material, {"records": [frozen]}) is None
