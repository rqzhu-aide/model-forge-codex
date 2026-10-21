"""Local data selection, immutable run inputs and exact portable code exports."""
import asyncio
import base64
import io
import json
import zipfile

import pytest

from model_forge_codex.implementation_export import export_implementation
from model_forge_codex.records import ArtifactError, publish_package
from model_forge_codex.researcher_inputs import freeze_inputs, import_input, input_brief, retain_support_files, selected_inputs
from model_forge_codex.storage import read_json, sha256_bytes, write_json_atomic
from test_researcher_workbench_api import api
from test_researcher_workbench_engine import workbench

BASE = "/api/v1/projects/project.test"


def request(content=b"patient,time,event\nsynthetic_a,3,1\n", **changes):
    return {"filename": "example.csv", "role": "dataset", "content_base64": base64.b64encode(content).decode(),
            "mapping": {"time": "time", "event": "event"}, **changes}


def test_freeze_keeps_private_bytes_out_of_brief_and_support_export(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    write_json_atomic(project / "project.json", {})
    original = b"patient,time,event\nprivate_identifier,3,1\n"
    row = import_input(project, **request(original))
    run = project / "runs/run.test"
    manifest = freeze_inputs(project, run, [row["input_id"]])
    from pathlib import Path
    assert Path(manifest["inputs"][0]["snapshot_path"]).read_bytes() == original
    assert "private_identifier" not in input_brief(manifest)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "renamed-data.txt").write_bytes(original)
    (workspace / "model.py").write_text("def fit(data): return len(data)\n")
    assert retain_support_files(workspace, tmp_path / "retained", set(), manifest) == ["renamed-data.txt"]
    assert not (tmp_path / "retained/renamed-data.txt").exists()
    assert (tmp_path / "retained/model.py").exists()
    (project / "researcher/inputs" / row["input_id"] / "content" / row["filename"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        selected_inputs(project, [row["input_id"]])
    assert Path(manifest["inputs"][0]["snapshot_path"]).read_bytes() == original


@pytest.mark.parametrize("filename", ["../data.csv", "C:\\data.csv", "con.txt", "data.", "a/b.csv"])
def test_inputs_reject_nonportable_names(tmp_path, filename):
    write_json_atomic(tmp_path / "project.json", {})
    with pytest.raises(ValueError, match="filename"):
        import_input(tmp_path, **request(filename=filename))


def test_input_json_filename_preserves_content_and_metadata(tmp_path):
    write_json_atomic(tmp_path / "project.json", {})
    row = import_input(tmp_path, **request(b'{"key": 42}', filename="input.json", role="configuration"))
    assert selected_inputs(tmp_path, [row["input_id"]]) == [row]


async def test_input_api_selection_persists_and_freezes_before_provider(api):
    client, engine, project, branch = api
    created = await client.post(BASE + "/inputs", json=request())
    assert created.status_code == 200, created.text
    row = created.json()
    assert "content_base64" not in row and "snapshot_path" not in row
    assert (await client.get(BASE + "/inputs")).json()["inputs"] == [row]
    prep = BASE + f"/branches/{branch}/phases/P4/preparation"
    assert (await client.put(prep, json={"instructions": "Analyze mapped data", "input_ids": [row["input_id"]]})).status_code == 200
    await client.put(prep, json={"instructions": "Update the analysis"})
    assert (await client.get(prep)).json()["input_ids"] == [row["input_id"]]
    assert (await client.put(prep, json={"instructions": "bad", "input_ids": ["input.unknown"]})).status_code == 400
    engine.bridge.script_thread(f"data_analyst:P4:{branch}", [("interruptible", 30)])
    launched = await client.post(BASE + "/runs", json={"phase": "P4", "mode": "p4.preliminary", "branch_id": branch,
        "input_ids": [row["input_id"]]})
    assert launched.status_code == 200, launched.text
    run_id = launched.json()["run_id"]
    try:
        basis = read_json(project / "runs" / run_id / "basis.json")
        assert basis["p4_inputs"]["inputs"][0]["sha256"] == row["sha256"]
        assert basis["p4_inputs"]["inputs"][0]["mapping"] == row["mapping"]
        async with asyncio.timeout(10):
            while not engine.bridge.turns:
                await asyncio.sleep(.01)
        assert (await client.post(BASE + f"/runs/{run_id}/pause")).status_code == 200
    finally:
        if run_id in engine._tasks and not engine._tasks[run_id].done():
            engine._tasks[run_id].cancel()
            await asyncio.gather(engine._tasks[run_id], return_exceptions=True)


def make_export(project, branch="method.test"):
    run_id = "run.export"
    destination = project / "runs" / run_id / "outputs/p4.analyst/code"
    destination.mkdir(parents=True)
    entries = {}
    for key, name in (("model_entrypoint", "model.py"), ("example_generator", "generate.py"),
                      ("example_runner", "example.py"), ("readme", "README.md")):
        data = (name + "\n").encode()
        (destination / name).write_bytes(data)
        entries[key] = {"kind": key, "artifact": {"path": "code/" + name, "sha256": sha256_bytes(data)}}
    document = {"reproduction": {"status": "available", "language": "python", **entries, "support_files": []}}
    package = publish_package(project / "branches" / branch / "phases/p4", {"implementation_record": json.dumps(document).encode()},
        run_id=run_id, phase="P4", branch_id=branch, metadata={"stage_ids": {"implementation_record": "p4.analyst"}})
    write_json_atomic(project / "runs" / run_id / "run.json", {"state": "published", "branch_id": branch, "phase": "P4"})
    return document, package["records"]["implementation_record"]


async def test_download_bundle_uses_exact_published_sources_and_rejects_mutation(api):
    client, engine, project, branch = api
    document, meta = make_export(project, branch)
    url = BASE + f"/branches/{branch}/phases/P4/records/implementation_record/{meta['generation_id']}/implementation-bundle"
    response = await client.get(url)
    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"].startswith("attachment")
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert set(archive.namelist()) == {"code/model.py", "code/generate.py", "code/example.py", "code/README.md", "model-forge-export.json"}
    view = (await client.get(BASE + f"/artifacts?branch={branch}")).json()
    account = view["implementations"][0]
    assert account["bundle_url"] == url
    assert all(item["download_url"].endswith("&download=true") for item in account["files"])
    assert (await client.get(account["files"][0]["download_url"])).headers["content-disposition"].startswith("attachment")
    (project / "runs/run.export/outputs/p4.analyst/code/model.py").write_text("changed")
    assert (await client.get(url)).status_code == 409
    account = (await client.get(BASE + f"/artifacts?branch={branch}")).json()["implementations"][0]
    assert "bundle_url" not in account and account["bundle_error"]


def test_export_rejects_raw_selected_dataset_and_incomplete_reproduction(tmp_path):
    document, meta = make_export(tmp_path)
    digest = document["reproduction"]["model_entrypoint"]["artifact"]["sha256"]
    write_json_atomic(tmp_path / "runs/run.export/basis.json", {"p4_inputs": {"inputs": [{"role": "dataset", "sha256": digest}]}})
    with pytest.raises(ArtifactError, match="datasets"):
        export_implementation(tmp_path, meta, document)


def test_export_reuses_exact_frozen_sources(tmp_path):
    document, meta = make_export(tmp_path)
    pointer = document["reproduction"]["model_entrypoint"]["artifact"]
    source = tmp_path / "runs/run.export/outputs/p4.analyst/code/model.py"
    retained = tmp_path / "runs/run.export/inputs/reused-model.py"
    retained.parent.mkdir(parents=True)
    retained.write_bytes(source.read_bytes())
    source.unlink()
    write_json_atomic(tmp_path / "runs/run.export/basis.json", {"artifacts": [
        {"content_sha256": pointer["sha256"], "original_path": pointer["path"], "path": str(retained)}]})
    bundle = zipfile.ZipFile(io.BytesIO(export_implementation(tmp_path, meta, document)))
    assert bundle.read("code/model.py") == retained.read_bytes()
    document["reproduction"]["readme"] = None
    with pytest.raises(ArtifactError, match="README"):
        export_implementation(tmp_path, meta, document)
