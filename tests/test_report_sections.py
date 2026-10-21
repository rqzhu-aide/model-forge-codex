"""A report discussion binds one authored section; comments remain researcher notes."""
import json
import shutil

import pytest

from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.records import current_records, generation_path
from model_forge_codex.report_sections import (resolve_report_section, load_section_comment, save_section_comment)
from model_forge_codex.runs import RunError
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from model_forge_codex.technical_reports import CONTENT_SECTIONS
from test_phase_interactions import answer
from test_researcher_workbench_api import api
from test_researcher_workbench_engine import workbench, publish, seed_theory


def retained_report(engine, project, branch, *, markdown=None, run_id="run.report"):
    seed_theory(project, branch)
    basis = engine.compute_basis("project.test", "P5", branch, "p5.assembly")
    directory = project / "runs" / run_id
    shutil.copytree(project / "contracts", directory / "contracts")
    for ref in basis["records"]:
        source = generation_path(project / "branches" / ref["branch"] / "phases" / ref["phase"].lower(), ref["family"], ref)
        destination = directory / "inputs" / ref["family"] / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        ref["snapshot_path"] = str(destination)
    for ref in basis.get("cumulative_inputs", {}).values():
        # Report discussions use selected exact records, never a newly built index.
        ref.pop("snapshot_path", None)
    write_json_atomic(directory / "basis.json", basis)
    primary = directory / "outputs" / "p5.assembly" / "report.md"
    primary.parent.mkdir(parents=True, exist_ok=True)
    markdown = markdown or "# Full technical report\n\n" + "\n\n".join(
        f'<a id="{key}"></a>\n## {key.replace("_", " ").title()}\n\nSECTION_{key.upper()} $x^2$.\n'
        for key in CONTENT_SECTIONS)
    primary.write_text(markdown, encoding="utf-8")
    theory = next(ref for ref in basis["records"] if ref["family"] == "theory_record")
    report = {"record_type": "technical_report", "title": "Exact technical report", "sections_present": list(CONTENT_SECTIONS),
              "section_anchors": {key: key for key in CONTENT_SECTIONS},
              "report_artifact": {"artifact_id": "artifact.report", "path": "report.md", "sha256": sha256_file(primary)},
              "claims": [{"claim_id": "claim.math", "text": "The exact retained argument.", "anchor": "justification",
                          "source_refs": [{key: theory[key] for key in ("branch", "phase", "family", "generation_id", "content_sha256")}]}]}
    package = publish(project, branch, "P5", {"technical_report": report}, run_id)
    pointer = package["records"]["technical_report"]
    target = {"kind": "report_section", "branch": branch, "phase": "P5", "family": "technical_report", "object_id": "justification",
              **{key: pointer[key] for key in ("generation_id", "run_id", "package_id")}, "sha256": pointer["content_sha256"]}
    return target, primary


async def discuss(engine, target, text="Explain the main argument.", **extra):
    record = await engine.start_run("project.test", phase="P5", mode="p3.assessment", branch_id=target["branch"],
        intent="assessment", assessment_purpose="model_dialogue", target=None if extra.get("assessment_id") else target,
        instructions=text, **extra)
    await engine._tasks[record.run_id]
    return engine.load_run("project.test", record.run_id)


def test_exact_section_contains_children_and_excludes_other_main_sections(workbench):
    engine, project, branch = workbench
    target, _ = retained_report(engine, project, branch)
    issue = resolve_report_section(project, target)
    assert "SECTION_JUSTIFICATION" in issue["summary_markdown"]
    assert "SECTION_MODEL" not in issue["summary_markdown"]
    assert "SECTION_NUMERICAL_ANALYSIS" not in issue["summary_markdown"]
    assert issue["responsible_role"] == "research_lead"
    assert len(issue["claims"]) == 1
    for changed in ({"sha256": "0" * 64}, {"package_id": "package.missing"}, {"object_id": "unknown"}, {"family": "manuscript"}):
        with pytest.raises(ValueError):
            resolve_report_section(project, {**target, **changed})


@pytest.mark.parametrize("markdown", [
    '<a id="justification"></a>\n## Justification\nOne\n<a id="justification"></a>\n## Duplicate\nTwo',
    '## Justification\nThe authored anchor is missing.',
    '```md\n<a id="justification"></a>\n## Fake\n```',
    '   ```md\n<a id="justification"></a>\n## Fake\n   ```',
    '<a id="justification"></a>\nThis is prose without a heading.',
])
def test_missing_or_ambiguous_anchor_is_not_guessed(workbench, markdown):
    engine, project, branch = workbench
    target, _ = retained_report(engine, project, branch, markdown=markdown)
    with pytest.raises(ValueError, match="anchor|heading"):
        resolve_report_section(project, target)


