"""Explicit catalog adoption without rewriting scientific history."""
from __future__ import annotations

from pathlib import Path
import os
import re
import shutil
import stat
import uuid

from .instance_lock import catalog_access
from .storage import read_json, sha256_file, write_json_atomic


_RECEIPT = "catalog-upgrade.json"
_TOKEN = re.compile(r"[0-9a-f]{32}")


def _version_parts(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", value):
        return ()
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return ()


def _inside_project(project_dir, *paths):
    root = project_dir.resolve()
    for path in (project_dir, *paths):
        try:
            info = path.lstat()
        except FileNotFoundError:
            info = None
        # st_file_attributes also recognizes Windows junctions on Python 3.11.
        linked = info is not None and (stat.S_ISLNK(info.st_mode)
                 or bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT))
        if linked or not path.resolve().is_relative_to(root):
            raise ValueError("Catalog destination is outside the selected project or is linked")


def _verified_catalog(path):
    from .catalog import Catalog
    try:
        catalog = Catalog(path, _project_access=False)
        if not _version_parts(catalog.version) or any(f.blocks_publication for f in catalog.verify_manifest()):
            raise ValueError("Invalid catalog version or manifest")
        return catalog
    except Exception as exc:
        raise ValueError("The workflow catalog failed integrity verification; no catalog was replaced.") from exc


def _discard_preparation(project_dir, staged, expected_pin=None):
    """Best-effort cleanup of this operation's exact disposable directory."""
    try:
        _inside_project(project_dir, staged)
        if not _TOKEN.fullmatch(staged.name.removeprefix("catalog-update-")):
            return
        if staged.is_dir():
            if expected_pin is not None:
                _verified_catalog(staged)
                if sha256_file(staged / "catalog-pin.json") != expected_pin:
                    return
            shutil.rmtree(staged)
    except (OSError, ValueError):
        pass  # A cleanup failure cannot make a restored catalog unavailable.


def recover_catalog_upgrade(project_dir: Path) -> None:
    """Restore an interrupted swap, or finish a committed swap's context setup.

    A present catalog is never replaced by recovery. Before receipts existed,
    the two renamed directories' shared token is sufficient only when exactly
    one such pair remains. Unpaired preparation copies are not adoption intent.
    """
    project_dir = Path(project_dir)
    if os.environ.get("MF_CODEX_READ_ONLY") == "1" or not (project_dir / "project.json").is_file():
        return
    current = project_dir / "contracts"
    receipt_path = project_dir / _RECEIPT
    if current.exists() and not receipt_path.exists():
        return
    with catalog_access(project_dir):
        _inside_project(project_dir, current, receipt_path, receipt_path.with_name(_RECEIPT + ".tmp"))
        receipt = read_json(receipt_path)
        if receipt_path.exists():
            if (not isinstance(receipt, dict) or not _TOKEN.fullmatch(str(receipt.get("token", "")))
                    or not _version_parts(receipt.get("previous_version"))
                    or any(not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get(key, "")))
                           for key in ("previous_pin_sha256", "offered_pin_sha256"))):
                if current.exists():
                    return  # Recovery evidence cannot supersede a present pin.
                raise ValueError("The interrupted workflow update record is unreadable; its catalogs were retained.")
        if current.exists():
            if receipt:
                pin_digest = sha256_file(current / "catalog-pin.json")
                if pin_digest == receipt["offered_pin_sha256"]:
                    _verified_catalog(current)
                    from .problem_context import supports_problem_context, initialize_problem_context
                    if supports_problem_context(project_dir):
                        context_path = project_dir / "researcher" / "problem_context.json"
                        _inside_project(project_dir, context_path.parent, context_path,
                                        context_path.with_name("problem_context.json.tmp"))
                        initialize_problem_context(project_dir)
                    receipt_path.unlink()
                elif pin_digest == receipt["previous_pin_sha256"]:
                    _verified_catalog(current)
                    _discard_preparation(project_dir, project_dir / ("catalog-update-" + receipt["token"]),
                                         receipt["offered_pin_sha256"])
                    receipt_path.unlink()
                # An unrelated current pin wins over stale recovery evidence.
            return
        history = project_dir / "catalog-history"
        _inside_project(project_dir, history)
        if receipt:
            archived = history / (receipt["previous_version"] + "-" + receipt["token"])
        else:
            pairs = []
            for staged in project_dir.glob("catalog-update-*"):
                token = staged.name.removeprefix("catalog-update-")
                if not _TOKEN.fullmatch(token):
                    continue
                for candidate in history.glob("*-" + token):
                    if _version_parts(candidate.name[:-(len(token) + 1)]):
                        _inside_project(project_dir, staged, candidate)
                        pairs.append(candidate)
            if not pairs:
                return
            if len(pairs) != 1:
                raise ValueError("Several interrupted workflow updates remain; their catalogs were retained for inspection.")
            archived = pairs[0]
        _inside_project(project_dir, archived)
        catalog = _verified_catalog(archived)
        if archived.name != catalog.version + "-" + archived.name.rsplit("-", 1)[-1]:
            raise ValueError("The interrupted workflow archive does not match its recorded version.")
        if receipt and sha256_file(archived / "catalog-pin.json") != receipt["previous_pin_sha256"]:
            raise ValueError("The interrupted workflow archive does not match its update record.")
        os.replace(archived, current)
        if receipt:
            _discard_preparation(project_dir, project_dir / ("catalog-update-" + receipt["token"]),
                                 receipt["offered_pin_sha256"])
            receipt_path.unlink()


