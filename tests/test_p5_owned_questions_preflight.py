"""Owned P5 questions and existing zero-model native readiness, without dispatch."""
import asyncio
import copy
import json
import runpy
import shutil
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from model_forge_codex.bridge import BridgeUnavailable, FakeCodexBridge
from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole, RunState
from model_forge_codex.p5_review_packet import prepare_review_packet
from model_forge_codex.researcher_pause import eligible_stage, validate_authored_question
from model_forge_codex.runs import RunError, owned_writes
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from test_researcher_workbench_engine import get_method, record, workbench
from test_technical_reports import report_case

REPO = Path(__file__).resolve().parents[1]
FOCUS = 'EXACT_P5_REVIEW_FOCUS: retain unknown collection process and negative findings.'
NATIVE = 'native_tool_preflight_v1'
OLD_PHASE = REPO / 'tests/fixtures/catalog-v1.21.1-p5/P5.json'


def frozen_run(engine, project, branch, report_case, mode='p5.review_revision', old=False):
    current = record(engine, branch, 'run.p5-owned-questions', 'P5', mode)
    current.state = RunState.RUNNING
    current.instructions = FOCUS
    directory = engine.run_dir(current.project_id, current.run_id)
    shutil.copytree(project / 'contracts', directory / 'contracts')
    if old:
        root = directory / 'contracts'
        phase = read_json(OLD_PHASE)
        shutil.copyfile(OLD_PHASE, root / 'contracts/phases/P5.json')
        aggregate = read_json(root / 'contracts/phases.json')
        aggregate['contracts'] = [phase if row['phase_id'] == 'P5' else row for row in aggregate['contracts']]
        write_json_atomic(root / 'contracts/phases.json', aggregate)
        for name in ('catalog-index.json', 'catalog-pin.json'):
            document = read_json(root / name)
            document['catalog_version'] = '1.21.1'
            write_json_atomic(root / name, document)
        (root / 'VERSION').write_text('1.21.1\n', encoding='utf-8')
        runpy.run_path(str(REPO / 'contracts/refresh_manifest.py'))['refresh'](root)
    catalog = Catalog(directory / 'contracts')
    stages = engine.stage_plan(current.project_id, 'P5', mode)
    if old:
        objectives = {row['stage_id']: row['objective'] for row in phase['role_stages']}
        stages = [replace(stage, objective=objectives[stage.stage_id]) for stage in stages]
    current.stage_states = {stage.stage_id: 'pending' for stage in stages}
    engine._save_run(current)
    write_json_atomic(directory / 'stage-plan.json', [asdict(stage) for stage in stages])
    report, basis, roots, frozen = report_case
    identity = get_method(project, branch)['identity']
    report['method_identity'] = copy.deepcopy(identity)
    basis['method'] = {'identity': copy.deepcopy(identity)}
    frozen('P5', 'technical_report', report)
    basis['records'][-1]['branch'] = branch
    primary = next(iter(roots.values())) / 'report.md'
    basis['artifacts'].append({'path': str(primary), 'content_sha256': sha256_file(primary),
                              'family': 'technical_report', 'phase': 'P5', 'original_path': 'report.md'})
    basis['project'] = {'research_instructions': 'PRIVATE_PROJECT_INSTRUCTIONS'}
    basis['selected_issues'] = [{'issue': 'PRIVATE_INTERNAL_ISSUE'}]
    basis['problem_context'].update(brief={'revision': 1, 'instructions': 'PRIVATE_PROJECT_INSTRUCTIONS'}, proposals=[])
    basis['problem_context']['private_dialogue'] = 'PRIVATE_RESEARCHER_DIALOGUE'
    basis['catalog_sha256'] = catalog.snapshot_sha256
    write_json_atomic(directory / 'basis.json', basis)
    producer_basis = copy.deepcopy(basis)
    producer_basis['records'] = []
    write_json_atomic(project / 'runs/run.report/basis.json', producer_basis)
    if mode == 'p5.review_revision':
        prepare_review_packet(directory, basis=basis, instructions=FOCUS, run_id=current.run_id,
                              project_dir=project, catalog=catalog)
    return current, stages, directory, basis


