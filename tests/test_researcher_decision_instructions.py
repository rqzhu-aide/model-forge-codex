"""New decisions are consequential and compact without upgrading historical reads."""
from copy import deepcopy
from pathlib import Path
import shutil
from types import SimpleNamespace

from jsonschema import Draft202012Validator
import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole
from model_forge_codex.math_validation import validate_authored_math
from model_forge_codex.problem_context import frozen_problem_context, save_context_item
from model_forge_codex.researcher_pause import pause_brief
from model_forge_codex.researcher_language import RESEARCHER_LANGUAGE_GUIDANCE
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import record, workbench


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def assert_mathematical_choice_guidance(text, context_field="context_markdown"):
    assert context_field in text
    assert "affected problem or equation" in text
    assert "enough formulation to understand the decision" in text
    assert "defining symbols and any shared objective once" in text
    assert "consequence gives its formulation or changed equation under that shared context" in text
    assert "concise practical effect" in text
    assert "prose-only options do not explain a mathematical distinction" in text
    assert "Plain study facts, budgets and choices without a mathematical distinction need no artificial equation" in text


def assert_editorial_formulation_guidance(text, context_field="context_markdown"):
    assert context_field + " shows the affected problem or equation" in text
    assert "defining symbols and any shared objective once" in text
    assert "Each option's consequence shows that retained formulation as it would appear" in text
    assert "This does not authorize choosing between scientific definitions" in text
    assert "Choices without a mathematical distinction need no artificial equation" in text
    assert "When mathematics distinguishes the choices" not in text
    assert "Each mathematically distinct option's consequence gives its formulation or changed equation" not in text


def test_legacy_attention_remains_readable_without_invented_priority():
    catalog = Catalog(CONTRACTS)
    item = read_json(CONTRACTS / "examples/attention-setting-decision.example.json")
    item.pop("decision_priority")
    item.pop("response_kind")
    item["options"] = ["Enrolled cohort", {"label": "Wider population"}]
    before = deepcopy(item)
    validator = Draft202012Validator(catalog.schema_doc("attention-item.schema.json"),
                                    registry=catalog._registry)
    assert not list(validator.iter_errors(item))
    assert item == before


def test_specialist_fact_proposal_needs_no_repeated_rationale():
    catalog = Catalog(CONTRACTS)
    document = read_json(CONTRACTS / "examples/literature-findings.example.json")
    document["proposed_questions"] = [{
        "question": "How many eligible patients and outcome events are available?",
        "context_markdown": "No patient data or dictionary has been supplied. The encoded feature dimension and event support remain unknown.",
        "answer_consequences_markdown": "The team can review conditional formulations now; actual-data feasibility remains unestablished until these counts and dimensions are known.",
        "source_refs": [],
    }]
    assert not catalog.validate_output("p1.empirical_literature", document)


def test_option_formulations_fit_existing_fields_and_supported_math():
    item = read_json(CONTRACTS / "examples/attention-setting-decision.example.json")
    item.update(
        question="Should cost protection limit tail risk or mean cost?",
        context_markdown=(r"Let $G_R$ and $G_C$ be reward and cost returns under policy $\pi$ from admissible class $\Pi$. "
                          r"Both choices maximize expected reward, $\max_{\pi\in\Pi}\mathbb E_\pi[G_R]$. "
                          r"Here $b$ is a cost threshold, $\alpha$ an allowed exceedance probability, "
                          r"and $B$ an allowed mean cost. The intended cost protection remains unspecified."),
        likely_consequence="The choice determines which cost behavior the eventual claim must address.",
        options=[
            {"id": "tail", "label": "Limit exceedance probability",
             "consequence": (r"Use the constraint $$\Pr_\pi(G_C>b)\le\alpha.$$ "
                             "Controls how often cost exceeds the threshold; it does not bound exceedance size.")},
            {"id": "mean", "label": "Limit mean cost",
             "consequence": (r"Use the constraint $$\mathbb E_\pi[G_C]\le B.$$ "
                             "Controls average cost; it does not impose the same exceedance probability limit.")},
        ],
        recommendation="Choose the protection matching the intended use; neither preference establishes feasibility.",
    )
    before = deepcopy(item)
    assert not Catalog(CONTRACTS).validate_output("p3.attention_items", [item])
    assert not validate_authored_math({"p3.attention_items": [item]})
    assert item == before


