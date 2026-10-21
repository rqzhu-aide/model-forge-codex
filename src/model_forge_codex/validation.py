"""Deterministic scientific consistency checks for catalog 1.4 and later.

These checks establish identity, reference integrity and arithmetic, not
the correctness of a proof or the adequacy of an experimental design.
No member-authored script is executed by validation.
"""
from __future__ import annotations

import hashlib
import json
import math
import operator
import statistics
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

from .catalog import Catalog
from .domain import Finding


def _objects(value: Any) -> list[dict]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _same_number(actual: Any, expected: Any) -> bool:
    if expected is None:
        return actual is None
    return _number(actual) and math.isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-10)


def _identity(value: Any) -> tuple | None:
    if not isinstance(value, dict):
        return None
    return tuple(value.get(key) for key in ("stable_id", "version", "definition_sha256"))


def _check_ids(items: list[dict], key: str, family: str, findings: list[Finding]) -> dict[str, dict]:
    ids = [item.get(key) for item in items]
    valid = [item for item in ids if isinstance(item, str) and item]
    if len(valid) != len(ids) or len(set(valid)) != len(valid):
        findings.append(Finding("reference.duplicate_or_missing_id", f"{key} values must be nonempty and unique.", family, "/" + key))
    return {item[key]: item for item in items if isinstance(item.get(key), str) and item[key]}


def _p3_analyst_issues(outputs: dict, findings: list[Finding], *, required: bool) -> dict[str, list[tuple[str, dict]]]:
    """Index authored concerns, without extracting new issues from prose."""
    indexed: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for family, field in (("p3.analyst_handoff", "unresolved_issues"), ("p3.analyst_audit", "issues")):
        document = outputs.get(family)
        if not isinstance(document, dict) or field not in document:
            continue
        values = document[field]
        seen = set()
        if not isinstance(values, list):
            if required:
                findings.append(Finding("p3.issue_traceability", "Authored Analyst issues must be a structured list.", family, "/" + field))
            continue
        for index, issue in enumerate(values):
            identifier = issue.get("issue_id") if isinstance(issue, dict) else None
            if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
                if required:
                    findings.append(Finding("p3.issue_traceability", "Each Analyst issue needs a nonblank ID unique within its list.", family, f"/{field}/{index}"))
                continue
            seen.add(identifier)
            targets = issue.get("component_ids")
            if required and targets is not None and (not isinstance(targets, list) or
                    any(not isinstance(target, str) or not target.strip() for target in targets)):
                findings.append(Finding("p3.issue_traceability", "Issue component targets must be a list of exact nonblank IDs.",
                                        family, f"/{field}/{index}/component_ids"))
            if required and any(prior != issue for _, prior in indexed[identifier]):
                findings.append(Finding("p3.issue_traceability", "A shared issue ID must retain the exact same Analyst concern across records.",
                                        family, f"/{field}/{index}"))
            indexed[identifier].append((family, issue))
    return indexed


def _p3_decision_entries(decision: dict, name: str, key: str, findings: list[Finding]) -> dict[str, dict]:
    values = decision.get(name, [])
    result = {}
    if not isinstance(values, list):
        findings.append(Finding("p3.issue_traceability" if name == "issue_dispositions" else "theory.assessment_change",
                                f"{name} must be a structured list.", "p3.decision", "/" + name))
        return result
    for index, entry in enumerate(values):
        identifier = entry.get(key) if isinstance(entry, dict) else None
        reason = entry.get("reason") if isinstance(entry, dict) else None
        valid = isinstance(identifier, str) and bool(identifier.strip()) and identifier not in result
        valid &= isinstance(reason, str) and bool(reason.strip())
        if name == "issue_dispositions":
            valid &= (isinstance(entry, dict) and isinstance(entry.get("status"), str)
                      and entry["status"] in {"resolved", "contested", "unresolved"})
        else:
            origin = entry.get("origin") if isinstance(entry, dict) else None
            valid &= isinstance(origin, str) and origin in {"lead_concern", "analyst_issue"}
            if isinstance(entry, dict):
                valid &= (isinstance(entry.get("issue_id"), str) and bool(entry["issue_id"].strip())
                          if origin == "analyst_issue" else "issue_id" not in entry)
            else:
                valid = False
        if not valid:
            findings.append(Finding("p3.issue_traceability" if name == "issue_dispositions" else "theory.assessment_change",
                                    f"{name} entries need unique IDs, a nonblank reason and a valid response/origin.",
                                    "p3.decision", f"/{name}/{index}"))
        elif identifier is not None:
            result[identifier] = entry
    return result


def _p3_negative_support(component: str, justification: Any, issues: dict, change: dict | None,
                         roots: dict | None, findings: list[Finding], *, required: bool) -> bool:
    """Accept only the exact Analyst's retained negative support, never Lead math."""
    if (not isinstance(justification, dict) or not isinstance(justification.get("kind"), str)
            or justification["kind"] not in {"counterexample", "empirical_evidence"}
            or not _objects(justification.get("artifacts"))):
        return False
    if required and (not change or change.get("origin") != "analyst_issue"):
        return False
    selected = issues.get(change.get("issue_id"), []) if change else [entry for group in issues.values() for entry in group]
    sources = []
    for family, issue in selected:
        targets = issue.get("component_ids")
        if not required and targets is None:
            targets = issue.get("statement_ids", [issue.get("statement_id")])
        if isinstance(targets, list) and component in targets and isinstance(issue.get("justification"), dict):
            sources.append((family, issue["justification"]))
    if not sources or any(support != justification for _, support in sources):
        return False
    if roots is None:
        return True  # Shape-only checks; publication always supplies collected roots.
    source_roots = {family: roots[family] for family, _ in sources if family in roots}
    source_findings: list[Finding] = []
    if not source_roots or any(not (pointer.get("path") or pointer.get("artifact_path"))
                               for pointer in _objects(justification.get("artifacts"))):
        findings.append(Finding("artifact.source_missing", "Changed negative support needs exact retained Analyst artifact bytes.",
                                "p3.complete_theory", f"/statements/{component}/justification"))
        return False
    family = next(iter(source_roots))
    _check_artifacts({family: {"justification": justification}}, source_roots, source_findings)
    findings.extend(source_findings)
    return not any(finding.blocks_publication for finding in source_findings)


