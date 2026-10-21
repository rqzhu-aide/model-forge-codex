"""Phase 2 history reports committed publication process facts, not quality."""
import copy
import json

import pytest

from model_forge_codex.domain import RunState
from model_forge_codex.research import artifacts_view
from model_forge_codex.storage import read_json, write_json_atomic
from test_direct_workflow import PID, complete, direct_engine, p1_documents, p2_documents, script
from test_literature_projection import publish


async def test_p2_publication_freezes_repair_and_correction_counts(direct_engine):
    engine, project = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    outputs, files = p2_documents(False)
    broken = copy.deepcopy(outputs)
    del broken["p2.catalog_assessment"]["method_dispositions"][0]["method_summary_markdown"]
    script(engine, "P2", "p2.full_catalog", broken, files)
    started = await engine.start_run(PID, phase="P2", mode="p2.full_catalog", branch_id="trunk")
    await engine._tasks[started.run_id]
    failed = engine.load_run(PID, started.run_id)
    assert failed.state is RunState.FAILED
    assert failed.mechanical_repair_attempts == {"p2.lead_reconciliation": 1}
    assert artifacts_view(project)["publication_history"] == []

    engine.bridge.script_thread("research_lead:PROJECT:trunk", [("ok", {
        "catalog_assessment.json": json.dumps(outputs["p2.catalog_assessment"]),
    })])
    await engine.correct(PID, started.run_id, "Supply the missing method procedure summary.")
    # Authorization is not publication: pending and failed corrections do not
    # acquire a publication-history row just because their count increased.
    assert artifacts_view(project)["publication_history"] == []
    await engine._tasks[started.run_id]
    assert engine.load_run(PID, started.run_id).state is RunState.PUBLISHED
    package = read_json(project / "branches/trunk/phases/p2/current-package.json")
    expected = {"mechanical_repair_rounds": 1, "researcher_correction_attempts": 1}
    assert package["metadata"]["publication_history"] == expected
    receipt = read_json(project / "authority/receipts" / (package["metadata"]["receipt_id"] + ".json"))
    assert receipt["publication_history"] == expected
    assert receipt["package_id"] == package["package_id"] and receipt["run_id"] == started.run_id
    row = artifacts_view(project)["publication_history"][0]
    assert row == {**expected, "branch": "trunk", "phase": "P2", "run_id": started.run_id,
                   "package_id": package["package_id"], "published_at": package["published_at"],
                   "receipt_id": receipt["receipt_id"], "is_current_package": True}
    run_path = engine.run_dir(PID, started.run_id) / "run.json"
    mutable = read_json(run_path)
    mutable.update(mechanical_repair_attempts={"later.history": 9}, correction_attempts=9)
    write_json_atomic(run_path, mutable)
    assert artifacts_view(project)["publication_history"][0] == row


def test_history_keeps_exact_committed_package_order_and_ignores_orphans(tmp_path):
    records = {"catalog_assessment": {"title": "A recorded comparison"}}
    first = publish(tmp_path, records, phase="P2", run_id="run.first", metadata={
        "receipt_id": "receipt.first", "publication_history": {
            "mechanical_repair_rounds": 2, "researcher_correction_attempts": 1,
        },
    })
    second = publish(tmp_path, records, phase="P2", run_id="run.second", metadata={
        "receipt_id": "receipt.second", "publication_history": {
            "mechanical_repair_rounds": 0, "researcher_correction_attempts": 0,
        },
    })

    def stop_before_commit(package):
        write_json_atomic(tmp_path / "authority/receipts/receipt.orphan.json", {
            "run_id": "run.orphan", "package_id": package["package_id"], "phase": "P2", "branch_id": "trunk",
        })
        raise RuntimeError("Publication interrupted")

    with pytest.raises(RuntimeError, match="interrupted"):
        publish(tmp_path, records, phase="P2", run_id="run.orphan", before_commit=stop_before_commit,
                metadata={"receipt_id": "receipt.orphan"})
    history = artifacts_view(tmp_path)["publication_history"]
    assert [(row["run_id"], row["package_id"], row["receipt_id"], row["is_current_package"])
            for row in history] == [("run.second", second["package_id"], "receipt.second", True),
                                   ("run.first", first["package_id"], "receipt.first", False)]
    assert [(row["mechanical_repair_rounds"], row["researcher_correction_attempts"])
            for row in history] == [(0, 0), (2, 1)]


def test_old_publication_counts_are_unknown_even_when_run_has_counts(tmp_path):
    publish(tmp_path, {"catalog_assessment": {"title": "Earlier comparison"}}, phase="P2", run_id="run.old")
    write_json_atomic(tmp_path / "runs/run.old/run.json", {
        "state": "published", "mechanical_repair_attempts": {}, "correction_attempts": 0,
    })
    row = artifacts_view(tmp_path)["publication_history"][0]
    assert row["run_id"] == "run.old"
    assert row["mechanical_repair_rounds"] is None and row["researcher_correction_attempts"] is None
    assert row["receipt_id"] is None


@pytest.mark.parametrize("invalid", [-1, True, "1", None])
def test_invalid_saved_counts_are_unavailable(tmp_path, invalid):
    publish(tmp_path, {"catalog_assessment": {}}, phase="P2", metadata={"publication_history": {
        "mechanical_repair_rounds": invalid, "researcher_correction_attempts": invalid,
    }})
    row = artifacts_view(tmp_path)["publication_history"][0]
    assert row["mechanical_repair_rounds"] is None and row["researcher_correction_attempts"] is None
