"""Exact researcher-selected empirical questions and isolated inspected evidence."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

from .records import ArtifactError, current_records, generation_path, read_generation, source_artifact_path
from .storage import read_json, sha256_file, write_json_atomic


def effective_protocol(protocol: dict) -> dict:
    """Project append-only amendments without rewriting the original design.

    Keep duplicate IDs visible: validation must reject ambiguous additions,
    rather than silently replacing an earlier case, metric or comparison.
    """
    result = deepcopy(protocol)
    additions = {"added_cases": "cases", "added_tests": "claim_tests", "added_work_items": "work_items",
                 "added_metrics": "metrics", "added_baselines": "baselines",
                 "added_decision_thresholds": "decision_thresholds", "added_data_sources": "data_sources"}
    amendments = protocol.get("amendments", [])
    for amendment in amendments if isinstance(amendments, list) else []:
        if not isinstance(amendment, dict):
            continue
        for source, target in additions.items():
            values = amendment.get(source, [])
            if isinstance(values, list) and values and isinstance(result.get(target, []), list):
                result.setdefault(target, []).extend(deepcopy(values))
    return result


def protocol_questions(protocol: dict, reference: dict) -> list[dict]:
    """Derive selectors only from authored tests and their declared cases."""
    protocol = effective_protocol(protocol) if isinstance(protocol, dict) else protocol
    tests = protocol.get("claim_tests", []) if isinstance(protocol, dict) else []
    cases = protocol.get("cases", []) if isinstance(protocol, dict) else []
    if not isinstance(tests, list) or not isinstance(cases, list):
        return []
    if (any(not isinstance(test, dict) or not isinstance(test.get("test_id"), str) or not test["test_id"] for test in tests)
            or any(not isinstance(case, dict) or not isinstance(case.get("case_id"), str)
                   or not isinstance(case.get("test_ids"), list) or any(not isinstance(item, str) for item in case["test_ids"])
                   for case in cases)):
        return []
    test_ids = [test.get("test_id") for test in tests if isinstance(test, dict)]
    case_ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
    if (any(not isinstance(item, str) for item in test_ids + case_ids)
            or len(test_ids) != len(set(test_ids)) or len(case_ids) != len(set(case_ids))):
        return []  # An ambiguous authored identifier cannot identify exact work.
    result = []
    for test in tests:
        if not isinstance(test, dict) or not isinstance(test.get("test_id"), str):
            continue
        test_id = test["test_id"]
        linked_cases = sorted(case["case_id"] for case in cases if isinstance(case, dict)
                              and isinstance(case.get("case_id"), str) and test_id in case.get("test_ids", []))
        statements = test.get("target_statement_ids", [])
        if not isinstance(statements, list) or any(not isinstance(s, str) for s in statements):
            continue
        selectors = {"question_id": test_id, "test_ids": [test_id], "case_ids": linked_cases,
                     "statement_ids": sorted(set(statements))}
        metric_ids = sorted({threshold["metric_id"] for threshold in protocol.get("decision_thresholds", [])
                             if isinstance(threshold, dict) and isinstance(threshold.get("metric_id"), str)
                             and threshold.get("threshold_id") in test.get("decision_threshold_ids", [])})
        target = {key: reference.get(key) for key in
                  ("branch", "phase", "family", "generation_id", "sha256", "run_id", "package_id")}
        target.update(kind="empirical_question", object_id=test_id, **selectors)
        labels = [case.get("label") or case.get("title") or case["case_id"] for case in cases
                  if isinstance(case, dict) and case.get("case_id") in linked_cases]
        result.append({**test, **selectors, "metric_ids": metric_ids, "case_labels": labels,
                       "title": test.get("hypothesis", test_id), "caption": test.get("design", ""),
                       "scope": protocol.get("scope", ""), "followup_target": target})
    return result


def _committed_evaluations(directory: Path):
    """Walk the authoritative ancestry, never an arbitrary prepared manifest."""
    marker = directory / "current-package.json"
    if not marker.exists():
        yield {"records": current_records(directory)}
        return
    package = read_json(marker)
    if not isinstance(package, dict) or not isinstance(package.get("records"), dict):
        raise ArtifactError("The committed evaluation history is malformed")
    seen = set()
    while package:
        identifier = package.get("package_id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", identifier) or identifier in seen:
            raise ArtifactError("The committed evaluation history is malformed")
        seen.add(identifier)
        yield package
        previous = package.get("previous_package_id")
        if not previous:
            # Exact legacy records retained by the first atomic publication.
            prior = package.get("metadata", {}).get("prior_evidence", [])
            records = {ref["family"]: ref for ref in prior if ref.get("phase") == "P4"
                       and ref.get("branch") == package.get("branch_id")}
            if records:
                yield {"records": records}
            return
        if not isinstance(previous, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", previous):
            raise ArtifactError("The committed evaluation history is malformed")
        package = read_json(directory / "packages" / (previous + ".json"))
        if not isinstance(package, dict) or package.get("package_id") != previous:
            raise ArtifactError("An earlier committed evaluation package is unavailable")


def resolve_empirical_target(project_dir: Path, branch: str, target: dict) -> tuple[dict, dict, dict]:
    """Return the canonical selection, question and committed inspected package."""
    if target.get("branch") != branch or target.get("phase") != "P4" or target.get("family") != "protocol" or target.get("kind") != "empirical_question":
        raise ArtifactError("Select an empirical question from this method's exact P4 protocol")
    directory = project_dir / "branches" / branch / "phases" / "p4"
    for package in _committed_evaluations(directory):
        pointer = package.get("records", {}).get("protocol")
        if not pointer or pointer.get("generation_id") != target.get("generation_id"):
            continue
        if package.get("branch_id", branch) != branch or package.get("phase", "P4") != "P4":
            raise ArtifactError("The selected evaluation belongs to another method or phase")
        if package.get("package_id") and (pointer.get("package_id") != package["package_id"] or pointer.get("run_id") != package.get("run_id")):
            raise ArtifactError("The selected protocol does not match its committed evaluation package")
        ref = {"branch": branch, "phase": "P4", "family": "protocol",
               "generation_id": pointer.get("generation_id"), "sha256": pointer.get("content_sha256") or pointer.get("sha256"),
               "run_id": pointer.get("run_id") or pointer.get("source_run_id"), "package_id": pointer.get("package_id")}
        if not ref["run_id"] or any(target.get(key) != value for key, value in ref.items()):
            raise ArtifactError("The selected evaluation generation, producer or digest does not match its published record")
        document = read_generation(directory, "protocol", pointer)
        question = next((q for q in protocol_questions(document, ref)
                         if q["question_id"] == target.get("question_id")), None)
        if question is None or question["followup_target"] != target:
            raise ArtifactError("The selected question, tests, cases or statements do not match the authored protocol")
        return question["followup_target"], question, package
    raise ArtifactError("The selected evaluation is not a current or committed historical P4 protocol")


_SCIENTIFIC_FAMILIES = ("protocol", "diagnostics", "metrics_long", "evidence", "exhibits", "empirical_evidence_index",
                        "empirical_synthesis", "implementation_record")
_ALIASES = {"empirical_evidence_index": "empirical_index_candidate", "empirical_synthesis": "empirical_synthesis_candidate",
            "implementation_record": "implementation_record_candidate"}


def _artifact_pointers(value):
    if isinstance(value, dict):
        if (value.get("path") or value.get("artifact_path")) and (value.get("sha256") or value.get("artifact_sha256")):
            yield value
        for child in value.values():
            yield from _artifact_pointers(child)
    elif isinstance(value, list):
        for child in value:
            yield from _artifact_pointers(child)


def freeze_empirical_target(project_dir: Path, run_dir: Path, branch: str, target: dict) -> dict:
    """Copy inspected evidence outside the new run's binding scientific basis."""
    target, question, package = resolve_empirical_target(project_dir, branch, target)
    snapshot = {"target": target, "question": {k: v for k, v in question.items() if k != "followup_target"},
                "records": [], "artifacts": [], "unavailable_artifacts": [], "tested_theory": {}}
    destination_root = run_dir / "inspected-evidence"

    def copy_record(phase, family, pointer, source=None):
        pointer = {**pointer, "content_sha256": pointer.get("content_sha256") or pointer.get("sha256")}
        directory = project_dir / "branches" / branch / "phases" / phase.lower()
        source = Path(source) if source else generation_path(directory, family, pointer)
        if not source.is_file() or sha256_file(source) != pointer.get("content_sha256"):
            raise ArtifactError("The inspected scientific source changed or disappeared")
        destination = destination_root / phase.lower() / family / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        ref = {**pointer, "branch": branch, "phase": phase, "family": family, "snapshot_path": str(destination)}
        snapshot["records"].append(ref)
        if pointer.get("format") == "jsonl":
            return ref
        document = json.loads(destination.read_text(encoding="utf-8"))
        for artifact in _artifact_pointers(document):
            try:
                original = source_artifact_path(project_dir, pointer, artifact)
                copied = destination_root / "artifacts" / (sha256_file(original) + "-" + original.name)
                copied.parent.mkdir(parents=True, exist_ok=True)
                copied.write_bytes(original.read_bytes())
                snapshot["artifacts"].append({"family": family, "phase": phase, "path": str(copied),
                    "content_sha256": sha256_file(copied), "original_path": artifact.get("path") or artifact.get("artifact_path")})
            except ArtifactError as exc:
                snapshot["unavailable_artifacts"].append({"family": family, "reason": str(exc)})
        return ref

    for preferred in _SCIENTIFIC_FAMILIES:
        family = preferred if preferred in package["records"] else _ALIASES.get(preferred)
        if family and family in package["records"]:
            pointer = package["records"][family]
            if package.get("package_id") and (pointer.get("package_id") != package["package_id"] or pointer.get("run_id") != package["run_id"]):
                raise ArtifactError("The inspected evidence does not belong to its committed evaluation package")
            copy_record("P4", family, pointer)
    from .empirical_context import load_evaluation_basis, verified_basis_theory
    try:
        basis = load_evaluation_basis(project_dir, target)
        theory, ref = verified_basis_theory(project_dir, basis, branch)
        if ref:
            copied = copy_record("P3", ref["family"], ref, ref.get("snapshot_path"))
            snapshot["tested_theory"] = {"status": "recorded", "reference": copied,
                                          "method": basis.get("method")}
        else:
            snapshot["tested_theory"] = {"status": "no_theory", "message": "This evaluation began without a theory package.",
                                          "method": basis.get("method")}
    except ArtifactError as exc:
        snapshot["tested_theory"] = {"status": "unavailable", "message": str(exc)}
    write_json_atomic(run_dir / "inspected-evidence.json", snapshot)
    return snapshot


