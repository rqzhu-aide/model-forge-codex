"""Research accounts retain exact sources across display and history."""
import json

import pytest

from model_forge_codex.p4_validation import check_progressive_evaluation
from model_forge_codex.records import generation_path
from model_forge_codex.research import artifacts_view
from model_forge_codex.storage import sha256_bytes, write_json_atomic
from test_researcher_workbench_engine import publish, workbench
from test_researcher_workbench_api import api


def saved_file(project, branch, run_id, filename, content, phase="P4", stage="p4.analyst"):
    run = project / "runs" / run_id
    write_json_atomic(run / "run.json", {"state": "published", "branch_id": branch, "phase": phase})
    path = run / "outputs" / stage / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"path": filename, "sha256": sha256_bytes(content), "artifact_id": "artifact." + filename.replace("/", ".")}, path


def test_implementation_code_and_correspondence_are_exact_and_read_only(workbench):
    _, project, branch = workbench
    pointer, path = saved_file(project, branch, "run.implementation", "method.py", b"def estimate(x): return sum(x)/len(x)\n")
    pointer.update(artifact_url="https://example.invalid/not-verified.py", source_verified=True)
    implementation = {"implementation_summary": {"correspondence": "The mean solves the estimating equation.",
                      "verification": "One fixture passed; invalid input remains unchecked.", "departures": "None declared."},
                      "scientific_outcome": {"conclusion": "The fixture passed.", "scope": "Nonempty finite input only."},
                      "representations": [{"information_layer": "primary_artifact", "artifact": pointer}]}
    audit = {"audit": {"mathematical_fidelity": {"status": "limited", "assessment": "One fixture is not a proof."}},
             "scientific_outcome": {"material_disagreement": ["Boundary behavior remains unchecked."]}}
    publish(project, branch, "P4", {"implementation_record": implementation, "theory_audit": audit}, "run.implementation")
    view = artifacts_view(project, branch)["implementations"][0]
    sections = {item["key"]: item["body_md"] for item in view["sections"]}
    assert sections["correspondence"] == implementation["implementation_summary"]["correspondence"]
    assert sections["outcome_scope"] == "Nonempty finite input only."
    assert view["files"][0]["source_verified"]
    review = {item["key"]: item["body_md"] for item in view["theorist_review"]["sections"]}
    assert review["mathematical_fidelity"] == "One fixture is not a proof."
    assert review["outcome_material_disagreement"] == "Boundary behavior remains unchecked."
    path.write_bytes(b"new unreviewed implementation")
    assert "artifact_url" not in artifacts_view(project, branch)["implementations"][0]["files"][0]
    # A new publication does not make old files or assessments part of it.
    publish(project, branch, "P4", {"implementation_record": implementation}, "run.later")
    current = artifacts_view(project, branch)["implementations"][0]
    assert "theorist_review" not in current and "source_error" in current["files"][0]


async def test_reused_implementation_opens_only_its_retained_input(api):
    client, _, project, branch = api
    run_id = "run.reused"
    run = project / "runs" / run_id
    write_json_atomic(run / "run.json", {"state": "published", "branch_id": branch, "phase": "P4"})
    source = run / "inputs" / "artifacts" / "method.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"print('reading this must not run it')\n")
    pointer = {"path": "method.py", "artifact_id": "artifact.code", "sha256": sha256_bytes(source.read_bytes())}
    write_json_atomic(run / "basis.json", {"artifacts": [{"artifact_id": pointer["artifact_id"], "original_path": "method.py",
                      "path": str(source), "content_sha256": pointer["sha256"]}]})
    publish(project, branch, "P4", {"implementation_record": {"representations": [{"artifact": pointer}]}}, run_id)
    file = artifacts_view(project, branch)["implementations"][0]["files"][0]
    assert file["source_kind"] == "retained_input"
    response = await client.get(file["artifact_url"])
    assert response.status_code == 200 and response.content == source.read_bytes()
    assert response.headers["content-type"].startswith("text/plain")
    source.write_text("changed")
    assert (await client.get(file["artifact_url"])).status_code == 404


