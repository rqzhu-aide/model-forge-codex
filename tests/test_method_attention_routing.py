"""Method questions retain their source and cannot instruct another branch."""
import json

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.cumulative_attention import attention_applies_to_branch, open_attention_items
from model_forge_codex.methods import activate_method
from model_forge_codex.records import publish_package
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, write_json_atomic
from test_contextual_attention import publish, request, setting
from test_direct_workflow import PID, direct_engine, p2_documents


@pytest.mark.parametrize("target_phase", ["P2", "P3", "P4", "P5"])
def test_p2_scope_uses_method_identity_regardless_of_target_phase(target_phase):
    item = request(target_phase=target_phase, phase="P2", branch="trunk",
                   affected_record_ids=["method.theory"])
    assert attention_applies_to_branch(item, "trunk", None)
    assert attention_applies_to_branch(item, "custom.theory", "method.theory")
    assert not attention_applies_to_branch(item, "custom.analyst", "method.empirical")
    assert not attention_applies_to_branch(item, "custom.theory", None)
    item["affected_record_ids"].append("method.empirical")
    assert attention_applies_to_branch(item, "custom.analyst", "method.empirical")


def test_shared_p1_context_and_empty_p2_scopes_remain_shared_without_guessing():
    assert attention_applies_to_branch(request(phase="P1", branch="trunk"), "theory", "method.theory")
    assert attention_applies_to_branch(request(phase="P2", branch="trunk", affected_record_ids=[]),
                                       "theory", "method.theory")
    assert not attention_applies_to_branch(request(phase="P2", branch="trunk", affected_record_ids=["record.unknown"]),
                                           "theory", "method.theory")
    assert not attention_applies_to_branch(request(phase="P3", branch="another.method"), "theory", "method.theory")


def publish_candidates(project):
    proposals, _ = p2_documents(False)
    methods = [proposals[f"p2.{role}_proposal"]["method"] for role in ("theory", "empirical")]
    questions = [request(f"question.{role}", target_phase=phase, affected_record_ids=[f"method.{role}"])
                 for role, phase in (("theory", "P3"), ("empirical", "P4"))]
    tasks = [request("task.both", kind="research_task", target_phase="P4",
                     affected_record_ids=["method.theory", "method.empirical"])]
    package = publish_package(project / "branches/trunk/phases/p2", {
        "method_catalog": json.dumps({"methods": methods}).encode(),
        "theory_proposal": json.dumps(proposals["p2.theory_proposal"]).encode(),
        "attention_items": json.dumps(questions + tasks).encode(),
    }, run_id="run.p2.candidates", phase="P2", branch_id="trunk")
    for method in methods:
        activate_method(project, method["identity"]["stable_id"])
    # A branch directory is not required to have the method's stable-ID name.
    registry_path = project / "researcher/methods.json"
    registry = read_json(registry_path)
    registry["branches"] = {"branch." + key.split(".")[-1]: value for key, value in registry["branches"].items()}
    write_json_atomic(registry_path, registry)
    return package


async def test_method_answers_are_inline_editable_and_only_enter_their_branch(direct_engine, monkeypatch):
    engine, project = direct_engine
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    publish(project, {"attention_items": [request("question.shared")], "literature_synthesis": setting()})
    package = publish_candidates(project)
    open_items = {item["attention_id"]: item for item in open_attention_items(project, {})}
    source = open_items["question.theory"]["related_source_refs"][0]
    assert source["family"] == "method_catalog"
    assert source["entry_pointer"] == "/methods/0"
    assert source["generation_id"] == package["records"]["method_catalog"]["generation_id"]
    for phase in ("P3", "P4"):
        for role in ("theory", "empirical"):
            basis = engine.compute_basis(PID, phase, "branch." + role)
            questions = basis["cumulative_inputs"]["open_attention"]["document"]["items"]
            assert {item["attention_id"] for item in questions} == {"question.shared", "question." + role, "task.both"}

    app = create_app(engine.data_root, engine.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for role in ("shared", "theory", "empirical"):
            result = await client.post(f"/api/v1/projects/{PID}/attention/question.{role}/resolve",
                                       json={"note": "ANSWER_" + role.upper()})
            assert result.status_code == 200, result.text
        for phase in ("P3", "P4"):
            for role in ("theory", "empirical"):
                basis = engine.compute_basis(PID, phase, "branch." + role)
                answers = basis["cumulative_inputs"]["researcher_answers"]["document"]["items"]
                assert {answer["note"] for answer in answers} == {"ANSWER_SHARED", "ANSWER_" + role.upper()}
                assert {item["attention_id"] for item in basis["cumulative_inputs"]["open_attention"]["document"]["items"]} == {"task.both"}
        other_before = engine.compute_basis(PID, "P4", "branch.empirical")
        own_before = engine.compute_basis(PID, "P3", "branch.theory")
        edited = await client.post(f"/api/v1/projects/{PID}/attention/question.theory/resolve",
                                   json={"note": "REVISED_THEORY_ANSWER"})
        assert edited.status_code == 200
        assert edited.json()["answer"]["attention"]["affected_record_ids"] == ["method.theory"]
        assert engine.compute_basis(PID, "P4", "branch.empirical")["sha256"] == other_before["sha256"]
        assert engine.compute_basis(PID, "P3", "branch.theory")["sha256"] != own_before["sha256"]
        pending = (await client.get(f"/api/v1/projects/{PID}/decisions-pending")).json()
        assert len(pending["researcher_answers"]) == 3
        assert [item["attention_id"] for item in pending["attention"]] == ["task.both"]


async def test_catalog_without_provenance_marks_method_origin_unavailable(direct_engine):
    engine, project = direct_engine
    publish_candidates(project)
    basis = engine.compute_basis(PID, "P3", "branch.theory")
    entry = basis["method_provenance"]["method.theory"]
    assert entry["origin"] is None
    assert entry["materials"] == {}
    assert entry["unavailable"] == ["The producing run for this method definition is not recorded."]
