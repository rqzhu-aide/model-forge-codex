"""Exact frozen P5 delivery checks without provider or scientific-quality claims."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.p5_review_packet import (
    FROZEN_REVIEW_CAPABILITY,
    frozen_review_packet_enabled,
    manuscript_scope_brief,
    prepare_review_packet,
    read_review_packet,
    review_packet_brief,
    validate_manuscript_scope,
    validate_review_packet_outputs,
)
from model_forge_codex.records import ArtifactError, generation_path
from model_forge_codex.storage import read_json, sha256_bytes, sha256_file, write_json_atomic
from test_technical_reports import report_case

REPO = Path(__file__).resolve().parents[1]
FOCUS = "P5_FOCUS_EXACT: assess the unsupported asymptotic comparison; preserve negative evidence."


def prepare_engine_review_packet(engine, run, basis=None):
    """Direct-review fixtures explicitly perform the real preparation boundary."""
    basis = basis if basis is not None else engine.compute_basis(run.project_id, "P5", run.branch_id, run.mode)
    run_dir = engine.run_dir(run.project_id, run.run_id)
    for ref in basis["records"]:
        if ref.get("snapshot_path"):
            continue
        store = engine.project_dir(run.project_id) / "branches" / ref["branch"] / "phases" / ref["phase"].lower()
        source = generation_path(store, ref["family"], ref)
        destination = run_dir / "inputs" / ref["branch"] / ref["phase"].lower() / ref["family"] / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        ref["snapshot_path"] = str(destination)
    write_json_atomic(run_dir / "basis.json", basis)
    return prepare_review_packet(run_dir, basis=basis, instructions=run.instructions, run_id=run.run_id)


def packet_basis(run_dir):
    inputs = run_dir / "inputs"
    inputs.mkdir(parents=True)
    paper = inputs / "paper.md"
    paper.write_text("# The actual submitted paper\n\nPartial evidence, explicit limitations.\n", encoding="utf-8")
    supplement = inputs / "references.bib"
    supplement.write_text("@article{public, title={Submitted public citation}}\n", encoding="utf-8")
    internal = inputs / "internal-notebook.md"
    internal.write_text("PRIVATE_P5_NOTEBOOK", encoding="utf-8")
    pointer = lambda path: {"artifact_id": "artifact." + path.stem, "path": path.name, "sha256": sha256_file(path)}
    manuscript = {"record_id": "record.paper", "target_audience": "Statistical researchers",
                  "venue_length": "journal", "manuscript_artifact": pointer(paper),
                  "supplementary_artifacts": [pointer(supplement)], "basis": [{"secret": "PRIVATE_ORIGINAL_BASIS"}]}
    snapshot = inputs / "manuscript-record.json"
    write_json_atomic(snapshot, manuscript)
    basis = {"project": {"venue_length": "conference", "research_instructions": "PRIVATE_PROJECT_INSTRUCTIONS"},
             "selected_issues": [{"issue": "PRIVATE_SELECTED_ISSUE"}],
             "records": [{"phase": "P5", "branch": "method.a", "family": "manuscript", "generation_id": "generation.reviewed_draft",
                          "content_sha256": sha256_file(snapshot), "snapshot_path": str(snapshot)}],
             "artifacts": [{"family": "manuscript", "phase": "P5", "generation_id": "generation.reviewed_draft",
                            "content_sha256": sha256_file(path), "path": str(path), "original_path": path.name}
                           for path in (paper, supplement, internal)]}
    return basis


@pytest.fixture
def prepared(tmp_path):
    run_dir = tmp_path / "run.review"
    basis = packet_basis(run_dir)
    packet = prepare_review_packet(run_dir, basis=basis, instructions=FOCUS, run_id="run.review")
    return run_dir, basis, packet


def test_packet_contains_exact_submission_focus_and_declared_scope_only(prepared):
    run_dir, basis, packet = prepared
    assert [entry["family"] for entry in packet["records"]] == ["manuscript", "supplement"]
    assert {entry["generation_id"] for entry in packet["records"]} == {"generation.reviewed_draft"}
    assert [entry["content_sha256"] for entry in packet["records"]] == [entry["content_sha256"] for entry in basis["artifacts"][:2]]
    assert {path.name for path in (run_dir / "review-packet").iterdir()} == {
        "manifest.json", "manuscript-0.md", "manuscript-1.bib", "instructions.md"}
    instruction = packet["instructions"]
    assert "generation_id" not in instruction
    assert instruction["source_choice_id"] == "p5.instructions" and instruction["source_run_id"] == "run.review"
    assert instruction["venue_length"] == "conference" and instruction["draft_venue_length"] == "journal"
    assert instruction["target_audience"] == "Statistical researchers"
    delivered = review_packet_brief(run_dir / "review-packet")
    assert FOCUS in delivered and "venue_length: conference" in delivered and "venue_length: journal" in delivered
    assert "Statistical researchers" in delivered and "generation.reviewed_draft" in delivered
    assert "page quota" in delivered
    assert "PRIVATE" not in "".join(path.read_text(encoding="utf-8") for path in (run_dir / "review-packet").iterdir())


def test_correction_and_changed_current_settings_reuse_original_bytes(prepared):
    run_dir, basis, original = prepared
    directory = run_dir / "review-packet"
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    changed = copy.deepcopy(basis)
    changed["project"]["venue_length"] = "journal"
    changed["records"][0]["generation_id"] = "generation.later"
    for source in [*basis["artifacts"], basis["records"][0]]:
        Path(source.get("path") or source["snapshot_path"]).unlink()
    assert prepare_review_packet(run_dir, basis=changed, instructions="LATER_UNDELIVERED_FOCUS", run_id="run.review") == original
    assert read_review_packet(directory) == original
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before
    assert "LATER_UNDELIVERED_FOCUS" not in review_packet_brief(directory)


def test_v2_review_packet_freezes_neutral_references_without_private_context(tmp_path):
    run_dir = tmp_path / "run.presentation"
    basis = packet_basis(run_dir)
    catalog = Catalog(REPO / "contracts")
    packet = prepare_review_packet(run_dir, basis=basis, instructions=FOCUS,
                                   run_id="run.presentation", catalog=catalog)
    text = Path(packet["instructions"]["path"]).read_text(encoding="utf-8")
    for name in ("scientific-explanation", "claims-and-evidence", "summary", "tables-and-figures"):
        reference = (catalog.root / "references/research-presentation" / f"{name}.md").read_text(encoding="utf-8").strip()
        assert text.count(reference) == 1
    inquiry = (catalog.root / "references/research-presentation/user-inquiry.md").read_text(encoding="utf-8").strip()
    assert inquiry not in text
    assert "PRIVATE" not in text
    before = Path(packet["instructions"]["path"]).read_bytes()
    prepare_review_packet(run_dir, basis={}, instructions="LATER FOCUS", run_id="run.presentation", catalog=catalog)
    assert Path(packet["instructions"]["path"]).read_bytes() == before


@pytest.mark.parametrize("target", ["instructions.md", "manuscript-0.md", "manuscript-1.bib"])
def test_changed_delivery_bytes_are_rejected(prepared, target):
    run_dir, _, _ = prepared
    (run_dir / "review-packet" / target).write_text("CHANGED", encoding="utf-8")
    with pytest.raises(ArtifactError, match="changed or disappeared"):
        read_review_packet(run_dir / "review-packet")
    findings = validate_review_packet_outputs(run_dir / "review-packet", {
        "p5.outside_review": {"review_basis_generation_id": "generation.reviewed_draft", "prioritized_issues": []}})
    assert [finding.code for finding in findings] == ["review.packet_invalid"]


@pytest.mark.parametrize("mutation", ["internal_family", "instruction_generation", "escaped_path", "extra_file", "mixed_generation"])
def test_packet_allowlist_excludes_internal_or_undeclared_material(prepared, mutation):
    run_dir, basis, _ = prepared
    directory = run_dir / "review-packet"
    manifest = read_json(directory / "manifest.json")
    if mutation == "internal_family":
        manifest["records"][1]["family"] = "theory_audit"
    elif mutation == "instruction_generation":
        manifest["instructions"]["generation_id"] = "generation.invented"
    elif mutation == "escaped_path":
        manifest["records"][0]["path"] = basis["artifacts"][2]["path"]
    elif mutation == "mixed_generation":
        manifest["records"][1]["generation_id"] = "generation.later"
    else:
        (directory / "internal-audit.json").write_text('{"secret": "internal"}', encoding="utf-8")
    write_json_atomic(directory / "manifest.json", manifest)
    with pytest.raises(ArtifactError):
        read_review_packet(directory)


def test_every_review_and_finding_names_the_same_draft(prepared):
    run_dir, _, _ = prepared
    correct = {"review_basis_generation_id": "generation.reviewed_draft"}
    outputs = {"p5.theory_audit": [dict(correct)], "p5.empirical_audit": [],
               "p5.outside_review": {**correct, "prioritized_issues": [dict(correct)]}}
    assert validate_review_packet_outputs(run_dir / "review-packet", outputs) == []
    outputs["p5.theory_audit"][0]["review_basis_generation_id"] = "generation.later_revision"
    outputs["p5.outside_review"]["prioritized_issues"][0]["review_basis_generation_id"] = "generation.later_revision"
    findings = validate_review_packet_outputs(run_dir / "review-packet", outputs)
    assert {(finding.object_id, finding.json_pointer) for finding in findings} == {
        ("p5.theory_audit", "/0/review_basis_generation_id"),
        ("p5.outside_review", "/prioritized_issues/0/review_basis_generation_id")}
    assert {finding.code for finding in findings} == {"review.target_mismatch"}


@pytest.mark.parametrize("missing", ["manuscript", "supplement", "record"])
def test_unavailable_frozen_submission_fails_before_packet_creation(tmp_path, missing):
    run_dir = tmp_path / "run.review"
    basis = packet_basis(run_dir)
    path = (basis["records"][0]["snapshot_path"] if missing == "record" else
            basis["artifacts"][0 if missing == "manuscript" else 1]["path"])
    Path(path).write_text("LATER_SOURCE", encoding="utf-8")
    with pytest.raises(ArtifactError):
        prepare_review_packet(run_dir, basis=basis, instructions=FOCUS, run_id="run.review")
    assert not (run_dir / "review-packet").exists()


def test_inline_legacy_manuscript_is_external_text_without_internal_package(tmp_path):
    run_dir = tmp_path / "run.inline"
    basis = packet_basis(run_dir)
    ref = basis["records"][0]
    source = Path(ref["snapshot_path"])
    write_json_atomic(source, {"markdown": "# LEGACY_PAPER", "private": "PRIVATE_INTERNAL_PACKAGE"})
    ref["content_sha256"] = sha256_file(source)
    packet = prepare_review_packet(run_dir, basis=basis, instructions=FOCUS, run_id="run.inline")
    assert read_json(Path(packet["records"][0]["path"])) == {"text": "# LEGACY_PAPER"}
    assert packet["instructions"]["draft_venue_length"] is None
    assert packet["instructions"]["target_audience"] is None


def test_existing_legacy_packet_never_acquires_undelivered_instructions(tmp_path):
    run_dir = tmp_path / "run.legacy"
    directory = run_dir / "review-packet"
    write_json_atomic(directory / "manifest.json", {"records": []})
    before = (directory / "manifest.json").read_bytes()
    with pytest.raises(ArtifactError, match="original legacy workflow"):
        prepare_review_packet(run_dir, basis={}, instructions="NEVER_DELIVERED", run_id="run.legacy")
    assert (directory / "manifest.json").read_bytes() == before
    assert not (directory / "instructions.md").exists()


def test_scope_is_required_only_for_newly_adopted_candidates(tmp_path):
    current = Catalog(REPO / "contracts")
    assert frozen_review_packet_enabled(current)
    legacy = SimpleNamespace(root=tmp_path / "old-contracts")
    write_json_atomic(legacy.root / "contracts/phases/P5.json", {"capabilities": []})
    assert not frozen_review_packet_enabled(legacy)
    basis = {"project": {"venue_length": "conference"}}
    outputs = {"p5.manuscript_candidate": {}}
    assert validate_manuscript_scope(legacy, outputs, basis) == []
    assert [finding.code for finding in validate_manuscript_scope(current, outputs, basis)] == ["manuscript.venue_length_required"]
    outputs["p5.manuscript_candidate"]["venue_length"] = "journal"
    assert [finding.code for finding in validate_manuscript_scope(current, outputs, basis)] == ["manuscript.venue_length_mismatch"]
    outputs["p5.manuscript_candidate"]["venue_length"] = "conference"
    assert validate_manuscript_scope(current, outputs, basis) == []
    assert "Requested venue_length: conference" in manuscript_scope_brief(basis)
    assert "unavailable" in manuscript_scope_brief({})
    assert FROZEN_REVIEW_CAPABILITY in read_json(current.root / "contracts/phases/P5.json")["capabilities"]


def test_schema_read_accepts_legacy_scope_and_rejects_unknown_genre(legacy_p5_catalog):
    catalog = legacy_p5_catalog
    manuscript = read_json(REPO / "contracts/examples/manuscript-package.example.json")
    assert catalog.validate_output("p5.manuscript_candidate", manuscript) == []
    manuscript.pop("venue_length")
    assert catalog.validate_output("p5.manuscript_candidate", manuscript) == []
    manuscript["venue_length"] = "workshop"
    assert catalog.validate_output("p5.manuscript_candidate", manuscript)


def test_report_packet_reader_directions_follow_captured_catalog_and_stay_frozen(report_case, tmp_path):
    report, basis, roots, frozen = report_case
    primary = next(iter(roots.values())) / "report.md"
    appendix = primary.with_name("appendix.md")
    appendix.write_text("# Proof appendix\n\nExplicitly incomplete retained proof.\n", encoding="utf-8")
    report["supplementary_artifacts"] = [{"artifact_id": "artifact.appendix", "path": appendix.name,
        "sha256": sha256_file(appendix), "media_type": "text/markdown"}]
    for path in (primary, appendix):
        basis["artifacts"].append({"path": str(path), "content_sha256": sha256_file(path)})
    frozen("P5", "technical_report", report)
    captured = SimpleNamespace(root=tmp_path / "captured-catalog")
    phase_path = captured.root / "contracts/phases/P5.json"
    write_json_atomic(phase_path, {"capabilities": ["p5.reader_report.v1"]})
    focus = ("Keep main scientific content strictly below eight printed pages, targeting seven. "
             "Exclude References and the separate proof appendix; start References on a new printed page.")
    packet = prepare_review_packet(tmp_path / "new-review", basis=basis, instructions=focus,
                                   run_id="run.new-review", project_dir=tmp_path, catalog=captured)
    assert packet["packet_version"] == "2.0.0"
    assert packet["instructions"]["focus_sha256"] == sha256_bytes(focus.encode("utf-8"))
    delivered = review_packet_brief(tmp_path / "new-review/review-packet")
    assert focus in delivered
    assert "## Report and proof exposition" in delivered
    assert "section_anchors.references boundary" in delivered
    assert "Parallel reviewers remain read-only" in delivered
    assert "revision Lead authors accepted exposition changes" in delivered
    assert "Check local expansions of supplied algebra or conditional reasoning" in delivered
    assert "incomplete proofs stay explicitly incomplete" in delivered
    assert Path(packet["records"][1]["path"]).read_bytes() == appendix.read_bytes()

    # A previously adopted report contract without the reader capability keeps
    # its original v2 instruction bytes even while the live code is newer.
    write_json_atomic(phase_path, {"capabilities": ["p5.technical_report.v1"]})
    legacy = prepare_review_packet(tmp_path / "old-review", basis=basis, instructions=focus,
                                   run_id="run.old-review", project_dir=tmp_path, catalog=captured)
    legacy_focus = Path(legacy["instructions"]["path"]).read_text(encoding="utf-8")
    assert legacy_focus == (
        "# Frozen technical report review directions\n\n## Researcher focus (verbatim)\n\n" + focus
        + "\n\nReview the exact technical report and every declared supporting exhibit, its retained data dependencies and supplements. "
        "The submitted model version, data or synthetic scope, and completion gaps remain part of the report. "
        "Mathematical, numerical and first-reader responsibilities remain separate. Missing support is a finding. "
        "No new model, proof or numerical work is authorized during this review.\n")
    before = {path.name: path.read_bytes() for path in (tmp_path / "old-review/review-packet").iterdir()}
    write_json_atomic(phase_path, {"capabilities": ["p5.reader_report.v1"]})
    assert prepare_review_packet(tmp_path / "old-review", basis={}, instructions="Undelivered later focus",
                                 run_id="run.old-review", catalog=captured) == legacy
    assert before == {path.name: path.read_bytes() for path in (tmp_path / "old-review/review-packet").iterdir()}


def test_report_schema_keeps_references_optional_and_seven_scientific_sections():
    catalog = Catalog(REPO / "contracts")
    example = read_json(REPO / "contracts/examples/technical-report.example.json")
    example["notation_updates"] = {"incoming_sources": [], "entries": [], "retirements": [], "correction_dispositions": []}
    assert catalog.validate_output("p5.technical_report_candidate", example) == []
    assert example["section_anchors"].pop("references") == "report-references"
    assert catalog.validate_output("p5.technical_report_candidate", example) == []
    example["sections_present"].append("references")
    assert catalog.validate_output("p5.technical_report_candidate", example)
