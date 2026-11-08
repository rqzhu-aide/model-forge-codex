"""Direct numerical evidence readers stay with the passage's producing publication."""
import copy
import json

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.records import ArtifactError, publish_package
from model_forge_codex.research import scientific_document_view, source_ref
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic


BRANCH = "method.a"


def publication(project, run_id="run.original", estimate=0.12, *, exhibit_ids=None, exhibits=None):
    run = project / "runs" / run_id
    stage = run / "outputs/p4.analyst"
    stage.mkdir(parents=True)
    table = stage / "results.json"
    write_json_atomic(table, {"columns": [{"key": "risk", "label": "Strict risk"}],
                              "rows": [{"risk": estimate}], "caption": "One recorded synthetic condition."})
    exhibit = {"exhibit_id": "table.safety", "title": f"Saved safety result {run_id}", "kind": "table",
               "artifact_path": table.name, "artifact_sha256": sha256_file(table), "media_type": "application/json"}
    documents = {
        "analyst_synthesis": {"question_results": [{"question_id": "q.safety", "title": "Safety calibration",
            "answer_markdown": f"The recorded strict risk is {estimate} in this condition.",
            "statement_ids": ["statement.saved"], "exhibit_ids": ["table.safety"] if exhibit_ids is None else exhibit_ids}]},
        "theory_audit": {"findings": [{"title": "Finite comparison", "statement": f"The {run_id} numerical comparison does not prove the theorem.",
                                       "statement_ids": ["statement.saved"], "status": "inconclusive"}]},
        "exhibits": [exhibit] if exhibits is None else exhibits,
    }
    stages = {"analyst_synthesis": "p4.analyst", "theory_audit": "p4.theorist", "exhibits": "p4.analyst"}
    raw = {family: json.dumps(document).encode() for family, document in documents.items()}
    seals = {"p4.analyst": {table.name: {"sha256": sha256_file(table)}}}
    for family, payload in raw.items():
        output = run / "outputs" / stages[family] / f"{family}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
        seals.setdefault(stages[family], {})[output.name] = {"sha256": sha256_file(output)}
    for name, outputs in seals.items():
        write_json_atomic(run / "outputs" / name / "seal.json", {"outputs": outputs})
    write_json_atomic(run / "run.json", {"state": "published", "phase": "P4", "branch_id": BRANCH})
    package = publish_package(project / f"branches/{BRANCH}/phases/p4", raw,
                              run_id=run_id, phase="P4", branch_id=BRANCH, metadata={"stage_ids": stages})
    return package, documents, table


def open_entry(project, package, family="analyst_synthesis", pointer="/question_results/0"):
    return scientific_document_view(project, BRANCH, "P4", family,
                                    package["records"][family]["generation_id"], entry_pointer=pointer)


def replace_pointer(project, package, family, pointer):
    """Represent a later committed publication explicitly retaining a prior generation."""
    package["records"][family] = copy.deepcopy(pointer)
    phase = project / f"branches/{BRANCH}/phases/p4"
    write_json_atomic(phase / "packages" / f"{package['package_id']}.json", package)
    if read_json(phase / "current-package.json")["package_id"] == package["package_id"]:
        write_json_atomic(phase / "current-package.json", package)


def test_current_and_earlier_passages_open_only_their_own_exact_saved_table(tmp_path):
    original, documents, _ = publication(tmp_path)
    current, _, _ = publication(tmp_path, "run.current", 0.34)
    before = copy.deepcopy(original)
    for package, value in [(original, 0.12), (current, 0.34)]:
        passage = open_entry(tmp_path, package)
        assert passage["entry"]["answer_markdown"] == f"The recorded strict risk is {value} in this condition."
        assert passage["generation_ref"] == source_ref(BRANCH, "P4", "analyst_synthesis", package["records"]["analyst_synthesis"])
        link = passage["cited_exhibits"][0]["reference"]
        assert link == {**source_ref(BRANCH, "P4", "exhibits", package["records"]["exhibits"]), "entry_pointer": "/0"}
        table = open_entry(tmp_path, package, "exhibits", link["entry_pointer"])["exhibit"]
        assert table["source_verified"] is True and "source_error" not in table
        assert table["table"]["rows"] == [{"risk": value}]
        assert f"/runs/{package['run_id']}/" in table["artifact_url"]
    assert open_entry(tmp_path, original)["structured"] == documents["analyst_synthesis"]
    assert original == before


