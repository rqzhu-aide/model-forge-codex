"""P1 recency guidance is anchored to the frozen run date for every member."""
import asyncio

import pytest

from model_forge_codex import runs
from test_direct_workflow import PID, direct_engine


@pytest.mark.parametrize("started_at, through_month", [
    ("2026-09-11T05:00:00.000Z", "2026-09"),
    ("2027-01-02T05:00:00.000Z", "2027-01"),
    ("2028-02-29T05:00:00.000Z", "2028-02"),
])
async def test_all_p1_briefs_keep_run_date_and_recent_search_scope(
    direct_engine, monkeypatch, started_at, through_month,
):
    engine, _ = direct_engine

    async def hold_run(_record, _stages):
        await asyncio.Event().wait()

    monkeypatch.setattr(engine, "_drive", hold_run)
    monkeypatch.setattr(runs, "_now", lambda: started_at)
    record = await engine.start_run(PID, phase="P1", mode="p1.literature_update", branch_id="trunk")
    directory = engine.run_dir(PID, record.run_id)
    # A later stage or correction must retain the original search reference date.
    monkeypatch.setattr(runs, "_now", lambda: "2030-12-31T23:59:59.000Z")
    try:
        briefs = [engine._render_brief(record, stage, role, directory)
                  for stage in engine._stages(record) for role in stage.roles]
        assert len(briefs) == 4
        for brief in briefs:
            assert f"Run date: {started_at[:10]}" in brief
            assert "Prioritize developments from more recent years" in brief
            assert "rolling three-year window" not in brief
            assert "rolling five-year window" not in brief
            assert f"current-year work through {through_month}" in brief
            assert "2030-12-31" not in brief
            assert "keywords, references and citing papers around recent work" in brief
            assert "This is a priority, not a cutoff." in brief
            assert "Retain older classical and foundational results" in brief
            assert "Use reliable sources, prioritizing primary research papers and authoritative publication sources" in brief
            assert "Verify citation details and identify preprints and publication status accurately" in brief
            assert "Preserve cumulative source identities and provenance" in brief
            assert "search_scope, coverage_limits and reading_extent" in brief
            assert "refer to sources by author/year" in brief
            assert "descriptive titles or question wording" in brief
            assert "Keep exact internal IDs in structured support/reference fields or technical references" in brief
            assert "rather than using them as prose citations" in brief
            assert "Each author supplies exact supported mathematics" in brief
            assert "method development belongs in P2" in brief
        assert engine.bridge.turns == []
    finally:
        await engine.cancel(PID, record.run_id)