@pytest.mark.parametrize("opening", ['## Argument <a id="justification"></a>', '## Argument\n\n<a id="justification"></a>', '   <a id="justification"></a>\n   ## Argument'])
def test_authored_anchor_before_after_or_on_heading(workbench, opening):
    engine, project, branch = workbench
    markdown = opening + '\n\nEXACT_ARGUMENT\n### Subargument\nCHILD_ARGUMENT\n\n<a id="limitations"></a>\n## Limitations\nEXCLUDED'
    target, _ = retained_report(engine, project, branch, markdown=markdown)
    text = resolve_report_section(project, target)["summary_markdown"]
    assert "EXACT_ARGUMENT" in text and "CHILD_ARGUMENT" in text
    assert "EXCLUDED" not in text and "## Limitations" not in text


def test_comment_edit_clear_history_conflict_and_report_version_isolation(workbench):
    engine, project, branch = workbench
    target, source = retained_report(engine, project, branch)
    before = source.read_bytes()
    assert load_section_comment(project, target) is None
    first = save_section_comment(project, target, "I need a clearer premise.", 0)
    edited = save_section_comment(project, target, "Please explain the premise.", first["revision"])
    assert edited["revision"] == 2
    with pytest.raises(ValueError, match="changed"):
        save_section_comment(project, target, "Stale edit", 1)
    cleared = save_section_comment(project, target, "", 2)
    assert cleared["note"] == "" and cleared["revision"] == 3
    stored = read_json(next((project / "researcher" / "report_section_comments").glob("*.json")))
    assert [item["revision"] for item in stored["history"]] == [1, 2]
    assert source.read_bytes() == before
    assert not (project / "researcher" / "attention_resolutions.json").exists()
    assert load_section_comment(project, {**target, "object_id": "model"}) is None
    next_target, _ = retained_report(engine, project, branch, run_id="run.report.next")
    assert load_section_comment(project, next_target) is None
    assert load_section_comment(project, target)["revision"] == 3


async def test_lead_discussion_uses_one_section_exact_support_and_latest_comment_per_question(workbench):
    engine, project, branch = workbench
    target, primary = retained_report(engine, project, branch)
    save_section_comment(project, target, "FIRST_COMMENT", 0)
    before = current_records(project / "branches" / branch / "phases" / "p5")
    answer(engine)
    first = await discuss(engine, target)
    assert first.state is RunState.ASSESSED, first.terminal_reason
    assert engine._stages(first)[0].roles == (MemberRole.RESEARCH_LEAD,)
    brief = engine.bridge.turns[-1]["brief"]
    assert "Report section discussion" in brief and "SECTION_JUSTIFICATION" in brief and "FIRST_COMMENT" in brief
    assert "SECTION_MODEL" not in brief and "SECTION_NUMERICAL_ANALYSIS" not in brief
    assert "theory_record" in brief and "literature_synthesis" not in brief
    assert "user-authored discussion context" in brief and "Do not save comments" in brief
    saved_basis = read_json(engine.run_dir("project.test", first.run_id) / "basis.json")
    assert {ref["family"] for ref in saved_basis["records"]} == {"theory_record"}
    assert not saved_basis["artifacts"]
    save_section_comment(project, target, "EDITED_COMMENT", 1)
    second = await discuss(engine, target, text="Explain more.", assessment_id=first.assessment_id)
    assert second.state is RunState.ASSESSED, second.terminal_reason
    assert "EDITED_COMMENT" in engine.bridge.turns[-1]["brief"]
    assert "FIRST_COMMENT" not in engine.bridge.turns[-1]["brief"]
    assert read_json(engine.run_dir("project.test", first.run_id) / "basis.json") == saved_basis
    assert current_records(project / "branches" / branch / "phases" / "p5") == before
    assert len(engine.list_assessments("project.test")) == 1
    assert primary.is_file()
    assert not (project / "researcher" / "problem_context.json").exists()


async def test_report_dialogue_never_creates_context_amendment_proposals(workbench):
    engine, project, branch = workbench
    target, _ = retained_report(engine, project, branch)
    engine.bridge.default_behavior = ("ok", {"assessment.json": json.dumps({
        "headline": "Explanation", "assessment_markdown": "A section discussion.", "limitations": [], "suggested_actions": [],
        "evidence_refs": [], "proposed_context_amendments": [{"statement": "INVENTED_ADOPTED_CONTEXT", "reason": "Unrequested proposal"}]})})
    before = {str(path): path.read_bytes() for path in (project / "researcher").glob("**/*") if path.is_file()}
    run = await discuss(engine, target)
    assert run.state is RunState.ASSESSED, run.terminal_reason
    after = {str(path): path.read_bytes() for path in (project / "researcher").glob("**/*") if path.is_file()}
    assert after == before