@pytest.mark.parametrize("legacy", [False, True])
def test_retained_generation_selects_original_sibling_tables_not_later_envelope(tmp_path, legacy):
    original, _, _ = publication(tmp_path)
    if legacy:
        phase = tmp_path / f"branches/{BRANCH}/phases/p4"
        for family, pointer in list(original["records"].items()):
            older = {key: value for key, value in pointer.items() if key not in {"package_id", "run_id"}}
            older["source_run_id"] = original["run_id"]
            original["records"][family] = older
            write_json_atomic(phase / family / "current.json", older)
        # The next atomic publication explicitly freezes these legacy heads.
        (phase / "current-package.json").unlink()
        original["package_id"] = None
    current, _, _ = publication(tmp_path, "run.current", 0.34)
    replace_pointer(tmp_path, current, "analyst_synthesis", original["records"]["analyst_synthesis"])
    link = open_entry(tmp_path, original)["cited_exhibits"][0]["reference"]
    assert link["generation_id"] == original["records"]["exhibits"]["generation_id"]
    assert link["run_id"] == original["run_id"]
    assert link["generation_id"] != current["records"]["exhibits"]["generation_id"]
    assert open_entry(tmp_path, original, "exhibits", "/0")["exhibit"]["table"]["rows"] == [{"risk": 0.12}]


@pytest.mark.parametrize("damage", ["duplicate_exhibit", "missing_exhibit", "different_run", "different_package", "corrupt_generation"])
def test_unavailable_or_ambiguous_exhibit_never_substitutes_current_table(tmp_path, damage):
    original, documents, _ = publication(tmp_path)
    if damage in {"duplicate_exhibit", "missing_exhibit"}:
        exhibits = documents["exhibits"] * 2 if damage == "duplicate_exhibit" else []
        original, _, _ = publication(tmp_path, "run.changed", exhibits=exhibits)
    elif damage in {"different_run", "different_package"}:
        pointer = {**original["records"]["exhibits"], "run_id" if damage == "different_run" else "package_id": "foreign"}
        replace_pointer(tmp_path, original, "exhibits", pointer)
    else:
        ref = original["records"]["exhibits"]
        (tmp_path / f"branches/{BRANCH}/phases/p4/exhibits/generations/{ref['generation_id']}.json").write_text("[]")
    publication(tmp_path, "run.current", 0.34)
    assert open_entry(tmp_path, original)["cited_exhibits"] == [{"title": "Cited result unavailable"}]


def test_duplicate_citation_ids_link_once_and_table_file_damage_stays_unavailable(tmp_path):
    package, _, table = publication(tmp_path, exhibit_ids=["table.safety", "table.safety", None, 3])
    assert len(open_entry(tmp_path, package)["cited_exhibits"]) == 1
    table.write_text('{"rows":[]}')
    opened = open_entry(tmp_path, package, "exhibits", "/0")["exhibit"]
    assert "source_error" in opened and not opened.get("source_verified")
    assert "table" not in opened


def test_new_current_theory_cannot_change_the_saved_analyst_or_theorist_passage(tmp_path):
    package, documents, _ = publication(tmp_path)
    phase = tmp_path / f"branches/{BRANCH}/phases/p3"
    for run_id, claim in [("run.theory.original", "An earlier qualified claim."), ("run.theory.current", "A different current claim.")]:
        publish_package(phase, {"theory_record": json.dumps({"statements": [{"statement_id": "statement.saved", "statement": claim}]}).encode()},
                        run_id=run_id, phase="P3", branch_id=BRANCH)
    assert open_entry(tmp_path, package)["entry"] == documents["analyst_synthesis"]["question_results"][0]
    audit = open_entry(tmp_path, package, "theory_audit", "/findings/0")
    assert audit["entry"] == documents["theory_audit"]["findings"][0]
    assert audit["generation_ref"]["run_id"] == package["run_id"]
    assert "current claim" not in json.dumps(audit)


