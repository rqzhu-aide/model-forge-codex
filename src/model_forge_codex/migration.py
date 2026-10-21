"""Explicit catalog adoption without rewriting scientific history."""
from __future__ import annotations

from pathlib import Path
import os
import shutil
import uuid

from .storage import read_json


def preview_catalog_upgrade(project_dir: Path, bundled_root: Path) -> dict:
    current = read_json(project_dir / "contracts" / "catalog-pin.json") or {}
    available = read_json(bundled_root / "catalog-pin.json") or {}
    version = current.get("catalog_version", "unknown")
    offered = available.get("catalog_version", "unknown")
    def parts(value):
        try:
            return tuple(int(part) for part in value.split("."))
        except ValueError:
            return ()
    blocked_runs = [{"run_id": record.get("run_id"), "state": record.get("state")}
                    for path in (project_dir / "runs").glob("*/run.json")
                    if (record := read_json(path) or {}).get("state") not in ("published", "assessed", "failed", "cancelled")]
    return {"version": version, "available_version": offered,
            "blocked_runs": blocked_runs,
            "can_adopt": not blocked_runs,
            "upgrade_available": bool(parts(offered) and parts(offered) > parts(version)),
            "history_policy": "Existing scientific generations and old run catalogs are retained."}


def upgrade_catalog(project_dir: Path, bundled_root: Path) -> dict:
    preview = preview_catalog_upgrade(project_dir, bundled_root)
    if not preview["upgrade_available"]:
        return preview
    for path in (project_dir / "runs").glob("*/run.json"):
        record = read_json(path) or {}
        if record.get("state") not in ("published", "assessed", "failed", "cancelled"):
            raise ValueError("Finish or cancel active or paused runs before adopting the model-development workflow.")
    token = uuid.uuid4().hex
    current = project_dir / "contracts"
    staged = project_dir / ("catalog-update-" + token)
    archived = project_dir / "catalog-history" / (preview["version"] + "-" + token)
    # Every move remains inside this explicitly selected project.
    for target in (current, staged, archived):
        if not target.resolve().is_relative_to(project_dir.resolve()):
            raise ValueError("Catalog destination is outside the selected project")
    if current.is_symlink():
        raise ValueError("Cannot upgrade a linked catalog directory")
    from .catalog import Catalog
    try:
        catalog = Catalog(bundled_root)
    except Exception as exc:
        raise ValueError("The offered workflow catalog failed integrity verification; its schema definitions could not be loaded.") from exc
    findings = catalog.verify_manifest()
    if any(finding.blocks_publication for finding in findings):
        raise ValueError("The offered workflow catalog failed integrity verification; the existing catalog is unchanged.")
    shutil.copytree(bundled_root, staged)
    archived.parent.mkdir(parents=True, exist_ok=True)
    os.replace(current, archived)
    try:
        os.replace(staged, current)
    except OSError:
        os.replace(archived, current)
        raise
    from .problem_context import supports_problem_context, initialize_problem_context
    if supports_problem_context(project_dir):
        initialize_problem_context(project_dir)
    return {**preview_catalog_upgrade(project_dir, bundled_root), "previous_catalog": str(archived.relative_to(project_dir))}
