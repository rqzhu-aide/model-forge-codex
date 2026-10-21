"""Researcher-facing TeX is checked during drafting and before publication."""
import copy
import subprocess

import pytest

from model_forge_codex import math_validation
from model_forge_codex.domain import MemberRole
from model_forge_codex.catalog import Catalog
from model_forge_codex.math_validation import validate_authored_math
from test_draft_validation import REPO, draft_engine, run, write_outputs, check, codes
from test_direct_workflow import p1_documents, p2_documents
from test_researcher_workbench_engine import scientific_output_documents


@pytest.mark.parametrize("bundled", [True, False])
def test_backend_uses_distributed_math_runtime_or_source_fallback(tmp_path, monkeypatch, bundled):
    package = tmp_path / "src/model_forge_codex"
    package.mkdir(parents=True)
    monkeypatch.setattr(math_validation, "__file__", str(package / "math_validation.py"))
    monkeypatch.setattr(math_validation, "_node_executable", lambda: "node")
    if bundled:
        runtime = tmp_path / "web/runtime/validate-math.mjs"
        runtime.parent.mkdir(parents=True)
        runtime.write_text("// Packaged checker", encoding="utf-8")
    calls = []

    def invoke(arguments, **kwargs):
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, stdout="[[]]", stderr="")

    monkeypatch.setattr(math_validation.subprocess, "run", invoke)
    math_validation._check_batch.cache_clear()
    try:
        assert validate_authored_math({"sample": {"latex": "x=1"}}) == []
        folder = "runtime" if bundled else "scripts"
        assert calls == [["node", str(tmp_path / f"web/{folder}/validate-math.mjs")]]
    finally:
        math_validation._check_batch.cache_clear()


def test_math_errors_have_exact_escaped_json_pointers_and_do_not_modify_documents():
    documents = {"p1.research_basis": {"attention/items": [{"context_markdown": r"Choose $\unknownCommand{x}$."}],
                                        "literal~field": {"latex": r"\frac{1}{"}}}
    before = copy.deepcopy(documents)
    findings = validate_authored_math(documents)
    assert {f.json_pointer for f in findings} == {"/attention~1items/0/context_markdown", "/literal~0field/latex"}
    assert all(f.code == "math.invalid_latex" and f.object_id == "p1.research_basis" for f in findings)
    assert all(f.blocks_publication for f in findings)
    assert documents == before


def test_overescaped_latex_is_not_accepted_as_successful_math():
    findings = validate_authored_math({"p1.research_basis": {"context_markdown": r"$\\Pr(H>B)\\le1-\\tau$"}})
    assert [f.code for f in findings] == ["math.overescaped_latex"]


def test_unclosed_display_equation_returns_its_field_to_the_author():
    findings = validate_authored_math({"p1.research_basis": {"research_setting": {
        "statement_markdown": r"Target $$q_\tau(H)\le B"}}})
    assert len(findings) == 1
    assert findings[0].code == "math.invalid_delimiter"
    assert findings[0].json_pointer == "/research_setting/statement_markdown"


def test_prose_code_urls_and_valid_aligned_equations_do_not_block():
    documents = {"p1.research_basis": {"text": "Plain words. `$\\badMacro$`\n```tex\n$\\badMacro$\n```",
                    "url": "https://example.org/$\\badMacro$",
                    "formula": r"$$\begin{aligned}x&=1\\\theta&=2\end{aligned}$$",
                    "latex": r"\begin{matrix}1&2\\3&4\end{matrix}"}}
    assert validate_authored_math(documents) == []


def test_recovered_named_definitions_validate_exact_fields_without_guessing_prose():
    canonical = {
        "target_or_estimand": {"definition": r"\theta=\unknownTarget{Y}"},
        "objective_or_estimating_equation": {"definition": r"\psi=\unknownScore{Y}"},
        "constraints_and_normalization": [
            {"definition": r"x=\unknownConstraint{Y}"},
            {"definition": r"Every observation needs x = 1."},
            {"definition": r"The value x=\unknownCommand{Y} remains prose."},
            {"definition": r"`x=\unknownCode{Y}`"},
            {"definition": r"https://example.org/?x=\unknownUrl{Y}"},
            {"definition": r"\[x=\unknownDelimited{Y}\]"},
            {"definition": r"x=E[Y]"},
        ],
        "unrelated": {"definition": r"x=\unknownUnrelated{Y}"},
    }
    documents = {"p2.theory_proposal": {"method": {"mathematical_definition": {"canonical_definition": canonical}}}}
    before = copy.deepcopy(documents)
    findings = validate_authored_math(documents)
    prefix = "/method/mathematical_definition/canonical_definition/"
    assert {f.json_pointer for f in findings} == {prefix + path for path in (
        "target_or_estimand/definition", "objective_or_estimating_equation/definition",
        "constraints_and_normalization/0/definition", "constraints_and_normalization/5/definition")}
    assert all(f.code == "math.invalid_latex" and f.blocks_publication for f in findings)
    assert documents == before