def test_manuscript_claims_keep_old_support_and_unresolved_counterevidence(workbench):
    _, project, branch = workbench
    previous = publish(project, branch, "P3", {"theory_record": {"record_id": "record.theory", "statements": [
        {"statement_id": "statement.consistency", "text": "Consistency under independence."}]}}, "run.old")
    source = {**previous["records"]["theory_record"], "branch": branch, "phase": "P3", "family": "theory_record"}
    write_json_atomic(project / "runs/run.paper/basis.json", {"records": [source]})
    trace = [{"statement_id": "claim.paper", "text": "The estimate is consistent under independence.",
              "supporting_evidence_ids": ["statement.consistency"], "counterevidence_ids": ["evidence.unresolved"], "source_locations": []}]
    publish(project, branch, "P5", {"manuscript": {"title": "A paper", "target_audience": "Researchers"}, "claim_traceability": trace}, "run.paper")
    publish(project, branch, "P3", {"theory_record": {"statements": [{"statement_id": "statement.consistency", "text": "Different new theorem."}]}}, "run.new")
    view = artifacts_view(project, branch)["claim_traceability"][0]
    links = view["claims"][0]["evidence_links"]
    assert links[0]["label"] == "Consistency under independence."
    assert source["generation_id"] in links[0]["source_url"]
    assert links[1]["source_error"] and "source_url" not in links[1]
    assert view["manuscript_generation_ref"]["run_id"] == "run.paper"
    # Missing original generation remains unresolved despite identical IDs in a newer one.
    path = generation_path(project / "branches" / branch / "phases/p3", "theory_record", source)
    path.unlink()
    missing = artifacts_view(project, branch)["claim_traceability"][0]["claims"][0]["evidence_links"][0]
    assert "source_error" in missing and "source_url" not in missing


def test_theory_literature_links_use_the_authored_graphs_frozen_basis(workbench):
    _, project, branch = workbench
    previous = publish(project, "trunk", "P1", {"lead_paper_cards": [{"subject_ref": "lit.example", "title": "Earlier literature account"}]}, "run.library")
    source = {**previous["records"]["lead_paper_cards"], "branch": "trunk", "phase": "P1", "family": "lead_paper_cards"}
    write_json_atomic(project / "runs/run.theory/basis.json", {"records": [source]})
    publish(project, branch, "P3", {"theory_record": {"statements": [{"statement_id": "claim.a", "text": "A theorem"}]},
                                  "claim_map": {"claims": [{"statement_id": "claim.a", "novelty_refs": ["lit.example", "lit.unknown"]}]}}, "run.theory")
    publish(project, "trunk", "P1", {"lead_paper_cards": [{"subject_ref": "lit.example", "title": "Later literature account"}]}, "run.later")
    links = artifacts_view(project, branch)["claim_maps"][0]["claims"][0]["novelty_links"]
    assert links[0]["label"] == "Earlier literature account"
    assert source["generation_id"] in links[0]["source_url"]
    assert "source_error" in links[1] and "source_url" not in links[1]


def test_theory_literature_entry_alias_uses_explicit_source_and_saved_generation(workbench):
    from model_forge_codex.research_sources import literature_reference_links
    _, project, _ = workbench
    alias = "lead.lu2026.bellman_certificates"
    paper = {"entry_id": alias, "formulation_markdown": "A saved assessment.",
             "source": {"source_id": "source.lu2026.bellman", "title": "Bellman Distributional Certificates"}}
    previous = publish(project, "trunk", "P1", {"lead_literature": {"papers": [paper],
        "source_refs": [{"entry_id": "lead.pointer_only", "source_id": "source.lu2026.bellman"}]}}, "run.library")
    source = {**previous["records"]["lead_literature"], "branch": "trunk", "phase": "P1", "family": "lead_literature"}
    write_json_atomic(project / "runs/run.theory/basis.json", {"records": [source]})
    publish(project, "trunk", "P1", {"lead_literature": {"papers": [
        {**paper, "source": {"source_id": "source.other", "title": "Later account"}},
        {"entry_id": "lead.only_current", "source": paper["source"]}]}}, "run.later")
    links = literature_reference_links(project, {"run_id": "run.theory"},
                                       [alias, "lead.pointer_only", "lead.only_current", "lead.unknown"])
    assert links[0]["identifier"] == alias
    assert links[0]["label"] == paper["source"]["title"]
    assert links[0]["source_id"] == paper["source"]["source_id"]
    assert links[0]["generation_ref"]["generation_id"] == source["generation_id"]
    assert links[0]["generation_ref"]["sha256"] == source["content_sha256"]
    assert links[0]["generation_ref"]["entry_pointer"] == "/papers/0"
    assert source["generation_id"] in links[0]["source_url"]
    assert all("source_error" in item and "source_url" not in item for item in links[1:])
    generation_path(project / "branches/trunk/phases/p1", "lead_literature", source).write_text("{}")
    assert "source_error" in literature_reference_links(project, {"run_id": "run.theory"}, [alias])[0]


