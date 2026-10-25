"""Exact saved aggregates travel with their prose scalar, without coercion."""
from copy import deepcopy
import json

import pytest

from test_technical_reports import IDENTITY, numerical, report_case
from model_forge_codex.catalog import Catalog
from model_forge_codex.p5_review_packet import prepare_review_packet
from model_forge_codex.records import ArtifactError
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from model_forge_codex.technical_reports import (
    report_required_artifacts, report_submitted_source_materials, resolve_report_scalar,
    resolve_report_source, validate_technical_report,
)
from test_p5_owned_questions_preflight import REPO, frozen_run, workbench
from model_forge_codex.domain import MemberRole


def artifact_quote(report_case, *, value=0.0004677606440342467, phase='P4', identity=None, collection=False):
    report, basis, roots, frozen = report_case
    numerical(report, basis, frozen)
    root = next(iter(roots.values()))
    artifact = root / 'paired.json'
    write_json_atomic(artifact, {'aggregate': {'paired_mcse': value}})
    pointer = {'artifact_id': 'artifact.paired', 'path': artifact.name,
               'sha256': sha256_file(artifact), 'media_type': 'application/json'}
    basis['artifacts'].append({'path': str(artifact), 'content_sha256': pointer['sha256']})
    record = {'method_identity': identity or deepcopy(IDENTITY),
        'artifacts': [pointer], 'private_dialogue': 'PRIVATE_DIALOGUE', 'unrelated_audit': 'PRIVATE_REVIEW'}
    document = [{'method_identity': {**IDENTITY, 'version': 9}, 'artifacts': []}, record] if collection else record
    reference = frozen(phase, 'aggregate_index', document)
    reference.update(pointer=('/1' if collection else '') + '/artifacts/0', scalar_pointer='/aggregate/paired_mcse')
    report['prose_values'] = [{'text': 'Paired MCSE was 0.000467761.', 'anchor': 'numerical_analysis',
        'reported_value': 0.000467761, 'source_refs': [reference], 'presentation': 'Squared probability, rounded to 9 places',
        'transformation': {'kind': 'round', 'decimals': 9}}]
    primary = root / 'report.md'
    primary.write_text(primary.read_text(encoding='utf-8') + '\n\nPaired MCSE was 0.000467761.\n', encoding='utf-8')
    report['report_artifact']['sha256'] = sha256_file(primary)
    report['artifact_authored_paths'] = {'artifact.paired': 'sources/paired.json'}
    return report, basis, roots, frozen, reference, artifact, pointer


@pytest.mark.parametrize('collection', [False, True])
def test_prose_only_artifact_scalar_retains_original_source_and_outside_dependency(report_case, tmp_path, collection):
    report, basis, roots, frozen, reference, artifact, pointer = artifact_quote(report_case, collection=collection)
    before = {path: path.read_bytes() for path in (artifact, next(iter(roots.values())) / 'report.md')}
    assert resolve_report_source(reference, basis)[0] == pointer
    assert resolve_report_scalar(reference, basis)[0] == 0.0004677606440342467
    assert validate_technical_report({'p5.technical_report_candidate': report}, basis, artifact_roots=roots) == []
    required = report_required_artifacts(report, basis)
    exact = next(item for item in required if item.get('artifact_id') == 'artifact.paired')
    assert exact['sha256'] == sha256_file(artifact) and exact['authored_path'] == 'sources/paired.json'
    submitted = report_submitted_source_materials(report, basis)
    entry = next(item for item in submitted['scientific_sources'] if item['source_ref'].get('scalar_pointer'))
    assert entry['source_ref'] == reference and entry['scientific_excerpt'] == 0.0004677606440342467
    assert 'PRIVATE_' not in json.dumps(submitted)
    primary = next(iter(roots.values())) / 'report.md'
    basis['artifacts'].append({'path': str(primary), 'content_sha256': sha256_file(primary)})
    frozen('P5', 'technical_report', report)
    packet = prepare_review_packet(tmp_path / 'review', basis=basis, instructions='Check the exact quoted aggregate.',
                                  run_id='run.review', project_dir=tmp_path)
    materials = read_json(tmp_path / 'review/review-packet/materials.json')
    linked = next(item for item in materials['materials'] if item['sha256'] == pointer['sha256'])
    assert (tmp_path / 'review/review-packet' / linked['submitted_name']).read_bytes() == artifact.read_bytes()
    assert entry in materials['scientific_sources'] and 'PRIVATE_' not in json.dumps(materials)
    assert packet['target']['report_artifact_sha256'] == report['report_artifact']['sha256']
    assert all(path.read_bytes() == contents for path, contents in before.items())