@pytest.mark.parametrize("phase", ["P1", "P2", "P3", "P4", "P5"])
def test_all_stage_objectives_include_reader_context_without_new_output(phase):
    contract = read_json(CONTRACTS / f"contracts/phases/{phase}.json")
    for stage in contract["role_stages"]:
        assert stage["objective"].count(RESEARCHER_LANGUAGE_GUIDANCE) == 1
        assert "within your owned outputs and permitted interaction scope" in stage["objective"]
    if phase == "P5":
        assert all("Researcher-directed attention and pauses remain limited to indispensable editorial choices" in stage["objective"]
                   for stage in contract["role_stages"])
        assert all("Scientific open-question findings stay in the owned review output or source records" in stage["objective"]
                   for stage in contract["role_stages"])


@pytest.mark.parametrize("example", ["donor_weighting", "pairing_unknown", "cost_timing"])
def test_cross_domain_questions_keep_existing_fields_and_renderable_math(example):
    item = read_json(CONTRACTS / "examples/attention-setting-decision.example.json")
    item.pop("options", None)
    item.pop("recommendation", None)
    item["severity"] = "minor"
    if example == "donor_weighting":
        item.update(
            question="Should the primary comparison describe an equally weighted donor population or a population weighted by sampled cells?",
            response_kind="choice",
            context_markdown=(r"In this illustrative design, $Y_{ij}$ is expression in cell $j$ from donor $i$, "
                              r"and $n_i$ is the number of sampled cells. The population weighting target is unresolved. "
                              "The following sample summaries illustrate the distinction; neither choice makes cells independent."),
            likely_consequence="The target determines which donors contribute more to the scientific comparison; inference still needs the sampling structure.",
            recommendation="The intended biological population is unspecified, so there is no justified default weighting target yet.",
            options=[
                {"id": "donor", "label": "Equal donor weight", "consequence":
                 r"$\bar Y_D=N^{-1}\sum_i n_i^{-1}\sum_jY_{ij}$ gives each donor equal weight."},
                {"id": "cell", "label": "Weight by sampled cells", "consequence":
                 r"$\bar Y_C=(\sum_i\sum_jY_{ij})/(\sum_i n_i)$ gives donors with more sampled cells more influence."},
            ],
        )
    elif example == "pairing_unknown":
        item.update(
            question="Optional: can before- and after-perturbation samples be linked to the same donors?",
            response_kind="study_fact",
            context_markdown="The supplied material does not establish matching. Unknown is acceptable; conditional planning can continue.",
            likely_consequence="This determines whether within-donor changes can be computed. It does not establish randomization or eliminate confounding.",
        )
    else:
        item.update(
            question="Optional: when are past cost measurements available to the decision system?",
            response_kind="study_fact",
            context_markdown=(r"The retained policy selects $A_t$ using the observed history $\mathcal H_t$. "
                              r"A measured cost can enter $\mathcal H_t$ only if available before that action. "
                              "Timing is unspecified; abstract work can continue conditionally."),
            likely_consequence="This determines which past costs an implemented policy can use, not whether the mathematical proof is valid.",
        )
    before = deepcopy(item)
    assert not Catalog(CONTRACTS).validate_output("p3.attention_items", [item])
    assert not validate_authored_math({"p3.attention_items": [item]})
    assert item == before