def _check_theory(outputs: dict, findings: list[Finding], *, conservative: bool = False,
                  artifact_roots: dict | None = None) -> None:
    candidate = outputs.get("p3.theory_candidate")
    complete = outputs.get("p3.complete_theory")
    theory = complete if isinstance(complete, dict) else candidate
    issues = _p3_analyst_issues(outputs, findings, required=conservative)
    decision = outputs.get("p3.decision")
    changes = {}
    if conservative and isinstance(decision, dict):
        dispositions = _p3_decision_entries(decision, "issue_dispositions", "issue_id", findings)
        for identifier in set(issues) ^ set(dispositions):
            findings.append(Finding("p3.issue_traceability", f"Analyst issue {identifier} needs one authored Lead disposition; unrelated IDs are not dispositions.",
                                    "p3.decision", "/issue_dispositions"))
        changes = _p3_decision_entries(decision, "assessment_changes", "component_id", findings)
    if not isinstance(theory, dict):
        return
    family = "p3.complete_theory" if isinstance(complete, dict) else "p3.theory_candidate"
    statements = _check_ids(_objects(theory.get("statements")), "statement_id", family, findings)
    assumptions = _check_ids(_objects(theory.get("assumptions")), "assumption_id", family, findings)
    implications = _check_ids(_objects(theory.get("empirical_implications")), "implication_id", family, findings)
    if set(statements) & set(assumptions):
        findings.append(Finding("theory.ambiguous_identity", "A statement and assumption cannot share an ID.", family, ""))
    known = set(statements) | set(assumptions)
    dependencies: dict[str, set[str]] = {}
    used_by: dict[str, set[str]] = defaultdict(set)
    for sid, statement in statements.items():
        edges = set(statement.get("depends_on_statement_ids", [])) | set(statement.get("assumption_ids", []))
        dependencies[sid] = edges
        for dep in edges:
            if dep not in known:
                findings.append(Finding("theory.missing_dependency", f"{sid} refers to unknown dependency {dep}.", family, f"/statements/{sid}"))
            used_by[dep].add(sid)
        if set(statement.get("assumption_ids", [])) - set(assumptions):
            findings.append(Finding("theory.assumption_reference", f"{sid} names an unknown assumption.", family, f"/statements/{sid}/assumption_ids"))
        if set(statement.get("empirical_implication_ids", [])) - set(implications):
            findings.append(Finding("theory.implication_reference", f"{sid} names an unknown empirical implication.", family, f"/statements/{sid}/empirical_implication_ids"))
    for aid, assumption in assumptions.items():
        if set(assumption.get("used_by_statement_ids", [])) != used_by[aid]:
            findings.append(Finding("theory.reverse_dependency_mismatch", f"{aid}'s dependent claims disagree with the statement registry.", family, f"/assumptions/{aid}"))
    for iid, implication in implications.items():
        if set(implication.get("statement_ids", [])) - set(statements):
            findings.append(Finding("theory.statement_reference", f"{iid} names an unknown statement.", family, f"/empirical_implications/{iid}"))
    # Kahn's algorithm avoids recursive depth limits for large theory maps.
    indegree = {sid: len(edges & set(statements)) for sid, edges in dependencies.items()}
    queue = deque(sid for sid, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        sid = queue.popleft(); visited += 1
        for dependent in used_by[sid]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)
    if visited != len(statements):
        findings.append(Finding("theory.cyclic_proof_dependency", "Proof dependencies contain a cycle; a claimed result cannot establish itself.", family, "/statements"))
    projection = outputs.get("p3.claim_map")
    if isinstance(projection, dict):
        candidate_statements = {item.get("statement_id"): item for item in _objects(candidate.get("statements"))} if isinstance(candidate, dict) else {}
        claims = _check_ids(_objects(projection.get("claims")), "statement_id", "p3.claim_map", findings)
        if set(claims) != set(statements):
            findings.append(Finding("theory.graph_coverage", "Graph claims must cover exactly the current statement registry.", "p3.claim_map", "/claims"))
        for sid in set(claims) & set(statements):
            claim, statement = claims[sid], candidate_statements.get(sid, statements[sid])
            if set(claim.get("depends_on", [])) != dependencies[sid]:
                findings.append(Finding("theory.graph_dependency_mismatch", f"Graph dependencies for {sid} disagree with the theory record.", "p3.claim_map", f"/claims/{sid}/depends_on"))
            if "used_by" in claim and set(claim["used_by"]) != used_by[sid]:
                findings.append(Finding("theory.graph_reverse_mismatch", f"Graph reverse dependencies for {sid} disagree with the theory record.", "p3.claim_map", f"/claims/{sid}/used_by"))
            if "scientific_status" in claim and claim["scientific_status"] != statement.get("status"):
                findings.append(Finding("theory.graph_status_mismatch", f"Graph assessment for {sid} disagrees with the submitted theorist account.", "p3.claim_map", f"/claims/{sid}/scientific_status"))
            justification = statement.get("justification") or {}
            if claim.get("proof_status") == "full" and justification.get("kind") in {"open_obligation", "counterexample"}:
                findings.append(Finding("theory.graph_proof_mismatch", f"{sid} has an obligation or counterexample, not a complete proof.", "p3.claim_map", f"/claims/{sid}/proof_status"))
    probes = outputs.get("p3.falsification_log")
    if isinstance(probes, dict):
        probe_map = _check_ids(_objects(probes.get("probes")), "probe_id", "p3.falsification_log", findings)
        for pid, probe in probe_map.items():
            if probe.get("target_statement") not in known:
                findings.append(Finding("theory.probe_target_missing", f"{pid} does not refer to a current statement or assumption.", "p3.falsification_log", f"/probes/{pid}"))
    # The lead integrates assessments but cannot silently replace audited math.
    if isinstance(candidate, dict) and isinstance(complete, dict):
        prior = {s.get("statement_id"): s for s in _objects(candidate.get("statements"))}
        prior_assumptions = {a.get("assumption_id"): a for a in _objects(candidate.get("assumptions"))}
        math_fields = ("statement_type", "text", "quantifiers", "regime", "assumption_ids", "depends_on_statement_ids", "empirical_implication_ids")
        if set(prior) != set(statements) or set(prior_assumptions) != set(assumptions):
            findings.append(Finding("theory.unaudited_math_change", "Lead integration must retain the exact statement and assumption registry.", family, ""))
        changed_components = set()
        for sid, statement in statements.items():
            if sid not in prior or any(statement.get(k) != prior[sid].get(k) for k in math_fields):
                findings.append(Finding("theory.unaudited_math_change", f"Lead output changes the mathematical content of {sid} after specialist audit.", family, f"/statements/{sid}"))
            if sid not in prior:
                continue
            original = prior[sid]
            old, new = original.get("status"), statement.get("status")
            support_changed = original.get("justification") != statement.get("justification")
            if old != new or support_changed:
                changed_components.add(sid)
            permitted = (old == new or new == "retracted" or (old == "established" and new == "conditional")
                         or (new == "incomplete" and old in {"established", "conditional", "untested"}) or new == "contradicted")
            if not permitted:
                findings.append(Finding("theory.unaudited_assessment_change", f"Lead integration cannot strengthen or rehabilitate {sid} without new specialist work.", family, f"/statements/{sid}/status"))
            if support_changed or (old != new and new == "contradicted"):
                sourced = (new in {"contradicted", "incomplete", "retracted"}
                           and _p3_negative_support(sid, statement.get("justification"), issues, changes.get(sid),
                                                    artifact_roots, findings, required=conservative))
                if not sourced:
                    findings.append(Finding("theory.unaudited_justification_change", f"Changed support for {sid} must be the exact retained Analyst counterexample/evidence, not a new Lead argument.", family, f"/statements/{sid}/justification"))
        for aid, assumption in assumptions.items():
            if aid not in prior_assumptions or any(assumption.get(k) != prior_assumptions[aid].get(k) for k in ("text", "scope", "used_by_statement_ids")):
                findings.append(Finding("theory.unaudited_math_change", f"Lead output changes assumption {aid} after specialist audit.", family, f"/assumptions/{aid}"))
            if aid in prior_assumptions and assumption.get("source_artifacts") != prior_assumptions[aid].get("source_artifacts"):
                findings.append(Finding("theory.unaudited_justification_change", f"Lead integration must retain the original source pointers for assumption {aid}.",
                                        family, f"/assumptions/{aid}/source_artifacts"))
            if aid in prior_assumptions and assumption.get("status") != prior_assumptions[aid].get("status"):
                changed_components.add(aid)
        if conservative and isinstance(decision, dict):
            for component in changed_components ^ set(changes):
                findings.append(Finding("theory.assessment_change", f"Changed component {component} needs exactly one authored assessment change; unchanged/unknown targets are not changes.", "p3.decision", "/assessment_changes"))
            for component, change in changes.items():
                if change.get("origin") == "analyst_issue":
                    targets = [issue for _, issue in issues.get(change.get("issue_id"), [])
                               if isinstance(issue.get("component_ids"), list) and component in issue["component_ids"]]
                    if not targets:
                        findings.append(Finding("theory.assessment_change", "An Analyst-origin assessment must name an actual issue targeting this component.", "p3.decision", "/assessment_changes"))


