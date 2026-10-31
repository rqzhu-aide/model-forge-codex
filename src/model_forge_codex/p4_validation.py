"""Deterministic links for progressive evaluation, not scientific grading."""
from __future__ import annotations

import json
import math
from collections import Counter

from .domain import Finding
from .empirical_targets import effective_protocol


def progressive_evaluation_enabled(catalog) -> bool:
    path = catalog.root / "contracts" / "phases" / "P4.json"
    try:
        return "progressive_evaluation_v1" in json.loads(path.read_text(encoding="utf-8")).get("capabilities", [])
    except (OSError, ValueError, TypeError):
        return False


def check_progressive_evaluation(outputs: dict, findings: list[Finding], *, question_appropriate=False,
                                 workflow_templates=False, frozen_inputs: dict | None = None) -> None:
    exhibits = [item for item in outputs.get("p4.exhibits", []) if isinstance(item, dict)]
    for index, exhibit in enumerate(exhibits):
        for identifier in exhibit.get("data_exhibit_ids", []):
            matches = [item for item in exhibits if item.get("exhibit_id") == identifier and item.get("kind") == "table"]
            if exhibit.get("kind") != "figure" or len(matches) != 1:
                findings.append(Finding("empirical.figure_data_reference",
                    "A figure's declared data exhibit must identify exactly one table in this exhibit record.",
                    "p4.exhibits", f"/{index}/data_exhibit_ids"))
    original = outputs.get("p4.protocol")
    if not isinstance(original, dict) or not original.get("plan_revision_id"):
        # Required progressive fields are enforced by the output-specific
        # schema. Arithmetic-only callers can still validate legacy records.
        return
    protocol = effective_protocol(original)
    if workflow_templates:
        _check_workflow_references(original, protocol, outputs, findings, frozen_inputs=frozen_inputs)

    def problem(code, message, family="p4.protocol", pointer=""):
        findings.append(Finding("empirical." + code, message, family, pointer))

    def keyed(items, key, family="p4.protocol"):
        items = [item for item in items if isinstance(item, dict)]
        counts = Counter(item.get(key) for item in items)
        if None in counts or any(count > 1 for count in counts.values()):
            problem("ambiguous_id", f"{key} must be present and unique.", family, "/" + key)
        return {item.get(key): item for item in items}

    tests = keyed(protocol.get("claim_tests", []), "test_id")
    cases = keyed(protocol.get("cases", []), "case_id")
    metrics = keyed(protocol.get("metrics", []), "metric_id")
    baselines = keyed(protocol.get("baselines", []), "baseline_id")
    items = keyed(protocol.get("work_items", []), "work_item_id")

    def located(field, added_field, id_field):
        # Effective arrays concatenate amendments; diagnostics point back to
        # the authored JSON rather than an index in that derived projection.
        entries = [(item, f"/{field}/{index}") for index, item in enumerate(original.get(field, [])) if isinstance(item, dict)]
        for index, amendment in enumerate(original.get("amendments", [])):
            if isinstance(amendment, dict):
                entries.extend((item, f"/amendments/{index}/{added_field}/{position}")
                               for position, item in enumerate(amendment.get(added_field, [])) if isinstance(item, dict))
        return {item.get(id_field): pointer for item, pointer in entries}

    question_locations = located("claim_tests", "added_tests", "test_id")
    case_locations = located("cases", "added_cases", "case_id")
    work_locations = located("work_items", "added_work_items", "work_item_id")
    revisions = {original.get("plan_revision_id")}
    prior = original.get("plan_revision_id")
    known_work = {item.get("work_item_id") for item in original.get("work_items", []) if isinstance(item, dict)}
    for index, amendment in enumerate(original.get("amendments", [])):
        if not isinstance(amendment, dict):
            continue
        revision = amendment.get("revision_id")
        if not revision or revision in revisions or amendment.get("supersedes_revision_id") != prior:
            problem("plan_revision", "Amendments must form an ordered chain of unique revisions.", pointer=f"/amendments/{index}")
        revisions.add(revision)
        prior = revision
        known_work.update(item.get("work_item_id") for item in amendment.get("added_work_items", []) if isinstance(item, dict))
        if set(amendment.get("deferred_work_item_ids", [])) - known_work:
            problem("deferred_work_reference", "Deferred work must name a declared work item.", pointer=f"/amendments/{index}")
        if "work_item_order" in amendment and set(amendment["work_item_order"]) != known_work:
            problem("work_order", "An amended work order must retain all declared work items.", pointer=f"/amendments/{index}/work_item_order")
    for identifier, item in items.items():
        for field, registry, locations, id_field in (
                ("question_ids", tests, question_locations, "test_id"),
                ("case_ids", cases, case_locations, "case_id"),
                ("depends_on", items, work_locations, "work_item_id")):
            for index, reference in enumerate(item.get(field, [])):
                if reference not in registry or field == "depends_on" and reference == identifier:
                    context = "; ".join(f"{key!r} at {pointer}/{id_field}" for key, pointer in locations.items())
                    dependency_hint = " Dependencies must name a different work item." if field == "depends_on" else ""
                    problem("work_reference", f"Work item {identifier!r} has an invalid {field} reference {reference!r}. "
                            f"Declared lookup definitions in this protocol: {context or 'none'}. "
                            + dependency_hint + " Verify the intended reference; no replacement is selected.",
                            pointer=f"{work_locations[identifier]}/{field}/{index}")
        visited = set()
        pending = list(item.get("depends_on", []))
        while pending:
            dependency = pending.pop()
            if dependency == identifier:
                problem("work_cycle", "Work dependencies contain a cycle.", pointer=f"/work_items/{identifier}")
                break
            if dependency not in visited:
                visited.add(dependency)
                pending.extend(items.get(dependency, {}).get("depends_on", []))
    if set(tests) - {qid for item in items.values() for qid in item.get("question_ids", [])}:
        problem("unscheduled_question", "Every declared question needs a scheduled or explicitly deferred work item.")
    categories = {item.get("category") for item in tests.values()}
    applicability = original.get("comparison_applicability")
    comparison_required = True
    if question_appropriate:
        if not isinstance(applicability, dict) or not isinstance(applicability.get("required"), bool) or not str(applicability.get("reason", "")).strip():
            problem("comparison_applicability", "State whether a baseline comparison is relevant to the material claims or expectations, with a reason.", pointer="/comparison_applicability")
        else:
            comparison_required = applicability["required"]
    feasibility = {"implementation", "performance"} if comparison_required else {"implementation"}
    if original.get("mode") == "p4.preliminary" and not feasibility.issubset(categories):
        problem("feasibility_questions", "Feasibility requires distinct implementation and baseline-comparison questions.", pointer="/claim_tests")
    if comparison_required and not any(
        test.get("category") == "performance"
        and "selected_method" in {case.get("comparator_id") for case in cases.values() if identifier in case.get("test_ids", [])}
        and any(case.get("comparator_id") in baselines for case in cases.values() if identifier in case.get("test_ids", []))
        for identifier, test in tests.items()
    ):
        problem("baseline_comparison", "At least one performance question must schedule separate selected-method and declared-baseline cases together; each case has one comparator identity.", pointer="/claim_tests")
    if comparison_required and not baselines:
        problem("baseline_required", "Declare a meaningful baseline and its authored rationale before evaluation.", pointer="/baselines")
    if comparison_required and not any(case.get("comparator_id") in baselines for case in cases.values()):
        problem("baseline_not_scheduled", "At least one declared case must execute a baseline comparison.", pointer="/cases")
    if not any(case.get("comparator_id") == "selected_method" for case in cases.values()):
        problem("method_not_scheduled", "Declare selected-method cases as well as baseline cases.", pointer="/cases")

    analyst = outputs.get("p4.analyst_synthesis")
    if isinstance(analyst, dict):
        family = "p4.analyst_synthesis"
        results = keyed(analyst.get("question_results", []), "question_id", family)
        if set(results) != set(tests):
            problem("question_result_coverage",
                    "Write exactly one question_result per effective protocol.claim_tests[].test_id, including "
                    "prospectively added_tests and unassessed or deferred work. Set question_id to that exact test_id "
                    "and test_ids=[test_id]; do not use aliases or merge tests. "
                    f"Expected question_id values: {json.dumps(sorted(tests, key=str))}; "
                    f"missing: {json.dumps(sorted(set(tests) - set(results), key=str))}; "
                    f"unknown: {json.dumps(sorted(set(results) - set(tests), key=str))}.",
                    family, "/question_results")
        evidence = keyed(outputs.get("p4.evidence", []), "evidence_id", "p4.evidence")
        exhibits = keyed(outputs.get("p4.exhibits", []), "exhibit_id", "p4.exhibits")
        rows = [row for row in outputs.get("p4.metrics_long", []) if isinstance(row, dict)]
        for qid, result in results.items():
            pointer = f"/question_results/{qid}"
            linked_cases = {cid for cid, case in cases.items() if qid in case.get("test_ids", [])}
            if set(result.get("test_ids", [])) != {qid} or set(result.get("case_ids", [])) != linked_cases:
                expected_scope = (
                    f"For question_id {json.dumps(qid)}, expected test_ids: {json.dumps([qid])}; "
                    f"expected case_ids: {json.dumps(sorted(linked_cases, key=str))}."
                    if qid in tests else
                    f"Unknown question_id {json.dumps(qid)}; choose one of the exact declared identifiers: "
                    f"{json.dumps(sorted(tests, key=str))} before selecting its linked cases."
                )
                problem("question_scope",
                        "Set question_id to one exact effective protocol.claim_tests[].test_id and test_ids=[test_id]. "
                        "case_ids must contain all and only cases whose test_ids includes that identifier, including "
                        "unfavorable or unrun cases. "
                        + expected_scope, family, pointer)
            if (set(result.get("metric_ids", [])) - set(metrics)
                    or set(result.get("comparator_ids", [])) - {"selected_method", *baselines}
                    or set(result.get("plan_revision_ids", [])) - revisions
                    or set(result.get("evidence_ids", [])) - set(evidence)
                    or set(result.get("exhibit_ids", [])) - set(exhibits)):
                problem("question_result_reference", "A question result contains an unresolved metric, comparator, revision, evidence or exhibit reference.", family, pointer)
            if result.get("category") != tests.get(qid, {}).get("category"):
                problem("question_category", "The result category must match its authored question.", family, pointer)
            if set(result.get("comparator_ids", [])) != {cases[cid].get("comparator_id") for cid in linked_cases}:
                problem("question_comparator_scope", "Retain all comparison identities declared for the question.", family, pointer)
            allowed_metrics = {metric for cid in linked_cases for metric in cases[cid].get("metric_ids", [])}
            if set(result.get("metric_ids", [])) - allowed_metrics:
                problem("question_metric_scope", "A displayed metric must belong to a case answering this question.", family, pointer)
            for eid in result.get("evidence_ids", []):
                item = evidence.get(eid, {})
                if item.get("test_ids") and qid not in item["test_ids"]:
                    problem("question_evidence_scope", "The cited evidence belongs to another question.", family, pointer)
            for eid in result.get("exhibit_ids", []):
                exhibit = exhibits.get(eid, {})
                if exhibit.get("test_ids") and qid not in exhibit["test_ids"]:
                    problem("question_exhibit_scope", "The cited exhibit belongs to another question.", family, pointer)
            all_observed = [row for row in rows if row.get("case_id") in linked_cases]
            observed = [row for row in all_observed if row.get("eligibility") != "invalidated"]
            if {row["plan_revision_id"] for row in observed if row.get("plan_revision_id")} - set(result.get("plan_revision_ids", [])):
                problem("question_revision_scope", "Name every plan revision supplying observed results for this question.", family, pointer)
            counts = {"planned": sum(len(cases[cid].get("replicates", [])) for cid in linked_cases),
                      **{status: sum(row.get("status") == status for row in observed)
                         for status in ("completed", "failed", "not_run")}}
            invalidated = len(all_observed) - len(observed)
            if invalidated or "invalidated" in result.get("observed_counts", {}):
                counts["invalidated"] = invalidated
            if result.get("observed_counts") != counts:
                problem("question_count_mismatch", "Question counts must match the complete declared replicate scope.", family, pointer + "/observed_counts")
            standard_metrics = {identifier for identifier, metric in metrics.items()
                                if (metric.get("summary") or {}).get("aggregation") in {"mean", "median", "sum", "identity"}}
            inline_rows = [row for row in (outputs.get("p4.diagnostics") or {}).get("headline_numbers", [])
                           if isinstance(row, dict) and row.get("case_id") in linked_cases
                           and row.get("metric") in set(result.get("metric_ids", [])) & standard_metrics
                           and isinstance(row.get("estimate"), (int, float)) and not isinstance(row.get("estimate"), bool)
                           and math.isfinite(row["estimate"])]
            comparison_cases = {row.get("case_id") for row in observed
                                if tests.get(qid, {}).get("category") == "performance"
                                and row.get("status") == "completed"
                                and cases[row["case_id"]].get("comparator_id") == "selected_method"
                                and cases[row["case_id"]].get("replication_unit") == "independent_dataset"
                                and row.get("replicate_id") in {item.get("replicate_id")
                                    for item in cases[row["case_id"]].get("replicates", [])}}
            linked_exhibit = bool(result.get("exhibit_ids"))
            if comparison_cases:
                # Generic supplementary sources do not supply an inline result.
                # Exact diagnostic rows already checked against observations do.
                linked_exhibit = any(exhibits.get(eid, {}).get("kind") in {"table", "figure"}
                                     and (not exhibits[eid].get("case_ids")
                                          or bool(set(exhibits[eid]["case_ids"]) & comparison_cases))
                                     for eid in result.get("exhibit_ids", []))
                inline_rows = [row for row in (outputs.get("p4.diagnostics") or {}).get("headline_numbers", [])
                               if isinstance(row, dict) and row.get("case_id") in comparison_cases
                               and row.get("metric") in set(result.get("metric_ids", [])) & standard_metrics]
            if counts["completed"] and result.get("outcome") != "not_evaluated" and not linked_exhibit and not inline_rows:
                problem("question_exhibit_missing", "A completed quantitative answer needs a linked verified exhibit or an exact independently recomputed inline result table.", family, pointer + "/exhibit_ids")

    lead = outputs.get("p4.empirical_synthesis_candidate")
    if isinstance(lead, dict):
        family = "p4.empirical_synthesis_candidate"
        relation = (lead.get("decision_summary") or {}).get("theory_relation") or {}
        named = set(relation.get("statement_ids", []))
        declared = {sid for test in tests.values() for sid in test.get("target_statement_ids", [])}
        if named - declared:
            problem("theory_relation_reference", "The overview names a theory statement outside the declared empirical questions.", family, "/decision_summary/theory_relation/statement_ids")
        if relation.get("status") == "tested":
            completed_cases = {row.get("case_id") for row in outputs.get("p4.metrics_long", [])
                               if row.get("status") == "completed" and row.get("eligibility") != "invalidated"}
            observed_statements = {sid for cid, case in cases.items() if cid in completed_cases
                                   for qid in case.get("test_ids", []) for sid in tests.get(qid, {}).get("target_statement_ids", [])}
            if named - observed_statements:
                problem("theory_relation_unperformed", "A claim described as empirically tested needs a completed declared case.", family, "/decision_summary/theory_relation")
        reviews = keyed(lead.get("question_reviews", []), "question_id", family)
        if set(reviews) != set(tests):
            problem("question_review_coverage",
                    "Write exactly one question_review per effective protocol.claim_tests[].test_id, including "
                    "prospectively added_tests and unassessed work. Use the analyst's exact protocol test_id as "
                    "question_id; do not use aliases or merge tests. "
                    f"Expected question_id values: {json.dumps(sorted(tests, key=str))}; "
                    f"missing: {json.dumps(sorted(set(tests) - set(reviews), key=str))}; "
                    f"unknown: {json.dumps(sorted(set(reviews) - set(tests), key=str))}.", family, "/question_reviews")
        for index, row in enumerate((lead.get("decision_summary") or {}).get("coverage", [])):
            if set(row.get("question_ids", [])) - set(tests):
                problem("decision_question_reference",
                        "Decision coverage question_ids must use exact effective protocol.claim_tests[].test_id "
                        "values, including prospectively added_tests, without aliases. "
                        f"Expected identifiers: {json.dumps(sorted(tests, key=str))}; "
                        f"unknown: {json.dumps(sorted(set(row.get('question_ids', [])) - set(tests), key=str))}.",
                        family, f"/decision_summary/coverage/{index}")


