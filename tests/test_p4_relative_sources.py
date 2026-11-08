"""P4 relative citations retain exact publication, stage and digest boundaries."""
import copy
import json

import pytest

from model_forge_codex.records import publish_package
from model_forge_codex.research import artifacts_view, scientific_document_view, source_ref
from model_forge_codex.research_sources import empirical_account_sources, empirical_run_sources
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from test_p4_run_sources import retained_sources


def relative_sources(project, *, duplicate_copy=False):
    run, docs, records, _, primary = retained_sources(project)
    stage = primary.parents[2]
    summary = primary.parent / "analysis/summary.json"
    summary.parent.mkdir()
    summary.write_text('{"completed":60}', encoding="utf-8")
    metrics = stage / "metrics_long.jsonl"
    metrics.write_text('{"returned":true}\n', encoding="utf-8")
    table = stage / "exhibit-artifacts/retained-safety.json"
    table.parent.mkdir()
    table.write_text('{"rows":[{"completed":60}]}', encoding="utf-8")
    authored = [{"exhibit_id": "exhibit.safety", "artifact_path": "tables/return_safety.json", "artifact_sha256": sha256_file(table)}]
    display = [{**authored[0], "artifact_path": "exhibit-artifacts/retained-safety.json", "title": "Return and safety"}]
    manifest = primary.parent / "exhibits.json"
    write_json_atomic(manifest, authored)
    docs["exhibits"] = display
    docs["metrics_long"] = [{"returned": True}]
    docs["protocol"].update(plan_revision_id="plan.current", work_items=[{"work_item_id": "work.analysis"}])
    docs["analyst_synthesis"] = {"title": "Fresh account", "representations": [],
        "summary_markdown": "Fresh larger-count returns. [Return and safety](tables/return_safety.json).",
        "experimental_setting_markdown": "Sixty independent learning datasets. [Exact summaries](analysis/summary.json) [Rows](metrics_long.jsonl) [Protocol](protocol.json).",
        "question_results": [{"question_id": "question.one", "answer_markdown": "The method returned on 60 datasets."}],
        "retained_outputs": [{"path": "analysis/summary.json", "sha256": sha256_file(summary)}]}
    if duplicate_copy:
        original = primary.parent / authored[0]["artifact_path"]
        original.parent.mkdir()
        original.write_bytes(table.read_bytes())
        docs["analyst_synthesis"]["retained_outputs"].append(
            {"path": authored[0]["artifact_path"], "sha256": sha256_file(original)})
        docs["analyst_synthesis"]["question_results"][0]["answer_markdown"] += " [Accounting](tables/return_safety.json)."
    raw = {family: json.dumps(doc).encode() for family, doc in docs.items()}
    raw["metrics_long"] = metrics.read_bytes()
    stages = {family: meta["generation_ref"]["stage_id"] for family, (_, meta) in records.items()}
    stages.update(exhibits="p4.analyst", metrics_long="p4.analyst")
    for family, content in raw.items():
        name = "empirical_synthesis_candidate.json" if family == "empirical_synthesis" else family + (".jsonl" if family == "metrics_long" else ".json")
        target = run / "outputs" / stages[family] / name
        target.write_bytes(content)
        seal = read_json(target.parent / "seal.json") or {"outputs": {}}
        seal["outputs"][name] = {"sha256": sha256_file(target)}
        write_json_atomic(target.parent / "seal.json", seal)
    seal = read_json(stage / "seal.json")
    seal["outputs"].update({"working/data_analyst/exhibits.json": {"sha256": sha256_file(manifest)},
                            "exhibit-artifacts/retained-safety.json": {"sha256": sha256_file(table)}})
    write_json_atomic(stage / "seal.json", seal)
    package = publish_package(project / "branches/method.a/phases/p4", raw, run_id=run.name, phase="P4", branch_id="method.a",
                              metadata={"stage_ids": stages, "formats": {"metrics_long": "jsonl"}})
    records = {family: (doc, {"generation_ref": source_ref("method.a", "P4", family, package["records"][family])}) for family, doc in docs.items()}
    return run, docs, records, summary, table, manifest


