"""Consequential choices remain authored, exact, editable and inert until a run."""
import json
from copy import deepcopy

import pytest

from model_forge_codex.cumulative_attention import open_attention_items
from model_forge_codex.phase_interactions import issue_source_identity, save_scoped_answer, selected_response
from model_forge_codex.records import generation_path
from model_forge_codex.storage import read_json, write_json_atomic
from test_problem_context import project, publish_question
from test_researcher_workbench_api import api
from test_researcher_workbench_engine import workbench, publish
from test_cumulative_attention import publish as publish_attention


OPTIONS = [
    {"id": "all", "label": "All surviving patients", "consequence": "Requires an account of incomplete follow-up."},
    {"id": "observed", "label": "Patients still observed", "consequence": "Restricts the population to ongoing observation."},
]


def choice(**extra):
    return {"schema_version": "1.2.0", "attention_id": "attention.population", "kind": "researcher_decision",
            "attention_version_id": "attention.population.v1", "scope": {"kind": "project"},
            "audience": ["research_lead"], "raised_by": "research_lead", "target_phase": "P1",
            "question": "Who must receive a prediction?", "disposition": "open", "severity": "major",
            "context_markdown": "The population determines to whom the conclusion applies.",
            "likely_consequence": "Changes the intended use and follow-up requirements.",
            "decision_priority": "interpretation", "response_kind": "choice",
            "options": deepcopy(OPTIONS), "recommendation": "Retain the full target for cohort-wide use.", **extra}


def test_selected_answer_is_canonical_editable_and_preserves_prior_scope(project):
    question = publish_question(project, 1, **{key: value for key, value in choice().items()
                                             if key not in {"attention_version_id"}})
    selected = save_scoped_answer(project, question, "UNTRUSTED CLIENT DESCRIPTION", expected_revision=0,
                                 selection={"option_id": "all", "note": "Include irregular follow-up."})
    assert selected["note"] == ("Selected option: All surviving patients\n\nRequires an account of incomplete follow-up."
                                "\n\nYour note: Include irregular follow-up.")
    assert selected["selection"] == {"option_id": "all", "label": OPTIONS[0]["label"],
                                     "consequence": OPTIONS[0]["consequence"], "note": "Include irregular follow-up."}
    again = save_scoped_answer(project, question, "", expected_revision=1,
                              selection={"option_id": "all", "note": "Include irregular follow-up."})
    assert again["revision"] == 1
    second = save_scoped_answer(project, question, "", expected_revision=1,
                               selection={"option_id": "observed", "note": "For the clinic workflow."})
    assert second["revision"] == 2 and second["selection"]["option_id"] == "observed"
    stored = read_json(project / "researcher/attention_resolutions.json")[question["attention_id"]]
    assert stored["history"][0]["selection"]["option_id"] == "all"
    with pytest.raises(ValueError, match="saved response changed"):
        save_scoped_answer(project, question, "", expected_revision=1, selection={"option_id": "all"})
    unknown = save_scoped_answer(project, question, "The intended population is not settled.",
                                expected_revision=2, origin="unknown")
    assert "selection" not in unknown and unknown["origin"] == "unknown"
    assert unknown["question_ref"] == selected["question_ref"]
    assert not (project / "runs").exists()


def test_mathematical_options_survive_answer_edit_and_context_mirroring(project):
    options = [
        {"id": "chance", "label": "Limit excessive-cost probability",
         "consequence": r"$$\mathbb{P}_{\pi}(G_C>b)\le\alpha.$$"
                        "\n\nBounds how often cumulative cost exceeds the threshold."},
        {"id": "mean", "label": "Limit average cost",
         "consequence": r"$$\mathbb{E}_{\pi}[G_C]\le B.$$"
                        "\n\nBounds average cumulative cost; it does not fix the tail probability."},
    ]
    question = publish_question(project, 1, **{key: value for key, value in choice(options=options,
        context_markdown=r"With cumulative reward $G_R$ and cost $G_C$, maximize $\mathbb{E}_{\pi}[G_R]$ over policies $\pi\in\Pi$.").items()
        if key != "attention_version_id"})
    first = save_scoped_answer(project, question, "", expected_revision=0, save_to_context=True,
                              selection={"option_id": "chance", "note": "Threshold not yet chosen."})
    second = save_scoped_answer(project, question, "", expected_revision=1, save_to_context=True,
                               selection={"option_id": "mean", "note": "Use the average-cost target instead."})
    assert first["selection"]["consequence"] == options[0]["consequence"]
    assert second["selection"]["consequence"] == options[1]["consequence"]
    assert second["selection"]["note"] == "Use the average-cost target instead."
    assert second["note"].count(options[1]["consequence"]) == 1
    assert options[0]["consequence"] not in second["note"]
    assert second["context_ref"]["item_id"] == first["context_ref"]["item_id"]
    from model_forge_codex.problem_context import load_problem_context
    context = load_problem_context(project)
    mirror = next(row for row in context["items"] if row["item_id"] == second["context_ref"]["item_id"])
    assert mirror["statement"] == second["note"]
    stored = read_json(project / "researcher/attention_resolutions.json")[question["attention_id"]]
    assert stored["history"][0]["selection"]["consequence"] == options[0]["consequence"]
    assert not (project / "runs").exists()