def test_p5_update_keeps_review_scope_and_writers_exact():
    current = read_json(REPO / 'contracts/contracts/phases/P5.json')
    previous = read_json(OLD_PHASE)
    assert current['contract_version'] == '3.5.2'
    assert current['capabilities'] == [*previous['capabilities'], NATIVE,
                                      'consequential_researcher_decisions_v1', 'p5.reader_report.v1',
                                      'research_presentation_v1', 'research_presentation_v2', 'project_notation_v1']
    for stage, old in zip(current['role_stages'], previous['role_stages']):
        assert {key: value for key, value in stage.items() if key != 'objective'} == {
            key: value for key, value in old.items() if key != 'objective'}
    prior_purpose = next(output['purpose'] for output in previous['run_local_outputs']
                         if output['output_id'] == 'p5.attention_items')
    prior_compatible = copy.deepcopy(current)
    attention = next(output for output in prior_compatible['run_local_outputs']
                     if output['output_id'] == 'p5.attention_items')
    attention['purpose'] = prior_purpose
    assert {key: value for key, value in prior_compatible.items()
            if key not in ('role_stages','capabilities','contract_version','prepared_contexts')} == {
        key: value for key, value in previous.items()
        if key not in ('role_stages','capabilities','contract_version','prepared_contexts')}
    current_context = copy.deepcopy(current['prepared_contexts'])
    current_context[0]['content_requirements'][1] = previous['prepared_contexts'][0]['content_requirements'][1]
    assert current_context == previous['prepared_contexts']
    for output in ('p5.theory_audit','p5.empirical_audit'):
        assert Catalog(REPO / 'contracts').output_schema(output)['type'] == 'array'
    assert 'prioritized_issues' in Catalog(REPO / 'contracts').output_schema('p5.outside_review')['properties']


def test_p5_attention_output_purpose_matches_editorial_only_objectives():
    fragment = read_json(REPO / 'contracts/contracts/phases/P5.json')
    aggregate = read_json(REPO / 'contracts/contracts/phases.json')
    assert next(phase for phase in aggregate['contracts'] if phase['phase_id'] == 'P5') == fragment
    attention = next(output for output in fragment['run_local_outputs']
                     if output['output_id'] == 'p5.attention_items')
    purpose = attention['purpose']
    assert 'only indispensable researcher editorial choices' in purpose
    assert 'an empty array is valid' in purpose
    assert 'source records or the review ledger and route upstream' in purpose
    assert 'do not reopen P1-P4 elicitation' in purpose
    assert 'newly identified research-attention item' not in purpose
    assert 'Distinguish researcher decisions from team tasks' not in purpose


def test_actual_review_briefs_route_questions_without_leaking_private_context(workbench, report_case):
    engine, project, branch = workbench
    current, stages, directory, _ = frozen_run(engine, project, branch, report_case)
    review, lead = stages
    snapshots = {path.name: path.read_bytes() for path in (directory / 'review-packet').iterdir()}
    for role in review.roles:
        brief = engine._render_brief(current, review, role, engine.member_workspace(current, review.stage_id, role))
        assert review.objective in brief and FOCUS in brief
        assert 'open_question findings in your owned review output' in brief
        assert 'scientific_consequence' in brief and 'requested_resolution' in brief
        assert 'Do not create attention_items.json or researcher-question.json' in brief
        assert 'Author researcher-decision attention' not in brief
        assert '## Consequential researcher input' not in brief
        assert 'p5.attention_items' not in owned_writes(review, role)
        assert '## Report and proof exposition' in brief
        assert 'Parallel reviewers remain read-only' in brief
        assert 'Substantive missing arguments, changed assumptions, new results and stronger claims remain P3 work' in brief
        if role is MemberRole.OUTSIDE_REVIEWER:
            assert 'fresh first-time reader' in brief
            assert 'only project-specific context' in brief
            assert 'PRIVATE_' not in brief
            assert 'prioritized_issues' in brief
            assert '## Frozen problem context' not in brief
            assert '## Project instructions' not in brief
    delivered = engine._render_brief(current, lead, MemberRole.RESEARCH_LEAD,
                                    engine.member_workspace(current, lead.stage_id, MemberRole.RESEARCH_LEAD))
    assert lead.objective in delivered and FOCUS in delivered
    assert 'p5.attention_items may be empty' in delivered
    assert 'editorial choice that prevents faithful writing of this exact report' in delivered
    assert 'Every new attention item uses schema_version 1.2.0' in delivered
    assert '## Consequential researcher input' in delivered
    assert 'Use the existing researcher-question.json only if' in delivered
    assert 'p5.attention_items' in owned_writes(lead, MemberRole.RESEARCH_LEAD)
    assert 'All proofs and proof sketches belong in a separate declared appendix' in delivered
    assert 'review run does not inherit an assembly run' in delivered
    assert snapshots == {path.name: path.read_bytes() for path in (directory / 'review-packet').iterdir()}
    assert engine.bridge.turns == []


