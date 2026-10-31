"""Scientific source admission and retained notation lifecycle, without models."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from model_forge_codex.notation import (
    build_account_notation, collect_notation_inputs, digest, freeze_notation_inputs,
    frozen_notation, notation_brief, notation_enabled, render_notation, retain_account_notation,
    retained_notation, resolve_notation_entry,
)
from model_forge_codex.records import ArtifactError, current_package_token, publish_package
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic


METHOD = {"identity": {"stable_id": "method.one", "version": 1, "definition_sha256": "a" * 64}}


def updates(entries=()):
    return {"incoming_sources": [], "entries": list(entries), "retirements": [], "correction_dispositions": []}


def entry(key="target", symbol=r"\mu_D", scope=None, output="p1.research_basis", pointer="/scientific_definition"):
    return {"quantity_key": key, "symbol_latex": symbol,
            "definition_markdown": r"$\mu_D=\mathbb E[\mu_i]$ is the donor-weighted population mean.",
            "meaning_markdown": "Each donor receives equal weight. Measurement units remain unknown.",
            "scope": scope or {"kind": "study"},
            "source_refs": [{"output_id": output, "pointer": pointer}]}


def basis(snapshot=None, refs=(), method=None, branch="trunk"):
    snapshot = snapshot or {"schema_version": "1.0.0", "sources": [], "entries": []}
    return {"notation": {"document": deepcopy(snapshot), "sha256": digest(snapshot)},
            "records": list(refs), "method": method, "basis_branch": branch}


def account(project, *, phase="P1", family="research_basis", branch="trunk", run_id="run.p1",
            incoming=None, additions=None, method=None, publish=True, extra=None, siblings=None):
    directory = project / "runs" / run_id
    stage = phase.lower() + ".synthesis"
    document = {"scientific_definition": r"$\mu_D=\mathbb E[\mu_i]$.",
                "notation_updates": updates([entry()] if additions is None else additions), **(extra or {})}
    incoming_basis = basis(incoming, method=method, branch=branch)
    current = {phase.lower() + "." + family: (document, stage)}
    if method:
        current["p2.method_catalog"] = ({"methods": [method]}, "p2.reconcile")
    generated, paths = retain_account_notation(project, directory, phase, branch, stage,
                                               document, family, incoming_basis, current)
    write_json_atomic(directory / "outputs" / stage / (family + ".json"), generated)
    snapshot = read_json(paths[0])
    if not publish:
        return generated, snapshot, incoming_basis, current
    package = publish_package(project / "branches" / branch / "phases" / phase.lower(),
        {family: json.dumps(generated).encode(), **{key: json.dumps(value).encode() for key, value in (siblings or {}).items()}},
        run_id=run_id, phase=phase, branch_id=branch,
        metadata={"stage_ids": {family: stage}})
    reference = {"phase": phase, "branch": branch, "family": family, **package["records"][family]}
    return reference, snapshot, generated


def test_p1_core_becomes_exact_frozen_p2_input_and_later_rerun_keeps_additions(tmp_path):
    reference, first, _ = account(tmp_path)
    incoming = collect_notation_inputs(tmp_path, [reference], None, "P2")
    assert incoming["entries"] == first["entries"]
    frozen = basis(incoming)
    freeze_notation_inputs(tmp_path / "runs/run.p2", frozen)
    assert read_json(Path(frozen["notation"]["snapshot_path"])) == incoming
    assert frozen_notation(frozen)["entries"][0]["definition_ref"] == first["entries"][0]["definition_ref"]
    assert Path(frozen["notation"]["markdown_path"]).read_text(encoding="utf-8") == render_notation(incoming)
    account(tmp_path, run_id="run.p1.new", incoming=collect_notation_inputs(tmp_path, [reference], None, "P1"),
            additions=[entry("sample_size", "n")])
    assert frozen_notation(frozen) == incoming
    # Historical account still has its own final view, including its additions.
    assert retained_notation(tmp_path, reference) == first


def test_empty_first_p1_and_old_records_do_not_invent_a_core(tmp_path):
    reference, snapshot, _ = account(tmp_path, additions=[])
    assert snapshot["entries"] == []
    package = publish_package(tmp_path / "branches/trunk/phases/p1", {"research_basis": b'{"old_prose":"mu means something"}'},
                              run_id="run.old", phase="P1", branch_id="trunk")
    old = {"phase": "P1", "branch": "trunk", "family": "research_basis", **package["records"]["research_basis"]}
    assert retained_notation(tmp_path, old) is None
    assert collect_notation_inputs(tmp_path, [old], None, "P2")["entries"] == []


def test_member_brief_includes_complete_shared_and_selected_method_definitions(tmp_path):
    core_ref, _, _ = account(tmp_path)
    method_scope = {"kind": "method", "method_identity": {
        "stable_id": METHOD["identity"]["stable_id"], "definition_sha256": "a" * 64}}
    tuning = entry("tuning", r"\lambda", method_scope, "p2.catalog_assessment")
    tuning["definition_markdown"] = r"$\lambda$ controls regularization strength."
    method_ref, _, _ = account(tmp_path, phase="P2", family="catalog_assessment", run_id="run.p2", method=METHOD,
        incoming=collect_notation_inputs(tmp_path, [core_ref], None, "P2"), additions=[tuning])
    proof = local("P3", "proof_constant")
    proof["definition_markdown"] = r"$\kappa$ bounds the proof remainder."
    proof_ref, _, _ = account(tmp_path, phase="P3", family="complete_theory", branch="method.one", run_id="run.p3",
        method=METHOD, incoming=collect_notation_inputs(tmp_path, [core_ref, method_ref], METHOD, "P3"), additions=[proof])
    frozen = basis(collect_notation_inputs(tmp_path, [core_ref, method_ref, proof_ref], METHOD, "P5"), method=METHOD)
    freeze_notation_inputs(tmp_path / "runs/run.p5", frozen)
    brief = notation_brief(frozen)
    assert entry()["definition_markdown"] in brief
    assert tuning["definition_markdown"] in brief
    assert tuning["meaning_markdown"] in brief
    assert proof["definition_markdown"] not in brief
    assert proof["definition_markdown"] in Path(frozen["notation"]["markdown_path"]).read_text(encoding="utf-8")
    assert notation_brief({}) == ""


def local(phase, key="local", symbol=r"\kappa", family=None, branch="method.one"):
    family = family or {"P3": "complete_theory", "P4": "empirical_synthesis_candidate", "P5": "technical_report_candidate"}[phase]
    return entry(key, symbol, {"kind": "account", "phase": phase, "branch": branch,
                 "account_family": family}, phase.lower() + "." + family)


def test_concurrent_source_local_collisions_survive_for_p5_without_global_winner(tmp_path):
    core_ref, _, _ = account(tmp_path)
    common = collect_notation_inputs(tmp_path, [core_ref], METHOD, "P3")
    theory_ref, theory, _ = account(tmp_path, phase="P3", family="complete_theory", branch="method.one", run_id="run.p3",
                                   incoming=common, additions=[local("P3", "moment_bound")], method=METHOD)
    p3_token = current_package_token(tmp_path / "branches/method.one/phases/p3")
    numerical_ref, numerical, _ = account(tmp_path, phase="P4", family="empirical_synthesis_candidate", branch="method.one", run_id="run.p4",
                                         incoming=common, additions=[local("P4", "bandwidth")], method=METHOD)
    assert current_package_token(tmp_path / "branches/method.one/phases/p3") == p3_token
    merged = collect_notation_inputs(tmp_path, [core_ref, theory_ref, numerical_ref], METHOD, "P5")
    assert [item["quantity_key"] for item in merged["entries"]] == ["target", "moment_bound", "bandwidth"]
    assert sum(item["symbol_latex"] == r"\kappa" for item in merged["entries"]) == 2
    assert merged["entries"][1]["definition_ref"] == theory["entries"][-1]["definition_ref"]
    assert merged["entries"][2]["definition_ref"] == numerical["entries"][-1]["definition_ref"]
    assert collect_notation_inputs(tmp_path, [numerical_ref, core_ref], METHOD, "P2")["entries"] == common["entries"]


def test_p2_candidate_scopes_match_exact_definition_and_do_not_rewrite_proposals(tmp_path):
    stable = METHOD["identity"]["stable_id"]
    scoped = {"kind": "method", "method_identity": {"stable_id": stable, "definition_sha256": "a" * 64}}
    ref, snapshot, _ = account(tmp_path, phase="P2", family="catalog_assessment", run_id="run.p2", method=METHOD,
                               additions=[entry("tuning", r"\lambda", scoped, "p2.catalog_assessment")])
    editorial = deepcopy(METHOD)
    editorial["identity"]["version"] = 2
    assert collect_notation_inputs(tmp_path, [ref], editorial, "P3")["entries"] == snapshot["entries"]
    changed = deepcopy(editorial)
    changed["identity"]["definition_sha256"] = "b" * 64
    assert collect_notation_inputs(tmp_path, [ref], changed, "P3")["entries"] == []
    invalid = deepcopy(scoped)
    invalid["method_identity"]["definition_sha256"] = "c" * 64
    with pytest.raises(ArtifactError, match="exact admitted candidate"):
        account(tmp_path, phase="P2", family="catalog_assessment", run_id="run.invalid", method=METHOD,
                additions=[entry("tuning", r"\lambda", invalid, "p2.catalog_assessment")])


@pytest.mark.parametrize("phase,family", [("P2", "catalog_assessment"), ("P3", "complete_theory"),
                                          ("P4", "empirical_synthesis_candidate"), ("P5", "technical_report_candidate")])
def test_later_phase_cannot_rewrite_study_core(tmp_path, phase, family):
    with pytest.raises(ArtifactError, match="owned by another"):
        account(tmp_path, phase=phase, family=family, run_id="run.wrong", additions=[entry(output=phase.lower() + "." + family)])


def test_explicit_replacement_retirement_keeps_old_definition_and_original_source(tmp_path):
    ref, original, _ = account(tmp_path)
    incoming = collect_notation_inputs(tmp_path, [ref], None, "P1")
    revised = entry()
    revised["symbol_latex"] = r"\theta_D"
    revised["replaces"] = {"snapshot_sha256": incoming["sources"][0]["snapshot_sha256"], "entry_id": original["entries"][0]["entry_id"]}
    second_ref, second, _ = account(tmp_path, run_id="run.p1.clarify", incoming=incoming, additions=[revised])
    assert second["entries"][0]["status"] == "retired"
    assert second["entries"][1]["status"] == "active"
    assert second["entries"][0]["definition_ref"] == original["entries"][0]["definition_ref"]
    assert retained_notation(tmp_path, ref) == original
    assert retained_notation(tmp_path, second_ref) == second


@pytest.mark.parametrize("clarification", [False, True])
def test_merging_stale_consumer_does_not_revive_owner_retirement(tmp_path, clarification):
    core, original, document = account(tmp_path)
    stale, _, _ = account(tmp_path, phase="P2", family="catalog_assessment", run_id="run.p2.stale",
                          incoming=collect_notation_inputs(tmp_path, [core], None, "P2"), additions=[])
    prior = {"snapshot_sha256": document["notation_snapshot"]["sha256"], "entry_id": original["entries"][0]["entry_id"]}
    changes = updates()
    if clarification:
        replacement = entry()
        replacement.update(symbol_latex=r"\theta_D", replaces=prior)
        changes["entries"] = [replacement]
    else:
        changes["retirements"] = [{"entry_ref": prior, "reason_markdown": "The current account no longer uses this symbol."}]
    current, _, _ = account(tmp_path, run_id="run.p1.revised", incoming=collect_notation_inputs(tmp_path, [core], None, "P1"),
                             extra={"notation_updates": changes})
    for records in ([current, stale], [stale, current]):
        merged = collect_notation_inputs(tmp_path, records, METHOD, "P3")
        assert merged["entries"][0]["status"] == "retired"
        assert any(prior["entry_id"] in source["active_entry_ids"] for source in merged["sources"] if source["phase"] == "P2")
        active = [row for row in merged["entries"] if row["status"] == "active"]
        assert len(active) == int(clarification)
    inherited, _, _ = account(tmp_path, phase="P3", family="complete_theory", branch="method.one", run_id="run.p3.inherited",
        incoming=merged, additions=[], method=METHOD)
    again = collect_notation_inputs(tmp_path, [stale, inherited], METHOD, "P5")
    assert next(row for row in again["entries"] if row["entry_id"] == prior["entry_id"])["status"] == "retired"
    assert retained_notation(tmp_path, core) == original


@pytest.mark.parametrize("change", ["duplicate", "missing_source", "unadmitted", "private", "wrong_pointer"])
def test_invalid_bindings_are_rejected_before_publication(tmp_path, change):
    entries = [entry()]
    extra = {}
    if change == "duplicate":
        entries.append(entry())
    elif change == "missing_source":
        entries[0]["source_refs"] = []
    elif change == "unadmitted":
        entries[0]["source_refs"] = [{"phase": "P4", "branch": "method.one", "family": "empirical_synthesis", "generation_id": "generation.fake", "content_sha256": "a" * 64, "pointer": "/conclusion"}]
    elif change == "private":
        entries[0]["source_refs"][0]["pointer"] = "/phase2_preparation"
        extra["phase2_preparation"] = "Lead-only direction"
    else:
        entries[0]["source_refs"][0]["pointer"] = "/does_not_exist"
    with pytest.raises(ArtifactError):
        account(tmp_path, additions=entries, extra=extra)
    assert not (tmp_path / "branches/trunk/phases/p1/current-package.json").exists()


def test_restricted_ancestor_and_output_audiences_cannot_be_bypassed_with_scalar_pointer(tmp_path):
    extra = {"details": {"audience": ["research_lead"], "definition": "A private instruction."}}
    private = entry(pointer="/details/definition")
    with pytest.raises(ArtifactError, match="restricted-audience"):
        account(tmp_path, additions=[private], extra=extra)
    # Selecting a permitted scientific field does not read its private sibling.
    account(tmp_path, run_id="run.shared", additions=[entry()], extra=extra)
    write_json_atomic(tmp_path / "runs/run.contract/contracts/contracts/phases/P1.json", {
        "role_stages": [{"artifact_contracts": {"p1.research_basis": {"audience": ["research_lead"]}}}]})
    with pytest.raises(ArtifactError, match="output contract restricts"):
        account(tmp_path, run_id="run.contract", additions=[entry()])


def test_one_explicit_scope_cannot_bind_the_same_symbol_to_target_and_estimator(tmp_path):
    with pytest.raises(ArtifactError, match="one symbol to different quantities"):
        account(tmp_path, additions=[entry("target"), entry("estimator")])
    reference, original, _ = account(tmp_path)
    with pytest.raises(ArtifactError, match="one symbol to different quantities"):
        account(tmp_path, run_id="run.rerun", incoming=collect_notation_inputs(tmp_path, [reference], None, "P1"),
                additions=[entry("estimator")])
    assert retained_notation(tmp_path, reference) == original


def test_local_quantity_scope_preserves_explicit_clarification_but_separates_new_accounts(tmp_path):
    reference, original, document = account(tmp_path, phase="P3", family="complete_theory", branch="method.one",
        run_id="run.p3.original", additions=[local("P3", "constant", "C")], method=METHOD)
    inherited = collect_notation_inputs(tmp_path, [reference], METHOD, "P3")
    original_entry = original["entries"][0]
    assert original_entry["account_scope_ref"] == original_entry["adoption_ref"]
    independent = local("P3", "constant", "B")
    independent["definition_markdown"] = "$B$ bounds a different theoretical remainder."
    other_ref, other, _ = account(tmp_path, phase="P3", family="complete_theory", branch="method.one",
        run_id="run.p3.independent", incoming=inherited, additions=[independent], method=METHOD)
    assert len(other["entries"]) == 2
    assert other["entries"][-1]["account_scope_ref"] != original_entry["account_scope_ref"]
    clarification = local("P3", "constant", "D")
    clarification["replaces"] = {"snapshot_sha256": document["notation_snapshot"]["sha256"],
                                 "entry_id": original_entry["entry_id"]}
    revised_ref, revised, _ = account(tmp_path, phase="P3", family="complete_theory", branch="method.one",
        run_id="run.p3.clarified", incoming=inherited, additions=[clarification], method=METHOD)
    assert revised["entries"][-1]["account_scope_ref"] == original_entry["account_scope_ref"]
    assert revised["entries"][0]["status"] == "retired"
    assert retained_notation(tmp_path, revised_ref) == revised
    assert retained_notation(tmp_path, other_ref) == other
    forged = local("P3", "constant", "E")
    forged["account_scope_ref"] = original_entry["adoption_ref"]
    with pytest.raises(ArtifactError, match="harness owns"):
        account(tmp_path, phase="P3", family="complete_theory", branch="method.one",
                run_id="run.p3.forged", additions=[forged], method=METHOD)


def test_retained_local_scope_cannot_point_to_an_unrelated_committed_adoption(tmp_path):
    _, original, document = account(tmp_path, phase="P3", family="complete_theory", branch="method.one",
        run_id="run.p3.original", additions=[local("P3", "constant", "C")], method=METHOD)
    _, unrelated, _ = account(tmp_path, phase="P3", family="complete_theory", branch="method.one",
        run_id="run.p3.unrelated", additions=[local("P3", "constant", "B")], method=METHOD)
    forged = deepcopy(original)
    forged["entries"][0]["account_scope_ref"] = unrelated["entries"][0]["adoption_ref"]
    directory = tmp_path / "runs/run.tampered/outputs/p3.synthesis"
    write_json_atomic(directory / "notation.json", forged)
    (directory / "notation.md").write_text(render_notation(forged), encoding="utf-8")
    document["notation_snapshot"]["sha256"] = sha256_file(directory / "notation.json")
    document["notation_snapshot"]["markdown"]["sha256"] = sha256_file(directory / "notation.md")
    package = publish_package(tmp_path / "branches/method.one/phases/p3", {"complete_theory": json.dumps(document).encode()},
        run_id="run.tampered", phase="P3", branch_id="method.one", metadata={"stage_ids": {"complete_theory": "p3.synthesis"}})
    source = {"phase": "P3", "branch": "method.one", "family": "complete_theory", **package["records"]["complete_theory"]}
    with pytest.raises(ArtifactError, match="differs from its exact authored adoption"):
        retained_notation(tmp_path, source)


def test_mapping_binds_exact_source_entry_without_rewriting_canonical_proof(tmp_path):
    ref, _, _ = account(tmp_path, phase="P3", family="complete_theory", branch="method.one", run_id="run.p3",
                         additions=[local("P3", "moment_bound")], method=METHOD)
    incoming = collect_notation_inputs(tmp_path, [ref], METHOD, "P5")
    report_entry = local("P5", "report_moment_bound", r"\zeta")
    report_entry["source_symbol_mapping"] = {
        "source_entry_ref": {"snapshot_sha256": incoming["sources"][0]["snapshot_sha256"], "entry_id": incoming["entries"][0]["entry_id"]},
        "source_symbol_latex": r"\kappa", "explanation_markdown": r"The report uses $\zeta$ for the proof's moment bound $\kappa$."}
    report_ref, report, _ = account(tmp_path, phase="P5", family="technical_report_candidate", branch="method.one", run_id="run.report",
                                    incoming=incoming, additions=[report_entry], method=METHOD)
    assert [item["symbol_latex"] for item in report["entries"]] == [r"\kappa", r"\zeta"]
    assert retained_notation(tmp_path, ref)["entries"][0]["symbol_latex"] == r"\kappa"
    assert retained_notation(tmp_path, report_ref)["entries"][-1]["source_symbol_mapping"] == report_entry["source_symbol_mapping"]


def test_exact_row_target_survives_later_publication_and_rejects_newer_digest(tmp_path):
    ref, snapshot, generated = account(tmp_path)
    target = {"kind": "notation_entry", **ref, "snapshot_sha256": generated["notation_snapshot"]["sha256"], "entry_id": snapshot["entries"][0]["entry_id"]}
    account(tmp_path, run_id="run.new", additions=[entry("size", "n")])
    selected = resolve_notation_entry(tmp_path, target)
    assert selected["entry"] == snapshot["entries"][0]
    assert selected["snapshot"] == snapshot
    with pytest.raises(ArtifactError, match="retained view"):
        resolve_notation_entry(tmp_path, {**target, "snapshot_sha256": "b" * 64})


def test_failed_package_commit_leaves_both_prior_science_and_notation_current(tmp_path, monkeypatch):
    reference, snapshot, _ = account(tmp_path)
    from model_forge_codex import records
    original_write = records.write_json_atomic
    def fail_commit(path, document):
        if path.name == "current-package.json":
            raise OSError("simulated commit failure")
        original_write(path, document)
    monkeypatch.setattr(records, "write_json_atomic", fail_commit)
    with pytest.raises(OSError):
        account(tmp_path, run_id="run.orphan", additions=[entry("new_target", r"\mu_C")])
    assert retained_notation(tmp_path, reference) == snapshot
    orphan = next(read_json(path) for path in (tmp_path / "branches/trunk/phases/p1/packages").glob("*.json")
                  if read_json(path)["run_id"] == "run.orphan")
    orphan_ref = {"phase": "P1", "branch": "trunk", "family": "research_basis", **orphan["records"]["research_basis"]}
    with pytest.raises(ArtifactError, match="not a committed"):
        retained_notation(tmp_path, orphan_ref)


def test_generated_markdown_and_json_are_jointly_verified(tmp_path):
    reference, _, generated = account(tmp_path)
    path = tmp_path / "runs/run.p1/outputs/p1.synthesis/notation.md"
    path.write_text("changed scientific meaning", encoding="utf-8")
    with pytest.raises(ArtifactError, match=r"could not be verified.*file: notation\.md"):
        retained_notation(tmp_path, reference)


def test_definition_field_source_integrity_and_conflicting_target_identities(tmp_path):
    reference, snapshot, document = account(tmp_path)
    target = {"kind": "notation_entry", **reference, "snapshot_sha256": document["notation_snapshot"]["sha256"],
              "entry_id": snapshot["entries"][0]["entry_id"]}
    for changes in ({"run_id": "run.wrong"}, {"sha256": "f" * 64}, {"object_id": "notation.wrong"},
                    {"project_id": "different-project"}):
        with pytest.raises(ArtifactError):
            resolve_notation_entry(tmp_path, {**target, **changes})
    source = next((tmp_path / "branches/trunk/phases/p1/research_basis/generations").glob("*.json"))
    source.write_text('{"scientific_definition":"A different target"}', encoding="utf-8")
    with pytest.raises(ArtifactError, match="Digest mismatch"):
        retained_notation(tmp_path, reference)


def test_dispositions_name_only_exact_admitted_saved_correction_revisions(tmp_path):
    document = {"scientific_definition": "The target is unchanged.", "notation_updates": updates()}
    correction = {"context_id": "context.notation.target", "revision": 2, "sha256": "a" * 64}
    disposition = {"correction_ref": correction, "disposition": "unchanged", "reason_markdown": "The target remains donor weighted under the recorded study goal."}
    document["notation_updates"]["correction_dispositions"] = [disposition]
    frozen = basis()
    frozen["problem_context"] = {"notation_correction_refs": [correction]}
    result = build_account_notation(tmp_path, tmp_path / "runs/run.p1", "P1", "trunk", "p1.synthesis", document, "research_basis", frozen,
                                    {"p1.research_basis": (document, "p1.synthesis")})
    assert result["correction_dispositions"] == [disposition]
    document["notation_updates"]["correction_dispositions"][0]["correction_ref"] = {**correction, "revision": 3}
    with pytest.raises(ArtifactError, match="exact admitted saved correction"):
        build_account_notation(tmp_path, tmp_path / "runs/run.p1", "P1", "trunk", "p1.synthesis", document, "research_basis", frozen,
                               {"p1.research_basis": (document, "p1.synthesis")})


def test_adopted_disposition_requires_an_actual_owned_definition_update(tmp_path):
    reference, original, generated = account(tmp_path)
    target = {**reference, "kind": "notation_entry", "entry_id": original["entries"][0]["entry_id"],
              "snapshot_sha256": generated["notation_snapshot"]["sha256"]}
    item = {"item_id": "context.notation.target", "revision": 2, "topic": "notation_correction",
            "statement": "Clarify the symbol while keeping donor weights.", "source_refs": [target]}
    correction = {"context_id": item["item_id"], "revision": 2, "sha256": digest(item)}
    frozen = basis(collect_notation_inputs(tmp_path, [reference], None, "P1"), refs=[reference])
    frozen["problem_context"] = {"items": [item], "notation_correction_refs": [correction]}
    document = {"scientific_definition": "The donor-weighted target is unchanged.", "notation_updates": updates()}
    document["notation_updates"]["correction_dispositions"] = [{"correction_ref": correction,
        "disposition": "adopted", "reason_markdown": "The symbol is clarified under the same target."}]
    arguments = (tmp_path, tmp_path / "runs/run.p1.corrected", "P1", "trunk", "p1.synthesis", document, "research_basis", frozen,
                 {"p1.research_basis": (document, "p1.synthesis")})
    with pytest.raises(ArtifactError, match="actual update"):
        build_account_notation(*arguments)
    document["notation_updates"]["entries"] = [entry("sample_size", "n")]
    with pytest.raises(ArtifactError, match="actual update"):
        build_account_notation(*arguments)
    clarification = entry()
    clarification["symbol_latex"] = r"\theta_D"
    clarification["replaces"] = {"snapshot_sha256": target["snapshot_sha256"], "entry_id": target["entry_id"]}
    document["notation_updates"]["entries"] = [clarification]
    assert build_account_notation(*arguments)["correction_dispositions"] == document["notation_updates"]["correction_dispositions"]
    with pytest.raises(ArtifactError, match="another phase's canonical"):
        build_account_notation(tmp_path, tmp_path / "runs/run.p3", "P3", "method.one", "p3.synthesis",
            {**document, "notation_updates": {**document["notation_updates"], "entries": []}}, "complete_theory", frozen, {})


@pytest.mark.parametrize("phase,family,scope", [
    ("P1", "research_basis", {"kind": "study"}),
    ("P2", "catalog_assessment", {"kind": "method", "method_identity": {
        "stable_id": METHOD["identity"]["stable_id"], "definition_sha256": "a" * 64}}),
    ("P3", "complete_theory", {"kind": "account", "phase": "P3", "branch": "method.one",
        "account_family": "complete_theory", "method_identity": {
            "stable_id": METHOD["identity"]["stable_id"], "definition_sha256": "a" * 64}}),
])
def test_correction_to_earlier_definition_must_update_active_successor(tmp_path, phase, family, scope):
    branch = "method.one" if phase == "P3" else "trunk"
    method = METHOD if phase in {"P2", "P3"} else None
    output = phase.lower() + "." + family
    stage = phase.lower() + ".synthesis"
    original = entry("bound", "C", scope, output)
    original["definition_markdown"] = "$C$ is a fixed finite bound under the recorded conditions."
    original["meaning_markdown"] = "The bound applies only under the scientific account's stated conditions."
    first, first_view, first_doc = account(tmp_path, phase=phase, family=family, branch=branch,
        run_id="run.first", additions=[original], method=method, extra={"scientific_definition": original["definition_markdown"]})
    second_update = {**deepcopy(original), "symbol_latex": "D", "replaces": {
        "snapshot_sha256": first_doc["notation_snapshot"]["sha256"], "entry_id": first_view["entries"][0]["entry_id"]}}
    second, second_view, second_doc = account(tmp_path, phase=phase, family=family, branch=branch,
        run_id="run.second", incoming=collect_notation_inputs(tmp_path, [first], method, phase), additions=[second_update],
        method=method, extra={"scientific_definition": original["definition_markdown"]})
    frozen = basis(collect_notation_inputs(tmp_path, [second], method, phase), refs=[second], method=method, branch=branch)
    target = {**first, "kind": "notation_entry", "snapshot_sha256": first_doc["notation_snapshot"]["sha256"],
              "entry_id": first_view["entries"][0]["entry_id"]}
    item = {"item_id": "context.notation.bound", "revision": 3, "topic": "notation_correction",
            "statement": "Remove or clarify this bound's notation.", "source_refs": [target]}
    correction = {"context_id": item["item_id"], "revision": item["revision"], "sha256": digest(item)}
    frozen["problem_context"] = {"items": [item], "notation_correction_refs": [correction]}
    retired_ref = {"snapshot_sha256": second_doc["notation_snapshot"]["sha256"], "entry_id": first_view["entries"][0]["entry_id"]}
    active_ref = {"snapshot_sha256": second_doc["notation_snapshot"]["sha256"], "entry_id": second_view["entries"][-1]["entry_id"]}

    def build(additions=(), retirements=()):
        changes = updates(additions)
        changes["retirements"] = list(retirements)
        changes["correction_dispositions"] = [{"correction_ref": correction, "disposition": "adopted",
            "reason_markdown": "This account applies the correction to the same bound and conditions."}]
        document = {"scientific_definition": original["definition_markdown"], "notation_updates": changes}
        documents = {output: (document, stage)}
        if method:
            documents["p2.method_catalog"] = ({"methods": [method]}, "p2.reconcile")
        return build_account_notation(tmp_path, tmp_path / "runs/run.third", phase, branch, stage, document, family, frozen, documents)

    with pytest.raises(ArtifactError, match="current active definition"):
        build([{**deepcopy(original), "symbol_latex": "E", "replaces": retired_ref}])
    with pytest.raises(ArtifactError, match="current active definition"):
        build(retirements=[{"entry_ref": retired_ref, "reason_markdown": "Remove the old notation."}])
    replacement = {**deepcopy(original), "symbol_latex": "E", "replaces": active_ref}
    replaced = build([replacement])
    assert [(row["symbol_latex"], row["status"]) for row in replaced["entries"]] == [("C", "retired"), ("D", "retired"), ("E", "active")]
    retirement = {"entry_ref": active_ref, "reason_markdown": "The current account no longer needs this bound's notation."}
    retired = build(retirements=[retirement])
    assert all(row["status"] == "retired" for row in retired["entries"])
    assert retired["correction_dispositions"][0]["correction_ref"] == correction
    for additions, retirements in (([replacement], [retirement]), ([], [retirement, retirement])):
        with pytest.raises(ArtifactError, match="current active definition"):
            build(additions, retirements)
    assert retained_notation(tmp_path, first) == first_view
    assert retained_notation(tmp_path, second) == second_view


def test_retiring_unrelated_local_origin_cannot_adopt_another_accounts_correction(tmp_path):
    first, first_view, first_doc = account(tmp_path, phase="P3", family="complete_theory", branch="method.one",
        run_id="run.p3.first", additions=[local("P3", "bound", "C")], method=METHOD)
    second, second_view, second_doc = account(tmp_path, phase="P3", family="complete_theory", branch="method.one",
        run_id="run.p3.other", additions=[local("P3", "bound", "C")], method=METHOD)
    frozen = basis(collect_notation_inputs(tmp_path, [first, second], METHOD, "P3"), refs=[first, second], method=METHOD, branch="method.one")
    target = {**first, "kind": "notation_entry", "snapshot_sha256": first_doc["notation_snapshot"]["sha256"],
              "entry_id": first_view["entries"][0]["entry_id"]}
    item = {"item_id": "context.notation.first", "revision": 1, "topic": "notation_correction",
            "statement": "Remove this account's bound notation.", "source_refs": [target]}
    correction = {"context_id": item["item_id"], "revision": 1, "sha256": digest(item)}
    frozen["problem_context"] = {"items": [item], "notation_correction_refs": [correction]}
    changes = updates()
    changes["retirements"] = [{"entry_ref": {"snapshot_sha256": second_doc["notation_snapshot"]["sha256"],
        "entry_id": second_view["entries"][0]["entry_id"]}, "reason_markdown": "Remove the unrelated account's symbol."}]
    changes["correction_dispositions"] = [{"correction_ref": correction, "disposition": "adopted", "reason_markdown": "The correction is applied."}]
    with pytest.raises(ArtifactError, match="actual update to its owned quantity and scope"):
        build_account_notation(tmp_path, tmp_path / "runs/run.third", "P3", "method.one", "p3.synthesis",
            {"notation_updates": changes}, "complete_theory", frozen, {})


def test_capability_reads_frozen_catalog_and_v1_inputs_remain_absent(tmp_path):
    from types import SimpleNamespace
    catalog = SimpleNamespace(root=tmp_path / "contracts")
    write_json_atomic(catalog.root / "contracts/phases/P1.json", {"capabilities": ["research_presentation_v1"]})
    assert not notation_enabled(catalog)
    assert frozen_notation({}) is None
    write_json_atomic(catalog.root / "contracts/phases/P1.json", {"capabilities": ["research_presentation_v2", "project_notation_v1"]})
    assert notation_enabled(catalog, "P1")
