"""Read-only progress from frozen stages, collected outputs and execution records.

Delivery receipts describe work received. Only the run's recorded stage state
establishes acceptance; neither a completed turn nor an output seal does so.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .storage import read_json

ROLE_LABELS = {"research_lead": "Research Lead", "theorist": "Theorist",
               "data_analyst": "Data Analyst", "outside_reviewer": "Outside Reviewer"}
STAGE_LABELS = {
    "p1.discovery": "Member literature searches", "p1.lead_synthesis": "Lead synthesis",
    "p2.independent_proposals": "Three method proposals", "p2.cross_review": "Specialist cross-reviews",
    "p2.lead_reconciliation": "Lead comparison", "p2.supplied_method_proposals": "Three method proposals",
    "p2.supplied_method_reviews": "Specialist cross-reviews", "p2.supplied_method_reconciliation": "Lead comparison",
    "p3.theorist": "Theory development", "p3.analyst": "Analyst audit", "p3.lead": "Lead synthesis",
    "p3.assessment": "Component assessment", "p4.analyst": "Protocol and empirical work",
    "p4.theorist": "Theorist audit", "p4.lead": "Lead interpretation",
    "p5.assembly_lead": "Technical report assembly", "p5.parallel_reviews": "Independent report reviews",
    "p5.revision_lead": "Lead revision",
}
PUBLICATION_LABELS = {"P1": "Literature update published", "P2": "Methods published",
                      "P3": "Theory account published", "P4": "Evaluation published",
                      "P5": "Technical report published"}
_ROLE_ALIASES = {"research_lead": ("lead",), "theorist": ("theory", "theorist"),
                 "data_analyst": ("empirical", "analyst", "data"), "outside_reviewer": ("review",)}
_IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_WORK_PURPOSES = {"scientific", "isolated", "mechanical_repair"}


def _optional_json(path: Path):
    try:
        return read_json(path)
    except UnicodeError:
        return None


def _optional_object(path: Path) -> dict:
    doc = _optional_json(path)
    if doc is None and not path.is_file():
        return {}
    if not isinstance(doc, dict):
        raise ValueError("Optional progress detail is unreadable")
    return doc


def _strings(value) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("Optional progress list is unreadable")
    return value


def _time(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _not_before(left, right) -> bool:
    a, b = _time(left), _time(right)
    try:
        return a is not None and b is not None and a >= b
    except TypeError:
        return False


def _owned(stage: dict, role: str) -> list[str]:
    writes = _strings(stage.get("writes", []))
    return writes if len(stage.get("roles", [])) == 1 else [item for item in writes
        if any(alias in item.split(".", 1)[-1] for alias in _ROLE_ALIASES.get(role, ()))]


def _repair_pending(run_dir: Path, run: dict, stage: dict, role: str, seal: dict, latest: dict | None) -> bool:
    """A saved repair request reopens its owner even before its next turn starts."""
    if run.get("stage_states", {}).get(stage["stage_id"]) != "correcting":
        return False
    scope = set(_strings(run.get("correction_scope") or []))
    attempt = (run.get("mechanical_repair_attempts") or {}).get(stage["stage_id"])
    if isinstance(attempt, int) and attempt > 0:
        archive = run_dir / "mechanical-repairs" / stage["stage_id"] / f"attempt-{attempt}"
        findings = _optional_object(archive / "findings.json")
        if "scope" not in findings:
            raise ValueError("Recorded repair scope is unavailable")
        scope.update(_strings(findings["scope"]))
        prior = _optional_object(archive / "outputs" / "seals" / f"{role}.json")
        if set(_owned(stage, role)).intersection(scope):
            return not seal or seal.get("sealed_at") == prior.get("sealed_at")
    if not set(_owned(stage, role)).intersection(scope):
        return False
    return not (latest and latest.get("correction_attempt", 0) >= run.get("correction_attempts", 0)
                and latest.get("state") == "completed" and _not_before(seal.get("sealed_at"), latest.get("finished_at")))


def _stage_members(run_dir: Path, run_doc: dict, stage: dict, execution: list[dict]) -> list[dict]:
    stage_id = stage["stage_id"]
    stage_state = run_doc.get("stage_states", {}).get(stage_id, "pending")
    roles = _strings(stage.get("roles", []))
    if any(not _IDENT.fullmatch(role) for role in roles):
        raise ValueError("Recorded member identity is unreadable")
    _strings(stage.get("writes", []))
    observations = []
    for role in roles:
        turns = [entry for entry in execution if entry.get("stage_id") == stage_id and entry.get("role") == role]
        latest = max(turns, key=lambda entry: (str(entry.get("started_at", "")), str(entry.get("execution_id", ""))), default=None)
        seal = _optional_object(run_dir / "outputs" / stage_id / "seals" / f"{role}.json")
        if seal and (seal.get("stage_id") != stage_id or seal.get("role") != role or not isinstance(seal.get("outputs"), dict)):
            raise ValueError("Recorded member seal is unreadable")
        has_receipt = bool(seal.get("outputs"))
        if has_receipt and _time(seal.get("sealed_at")) is None:
            raise ValueError("Recorded member seal date is unavailable")
        if latest:
            # Collection follows a successful model turn. An earlier seal
            # remains historical while a correction or continuation works.
            has_receipt = has_receipt and latest.get("state") == "completed" and _not_before(seal.get("sealed_at"), latest.get("finished_at"))
        reopened = _repair_pending(run_dir, run_doc, stage, role, seal, latest)
        received = has_receipt and stage_state != "pending" and not reopened
        accepted = stage_state == "succeeded"
        member_state = ("accepted" if accepted else "correcting" if reopened else "received" if received
                        else latest.get("state", "pending") if latest else "pending")
        if member_state == "completed":
            member_state = "collecting"
        if latest and latest.get("purpose") == "mechanical_repair" and member_state == "running":
            member_state = "correcting"
        if run_doc.get("state") in {"failed", "cancelled"} and member_state in {"running", "correcting", "collecting"}:
            member_state = run_doc["state"]
        if stage_state == "awaiting_user" and member_state in {"running", "collecting", "pending"}:
            member_state = "awaiting_user"
        observations.append({"role": role, "label": ROLE_LABELS.get(role, role.replace("_", " ").title()),
                             "state": member_state, "received": received, "accepted": accepted,
                             "detail_available": bool(latest or seal)})
    return observations


def _repair_status(run_dir: Path, run_doc: dict, stage_id: str, state: str) -> dict | None:
    attempt = (run_doc.get("mechanical_repair_attempts") or {}).get(stage_id)
    if type(attempt) is not int or attempt <= 0:
        return None
    if state == "correcting" and run_doc.get("state") != "correcting":
        return {"attempt": attempt, "state": "working",
                "message": f"Correcting saved artifacts, attempt {attempt}."}
    if state == "succeeded":
        return {"attempt": attempt, "state": "accepted", "message": "Saved artifacts were accepted after repair."}
    if state not in {"failed", "cancelled"}:
        return None
    try:
        result = _optional_object(run_dir / "mechanical-repairs" / stage_id / f"attempt-{attempt}" / "result.json")
    except (OSError, ValueError):
        result = {}
    unchanged = result.get("unchanged") is True and bool(result.get("remaining_findings") or result.get("new_findings"))
    message = ("Automatic repair stopped because the same issue remained. Review the findings before requesting correction."
               if unchanged else "Repair did not complete. Review the findings and recorded activity." if not result
               else "Automatic repair ended with unresolved findings. Review them before requesting correction.")
    if state == "cancelled":
        message = "Repair was cancelled. Saved work remains available for inspection."
    return {"attempt": attempt, "state": "stopped", "message": message}


def project_run_progress(run_dir: Path, run_doc: dict) -> dict:
    """Project a run without writing state or relying on the recent event tail.

    Frozen stage plans and recorded stage states remain readable when older
    runs lack role executions or seals. Such runs receive no inferred counts.
    The projection includes no provider settings, credentials or workspace paths.
    """
    frozen = _optional_json(run_dir / "stage-plan.json")
    plan = frozen.get("stages", []) if isinstance(frozen, dict) else frozen
    plan = [stage for stage in plan if isinstance(stage, dict)] if isinstance(plan, list) else []
    execution, execution_unavailable = [], False
    for path in (run_dir / "execution").glob("*/execution.json"):
        try:
            entry = _optional_object(path)
            purpose = entry.get("purpose")
            if purpose is not None and not isinstance(purpose, str):
                raise ValueError("Recorded execution purpose is unreadable")
            if purpose not in _WORK_PURPOSES:
                continue
            if any(not isinstance(entry.get(key), str) for key in ("stage_id", "role", "state")) or _time(entry.get("started_at")) is None:
                raise ValueError("Recorded execution detail is unreadable")
            if entry["state"] != "running" and _time(entry.get("finished_at")) is None:
                raise ValueError("Recorded execution completion date is unavailable")
            if type(entry.get("correction_attempt", 0)) is not int:
                raise ValueError("Recorded execution correction detail is unreadable")
            execution.append(entry)
        except ValueError:
            execution_unavailable = True
    state = run_doc.get("state")
    states = run_doc.get("stage_states") or {}
    # A malformed optional plan must not drop states from the run record.
    known_stages = {stage.get("stage_id") for stage in plan if isinstance(stage.get("stage_id"), str)}
    plan.extend({"stage_id": stage_id} for stage_id in states if stage_id not in known_stages)
    stages = []
    for index, stage in sorted(enumerate(plan), key=lambda item: item[1].get("sequence") if type(item[1].get("sequence")) is int else item[0]):
        stage_id = stage.get("stage_id", "")
        if not isinstance(stage_id, str) or not _IDENT.fullmatch(stage_id):
            continue
        stage_state = states.get(stage_id, "pending")
        try:
            if execution_unavailable or "sequence" in stage and type(stage["sequence"]) is not int:
                raise ValueError("Optional member detail is unavailable")
            observations = _stage_members(run_dir, run_doc, stage, execution)
        except (ValueError, TypeError, AttributeError):
            observations = []
        detailed = bool(observations) and any(member["detail_available"] for member in observations)
        # Acceptance survives incomplete historical receipts. A partial count
        # would contradict that recorded outcome and imply missing deliveries.
        if stage_state == "succeeded" and not all(member["received"] for member in observations):
            detailed = False
        stages.append({"stage_id": stage_id, "label": STAGE_LABELS.get(stage_id, stage_id.replace(".", " ").replace("_", " ").title()),
                       "state": stage_state, "parallel": stage.get("execution") == "parallel",
                       "member_detail_available": detailed, "members": observations if detailed else [],
                       "received_accounts": sum(member["received"] for member in observations) if detailed else None,
                       "total_accounts": len(observations) if observations else None})
        repair = _repair_status(run_dir, run_doc, stage_id, stage_state)
        if repair:
            stages[-1]["repair"] = repair
    assessment = run_doc.get("intent") == "assessment"
    publication = {"label": "Assessment saved" if assessment else PUBLICATION_LABELS.get(run_doc.get("phase"), "Update published"),
                   "state": "completed" if state == ("assessed" if assessment else "published") else "checking" if state == "validating" else "pending"}
    return {"run_id": run_doc.get("run_id"), "phase": run_doc.get("phase"), "mode": run_doc.get("mode"),
            "state": state, "stages": stages, "publication": publication}
