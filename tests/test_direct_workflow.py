"""Exercise the direct P1/P2 artifacts through actual orchestration and API."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.catalog import Catalog
from model_forge_codex.direct_validation import validate_direct_outputs
from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.members import provision_team
from model_forge_codex.records import current_records, publish_package, read_generation
from model_forge_codex.runs import RunEngine, RunError, owned_writes
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, write_json_atomic

REPO = Path(__file__).resolve().parents[1]
PID = "project.direct"
SEED = {"title": "Supplied operator", "specification_markdown": "$T_\\lambda V=V$.",
        "source_reference": "Researcher's project instructions"}


@pytest.fixture
def direct_engine(tmp_path):
    root = tmp_path / "data"
    project = root / "projects" / PID
    project.mkdir(parents=True)
    write_json_atomic(project / "project.json", {
        "project_id": PID, "name": "Control research",
        "research_instructions": "Maximize discounted reward subject to the specified resource constraint.",
    })
    shutil.copytree(REPO / "contracts", project / "contracts")
    provision_team(project)
    from model_forge_codex.problem_context import initialize_problem_context
    initialize_problem_context(project)
    return RunEngine(root, FakeCodexBridge()), project


def p1_documents(source_ids=("citation.first",)):
    source = read_json(REPO / "contracts/examples/literature-source.example.json")
    source.pop("source_artifact", None)
    entries = []
    for index, source_id in enumerate(source_ids):
        citation = copy.deepcopy(source)
        citation.update(source_id=source_id, record_id="record." + source_id,
                        title="Discounted control " + source_id,
                        identifiers=[{"kind": "doi", "value": "10.1234/" + source_id}])
        entries.append({
            "entry_id": "entry." + source_id, "source": citation,
            "formulation_markdown": r"$$J(\pi)=\mathbb E_\pi[\sum_{t\geq0}\gamma^tR_t].$$",
            "explanation_markdown": "The criterion is discounted reward.",
            "relevance_markdown": "Specifies the research objective.",
            "limitations_markdown": "Constraint learning is outside this statement.",
            "evidence_locations": ["Definition 1"],
            "reading_extent": "Structural test fixture; no primary-source reading is claimed.",
        })
    collections = {
        "p1." + role + "_literature": {
            "schema_version": "1.2.0", "title": role + " literature",
            "search_scope": "Recorded primary-source search.", "coverage_limits": [],
            "papers": entries if role == "lead" else [],
        } for role in ("lead", "theory", "empirical")
    }
    collections["p1.research_basis"] = {
        "schema_version": "1.3.0", "title": "Research setting and landscape",
        # This common current-catalog fixture tests scientific orchestration;
        # notation lifecycle tests supply their own source-backed additions.
        "notation_updates": {"incoming_sources": [], "entries": [], "retirements": [], "correction_dispositions": []},
        "research_setting": {"statement_markdown": r"$$\max_{\pi\in\Pi}J(\pi)\quad\mathrm{s.t.}\quad \rho(\pi)\leq\varepsilon.$$",
                             "component_interpretations": [], "research_goal_markdown": "Develop a constrained control model and describe it in a technical report."},
        "phase2_preparation": {"instructions_markdown": "Propose methods within this setting.", "supplied_method": SEED},
        "landscape": {"summary_markdown": "The recorded literature defines discounted objectives.",
                      "topics": [{"topic_id": "topic.control", "title": "Control objectives",
                                  "description_markdown": "Discounted control formulations.", "source_ids": list(source_ids)}],
                      "frameworks": [], "variants": [], "relationships": [], "algorithm_families": [],
                      "overview_item_ids": [], "citation_refs": [], "common_assumptions": []},
        "scientific_review": {"scope_markdown": "Structural test fixture; scientific claims were not assessed.",
                              "findings": [], "limitations": ["No source verification is claimed."]},
        "entry_corrections": [],
        "coverage_limits": ["No empirical performance established."],
    }
    return collections


def p2_documents(with_seed, *, include_lead=True):
    outputs = {}
    files = {}
    roles = ["theory", "empirical"] + (["lead"] if include_lead else [])
    for role in roles:
        method = read_json(REPO / "contracts/examples/method.example.json")
        method["identity"]["stable_id"] = "method." + role
        method["record_id"] = "record.method." + role
        method["title"] = role + " proposal"
        artifact = method["mathematical_definition"]["canonical_artifact"]
        path = "method-" + role + ".md"
        content = "Exact method definition for " + role + ".\n"
        artifact.update(path=path, sha256=hashlib.sha256(content.encode()).hexdigest())
        files[path] = content
        outputs["p2." + role + "_proposal"] = {
            "schema_version": "1.1.0", "proposal_id": "proposal." + role, "method": method,
            "data_requirements_markdown": "Access to the specified transition model.",
            "proposed_evaluation_markdown": "Evaluate reward and constraint on held-out trajectories.",
            "computational_profile": {
                "per_iteration_markdown": "One iteration applies the stated update rule to all n observations.",
                "memory_markdown": "The procedure stores the data matrix and the fitted nuisance objects.",
                "scaling_markdown": "Cost grows linearly in the sample size for the stated updates.",
            },
            **({"researcher_origin": copy.deepcopy(SEED)} if role == "lead" and with_seed else {}),
        }
    for role, other in (("theory", "empirical"), ("empirical", "theory")):
        outputs["p2." + role + "_review"] = {
            "schema_version": "1.2.0", "review_id": "review." + role,
            "assessments": [{"proposal_id": "proposal." + target,
                             "headline": "The stated assumptions require further investigation.",
                             "applicability_markdown": "The proposal requires the specified data and declared conditions; their adequacy remains unverified.",
                             "assessment_markdown": "The stated assumptions require further investigation.",
                             "findings": []} for target in [other] + (["lead"] if include_lead else [])],
        }
    outputs["p2.catalog_assessment"] = {
        "schema_version": "1.3.0", "title": "Method comparison",
        "notation_updates": {"incoming_sources": [], "entries": [], "retirements": [], "correction_dispositions": []},
        "overview_markdown": "The candidates remain distinct; their assumptions need investigation before claims can be assessed.",
        "comparison_markdown": "The proposals remain distinct mathematical candidates.",
        "method_dispositions": [{"proposal_id": "proposal." + role, "status": "retain",
                                 "method_summary_markdown": "Apply the original proposal's stated update rule to the specified inputs and return its estimator.",
                                 "rationale": "Retain for researcher selection."} for role in roles],
        "modification_options": [{
            "option_id": "mod.proposal." + role + ".refinement",
            "applies_to": "proposal." + role,
            "title": "Tightened " + role + " update",
            "what_changes_markdown": "Replace the stated update constant with its halved value.",
            "when_preferable_markdown": "Preferable when the recorded diagnostics show instability at the proposed step size.",
        } for role in roles],
    }
    return outputs, files


def script(engine, phase, mode, outputs, files=None):
    queues = {}
    for stage in engine.stage_plan(PID, phase, mode):
        for role in stage.roles:
            key = "research_lead:PROJECT:trunk" if role is MemberRole.RESEARCH_LEAD else role.value + ":" + phase + ":trunk"
            docs = {output.split(".", 1)[1] + ".json": json.dumps(outputs[output])
                    for output in owned_writes(stage, role)}
            docs.update(files or {})
            queues.setdefault(key, []).append(("ok", docs))
    for key, queue in queues.items():
        engine.bridge.script_thread(key, queue)


async def complete(engine, phase, mode, **kwargs):
    record = await engine.start_run(PID, phase=phase, mode=mode, branch_id="trunk", **kwargs)
    await engine._tasks[record.run_id]
    final = engine.load_run(PID, record.run_id)
    assert final.state is RunState.PUBLISHED, (final.terminal_reason, final.findings_history)
    return final


async def test_p1_four_outputs_publish_and_cumulative_rerun_keeps_authored_math(direct_engine):
    engine, project = direct_engine
    first_docs = p1_documents()
    script(engine, "P1", "p1.literature_update", first_docs)
    first = await complete(engine, "P1", "p1.literature_update")
    phase_dir = project / "branches/trunk/phases/p1"
    first_refs = current_records(phase_dir)
    assert len(list((project / "runs" / first.run_id / "outputs").glob("*/*.json"))) >= 4
    first_source = read_generation(phase_dir, "lead_literature", first_refs["lead_literature"])
    assert first_source == first_docs["p1.lead_literature"]
    assert not {"phase_summary", "synthesis_compact", "phase2_handoff"} & first_refs.keys()
    second_docs = p1_documents(("citation.second",))
    script(engine, "P1", "p1.literature_update", second_docs)
    await complete(engine, "P1", "p1.literature_update")
    current = current_records(phase_dir)
    library = read_generation(phase_dir, "literature_library", current["literature_library"])
    assert {source["source_id"] for source in library["sources"]} == {"citation.first", "citation.second"}
    retained = next(source for source in library["sources"] if source["source_id"] == "citation.first")
    assert retained["assessments"][0]["entry"] == first_docs["p1.lead_literature"]["papers"][0]
    downstream = engine.compute_basis(PID, "P2", "trunk", "p2.full_catalog")
    assert downstream["cumulative_inputs"]["literature_library"]["document"] == library
    assert read_generation(phase_dir, "lead_literature", first_refs["lead_literature"]) == first_source
    from model_forge_codex.research import artifacts_view
    view = artifacts_view(project)
    assert view["research_bases"][0]["research_setting"] == second_docs["p1.research_basis"]["research_setting"]


@pytest.mark.parametrize("with_seed", [False, True])
async def test_p2_independent_proposals_required_cross_audits_and_exact_seed(direct_engine, with_seed):
    engine, project = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    engine.bridge.turns.clear()
    mode = "p2.researcher_proposal" if with_seed else "p2.full_catalog"
    outputs, files = p2_documents(with_seed)
    script(engine, "P2", mode, outputs, files)
    final = await complete(engine, "P2", mode, supplied_method=copy.deepcopy(SEED) if with_seed else None)
    assert len(engine.bridge.turns) == 6
    stages = engine._stages(final)
    assert len(stages[0].roles) == 3
    run_dir = engine.run_dir(PID, final.run_id)
    for role in stages[0].roles:
        brief = (run_dir / "briefs" / f"{stages[0].stage_id}.{role.value}.md").read_text()
        assert "(this run, stage" not in brief
    for role in stages[1].roles:
        brief = (run_dir / "briefs" / f"{stages[1].stage_id}.{role.value}.md").read_text()
        opposite = "empirical" if role is MemberRole.THEORIST else "theory"
        assert f"p2.{opposite}_proposal" in brief
        assert "p2.lead_proposal" in brief
    phase_dir = project / "branches/trunk/phases/p2"
    current = current_records(phase_dir)
    methods = read_generation(phase_dir, "method_catalog", current["method_catalog"])["methods"]
    assert {method["identity"]["stable_id"] for method in methods} == {"method.theory", "method.empirical", "method.lead"}
    assert final.supplied_method == (SEED if with_seed else None)


def test_cross_audit_cannot_omit_lead_or_substitute_self_review():
    outputs, _ = p2_documents(True)
    assert validate_direct_outputs("P2", outputs, supplied_method=SEED) == []
    bad = copy.deepcopy(outputs)
    bad["p2.theory_review"]["assessments"] = [{"proposal_id": "proposal.theory", "assessment_markdown": "Self review", "findings": []}]
    assert any(f.code == "review.target_coverage" and f.object_id == "p2.theory_review"
               for f in validate_direct_outputs("P2", bad, supplied_method=SEED))


def test_focused_proposals_preserve_unrelated_catalog_methods():
    outputs, _ = p2_documents(False)
    selected = outputs["p2.theory_proposal"]["method"]
    unrelated = outputs["p2.empirical_proposal"]["method"]
    options = {"mode": "p2.focused_method", "frozen_method": selected["identity"],
               "previous_catalog": {"methods": [selected, unrelated]}, "catalog": Catalog(REPO / "contracts")}
    assert any(f.code == "proposal.focus_scope" for f in validate_direct_outputs("P2", outputs, **options))
    outputs["p2.empirical_proposal"]["method"]["identity"]["stable_id"] = "method.new_alternative"
    # Keep the prior catalog independent of the proposed change.
    options["previous_catalog"] = {"methods": [selected, p2_documents(False)[0]["p2.empirical_proposal"]["method"]]}
    assert validate_direct_outputs("P2", outputs, **options) == []


async def test_setting_amendment_is_saved_and_frozen_for_next_run(direct_engine, monkeypatch):
    engine, project = direct_engine
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    app = create_app(engine.data_root, engine.bridge)
    text = r"Require $\mathbb E_\pi[(H-B)_+]\leq\varepsilon$."
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        context = (await client.get(f"/api/v1/projects/{PID}/problem-context")).json()
        brief = context["brief"]
        target = {"kind": "project_brief", "project_id": PID, "revision": brief["revision"],
                  "sha256": brief["sha256"], "text": "specified resource constraint"}
        missing_target = await client.patch(f"/api/v1/projects/{PID}", json={"setting_amendment": text})
        assert missing_target.status_code == 422
        response = await client.patch(f"/api/v1/projects/{PID}", json={"setting_amendment": text, "setting_amends": [target]})
        assert response.status_code == 200, response.text
        saved = response.json()["project"]
        assert saved["research_instructions"] == brief["instructions"]
        context = (await client.get(f"/api/v1/projects/{PID}/problem-context")).json()
        assert context["items"][-1]["statement"] == text
        assert context["items"][-1]["amends"] == [target]
    script(engine, "P1", "p1.literature_update", p1_documents())
    run = await complete(engine, "P1", "p1.literature_update")
    basis = read_json(engine.run_dir(PID, run.run_id) / "basis.json")
    assert basis["project"]["research_instructions"] == brief["instructions"]
    assert basis["problem_context"]["effective_account"]["items"][-1]["statement"] == text
    assert "specified resource constraint" not in basis["problem_context"]["effective_account"]["unamended_instructions"]
    assert all(json.dumps(text, ensure_ascii=False) in turn["brief"] for turn in engine.bridge.turns)


async def test_supplied_method_requires_explicit_specification_before_any_turn(direct_engine):
    engine, _ = direct_engine
    with pytest.raises(RunError, match="Select or enter"):
        await engine.start_run(PID, phase="P2", mode="p2.researcher_proposal", branch_id="trunk")
    with pytest.raises(RunError, match="title, exact specification"):
        await engine.start_run(PID, phase="P2", mode="p2.full_catalog", branch_id="trunk", supplied_method={"title": "Missing"})
    assert not engine.bridge.turns


async def test_focused_mode_cannot_run_without_a_selected_baseline(direct_engine):
    engine, _ = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    engine.bridge.turns.clear()
    assert any("exact selected baseline" in reason for reason in engine.check_readiness(PID, "P2", "trunk", "p2.focused_method"))
    with pytest.raises(RunError, match="not yet available"):
        await engine.start_run(PID, phase="P2", mode="p2.focused_method", branch_id="trunk")
    assert not engine.bridge.turns


@pytest.mark.parametrize("phase,family,field,value", [
    ("P1", "p1.research_basis", "landscape", ["malformed"]),
    ("P2", "p2.catalog_assessment", "method_dispositions", [1]),
])
async def test_malformed_direct_shapes_remain_correctable_schema_findings(direct_engine, phase, family, field, value):
    engine, _ = direct_engine
    files = {}
    if phase == "P2":
        script(engine, "P1", "p1.literature_update", p1_documents())
        await complete(engine, "P1", "p1.literature_update")
        outputs, files = p2_documents(False)
    else:
        outputs = p1_documents()
    outputs[family][field] = value
    mode = "p1.literature_update" if phase == "P1" else "p2.full_catalog"
    script(engine, phase, mode, outputs, files)
    run = await engine.start_run(PID, phase=phase, mode=mode, branch_id="trunk")
    await engine._tasks[run.run_id]
    failed = engine.load_run(PID, run.run_id)
    assert failed.state is RunState.FAILED
    assert any(f["code"] == "schema.type" and f["object_id"] == family for batch in failed.findings_history for f in batch)


def test_modification_options_require_known_targets_and_bounded_coverage():
    catalog = Catalog(REPO / "contracts")
    outputs, _ = p2_documents(False)
    assert validate_direct_outputs("P2", outputs, catalog=catalog) == []
    unknown = copy.deepcopy(outputs)
    unknown["p2.catalog_assessment"]["modification_options"].append({
        "option_id": "mod.proposal.unknown.extra", "applies_to": "proposal.unknown",
        "title": "Unknown target", "what_changes_markdown": "Change the stated constant.",
        "when_preferable_markdown": "Preferable in a regime this run does not propose."})
    findings = validate_direct_outputs("P2", unknown, catalog=catalog)
    assert [f.code for f in findings] == ["catalog.unknown_modification_target"]
    assert findings[0].json_pointer == "/modification_options/3/applies_to"
    missing = copy.deepcopy(outputs)
    missing["p2.catalog_assessment"]["modification_options"] = [
        option for option in missing["p2.catalog_assessment"]["modification_options"]
        if option["applies_to"] != "proposal.theory"]
    assert any(f.code == "catalog.modification_coverage"
               for f in validate_direct_outputs("P2", missing, catalog=catalog))
    duplicate = copy.deepcopy(outputs)
    options = duplicate["p2.catalog_assessment"]["modification_options"]
    options[1]["option_id"] = options[0]["option_id"]
    assert any(f.code == "catalog.modification_coverage"
               for f in validate_direct_outputs("P2", duplicate, catalog=catalog))
    excessive = copy.deepcopy(outputs)
    options = excessive["p2.catalog_assessment"]["modification_options"]
    for index in range(3):
        options.append({**copy.deepcopy(options[0]), "option_id": f"mod.proposal.theory.extra_{index}"})
    assert any(f.code == "catalog.modification_coverage"
               for f in validate_direct_outputs("P2", excessive, catalog=catalog))
    excluded = copy.deepcopy(outputs)
    for disposition in excluded["p2.catalog_assessment"]["method_dispositions"]:
        disposition["status"] = "exclude"
    excluded["p2.catalog_assessment"]["modification_options"] = []
    assert validate_direct_outputs("P2", excluded, catalog=catalog) == []
    catalog.version = "1.8.0"
    assert validate_direct_outputs("P2", unknown, catalog=catalog) == []
    assert validate_direct_outputs("P2", missing, catalog=catalog) == []


async def test_missing_computational_profile_blocks_and_routes_to_proposer(direct_engine):
    engine, _ = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    outputs, files = p2_documents(False)
    del outputs["p2.theory_proposal"]["computational_profile"]
    script(engine, "P2", "p2.full_catalog", outputs, files)
    run = await engine.start_run(PID, phase="P2", mode="p2.full_catalog", branch_id="trunk")
    await engine._tasks[run.run_id]
    failed = engine.load_run(PID, run.run_id)
    assert failed.state is RunState.FAILED
    assert any(f["code"] == "schema.required" and f["object_id"] == "p2.theory_proposal"
               for batch in failed.findings_history for f in batch)
    assert failed.mechanical_repair_attempts == {"p2.independent_proposals": 1}
    repair = read_json(engine.run_dir(PID, run.run_id) / "mechanical-repairs/p2.independent_proposals/attempt-1/result.json")
    assert repair["unchanged"] and repair["remaining_findings"]


@pytest.mark.parametrize("code,mutate", [
    ("catalog.unknown_modification_target", "unknown_target"),
    ("catalog.modification_coverage", "drop_option"),
])
async def test_modification_option_findings_block_and_route_to_lead(direct_engine, code, mutate):
    engine, _ = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    outputs, files = p2_documents(False)
    options = outputs["p2.catalog_assessment"]["modification_options"]
    if mutate == "unknown_target":
        options[2]["applies_to"] = "proposal.unknown"
    else:
        del options[0]
    script(engine, "P2", "p2.full_catalog", outputs, files)
    run = await engine.start_run(PID, phase="P2", mode="p2.full_catalog", branch_id="trunk")
    await engine._tasks[run.run_id]
    failed = engine.load_run(PID, run.run_id)
    assert failed.state is RunState.FAILED
    assert any(f["code"] == code and f["object_id"] == "p2.catalog_assessment"
               for batch in failed.findings_history for f in batch)
    assert failed.mechanical_repair_attempts == {"p2.lead_reconciliation": 1}
    repair = read_json(engine.run_dir(PID, run.run_id) / "mechanical-repairs/p2.lead_reconciliation/attempt-1/result.json")
    assert repair["unchanged"] and repair["remaining_findings"]


async def test_researcher_answer_keeps_question_and_enters_frozen_inputs(direct_engine, monkeypatch):
    engine, project = direct_engine
    from test_cumulative_attention import issue
    publish_package(project / "branches/trunk/phases/p1", {
        "attention_items": json.dumps([issue("question.discount")]).encode()
    }, run_id="run.question", phase="P1", branch_id="trunk")
    monkeypatch.delenv("MF_CODEX_READ_ONLY", raising=False)
    app = create_app(engine.data_root, engine.bridge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/projects/{PID}/attention/question.discount/resolve", json={"note": "Use discount factor 0.95."})
        assert response.status_code == 200
    script(engine, "P1", "p1.literature_update", p1_documents())
    run = await complete(engine, "P1", "p1.literature_update")
    basis = read_json(engine.run_dir(PID, run.run_id) / "basis.json")
    frozen = read_json(Path(basis["cumulative_inputs"]["researcher_answers"]["snapshot_path"]))["items"][0]
    assert frozen["note"] == "Use discount factor 0.95."
    assert frozen["attention"]["question"] == issue("question.discount")["question"]
    assert frozen["attention"]["generation_ref"]["run_id"] == "run.question"
    assert all("researcher_answers" in turn["brief"] for turn in engine.bridge.turns)


async def test_p2_rerun_keeps_retained_method_attachment_origin(direct_engine):
    engine, project = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    outputs, files = p2_documents(False)
    script(engine, "P2", "p2.full_catalog", outputs, files)
    first = await complete(engine, "P2", "p2.full_catalog")
    second_outputs, second_files = p2_documents(False)
    for role in ("theory", "empirical"):
        second_outputs["p2." + role + "_proposal"]["method"]["identity"]["stable_id"] += ".next"
    script(engine, "P2", "p2.full_catalog", second_outputs, second_files)
    await complete(engine, "P2", "p2.full_catalog")
    script(engine, "P2", "p2.full_catalog", second_outputs, second_files)
    third = await complete(engine, "P2", "p2.full_catalog")
    basis = read_json(engine.run_dir(PID, third.run_id) / "basis.json")
    catalog = read_json(Path(basis["cumulative_inputs"]["method_catalog"]["snapshot_path"]))
    assert len(catalog["methods"]) == 5
    assert catalog["method_sources"]["method.theory"]["run_id"] == first.run_id
    artifact = outputs["p2.theory_proposal"]["method"]["mathematical_definition"]["canonical_artifact"]
    assert any(item["producing_run_id"] == first.run_id and item["content_sha256"] == artifact["sha256"] for item in basis["artifacts"])
    assert not basis["unavailable_artifacts"]


async def test_legacy_method_changes_rebuild_keeps_provenance_in_basis(direct_engine):
    engine, project = direct_engine
    script(engine, "P1", "p1.literature_update", p1_documents())
    await complete(engine, "P1", "p1.literature_update")
    outputs, files = p2_documents(False)
    script(engine, "P2", "p2.full_catalog", outputs, files)
    await complete(engine, "P2", "p2.full_catalog")
    # A legacy-style incremental publication with no complete catalog record.
    changed = copy.deepcopy(outputs["p2.theory_proposal"]["method"])
    changed["identity"].update(version=2, definition_sha256="d" * 64)
    carried = [outputs[f"p2.{role}_proposal"]["method"] for role in ("empirical", "lead")]
    publish_package(project / "branches/trunk/phases/p2", {
        "method_changes": json.dumps({"methods": [changed, *carried]}).encode(),
    }, run_id="run.legacy.increment", phase="P2", branch_id="trunk")
    basis = engine.compute_basis(PID, "P2", "trunk", "p2.full_catalog")
    catalog = basis["cumulative_inputs"]["method_catalog"]["document"]
    assert catalog["derived"] is True
    assert catalog["record_type"] == "method_catalog"
    source = catalog["method_sources"]["method.theory"]
    assert source["run_id"] == "run.legacy.increment"
    assert source["family"] == "method_changes"
    assert source["identity"] == changed["identity"]
    provenance = basis["method_provenance"]["method.theory"]
    assert provenance["materials"]["method_changes"]["ref"]["run_id"] == "run.legacy.increment"
    assert provenance["materials"]["method_changes"]["document"] == {"methods": [changed, *carried]}
    assert provenance["unavailable"] == []