def test_assembly_lead_receives_conditional_question_scope(workbench, report_case):
    engine, project, branch = workbench
    current, stages, _, _ = frozen_run(engine, project, branch, report_case, mode='p5.assembly')
    stage = stages[0]
    brief = engine._render_brief(current, stage, MemberRole.RESEARCH_LEAD,
                                 engine.member_workspace(current, stage.stage_id, MemberRole.RESEARCH_LEAD))
    assert stage.objective in brief and FOCUS in brief
    assert 'conditional or interim work' in brief
    assert 'kind researcher_decision' in brief
    assert 'without reopening problem, method or study-design elicitation owned by P1-P4' in brief
    assert 'researcher-question.json' in brief and 'blocking=true' in brief
    assert eligible_stage(current, stage)


@pytest.mark.parametrize('mode', ['p5.assembly', 'p5.review_revision'])
def test_frozen_report_lead_briefs_deliver_concise_statistical_authoring(workbench, report_case, mode):
    engine, project, branch = workbench
    current, stages, directory, _ = frozen_run(engine, project, branch, report_case, mode=mode)
    lead = stages[-1]
    frozen_phase = read_json(directory / 'contracts/contracts/phases/P5.json')
    project_phase = read_json(project / 'contracts/contracts/phases/P5.json')
    project_phase['role_stages'][-1]['objective'] = 'LATER_UNFROZEN_WRITING_DIRECTION'
    write_json_atomic(project / 'contracts/contracts/phases/P5.json', project_phase)
    brief = engine._render_brief(current, lead, MemberRole.RESEARCH_LEAD,
                                engine.member_workspace(current, lead.stage_id, MemberRole.RESEARCH_LEAD))
    assert brief.count('## Frozen technical report scope') == 1
    assert lead.objective in brief
    assert 'LATER_UNFROZEN_WRITING_DIRECTION' not in brief
    assert 'seven anchored content sections' in brief
    assert 'no word or equation quota' in brief
    assert 'Use cross-references instead of repeating definitions' in brief
    assert 'generation IDs, digests, scalar pointers, review dispositions' in brief
    assert 'estimand, estimator and realized estimate' in brief
    assert 'sampling variability, resampling variability and Monte Carlo standard error' in brief
    assert 'model-defining assumptions, constraints, tuning conventions' in brief
    assert 'quantifiers, conditioning, signs, bounds' in brief
    assert 'KaTeX-supported LaTeX' in brief
    assert 'Check the actual report Markdown with validate_artifacts' in brief
    assert 'A syntax pass does not establish mathematical fidelity' in brief
    assert 'Detailed derivations, secondary full tables and lengthy reproduction recipes' in brief
    assert 'Do not reopen P1-P4 problem, collection, method or study-design questions' in brief
    assert 'indispensable editorial choice' in brief
    assert 'author an informational attention question' not in brief
    assert 'section_anchors mapping the seven content IDs' in brief
    assert 'section_anchors.references as a distinct trailing bibliography boundary' in brief
    assert 'Put all proofs, proof sketches, proof-only derivations and auxiliary lemmas in a separate declared appendix' in brief
    assert 'Checked local expansions of supplied algebra or conditional reasoning are allowed' in brief
    assert "Follow this run's exact p5.instructions for reading scope and appendix organization" in brief
    assert 'Do not require PDF creation, print layout or page-count checks unless the researcher explicitly requests them later' in brief
    assert frozen_phase == read_json(directory / 'contracts/contracts/phases/P5.json')
    assert len(stages) == (1 if mode == 'p5.assembly' else 2)
    assert engine.bridge.turns == []


