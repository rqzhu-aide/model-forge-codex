import shutil
import json
import runpy
from pathlib import Path

import pytest

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.members import provision_team
from model_forge_codex.methods import activate_method
from model_forge_codex.runs import RunEngine
from model_forge_codex.storage import write_json_atomic, sha256_file, read_json

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "contracts"
GOLDENS = CATALOG / "examples"
LEGACY = REPO / "tests" / "fixtures" / "catalog-v1.3"


def use_legacy_p5_catalog(catalog_root):
    """Explicit manuscript workflow with current strict retained-source schemas.

    The pre-report P5 declaration is retained as a test fixture. This profile
    adds frozen instruction delivery and reader objectives tested by the later
    manuscript implementation; it does not change the actual revised catalog.
    """
    catalog_root = Path(catalog_root)
    contract = read_json(REPO / "tests/fixtures/legacy-p5-contract.json")
    write_json_atomic(catalog_root / "contracts/phases/P5.json", contract)
    registry_path = catalog_root / "contracts/phases.json"
    registry = read_json(registry_path)
    registry["contracts"] = [contract if row["phase_id"] == "P5" else row for row in registry["contracts"]]
    write_json_atomic(registry_path, registry)
    runpy.run_path(str(REPO / "contracts/refresh_manifest.py"))["refresh"](catalog_root)
    from model_forge_codex.catalog import Catalog
    return Catalog(catalog_root)


@pytest.fixture
def legacy_p5_catalog(tmp_path):
    root = tmp_path / "legacy-p5-catalog"
    shutil.copytree(CATALOG, root)
    return use_legacy_p5_catalog(root)


@pytest.fixture
def legacy_p5_workbench(workbench):
    engine, project, branch = workbench
    use_legacy_p5_catalog(project / "contracts")
    return engine, project, branch


@pytest.fixture
def golden():
    def read(name: str) -> str:
        source = LEGACY / "examples" / name
        return (source if source.is_file() else GOLDENS / name).read_text(encoding="utf-8")

    return read


@pytest.fixture
def engine(tmp_path):
    data_root = tmp_path / "mf-codex"
    project_id = "project.demo"
    project_dir = data_root / "projects" / project_id
    project_dir.mkdir(parents=True)
    write_json_atomic(
        project_dir / "project.json",
        {"project_id": project_id, "name": "demo",
         "research_question": "Does the estimator track Monte Carlo ground truth?"},
    )
    # Pin-sync the universal catalog into the project (ADR-007).
    shutil.copytree(CATALOG, project_dir / "contracts")
    # Historical harness fixtures deliberately retain their actual old schema
    # shapes. New contract and workbench tests use the current catalog directly.
    shutil.copytree(LEGACY / "schemas", project_dir / "contracts" / "schemas", dirs_exist_ok=True)
    shutil.copytree(LEGACY / "contracts", project_dir / "contracts" / "contracts", dirs_exist_ok=True)
    # P4 did not previously have an overlay file. Keep this historical harness
    # on its original single-turn semantics as the installed catalog evolves.
    p4_path = project_dir / "contracts" / "contracts" / "phases" / "P4.json"
    p4 = read_json(p4_path)
    p4.pop("capabilities", None)
    for output in p4.get("run_local_outputs", []):
        if output.get("schema_uri", "").endswith("p4-progressive-protocol.schema.json"):
            output["schema_uri"] = "architecture/schemas/empirical-protocol.schema.json"
        elif output.get("schema_uri", "").endswith(("p4-analyst-synthesis.schema.json", "p4-lead-synthesis.schema.json")):
            output["schema_uri"] = "architecture/schemas/scientific-record.schema.json"
    write_json_atomic(p4_path, p4)
    registry_path = project_dir / "contracts" / "contracts" / "phases.json"
    registry = read_json(registry_path)
    registry["contracts"] = [
        read_json(project_dir / "contracts" / "contracts" / "phases" / f"{phase['phase_id']}.json")
        for phase in registry["contracts"]
    ]
    write_json_atomic(registry_path, registry)
    pin = read_json(project_dir / "contracts" / "catalog-pin.json")
    write_json_atomic(project_dir / "contracts" / "catalog-pin.json", {**pin, "catalog_version": "1.3.0"})
    provision_team(project_dir)
    seed_trunk_through_p3(project_dir)
    bridge = FakeCodexBridge()
    return RunEngine(data_root, bridge), bridge, project_id