@pytest.mark.parametrize("reverse", [False, True])
def test_identical_working_and_relocated_exhibit_copies_open_the_exact_published_table(tmp_path, reverse):
    _, docs, records, _, table, _ = relative_sources(tmp_path, duplicate_copy=True)
    if reverse:
        records = dict(reversed(records.items()))
    before = copy.deepcopy(records)
    links = empirical_run_sources(tmp_path, docs["analyst_synthesis"], records["analyst_synthesis"][1], records)
    linked = next(link for link in links if link["uri"] == "tables/return_safety.json")
    expected = {**records["exhibits"][1]["generation_ref"], "entry_pointer": "/0"}
    assert linked["exhibit_ref"] == expected
    assert linked["sha256"] == sha256_file(table)
    assert "path=exhibit-artifacts%2Fretained-safety.json" in linked["artifact_url"]
    ref = records["analyst_synthesis"][1]["generation_ref"]
    opened = scientific_document_view(tmp_path, "method.a", "P4", "analyst_synthesis", ref["generation_id"],
                                      entry_pointer="/question_results/0")
    assert next(link for link in opened["inline_sources"] if link["uri"] == linked["uri"]) == linked
    exhibit = scientific_document_view(tmp_path, "method.a", "P4", "exhibits", expected["generation_id"],
                                       entry_pointer=expected["entry_pointer"])["exhibit"]
    assert exhibit["source_verified"] is True
    assert records == before


def test_another_stage_cannot_share_a_relative_exhibit_alias_even_with_identical_bytes(tmp_path):
    run, docs, records, _, table, _ = relative_sources(tmp_path, duplicate_copy=True)
    other = run / "outputs/p4.theorist/working/data_analyst/tables/return_safety.json"
    other.parent.mkdir(parents=True)
    other.write_bytes(table.read_bytes())
    docs["theory_audit"]["retained_outputs"] = [{"path": "tables/return_safety.json", "sha256": sha256_file(other)}]
    links = empirical_run_sources(tmp_path, docs["analyst_synthesis"], records["analyst_synthesis"][1], records)
    assert "tables/return_safety.json" not in {link["uri"] for link in links}


def test_full_structured_analyst_account_links_to_exact_package_and_sealed_relocated_table(tmp_path):
    run, docs, records, summary, _, _ = relative_sources(tmp_path)
    before = copy.deepcopy(records)
    links = empirical_account_sources(tmp_path, docs["analyst_synthesis"], records["analyst_synthesis"][1])
    assert {link["uri"] for link in links} == {"tables/return_safety.json", "analysis/summary.json", "metrics_long.jsonl", "protocol.json"}
    assert all(link["source_verified"] and link["sha256"] in link["artifact_url"] for link in links)
    assert "path=exhibit-artifacts%2Fretained-safety.json" in next(link for link in links if link["uri"].startswith("tables/"))["artifact_url"]
    assert next(link for link in links if link["uri"] == "analysis/summary.json")["sha256"] == sha256_file(summary)
    opened = scientific_document_view(tmp_path, "method.a", "P4", "analyst_synthesis", records["analyst_synthesis"][1]["generation_ref"]["generation_id"])
    assert opened["structured"] == docs["analyst_synthesis"] and opened["inline_sources"] == links
    question = artifacts_view(tmp_path, "method.a")["questions"][0]
    assert question["result"]["has_full_analyst_account"] is True
    assert question["result"]["generation_ref"] == records["analyst_synthesis"][1]["generation_ref"]
    assert records == before


@pytest.mark.parametrize("damage", ["changed_summary", "undeclared_summary", "foreign_package", "unpublished", "conflicting_summary", "changed_manifest", "unsealed_manifest", "changed_table", "only_other_role_summary"])
def test_relative_sources_do_not_guess_or_substitute_missing_changed_or_foreign_files(tmp_path, damage):
    run, docs, records, summary, table, manifest = relative_sources(tmp_path)
    missing = "analysis/summary.json"
    if damage == "changed_summary":
        summary.write_text("{}")
    elif damage == "undeclared_summary":
        docs["analyst_synthesis"].pop("retained_outputs")
    elif damage == "foreign_package":
        records["analyst_synthesis"][1]["generation_ref"]["package_id"] = "package.other"
    elif damage == "unpublished":
        write_json_atomic(run / "run.json", {"state": "running", "branch_id": "method.a", "phase": "P4"})
    elif damage == "conflicting_summary":
        docs["analyst_synthesis"]["retained_outputs"].append({"path": missing, "sha256": "f" * 64})
    elif damage == "changed_manifest":
        manifest.write_text("[]")
        missing = "tables/return_safety.json"
    elif damage == "unsealed_manifest":
        path = run / "outputs/p4.analyst/seal.json"
        seal = read_json(path)
        del seal["outputs"]["working/data_analyst/exhibits.json"]
        write_json_atomic(path, seal)
        missing = "tables/return_safety.json"
    elif damage == "only_other_role_summary":
        other = run / "outputs/p4.theorist/working/data_analyst/analysis/summary.json"
        other.parent.mkdir(parents=True)
        other.write_bytes(summary.read_bytes())
        summary.unlink()
    else:
        table.write_text("{}")
        missing = "tables/return_safety.json"
    links = empirical_run_sources(tmp_path, docs["analyst_synthesis"], records["empirical_synthesis"][1], records)
    assert missing not in {link["uri"] for link in links}


