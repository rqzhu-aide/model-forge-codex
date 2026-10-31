"""Real run-engine seams with scripted scientific outputs and no model calls."""
import shutil
from copy import deepcopy

import pytest

from model_forge_codex.domain import RunState
from model_forge_codex.notation import frozen_notation, retained_notation
from model_forge_codex.records import current_records, read_generation
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from test_researcher_workbench_engine import workbench, record, script_scientific_run
from test_notation_lifecycle import account, entry, updates
from test_technical_reports import report_case


@pytest.mark.asyncio
async def test_fresh_p1_final_snapshot_is_sealed_and_the_exact_p2_authorization_input(workbench):
    engine, project, _ = workbench
    from test_direct_workflow import p1_documents
    def authored(outputs):
        outputs.clear()
        outputs.update(p1_documents())
        document = outputs["p1.research_basis"]
        document["phase2_preparation"].pop("supplied_method", None)
        adopted = entry("policy", r"\pi", pointer="/research_setting/statement_markdown")
        adopted["definition_markdown"] = r"$\pi\in\Pi$ is an admissible decision policy."
        adopted["meaning_markdown"] = "The policy selects actions for the constrained control problem."
        document["notation_updates"] = updates([adopted])
    script_scientific_run(engine, project, "trunk", "P1", "p1.literature_update", transform=authored)
    run = await engine.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    await engine._tasks[run.run_id]
    final = engine.load_run("project.test", run.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    pointer = current_records(project / "branches/trunk/phases/p1")["research_basis"]
    reference = {"phase": "P1", "branch": "trunk", "family": "research_basis", **pointer}
    snapshot = retained_notation(project, reference)
    assert snapshot["entries"][0]["symbol_latex"] == r"\pi"
    directory = project / "runs" / run.run_id / "outputs" / pointer["stage_id"]
    seal = read_json(directory / "seal.json")["outputs"]
    assert seal["notation.json"]["sha256"] == sha256_file(directory / "notation.json")
    assert seal["notation.md"]["sha256"] == sha256_file(directory / "notation.md")
    p2 = engine.compute_basis("project.test", "P2", "trunk", "p2.full_catalog")
    assert frozen_notation(p2)["entries"] == snapshot["entries"]
    assert len(snapshot["entries"]) == 1  # Final view contains synthesis additions, not only input.


def test_old_catalog_basis_and_brief_do_not_gain_notation(workbench):
    engine, project, branch = workbench
    for phase in ("P1", "P2", "P3", "P4", "P5"):
        path = project / "contracts/contracts/phases" / (phase + ".json")
        contract = read_json(path)
        contract["capabilities"] = [value for value in contract.get("capabilities", [])
                                    if value not in {"project_notation_v1", "research_presentation_v2"}]
        write_json_atomic(path, contract)
    run = record(engine, branch, "run.old", "P3", "p3.theory_establishment")
    directory = engine.run_dir(run.project_id, run.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    frozen = engine.compute_basis("project.test", "P3", branch, run.mode)
    assert "notation" not in frozen
    write_json_atomic(directory / "basis.json", frozen)
    stage = engine.stage_plan("project.test", "P3", run.mode)[0]
    brief = engine._render_brief(run, stage, stage.roles[0], engine.member_workspace(run, stage.stage_id, stage.roles[0]))
    assert "Frozen scientific notation" not in brief


@pytest.mark.asyncio
async def test_p3_additions_publish_with_theory_and_cannot_adopt_study_scope(workbench):
    engine, project, branch = workbench
    def authored(outputs):
        document = outputs["p3.complete_theory"]
        adopted = entry("bound_constant", "C", {"kind": "account", "phase": "P3", "branch": branch,
                         "account_family": "complete_theory"}, "p3.complete_theory", "/statements/0/text")
        adopted["definition_markdown"] = "$C$ denotes the constant used in this account's stated bound."
        adopted["meaning_markdown"] = "Its conditions are those of the retained theoretical statement."
        document["notation_updates"] = updates([adopted])
    script_scientific_run(engine, project, branch, "P3", "p3.theory_establishment", transform=authored)
    run = await engine.start_run("project.test", phase="P3", mode="p3.theory_establishment", branch_id=branch)
    await engine._tasks[run.run_id]
    final = engine.load_run("project.test", run.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    pointer = current_records(project / "branches" / branch / "phases/p3")["theory_record"]
    snapshot = retained_notation(project, {"phase": "P3", "branch": branch, "family": "theory_record", **pointer})
    assert snapshot["entries"][0]["scope"]["method_identity"]["definition_sha256"]
    assert snapshot["account"]["method_identity"]["stable_id"]
    def invalid(outputs):
        outputs["p3.complete_theory"]["notation_updates"] = updates([entry(output="p3.complete_theory", pointer="/statements/0/text")])
    script_scientific_run(engine, project, branch, "P3", "p3.theory_revision", transform=invalid)
    failed = await engine.start_run("project.test", phase="P3", mode="p3.theory_revision", branch_id=branch)
    await engine._tasks[failed.run_id]
    state = engine.load_run("project.test", failed.run_id)
    assert state.state is RunState.FAILED
    assert current_records(project / "branches" / branch / "phases/p3")["theory_record"] == pointer


@pytest.mark.asyncio
async def test_p2_reconciliation_adopts_scoped_candidate_notation_without_rewriting_originals(workbench):
    engine, project, _ = workbench
    original_proposals = {}
    def authored(outputs):
        additions = []
        for role in ("theory", "empirical", "lead"):
            output_id = "p2." + role + "_proposal"
            proposal = outputs[output_id]
            original_proposals[output_id.split(".")[1]] = deepcopy(proposal)
            identity = proposal["method"]["identity"]
            scoped = {"kind": "method", "method_identity": {key: identity[key] for key in ("stable_id", "definition_sha256")}}
            adopted = entry("overlap_bound", r"\varepsilon", scoped, output_id,
                            "/method/mathematical_definition/canonical_definition/tuning_definition")
            adopted["definition_markdown"] = r"$\varepsilon$ is this candidate's overlap bound."
            adopted["meaning_markdown"] = "Its scientific role and permitted values remain those of this exact candidate definition."
            additions.append(adopted)
        outputs["p2.catalog_assessment"]["notation_updates"] = updates(additions)
    script_scientific_run(engine, project, "trunk", "P2", "p2.full_catalog", transform=authored)
    run = await engine.start_run("project.test", phase="P2", mode="p2.full_catalog", branch_id="trunk")
    await engine._tasks[run.run_id]
    final = engine.load_run("project.test", run.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    directory = project / "branches/trunk/phases/p2"
    pointers = current_records(directory)
    for family, expected in original_proposals.items():
        assert read_generation(directory, family, pointers[family]) == expected
    snapshot = retained_notation(project, {"phase": "P2", "branch": "trunk", "family": "catalog_assessment", **pointers["catalog_assessment"]})
    assert len(snapshot["entries"]) == 3
    assert {row["scope"]["method_identity"]["stable_id"] for row in snapshot["entries"]} == {"method.theory", "method.empirical", "method.lead"}


@pytest.mark.asyncio
async def test_progressive_p4_lead_retains_its_own_final_notation_addition(workbench):
    engine, project, branch = workbench
    def authored(outputs):
        adopted = entry("evaluation_sample_size", "n", {"kind": "account", "phase": "P4", "branch": branch,
            "account_family": "empirical_synthesis_candidate"}, "p4.empirical_synthesis_candidate", "/decision_summary")
        adopted["definition_markdown"] = "$n$ is the number of observations in an evaluated sample."
        adopted["meaning_markdown"] = "The value and evaluated regime stay with their exact numerical evidence."
        outputs["p4.empirical_synthesis_candidate"]["notation_updates"] = updates([adopted])
    script_scientific_run(engine, project, branch, "P4", "p4.preliminary", transform=authored)
    run = await engine.start_run("project.test", phase="P4", mode="p4.preliminary", branch_id=branch)
    await engine._tasks[run.run_id]
    final = engine.load_run("project.test", run.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    pointer = current_records(project / "branches" / branch / "phases/p4")["empirical_synthesis"]
    snapshot = retained_notation(project, {"phase": "P4", "branch": branch, "family": "empirical_synthesis", **pointer})
    assert snapshot["entries"][-1]["quantity_key"] == "evaluation_sample_size"
    from pathlib import Path
    from model_forge_codex.empirical_context import load_evaluation_basis
    from model_forge_codex.notation import digest, render_notation
    from model_forge_codex.records import ArtifactError
    protocol = current_records(project / "branches" / branch / "phases/p4")["protocol"]
    source = {"phase": "P4", "branch": branch, "family": "protocol", **protocol,
              "sha256": protocol["content_sha256"]}
    basis_path = project / "runs" / run.run_id / "basis.json"
    original_basis = basis_path.read_bytes()
    bound = load_evaluation_basis(project, source)
    assert bound["sha256"] == final.basis_sha256
    frozen = Path(bound["notation"]["snapshot_path"])
    readable = Path(bound["notation"]["markdown_path"])
    original_notation = frozen.read_bytes()
    original_markdown = readable.read_bytes()
    forged = read_json(frozen)
    forged["sources"] = [{"generation_id": "unadmitted.source"}]
    write_json_atomic(frozen, forged)
    with pytest.raises(ArtifactError, match="frozen notation changed"):
        load_evaluation_basis(project, source)
    bound["notation"]["sha256"] = digest(forged)
    readable.write_text(render_notation(forged), encoding="utf-8")
    bound["notation"]["markdown_sha256"] = sha256_file(readable)
    write_json_atomic(basis_path, bound)
    with pytest.raises(ArtifactError, match="frozen basis no longer matches"):
        load_evaluation_basis(project, source)
    basis_path.write_bytes(original_basis)
    frozen.write_bytes(original_notation)
    readable.write_bytes(original_markdown)
    assert load_evaluation_basis(project, source)["sha256"] == final.basis_sha256


def test_publication_rechecks_generated_final_view_and_has_no_cross_phase_notation_gate(workbench):
    engine, project, branch = workbench
    from model_forge_codex.notation import retain_account_notation
    from model_forge_codex.records import current_package_token
    run = record(engine, branch, "run.notation", "P3", "p3.theory_establishment")
    directory = engine.run_dir(run.project_id, run.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    frozen = engine.compute_basis("project.test", "P3", branch, run.mode)
    write_json_atomic(directory / "basis.json", frozen)
    write_json_atomic(directory / "publication-base.json", {"phase": "P3", "branch_id": branch,
        "token": current_package_token(project / "branches" / branch / "phases/p3")})
    # A P4 source published after authorization does not invalidate frozen P3.
    account(project, phase="P4", family="empirical_synthesis_candidate", branch=branch,
            run_id="run.p4.concurrent", additions=[], method=frozen["method"])
    assert engine._assert_publication_current(run)
    assert frozen_notation(read_json(directory / "basis.json")) == frozen_notation(frozen)
    stage_id = "p3.synthesis"
    document = {"scientific_definition": "The constant belongs to the stated bound.",
                "notation_updates": updates([entry("constant", "C", {"kind": "account", "phase": "P3",
                    "branch": branch, "account_family": "complete_theory"}, "p3.complete_theory")])}
    output_id = "p3.complete_theory"
    current = {output_id: (document, stage_id)}
    generated, paths = retain_account_notation(project, directory, "P3", branch, stage_id, document,
                                               "complete_theory", frozen, current)
    write_json_atomic(directory / "stage-plan.json", [{"stage_id": stage_id, "writes": [output_id]}])
    write_json_atomic(directory / "outputs" / stage_id / "complete_theory.json", generated)
    roots = {output_id: directory / "outputs" / stage_id}
    assert engine._notation_findings(run, {output_id: generated}, roots, require_retained=True) == []
    paths[0].write_text('{"entries": []}', encoding="utf-8")
    failures = engine._notation_findings(run, {output_id: generated}, roots, require_retained=True)
    assert failures[0].code == "notation.invalid_account"


def test_notation_validation_uses_exact_correction_revision_accepted_during_continuation(workbench):
    from model_forge_codex.notation import build_account_notation, digest, retain_account_notation
    from model_forge_codex.records import ArtifactError
    from model_forge_codex.researcher_pause import ResearcherPauseStore
    from test_notation_lifecycle import local
    engine, project, branch = workbench
    method = engine.compute_basis("project.test", "P3", branch)["method"]
    source, snapshot, source_document = account(project, phase="P3", family="complete_theory", branch=branch,
        run_id="run.p3.original", additions=[local("P3", branch=branch)], method=method,
        extra={"method_identity": method["identity"]})
    current = record(engine, branch, "run.p3.continued", "P3", "p3.theory_revision")
    directory = engine.run_dir(current.project_id, current.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    frozen = engine.compute_basis("project.test", "P3", branch, current.mode)
    target = {**source, "kind": "notation_entry", "entry_id": snapshot["entries"][0]["entry_id"],
              "snapshot_sha256": source_document["notation_snapshot"]["sha256"]}
    original = {"item_id": "context.notation.local", "revision": 1, "topic": "notation_correction", "scope": {"kind": "project"},
                "status": "confirmed", "origin": "researcher_reported", "statement": "Explain the bound.", "source_refs": [target]}
    accepted = {**deepcopy(original), "revision": 2, "statement": "Keep the exact stated bound conditions."}
    frozen["problem_context"].update(items=[original], notation_correction_refs=[
        {"context_id": original["item_id"], "revision": 1, "sha256": digest(original)}])
    write_json_atomic(directory / "basis.json", frozen)
    pause = ResearcherPauseStore(directory)
    state = pause.snapshot()
    state["continuations"] = [{"accepted_context_items": [accepted]}]
    write_json_atomic(pause.path, state)
    document = {"scientific_definition": "The definition remains unchanged.", "notation_updates": updates()}
    document["notation_updates"]["correction_dispositions"] = [{
        "correction_ref": {"context_id": accepted["item_id"], "revision": 2, "sha256": digest(accepted)},
        "disposition": "unchanged", "reason_markdown": "The retained conditions already state the intended scope."}]
    stage = "p3.synthesis"
    documents = {"p3.complete_theory": (document, stage)}
    with pytest.raises(ArtifactError, match="exact admitted saved correction"):
        build_account_notation(project, directory, "P3", branch, stage, document, "complete_theory", frozen, documents)
    generated, _ = retain_account_notation(project, directory, "P3", branch, stage, document, "complete_theory",
                                            pause.context_basis(current), documents)
    root = directory / "outputs" / stage
    write_json_atomic(root / "complete_theory.json", generated)
    write_json_atomic(directory / "stage-plan.json", [{"stage_id": stage, "writes": ["p3.complete_theory"]}])
    assert engine._notation_findings(current, {"p3.complete_theory": generated}, {"p3.complete_theory": root}, require_retained=True) == []
    assert read_json(directory / "basis.json") == frozen


@pytest.mark.parametrize("replace", [False, True])
def test_p5_review_freezes_candidate_added_notation_and_revision_retains_or_clarifies_it(workbench, report_case, replace):
    import json
    from pathlib import Path
    from model_forge_codex.notation import retain_account_notation, freeze_notation_inputs
    from model_forge_codex.p5_review_packet import prepare_review_packet
    from model_forge_codex.records import generation_path, publish_package
    from test_notation_lifecycle import local
    engine, project, branch = workbench
    report = deepcopy(report_case[0])
    producer_basis = engine.compute_basis("project.test", "P5", branch, "p5.assembly")
    report["method_identity"] = deepcopy(producer_basis["method"]["identity"])
    context = producer_basis["problem_context"]
    report["problem_context_ref"] = {"revision": context["revision"], "sha256": context["sha256"]}
    definition = r"$\kappa$ is the bandwidth used in this report's exposition."
    report["claims"] = [{"claim_id": "claim.notation", "text": definition, "anchor": "scientific_model",
                         "support_route": "model_description", "source_refs": []}]
    addition = local("P5", "report_bandwidth", branch=branch)
    addition.update(definition_markdown=definition, source_refs=[{"output_id": "p5.technical_report_candidate", "pointer": "/claims/0/text"}])
    report["notation_updates"] = updates([addition])
    producer = project / "runs/run.p5.assembly"
    stage = "p5.assembly_lead"
    candidate, _ = retain_account_notation(project, producer, "P5", branch, stage, report, "technical_report_candidate",
        producer_basis, {"p5.technical_report_candidate": (report, stage)})
    output = producer / "outputs" / stage
    (output / "report.md").write_bytes((next(iter(report_case[2].values())) / "report.md").read_bytes())
    write_json_atomic(producer / "basis.json", producer_basis)
    phase = project / "branches" / branch / "phases/p5"
    raw = json.dumps(candidate).encode()
    package = publish_package(phase, {"technical_report": raw, "technical_report_candidate": raw}, run_id=producer.name, phase="P5", branch_id=branch,
        metadata={"stage_ids": {family: stage for family in ("technical_report", "technical_report_candidate")}})
    original = {"phase": "P5", "branch": branch, "family": "technical_report", **package["records"]["technical_report"]}
    original_view = retained_notation(project, original)
    review_basis = engine.compute_basis("project.test", "P5", branch, "p5.review_revision")
    assert frozen_notation(review_basis)["entries"][-1]["entry_id"] == original_view["entries"][-1]["entry_id"]
    for reference in review_basis["records"]:
        reference["snapshot_path"] = str(generation_path(project / "branches" / reference["branch"] / "phases" / reference["phase"].lower(), reference["family"], reference))
    review_basis["artifacts"] = [{"path": str(path), "content_sha256": sha256_file(path)}
                                for path in (output / "report.md", output / "notation.json", output / "notation.md")]
    review = project / "runs/run.p5.review"
    freeze_notation_inputs(review, review_basis)
    packet = prepare_review_packet(review, basis=review_basis, instructions="Check the submitted symbols.", run_id=review.name, project_dir=project)
    materials = read_json(review / "review-packet/materials.json")["materials"]
    submitted = next(row for row in materials if row["authored_path"] == "notation.json")
    reviewed_path = review / "review-packet" / submitted["submitted_name"]
    reviewed_bytes = reviewed_path.read_bytes()
    assert read_json(reviewed_path) == original_view
    revision = deepcopy(candidate)
    revision["notation_updates"] = updates()
    if replace:
        clarification = deepcopy(addition)
        clarification.update(symbol_latex=r"\zeta", replaces={"snapshot_sha256": candidate["notation_snapshot"]["sha256"],
            "entry_id": original_view["entries"][-1]["entry_id"]})
        revision["notation_updates"]["entries"] = [clarification]
    final, _ = retain_account_notation(project, review, "P5", branch, "p5.revision_lead", revision, "technical_report_candidate",
        review_basis, {"p5.technical_report_candidate": (revision, "p5.revision_lead")})
    revised_view = read_json(review / "outputs/p5.revision_lead/notation.json")
    assert revised_view["entries"][-1]["symbol_latex"] == (r"\zeta" if replace else r"\kappa")
    assert revised_view["entries"][-1]["account_scope_ref"] == original_view["entries"][-1]["account_scope_ref"]
    assert revised_view["entries"][0]["status"] == ("retired" if replace else "active")
    final_raw = json.dumps(final).encode()
    committed = publish_package(phase, {"technical_report": final_raw, "technical_report_candidate": final_raw},
        run_id=review.name, phase="P5", branch_id=branch,
        metadata={"stage_ids": {family: "p5.revision_lead" for family in ("technical_report", "technical_report_candidate")}})
    final_ref = {"phase": "P5", "branch": branch, "family": "technical_report", **committed["records"]["technical_report"]}
    assert retained_notation(project, final_ref) == revised_view
    assert reviewed_path.read_bytes() == reviewed_bytes and retained_notation(project, original) == original_view


@pytest.mark.asyncio
async def test_targeted_advice_uses_final_synthesis_additions_from_exact_source_package(workbench, monkeypatch):
    engine, project, branch = workbench
    from model_forge_codex.phase_interactions import published_issues
    from test_notation_lifecycle import local
    original = engine.compute_basis("project.test", "P3", branch, "p3.theory_establishment")
    assert frozen_notation(original)["entries"] == []
    source, final_snapshot, _ = account(project, phase="P3", family="complete_theory", branch=branch,
        run_id="run.source", method=original["method"], additions=[local("P3", "final_constant", branch=branch)],
        siblings={"analyst_audit": {"issues": [{"issue_id": "issue.exact", "title": "The bound needs interpretation.",
                    "issue": "Explain the constant in the retained bound.", "raised_by": "data_analyst"}]}})
    source_dir = project / "runs/run.source"
    shutil.copytree(project / "contracts", source_dir / "contracts")
    write_json_atomic(source_dir / "basis.json", original)
    issue = next(item for item in published_issues(project) if item.get("object_id") == "issue.exact")
    # A later P3 account must not supply a similarly named definition.
    account(project, phase="P3", family="complete_theory", branch=branch,
            run_id="run.newer", method=original["method"], additions=[local("P3", "different_constant", symbol="B", branch=branch)])
    async def no_work(*args):
        return None
    monkeypatch.setattr(engine, "_drive", no_work)
    run = await engine.start_run("project.test", phase="P3", mode="explanation", branch_id=branch,
        intent="assessment", assessment_purpose="issue_suggestions", target=issue["explanation_target"],
        instructions="What does this constant mean?")
    await engine._tasks[run.run_id]
    frozen = read_json(engine.run_dir("project.test", run.run_id) / "basis.json")
    assert frozen_notation(frozen) == final_snapshot
    assert frozen_notation(frozen)["entries"][0]["quantity_key"] == "final_constant"
    assert frozen_notation(frozen)["account"]["run_id"] == source["run_id"]