def _check_workflow_references(original, protocol, outputs, findings, *, frozen_inputs=None):
    """Resolve declared sources and final disposition, without grading scientific prose.

    Schema validation owns field shapes. These checks add exact identity and
    eligible-completion links. A missing frozen manifest means input membership
    was not checked, rather than assuming that no dataset was supplied.
    """
    def objects(value):
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    def problem(code, message, family="p4.protocol", pointer=""):
        findings.append(Finding("empirical." + code, message, family, pointer))

    source_entries = [(source, f"/data_sources/{index}")
                      for index, source in enumerate(objects(original.get("data_sources")))]
    known = {source.get("data_source_id") for source, _ in source_entries}

    def check_cases(cases, prefix):
        for index, case in enumerate(objects(cases)):
            unknown = set(case.get("data_source_ids", [])) - known
            if unknown:
                problem("case_source_reference", "Case sources must be declared in the original plan or in the same or an earlier prospective amendment. "
                        f"Unknown source IDs: {json.dumps(sorted(unknown, key=str))}.",
                        pointer=f"{prefix}/{index}/data_source_ids")

    check_cases(original.get("cases"), "/cases")
    for index, amendment in enumerate(objects(original.get("amendments"))):
        additions = [(source, f"/amendments/{index}/added_data_sources/{position}")
                     for position, source in enumerate(objects(amendment.get("added_data_sources")))]
        source_entries.extend(additions)
        known.update(source.get("data_source_id") for source, _ in additions)
        check_cases(amendment.get("added_cases"), f"/amendments/{index}/added_cases")
    counts = Counter(source.get("data_source_id") for source, _ in source_entries)
    for source, pointer in source_entries:
        if counts[source.get("data_source_id")] != 1:
            problem("source_ambiguous_id", "Source IDs must be unique across the original plan and prospective additions; never redefine an earlier source.",
                    pointer=pointer + "/data_source_id")
    sources = {source.get("data_source_id"): source for source, _ in source_entries}
    inputs = {row.get("input_id"): row for row in objects((frozen_inputs or {}).get("inputs"))}
    dataset_ids = {identifier for identifier, row in inputs.items() if row.get("role") == "dataset"}
    actual_origins = {"researcher_observed", "external_data"}
    actual_sources = {identifier for identifier, source in sources.items() if source.get("origin") in actual_origins}
    if frozen_inputs is not None:
        for source, pointer in source_entries:
            identifiers = set(source.get("input_ids", []))
            if identifiers - set(inputs):
                problem("source_input_reference", "A declared input_id must identify bytes selected and frozen for this run; a newly supplied dataset needs a new frozen run input.",
                        pointer=pointer + "/input_ids")
            if source.get("origin") in actual_origins and not identifiers & dataset_ids:
                problem("source_dataset_reference", "Observed/external data must reference at least one selected frozen input whose role is dataset.",
                        pointer=pointer + "/input_ids")

    cases = {case.get("case_id"): case for case in objects(protocol.get("cases"))}
    tests = {test.get("test_id") for test in objects(protocol.get("claim_tests"))}
    completed = {row.get("case_id") for row in objects(outputs.get("p4.metrics_long"))
                 if row.get("status") == "completed" and row.get("eligibility") != "invalidated"
                 and row.get("case_id") in cases
                 and row.get("replicate_id") in {replicate.get("replicate_id")
                     for replicate in objects(cases[row["case_id"]].get("replicates"))}}
    selected_actual_cases = {identifier: case for identifier, case in cases.items()
                             if case.get("comparator_id") == "selected_method"
                             and set(case.get("data_source_ids", [])) & actual_sources}
    analyst = outputs.get("p4.analyst_synthesis")
    account = analyst.get("actual_data_application") if isinstance(analyst, dict) else None
    if isinstance(account, dict):
        family = "p4.analyst_synthesis"
        pointer = "/actual_data_application"
        source_ids = set(account.get("data_source_ids", []))
        question_ids = set(account.get("question_ids", []))
        if source_ids - actual_sources:
            problem("actual_data_source_reference", "Actual-data disposition source IDs must resolve to declared researcher-observed or external-data sources.",
                    family, pointer + "/data_source_ids")
        if question_ids - tests:
            problem("actual_data_question_reference", "Actual-data disposition questions must use exact effective protocol test IDs.",
                    family, pointer + "/question_ids")
        related_cases = {identifier: case for identifier, case in selected_actual_cases.items()
                         if set(case.get("data_source_ids", [])) & source_ids}
        linked_questions = {qid for case in related_cases.values() for qid in case.get("test_ids", [])}
        if question_ids - linked_questions:
            problem("actual_data_question_scope", "Each cited actual-data question needs a selected-method case linked to one of the cited actual-data sources.",
                    family, pointer + "/question_ids")
        status = account.get("status")
        if status == "not_supplied" and (dataset_ids or actual_sources):
            problem("actual_data_absence_mismatch", "Actual data was selected or declared, so its final disposition cannot be not_supplied. Record analyzed or supplied_not_analyzed with scope or omission reason.",
                    family, pointer + "/status")
        if status == "analyzed":
            supporting_cases = {identifier for identifier, case in related_cases.items()
                                if set(case.get("test_ids", [])) & question_ids}
            if not supporting_cases & completed:
                problem("actual_data_unperformed", "Analyzed actual-data status requires a completed eligible planned selected-method replicate linked to its cited data and question.",
                        family, pointer + "/status")
        if status == "supplied_not_analyzed" and set(selected_actual_cases) & completed:
            problem("actual_data_omission_mismatch", "A selected-method actual-data case has an eligible completed result; explain its performed scope using analyzed status.",
                    family, pointer + "/status")

    lead = outputs.get("p4.empirical_synthesis_candidate")
    summary = lead.get("decision_summary") if isinstance(lead, dict) else None
    if isinstance(summary, dict):
        exhibits = objects(outputs.get("p4.exhibits"))
        for index, identifier in enumerate(summary.get("headline_exhibit_ids", [])):
            matches = [exhibit for exhibit in exhibits if exhibit.get("exhibit_id") == identifier]
            if len(matches) != 1 or matches[0].get("kind") not in {"table", "figure"}:
                problem("headline_exhibit_reference", "Each headline must reference exactly one table or figure in this evaluation's exhibit manifest. Existing artifact checks verify its retained bytes.",
                        "p4.empirical_synthesis_candidate", f"/decision_summary/headline_exhibit_ids/{index}")
        for row_index, row in enumerate(objects(summary.get("coverage"))):
            for index, identifier in enumerate(row.get("exhibit_ids", [])):
                matches = [exhibit for exhibit in exhibits if exhibit.get("exhibit_id") == identifier]
                if len(matches) != 1 or matches[0].get("kind") not in {"table", "figure"}:
                    problem("coverage_exhibit_reference", "Each topic exhibit must reference exactly one table or figure in this evaluation's exhibit manifest. Existing artifact checks verify its retained bytes.",
                            "p4.empirical_synthesis_candidate", f"/decision_summary/coverage/{row_index}/exhibit_ids/{index}")