def test_p2_bare_formula_errors_reach_draft_and_publication_checks(draft_engine):
    engine = draft_engine
    record, stages, _ = run(engine, "P2", "p2.full_catalog")
    stage = stages[0]
    role = MemberRole.THEORIST
    documents, files = p2_documents(False)
    document = documents["p2.theory_proposal"]
    target = document["method"]["mathematical_definition"]["canonical_definition"]["target_or_estimand"]
    target["definition"] = r"\theta=\unknownTarget{Y}"
    pointer = "/method/mathematical_definition/canonical_definition/target_or_estimand/definition"
    workspace = engine.member_workspace(record, stage.stage_id, role)
    write_outputs(workspace, {"p2.theory_proposal": document}, files)
    result = check(engine, record, stage, role)
    assert any(f["code"] == "math.invalid_latex" and f["json_pointer"] == pointer for f in result["findings"])
    sealed = engine.run_dir(record.project_id, record.run_id) / "outputs" / stage.stage_id
    write_outputs(sealed, {"p2.theory_proposal": document}, files)
    findings = engine._validate_run_outputs(record, [stage], [], scoped_outputs={"p2.theory_proposal"})
    assert any(f.code == "math.invalid_latex" and f.json_pointer == pointer for f in findings)
    target["definition"] = r"\theta=E[Y]"
    write_outputs(workspace, {"p2.theory_proposal": document}, files)
    assert "math.invalid_latex" not in codes(check(engine, record, stage, role))


def test_author_receives_math_findings_while_drafting_and_final_gate_rechecks(draft_engine):
    engine = draft_engine
    record, stages, _ = run(engine, "P1", "p1.literature_update")
    stage = stages[0]
    role = MemberRole.RESEARCH_LEAD
    document = p1_documents()["p1.lead_literature"]
    # A schema-valid authored field. The math checker must run in the ordinary
    # member tool before any other member or downstream synthesis is ready.
    document["papers"][0]["explanation_markdown"] = r"Invalid $\badMacro$."
    workspace = engine.member_workspace(record, stage.stage_id, role)
    write_outputs(workspace, {"p1.lead_literature": document})
    result = check(engine, record, stage, role)
    assert "math.invalid_latex" in codes(result), result["findings"]
    assert result["scientific_correctness"] == "not_assessed"
    sealed = engine.run_dir(record.project_id, record.run_id) / "outputs" / stage.stage_id
    write_outputs(sealed, {"p1.lead_literature": document})
    findings = engine._validate_run_outputs(record, [stage], [], scoped_outputs={"p1.lead_literature"})
    assert any(f.code == "math.invalid_latex" for f in findings)
    document["papers"][0]["explanation_markdown"] = r"A valid bound $$\Pr(H>B)\le1-\tau$$."
    write_outputs(workspace, {"p1.lead_literature": document})
    assert "math.invalid_latex" not in codes(check(engine, record, stage, role))


def test_later_phase_graph_latex_is_checked_during_its_own_task(draft_engine):
    engine = draft_engine
    record, stages, identity = run(engine, "P3", "p3.theory_establishment")
    stage = stages[0]
    documents, files = scientific_output_documents(Catalog(REPO / "contracts"), "P3", identity)
    documents["p3.claim_map"]["claims"][0]["latex"] = r"\unknownSymbol"
    write_outputs(engine.member_workspace(record, stage.stage_id, MemberRole.THEORIST),
                  {family: documents[family] for family in stage.writes}, files)
    findings = check(engine, record, stage, MemberRole.THEORIST)["findings"]
    assert any(f["code"] == "math.invalid_latex" and f["object_id"] == "p3.claim_map"
               and f["json_pointer"] == "/claims/0/latex" for f in findings)


def test_member_guidance_requires_display_equations_and_own_draft_correction(draft_engine):
    record, stages, _ = run(draft_engine, "P1", "p1.literature_update")
    brief = draft_engine._artifact_check_brief(record, stages[-1], MemberRole.RESEARCH_LEAD)
    assert "major equations are centered" in brief
    assert "aligned environment" in brief
    assert "Correct reported LaTeX in your own draft before finishing" in brief
    assert "does not assess the equation's scientific correctness" in brief
