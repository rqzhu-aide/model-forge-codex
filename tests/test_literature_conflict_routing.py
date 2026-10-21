"""Citation conflicts identify their original owners without adjudicating them."""
from copy import deepcopy
import json

from model_forge_codex.browse import correction_preview
from model_forge_codex.direct_validation import validate_direct_outputs
from model_forge_codex.domain import RunState
from model_forge_codex.literature import build_library, source_identity_conflicts
from model_forge_codex.storage import read_json, write_json_atomic
from test_direct_workflow import PID, direct_engine, p1_documents, script


def paper(source_id, *, title=None, authors=None, locator=None, extra_identifiers=()):
    entry = deepcopy(p1_documents((source_id,))["p1.lead_literature"]["papers"][0])
    source = entry["source"]
    if title:
        source["title"] = title
    if authors:
        source["authors"] = authors
    if locator:
        source["identifiers"] = [{"kind": "doi", "value": locator}]
    source["identifiers"] += list(extra_identifiers)
    return entry


def collection(*papers):
    return {"papers": list(papers)}


def test_all_collision_groups_keep_exact_entry_ownership_and_shared_identifiers():
    book = paper("source.book", title="Constrained control book", authors=["Book Author"])
    wrong_book = deepcopy(book)
    wrong_book["source"]["identifiers"].append({"kind": "url", "value": "https://arxiv.org/abs/2101.10895"})
    citing_paper = paper("source.citing", title="A different primal dual paper", authors=["Paper Author"],
                         extra_identifiers=[{"kind": "arxiv", "value": "2101.10895v2"}])
    ordered = paper("source.order", authors=["First Author", "Second Author"])
    reordered = deepcopy(ordered)
    reordered["source"]["authors"].reverse()
    spelling = paper("source.spelling", authors=["Unaccented Name"])
    accented, expanded = deepcopy(spelling), deepcopy(spelling)
    accented["source"]["authors"] = ["Accénted Name"]
    expanded["source"]["authors"] = ["Expanded Given Name"]
    outputs = {"p1.lead_literature": collection(book, ordered, spelling),
               "p1.theory_literature": collection(wrong_book, citing_paper, accented),
               "p1.empirical_literature": collection(reordered, expanded)}
    before = deepcopy(outputs)
    findings = validate_direct_outputs("P1", outputs)
    assert outputs == before and len(findings) == 10
    assert {finding.code for finding in findings} == {"literature.source_identity_conflict"}
    assert {finding.object_id for finding in findings} == set(outputs)
    book_findings = [finding for finding in findings if "arxiv:2101.10895" in finding.message]
    assert {(finding.object_id, finding.json_pointer) for finding in book_findings} == {
        ("p1.theory_literature", "/papers/0/source"), ("p1.theory_literature", "/papers/1/source")}
    assert all("source.book" in finding.message and "source.citing" in finding.message
               and "record.source.book" in finding.message and "record.source.citing" in finding.message
               for finding in book_findings)
    assert all("does not decide which record is correct" in finding.message for finding in findings)


def test_existing_identifier_equivalence_and_bibliographic_rules_are_preserved():
    original = paper("source.original")["source"]
    equivalent = deepcopy(original)
    equivalent.update(source_id="source.alias", record_id="record.alias",
                      title="  " + original["title"].upper() + "  ", authors=[name.upper() for name in original["authors"]])
    equivalent["identifiers"] = [{"kind": "url", "value": "https://doi.org/" + original["identifiers"][0]["value"]}]
    assert source_identity_conflicts([original, equivalent]) == []
    assert build_library(None, [original, equivalent], run_id="run.test")["total_sources"] == 1
    unrelated = deepcopy(original)
    unrelated.update(source_id="source.different", record_id="record.different", identifiers=[{"kind": "doi", "value": "10.1234/different"}])
    assert source_identity_conflicts([original, unrelated]) == []
    reused = deepcopy(unrelated)
    reused["source_id"] = original["source_id"]
    conflicts = source_identity_conflicts([original, reused])
    assert len(conflicts) == 1 and "different DOI identifiers" in conflicts[0]["reasons"]