def empirical_target_context(run_dir: Path, target: dict) -> str:
    snapshot = read_json(run_dir / "inspected-evidence.json")
    if not snapshot or snapshot.get("target") != target:
        raise ArtifactError("The selected empirical question's frozen context is unavailable")
    for ref in snapshot["records"] + snapshot["artifacts"]:
        path = Path(ref.get("snapshot_path") or ref["path"])
        if not path.is_file() or sha256_file(path) != ref["content_sha256"]:
            raise ArtifactError("The inspected scientific source changed or disappeared")
    question = snapshot["question"]
    protocols = [ref for ref in snapshot["records"] if ref.get("phase") == "P4" and ref.get("family") == "protocol"
                 and ref.get("generation_id") == target["generation_id"] and ref.get("content_sha256") == target["sha256"]
                 and (ref.get("run_id") or ref.get("source_run_id")) == target["run_id"]]
    if len(protocols) != 1:
        raise ArtifactError("The inspected protocol no longer matches its exact selected generation")
    authored = next((q for q in protocol_questions(read_json(Path(protocols[0]["snapshot_path"])), target)
                     if q["followup_target"] == target), None)
    if authored is None or {k: v for k, v in authored.items() if k != "followup_target"} != question:
        raise ArtifactError("The inspected question no longer matches its authored protocol")
    sources = "\n".join(f"- {ref['phase']} {ref['family']}: `{ref['snapshot_path']}` (generation {ref['generation_id']}, sha256 {ref['content_sha256']})"
                         for ref in snapshot["records"])
    artifacts = "\n".join(f"- {ref['family']} / {ref['original_path']}: `{ref['path']}`" for ref in snapshot["artifacts"])
    unavailable = "\n".join(f"- {item['family']}: {item['reason']}" for item in snapshot["unavailable_artifacts"])
    return ("## Researcher-selected empirical follow-up\n\n"
            f"Question: {question.get('hypothesis', question['question_id'])}\n\n"
            f"Exact inspected selection: {json.dumps(target, ensure_ascii=False)}\n\n"
            f"Authored test: {json.dumps(question, ensure_ascii=False)}\n\n"
            f"Theory used by the inspected evaluation: {json.dumps(snapshot['tested_theory'], ensure_ascii=False)}\n\n"
            "The binding basis above is current at this new request. The inspected evaluation below is historical context for the selected question, "
            "even when some sources are also current. Do not treat these older results as measurements of a changed method or theory. "
            "Address the selected tests and cases first, explain which prior conclusions remain applicable, and record any new cases or protocol changes explicitly. "
            "The researcher-selected preliminary or comprehensive scope still governs this run.\n\n"
            f"Inspected scientific sources:\n{sources}\n\nInspected source files:\n{artifacts or '(none)'}\n\n"
            f"Unavailable source files, do not claim to have inspected them:\n{unavailable or '(none)'}\n\n")
