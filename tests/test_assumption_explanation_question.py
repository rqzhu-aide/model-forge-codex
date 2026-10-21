"""Question-focused answer guidance reaches explanation turns only."""

from model_forge_codex.domain import RunState
from test_assumption_conversations import ask, set_answer
from test_researcher_workbench_engine import seed_theory, target, workbench


async def test_removing_assumption_question_receives_direct_answer_and_evidence_guidance(workbench):
    engine, project, branch = workbench
    package = seed_theory(project, branch)
    set_answer(engine, package)

    run = await ask(engine, branch, package, "What happens if we do not have this assumption?")

    assert run.state is RunState.ASSESSED
    brief = engine.bridge.turns[-1]["brief"]
    assert "Researcher note (verbatim):\nWhat happens if we do not have this assumption?" in brief
    assert "Start assessment_markdown with a direct answer in one or two sentences" in brief
    assert "which guarantee is no longer justified by the saved argument" in brief
    assert "Distinguish an argument that no longer applies from a result or method that actually fails" in brief
    assert "surviving results or valid weaker assumptions only when supported" in brief
    assert "otherwise state what remains unknown" in brief
    assert "For other questions, follow the requested focus" in brief


async def test_ordinary_assessment_keeps_its_own_objective(workbench):
    engine, project, branch = workbench
    package = seed_theory(project, branch)
    set_answer(engine, package)

    run = await engine.start_run(
        "project.test", phase="P3", mode="p3.assessment", branch_id=branch,
        intent="assessment", target=target(package, branch),
        instructions="What happens if we do not have this assumption?",
    )
    await engine._tasks[run.run_id]

    assert engine.load_run("project.test", run.run_id).state is RunState.ASSESSED
    brief = engine.bridge.turns[-1]["brief"]
    assert "Component assessment" in brief
    assert "Examine the component without presuming an error" in brief
    assert "Start assessment_markdown with a direct answer" not in brief
    assert "which guarantee is no longer justified" not in brief