def _check_reassessment(outputs: dict, frozen_basis: dict | None, findings: list[Finding]) -> None:
    """A P3 run armed with predecessor history must publish an explicit account.

    The harness supplied the branch's prior theory package as historical
    material because the method definition changed. The published record must
    name that predecessor in its revision account; the account's content is
    authored, not inferred.
    """
    materials = ((frozen_basis or {}).get("predecessor_material") or {}).get("materials") or {}
    if not materials:
        return
    complete = outputs.get("p3.complete_theory")
    theory = complete if isinstance(complete, dict) else outputs.get("p3.theory_candidate")
    if not isinstance(theory, dict):
        return  # Missing outputs are reported by the required-output checks.
    family = "p3.complete_theory" if isinstance(complete, dict) else "p3.theory_candidate"
    account = theory.get("revision_account")
    if not isinstance(account, dict):
        findings.append(Finding(
            "theory.revision_account_missing",
            "This run was briefed with the branch's prior theory as historical material for a revised method; "
            "the published theory must carry a revision_account stating what survives, what changed, and what remains unresolved.",
            family, "/revision_account"))
        return
    supplied = {ref.get("generation_id") for ref in materials.values() if ref.get("generation_id")}
    if account.get("prior_generation_id") not in supplied:
        verified = []
        for source_family, ref in materials.items():
            if not ref.get("snapshot_path"):
                continue
            try:
                path = Path(ref["snapshot_path"])
                if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == ref.get("content_sha256"):
                    verified.append({**ref, "phase": "P3", "family": source_family})
            except (OSError, ValueError):
                continue  # Missing or changed bytes are not suggested as a lookup source.
        context = (" Supplied predecessor generation IDs in the frozen basis: " + ", ".join(sorted(map(str, supplied))) + "."
                   + (_frozen_source_hint(verified) if verified else
                      " No predecessor snapshot could be verified; restore the saved historical source before correcting this reference. "
                      "Do not substitute current project generations."))
        findings.append(Finding(
            "theory.revision_account_source",
            f"revision_account.prior_generation_id {account.get('prior_generation_id')!r} must name a supplied predecessor generation "
            "from this run's frozen basis." + context,
            family, "/revision_account/prior_generation_id"))


