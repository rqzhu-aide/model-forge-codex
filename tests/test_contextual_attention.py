"""Research clarifications preserve their mathematical context and exact sources."""
import json

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.cumulative_attention import open_attention_items
from model_forge_codex.records import generation_path, publish_package
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, sha256_bytes, write_json_atomic
from test_direct_workflow import PID, direct_engine


def request(identifier="attention.policy", **changes):
    return {
        "schema_version": "1.1.0", "attention_id": identifier,
        "kind": "researcher_decision", "target_phase": "P1", "severity": "major",
        "raised_by": "research_lead", "disposition": "open",
        "question": "May the policy use remaining budget?",
        "context_markdown": r"$$A_t\sim\pi(\cdot\mid S_t,Z_t),\quad Z_{t+1}=(Z_t-C_t)/\gamma.$$",
        "likely_consequence": "The policy information set defines the feasible class.",
        "affected_record_ids": ["record.setting"], **changes,
    }


def publish(project, records, run="run.original"):
    return publish_package(project / "branches/trunk/phases/p1",
                           {family: json.dumps(document).encode() for family, document in records.items()},
                           run_id=run, phase="P1", branch_id="trunk")


def setting(**changes):
    return {"record_id": "record.setting", "record_type": "literature_synthesis",
            "body_md": r"$$Z_{t+1}=(Z_t-C_t)/\gamma.$$",
            **changes}


@pytest.mark.parametrize("wrapped,entry_pointer", [(False, "/1"), (True, "/items/1")])
def test_exact_item_pointer_and_scientific_source_survive_later_updates(tmp_path, wrapped, entry_pointer):
    items = [request("attention.other", affected_record_ids=[]), request()]
    document = {"items": items} if wrapped else items
    first = publish(tmp_path, {"attention_items": document,
                               "literature_synthesis": setting(),
                               "synthesis_candidate": setting(body_md="Earlier candidate, same record ID.")})
    publish(tmp_path, {"attention_items": [], "literature_synthesis": setting(body_md="Later formulation.")},
            run="run.later")
    actual = next(item for item in open_attention_items(tmp_path, {}) if item["attention_id"] == "attention.policy")
    assert actual["context_markdown"] == items[1]["context_markdown"]
    assert actual["generation_ref"]["generation_id"] == first["records"]["attention_items"]["generation_id"]
    assert actual["generation_ref"]["entry_pointer"] == actual["entry_pointer"] == entry_pointer
    assert len(actual["related_source_refs"]) == 1
    reference = actual["related_source_refs"][0]
    assert reference["record_id"] == "record.setting"
    assert reference["family"] == "literature_synthesis"
    assert reference["generation_id"] == first["records"]["literature_synthesis"]["generation_id"]
    assert reference["sha256"] == first["records"]["literature_synthesis"]["content_sha256"]
    assert reference["run_id"] == "run.original"


def test_related_sources_do_not_guess_from_nested_mentions_or_later_matches(tmp_path):
    publish(tmp_path, {"attention_items": [request()],
                      "unrelated": {"basis": [{"record_id": "record.setting"}]}})
    publish(tmp_path, {"attention_items": [], "literature_synthesis": setting()}, run="run.later")
    assert open_attention_items(tmp_path, {})[0]["related_source_refs"] == []


def test_unavailable_original_source_is_not_replaced_by_a_later_generation(tmp_path):
    first = publish(tmp_path, {"attention_items": [request()], "literature_synthesis": setting()})
    original = generation_path(tmp_path / "branches/trunk/phases/p1", "literature_synthesis",
                               first["records"]["literature_synthesis"])
    original.write_text('{"record_id":"record.setting","body_md":"Tampered source"}')
    publish(tmp_path, {"attention_items": [], "literature_synthesis": setting()}, run="run.later")
    actual = open_attention_items(tmp_path, {})[0]
    assert actual["question"] == request()["question"]
    assert actual["related_source_refs"] == []


