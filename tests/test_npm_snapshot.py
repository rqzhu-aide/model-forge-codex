"""Packaged releases retain verified bytes independently of npm's mutable cache."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import threading

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/npm_snapshot.py"
spec = importlib.util.spec_from_file_location("npm_snapshot_checks", SCRIPT)
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


def seal_manifest(source, files, version="1.2.3"):
    identity = {"package": snapshot.PACKAGE, "version": version, "files": dict(sorted(files.items()))}
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    manifest = {"schema_version": 1, **identity, "release_id": f"npm-{version}-{digest[:16]}"}
    (source / snapshot.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def source_release(tmp_path):
    source = tmp_path / "npm cache/package"
    payloads = {
        "scripts/npm_launcher.py": "# Launcher\n",
        "scripts/npm_snapshot.py": "# Snapshot helper\n",
        "scripts/validate_local_install.py": "# Preflight\n",
        "src/model_forge_codex/local_app.py": "# Application\n",
        "contracts/catalog-pin.json": json.dumps({"catalog_version": "1.14.0"}),
        "web/dist/index.html": "<html>Research application</html>",
        "web/runtime/validate-math.mjs": "// Bundled mathematical notation checker\n",
        "web/runtime/export-report.mjs": "// Bundled portable report exporter\n",
        "web/dist/assets/app.js": "window.research = true;\n",
    }
    files = {}
    for relative, text in payloads.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        files[relative] = snapshot.file_digest(path)
    return source, seal_manifest(source, files)


def test_snapshot_remains_usable_after_npm_changes_its_download_cache(tmp_path):
    source, manifest = source_release(tmp_path)
    releases = tmp_path / "persistent app/releases"
    target = snapshot.snapshot_release(source, releases)
    assert target.parent == releases.resolve()
    original = (target / "web/dist/assets/app.js").read_bytes()
    (source / "web/dist/assets/app.js").write_text("window.research = 'changed cache';", encoding="utf-8")
    assert (target / "web/dist/assets/app.js").read_bytes() == original
    # An already verified snapshot remains reusable even if npm replaced its cache.
    assert snapshot.snapshot_release(source, releases) == target
    metadata = json.loads((target / "local-release.json").read_text(encoding="utf-8"))
    assert metadata == {"release_id": manifest["release_id"], "package_version": "1.2.3", "catalog_version": "1.14.0"}
    assert not list(releases.glob(".staging-*"))


def test_same_version_with_changed_payload_gets_a_distinct_retained_release(tmp_path):
    source, manifest = source_release(tmp_path)
    releases = tmp_path / "persistent app/releases"
    first = snapshot.snapshot_release(source, releases)
    relative = "web/dist/assets/app.js"
    before = (first / relative).read_bytes()
    (source / relative).write_text("window.research = 'revised';", encoding="utf-8")
    files = dict(manifest["files"], **{relative: snapshot.file_digest(source / relative)})
    changed = seal_manifest(source, files)
    second = snapshot.snapshot_release(source, releases)
    assert second != first
    assert changed["release_id"] != manifest["release_id"]
    assert (first / relative).read_bytes() == before
    assert (second / relative).read_bytes() == (source / relative).read_bytes()


@pytest.mark.parametrize("missing", [False, True])
def test_changed_or_missing_source_file_is_rejected_before_creating_release(tmp_path, missing):
    source, _ = source_release(tmp_path)
    payload = source / "web/dist/assets/app.js"
    if missing:
        payload.unlink()
    else:
        payload.write_text("Changed after manifest was sealed", encoding="utf-8")
    releases = tmp_path / "persistent app/releases"
    with pytest.raises(ValueError, match="Release file is missing or changed"):
        snapshot.snapshot_release(source, releases)
    assert not releases.exists()


@pytest.mark.parametrize("kind", ["payload", "metadata"])
def test_changed_saved_release_is_rejected_instead_of_reused(tmp_path, kind):
    source, _ = source_release(tmp_path)
    releases = tmp_path / "persistent app/releases"
    target = snapshot.snapshot_release(source, releases)
    if kind == "payload":
        (target / "web/dist/assets/app.js").write_text("Changed installed file", encoding="utf-8")
    else:
        (target / "local-release.json").write_text('{"release_id": "different"}', encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        snapshot.snapshot_release(source, releases)
    assert not list(releases.glob(".staging-*"))


@pytest.mark.parametrize("relative", ["../outside.txt", "/outside.txt", "C:/outside.txt", "web/../../outside.txt", "web\\outside.txt"])
def test_traversal_is_rejected_even_with_a_matching_manifest_identity(tmp_path, relative):
    source, manifest = source_release(tmp_path)
    files = {**manifest["files"], relative: "0" * 64}
    seal_manifest(source, files)
    releases = tmp_path / "persistent app/releases"
    with pytest.raises(ValueError, match="invalid file entry"):
        snapshot.snapshot_release(source, releases)
    assert not releases.exists()
    assert not (tmp_path / "outside.txt").exists()


def test_cache_change_during_copy_is_detected_and_staging_is_removed(tmp_path, monkeypatch):
    source, _ = source_release(tmp_path)
    releases = tmp_path / "persistent app/releases"
    copy = snapshot.shutil.copyfile

    def change_while_copying(origin, destination):
        if Path(origin).name == "app.js":
            Path(origin).write_text("Cache changed while copying", encoding="utf-8")
        return copy(origin, destination)

    monkeypatch.setattr(snapshot.shutil, "copyfile", change_while_copying)
    with pytest.raises(ValueError, match="Release file is missing or changed"):
        snapshot.snapshot_release(source, releases)
    assert list(releases.iterdir()) == []


def test_simultaneous_launches_publish_one_complete_snapshot_and_can_reuse_it(tmp_path, monkeypatch):
    source, manifest = source_release(tmp_path)
    releases = tmp_path / "persistent app/releases"
    both_copying = threading.Barrier(2)
    copy = snapshot.shutil.copyfile
    first_relative = next(iter(manifest["files"]))

    def wait_for_both_launchers(origin, destination):
        if Path(origin) == source / first_relative:
            both_copying.wait(timeout=10)
        return copy(origin, destination)

    monkeypatch.setattr(snapshot.shutil, "copyfile", wait_for_both_launchers)
    with ThreadPoolExecutor(max_workers=2) as workers:
        launched = [workers.submit(snapshot.snapshot_release, source, releases) for _ in range(2)]
        targets = [future.result(timeout=20) for future in launched]
    assert targets[0] == targets[1]
    assert list(releases.iterdir()) == [targets[0]]
    snapshot.verify_files(targets[0], manifest["files"])
    assert snapshot.snapshot_release(source, releases) == targets[0]