def recompute_diagnostics(protocol: dict, rows: list[dict]) -> dict:
    """Recompute supported summaries from recorded replicates, without a model.

    Custom estimators/uncertainty are explicitly left unverified. This is a
    verification of recorded results, not a replay of the original experiment.
    """
    from .empirical_targets import effective_protocol
    protocol = effective_protocol(protocol)
    cases = {c["case_id"]: c for c in _objects(protocol.get("cases"))}
    metrics = {m["metric_id"]: m for m in _objects(protocol.get("metrics"))}
    by_case = defaultdict(list)
    for row in _objects(rows):
        if row.get("eligibility") == "invalidated":
            continue
        by_case[row.get("case_id")].append(row)
    result = {"headline_numbers": [], "stability": [], "solver_health": [], "runtime": {"total_ms": 0, "per_case": []}}
    regimes = defaultdict(list)
    operations = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}
    for case_id, case in cases.items():
        observed = by_case[case_id]
        timed = [r["runtime_ms"] for r in observed if _number(r.get("runtime_ms"))]
        if timed:
            result["runtime"]["total_ms"] += sum(timed)
            result["runtime"]["per_case"].append({"case_id": case_id, "mean_ms": statistics.mean(timed), "max_ms": max(timed)})
        for row in observed:
            if "converged" in row or "solver_status" in row:
                regimes[case.get("regime", case_id)].append(row)
        for metric_id in case.get("metric_ids", []):
            definition = metrics.get(metric_id, {}).get("summary", {})
            sampled = [r for r in observed if r.get("status") == "completed" and _number((r.get("metrics") or {}).get(metric_id))]
            values = [r["metrics"][metric_id] for r in sampled]
            aggregation = definition.get("aggregation")
            estimate = None
            if values:
                if aggregation == "mean": estimate = statistics.mean(values)
                elif aggregation == "median": estimate = statistics.median(values)
                elif aggregation == "sum": estimate = sum(values)
                elif aggregation == "identity" and len(values) == 1: estimate = values[0]
            uncertainty = definition.get("uncertainty", "not_assessed")
            mcse = statistics.stdev(values) / math.sqrt(len(values)) if uncertainty == "mcse" and aggregation == "mean" and len(values) > 1 else None
            result["headline_numbers"].append({"case_id": case_id, "metric": metric_id, "estimate": estimate, "mcse": mcse,
                                                "uncertainty_kind": uncertainty, "n_replicates": len(values), "aggregation": aggregation})
            rule = definition.get("decision_rule") or {}
            verdicts = {operations[rule["operator"]](v, rule["threshold"]) for v in values} if rule.get("operator") in operations and _number(rule.get("threshold")) else set()
            result["stability"].append({"case_id": case_id, "metric": metric_id,
                                         "mean": statistics.mean(values) if values else None,
                                         "sd": statistics.stdev(values) if len(values) > 1 else None,
                                         "n_seeds": len({r["seed"] for r in sampled if "seed" in r}),
                                         "seed_flip": len(verdicts) > 1 if len(values) > 1 and verdicts else None})
    for regime, observations in regimes.items():
        failures = sum(row.get("status") != "completed" or row.get("converged") is False for row in observations)
        result["solver_health"].append({"regime": regime, "n_runs": len(observations), "n_failures": failures, "failure_rate": failures / len(observations)})
    return result