@pytest.mark.parametrize("phase", ["P1", "P2", "P3", "P4", "P5"])
def test_executable_lead_instructions_author_compact_decisions(phase):
    source = read_json(CONTRACTS / "contracts/phases.json")
    expected = next(contract for contract in source["contracts"] if contract["phase_id"] == phase)
    contract = read_json(CONTRACTS / f"contracts/phases/{phase}.json")
    assert contract == expected
    assert "consequential_researcher_decisions_v1" in contract["capabilities"]
    for stage in contract["role_stages"]:
        if stage["execution"] == "serial" and stage["roles"] == ["research_lead"]:
            objective = stage["objective"]
            if phase == "P5":
                assert_editorial_formulation_guidance(objective)
            else:
                assert_mathematical_choice_guidance(objective)
            assert all(field in objective for field in ("decision_priority", "response_kind", "{id,label,consequence}", "recommendation"))
            assert "Empty attention output is valid" in objective or "attention_items may be empty" in objective
            if phase != "P5":
                assert "Different mathematical definitions or defensible alternatives alone do not create a researcher decision" in objective
                assert "counting all attempted developments" in objective
                assert "Preserve the intended inferential claim" in objective
                assert "existing owned attention output at its designated stage even if conditional work can proceed" in objective
                assert "Do not omit such an invitation merely because it is not a blocker" in objective
                assert "In an eligible stage" in objective
                assert "there is no question quota" in objective


@pytest.mark.parametrize("phase,mode", [
    ("P1", "p1.literature_update"), ("P2", "p2.full_catalog"),
    ("P3", "p3.theory_establishment"), ("P4", "p4.preliminary"),
])
def test_generated_lead_brief_distinguishes_invitation_team_work_and_blocker(workbench, phase, mode):
    engine, project, method_branch = workbench
    unknown = "The intended use of the first useful result remains unknown."
    save_context_item(project, unknown, expected_revision=1, origin="unknown")
    context = frozen_problem_context(project)
    branch = "trunk" if phase in {"P1", "P2"} else method_branch
    candidate = record(engine, branch, "run.invitation." + phase, phase, mode)
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    basis = engine.compute_basis(candidate.project_id, phase, branch, mode)
    write_json_atomic(directory / "basis.json", basis)
    stage = next(stage for stage in reversed(engine.stage_plan(candidate.project_id, phase, mode))
                 if stage.roles == (MemberRole.RESEARCH_LEAD,))
    brief = engine._render_brief(candidate, stage, MemberRole.RESEARCH_LEAD,
                                 engine.member_workspace(candidate, stage.stage_id, MemberRole.RESEARCH_LEAD))

    # The actual member brief must offer steering despite conditional progress,
    # while retaining scientific ownership and a distinct blocking threshold.
    assert "existing owned attention output at its designated stage even if conditional work can proceed" in brief
    assert "claim to support first or reference standard for judging success" in brief
    assert "keeping any proposed default provisional until adopted" in brief
    assert "Different mathematical definitions or defensible alternatives alone do not create a researcher decision" in brief
    assert "scientific judgment and routine choices within the agreed goal and budget" in brief
    assert "pause only when missing input makes the next authorized action unjustified" in brief
    assert "an unresolved consequential preference remains eligible for a useful nonblocking invitation" in brief
    assert "Reuse exact applicable saved answers" in brief
    assert "Unknown and no-data responses remain legitimate" in brief
    assert "there is no question quota" in brief
    assert "A researcher cannot certify assumptions by preference" in brief
    assert_mathematical_choice_guidance(brief)
    assert "revisit only when needed" not in brief
    assert unknown in brief
    assert frozen_problem_context(project) == context
    assert read_json(directory / "basis.json") == basis
    assert engine.bridge.turns == [] and engine._tasks == {}


@pytest.mark.parametrize("phase,mode,parallel_rule", [
    ("P1", "p1.literature_update", "Do not create attention records, fabricate answers, pause parallel discovery"),
    ("P2", "p2.full_catalog", "This output schema has no attention_items or separate question artifact"),
])
def test_generated_parallel_brief_keeps_invitation_at_designated_lead_stage(workbench, phase, mode, parallel_rule):
    engine, project, _ = workbench
    candidate = record(engine, "trunk", "run.parallel.invitation." + phase, phase, mode)
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    write_json_atomic(directory / "basis.json", engine.compute_basis(candidate.project_id, phase, "trunk", mode))
    stage = next(stage for stage in engine.stage_plan(candidate.project_id, phase, mode)
                 if stage.execution == "parallel")
    for role in stage.roles:
        brief = engine._render_brief(candidate, stage, role, engine.member_workspace(candidate, stage.stage_id, role))
        assert parallel_rule in brief
        assert "existing owned attention output at its designated stage" in brief
        assert "members propose it in their existing owned outputs for consolidation" in brief
        assert "In an eligible stage" in brief
        if phase == "P1":
            assert "affected premise and sufficient mathematical formulation when relevant in context_markdown" in brief
            assert "make mathematically distinct alternatives explicit for Lead consolidation" in brief
    assert engine.bridge.turns == [] and engine._tasks == {}