def test_older_frozen_lead_retry_keeps_original_report_policy(workbench, report_case):
    engine, project, branch = workbench
    current, stages, directory, _ = frozen_run(engine, project, branch, report_case, old=True)
    lead = stages[-1]
    before = {path.name: path.read_bytes() for path in (directory / 'review-packet').iterdir()}
    assert 'p5.reader_report.v1' in read_json(project / 'contracts/contracts/phases/P5.json')['capabilities']
    brief = engine._render_brief(current, lead, MemberRole.RESEARCH_LEAD,
                                 engine.member_workspace(current, lead.stage_id, MemberRole.RESEARCH_LEAD))
    assert lead.objective in brief
    assert '## Report and proof exposition' not in brief
    assert 'section_anchors.references as a distinct trailing bibliography boundary' not in brief
    assert before == {path.name: path.read_bytes() for path in (directory / 'review-packet').iterdir()}
    assert engine.bridge.turns == []


def test_blocking_pause_is_lead_owned_and_cannot_be_authored_by_parallel_reviewer(workbench, report_case):
    engine, project, branch = workbench
    current, stages, _, basis = frozen_run(engine, project, branch, report_case)
    review, lead = stages
    question = {'question': 'Which authorized audience should this report address?', 'reason': 'The conflicting editorial directions prevent a faithful report.',
                'blocking': True, 'scope': {'kind': 'model', 'branch': branch, 'model_ref': basis['method']['identity']}, 'source_refs': []}
    assert not eligible_stage(current, review)
    with pytest.raises(ValueError, match='single-member sequential'):
        validate_authored_question(current, review, question, basis)
    assert validate_authored_question(current, lead, question, basis)['blocking'] is True
    path = engine.member_workspace(current, review.stage_id, MemberRole.OUTSIDE_REVIEWER)
    write_json_atomic(path / 'researcher-question.json', question)
    with pytest.raises(RunError, match='cannot pause'):
        engine._authored_researcher_question(current, review, path)


def test_project_instruction_edits_do_not_rewrite_frozen_review_questions(workbench, report_case):
    engine, project, branch = workbench
    current, stages, _, _ = frozen_run(engine, project, branch, report_case)
    original = stages[0].objective
    contract = read_json(project / 'contracts/contracts/phases/P5.json')
    contract['role_stages'][1]['objective'] = 'LATER_PROJECT_QUESTION_INSTRUCTION'
    write_json_atomic(project / 'contracts/contracts/phases/P5.json', contract)
    stage = engine._stages(current)[0]
    brief = engine._render_brief(current, stage, MemberRole.OUTSIDE_REVIEWER,
                                 engine.member_workspace(current, stage.stage_id, MemberRole.OUTSIDE_REVIEWER))
    assert original in brief
    assert 'LATER_PROJECT_QUESTION_INSTRUCTION' not in brief


class NativeReviewBridge(FakeCodexBridge):
    """Host barrier fixture; successful checks are not actual sandbox claims."""
    def __init__(self, behavior='passed'):
        super().__init__()
        self.behavior = behavior
        self.checked = []
        self.default_behavior = ('fail', 'Bounded fixture stops after observing ordinary turn release.')

    async def check_native_tools(self, thread_id, workspace):
        role = self.threads[thread_id]['key'].split(':',1)[0]
        self.checked.append((role, len(self.turns), str(workspace)))
        await asyncio.sleep(0)
        if self.behavior == 'raised' and role == 'theorist':
            raise BridgeUnavailable('Bounded fixture native failure')
        if self.behavior != 'passed' and role == 'theorist':
            return None if self.behavior == 'malformed' else {'status': self.behavior, 'model_turns': 0}
        return {'status': 'passed', 'native_editing': 'unverified', 'model_turns': 0}