def test_theory_literature_entry_alias_keeps_conflicting_explicit_sources(workbench):
    from model_forge_codex.research_sources import literature_reference_links
    _, project, _ = workbench
    previous = publish(project, "trunk", "P1", {"lead_literature": {"papers": [
        {"entry_id": "lead.shared", "source": {"source_id": identifier, "title": "Shared title"}}
        for identifier in ("source.a", "source.b")]}}, "run.library")
    source = {**previous["records"]["lead_literature"], "branch": "trunk", "phase": "P1", "family": "lead_literature"}
    write_json_atomic(project / "runs/run.theory/basis.json", {"records": [source]})
    links = literature_reference_links(project, {"run_id": "run.theory"}, ["lead.shared"])
    assert {item["source_id"] for item in links} == {"source.a", "source.b"}
    assert {item["generation_ref"]["entry_pointer"] for item in links} == {"/papers/0", "/papers/1"}


def test_theory_literature_identical_library_copy_uses_original_paper_pointer(workbench):
    from model_forge_codex.research_sources import literature_reference_links
    _, project, _ = workbench
    paper = {"entry_id": "lead.paper", "source": {"source_id": "source.paper", "title": "Saved paper"},
             "formulation_markdown": "Original formulation."}
    distinct = {**paper, "formulation_markdown": "Distinct later assessment."}
    previous = publish(project, "trunk", "P1", {
        "lead_literature": {"papers": [paper]},
        "theory_literature": {"papers": [paper]},
        "literature_library": {"sources": [{"assessments": [{"entry": paper}, {"entry": distinct}]}]}}, "run.library")
    sources = [{**pointer, "branch": "trunk", "phase": "P1", "family": family}
               for family, pointer in previous["records"].items()]
    # Even when the cumulative copy is seen first, prefer the exact original
    # report for identical content. The other assessment must remain separate.
    sources.sort(key=lambda ref: ref["family"] != "literature_library")
    write_json_atomic(project / "runs/run.theory/basis.json", {"records": sources})
    links = literature_reference_links(project, {"run_id": "run.theory"}, ["lead.paper"])
    assert len(links) == 3
    assert {(item["generation_ref"]["family"], item["generation_ref"]["entry_pointer"]) for item in links} == {
        ("lead_literature", "/papers/0"), ("theory_literature", "/papers/0"),
        ("literature_library", "/sources/0/assessments/1/entry")}


async def test_manuscript_source_locations_use_retained_bytes_and_declared_aliases(api):
    client, _, project, branch = api
    content = b"The complete saved argument."
    digest = sha256_bytes(content)
    alias = {"artifact_id": "artifact.proof.alias", "sha256": digest, "path": "proof-alias.txt"}
    previous = publish(project, branch, "P3", {"theory_record": {"record_id": "record.theory",
                       "representations": [{"artifact": alias}]}}, "run.theory")
    source = {**previous["records"]["theory_record"], "branch": branch, "phase": "P3", "family": "theory_record"}
    run = project / "runs/run.paper"
    frozen = run / "inputs/artifacts/proof.txt"
    frozen.parent.mkdir(parents=True)
    frozen.write_bytes(content)
    write_json_atomic(run / "run.json", {"state": "published", "phase": "P5", "branch_id": branch})
    write_json_atomic(run / "basis.json", {"records": [source], "artifacts": [{"artifact_id": "artifact.proof.original",
                      "content_sha256": digest, "path": str(frozen), "phase": "P3", "original_path": "proof.txt"}]})
    publish(project, branch, "P5", {"manuscript": {"title": "Current draft"}, "claim_traceability": [
        {"statement_id": "claim.a", "text": "A qualified result", "source_locations": [alias]}]}, "run.paper")
    link = artifacts_view(project, branch)["claim_traceability"][0]["claims"][0]["source_links"][0]
    assert link["source_verified"] and link["source_kind"] == "retained_input"
    assert (await client.get(link["artifact_url"])).content == content
    frozen.write_bytes(b"changed")
    assert (await client.get(link["artifact_url"])).status_code == 404
    assert "source_error" in artifacts_view(project, branch)["claim_traceability"][0]["claims"][0]["source_links"][0]