def test_generated_p5_lead_brief_keeps_scientific_steering_upstream(workbench):
    engine, project, branch = workbench
    candidate = record(engine, branch, "run.invitation.P5", "P5", "p5.assembly")
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    write_json_atomic(directory / "basis.json", engine.compute_basis(candidate.project_id, "P5", branch, "p5.assembly"))
    stage = next(stage for stage in engine.stage_plan(candidate.project_id, "P5", "p5.assembly")
                 if stage.roles == (MemberRole.RESEARCH_LEAD,))
    brief = engine._render_brief(candidate, stage, MemberRole.RESEARCH_LEAD,
                                 engine.member_workspace(candidate, stage.stage_id, MemberRole.RESEARCH_LEAD))
    assert "indispensable editorial choice" in brief
    assert "Do not reopen problem, collection, method or study-design questions from P1-P4" in brief
    assert "missing scientific inputs" in brief.lower()
    assert_editorial_formulation_guidance(brief)
    assert "claim to support first or reference standard for judging success" not in brief
    assert "an unresolved consequential preference remains eligible for a useful nonblocking invitation" not in brief
    assert engine.bridge.turns == [] and engine._tasks == {}


def test_nonblocking_pause_guidance_does_not_manufacture_a_question():
    stage = SimpleNamespace(execution="serial", roles=["research_lead"])
    brief = pause_brief(SimpleNamespace(phase="P2", intent="run"), stage, "research_lead")
    assert "Attention may be empty; do not manufacture a question" in brief
    assert "Otherwise continue justified work with explicit conditions" in brief
    assert "existing owned attention output at its designated stage even if conditional work can proceed" in brief
    assert "If that missing input makes the next authorized action unjustified" in brief
    assert "reuse exact applicable saved answers" in brief.lower()
    assert "no question quota" in brief
    assert "revisit only when needed" not in brief
    assert "author an informational attention question" not in brief
    assert_mathematical_choice_guidance(brief, "reason")
    editorial = pause_brief(SimpleNamespace(phase="P5", intent="run"), stage, "research_lead")
    assert "indispensable editorial choice" in editorial
    assert "Do not reopen problem, collection, method or study-design questions" in editorial
    assert_editorial_formulation_guidance(editorial, "reason")


@pytest.mark.parametrize("role", [MemberRole.DATA_ANALYST, MemberRole.THEORIST, MemberRole.RESEARCH_LEAD])
def test_generated_p4_member_brief_explains_mathematical_pause_options(workbench, role):
    engine, project, branch = workbench
    candidate = record(engine, branch, "run.math.pause." + role.value, "P4", "p4.preliminary")
    directory = engine.run_dir(candidate.project_id, candidate.run_id)
    shutil.copytree(project / "contracts", directory / "contracts")
    write_json_atomic(directory / "basis.json", engine.compute_basis(candidate.project_id, "P4", branch, "p4.preliminary"))
    stage = next(stage for stage in engine.stage_plan(candidate.project_id, "P4", "p4.preliminary")
                 if stage.roles == (role,))
    brief = engine._render_brief(candidate, stage, role, engine.member_workspace(candidate, stage.stage_id, role))

    assert "A pause uses request_decision" in brief
    assert_mathematical_choice_guidance(brief, "reason")
    assert "Do not manufacture alternatives for a study fact" in brief
    assert engine.bridge.turns == [] and engine._tasks == {}
