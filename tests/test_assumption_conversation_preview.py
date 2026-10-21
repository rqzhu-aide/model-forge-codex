"""The simulated preview must answer its supported question or disclose its limit."""
import importlib.util
from pathlib import Path

from model_forge_codex.domain import RunState
from model_forge_codex.methods import get_method
from model_forge_codex.storage import read_json
from test_researcher_workbench_engine import workbench, publish, target


spec = importlib.util.spec_from_file_location(
    "assumption_preview", Path(__file__).resolve().parents[1] / "scripts/assumption_conversations_preview.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


async def test_question_about_removing_assumption_gets_consequences_not_generic_motivation(workbench):
    engine, project, branch = workbench
    engine.bridge = preview.ConversationPreviewBridge()
    theory = read_json(Path(__file__).resolve().parents[1] / "contracts/examples/theory-record.example.json")
    theory["method_identity"] = get_method(project, branch)["identity"]
    package = publish(project, branch, "P3", {"theory_record": theory})
    source = {**target(package, branch), "object_id": preview.ASSUMPTION_ID}
    question = "What happens if we do not have this assumption?"
    run = await engine.start_run("project.test", phase="P3", mode="p3.assessment", branch_id=branch,
                                 intent="assessment", assessment_purpose="explanation", target=source,
                                 instructions=question)
    await engine._tasks[run.run_id]
    assert engine.load_run("project.test", run.run_id).state is RunState.ASSESSED
    turn = engine.list_assessments("project.test", branch)[0]["turns"][0]
    first_paragraph = turn["assessment_markdown"].split("\n\n")[0]
    assert "Without Assumption A1" in first_paragraph
    assert "no longer justifies" in first_paragraph
    assert "does not show that the estimator fails" in first_paragraph
    assert "unverified" in turn["assessment_markdown"]
    assert "\\Pr" not in turn["assessment_markdown"]
    assert turn["instructions"] == question
    assert turn["evidence_refs"][0]["generation_ref"]["generation_id"] == source["generation_id"]


def test_unsupported_questions_and_other_assumptions_do_not_receive_a1_explanations():
    for question, assumption_id in (
        ("What sample size should I choose?", preview.ASSUMPTION_ID),
        ("Can you give a counterexample to the normality theorem?", preview.ASSUMPTION_ID),
        ("What happens if we do not have this assumption?", "assumption.example_a2"),
    ):
        answer, uses_source = preview.scripted_explanation(question, assumption_id)
        assert "No model was called" in answer
        assert "no prepared answer" in answer
        assert not uses_source
        assert "sub-Gaussian" not in answer


def test_necessity_question_gets_a_direct_answer_separate_from_motivation():
    answer, uses_source = preview.scripted_explanation(
        "Does the saved proof establish that this assumption is necessary?", preview.ASSUMPTION_ID)
    assert answer.startswith("**Simulated explanation.** No.")
    assert uses_source