def _check_empirical(outputs: dict, findings: list[Finding]) -> None:
    protocol, rows, diagnostics = (outputs.get(key) for key in ("p4.protocol", "p4.metrics_long", "p4.diagnostics"))
    if not isinstance(protocol, dict) or not isinstance(rows, list) or not isinstance(diagnostics, dict):
        return
    original_protocol = protocol
    from .empirical_targets import effective_protocol
    protocol = effective_protocol(protocol)
    cases = _check_ids(_objects(protocol.get("cases")), "case_id", "p4.protocol", findings)
    tests = _check_ids(_objects(protocol.get("claim_tests")), "test_id", "p4.protocol", findings)
    metrics = _check_ids(_objects(protocol.get("metrics")), "metric_id", "p4.protocol", findings)
    baselines = _check_ids(_objects(protocol.get("baselines")), "baseline_id", "p4.protocol", findings)
    for metric in metrics.values():
        summary = metric.get("summary") or {}
        if summary.get("aggregation") == "custom" or summary.get("uncertainty") == "custom":
            findings.append(Finding("diagnostics.custom_not_recomputed", "Custom estimates or uncertainty are reported but not independently recomputed by the standard arithmetic checks.", "p4.diagnostics", "", blocks_publication=False))
            break
    expected: dict[tuple[str, str], dict] = {}
    for cid, case in cases.items():
        if set(case.get("test_ids", [])) - set(tests) or set(case.get("metric_ids", [])) - set(metrics):
            findings.append(Finding("empirical.case_reference", f"{cid} refers to an undeclared test or metric.", "p4.protocol", f"/cases/{cid}"))
        if case.get("comparator_id") not in {"selected_method", *baselines}:
            findings.append(Finding("empirical.comparator_reference", f"{cid} refers to an undeclared comparator.", "p4.protocol", f"/cases/{cid}"))
        for rid, replicate in _check_ids(_objects(case.get("replicates")), "replicate_id", "p4.protocol", findings).items():
            expected[cid, rid] = replicate
    planned_tests = {test for case in cases.values() for test in case.get("test_ids", [])}
    if planned_tests != set(tests):
        findings.append(Finding("empirical.test_coverage", "Each protocol test must have at least one declared case.", "p4.protocol", "/cases"))
    for evidence in _objects(outputs.get("p4.evidence")):
        if set(evidence.get("test_ids", [])) - set(tests) or set(evidence.get("case_ids", [])) - set(cases):
            findings.append(Finding("empirical.evidence_reference", "Evidence refers to an undeclared test or case.", "p4.evidence", "/case_ids"))
        comparator = evidence.get("comparator_id", "selected_method")
        if comparator not in {"selected_method", *baselines}:
            findings.append(Finding("empirical.evidence_comparator", "Evidence refers to an undeclared comparison method.", "p4.evidence", "/comparator_id"))
        if any(cases[cid].get("comparator_id") != comparator for cid in evidence.get("case_ids", []) if cid in cases):
            findings.append(Finding("empirical.evidence_comparator", "Evidence and its cases name different comparison methods.", "p4.evidence", "/comparator_id"))
    observed = Counter((row.get("case_id"), row.get("replicate_id")) for row in _objects(rows)
                       if row.get("eligibility") != "invalidated")
    if set(observed) != set(expected) or any(n != 1 for n in observed.values()):
        findings.append(Finding("empirical.replicate_grid", "Eligible rows must cover each planned case/replicate exactly once, including failed or not-run work; invalidated attempts remain separate.", "p4.metrics_long", ""))
    for index, row in enumerate(_objects(rows)):
        if (row.get("case_id"), row.get("replicate_id")) not in expected:
            findings.append(Finding("empirical.undeclared_attempt", "Every retained attempt must name a declared case and replicate.", "p4.metrics_long", f"/{index}"))
        case = cases.get(row.get("case_id"), {})
        planned = expected.get((row.get("case_id"), row.get("replicate_id")), {})
        if "seed" in planned and row.get("seed") != planned["seed"]:
            findings.append(Finding("empirical.seed_mismatch", "The recorded seed differs from the prespecified replicate.", "p4.metrics_long", f"/{index}/seed"))
        values = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        if ("runtime_ms" in row and not _number(row["runtime_ms"])) or any(value is not None and not _number(value) for value in values.values()):
            findings.append(Finding("empirical.nonfinite_value", "Recorded metrics and wall times must be finite numbers or explicitly unavailable metrics.", "p4.metrics_long", f"/{index}"))
        if row.get("eligibility") != "invalidated":
            # Retain the original payload of a rejected attempt, including
            # the serialization mistake that caused its invalidation. It is
            # excluded from diagnostics; schema and host checks still bind
            # its reason, execution identity and unchanged observed bytes.
            if set(values) - set(case.get("metric_ids", [])):
                findings.append(Finding("empirical.metric_reference", "A replicate contains an undeclared metric.", "p4.metrics_long", f"/{index}/metrics"))
            if row.get("status") == "completed" and (set(values) != set(case.get("metric_ids", [])) or any(v is not None and not _number(v) for v in values.values())):
                findings.append(Finding("empirical.completed_metrics", "A completed replicate must report every declared metric as a finite value or explicitly unavailable null.", "p4.metrics_long", f"/{index}/metrics"))
    if not cases:
        return  # Schema validation reports the missing declared design.
    expected_diagnostics = recompute_diagnostics(original_protocol, rows)
    for section, keys, fields in (
        ("headline_numbers", ("case_id", "metric"), ("estimate", "mcse", "n_replicates")),
        ("stability", ("case_id", "metric"), ("mean", "sd", "n_seeds", "seed_flip")),
        ("solver_health", ("regime",), ("n_runs", "n_failures", "failure_rate")),
    ):
        expected_items = {tuple(item[k] for k in keys): item for item in expected_diagnostics[section]}
        seen = set()
        for index, row in enumerate(_objects(diagnostics.get(section))):
            key = tuple(row.get(k) for k in keys)
            expected_item = expected_items.get(key)
            if key in seen or expected_item is None:
                findings.append(Finding("diagnostics.unknown_or_duplicate_group", f"{section} contains an unknown or duplicate group.", "p4.diagnostics", f"/{section}/{index}")); continue
            seen.add(key)
            if section == "headline_numbers" and row.get("estimate") is not None and not _number(row["estimate"]):
                findings.append(Finding("diagnostics.nonfinite_estimate", "A reported estimate must be finite or explicitly unavailable.", "p4.diagnostics", f"/{section}/{index}/estimate"))
            for field in fields:
                if field == "n_replicates" and field not in row:
                    continue
                if section == "headline_numbers":
                    if field == "estimate" and expected_item.get("aggregation") == "custom":
                        continue
                    if field == "mcse" and expected_item.get("uncertainty_kind") != "mcse":
                        if row.get(field) is not None:
                            findings.append(Finding("diagnostics.inapplicable_mcse", "MCSE is not the declared uncertainty measure.", "p4.diagnostics", f"/{section}/{index}/{field}"))
                        continue
                expected_value = expected_item.get(field)
                matches = row.get(field) is expected_value if field == "seed_flip" else _same_number(row.get(field), expected_value)
                if not matches:
                    findings.append(Finding("diagnostics.aggregate_mismatch", f"{section} {key}: {field} does not recompute from recorded replicates.", "p4.diagnostics", f"/{section}/{index}/{field}"))
            if section == "headline_numbers" and row.get("uncertainty_kind") != expected_item.get("uncertainty_kind"):
                findings.append(Finding("diagnostics.uncertainty_mismatch", "Uncertainty type differs from the protocol.", "p4.diagnostics", f"/{section}/{index}/uncertainty_kind"))
            if section == "headline_numbers" and ("ci_lo" in row or "ci_hi" in row):
                lower, upper = row.get("ci_lo"), row.get("ci_hi")
                if not _number(lower) or not _number(upper) or lower > upper:
                    findings.append(Finding("diagnostics.invalid_interval", "An interval requires finite ordered lower and upper endpoints.", "p4.diagnostics", f"/{section}/{index}"))
        # Headline results are the research account, even when all runs fail.
        if section == "headline_numbers" and seen != set(expected_items):
            findings.append(Finding("diagnostics.missing_group", "Headline results must cover every declared case/metric, with null estimates when unavailable.", "p4.diagnostics", "/headline_numbers"))
        if section == "stability":
            applicable = {key for key, item in expected_items.items()
                          if item["n_seeds"] >= 2 and metrics[item["metric"]].get("summary", {}).get("decision_rule")}
            if applicable - seen:
                findings.append(Finding("diagnostics.missing_stability", "Declared verdict checks with repeated seeds must retain every applicable case/metric result.", "p4.diagnostics", "/stability"))
        if section == "solver_health" and set(expected_items) - seen:
            findings.append(Finding("diagnostics.missing_solver_health", "Recorded solver outcomes must remain visible for every evaluated regime.", "p4.diagnostics", "/solver_health"))
    runtime = diagnostics.get("runtime") or {}
    if not _same_number(runtime.get("total_ms"), expected_diagnostics["runtime"]["total_ms"]):
        findings.append(Finding("diagnostics.runtime_mismatch", "Total runtime does not equal the recorded wall times.", "p4.diagnostics", "/runtime/total_ms"))
    expected_runtime = {r["case_id"]: r for r in expected_diagnostics["runtime"]["per_case"]}
    seen_runtime = set()
    for row in _objects(runtime.get("per_case")):
        cid = row.get("case_id"); target = expected_runtime.get(cid)
        if cid in seen_runtime or target is None or any(not _same_number(row.get(k), target[k]) for k in ("mean_ms", "max_ms")):
            findings.append(Finding("diagnostics.runtime_mismatch", "Per-case runtime does not recompute from recorded wall times.", "p4.diagnostics", "/runtime/per_case"))
        seen_runtime.add(cid)
    if seen_runtime != set(expected_runtime):
        findings.append(Finding("diagnostics.runtime_coverage", "Per-case runtime omits recorded cases.", "p4.diagnostics", "/runtime/per_case"))
    for exhibit in _objects(outputs.get("p4.exhibits")):
        if set(exhibit.get("test_ids", [])) - set(tests) or set(exhibit.get("case_ids", [])) - set(cases):
            findings.append(Finding("empirical.exhibit_reference", "An exhibit refers to an undeclared test or case.", "p4.exhibits", ""))