def test_relative_traversal_and_same_basename_are_not_aliases(tmp_path):
    _, _, records, _, _, _ = relative_sources(tmp_path)
    document = {"summary_markdown": "[Private](../analysis/summary.json) [Guess](summary.json) [Drive](C:/private/summary.json) [Unbound](unknown.json)"}
    assert not {"../analysis/summary.json", "summary.json", "C:/private/summary.json", "unknown.json"}.intersection(
        link["uri"] for link in empirical_run_sources(tmp_path, document, records["analyst_synthesis"][1], records))
    assert empirical_account_sources(tmp_path, document, {"generation_ref": {**records["analyst_synthesis"][1]["generation_ref"], "package_id": "package.foreign"}}) == []


@pytest.mark.parametrize("damage", [None, "published_amendment", "failed", "wrong_revision", "unknown_work", "unrequested_result", "changed_retained", "outside_batch", "changed_stage", "only_other_stage", "conflicting_digest", "traversal"])
def test_unpromoted_relative_citation_requires_accepted_batch_and_exact_same_stage_copy(tmp_path, damage):
    run, _, records, summary, _, _ = relative_sources(tmp_path)
    uri = "tables/complete_quality.json"
    stage_file = summary.parents[1] / uri
    stage_file.parent.mkdir(parents=True, exist_ok=True)
    stage_file.write_text('{"means":[0.38,0.19]}', encoding="utf-8")
    digest = sha256_file(stage_file)
    retained = run / "p4-execution/batches/attempt.analysis/artifacts" / uri
    retained.parent.mkdir(parents=True)
    retained.write_bytes(stage_file.read_bytes())
    batch = {"attempt_id": "attempt.analysis", "work_item_id": "work.analysis", "plan_revision_id": "plan.current",
             "status": "completed", "exit_code": 0, "result_paths": [uri],
             "artifacts": [{"source_path": uri, "path": str(retained), "sha256": digest}]}
    if damage == "published_amendment":
        protocol = records["protocol"][0]
        protocol.update(work_items=[], amendments=[{"revision_id": "plan.amended", "added_work_items": [{"work_item_id": "work.analysis"}]}])
        batch["plan_revision_id"] = "plan.amended"
    elif damage == "failed":
        batch.update(status="failed", exit_code=1)
    elif damage == "wrong_revision":
        batch["plan_revision_id"] = "plan.other"
    elif damage == "unknown_work":
        batch["work_item_id"] = "work.undeclared"
    elif damage == "unrequested_result":
        batch["result_paths"] = []
    elif damage == "changed_retained":
        retained.write_text("{}")
    elif damage == "outside_batch":
        batch["artifacts"][0]["path"] = str(stage_file)
    elif damage == "changed_stage":
        stage_file.write_text("{}")
    elif damage == "only_other_stage":
        other = run / "outputs/p4.theorist/working/data_analyst" / uri
        other.parent.mkdir(parents=True)
        other.write_bytes(stage_file.read_bytes())
        stage_file.unlink()
    elif damage == "conflicting_digest":
        batch["artifacts"].append({"source_path": uri, "path": str(retained), "sha256": "f" * 64})
    elif damage == "traversal":
        uri = "tables/../tables/complete_quality.json"
        batch["artifacts"][0]["source_path"] = uri
        batch["result_paths"] = [uri]
    write_json_atomic(run / "p4-execution/state.json", {"ledger": [batch]})
    before = copy.deepcopy(records)
    links = empirical_run_sources(tmp_path, {"summary_markdown": f"[Complete marginal quality]({uri})"}, records["empirical_synthesis"][1], records)
    matches = [link for link in links if link["uri"] == uri]
    if damage not in (None, "published_amendment"):
        assert matches == []
    else:
        assert len(matches) == 1 and matches[0]["sha256"] == digest
        assert "path=working%2Fdata_analyst%2Ftables%2Fcomplete_quality.json" in matches[0]["artifact_url"]
    assert records == before
