"""The portable candidate check verifies reviewed bytes before executing them."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tarfile

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify_npm_candidate.py"
spec = importlib.util.spec_from_file_location("verify_npm_candidate_checks", SCRIPT)
candidate_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate_check)


def packed_candidate(path, *, linked_manifest=False):
    files = {
        "npm-release-manifest.json": {"package": "@rqzhu-aide/model-forge-codex", "version": "1.2.3",
                                      "release_id": "npm-1.2.3-abcdef0123456789"},
        "package.json": {"name": "@rqzhu-aide/model-forge-codex", "version": "1.2.3"},
        "contracts/catalog-pin.json": {"catalog_version": "4.5.6"},
        "web/dist/index.html": "<html>Reviewed interface</html>",
    }
    with tarfile.open(path, "w:gz") as archive:
        for name, value in files.items():
            contents = (value if isinstance(value, str) else json.dumps(value)).encode()
            member = tarfile.TarInfo("package/" + name)
            if linked_manifest and name == "npm-release-manifest.json":
                member.type = tarfile.SYMTYPE
                member.linkname = "../../outside.json"
                archive.addfile(member)
            else:
                member.size = len(contents)
                archive.addfile(member, io.BytesIO(contents))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_checksum_mismatch_does_not_read_archive_or_resolve_or_launch_runtimes(tmp_path, monkeypatch, capsys):
    tarball = tmp_path / "candidate.tgz"
    tarball.write_bytes(b"not even a tar archive")
    monkeypatch.setattr(candidate_check.tarfile, "open", lambda *a, **kw: pytest.fail("must verify SHA before reading archive"))
    monkeypatch.setattr(candidate_check, "shared_node_npm", lambda *a: pytest.fail("must verify SHA before using runtimes"))
    monkeypatch.setattr(candidate_check.subprocess, "Popen", lambda *a, **kw: pytest.fail("must not launch mismatched bytes"))
    assert candidate_check.main([str(tarball), "--sha256", "0" * 64]) == 1
    assert "SHA-256 mismatch" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == [tarball]


def test_portable_copy_reads_only_verified_archive_metadata_without_extraction(tmp_path, monkeypatch):
    copied = tmp_path / "verify_npm_candidate.py"
    copied.write_bytes(SCRIPT.read_bytes())
    portable_spec = importlib.util.spec_from_file_location("standalone_candidate_check", copied)
    portable = importlib.util.module_from_spec(portable_spec)
    portable_spec.loader.exec_module(portable)
    tarball = tmp_path / "candidate.tgz"
    digest = packed_candidate(tarball)
    monkeypatch.setattr(tarfile.TarFile, "extract", lambda *a, **kw: pytest.fail("must not extract"))
    monkeypatch.setattr(tarfile.TarFile, "extractall", lambda *a, **kw: pytest.fail("must not extract"))
    checked = portable.read_candidate(tarball, digest.upper())
    assert checked == {"sha256": digest, "version": "1.2.3", "release_id": "npm-1.2.3-abcdef0123456789",
                       "catalog": "4.5.6", "html": b"<html>Reviewed interface</html>"}
    digest = packed_candidate(tarball, linked_manifest=True)
    with pytest.raises(ValueError, match="non-file"):
        portable.read_candidate(tarball, digest)


def test_failed_ui_check_stops_owned_instance_and_retains_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setattr(candidate_check.tempfile, "mkdtemp", lambda **kw: str(tmp_path))
    data = tmp_path / "researcher's data"
    running = {"value": True}
    launched = SimpleNamespace(poll=lambda: None if running["value"] else 0)
    state = {"stopping": False, "release_id": "reviewed", "catalog_version": "4.5.6", "simulated": False,
             "app_root": str(Path.home() / ".model-forge-codex-app/releases/reviewed")}
    monkeypatch.setattr(candidate_check, "test_status", lambda *a: state if running["value"] else None)
    monkeypatch.setattr(candidate_check.subprocess, "Popen", lambda *a, **kw: launched)
    monkeypatch.setattr(candidate_check, "http_get", lambda *a: b"Unexpected interface")
    seen = []

    def stop(command, **options):
        seen.append(command)
        running["value"] = False
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(candidate_check.subprocess, "run", stop)
    with pytest.raises(RuntimeError, match="served interface differs"):
        candidate_check.verify(tmp_path / "candidate.tgz",
                               {"release_id": "reviewed", "catalog": "4.5.6", "html": b"Reviewed interface"},
                               tmp_path / "node", tmp_path / "npm-cli.js")
    assert len(seen) == 1 and seen[0][-1] == "stop"
    assert "./researcher's data" in seen[0]
    assert not running["value"]
    assert (tmp_path / "launcher.log").is_file()
    assert (data / "providers.toml").read_bytes() == b"# Disposable verification settings.\n"


def test_cleanup_never_stops_another_instance(tmp_path, monkeypatch):
    state = {"application": "model-forge-codex", "data_root": str(tmp_path / "unrelated research")}
    monkeypatch.setattr(candidate_check, "http_get", lambda *a: json.dumps(state).encode())
    monkeypatch.setattr(candidate_check.subprocess, "run", lambda *a, **kw: pytest.fail("must leave unrelated instance running"))
    with pytest.raises(RuntimeError, match="another instance"):
        candidate_check.stop_test(SimpleNamespace(poll=lambda: None), ["npm", "exec"], {}, 18766, tmp_path / "test data")