def _check_artifacts(outputs: dict, roots: dict[str, Path], findings: list[Finding], *, progressive_p4=False) -> None:
    checked = set()
    def verify(family: str, pointer: dict, location: str):
        rel = pointer.get("path") or pointer.get("artifact_path")
        digest = pointer.get("sha256") or pointer.get("artifact_sha256")
        if not rel:
            return  # Logical generation references are resolved by the engine.
        is_table = progressive_p4 and family == "p4.exhibits" and pointer.get("kind") == "table"
        key = (family, str(rel), str(digest), json.dumps(pointer.get("table_columns", []), sort_keys=True) if is_table else "")
        if key in checked:
            return
        checked.add(key)
        search_roots = list(dict.fromkeys([roots[family], *roots.values()])) if family in roots else list(roots.values())
        # Workspace-relative locators retain their scientific identity when
        # the collector copies primary files into working/<producer>/.
        search_roots += [child for root in list(search_roots)
                         for child in (Path(root) / "working").glob("*") if child.is_dir()]
        candidates = []
        for root in search_roots:
            root = Path(root).resolve(); candidate = (root / str(rel)).resolve()
            if candidate.is_relative_to(root) and candidate.is_file():
                candidates.append(candidate)
        if not candidates:
            findings.append(Finding("artifact.source_missing", f"Referenced source {rel!r} is missing from the collected run artifacts.", family, location))
        else:
            matched = next((path for path in candidates if hashlib.sha256(path.read_bytes()).hexdigest() == digest), None)
            if matched is None:
                findings.append(Finding("artifact.digest_mismatch", f"Referenced source {rel!r} does not match its recorded digest.", family, location))
            elif is_table:
                from .table_exhibits import table_preview
                try:
                    table_preview(matched, pointer)
                except (ValueError, TypeError, OSError) as error:
                    findings.append(Finding("artifact.table_parse", f"Table {rel!r} cannot render inline: {error}", family, location))
    def walk(family: str, value: Any, location: str = ""):
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(family, item, f"{location}/{index}")
        elif isinstance(value, dict):
            if "artifact_path" in value:
                verify(family, value, location + "/artifact_path")
            for name, item in value.items():
                pointer = location + "/" + name.replace("~", "~0").replace("/", "~1")
                if name in ("primary_artifact", "manuscript_artifact", "canonical_artifact", "artifact") and isinstance(item, dict):
                    verify(family, item, pointer)
                elif name in ("artifacts", "supplementary_artifacts"):
                    for index, artifact in enumerate(_objects(item)):
                        verify(family, artifact, f"{pointer}/{index}")
                walk(family, item, pointer)
    for family, document in outputs.items():
        walk(family, document)
    diagnostics = outputs.get("p4.diagnostics")
    if isinstance(diagnostics, dict) and "p4.diagnostics" in roots:
        base = Path(roots["p4.diagnostics"]).resolve()
        paths = {"protocol_sha256": Path(roots.get("p4.protocol", base)) / "protocol.json",
                 "metrics_sha256": Path(roots.get("p4.metrics_long", base)) / "metrics_long.jsonl",
                 "script_sha256": base / str(diagnostics.get("regenerated_by", ""))}
        hashes = diagnostics.get("provenance") or {}
        for key, path in paths.items():
            candidates = [path]
            if progressive_p4 and key == "script_sha256":
                candidates.append(base / "working" / "data_analyst" / str(diagnostics.get("regenerated_by", "")))
            matched = any(candidate.is_file()
                          and any(candidate.resolve().is_relative_to(Path(root).resolve()) for root in roots.values())
                          and hashlib.sha256(candidate.read_bytes()).hexdigest() == hashes.get(key)
                          for candidate in candidates)
            if not matched:
                findings.append(Finding("diagnostics.provenance_mismatch", f"Diagnostic {key} does not identify the collected source bytes.", "p4.diagnostics", f"/provenance/{key}"))


def _frozen_source_hint(references: list[dict]) -> str:
    """Describe verified lookup context without selecting a substitute identity."""
    sources = []
    for ref in references:
        source = (f"`{ref.get('snapshot_path') or ref.get('path')}` "
                  f"({ref.get('phase')} {ref.get('family')}, generation {ref.get('generation_id')}, "
                  f"sha256 {ref.get('content_sha256')})")
        if source not in sources:
            sources.append(source)
    if not sources:
        return " No verified frozen P1 through P4 source is available; retain the unresolved reference and report the missing evidence."
    return (" Verify the intended reference against these permitted frozen sources: " + "; ".join(sources)
            + ". Source locations provide lookup context; an unresolved identity still requires source verification.")