@pytest.mark.parametrize("family,pointer", [
    ("analyst_synthesis", ""), ("analyst_synthesis", "/question_results/-1"),
    ("analyst_synthesis", "/question_results/01"), ("analyst_synthesis", "/question_results/0.0"),
    ("analyst_synthesis", "/question_results/0/answer_markdown"), ("analyst_synthesis", "/question_results/99"),
    ("analyst_synthesis", "/question_results/1000000000"), ("analyst_synthesis", "/findings/0"),
    ("theory_audit", "/findings/-1"), ("theory_audit", "/findings/1"),
    ("exhibits", "/-1"), ("exhibits", "/1"), ("exhibits", "/0/artifact_path"),
])
def test_bad_or_out_of_range_entry_pointer_is_rejected(tmp_path, family, pointer):
    package, _, _ = publication(tmp_path)
    with pytest.raises(ValueError):
        open_entry(tmp_path, package, family, pointer)


def test_non_evidence_family_wrong_phase_and_unknown_generation_cannot_become_an_entry(tmp_path):
    package, _, _ = publication(tmp_path)
    phase = tmp_path / f"branches/{BRANCH}/phases/p4"
    other = publish_package(phase, {"protocol": b'{"question_results":[{"title":"Not an authored finding"}]}'},
                            run_id="run.other", phase="P4", branch_id=BRANCH)
    with pytest.raises(ValueError, match="no numerical evidence reader"):
        open_entry(tmp_path, other, "protocol")
    theory = publish_package(tmp_path / f"branches/{BRANCH}/phases/p3", {"theory_audit": b'{"findings":[{"title":"P3 source"}]}'},
                             run_id="run.theory", phase="P3", branch_id=BRANCH)
    with pytest.raises(ValueError, match="no numerical evidence reader"):
        scientific_document_view(tmp_path, BRANCH, "P3", "theory_audit", theory["records"]["theory_audit"]["generation_id"], entry_pointer="/findings/0")
    assert scientific_document_view(tmp_path, BRANCH, "P4", "analyst_synthesis", "generation.absent", entry_pointer="/question_results/0") is None
    assert open_entry(tmp_path, package)["entry"]["question_id"] == "q.safety"


def test_passage_generation_digest_is_checked_before_any_projection(tmp_path):
    package, _, _ = publication(tmp_path)
    ref = package["records"]["analyst_synthesis"]
    (tmp_path / f"branches/{BRANCH}/phases/p4/analyst_synthesis/generations/{ref['generation_id']}.json").write_text("{}")
    with pytest.raises(ArtifactError, match="Digest mismatch"):
        open_entry(tmp_path, package)


async def test_document_api_dispatches_exact_evidence_pointer_and_rejects_invalid_targets(tmp_path):
    project = tmp_path / "projects/project.evidence"
    original, _, table_file = publication(project)
    current, _, _ = publication(project, "run.current", 0.34)
    replace_pointer(project, current, "analyst_synthesis", original["records"]["analyst_synthesis"])
    generation = original["records"]["analyst_synthesis"]["generation_id"]
    record_base = f"/api/v1/projects/{project.name}/branches/{BRANCH}/phases/P4/records"
    url = f"{record_base}/analyst_synthesis/{generation}"
    app = create_app(data_root=tmp_path, bridge=FakeCodexBridge())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get(url, params={"view": "document", "entry_pointer": "/question_results/0"})
        assert response.status_code == 200
        passage = response.json()
        assert passage["generation_ref"]["run_id"] == original["run_id"]
        link = passage["cited_exhibits"][0]["reference"]
        table_url = f"{record_base}/exhibits/{link['generation_id']}"
        response = await client.get(table_url, params={"view": "document", "entry_pointer": link["entry_pointer"]})
        assert response.status_code == 200
        exhibit = response.json()["exhibit"]
        assert exhibit["table"]["rows"] == [{"risk": 0.12}]
        assert (await client.get(exhibit["artifact_url"])).content == table_file.read_bytes()
        table_file.write_text("changed")
        assert (await client.get(exhibit["artifact_url"])).status_code == 409
        assert (await client.get(url, params={"view": "document", "entry_pointer": "/question_results/-1"})).status_code == 400
        assert (await client.get(f"{record_base}/analyst_synthesis/generation.absent", params={"view": "document", "entry_pointer": "/question_results/0"})).status_code == 404
