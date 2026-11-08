"""Interrupted catalog adoption repairs only the selected project's catalog."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import shutil
import threading

import pytest

from model_forge_codex import migration
from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.catalog import Catalog, CatalogError
from model_forge_codex.runs import RunEngine
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import workbench, REPO


class ProcessLost(BaseException):
    """Bypass the ordinary exception rollback, as a process kill would."""


def make_catalog(root, version, *, dialogue=False):
    write_json_atomic(root / "schemas/value.schema.json", {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"})
    write_json_atomic(root / "contracts/phases/P1.json", {"phase_id": "P1", "capabilities": ["researcher_dialogue_v1"] if dialogue else []})
    (root / "VERSION").write_text(version, encoding="utf-8")
    manifest = "".join(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.relative_to(root).as_posix() + "\n"
                       for path in sorted(root.rglob("*")) if path.is_file())
    (root / "MANIFEST.sha256").write_text(manifest, encoding="utf-8", newline="\n")
    write_json_atomic(root / "catalog-pin.json", {"catalog_version": version,
                      "catalog_manifest_sha256": hashlib.sha256(manifest.encode()).hexdigest()})


@pytest.fixture
def catalogs(tmp_path, monkeypatch):
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    project = tmp_path / "data/projects/project.test"
    write_json_atomic(project / "project.json", {"project_id": "project.test", "research_question": "Preserve my study."})
    make_catalog(project / "contracts", "1.0.0")
    offer = tmp_path / "offered"
    make_catalog(offer, "2.0.0", dialogue=True)
    shutil.copytree(project / "contracts", project / "runs/run.old/contracts")
    write_json_atomic(project / "runs/run.old/run.json", {"run_id": "run.old", "state": "published"})
    write_json_atomic(project / "researcher/answers.json", {"saved": "My original answer"})
    write_json_atomic(project / "branches/trunk/phases/p1/history.json", {"claim": "Retain exact evidence"})
    return project, offer


def retained_bytes(project):
    return {path.relative_to(project).as_posix(): path.read_bytes()
            for directory in ("runs", "researcher", "branches")
            for path in (project / directory).rglob("*") if path.is_file()}


def strand_legacy(project, offer, token="a" * 32, *, source=None):
    staged = project / ("catalog-update-" + token)
    shutil.copytree(offer, staged)
    source = source or project / "contracts"
    version = read_json(source / "catalog-pin.json")["catalog_version"]
    archive = project / "catalog-history" / (version + "-" + token)
    archive.parent.mkdir(exist_ok=True)
    if source == project / "contracts":
        os.replace(source, archive)
    else:
        shutil.copytree(source, archive)
    return staged, archive


def lose_process_at(monkeypatch, project, after):
    replace = os.replace
    def interrupted(source, destination):
        replace(source, destination)
        source, destination = Path(source), Path(destination)
        if ((after == "archive" and source == project / "contracts") or
                (after == "promote" and source.name.startswith("catalog-update-") and destination == project / "contracts")):
            raise ProcessLost()
    monkeypatch.setattr(migration.os, "replace", interrupted)


@pytest.mark.parametrize("access", ["catalog", "project", "preview", "boot", "retry"])
def test_legacy_interruption_recovers_on_normal_access(catalogs, access):
    project, offer = catalogs
    before = retained_bytes(project)
    stage, archive = strand_legacy(project, offer)
    engine = RunEngine(project.parents[1], FakeCodexBridge())
    if access == "catalog":
        assert Catalog(project / "contracts").version == "1.0.0"
    elif access == "project":
        assert engine.project_dir("project.test") == project
    elif access == "preview":
        assert migration.preview_catalog_upgrade(project, offer)["version"] == "1.0.0"
    elif access == "boot":
        engine.reconcile_on_boot()
    else:
        assert migration.upgrade_catalog(project, offer)["version"] == "2.0.0"
    assert Catalog(project / "runs/run.old/contracts").version == "1.0.0"
    assert before.items() <= retained_bytes(project).items()
    assert stage.exists() and not archive.exists()
    if access != "retry":
        assert Catalog(project / "contracts").version == "1.0.0"
        assert not (project / "researcher/problem_context.json").exists()


@pytest.mark.parametrize("after", ["archive", "promote"])
def test_receipted_process_loss_recovers_and_retry_is_safe(catalogs, monkeypatch, after):
    project, offer = catalogs
    before = retained_bytes(project)
    with monkeypatch.context() as interrupted:
        lose_process_at(interrupted, project, after)
        with pytest.raises(ProcessLost):
            migration.upgrade_catalog(project, offer)
    assert (project / "catalog-upgrade.json").is_file()
    assert Catalog(project / "contracts").version == ("1.0.0" if after == "archive" else "2.0.0")
    assert not (project / "catalog-upgrade.json").exists()
    assert not list(project.glob("catalog-update-*"))
    assert before.items() <= retained_bytes(project).items()
    assert migration.upgrade_catalog(project, offer)["version"] == "2.0.0"
    assert read_json(project / "researcher/problem_context.json")["revision"] == 1
    assert len(list((project / "catalog-history").iterdir())) == 1


def test_context_initialization_failure_finishes_on_access_without_replacing_saved_context(catalogs, monkeypatch):
    project, offer = catalogs
    from model_forge_codex import problem_context
    initialize = problem_context.initialize_problem_context
    with monkeypatch.context() as failing:
        failing.setattr(problem_context, "initialize_problem_context", lambda _: (_ for _ in ()).throw(OSError("disk unavailable")))
        with pytest.raises(OSError, match="disk unavailable"):
            migration.upgrade_catalog(project, offer)
    assert read_json(project / "contracts/catalog-pin.json")["catalog_version"] == "2.0.0"
    saved = initialize(project)
    saved["revision"] = 7
    saved["items"] = [{"statement": "Researcher-owned context"}]
    write_json_atomic(project / "researcher/problem_context.json", saved)
    before = retained_bytes(project)
    assert migration.preview_catalog_upgrade(project, offer)["version"] == "2.0.0"
    assert retained_bytes(project) == before
    assert not (project / "catalog-upgrade.json").exists()


def test_ordinary_rename_and_rollback_io_failure_remains_recoverable(catalogs, monkeypatch):
    project, offer = catalogs
    replace = os.replace
    def fail_promote_and_rollback(source, destination):
        if Path(destination) == project / "contracts":
            raise PermissionError("temporary directory sharing failure")
        replace(source, destination)
    with monkeypatch.context() as failing:
        failing.setattr(migration.os, "replace", fail_promote_and_rollback)
        with pytest.raises(PermissionError, match="sharing"):
            migration.upgrade_catalog(project, offer)
    assert not (project / "contracts").exists()
    assert Catalog(project / "contracts").version == "1.0.0"
    assert not list(project.glob("catalog-update-*"))
    assert migration.upgrade_catalog(project, offer)["version"] == "2.0.0"


def test_ambiguous_or_tampered_legacy_recovery_fails_closed(catalogs):
    project, offer = catalogs
    _, archive = strand_legacy(project, offer)
    strand_legacy(project, offer, token="b" * 32, source=archive)
    before = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="Several"):
        migration.recover_catalog_upgrade(project)
    assert not (project / "contracts").exists()
    assert {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()} == before
    shutil.rmtree(project / ("catalog-update-" + "b" * 32))
    (archive / "schemas/value.schema.json").write_text("{}")
    with pytest.raises(ValueError, match="integrity"):
        migration.recover_catalog_upgrade(project)
    assert not (project / "contracts").exists()


def test_valid_current_pin_wins_over_leftover_legacy_pairs(catalogs):
    project, offer = catalogs
    _, archive = strand_legacy(project, offer)
    shutil.copytree(offer, project / "contracts")
    before = retained_bytes(project)
    assert Catalog(project / "contracts").version == "2.0.0"
    assert migration.upgrade_catalog(project, offer)["version"] == "2.0.0"
    assert archive.exists() and retained_bytes(project) == before
    assert not (project / "researcher/problem_context.json").exists()


@pytest.mark.parametrize("version", ["../9", [9, 0, 0], "x.999", None])
def test_invalid_offered_version_changes_nothing(catalogs, version):
    project, offer = catalogs
    pin = read_json(offer / "catalog-pin.json")
    write_json_atomic(offer / "catalog-pin.json", {**pin, "catalog_version": version})
    before = Catalog(project / "contracts").snapshot_sha256
    with pytest.raises(ValueError, match="version"):
        migration.upgrade_catalog(project, offer)
    assert Catalog(project / "contracts").snapshot_sha256 == before
    assert not list(project.glob("catalog-update-*"))


def test_competing_upgrade_and_reader_wait_for_completed_swap(catalogs, monkeypatch):
    project, offer = catalogs
    archived = threading.Event()
    proceed = threading.Event()
    replace = os.replace
    def paused(source, destination):
        replace(source, destination)
        if Path(source) == project / "contracts":
            archived.set()
            assert proceed.wait(10)
    monkeypatch.setattr(migration.os, "replace", paused)
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(migration.upgrade_catalog, project, offer)
        assert archived.wait(10)
        second = pool.submit(migration.upgrade_catalog, project, offer)
        reader = pool.submit(lambda: Catalog(project / "contracts").version)
        try:
            assert not second.done() and not reader.done()
        finally:
            proceed.set()
        assert first.result()["version"] == second.result()["version"] == reader.result() == "2.0.0"
    assert len(list((project / "catalog-history").iterdir())) == 1
    assert not list(project.glob("catalog-update-*"))


def test_old_catalog_object_cannot_mix_old_schemas_with_new_project_pin(catalogs):
    project, offer = catalogs
    old = Catalog(project / "contracts")
    frozen = Catalog(project / "runs/run.old/contracts")
    migration.upgrade_catalog(project, offer)
    with pytest.raises(CatalogError, match="workflow changed"):
        old.output_definitions()
    assert frozen.schema_doc("value.schema.json")["type"] == "object"


def test_read_only_browse_never_initializes_or_repairs(catalogs, monkeypatch):
    project, offer = catalogs
    before = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    monkeypatch.setenv("MF_CODEX_READ_ONLY", "1")
    assert Catalog(project / "contracts").version == "1.0.0"
    assert migration.preview_catalog_upgrade(project, offer)["version"] == "1.0.0"
    assert {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()} == before
    strand_legacy(project, offer)
    migration.recover_catalog_upgrade(project)
    assert not (project / "contracts").exists()


def test_healthy_read_only_project_does_not_require_any_research_write(catalogs, monkeypatch):
    project, offer = catalogs
    monkeypatch.setenv("MF_CODEX_READ_ONLY", "1")
    original = Path.open
    def read_only(path, mode="r", *args, **kwargs):
        if path.is_relative_to(project) and any(flag in mode for flag in "wax+"):
            raise PermissionError("Research storage is physically read-only")
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, "open", read_only)
    assert Catalog(project / "contracts").verify_manifest() == []
    assert migration.preview_catalog_upgrade(project, offer)["version"] == "1.0.0"
    with pytest.raises(ValueError, match="read-only"):
        migration.upgrade_catalog(project, offer)


def test_linked_history_cannot_restore_an_unrelated_catalog(catalogs, tmp_path):
    project, offer = catalogs
    token = "a" * 32
    shutil.copytree(offer, project / ("catalog-update-" + token))
    outside = tmp_path / "unrelated"
    outside.mkdir()
    archived = outside / ("1.0.0-" + token)
    os.replace(project / "contracts", archived)
    history = project / "catalog-history"
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(outside), str(history))
    else:
        history.symlink_to(outside, target_is_directory=True)
    before = Catalog(archived).snapshot_sha256
    with pytest.raises(ValueError, match="outside"):
        migration.recover_catalog_upgrade(project)
    assert not (project / "contracts").exists()
    assert Catalog(archived).snapshot_sha256 == before


def test_existing_staging_directory_is_never_adopted_or_cleaned(catalogs, monkeypatch):
    project, offer = catalogs
    token = migration.uuid.UUID(int=1)
    monkeypatch.setattr(migration.uuid, "uuid4", lambda: token)
    stage = project / ("catalog-update-" + token.hex)
    stage.mkdir()
    sentinel = stage / "prior-attempt.txt"
    sentinel.write_text("retain", encoding="utf-8")
    with pytest.raises(FileExistsError):
        migration.upgrade_catalog(project, offer)
    assert sentinel.read_text(encoding="utf-8") == "retain"
    assert Catalog(project / "contracts").version == "1.0.0"


def test_changed_offered_copy_is_rejected_before_existing_catalog_moves(catalogs, monkeypatch):
    project, offer = catalogs
    original = shutil.copytree
    def changed_copy(source, destination, *args, **kwargs):
        result = original(source, destination, *args, **kwargs)
        if Path(source) == offer:
            (Path(destination) / "schemas/value.schema.json").write_text("{}")
        return result
    monkeypatch.setattr(migration.shutil, "copytree", changed_copy)
    with pytest.raises(ValueError, match="integrity"):
        migration.upgrade_catalog(project, offer)
    assert Catalog(project / "contracts").version == "1.0.0"
    assert not (project / "catalog-upgrade.json").exists()


def test_active_or_paused_run_blocks_adoption_but_not_catalog_recovery(catalogs):
    project, offer = catalogs
    strand_legacy(project, offer)
    write_json_atomic(project / "runs/run.paused/run.json", {"run_id": "run.paused", "state": "awaiting_user"})
    with pytest.raises(ValueError, match="Finish or cancel"):
        migration.upgrade_catalog(project, offer)
    assert Catalog(project / "contracts").version == "1.0.0"
    assert read_json(project / "runs/run.paused/run.json")["state"] == "awaiting_user"


def test_one_broken_project_does_not_prevent_unrelated_boot_recovery(catalogs):
    project, offer = catalogs
    _, archive = strand_legacy(project, offer)
    strand_legacy(project, offer, token="b" * 32, source=archive)
    write_json_atomic(project / "runs/run.active/run.json", {"run_id": "run.active", "state": "running"})
    other = project.with_name("project.other")
    shutil.copytree(project, other)
    shutil.rmtree(other / ("catalog-update-" + "b" * 32))
    shutil.rmtree(other / "runs/run.active")
    engine = RunEngine(project.parents[1], FakeCodexBridge())
    assert engine.reconcile_on_boot() == []
    assert not (project / "contracts").exists()
    assert Catalog(other / "contracts").version == "1.0.0"


async def test_first_run_after_recovery_and_later_adoption_keep_their_own_pins(workbench, monkeypatch):
    engine, project, branch = workbench
    pin = read_json(project / "contracts/catalog-pin.json")
    write_json_atomic(project / "contracts/catalog-pin.json", {**pin, "catalog_version": "1.3.0"})
    strand_legacy(project, REPO / "contracts")
    async def no_model_calls(*args):
        pass
    monkeypatch.setattr(engine, "_drive", no_model_calls)
    first = await engine.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    await engine._tasks[first.run_id]
    first_directory = project / "runs" / first.run_id
    assert Catalog(first_directory / "contracts").version == "1.3.0"
    assert read_json(first_directory / "basis.json")["catalog_pin"]["catalog_version"] == "1.3.0"
    from model_forge_codex.domain import RunState
    first.state = RunState.FAILED
    engine._save_run(first)
    before = {p.relative_to(first_directory).as_posix(): p.read_bytes() for p in first_directory.rglob("*") if p.is_file()}
    migration.upgrade_catalog(project, REPO / "contracts")
    second = await engine.start_run("project.test", phase="P1", mode="p1.literature_update", branch_id="trunk")
    await engine._tasks[second.run_id]
    assert Catalog(project / "runs" / second.run_id / "contracts").version == pin["catalog_version"]
    assert {p.relative_to(first_directory).as_posix(): p.read_bytes() for p in first_directory.rglob("*") if p.is_file()} == before
