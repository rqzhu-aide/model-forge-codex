"""New recap and notation remain literal, source-backed published fields."""
from model_forge_codex.research import artifacts_view
from test_p4_run_sources import retained_sources


def test_recap_and_notation_projection_keep_exact_text_and_generation(tmp_path):
    run, docs, records, uris, _ = retained_sources(tmp_path, presentation=True)
    summary = artifacts_view(tmp_path, "method.a")["empirical_summaries"][0]
    assert summary["decision_summary"] == docs["empirical_synthesis"]["decision_summary"]
    assert summary["generation_ref"] == records["empirical_synthesis"][1]["generation_ref"]
    links = {item["uri"]: item for item in summary["run_sources"]}
    for uri in uris:
        assert links[uri]["source_verified"]
        assert links[uri]["producing_run_id"] == run.name


def test_legacy_summary_gains_no_inferred_recap_or_notation(tmp_path):
    retained_sources(tmp_path)
    summary = artifacts_view(tmp_path, "method.a")["empirical_summaries"][0]["decision_summary"]
    assert "method_recap_markdown" not in summary
    assert "notation_markdown" not in summary