def test_excluded_observation_reasons_stay_with_declared_question_cases(workbench):
    _, project, branch = workbench
    protocol = {"claim_tests": [{"test_id": "test.a"}], "cases": [{"case_id": "case.a", "test_ids": ["test.a"]}]}
    rows = [{"case_id": case, "attempt_id": "attempt.one", "plan_revision_id": "plan.one", "eligibility": "invalidated",
             "invalidation_reason": reason} for case, reason in [("case.a", "Configuration did not match"),
                 ("case.a", "Configuration did not match"), ("case.b", "Unrelated question")]]
    publish(project, branch, "P4", {"protocol": protocol, "metrics_long": rows}, "run.observations")
    question = artifacts_view(project, branch)["questions"][0]
    assert len(question["excluded_observations"]) == 1
    excluded = question["excluded_observations"][0]
    assert excluded["count"] == 2 and excluded["invalidation_reason"] == "Configuration did not match"
    assert excluded["generation_ref"]["family"] == "metrics_long" and excluded["source_url"]


def test_review_links_the_exact_earlier_manuscript_not_the_revision(workbench):
    _, project, branch = workbench
    previous = publish(project, branch, "P5", {"manuscript": {"title": "Original draft"}}, "run.draft")
    source = {**previous["records"]["manuscript"], "branch": branch, "phase": "P5", "family": "manuscript"}
    write_json_atomic(project / "runs/run.review/basis.json", {"records": [source]})
    publish(project, branch, "P5", {"manuscript": {"title": "Revised draft"}, "outside_review": {"summary_markdown": "Original draft needs revision."}}, "run.review")
    documents = artifacts_view(project, branch)["documents"]
    review = next(item for item in documents if item["kind"] == "outside_review")
    assert review["reviewed_manuscript_ref"]["generation_id"] == source["generation_id"]
    current = next(item for item in documents if item["kind"] == "manuscript")
    assert current["generation_ref"]["generation_id"] != review["reviewed_manuscript_ref"]["generation_id"]


async def test_tex_is_labeled_source_and_pdf_uses_document_media_type(api):
    client, _, project, branch = api
    for suffix, content, media in [("tex", b"\\documentclass{article}\n\\begin{document}Exact source\\end{document}", "application/x-tex"),
                                   ("pdf", b"%PDF-1.4\ncontrolled fixture", "application/pdf")]:
        pointer, path = saved_file(project, branch, "run.paper." + suffix, "paper." + suffix, content, "P5", "p5.lead")
        publish(project, branch, "P5", {"manuscript": {"manuscript_artifact": pointer}}, "run.paper." + suffix)
        doc = next(item for item in artifacts_view(project, branch)["documents"] if item["kind"] == "manuscript")
        assert doc["primary_artifact_media_type"] == media
        if suffix == "tex":
            assert doc["primary_artifact_kind"] == "tex_source" and doc["source_text"] == content.decode()
            assert "\\documentclass" not in doc["body_md"]
        response = await client.get(doc["primary_artifact_url"])
        assert response.content == content and response.headers["content-type"].startswith(media)


