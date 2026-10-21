#!/usr/bin/env python3
"""Seed a scratch demo home using the current repository workflow catalog.

Reuses the repo's own test helpers (golden contract examples scripted into
the fake bridge) so every phase publishes through the real engine and
validation path: a P1 literature update, a P2 full-catalog run whose
proposals carry computational profiles and whose assessment carries
modification options, then P3 theory and P4 preliminary evidence on the
activated method branch. Deletes and recreates C:\\tmp\\mfc-demo unless
MFC_DEMO_HOME explicitly selects a different scratch directory.
"""
import asyncio
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.members import provision_team
from model_forge_codex.methods import activate_method
from model_forge_codex.runs import RunEngine
from model_forge_codex.storage import read_json, write_json_atomic

from test_researcher_workbench_engine import publish, script_scientific_run
from test_direct_workflow import p1_documents

# The seeder wipes and recreates ROOT. Never point it at a live data home —
# use a scratch directory. Override with MFC_DEMO_HOME if needed.
ROOT = Path(os.environ.get("MFC_DEMO_HOME", r"C:\tmp\mfc-demo"))
PROJECT_ID = "project.test"  # the test helpers hardcode this id


async def drive(eng, project, branch, phase, mode, **kw):
    script_scientific_run(eng, project, branch, phase, mode, **kw)
    r = await eng.start_run(PROJECT_ID, phase=phase, mode=mode, branch_id=branch)
    await eng._tasks[r.run_id]
    final = eng.load_run(PROJECT_ID, r.run_id)
    print(f"{phase} {mode}: {final.state.value} {final.terminal_reason or ''}")
    for attempt in final.findings_history:
        for f in attempt:
            if f.get("blocks_publication"):
                print("  blocking:", f.get("code"), (f.get("message") or "")[:140], f.get("object_id"))
    return final


async def main():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    project = ROOT / "projects" / PROJECT_ID
    project.mkdir(parents=True)
    write_json_atomic(project / "project.json", {
        "project_id": PROJECT_ID,
        "name": "adaptive-search-df",
        "research_question": "Adaptive search degrees of freedom in random forests",
    })
    shutil.copytree(REPO / "contracts", project / "contracts")
    provision_team(project)
    method = read_json(REPO / "contracts/examples/method.example.json")
    publish(project, "trunk", "P1", {"literature_synthesis": {"headline": "Frozen literature"}})
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [method]}})
    branch = activate_method(project, method["identity"]["stable_id"])["branch_id"]
    print("method branch:", branch)
    eng = RunEngine(ROOT, FakeCodexBridge())

    def current_literature(outputs):
        outputs.clear()
        outputs.update(p1_documents())
        outputs["p1.research_basis"]["phase2_preparation"].pop("supplied_method", None)

    await drive(eng, project, "trunk", "P1", "p1.literature_update", transform=current_literature)
    await drive(eng, project, "trunk", "P2", "p2.full_catalog")
    await drive(eng, project, branch, "P3", "p3.theory_establishment")
    await drive(eng, project, branch, "P4", "p4.preliminary")


asyncio.run(main())
print("seeded at", ROOT)
