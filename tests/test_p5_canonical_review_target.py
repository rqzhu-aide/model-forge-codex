"""A published report alias pair supplies one exact authoritative review target."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from model_forge_codex.domain import RunState
from model_forge_codex.p5_review_packet import prepare_review_packet, read_review_packet
from model_forge_codex.records import ArtifactError, publish_package
from model_forge_codex.research import artifacts_view
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from test_p5_owned_questions_preflight import REPO, frozen_run
from test_researcher_workbench_engine import workbench
from test_technical_reports import report_case


def target_basis(report_case, *, canonical=True, candidate=True):
    report, basis, roots, frozen = report_case
    primary = next(iter(roots.values())) / 'report.md'
    basis['artifacts'].append({'path': str(primary), 'content_sha256': sha256_file(primary)})
    refs = {}
    if canonical:
        refs['canonical'] = frozen('P5', 'technical_report', report)
    if candidate:
        refs['candidate'] = frozen('P5', 'technical_report_candidate', report)
    return report, basis, roots, refs


@pytest.mark.parametrize('change', ['same_alias', 'different_alias', 'reverse_order'])
def test_packet_uses_exact_canonical_even_with_unselected_candidate(report_case, tmp_path, change):
    report, basis, _, refs = target_basis(report_case)
    if change == 'different_alias':
        candidate = next(row for row in basis['records'] if row['family'] == 'technical_report_candidate')
        path = Path(candidate['snapshot_path'])
        path.write_text('{"unselected":true}', encoding='utf-8')
        candidate['content_sha256'] = sha256_file(path)
    elif change == 'reverse_order':
        basis['records'].reverse()
    packet = prepare_review_packet(tmp_path / 'review', basis=basis, instructions='Check the canonical original.', run_id='run.review', project_dir=tmp_path)
    assert packet['target']['family'] == 'technical_report'
    assert packet['target']['generation_id'] == refs['canonical']['generation_id']
    assert packet['target']['content_sha256'] == refs['canonical']['content_sha256']
    assert packet['target']['report_artifact_sha256'] == report['report_artifact']['sha256']


def test_candidate_only_legacy_packet_keeps_its_exact_target(report_case, tmp_path):
    _, basis, _, refs = target_basis(report_case, canonical=False)
    packet = prepare_review_packet(tmp_path / 'review', basis=basis, instructions='Check retained candidate.', run_id='run.review', project_dir=tmp_path)
    assert packet['target']['family'] == 'technical_report_candidate'
    assert packet['target']['generation_id'] == refs['candidate']['generation_id']
    assert packet['target']['content_sha256'] == refs['candidate']['content_sha256']


@pytest.mark.parametrize('change', ['duplicate_canonical', 'duplicate_candidate', 'missing', 'tampered_canonical'])
def test_packet_does_not_guess_or_fall_back_from_invalid_authoritative_target(report_case, tmp_path, change):
    _, basis, _, _ = target_basis(report_case, canonical=change != 'duplicate_candidate')
    if change == 'duplicate_canonical':
        basis['records'].append(deepcopy(next(r for r in basis['records'] if r['family'] == 'technical_report')))
    elif change == 'duplicate_candidate':
        basis['records'].append(deepcopy(basis['records'][0]))
    elif change == 'missing':
        basis['records'] = []
    else:
        Path(next(r for r in basis['records'] if r['family'] == 'technical_report')['snapshot_path']).write_text('{}', encoding='utf-8')
    with pytest.raises(ArtifactError):
        prepare_review_packet(tmp_path / 'review', basis=basis, instructions='No guessing.', run_id='run.review', project_dir=tmp_path)


async def test_real_publication_aliases_enter_engine_review_and_exact_original_projection(workbench, report_case):
    engine, project, branch = workbench
    producer, stages, directory, basis = frozen_run(engine, project, branch, report_case, mode='p5.assembly')
    report = report_case[0]
    primary = directory / 'outputs/p5.assembly_lead/report.md'
    primary.parent.mkdir(parents=True)
    primary.write_bytes((next(iter(report_case[2].values())) / 'report.md').read_bytes())
    phase = project / 'branches' / branch / 'phases/p5'
    raw = json.dumps(report).encode('utf-8')
    package = publish_package(phase, {'technical_report': raw, 'technical_report_candidate': raw},
                              run_id=producer.run_id, phase='P5', branch_id=branch,
                              metadata={'stage_ids': {name: stages[0].stage_id for name in ('technical_report', 'technical_report_candidate')},
                                        'method': basis['method']})
    producer.state = RunState.PUBLISHED
    engine._save_run(producer)
    engine.bridge.default_behavior = ('fail', 'Bounded fixture stops after real reviewer packet dispatch.')
    review = await engine.start_run('project.test', phase='P5', mode='p5.review_revision', branch_id=branch,
                                    instructions='EXACT_ORIGINAL_REVIEW_FOCUS')
    await engine._tasks[review.run_id]
    run_root = engine.run_dir(review.project_id, review.run_id)
    packet = read_review_packet(run_root / 'review-packet')
    expected = package['records']['technical_report']
    assert packet['target']['generation_id'] == expected['generation_id']
    assert packet['target']['content_sha256'] == expected['content_sha256']
    assert packet['target']['report_artifact_sha256'] == sha256_file(primary)
    frozen = read_json(run_root / 'basis.json')
    assert {r['family'] for r in frozen['records'] if r['phase'] == 'P5'} == {'technical_report', 'technical_report_candidate'}
    assert len(engine.bridge.turns) == 3
    outside = next(turn for turn in engine.bridge.turns if 'fresh first-time reader' in turn['brief'])
    assert 'EXACT_ORIGINAL_REVIEW_FOCUS' in outside['brief'] and 'PRIVATE_' not in outside['brief']
    # Publish fixture review bytes to exercise the real researcher projection,
    # without a new proof, computation or claim of independent scientific quality.
    outside_doc = read_json(REPO / 'contracts/examples/review-report.example.json')
    outside_doc.update(review_basis_generation_id=expected['generation_id'], prioritized_issues=[])
    publish_package(phase, {'outside_review': json.dumps(outside_doc).encode('utf-8')}, run_id=review.run_id,
                    phase='P5', branch_id=branch, metadata={'method': basis['method']})
    reading = artifacts_view(project, branch)
    projected = next(row for row in reading['documents'] if row['family'] == 'outside_review')
    assert projected['reviewed_report_ref']['family'] == 'technical_report'
    assert projected['reviewed_report_ref']['generation_id'] == expected['generation_id']
    assert projected['reviewed_report_ref']['sha256'] == expected['content_sha256']
    assert 'review_document_error' not in projected and projected['reviewed_source_url']
