"""Browse + activity queries (design/07, build-plan Phase C).

Read-only projectors over the data root: branches, phase stores, record
bodies, journal, receipts, member memory surfaces, correction previews,
and the SSE activity stream. Nothing here mutates state. Identifiers that
become path segments are whitelisted (belt-and-braces; the HTTP layer
already rejects encoded slashes).
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from .domain import TERMINAL_STATES, MemberRole
from .storage import read_json, read_jsonl
from .records import current_records, read_generation
from .run_progress import project_run_progress

_IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _check_ident(*values: str) -> None:
    for v in values:
        if not _IDENT.fullmatch(v):
            raise ValueError(f"invalid identifier {v!r}")


def list_runs(project_dir: Path) -> list[dict]:
    """Run summaries, newest first (design/07 run table)."""
    runs_dir = project_dir / "runs"
    if not runs_dir.is_dir():
        return []
    out = []
    for run_dir in runs_dir.iterdir():
        doc = read_json(run_dir / "run.json")
        if not doc:
            continue
        out.append(
            {
                "run_id": doc["run_id"],
                "phase": doc["phase"],
                "mode": doc["mode"],
                "branch_id": doc["branch_id"],
                "state": doc["state"],
                "stage_states": doc.get("stage_states", {}),
                "correction_attempts": doc.get("correction_attempts", 0),
                "usage": doc.get("usage", {}),
                "created_at": doc.get("created_at", ""),
                "updated_at": doc.get("updated_at", ""),
                "intent": doc.get("intent", "run"),
                "target": doc.get("target"),
                "assessment_id": doc.get("assessment_id"),
                "assessment_purpose": doc.get("assessment_purpose", "assessment"),
                "terminal_reason": doc.get("terminal_reason"),
                "progress": project_run_progress(run_dir, doc),
            }
        )
    _annotate_run_statuses(project_dir, runs_dir, out)
    return sorted(out, key=lambda r: r["created_at"], reverse=True)


def _annotate_run_statuses(project_dir: Path, runs_dir: Path, summaries: list[dict]) -> None:
    """Derived freshness for published method-phase runs; never changes state."""
    catalog = None
    for summary in summaries:
        if summary.get("state") != "published" or summary.get("phase") not in ("P3", "P4", "P5"):
            continue
        if not summary.get("branch_id") or summary["branch_id"] == "trunk":
            continue
        from .methods import _catalog_methods, output_method_status
        if catalog is None:
            catalog = _catalog_methods(project_dir)
        basis = read_json(runs_dir / summary["run_id"] / "basis.json") or {}
        summary["method_status"] = output_method_status(project_dir, basis.get("method"), catalog=catalog)


def list_branches(project_dir: Path) -> list[dict]:
    out = []
    branches_dir = project_dir / "branches"
    if not branches_dir.is_dir():
        return out
    for branch_dir in sorted(p for p in branches_dir.iterdir() if p.is_dir()):
        phases = {}
        phases_dir = branch_dir / "phases"
        if phases_dir.is_dir():
            for phase_dir in sorted(p for p in phases_dir.iterdir() if p.is_dir()):
                families = list(current_records(phase_dir))
                if families:
                    phases[phase_dir.name] = sorted(families)
        threads = read_json(branch_dir / "threads.json") or {}
        out.append(
            {
                "branch_id": branch_dir.name,
                "phases": phases,  # phase -> published record families
                "threads": {
                    k: {"thread_id": v["thread_id"], "turns": v.get("turns", 0),
                        "archived": v.get("archived", False)}
                    for k, v in threads.items()
                },
            }
        )
    from .methods import get_method
    for item in out:
        method = get_method(project_dir, item["branch_id"])
        if method:
            item["method"] = {key: value for key, value in method.items() if key != "definition"}
    return out


def list_records(project_dir: Path, branch_id: str, phase: str) -> list[dict]:
    _check_ident(branch_id, phase)
    store = project_dir / "branches" / branch_id / "phases" / phase.lower()
    if not store.is_dir():
        return []
    out = []
    current = current_records(store)
    for family in sorted(p for p in store.iterdir() if p.is_dir()):
        if family.name == "packages":
            continue
        gens_dir = family / "generations"
        generations = sorted(
            (g.stem for g in gens_dir.glob("*.json*")),
        ) if gens_dir.is_dir() else []
        out.append(
            {
                "family": family.name,
                "generations": generations,
                "current": current.get(family.name),
            }
        )
    return out


def get_record(
    project_dir: Path, branch_id: str, phase: str, family: str, generation_id: str
) -> dict | None:
    _check_ident(branch_id, phase, family, generation_id)
    phase_dir = project_dir / "branches" / branch_id / "phases" / phase.lower()
    current = current_records(phase_dir).get(family)
    if current and current.get("generation_id") == generation_id:
        return read_generation(phase_dir, family, current)
    for package_path in (phase_dir / "packages").glob("*.json"):
        package = read_json(package_path) or {}
        pointer = package.get("records", {}).get(family)
        if pointer and pointer.get("generation_id") == generation_id:
            return read_generation(phase_dir, family, pointer)
    # Unreferenced legacy history is still readable as raw historical data.
    # It is never substituted for a missing current generation or an action basis.
    return read_json(phase_dir / family / "generations" / f"{generation_id}.json")


def journal(project_dir: Path) -> list[dict]:
    events, _ = read_jsonl(project_dir / "authority" / "journal.jsonl")
    return events


def receipts(project_dir: Path) -> list[dict]:
    receipts_dir = project_dir / "authority" / "receipts"
    if not receipts_dir.is_dir():
        return []
    out = []
    for path in sorted(receipts_dir.glob("*.json")):
        doc = read_json(path)
        if doc:
            if doc.get("package_id"):
                from .records import package_committed
                phase_dir = project_dir / "branches" / doc["branch_id"] / "phases" / doc["phase"].lower()
                if not package_committed(phase_dir, doc["package_id"]):
                    continue
            out.append(doc)
    return out


def member_memory(project_dir: Path, role: str, kind: str) -> str:
    """kind: 'research' | 'publishable' (design/04 §6)."""
    if kind not in ("research", "publishable"):
        raise ValueError("unknown memory kind")
    try:
        MemberRole(role)
    except ValueError:
        raise ValueError(f"unknown role {role}") from None
    path = project_dir / "members" / role / "codex-home" / f"{kind}_memory.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def append_member_memory(project_dir: Path, role: str, kind: str, text: str) -> None:
    if kind not in ("research", "publishable"):
        raise ValueError("unknown memory kind")
    try:
        MemberRole(role)
    except ValueError:
        raise ValueError(f"unknown role {role}") from None
    path = project_dir / "members" / role / "codex-home" / f"{kind}_memory.md"
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {stamp}\n\n{text.strip()}\n")


def correction_preview(project_dir: Path, run_dir: Path, record_doc: dict) -> dict:
    """What the researcher sees before authorizing a correction (C4):
    the latest findings, the affected stage outputs, and their sealed
    digests (design/02 §5)."""
    history = record_doc.get("findings_history") or []
    latest = history[-1] if history else []
    frozen_plan = read_json(run_dir / "stage-plan.json") or []
    stages = frozen_plan.get("stages", []) if isinstance(frozen_plan, dict) else frozen_plan
    owners = {output: stage["stage_id"] for stage in stages if isinstance(stage, dict) and stage.get("stage_id")
              for output in stage.get("writes", [])}
    affected: dict[str, list[str]] = {}
    for finding in latest:
        output_id = str(finding.get("object_id", ""))
        stage = owners.get(output_id, output_id)
        affected.setdefault(stage, [])
        ptr = finding.get("json_pointer") or ""
        if ptr and ptr not in affected[stage]:
            affected[stage].append(ptr)
    seals = {}
    outputs_dir = run_dir / "outputs"
    if outputs_dir.is_dir():
        for stage_dir in sorted(p for p in outputs_dir.iterdir() if p.is_dir()):
            seal = read_json(stage_dir / "seal.json")
            if seal:
                seals[stage_dir.name] = seal.get("outputs", {})
    return {
        "run_id": record_doc.get("run_id"),
        "correction_attempts": record_doc.get("correction_attempts", 0),
        "attempts_remaining": max(0, 1 - int(record_doc.get("correction_attempts", 0))),
        "eligible": record_doc.get("state") == "failed" and bool(latest) and int(record_doc.get("correction_attempts", 0)) < 1,
        "findings": latest,
        "affected_stages": affected,
        "sealed_outputs": seals,
    }


async def stream_activity(run_dir: Path, state_reader, poll: float = 1.5, *, stop_requested=None) -> AsyncIterator[str]:
    """SSE stream of the run's event journal: replay then follow until the
    run reaches a terminal state (then one final drain + close)."""
    path = run_dir / "events.jsonl"
    sent = 0
    while True:
        events, _ = read_jsonl(path)
        for event in events[sent:]:
            sent += 1
            yield f"data: {json.dumps(event)}\n\n"
        state = state_reader()
        if state in {s.value for s in TERMINAL_STATES} | {"awaiting_user"}:
            # final drain, then goodbye
            events, _ = read_jsonl(path)
            for event in events[sent:]:
                yield f"data: {json.dumps(event)}\n\n"
            yield f"data: {json.dumps({'type': 'stream.closed', 'state': state})}\n\n"
            return
        if stop_requested is not None and stop_requested():
            # Let Uvicorn drain this response before lifespan cleanup stops
            # owned runs. Closing a stream does not make its run terminal.
            yield f"data: {json.dumps({'type': 'stream.closed', 'state': state, 'reason': 'service_stopping'})}\n\n"
            return
        await asyncio.sleep(poll)