@pytest.mark.parametrize("in_history", [False, True])
def test_legacy_answer_without_top_level_source_remains_editable(project, in_history):
    question = publish_question(project, 1, **{key: value for key, value in choice().items()
                                             if key != "attention_version_id"})
    legacy = {"note": "Original free-text answer", "revision": 1, "attention": question}
    current = legacy
    if in_history:
        newer_question = {**question, "generation_ref": {**question["generation_ref"], "generation_id": "different.generation"}}
        current = {"note": "A different question", "revision": 2, "attention": newer_question, "history": [legacy]}
    write_json_atomic(project / "researcher/attention_resolutions.json", {question["attention_id"]: current})
    edited = save_scoped_answer(project, question, "Edited original answer", expected_revision=1)
    assert edited["revision"] == (3 if in_history else 2)
    assert edited["question_ref"] == issue_source_identity(question)
    stored = read_json(project / "researcher/attention_resolutions.json")[question["attention_id"]]
    assert stored["history"][0]["note"] == "Original free-text answer"


@pytest.mark.parametrize("change,selection,origin", [
    ({}, {"option_id": "invented"}, "researcher_reported"),
    ({}, {"option_id": "all", "label": "FORGED"}, "researcher_reported"),
    ({}, {"option_id": "all", "note": 3}, "researcher_reported"),
    ({}, {"option_id": "all"}, "unknown"),
    ({"response_kind": "study_fact"}, {"option_id": "all"}, "researcher_reported"),
    ({"options": [OPTIONS[0], OPTIONS[0]]}, {"option_id": "all"}, "researcher_reported"),
    ({"options": ["legacy prose"]}, {"option_id": "all"}, "researcher_reported"),
])
def test_selection_rejects_unavailable_ambiguous_or_fabricated_choices(change, selection, origin):
    with pytest.raises(ValueError):
        selected_response(choice(**change), selection, origin=origin)


@pytest.mark.parametrize("legacy", [False, True])
async def test_api_choice_save_edit_and_unknown_are_local_and_exact(api, monkeypatch, legacy):
    client, engine, project, branch = api
    if legacy:
        monkeypatch.setattr("model_forge_codex.service.supports_problem_context", lambda _: False)
    package = publish(project, "trunk", "P1", {"attention_items": [choice()]})
    question = open_attention_items(project, {})[0]
    source = issue_source_identity(question)
    original = generation_path(project / "branches/trunk/phases/p1", "attention_items", package["records"]["attention_items"])
    before = original.read_bytes()
    url = "/api/v1/projects/project.test/attention/attention.population/resolve"
    args = {"note": "", "expected_source": source, "expected_revision": 0, "selection": {"option_id": "all"}}
    missing = await client.post(url, json={key: value for key, value in args.items() if key != "expected_source"})
    assert missing.status_code == 409
    wrong = await client.post(url, json={**args, "selection": {"option_id": "invented"}})
    assert wrong.status_code == 409
    response = await client.post(url, json=args)
    assert response.status_code == 200, response.text
    first = response.json()["answer"]
    assert first["selection"]["option_id"] == "all" and first["revision"] == 1
    response = await client.post(url, json={**args, "expected_revision": 1,
                                          "selection": {"option_id": "observed", "note": "Restricted workflow."}})
    assert response.status_code == 200, response.text
    assert response.json()["answer"]["selection"]["note"] == "Restricted workflow."
    response = await client.post(url, json={"note": "I have not decided.", "origin": "unknown",
                                          "expected_source": source, "expected_revision": 2})
    assert response.status_code == 200, response.text
    last = response.json()["answer"]
    assert last["origin"] == "unknown" and "selection" not in last
    assert original.read_bytes() == before and not engine._tasks


async def test_unsaved_stale_selection_does_not_answer_a_successor(api):
    client, engine, project, branch = api
    publish(project, "trunk", "P1", {"attention_items": [choice()]})
    old_source = issue_source_identity(open_attention_items(project, {})[0])
    publish(project, "trunk", "P1", {"attention_items": [choice(attention_version_id="attention.population.v2",
        options=[{**OPTIONS[0], "label": "Changed meaning"}, OPTIONS[1]])]}, "run.successor")
    result = await client.post("/api/v1/projects/project.test/attention/attention.population/resolve",
                               json={"note": "", "expected_source": old_source,
                                     "selection": {"option_id": "all"}, "expected_revision": 0})
    assert result.status_code == 409
    assert not (project / "researcher/attention_resolutions.json").exists()


def test_priority_survives_carry_forward_and_preserves_numeric_authored_order(tmp_path):
    first = [choice(attention_id=f"attention.z{index}", decision_priority="interpretation") for index in range(12)]
    original = publish_attention(tmp_path, first)
    publish_attention(tmp_path, [choice(attention_id="attention.a", decision_priority="resources", severity="blocking")], phase="P2")
    publish_attention(tmp_path, [{"attention_id": "attention.legacy", "question": "Unranked history", "severity": "blocking"}], phase="P3")
    rows = open_attention_items(tmp_path, {})
    assert [item["attention_id"] for item in rows] == [*(f"attention.z{i}" for i in range(12)), "attention.a", "attention.legacy"]
    assert [item["authored_order"] for item in rows[:12]] == list(range(12))
    assert rows[10]["generation_ref"]["generation_id"] == original["records"]["attention_items"]["generation_id"]
    assert rows[10]["entry_pointer"] == "/10"
    assert "decision_priority" not in rows[-1] and "response_kind" not in rows[-1]