async def test_svg_response_is_isolated_for_embedding_and_original_navigation(api):
    client, _, project, branch = api
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><text x="10" y="20">Visible figure</text><script>window.fixtureExecuted=true;</script></svg>'
    pointer, _ = saved_file(project, branch, "run.svg", "figure.svg", svg)
    url = f"/api/v1/projects/project.test/runs/run.svg/outputs/p4.analyst/artifact?path=figure.svg&sha256={pointer['sha256']}"
    for destination in ("image", "document"):
        response = await client.get(url, headers={"Sec-Fetch-Dest": destination})
        assert response.status_code == 200 and response.content == svg
        policy = response.headers["content-security-policy"]
        assert "sandbox" in policy and "default-src 'none'" in policy
        assert "allow-scripts" not in policy and "allow-same-origin" not in policy
        assert response.headers["x-content-type-options"] == "nosniff"


async def test_verified_table_pages_keep_labels_units_and_all_values(api):
    client, _, project, branch = api
    content = ("sample_size,error_value\n" + "\n".join(f"{i},{i / 1000}" for i in range(405))).encode()
    pointer, path = saved_file(project, branch, "run.table", "results.csv", content)
    exhibit = {"exhibit_id": "exhibit.values", "kind": "table", "artifact_path": pointer["path"],
               "artifact_sha256": pointer["sha256"], "media_type": "text/csv",
               "table_columns": [{"key": "error_value", "label": "Absolute error", "unit": "mg"}]}
    write_json_atomic(path.parent / "exhibits.json", [exhibit])
    publish(project, branch, "P4", {"exhibits": [exhibit]}, "run.table")
    table = artifacts_view(project, branch)["exhibits"][0]["table"]
    assert table["columns"][0]["label"] == "Sample size"
    assert table["columns"][1] == {"key": "error_value", "label": "Absolute error", "unit": "mg"}
    response = await client.get(table["next_page_url"])
    second = response.json()
    assert response.status_code == 200 and second["row_offset"] == 200 and len(second["rows"]) == 200
    assert second["rows"][0] == {"sample_size": "200", "error_value": "0.2"}
    last = (await client.get(second["next_page_url"])).json()
    assert last["row_offset"] == 400 and len(last["rows"]) == 5 and "next_page_url" not in last
    assert (await client.get(last["previous_page_url"])).json()["rows"] == second["rows"]
    assert (await client.get(second["next_page_url"].replace("exhibit.values", "exhibit.other"))).status_code == 404
    path.write_bytes(b"tampered")
    assert (await client.get(table["next_page_url"])).status_code == 409


def test_figure_data_association_is_explicit_and_same_publication(workbench):
    _, project, branch = workbench
    data, path = saved_file(project, branch, "run.figure", "values.csv", b"estimate\n0\n")
    figure_pointer, _ = saved_file(project, branch, "run.figure", "figure.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>')
    table = {"exhibit_id": "exhibit.data", "kind": "table", "artifact_path": data["path"], "artifact_sha256": data["sha256"], "media_type": "text/csv"}
    figure = {"exhibit_id": "exhibit.figure", "kind": "figure", "artifact_path": figure_pointer["path"],
              "artifact_sha256": figure_pointer["sha256"], "media_type": "image/svg+xml", "data_exhibit_ids": ["exhibit.data"]}
    write_json_atomic(path.parent / "exhibits.json", [table, figure])
    publish(project, branch, "P4", {"exhibits": [figure, table]}, "run.figure")
    projected = artifacts_view(project, branch)["exhibits"][0]
    assert projected["data_source_status"] == "verified" and projected["data_sources"][0]["table"]["rows"] == [{"estimate": "0"}]
    # The data in an earlier evaluation must not satisfy this new figure.
    publish(project, branch, "P4", {"exhibits": [figure]}, "run.figure")
    assert artifacts_view(project, branch)["exhibits"][0]["data_source_status"] == "unavailable"
    findings = []
    check_progressive_evaluation({"p4.exhibits": [figure]}, findings)
    assert {item.code for item in findings} == {"empirical.figure_data_reference"}
    del figure["data_exhibit_ids"]
    figure["caption"] = "See values.csv for data"
    publish(project, branch, "P4", {"exhibits": [figure, table]}, "run.figure")
    assert artifacts_view(project, branch)["exhibits"][0]["data_source_status"] == "missing"