def _check_manuscript(outputs: dict, frozen_basis: dict | None, findings: list[Finding]) -> None:
    """Resolve authored references against saved inputs, without judging claims."""
    manuscript = outputs.get("p5.manuscript_candidate") or {}
    trace = _check_ids(_objects(outputs.get("p5.claim_traceability")), "statement_id", "p5.claim_traceability", findings)
    index = manuscript.get("claim_support_index") or {}
    for group, claim_ids in index.items():
        for position, claim_id in enumerate(claim_ids):
            if claim_id not in trace:
                escaped_group = group.replace("~", "~0").replace("/", "~1")
                findings.append(Finding("manuscript.claim_unmapped", f"Central claim {claim_id!r} has no traceability statement. Inspect the declared claim_traceability.json output; do not substitute a different claim.", "p5.manuscript_candidate", f"/claim_support_index/{escaped_group}/{position}"))
    if frozen_basis is None:
        return  # A shape-only caller has no authority to resolve saved sources.

    definitions: dict[str, set[str]] = defaultdict(set)
    definition_records: dict[str, set[tuple[str, str]]] = defaultdict(set)
    artifacts: dict[tuple[str, str], set[str]] = defaultdict(set)
    artifact_records: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    declared_artifacts: list[tuple[tuple[str, str], str, tuple[str, str] | None]] = []
    records: dict[tuple[str, str], list[tuple[dict, dict]]] = defaultdict(list)
    verified_records = []
    verified_artifacts = []

    def record_hint(*, keys=(), record_id=None):
        matched = [ref for key, values in records.items() for ref, _ in values
                   if key in keys or record_id is not None and key[0] == record_id]
        return _frozen_source_hint(matched or verified_records)

    def walk(value: Any):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    for ref in _objects(frozen_basis.get("records")):
        if str(ref.get("phase", "")).upper() not in ("P1", "P2", "P3", "P4"):
            continue  # A previous manuscript cannot establish its own support.
        path = Path(ref.get("snapshot_path") or "")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("content_sha256"):
            findings.append(Finding("manuscript.frozen_source_changed",
                "A frozen manuscript source is missing or its digest changed. "
                f"Expected input `{ref.get('snapshot_path') or '(not recorded)'}`, generation {ref.get('generation_id')}, "
                f"sha256 {ref.get('content_sha256')}. Report the unavailable frozen input; do not replace it with a current generation.",
                "p5.upstream_basis_manifest", "/basis"))
            continue
        text = path.read_text(encoding="utf-8")
        doc = [json.loads(line) for line in text.splitlines() if line.strip()] if ref.get("format") == "jsonl" else json.loads(text)
        verified_records.append(ref)
        phase = ref["phase"].upper()
        # Only object definitions count. Lists of referenced IDs do not create
        # evidence, and P5 records never enter this registry.
        for root in doc if isinstance(doc, list) else [doc]:
            owner = (root["record_id"], ref["generation_id"]) if isinstance(root, dict) and root.get("record_id") else None
            if owner:
                records[owner].append((ref, root))
            for item in walk(root):
                for key in ("evidence_id", "statement_id", "claim_id", "source_id", "assumption_id", "stable_id"):
                    if isinstance(item.get(key), str) and len(item) > 1:
                        definitions[item[key]].add(phase)
                        if owner:
                            definition_records[item[key]].add(owner)
                if item.get("artifact_id") and item.get("sha256"):
                    declared_artifacts.append(((item["artifact_id"], item["sha256"]), phase, owner))

    for artifact in _objects(frozen_basis.get("artifacts")):
        if str(artifact.get("phase", "")).upper() not in ("P1", "P2", "P3", "P4"):
            continue
        path = Path(artifact.get("path") or "")
        digest = artifact.get("content_sha256")
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            verified_artifacts.append(artifact)
            artifacts[(artifact.get("artifact_id"), digest)].add(artifact["phase"].upper())
            # The snapshot collector deduplicates identical source bytes, so
            # retain other declared names for those same verified bytes.
            for key, phase, owner in declared_artifacts:
                if key[1] == digest and phase == artifact["phase"].upper():
                    artifacts[key].add(phase)
                    if owner:
                        artifact_records[key].add(owner)

    manifest = outputs.get("p5.upstream_basis_manifest") or {}
    # A new interpretation can point to its location in this manuscript.
    # This locates the claim; it does not supply upstream scientific support.
    local_locations = {(p.get("artifact_id"), p.get("sha256")) for p in
                       (manuscript.get("manuscript_artifact"), manuscript.get("primary_artifact")) if isinstance(p, dict)}
    manifest_keys = set()
    for family, document in (("p5.upstream_basis_manifest", manifest), ("p5.manuscript_candidate", manuscript)):
        seen = set()
        for position, binding in enumerate(_objects(document.get("basis"))):
            key = (binding.get("record_id"), binding.get("generation_id"))
            pointer = f"/basis/{position}"
            matches = records.get(key, [])
            if key in seen:
                findings.append(Finding("manuscript.duplicate_basis", "A source generation occurs more than once in this basis.", family, pointer))
            seen.add(key)
            if not matches:
                findings.append(Finding("manuscript.basis_unresolved", "The record and generation do not identify a frozen P1 through P4 input." + record_hint(record_id=key[0]), family, pointer))
                continue
            ref, source = matches[0]
            valid = (binding.get("content_sha256") == ref.get("content_sha256")
                     and binding.get("record_type") == source.get("record_type")
                     and binding.get("publication_state_at_use") == ref.get("publication_state", "formal")
                     and binding.get("record_position_at_use") == ref.get("record_position", "current"))
            if "method_identity" in binding:
                valid = valid and _identity(binding["method_identity"]) == _identity(source.get("method_identity"))
            if "generation_number" in binding and source.get("generation_number") is not None:
                valid = valid and binding["generation_number"] == source["generation_number"]
            if not valid:
                findings.append(Finding("manuscript.basis_mismatch", "The source digest, record type, method, or authority differs from the frozen input." + record_hint(keys={key}), family, pointer))
            elif family == "p5.upstream_basis_manifest":
                manifest_keys.add(key)
        if family == "p5.manuscript_candidate" and seen - manifest_keys:
            findings.append(Finding("manuscript.basis_not_manifested", "The manuscript cites source generations absent from its upstream basis manifest." + record_hint(keys=seen - manifest_keys), family, "/basis"))

    required_phases: set[str] = set()
    for position, statement in enumerate(_objects(outputs.get("p5.claim_traceability"))):
        pointer = f"/{position}"
        supporting_phases: set[str] = set()
        outcome = statement.get("scientific_outcome") or {}
        references = [(field, statement.get(field, [])) for field in ("supporting_evidence_ids", "counterevidence_ids", "assumptions")]
        references += [("scientific_outcome/" + field, outcome.get(field, []))
                       for field in ("strongest_evidence_ids", "strongest_counterevidence_ids")]
        for field, identifiers in references:
            for reference_position, identifier in enumerate(identifiers):
                reference_pointer = f"{pointer}/{field}/{reference_position}"
                phases = definitions.get(identifier, set())
                if not phases:
                    findings.append(Finding("manuscript.evidence_unresolved", f"Reference {identifier!r} does not identify evidence in the frozen upstream inputs." + record_hint(), "p5.claim_traceability", reference_pointer))
                owners = definition_records.get(identifier, set())
                if owners and not owners & manifest_keys:
                    findings.append(Finding("manuscript.basis_not_manifested", f"The source generation for {identifier!r} is absent from the upstream basis manifest." + record_hint(keys=owners), "p5.claim_traceability", reference_pointer))
                if field != "assumptions":
                    supporting_phases.update(phases)
        for location_position, location in enumerate(_objects(statement.get("source_locations"))):
            location_pointer = f"{pointer}/source_locations/{location_position}"
            phases = artifacts.get((location.get("artifact_id"), location.get("sha256")), set())
            if not phases and (location.get("artifact_id"), location.get("sha256")) not in local_locations:
                exact_id_sources = [artifact for artifact in verified_artifacts
                                    if artifact.get("artifact_id") == location.get("artifact_id")]
                findings.append(Finding("manuscript.source_unresolved", "A claim source does not identify a verified frozen upstream artifact."
                                        + _frozen_source_hint(exact_id_sources or verified_artifacts), "p5.claim_traceability", location_pointer))
            owners = artifact_records.get((location.get("artifact_id"), location.get("sha256")), set())
            if owners and not owners & manifest_keys:
                findings.append(Finding("manuscript.basis_not_manifested", "The claim's exact source generation is absent from the upstream basis manifest." + record_hint(keys=owners), "p5.claim_traceability", location_pointer))
            supporting_phases.update(phases)
        owner_key = (statement.get("record_id"), statement.get("record_generation_id"))
        if statement.get("record_id") != manuscript.get("record_id"):
            if owner_key not in records:
                findings.append(Finding("manuscript.statement_generation_unresolved", "The statement's source record generation is not in the frozen inputs." + record_hint(record_id=owner_key[0]), "p5.claim_traceability", pointer + "/record_generation_id"))
            elif owner_key not in manifest_keys:
                findings.append(Finding("manuscript.basis_not_manifested", "The statement's source generation is absent from the upstream basis manifest." + record_hint(keys={owner_key}), "p5.claim_traceability", pointer + "/record_generation_id"))
        elif manuscript.get("generation_id") and statement.get("record_generation_id") != manuscript["generation_id"]:
            findings.append(Finding("manuscript.statement_generation_mismatch", "The statement names a different manuscript generation.", "p5.claim_traceability", pointer + "/record_generation_id"))
        for group, claim_ids in index.items():
            if statement.get("statement_id") not in claim_ids or not group.startswith(("p1_", "p2_", "p3_", "p4_")):
                continue
            phase = group[:2].upper()
            state = (statement.get("scientific_outcome") or {}).get("state")
            if phase not in supporting_phases and state not in ("inconclusive", "not_assessed", "not_applicable"):
                findings.append(Finding("manuscript.claim_phase_unsupported", f"The claim is indexed as {phase} but has no resolved source from that phase."
                                        + _frozen_source_hint([ref for ref in verified_records if ref["phase"].upper() == phase]), "p5.claim_traceability", pointer))
            if phase in supporting_phases:
                required_phases.add(phase)
    # Some legacy sources have no scientific-record envelope. Where an
    # envelope exists, the manifest must name an exact generation for each
    # upstream phase used to support central claims.
    available_phases = {ref["phase"].upper() for matches in records.values() for ref, _ in matches}
    manifested_phases = {ref["phase"].upper() for key in manifest_keys for ref, _ in records[key]}
    if required_phases & available_phases - manifested_phases:
        findings.append(Finding("manuscript.basis_incomplete", "The upstream basis manifest omits a phase used to support the manuscript's central claims."
                                + _frozen_source_hint([ref for ref in verified_records if ref["phase"].upper() in required_phases - manifested_phases]), "p5.upstream_basis_manifest", "/basis"))


