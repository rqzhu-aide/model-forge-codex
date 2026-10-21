"""Exhaustive numerical diagnostics retain validation and file-based delivery."""
import copy
import hashlib
import json

from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole, StageSpec
from model_forge_codex.storage import sha256_file
from model_forge_codex.validation import recompute_diagnostics
from test_draft_validation import REPO, draft_engine, run, write_outputs
from test_researcher_workbench_engine import scientific_output_documents


def test_large_required_diagnostics_are_advisory_and_opened_by_exact_file(draft_engine):
    engine = draft_engine
    record, stages, identity = run(engine, "P4", "p4.preliminary")
    stage = stages[0]
    documents, files = scientific_output_documents(Catalog(REPO / "contracts"), "P4", identity)
    protocol, rows = documents["p4.protocol"], documents["p4.metrics_long"]
    template = copy.deepcopy(protocol["cases"][0])
    metric = copy.deepcopy(protocol["metrics"][0])
    source_rows = [copy.deepcopy(row) for row in rows if row["case_id"] == template["case_id"]]
    metric_ids = [f"metric.diagnostic_{index:02}" for index in range(32)]
    protocol["metrics"].extend({**copy.deepcopy(metric), "metric_id": name} for name in metric_ids)
    for index in range(24):
        case = {**copy.deepcopy(template), "case_id": f"case.diagnostic_{index:02}", "metric_ids": metric_ids}
        protocol["cases"].append(case)
        protocol["work_items"][0]["case_ids"].append(case["case_id"])
        for row in source_rows:
            rows.append({**copy.deepcopy(row), "case_id": case["case_id"],
                         "metrics": {name: row["metrics"][metric["metric_id"]] for name in metric_ids}})
    computed = recompute_diagnostics(protocol, rows)
    for item in computed["headline_numbers"]:
        item.pop("aggregation")
    for item in computed["stability"]:
        item["assessment"] = "assessed" if item["n_seeds"] >= 2 else "not_applicable"
    diagnostics = documents["p4.diagnostics"]
    diagnostics.update(computed)
    diagnostics["provenance"] = {
        "protocol_sha256": hashlib.sha256(json.dumps(protocol).encode()).hexdigest(),
        "metrics_sha256": hashlib.sha256("\n".join(json.dumps(row) for row in rows).encode()).hexdigest(),
        "script_sha256": hashlib.sha256(files[diagnostics["regenerated_by"]].encode()).hexdigest()}
    selected = {"p4.protocol": protocol, "p4.metrics_long": rows, "p4.diagnostics": diagnostics}
    directory = engine.run_dir(record.project_id, record.run_id) / "outputs" / stage.stage_id
    write_outputs(directory, selected, {diagnostics["regenerated_by"]: files[diagnostics["regenerated_by"]],
                                        "fixture_source.json": files["fixture_source.json"]})
    minimum = [{key: item[key] for key in ("case_id", "metric", "estimate", "uncertainty_kind")}
               for item in diagnostics["headline_numbers"]]
    assert len(json.dumps(minimum, separators=(",", ":")).encode()) > 32768

    def validate():
        return engine._validate_run_outputs(record, [stage], scoped_outputs=set(selected))

    findings = validate()
    assert not [finding for finding in findings if finding.blocks_publication], findings
    warning = next(finding for finding in findings if finding.code == "output.size_cap_exceeded"
                   and finding.object_id == "p4.diagnostics")
    assert not warning.blocks_publication
    sections = engine._same_run_sections(record, stages[1], MemberRole.THEORIST)
    assert "### `p4.diagnostics`" not in "\n".join(sections["packets"])
    path = directory / "diagnostics.json"
    assert str(path) in "\n".join(sections["instructed"])
    assert sha256_file(path) in "\n".join(sections["instructed"])
    # Another recipient with neither an audience entry nor a required read gets no payload.
    observer = StageSpec("p4.observer", stages[1].sequence, "serial", (MemberRole.OUTSIDE_REVIEWER,), ())
    outsider = engine._same_run_sections(record, observer, MemberRole.OUTSIDE_REVIEWER)
    assert "p4.diagnostics" not in "\n".join(outsider["packets"] + outsider["instructed"])
    current = engine._same_run_sections(record, stage, MemberRole.DATA_ANALYST)
    assert "p4.diagnostics" not in str(current)

    diagnostics["headline_numbers"][0]["estimate"] += 1
    write_outputs(directory, {"p4.diagnostics": diagnostics})
    assert any(finding.code == "diagnostics.aggregate_mismatch" and finding.blocks_publication
               for finding in validate())
    protocol["cases"][0]["metric_ids"].append("metric.undeclared")
    write_outputs(directory, {"p4.protocol": protocol})
    assert any(finding.code == "empirical.case_reference" and finding.blocks_publication
               for finding in validate())