@pytest.mark.parametrize('value', [True, '0.0004677606440342467', None, {}, [], float('nan'), float('inf')])
def test_artifact_scalar_rejects_nonfinite_or_nonnumeric_json(report_case, value):
    _, basis, _, _, reference, _, _ = artifact_quote(report_case, value=value)
    with pytest.raises(ArtifactError, match='finite JSON number'):
        resolve_report_scalar(reference, basis)


@pytest.mark.parametrize('change', ['source_bytes', 'artifact_bytes', 'source_pointer', 'scalar_pointer',
                                   'invalid_pointer', 'missing_artifact', 'wrong_phase', 'wrong_model'])
def test_artifact_scalar_keeps_exact_source_artifact_and_model_boundaries(report_case, change):
    kwargs = {'phase': 'P3'} if change == 'wrong_phase' else {}
    if change == 'wrong_model':
        kwargs['identity'] = {**IDENTITY, 'version': 2}
    report, basis, roots, _, reference, artifact, _ = artifact_quote(report_case, **kwargs)
    if change == 'source_bytes':
        record = next(row for row in basis['records'] if row['family'] == 'aggregate_index')
        with open(record['snapshot_path'], 'a', encoding='utf-8') as stream:
            stream.write(' ')
    elif change == 'artifact_bytes':
        artifact.write_text('{"aggregate":{"paired_mcse":1}}', encoding='utf-8')
    elif change == 'source_pointer':
        reference['pointer'] = '/missing'
    elif change == 'scalar_pointer':
        reference['scalar_pointer'] = '/aggregate/missing'
    elif change == 'invalid_pointer':
        reference['scalar_pointer'] = '/bad~2escape'
    elif change == 'missing_artifact':
        artifact.unlink()
    with pytest.raises(ArtifactError):
        resolve_report_scalar(reference, basis)
    findings = validate_technical_report({'p5.technical_report_candidate': report}, basis, artifact_roots=roots)
    assert any(item.code == 'report.prose_value_mismatch' for item in findings)


def test_direct_record_scalar_remains_direct_and_artifact_pointer_needs_explicit_selector(report_case):
    report, basis, _, _, reference, _, pointer = artifact_quote(report_case)
    direct = {**report['numerical_analysis'][0]['evidence_refs'][0], 'pointer': '/metrics/estimate'}
    assert resolve_report_scalar(direct, basis) == resolve_report_source(direct, basis)
    reference.pop('scalar_pointer')
    assert resolve_report_scalar(reference, basis)[0] == pointer


def test_collection_scalar_cannot_borrow_identity_from_another_record(report_case):
    _, basis, _, _, reference, _, _ = artifact_quote(report_case, collection=True, identity={**IDENTITY, 'version': 2})
    with pytest.raises(ArtifactError, match='exact-model retained P4'):
        resolve_report_scalar(reference, basis)


@pytest.mark.parametrize('pointer', [None, ''])
def test_collection_scalar_needs_an_explicit_artifact_pointer(report_case, pointer):
    report, basis, roots, _, reference, _, _ = artifact_quote(report_case, collection=True)
    if pointer is None:
        reference.pop('pointer')
    else:
        reference['pointer'] = pointer
    with pytest.raises(ArtifactError, match='exact-model retained P4 artifact pointer'):
        resolve_report_scalar(reference, basis)
    assert any(item.code == 'report.prose_value_mismatch' for item in
               validate_technical_report({'p5.technical_report_candidate': report}, basis, artifact_roots=roots))


@pytest.mark.parametrize('mode', ['p5.assembly', 'p5.review_revision'])
def test_current_lead_briefs_describe_unique_material_aliases_and_explicit_scalar(workbench, report_case, mode):
    engine, project, branch = workbench
    current, stages, _, _ = frozen_run(engine, project, branch, report_case, mode=mode)
    lead = stages[-1]
    brief = engine._render_brief(current, lead, MemberRole.RESEARCH_LEAD,
                                engine.member_workspace(current, lead.stage_id, MemberRole.RESEARCH_LEAD))
    assert 'artifact_authored_paths keyed by that exact artifact_id, with one nonempty report-relative path string per artifact' in brief
    assert 'Existing matching path/artifact_path aliases need no extra mapping' in brief
    assert 'supplementary_artifacts with exact relative path, media_type and sha256' in brief
    assert 'scalar_pointer selects one finite JSON number' in brief
    assert 'private researcher dialogue and current P5 parallel review findings' in brief
    assert engine.bridge.turns == []
    catalog = Catalog(REPO / 'contracts')
    assert catalog.verify_manifest() == []
    assert read_json(REPO / 'contracts/contracts/phases/P5.json')['contract_version'] == '3.3.0'