def validate_scientific_outputs(
    catalog: Catalog, phase: str, outputs: dict[str, Any],
    artifact_roots: dict[str, Path] | None = None, frozen_method: dict | None = None,
    frozen_basis: dict | None = None,
) -> list[Finding]:
    """Validate parsed full-ID outputs against one frozen scientific basis.

    artifact_roots maps an output ID to its containing collected stage
    folder. Omit it only for shape/arithmetic validation, not publication.
    """
    if not catalog.scientific_validation_enabled:
        return []
    findings: list[Finding] = []
    protocol = outputs.get("p4.protocol")
    protocol = protocol if isinstance(protocol, dict) else {}
    if frozen_method:
        from .empirical_targets import effective_protocol
        declared_baselines = {baseline.get("baseline_id") for baseline in _objects(effective_protocol(protocol).get("baselines"))}
        frozen = frozen_method.get("identity") or frozen_method.get("method_identity") or frozen_method
        for family, value in outputs.items():
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, dict) and "method_identity" in item and _identity(item["method_identity"]) != _identity(frozen):
                    is_comparison = (family == "p4.evidence" and item.get("comparator_id") in declared_baselines
                                     and (item.get("applicability_at_creation") or {}).get("method_match") == "not_applicable")
                    if not is_comparison:
                        findings.append(Finding("method.identity_mismatch", "Output method identity differs from the authorized method.", family, "/method_identity"))
    try:
        if phase.upper() == "P3":
            contract = json.loads((catalog.root / "contracts/phases/P3.json").read_text(encoding="utf-8"))
            _check_theory(outputs, findings, conservative="p3.conservative_assessment_v1" in contract.get("capabilities", []),
                          artifact_roots=artifact_roots)
            _check_reassessment(outputs, frozen_basis, findings)
        if phase.upper() == "P4":
            _check_empirical(outputs, findings)
            from .p4_validation import check_progressive_evaluation, progressive_evaluation_enabled
            if progressive_evaluation_enabled(catalog):
                contract = json.loads((catalog.root / "contracts/phases/P4.json").read_text(encoding="utf-8"))
                check_progressive_evaluation(outputs, findings,
                    question_appropriate="p4.question_appropriate_numerics.v1" in contract.get("capabilities", []),
                    workflow_templates="p4.workflow_templates.v1" in contract.get("capabilities", []),
                    frozen_inputs=(frozen_basis or {}).get("p4_inputs"))
        if phase.upper() == "P5":
            from .technical_reports import technical_report_enabled, validate_technical_report
            if technical_report_enabled(catalog):
                findings.extend(validate_technical_report(outputs, frozen_basis or {}, artifact_roots=artifact_roots))
            else:
                _check_manuscript(outputs, frozen_basis, findings)
        if artifact_roots:
            _check_artifacts(outputs, artifact_roots, findings,
                             progressive_p4=phase.upper() == "P4" and progressive_evaluation_enabled(catalog))
    except (KeyError, TypeError, ValueError, OSError) as error:
        # Shape findings are produced separately by Catalog. Malformed
        # member bytes must fail validation rather than crash the driver.
        findings.append(Finding("scientific.invalid_structure", f"Scientific consistency could not be checked: {error}", phase.lower(), ""))
    return findings
