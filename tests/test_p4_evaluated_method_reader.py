"""A reader must show the definition evaluated in that publication."""
import copy
import json

from model_forge_codex.records import publish_package
from model_forge_codex.research import artifacts_view
from model_forge_codex.research_sources import evaluated_method_projection
from model_forge_codex.storage import sha256_bytes, write_json_atomic


def snapshot(version=1):
    identity = {"stable_id": "method.example", "version": version, "definition_sha256": str(version) * 64}
    source = {"branch": "trunk", "phase": "P2", "family": "method_catalog",
              "generation_id": f"generation.method{version}", "sha256": "a" * 64}
    return {"identity": identity, "source_ref": source, "definition": {
        "identity": identity, "title": f"Evaluated model {version}",
        "summary": rf"Frozen model {version}: $Y=X\beta+\epsilon$.",
        "mathematical_definition": {"canonical_definition": {
            "target_or_estimand": {"definition": r"Target $\beta=E(XX^T)^{-1}E(XY)$."},
            "objective_or_estimating_equation": {"definition": r"Fit $$\hat\beta=\arg\min_b\sum_i(y_i-x_i^Tb)^2.$$"}}}}}


def publish(project, method, run):
    document = {"method_identity": method["identity"], "decision_summary": {"conclusion_markdown": "Recorded conclusion."}}
    return publish_package(project / "branches/method.example/phases/p4",
                           {"empirical_synthesis": json.dumps(document).encode()},
                           phase="P4", branch_id="method.example", run_id=run, metadata={"method": method})


def test_each_published_evaluation_keeps_its_own_frozen_math(tmp_path):
    first, second = snapshot(1), snapshot(2)
    publish(tmp_path, first, "run.first")
    publish(tmp_path, second, "run.second")
    view = artifacts_view(tmp_path, "method.example")
    current = view["empirical_summaries"][0]["evaluated_method"]
    earlier = view["prior_evaluations"][0]["artifacts"]["empirical_summaries"][0]["evaluated_method"]
    assert current["summary"] == second["definition"]["summary"]
    assert earlier["summary"] == first["definition"]["summary"]
    assert earlier["source_ref"] == first["source_ref"]
    assert current["objective_markdown"] == second["definition"]["mathematical_definition"]["canonical_definition"]["objective_or_estimating_equation"]["definition"]


def test_retained_legacy_evaluation_uses_its_own_basis_before_later_metadata(tmp_path):
    frozen = snapshot()
    later = copy.deepcopy(frozen)
    later["definition"]["summary"] = "Later editorial account of the same method."
    later["source_ref"]["generation_id"] = "generation.later-editorial"
    write_json_atomic(tmp_path / "runs/run.legacy/basis.json", {"method": frozen})
    store = tmp_path / "branches/method.example/phases/p4"
    document = {"method_identity": frozen["identity"],
                "decision_summary": {"conclusion_markdown": "Legacy evaluation."}}
    data = json.dumps(document).encode()
    generation = store / "empirical_synthesis/generations/generation.legacy.json"
    generation.parent.mkdir(parents=True)
    generation.write_bytes(data)
    pointer = {"generation_id": "generation.legacy", "content_sha256": sha256_bytes(data),
               "run_id": "run.legacy"}
    write_json_atomic(store / "empirical_synthesis/current.json", pointer)
    publish_package(store, {"empirical_synthesis": json.dumps(document).encode()},
                    phase="P4", branch_id="method.example", run_id="run.later",
                    metadata={"method": later, "prior_evidence": [
                        {**pointer, "branch": "method.example", "phase": "P4",
                         "family": "empirical_synthesis"}]})

    view = artifacts_view(tmp_path, "method.example")
    current = view["empirical_summaries"][0]["evaluated_method"]
    earlier = view["prior_evaluations"][0]["artifacts"]["empirical_summaries"][0]["evaluated_method"]
    assert current["summary"] == later["definition"]["summary"]
    assert earlier["summary"] == frozen["definition"]["summary"]
    assert earlier["source_ref"] == frozen["source_ref"]


def test_missing_package_can_use_exact_run_basis_not_current_method(tmp_path):
    frozen = snapshot()
    write_json_atomic(tmp_path / "runs/run.old/basis.json", {"method": frozen})
    result = evaluated_method_projection(tmp_path, {"method_identity": frozen["identity"]},
                                         {"run_id": "run.old", "branch": "method.example", "package_id": "package.missing"})
    assert result["summary"] == frozen["definition"]["summary"]
    assert result["target_markdown"].startswith("Target")


def test_mismatched_snapshot_cannot_substitute_newer_math(tmp_path):
    earlier, newer = snapshot(1), snapshot(2)
    assert evaluated_method_projection(tmp_path, {"method_identity": earlier["identity"]}, {}, {"method": newer}) is None
    mixed = copy.deepcopy(earlier)
    mixed["definition"] = newer["definition"]
    assert evaluated_method_projection(tmp_path, {"method_identity": earlier["identity"]}, {}, {"method": mixed}) is None


def test_projection_does_not_mutate_or_scrape_the_authored_definition(tmp_path):
    frozen = snapshot()
    original = copy.deepcopy(frozen)
    frozen["definition"]["mathematical_definition"] = "A legacy account with $x$ but no named components."
    result = evaluated_method_projection(tmp_path, {"method_identity": frozen["identity"]}, {}, {"method": frozen})
    assert result["objective_markdown"] == result["target_markdown"] == ""
    result["identity"]["version"] = 99
    result["source_ref"]["sha256"] = "changed"
    assert frozen["identity"] == original["identity"]
    assert frozen["source_ref"] == original["source_ref"]
