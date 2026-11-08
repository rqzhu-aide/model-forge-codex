"""Complete scientific inputs survive focused instruction delivery."""
import json
from pathlib import Path

from model_forge_codex.domain import MemberRole
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic


def test_disposable_full_brief_preserves_selected_method_answers_notation_and_sources(workbench):
    from model_forge_codex.notation import digest, freeze_notation_inputs
    from test_context_audience_projection import SHARED, answer, context, item
    from test_researcher_workbench_engine import record

    engine, project, branch = workbench
    candidate = record(engine, branch, "run.context.delivery", "P4", "p4.preliminary")
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    basis = engine.compute_basis(candidate.project_id, "P4", branch, candidate.mode)
    for ref in basis["records"]:
        family_dir = project / "branches" / ref["branch"] / "phases" / ref["phase"].lower() / ref["family"]
        _, _, source = engine._generation_text(family_dir, ref)
        frozen = directory / "inputs" / ref["family"] / source.name
        frozen.parent.mkdir(parents=True, exist_ok=True)
        frozen.write_bytes(source.read_bytes())
        ref["snapshot_path"] = str(frozen)
    saved = {**answer("study.unknown", audience=SHARED), "note": "Costs are in unknown units.",
             "origin": "unknown", "selected_option_id": None, "custom_answer": "Keep units unknown."}
    answers = {"items": [saved]}
    answer_path = directory / "inputs/researcher_answers.json"
    write_json_atomic(answer_path, answers)
    basis["cumulative_inputs"]["researcher_answers"] = {
        "snapshot_path": str(answer_path), "sha256": engine._cumulative_digest(answers)}
    basis["problem_context"] = context([item("study.units.unknown", saved, origin="unknown")])
    notation = {"schema_version": "1.0.0", "sources": [], "entries": [{
        "entry_id": "notation.cost", "symbol_latex": "G_C", "scope": {"kind": "study"},
        "definition_markdown": "$$G_C=\\sum_t\\gamma^t C_t$$", "meaning_markdown": "Cost units remain unknown."}]}
    basis["notation"] = {"document": notation, "sha256": digest(notation)}
    freeze_notation_inputs(directory, basis)
    proof = directory / "inputs/artifacts/proof.md"
    proof.parent.mkdir(parents=True, exist_ok=True)
    proof.write_text("Frozen qualification: strict threshold; equality is safe.", encoding="utf-8")
    basis["artifacts"] = [{"family": "theory_record", "path": str(proof),
        "content_sha256": sha256_file(proof), "original_path": "proof.md", "producing_run_id": "run.theory"}]
    write_json_atomic(directory / "basis.json", basis)
    before = {path: path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    stage = next(stage for stage in engine.stage_plan(candidate.project_id, "P4", candidate.mode)
                 if MemberRole.DATA_ANALYST in stage.roles)

    brief = engine._render_brief(candidate, stage, MemberRole.DATA_ANALYST,
                                engine.member_workspace(candidate, stage.stage_id, MemberRole.DATA_ANALYST))

    selected = brief.split("## Exact selected method\n\n```json\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(selected) == basis["method"]
    assert "study.units.unknown" in brief and '"origin": "unknown"' in brief
    assert "Cost units remain unknown." in brief and str(Path(basis["notation"]["snapshot_path"])) in brief
    assert str(proof) in brief and sha256_file(proof) in brief
    delivered_answers = read_json(directory / "inputs/answer-views/data_analyst/researcher_answers.json")
    assert delivered_answers["items"] == [saved]
    schema = engine._catalog(candidate).output_schema(stage.writes[0])
    assert json.dumps(schema, indent=1) in brief
    assert {path: path.read_bytes() for path in before} == before


# Kept here so pytest resolves the shared disposable fixture locally.
from test_researcher_workbench_engine import workbench