def _preview(project_dir, bundled_root):
    current = read_json(project_dir / "contracts" / "catalog-pin.json") or {}
    available = read_json(bundled_root / "catalog-pin.json") or {}
    current = current if isinstance(current, dict) else {}
    available = available if isinstance(available, dict) else {}
    version = current.get("catalog_version", "unknown")
    offered = available.get("catalog_version", "unknown")
    blocked_runs = [{"run_id": record.get("run_id"), "state": record.get("state")}
                    for path in (project_dir / "runs").glob("*/run.json")
                    if (record := read_json(path) or {}).get("state") not in ("published", "assessed", "failed", "cancelled")]
    return {"version": version, "available_version": offered,
            "blocked_runs": blocked_runs,
            "can_adopt": not blocked_runs,
            "upgrade_available": bool(_version_parts(offered) and _version_parts(offered) > _version_parts(version)),
            "history_policy": "Existing scientific generations and old run catalogs are retained."}


def preview_catalog_upgrade(project_dir: Path, bundled_root: Path) -> dict:
    with catalog_access(project_dir):
        recover_catalog_upgrade(project_dir)
        return _preview(project_dir, bundled_root)


def upgrade_catalog(project_dir: Path, bundled_root: Path) -> dict:
    if os.environ.get("MF_CODEX_READ_ONLY") == "1":
        raise ValueError("This viewer is read-only.")
    with catalog_access(project_dir):
        recover_catalog_upgrade(project_dir)
        preview = _preview(project_dir, bundled_root)
        if not _version_parts(preview["available_version"]):
            raise ValueError("The offered workflow catalog failed integrity verification; its version is invalid.")
        if not _version_parts(preview["version"]):
            raise ValueError("The existing workflow catalog failed integrity verification; its version is invalid.")
        if not preview["upgrade_available"]:
            return preview
        if preview["blocked_runs"]:
            raise ValueError("Finish or cancel active or paused runs before adopting the model-development workflow.")
        token = uuid.uuid4().hex
        current = project_dir / "contracts"
        staged = project_dir / ("catalog-update-" + token)
        archived = project_dir / "catalog-history" / (preview["version"] + "-" + token)
        receipt_path = project_dir / _RECEIPT
        _inside_project(project_dir, current, staged, archived, archived.parent,
                        receipt_path, receipt_path.with_name(_RECEIPT + ".tmp"))
        _verified_catalog(current)
        offered = _verified_catalog(bundled_root)
        offered_pin = sha256_file(bundled_root / "catalog-pin.json")
        offered_snapshot = offered.snapshot_sha256
        staged.mkdir()  # Only a staging area created by this attempt can be cleaned up below.
        try:
            shutil.copytree(bundled_root, staged, dirs_exist_ok=True)
            prepared = _verified_catalog(staged)
            if (prepared.version != preview["available_version"] or prepared.snapshot_sha256 != offered_snapshot
                    or sha256_file(staged / "catalog-pin.json") != offered_pin):
                raise ValueError("The offered workflow catalog changed during preparation; the existing catalog is unchanged.")
            archived.parent.mkdir(parents=True, exist_ok=True)
            write_json_atomic(receipt_path, {"token": token, "previous_version": preview["version"],
                "previous_pin_sha256": sha256_file(current / "catalog-pin.json"), "offered_pin_sha256": offered_pin})
        except Exception:
            _discard_preparation(project_dir, staged)
            raise
        try:
            os.replace(current, archived)
            os.replace(staged, current)
        except OSError:
            # Preserve the original I/O error. If rollback also fails, ordinary
            # access/restart uses the same durable receipt to retry recovery.
            try:
                recover_catalog_upgrade(project_dir)
            except (OSError, ValueError):
                pass
            raise
        recover_catalog_upgrade(project_dir)
        return {**_preview(project_dir, bundled_root), "previous_catalog": str(archived.relative_to(project_dir))}