async def test_retry_preserves_failed_question_comment_and_historical_followup_gets_latest(workbench):
    engine, project, branch = workbench
    target, primary = retained_report(engine, project, branch)
    save_section_comment(project, target, "COMMENT_AT_FAILED_QUESTION", 0)
    engine.bridge.default_behavior = ("fail", "Temporary provider failure")
    first = await discuss(engine, target, text="ORIGINAL_QUESTION")
    assert first.state is RunState.FAILED
    save_section_comment(project, target, "LATEST_COMMENT_FOR_FOLLOWUP", 1)
    retained_report(engine, project, branch, run_id="run.report.successor")
    primary.unlink()
    answer(engine)
    retry = await discuss(engine, target, text="REPLACEMENT_QUESTION", assessment_id=first.assessment_id, retry_run_id=first.run_id)
    assert retry.state is RunState.ASSESSED, retry.terminal_reason
    assert retry.instructions == "ORIGINAL_QUESTION"
    assert "COMMENT_AT_FAILED_QUESTION" in engine.bridge.turns[-1]["brief"]
    assert "LATEST_COMMENT_FOR_FOLLOWUP" not in engine.bridge.turns[-1]["brief"]
    followup = await discuss(engine, target, text="A new follow-up.", assessment_id=first.assessment_id)
    assert followup.state is RunState.ASSESSED, followup.terminal_reason
    assert followup.target == target
    assert "LATEST_COMMENT_FOR_FOLLOWUP" in engine.bridge.turns[-1]["brief"]
    assert "SECTION_JUSTIFICATION" in engine.bridge.turns[-1]["brief"]
    assert read_json(engine.run_dir("project.test", first.run_id) / "basis.json")["explanation_issue"]["researcher_comment"]["revision"] == 1


def test_fence_prefix_with_text_does_not_end_code_or_create_a_section():
    from model_forge_codex.report_sections import _section
    markdown = ('<a id="problem"></a>\n## Problem\n\n   ```python\ncode\n   ```not-a-closing-fence\n'
        '<a id="model"></a>\n## Fake model inside code\n   ```\n\n<a id="model"></a>\n## Actual model\n\nACTUAL_MODEL')
    text, title, _ = _section(markdown, {"problem": "problem", "model": "model"}, "model")
    assert title == "Actual model" and "ACTUAL_MODEL" in text and "Fake model" not in text


async def test_comment_api_exact_get_save_edit_and_conflict(api):
    client, engine, project, branch = api
    target, _ = retained_report(engine, project, branch)
    url = "/api/v1/projects/project.test/report-section-comment"
    response = await client.get(url, params={"target": json.dumps(target)})
    assert response.status_code == 200 and response.json() == {"comment": None}
    response = await client.put(url, json={"target": target, "note": "API comment", "expected_revision": 0})
    assert response.status_code == 200 and response.json()["comment"]["revision"] == 1
    stale = await client.put(url, json={"target": target, "note": "stale", "expected_revision": 0})
    assert stale.status_code == 409 and "changed" in stale.json()["detail"]
    cleared = await client.put(url, json={"target": target, "note": "", "expected_revision": 1})
    assert cleared.status_code == 200 and cleared.json()["comment"]["revision"] == 2
    assert (await client.get(url, params={"target": json.dumps(target)})).json() == cleared.json()
    invalid = await client.get(url, params={"target": json.dumps({**target, "sha256": "0" * 64})})
    assert invalid.status_code == 409
    answer(engine)
    created = await client.post("/api/v1/projects/project.test/runs", json={
        "phase": "P5", "mode": "p3.assessment", "branch_id": branch, "intent": "assessment",
        "assessment_purpose": "model_dialogue", "target": target, "instructions": "Explain this section."})
    assert created.status_code == 200, created.text
    await engine._tasks[created.json()["run_id"]]
    followup = await client.post(f"/api/v1/projects/project.test/assessments/{created.json()['assessment_id']}/messages",
                                json={"instructions": "Explain its qualification."})
    assert followup.status_code == 200, followup.text
    await engine._tasks[followup.json()["run_id"]]
    history = (await client.get("/api/v1/projects/project.test/assessments")).json()["assessments"][0]
    assert history["target"] == target and len(history["turns"]) == 2
