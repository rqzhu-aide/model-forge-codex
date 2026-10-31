"""Draft answer choices survive discussion without saving or changing science."""
import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import RunState
from model_forge_codex.phase_interactions import published_issues, save_scoped_answer
from model_forge_codex.records import current_records
from model_forge_codex.runs import RunError
from test_decision_choices import choice
from test_issue_suggestions import ask
from test_phase_interactions import answer
from test_researcher_workbench_engine import publish, workbench


def question(project, branch, *, suffix="one", option_id="all"):
    item = choice(target_phase="P3", options=[
        {"id": option_id, "label": "All eligible individuals", "consequence": "Includes incomplete follow-up."},
        {"id": "observed", "label": "Observed individuals", "consequence": "Restricts the target population."},
    ])
    publish(project, branch, "P3", {"attention_items": [item]}, "run.question." + suffix)
    return next(item for item in published_issues(project, branch)
                if item.get("explanation_target", {}).get("run_id") == "run.question." + suffix)


@pytest.mark.parametrize("purpose", ["issue_explanation", "issue_suggestions", "model_dialogue"])
async def test_no_note_choice_reaches_brief_with_saved_answer_separate(workbench, purpose):
    engine, project, branch = workbench
    issue = question(project, branch)
    saved = save_scoped_answer(project, issue, "Still considering the population.", expected_revision=0)
    answers = project / "researcher/attention_resolutions.json"
    before = answers.read_bytes()
    sources = current_records(project / "branches" / branch / "phases/p3")
    answer(engine)
    run = await ask(engine, issue, purpose, researcher_response_draft={"kind": "choice", "option_id": "all", "note": ""})
    assert run.state is RunState.ASSESSED, run.terminal_reason
    expected = {"kind": "choice", "option_id": "all", "label": "All eligible individuals",
                "consequence": "Includes incomplete follow-up.", "note": ""}
    assert run.researcher_response_draft == expected
    brief = engine.bridge.turns[-1]["brief"]
    assert "Researcher answer draft (unsaved" in brief and expected["label"] in brief
    assert "not a saved answer, adopted preference or validated fact" in brief
    assert saved["note"] in brief
    history = engine.list_assessments("project.test")[0]
    assert history["researcher_response_draft"] == expected
    assert history["messages"][0]["researcher_response_draft"] == expected
    assert answers.read_bytes() == before
    assert current_records(project / "branches" / branch / "phases/p3") == sources


async def test_actual_discussion_freezes_references_and_followup_ignores_project_edits(workbench):
    engine, project, branch = workbench
    issue = question(project, branch)
    original = (project / "contracts/references/research-presentation/user-inquiry.md").read_text(encoding="utf-8").strip()
    answer(engine)
    first = await ask(engine, issue)
    assert first.state is RunState.ASSESSED
    frozen = engine.run_dir("project.test", first.run_id) / "contracts"
    assert Catalog(frozen).verify_manifest() == []
    assert len(list((frozen / "references/research-presentation").glob("*.md"))) == 5
    assert engine.bridge.turns[-1]["brief"].count(original) == 1
    (project / "contracts/references/research-presentation/user-inquiry.md").write_text("Later project guidance", encoding="utf-8")
    second = await ask(engine, issue, assessment_id=first.assessment_id)
    assert second.state is RunState.ASSESSED
    brief = engine.bridge.turns[-1]["brief"]
    assert brief.count(original) == 1 and "Later project guidance" not in brief


@pytest.mark.parametrize("draft", [
    {"kind": "unknown", "note": ""}, {"kind": "custom", "note": "Restrict to the intended clinic population."},
])
async def test_unknown_and_custom_remain_provisional(workbench, draft):
    engine, project, branch = workbench
    issue = question(project, branch)
    answer(engine)
    run = await ask(engine, issue, researcher_response_draft=draft)
    assert run.state is RunState.ASSESSED
    assert run.researcher_response_draft == draft
    assert not (project / "researcher/attention_resolutions.json").exists()


async def test_wrong_option_and_client_text_rejected_before_model_call(workbench):
    engine, project, branch = workbench
    issue = question(project, branch)
    for draft in ({"kind": "choice", "option_id": "missing"},
                  {"kind": "choice", "option_id": "all", "label": "Client injected interpretation"}):
        with pytest.raises(RunError):
            await ask(engine, issue, researcher_response_draft=draft)
    assert engine.bridge.turns == []


async def test_retry_retains_authoritative_draft_and_followup_uses_frozen_question(workbench):
    engine, project, branch = workbench
    issue = question(project, branch)
    engine.bridge.default_behavior = ("fail", "Temporary failure")
    failed = await ask(engine, issue, researcher_response_draft={"kind": "choice", "option_id": "all"})
    assert failed.state is RunState.FAILED
    question(project, branch, suffix="new", option_id="new-population")
    answer(engine)
    retry = await ask(engine, issue, assessment_id=failed.assessment_id, retry_run_id=failed.run_id)
    assert retry.state is RunState.ASSESSED, retry.terminal_reason
    assert retry.researcher_response_draft == failed.researcher_response_draft
    followup = await ask(engine, issue, assessment_id=failed.assessment_id,
                         researcher_response_draft={"kind": "choice", "option_id": "observed"})
    assert followup.state is RunState.ASSESSED
    assert followup.researcher_response_draft["label"] == "Observed individuals"
    with pytest.raises(RunError, match="exact question"):
        await ask(engine, issue, assessment_id=failed.assessment_id,
                  researcher_response_draft={"kind": "choice", "option_id": "new-population"})