def test_ambiguous_sources_are_omitted_and_array_records_have_exact_entry_pointers(tmp_path):
    publish(tmp_path, {"attention_items": [request(affected_record_ids=["record.setting", "record.unique"])],
                      "first_candidate": setting(), "second_candidate": setting(),
                      "sources": {"items": [{"record_id": "record.unrelated"},
                                             {"record_id": "record.unique", "body_md": "Original account."}]}})
    references = open_attention_items(tmp_path, {})[0]["related_source_refs"]
    assert len(references) == 1 and references[0]["record_id"] == "record.unique"
    assert references[0]["entry_pointer"] == "/items/1"


def test_retained_attention_pointer_resolves_its_original_package(tmp_path):
    first = publish(tmp_path, {"attention_items": [request()], "literature_synthesis": setting()})
    later = publish(tmp_path, {"literature_synthesis": setting(body_md="Newer source.")}, run="run.later")
    later["records"]["attention_items"] = first["records"]["attention_items"]
    write_json_atomic(tmp_path / "branches/trunk/phases/p1/current-package.json", later)
    source = open_attention_items(tmp_path, {})[0]["related_source_refs"][0]
    assert source["generation_id"] == first["records"]["literature_synthesis"]["generation_id"]


def test_legacy_mixed_run_pointers_cannot_attach_a_newer_scientific_source(tmp_path):
    directory = tmp_path / "branches/trunk/phases/p1"
    historical = request(schema_version="1.0.0")
    for field in ("kind", "target_phase", "context_markdown"):
        historical.pop(field)
    for family, document, run_id in (("attention_items", [historical], "run.original"),
                                      ("literature_synthesis", setting(), "run.later")):
        content = json.dumps(document).encode()
        path = directory / family / "generations/generation.legacy.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        write_json_atomic(directory / family / "current.json",
                          {"generation_id": "generation.legacy", "content_sha256": sha256_bytes(content),
                           "source_run_id": run_id})
    actual = open_attention_items(tmp_path, {})[0]
    assert actual["related_source_refs"] == []
    assert not any(field in actual for field in ("kind", "target_phase", "context_markdown"))


async def test_researcher_decision_needs_an_answer_and_preserves_original_context(direct_engine, monkeypatch):
    engine, project = direct_engine
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    package = publish(project, {"attention_items": [request()], "literature_synthesis": setting()})
    original = generation_path(project / "branches/trunk/phases/p1", "attention_items", package["records"]["attention_items"])
    original_bytes = original.read_bytes()
    app = create_app(engine.data_root, engine.bridge)
    url = f"/api/v1/projects/{PID}/attention/attention.policy/resolve"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for body in ({}, {"note": " \n "}, {"note": None}, {"note": {"invalid": True}}):
            assert (await client.post(url, json=body)).status_code == 422
        assert not (project / "researcher/attention_resolutions.json").exists()
        answer = r"Permit $\pi(\cdot\mid S_t,Z_t)$."
        saved = await client.post(url, json={"note": answer})
        assert saved.status_code == 200
        assert saved.json()["answer"]["note"] == answer
        assert saved.json()["answer"]["attention_id"] == "attention.policy"
        pending_response = await client.get(f"/api/v1/projects/{PID}/decisions-pending")
        assert pending_response.status_code == 200
        pending = pending_response.json()
        assert pending["attention"] == []
    stored = read_json(project / "researcher/attention_resolutions.json")["attention.policy"]
    assert stored["note"] == answer
    assert stored["attention"]["question"] == request()["question"]
    assert stored["attention"]["context_markdown"] == request()["context_markdown"]
    assert stored["attention"]["generation_ref"]["generation_id"] == package["records"]["attention_items"]["generation_id"]
    assert stored["attention"]["related_source_refs"][0]["run_id"] == "run.original"
    assert pending["researcher_answers"] == [{**stored, "attention_id": "attention.policy", "applied_to": [], "previously_applied_to": []}]
    assert original.read_bytes() == original_bytes


