"""Keep running applications independent of npm's replaceable download cache."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile

PACKAGE = "@rqzhu-aide/model-forge-codex"
MANIFEST = "npm-release-manifest.json"


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_manifest(source: Path) -> dict:
    manifest = json.loads((source / MANIFEST).read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("package") != PACKAGE:
        raise ValueError("This is not a recognized Model Forge npm release.")
    version, files = manifest.get("version"), manifest.get("files")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?", version):
        raise ValueError("The npm release version is invalid.")
    if not isinstance(files, dict) or not files:
        raise ValueError("The npm release has no file inventory.")
    for relative, digest in files.items():
        path = PurePosixPath(relative)
        if (not relative or path.is_absolute() or ".." in path.parts or "\\" in relative
                or ":" in relative or str(path) != relative or relative in {MANIFEST, "local-release.json"}
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("The npm release contains an invalid file entry.")
    identity = {"package": PACKAGE, "version": version, "files": dict(sorted(files.items()))}
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    if manifest.get("release_id") != f"npm-{version}-{digest[:16]}":
        raise ValueError("The npm release identity does not match its file inventory.")
    required = {"scripts/npm_launcher.py", "scripts/npm_snapshot.py", "scripts/validate_local_install.py",
                "src/model_forge_codex/local_app.py", "contracts/catalog-pin.json", "web/dist/index.html",
                "web/runtime/validate-math.mjs", "web/runtime/export-report.mjs"}
    if not required.issubset(files):
        raise ValueError("The npm release is incomplete. Rebuild it before publishing.")
    return manifest


def verify_files(directory: Path, files: dict) -> None:
    for relative, expected in files.items():
        target = directory / relative
        if (not target.resolve().is_relative_to(directory.resolve()) or target.is_symlink()
                or not target.is_file() or file_digest(target) != expected):
            raise ValueError(f"Release file is missing or changed: {relative}. Download the release again.")


def snapshot_release(source: Path, releases: Path | None = None) -> Path:
    source = source.resolve()
    manifest = read_manifest(source)
    releases = (releases or Path.home() / ".model-forge-codex-app" / "releases").resolve()
    target = releases / manifest["release_id"]
    if target.resolve().parent != releases:
        raise ValueError("The release destination is outside the app directory.")
    if target.exists():
        verify_files(target, manifest["files"])
        metadata = json.loads((target / "local-release.json").read_text(encoding="utf-8"))
        if metadata.get("release_id") != manifest["release_id"]:
            raise ValueError("The saved application release has changed. Download the release again.")
        return target
    verify_files(source, manifest["files"])
    releases.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=releases)).resolve()
    try:
        for relative in manifest["files"]:
            output = staging / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, output)
        # Verify the bytes we copied, in case npm updated its cache during copy.
        verify_files(staging, manifest["files"])
        (staging / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
        catalog = json.loads((staging / "contracts/catalog-pin.json").read_text(encoding="utf-8"))
        (staging / "local-release.json").write_text(json.dumps({
            "release_id": manifest["release_id"], "package_version": manifest["version"],
            "catalog_version": catalog["catalog_version"],
        }), encoding="utf-8")
        if staging.parent != releases or target.resolve().parent != releases:
            raise ValueError("The staged release is outside the app directory.")
        try:
            staging.rename(target)
        except OSError:
            if not target.is_dir():
                raise
            verify_files(target, manifest["files"])
        return target
    finally:
        if staging.exists() and staging.resolve().parent == releases:
            shutil.rmtree(staging)
