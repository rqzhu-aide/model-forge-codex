"""Saved-row presentation uses the ordinary managed route, without new observations."""
import json
from pathlib import Path
from copy import deepcopy
import shutil

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.p4_execution import P4Controller, P4ExecutionError
from test_p4_execution import local_runner, queue
from test_researcher_workbench_engine import scientific_output_documents


@pytest.mark.asyncio
async def test_saved_display_batch_seals_a_compact_file_and_keeps_original_rows(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_dir = tmp_path / "run"
    shutil.copytree(repo / "contracts", run_dir / "contracts")
    catalog = Catalog(run_dir / "contracts")
    identity = json.loads((repo / "contracts/examples/method.example.json").read_text())["identity"]
    documents, files = scientific_output_documents(catalog, "P4", identity, mode="p4.preliminary")
    for name, content in files.items():
        destination = workspace / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    plan = documents["p4.protocol"]
    display_work = deepcopy(plan["work_items"][0])
    display_work.update(work_item_id="work.display", title="Format the saved comparison rows",
                        depends_on=[], essential=False, estimated_seconds=1,
                        stop_conditions_markdown="Stop after retaining the display; do not generate new observations.")
    plan["work_items"].append(display_work)
    assert catalog.validate_output("p4.protocol", plan) == []
    (workspace / "protocol.json").write_text(json.dumps(plan), encoding="utf-8")
    controller = P4Controller(run_dir, workspace, stage_id="p4.analyst", member="data_analyst", runner=local_runner())
    assert controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})["accepted"]
    rows = [{"condition": "A", "estimate": 0.12, "diagnostic": "retained"},
            {"condition": "B", "estimate": None, "diagnostic": "no selected policy"}]
    source = workspace / "saved_rows.json"
    source.write_text(json.dumps(rows), encoding="utf-8")
    before = source.read_bytes()
    (workspace / "compute.py").write_text(
        "import json,pathlib\n"
        "rows=json.loads(pathlib.Path('saved_rows.json').read_text())\n"
        "table={'columns':['condition','estimate'],'rows':[{'condition':r['condition'],"
        "'estimate':r['estimate'] if r['estimate'] is not None else 'Undefined: no selected policy'} for r in rows]}\n"
        "pathlib.Path('compact.json').write_text(json.dumps(table))\n", encoding="utf-8")
    queue(controller, work_item_id="work.display", support_files=["saved_rows.json"], result_paths=["compact.json"])
    attempt = await controller.execute_pending()
    assert attempt["status"] == "completed"
    assert source.read_bytes() == before
    artifact = next(item for item in attempt["artifacts"] if Path(item["path"]).name == "compact.json")
    display = json.loads(Path(artifact["path"]).read_text())
    assert display["columns"] == ["condition", "estimate"]
    assert display["rows"] == [{"condition": "A", "estimate": 0.12},
                               {"condition": "B", "estimate": "Undefined: no selected policy"}]
    assert any(item["path"] == "saved_rows.json" for item in attempt["source_files"])
    assert controller.snapshot()["budget"]["used_seconds"] > 0
    # Presentation execution is still a charged attempt, not a new observation.
    assert len(controller.snapshot()["ledger"]) == 1
    controller.request({"operation": "request_decision", "question": "Finish with existing evidence?",
                        "reason": "No further execution is needed."})
    controller.resume("Finish with existing evidence.", {"action": "finish", "revision": 1})
    with pytest.raises(P4ExecutionError, match="existing evidence"):
        queue(controller, work_item_id="work.display", batch_id="batch.after-finish", result_paths=["compact.json"])