async def test_edit_clarification_preserves_question_and_supplies_only_latest_answer(direct_engine, monkeypatch):
    engine, project = direct_engine
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    package = publish(project, {"attention_items": [request()], "literature_synthesis": setting()})
    original = generation_path(project / "branches/trunk/phases/p1", "attention_items", package["records"]["attention_items"])
    original_bytes = original.read_bytes()
    app = create_app(engine.data_root, engine.bridge)
    url = f"/api/v1/projects/{PID}/attention/attention.policy/resolve"
    store = project / "researcher/attention_resolutions.json"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = (await client.post(url, json={"note": "Use stationary policies."})).json()["answer"]
        previous_basis = engine.compute_basis(PID, "P1", "trunk", "p1.literature_update")
        edited = await client.post(url, json={"note": "Allow policies to use remaining budget."})
        assert edited.status_code == 200
        answer = edited.json()["answer"]
        assert answer["attention"] == first["attention"]
        assert answer["note"] == "Allow policies to use remaining budget."
        assert "history" not in answer
        current_basis = engine.compute_basis(PID, "P1", "trunk", "p1.literature_update")
        assert previous_basis["sha256"] != current_basis["sha256"]
        usage_fields = {"applied_to", "previously_applied_to"}
        assert previous_basis["cumulative_inputs"]["researcher_answers"]["document"]["items"] == [{k: v for k, v in first.items() if k not in usage_fields}]
        current_answers = current_basis["cumulative_inputs"]["researcher_answers"]["document"]
        assert current_answers["items"] == [{k: v for k, v in answer.items() if k not in usage_fields}]
        assert "Use stationary policies." not in json.dumps(current_answers)
        stored = read_json(store)["attention.policy"]
        assert len(stored["history"]) == 1
        assert stored["history"][0]["note"] == first["note"]
        saved_bytes = store.read_bytes()
        for note in ("", " \n ", None, {"invalid": True}):
            assert (await client.post(url, json={"note": note})).status_code == 422
        repeated = await client.post(url, json={"note": answer["note"]})
        assert repeated.json()["answer"] == answer
        assert store.read_bytes() == saved_bytes
        pending = (await client.get(f"/api/v1/projects/{PID}/decisions-pending")).json()
        assert pending["attention"] == []
        assert pending["researcher_answers"] == [answer]
    assert original.read_bytes() == original_bytes


async def test_saved_answers_omit_empty_or_invalid_entries_without_rewriting_legacy_notes(direct_engine):
    engine, project = direct_engine
    valid = {"note": "  Use the saved policy class.  ", "resolved_at": "2026-09-11T02:00:00Z"}
    write_json_atomic(project / "researcher/attention_resolutions.json", {
        "legacy.answer": valid,
        "legacy.empty": {"note": ""}, "legacy.blank": {"note": " \n "},
        "invalid.entry": "Done", "invalid.note": {"note": {"text": "Done"}},
        "invalid.context": {"note": "Done", "attention": "Invalid context"},
        "missing.note": {"resolved_at": "2026-09-11T02:00:00Z"},
    })
    app = create_app(engine.data_root, engine.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{PID}/decisions-pending")
        assert response.status_code == 200
    assert response.json()["researcher_answers"] == [{**valid, "attention_id": "legacy.answer", "applied_to": [], "previously_applied_to": []}]


async def test_team_task_cannot_be_closed_as_a_human_answer_and_unknown_id_is_rejected(direct_engine, monkeypatch):
    engine, project = direct_engine
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    publish(project, {"attention_items": [request(kind="research_task", target_phase="P3")]})
    app = create_app(engine.data_root, engine.bridge)
    base = f"/api/v1/projects/{PID}/attention"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post(base + "/attention.policy/resolve", json={"note": "Done"})).status_code == 409
        assert (await client.post(base + "/not.present/resolve", json={"note": "Done"})).status_code == 404
    assert not (project / "researcher/attention_resolutions.json").exists()
    assert open_attention_items(project, {})[0]["kind"] == "research_task"