def seed_trunk_through_p3(project_dir: Path) -> None:
    """Readable exact sources plus a real selected method, not fake pointers."""
    method = json.loads((GOLDENS / "method.example.json").read_text(encoding="utf-8"))
    method["identity"]["stable_id"] = "method.demo"
    for branch, phase, name, document in (
        ("trunk", "p1", "seed_record", {"headline": "Seed literature"}),
        ("trunk", "p2", "method_catalog", {"methods": [method]}),
        ("method.demo", "p3", "seed_record", {"method_identity": method["identity"], "headline": "Seed theory"}),
    ):
        family = project_dir / "branches" / branch / "phases" / phase / name
        family.mkdir(parents=True, exist_ok=True)
        generation = family / "generations" / f"generation.seed.{phase}.json"
        write_json_atomic(generation, document)
        write_json_atomic(
            family / "current.json",
            {
                "generation_id": f"generation.seed.{phase}",
                "content_sha256": sha256_file(generation),
                "published_at": "2026-09-01T00:00:00Z",
            },
        )
    activate_method(project_dir, "method.demo")


async def settle(engine: RunEngine, run_id: str):
    task = engine._tasks[run_id]
    await task


_T1_CARD = {
    "card_id": "card.test.1",
    "subject_ref": "method.test",
    "title": "Test Method",
    "innovation": "x",
    "definition": "y = x",
    "evaluation": "preliminary",
    "created_at": "2026-09-01T00:00:00Z",
}
_T2S = {
    "summary_id": "t2s.test.1",
    "phase": "P1",
    "headline": "test summary",
    "evaluation_markdown": "ok",
    "created_at": "2026-09-01T00:00:00Z",
}


def spec_extras(*families: str) -> dict[str, str]:
    """Minimal valid payloads for the SPEC artifact outputs added in
    contracts v1.2.0 (paper_cards / method_cards / phase_summary /
    revision_account), so staged scripts stay focused on their subject."""
    import json as _json

    out: dict[str, str] = {}
    for fam in families:
        suffix = fam.split(".", 1)[-1]  # files are named <suffix>.json
        if fam.endswith(("paper_cards", "method_cards")):
            out[f"{suffix}.json"] = _json.dumps([_T1_CARD])
        elif fam.endswith(("phase_summary", "revision_account")):
            doc = dict(_T2S)
            doc["phase"] = fam.split(".")[0].upper()
            out[f"{suffix}.json"] = _json.dumps(doc)
        elif suffix == "claim_map":
            out["claim_map.json"] = _json.dumps({"claims": []})
        elif suffix == "falsification_log":
            out["falsification_log.json"] = _json.dumps({"probes": []})
        elif suffix == "metrics_long":
            out["metrics_long.jsonl"] = _json.dumps({
                "case_id": "case.test", "seed": 1, "runtime_ms": 12.5,
                "solver_status": "ok", "converged": True, "metrics": {"J": 1.0},
            }) + "\n"
        elif suffix == "diagnostics":
            out["diagnostics.json"] = _json.dumps({
                "diagnostics_id": "diag.test.1",
                "headline_numbers": [
                    {"case_id": "case.test", "metric": "J", "estimate": 1.0, "mcse": 0.01}
                ],
                "stability": [
                    {"case_id": "case.test", "metric": "J", "mean": 1.0,
                     "sd": 0.01, "n_seeds": 8, "seed_flip": False}
                ],
                "solver_health": [
                    {"regime": "all", "n_runs": 8, "n_failures": 0, "failure_rate": 0.0}
                ],
                "runtime": {"total_ms": 100.0,
                            "per_case": [{"case_id": "case.test", "mean_ms": 12.5, "max_ms": 12.5}]},
                "regenerated_by": "make_diagnostics.py",
                "environment": {"python": "3.11", "platform": "test"},
            })
            out["make_diagnostics.py"] = "# regeneration script (D22)\n"
        elif suffix == "exhibits":
            import hashlib as _hl
            svg = "<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'/>"
            out["exhibits.json"] = _json.dumps([{
                "exhibit_id": "exhibit.test.fig1", "kind": "figure",
                "title": "Test figure", "caption": "A test exhibit.",
                "artifact_path": "figures/fig1.svg",
                "artifact_sha256": _hl.sha256(svg.encode()).hexdigest(),
                "media_type": "image/svg+xml", "figure_kind": "other",
            }])
            out["figures/fig1.svg"] = svg
        else:  # pragma: no cover - guard against typos
            raise ValueError(fam)
    return out