@pytest.mark.parametrize('stage_id,mode', [('p5.assembly_lead','p5.assembly'),
    ('p5.parallel_reviews','p5.review_revision'), ('p5.revision_lead','p5.review_revision')])
async def test_all_p5_members_check_native_readiness_before_ordinary_turn(workbench, report_case, stage_id, mode):
    engine, project, branch = workbench
    current, stages, directory, _ = frozen_run(engine, project, branch, report_case, mode)
    engine.bridge = bridge = NativeReviewBridge()
    stage = next(stage for stage in stages if stage.stage_id == stage_id)
    result = await engine._execute_stage(current, stage)
    assert result.succeeded is False  # The authored fake deliberately ends here.
    assert {role for role,_,_ in bridge.checked} == {role.value for role in stage.roles}
    assert all(turns == 0 for _,turns,_ in bridge.checked)
    assert len(bridge.turns) == len(stage.roles)
    for role in stage.roles:
        check = read_json(directory / 'native-checks' / stage_id / (role.value + '.json'))
        assert check['status'] == 'passed' and check['model_turns'] == 0


@pytest.mark.parametrize('behavior',['failed','unavailable','malformed','raised'])
async def test_one_p5_native_failure_blocks_every_parallel_ordinary_turn(workbench, report_case, behavior):
    engine, project, branch = workbench
    current, stages, directory, _ = frozen_run(engine, project, branch, report_case)
    stage = stages[0]
    engine.bridge = bridge = NativeReviewBridge(behavior)
    result = await engine._execute_stage(current, stage)
    assert result.succeeded is False
    assert {role for role,_,_ in bridge.checked} == {role.value for role in stage.roles}
    assert bridge.turns == []
    assert engine.load_run(current.project_id,current.run_id).stage_states[stage.stage_id] == 'failed'
    assert 'runtime.native_tools_unavailable' in {finding['code'] for finding in engine.load_run(current.project_id,current.run_id).findings_history[-1]}
    assert not (directory / 'execution').exists()


async def test_frozen_p5_3_0_keeps_original_brief_and_skips_new_preflight(workbench, report_case):
    engine, project, branch = workbench
    current, stages, directory, _ = frozen_run(engine, project, branch, report_case, old=True)
    old_hash = sha256_file(directory / 'contracts/contracts/phases/P5.json')
    assert old_hash == sha256_file(OLD_PHASE)
    assert NATIVE not in read_json(directory / 'contracts/contracts/phases/P5.json')['capabilities']
    assert read_json(project / 'contracts/catalog-pin.json') == read_json(REPO / 'contracts/catalog-pin.json')
    assert engine._catalog(current).version == '1.21.1'
    stage = stages[0]
    brief = engine._render_brief(current, stage, MemberRole.OUTSIDE_REVIEWER,
                                 engine.member_workspace(current, stage.stage_id, MemberRole.OUTSIDE_REVIEWER))
    assert 'Author researcher-decision attention' in brief
    assert 'open_question findings in your owned review output' not in brief
    assert '## Report and proof exposition' not in brief
    assert 'section_anchors.references' not in brief
    lead = stages[-1]
    lead_brief = engine._render_brief(current, lead, MemberRole.RESEARCH_LEAD,
                                     engine.member_workspace(current, lead.stage_id, MemberRole.RESEARCH_LEAD))
    assert '## Report and proof exposition' not in lead_brief
    assert 'section_anchors.references as a distinct trailing bibliography boundary' not in lead_brief
    engine.bridge = bridge = NativeReviewBridge('raised')
    await engine._execute_stage(current,stage)
    assert bridge.checked == [] and len(bridge.turns) == 3
    assert not (directory / 'native-checks').exists()
    assert sha256_file(directory / 'contracts/contracts/phases/P5.json') == old_hash