def test_preview_resolves_real_frozen_stages_and_retains_exact_source_pointers(tmp_path):
    write_json_atomic(tmp_path / "stage-plan.json", {"stages": [
        {"stage_id": "p1.discovery", "writes": ["p1.theory_literature", "p1.empirical_literature"]},
        {"stage_id": "p1.lead_synthesis", "writes": ["p1.research_basis"]}]})
    record = {"run_id": "run.test", "state": "failed", "findings_history": [[
        {"object_id": "p1.theory_literature", "json_pointer": "/papers/2/source"},
        {"object_id": "p1.theory_literature", "json_pointer": "/papers/2/source"},
        {"object_id": "p1.empirical_literature", "json_pointer": "/papers/4/source"}]]}
    preview = correction_preview(tmp_path, tmp_path, record)
    assert preview["affected_stages"] == {"p1.discovery": ["/papers/2/source", "/papers/4/source"]}


async def test_source_correction_reaches_original_member_then_refreshes_synthesis(direct_engine):
    engine, project = direct_engine
    engine._MAX_MECHANICAL_REPAIRS = 0  # This test authorizes the correction explicitly.
    documents = p1_documents()
    theory = deepcopy(documents["p1.lead_literature"]["papers"][0])
    theory["source"].update(source_id="citation.wrong", record_id="record.wrong", title="An unrelated work")
    documents["p1.lead_literature"]["papers"][0]["source"]["identifiers"].append({"kind": "pmid", "value": "101"})
    theory["source"]["identifiers"].append({"kind": "pmid", "value": "999"})
    theory["entry_id"] = "entry.wrong"
    documents["p1.theory_literature"]["papers"] = [theory]
    script(engine, "P1", "p1.literature_update", documents)
    run = await engine.start_run(PID, phase="P1", mode="p1.literature_update", branch_id="trunk")
    await engine._tasks[run.run_id]
    failed = engine.load_run(PID, run.run_id)
    assert failed.state is RunState.FAILED
    assert failed.stage_states == {"p1.discovery": "failed", "p1.lead_synthesis": "pending"}
    findings = failed.findings_history[-1]
    assert {finding["object_id"] for finding in findings} == {"p1.lead_literature", "p1.theory_literature"}
    assert {finding["code"] for finding in findings} == {"literature.source_identity_conflict"}
    directory = engine.run_dir(PID, run.run_id)
    before = (directory / "outputs/p1.discovery/empirical_literature.json").read_bytes()
    fixed_theory = deepcopy(documents["p1.theory_literature"])
    fixed_theory["papers"][0]["source"]["identifiers"] = [{"kind": "doi", "value": "10.1234/unrelated"}]
    def response(family, document):
        return "ok", {family + ".json": json.dumps(document)}
    engine.bridge.script_thread("research_lead:PROJECT:trunk", [
        response("lead_literature", documents["p1.lead_literature"]),
        response("research_basis", documents["p1.research_basis"])])
    engine.bridge.script_thread("theorist:P1:trunk", [response("theory_literature", fixed_theory)])
    turn_count = len(engine.bridge.turns)
    await engine.correct(PID, run.run_id, "Check the conflicting source identities; preserve the unrelated collection.")
    await engine._tasks[run.run_id]
    final = engine.load_run(PID, run.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    assert final.correction_scope == ["p1.lead_literature", "p1.theory_literature"]
    assert len(engine.bridge.turns) == turn_count + 3
    assert (directory / "outputs/p1.discovery/empirical_literature.json").read_bytes() == before
    assert read_json(directory / "attempts/original/outputs/p1.discovery/theory_literature.json") == documents["p1.theory_literature"]
