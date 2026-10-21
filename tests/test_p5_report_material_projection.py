"""Required report exhibits use exact frozen bytes without changing ordinary links."""
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from model_forge_codex.research import _report_material_projection
from model_forge_codex.research_sources import artifact_link, frozen_artifact
from model_forge_codex.storage import sha256_bytes, write_json_atomic


@pytest.fixture
def retained_report(tmp_path):
    project = tmp_path / 'project.test'
    ref = {'run_id': 'run.report', 'branch': 'method.test', 'phase': 'P5', 'stage_id': 'p5.assembly_lead'}
    run_root = project / 'runs' / ref['run_id']
    write_json_atomic(run_root / 'run.json', {'state': 'published', 'branch_id': ref['branch'], 'phase': ref['phase']})
    content = b'[{"loss":0.003,"usable_pairs":19}]\n'
    digest = sha256_bytes(content)
    path = run_root / 'inputs/artifacts' / (digest + '-performance.json')
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    basis = {'artifacts': [{'artifact_id': 'artifact.performance', 'original_path': 'performance.json',
                            'path': str(path), 'content_sha256': digest}]}
    write_json_atomic(run_root / 'basis.json', basis)
    pointer = {'artifact_path': 'exhibit-artifacts/performance.json', 'artifact_sha256': digest,
               'media_type': 'application/json', 'title': 'Retained paired loss'}
    return project, ref, run_root, basis, pointer, path


def test_imported_report_exhibit_reuses_exact_declared_input_without_global_relaxation(retained_report):
    project, ref, run_root, basis, pointer, path = retained_report
    before = deepcopy(pointer)
    assert 'source_error' in artifact_link(project, ref, pointer)
    projected = _report_material_projection(project, ref, pointer, basis, {})
    assert projected['source_verified'] and projected['source_kind'] == 'retained_input'
    assert projected['artifact_path'] == before['artifact_path'] and projected['title'] == before['title']
    query = parse_qs(urlsplit(projected['artifact_url']).query)
    assert query['sha256'] == [pointer['artifact_sha256']]
    assert frozen_artifact(project, ref['run_id'], query['sha256'][0]) == path.resolve()
    assert pointer == before
    # Repeated declarations of the identical retained path are not ambiguous files.
    basis['artifacts'].append(deepcopy(basis['artifacts'][0]))
    write_json_atomic(run_root / 'basis.json', basis)
    assert _report_material_projection(project, ref, pointer, basis, {})['source_verified']


def test_equal_byte_report_alias_opens_the_unique_retained_input(retained_report):
    project, ref, _, basis, pointer, path = retained_report
    pointer['artifact_id'] = 'artifact.audit-source.performance'
    before = deepcopy(pointer)
    assert 'source_error' in artifact_link(project, ref, pointer)
    projected = _report_material_projection(project, ref, pointer, basis, {})
    assert projected['source_verified'] and projected['source_kind'] == 'retained_input'
    assert projected['artifact_id'] == pointer['artifact_id']
    query = parse_qs(urlsplit(projected['artifact_url']).query)
    assert query == {'sha256': [pointer['artifact_sha256']]}
    assert frozen_artifact(project, ref['run_id'], query['sha256'][0]) == path.resolve()
    assert pointer == before
    assert 'source_error' in artifact_link(project, ref, pointer)


@pytest.mark.parametrize('change', ['missing', 'changed', 'ambiguous', 'undeclared', 'outside', 'wrong_digest',
                                  'conflicting_basis',
                                  'unpublished', 'wrong_branch', 'wrong_phase'])
def test_report_exhibit_never_substitutes_unavailable_or_unbound_input(retained_report, change):
    project, ref, run_root, basis, pointer, path = retained_report
    pointer['artifact_id'] = 'artifact.audit-source.performance'
    if change == 'missing':
        path.unlink()
    elif change == 'changed':
        path.write_bytes(b'[{"loss":0}]')
    elif change == 'ambiguous':
        second = path.with_name('other.json')
        second.write_bytes(path.read_bytes())
        basis['artifacts'].append({**basis['artifacts'][0], 'artifact_id': 'artifact.other', 'path': str(second)})
    elif change == 'undeclared':
        basis['artifacts'] = []
    elif change == 'outside':
        outside = run_root / 'unsubmitted.json'
        outside.write_bytes(path.read_bytes())
        basis['artifacts'][0]['path'] = str(outside)
    elif change == 'wrong_digest':
        pointer['artifact_sha256'] = sha256_bytes(b'different bytes')
    elif change == 'conflicting_basis':
        second = path.with_name('different-capture.json')
        second.write_bytes(path.read_bytes())
        basis = deepcopy(basis)
        basis['artifacts'][0]['path'] = str(second)
    else:
        run = {'state': 'published', 'branch_id': ref['branch'], 'phase': ref['phase']}
        run[{'unpublished': 'state', 'wrong_branch': 'branch_id', 'wrong_phase': 'phase'}[change]] = 'other'
        write_json_atomic(run_root / 'run.json', run)
    if change != 'conflicting_basis':
        write_json_atomic(run_root / 'basis.json', basis)
    projected = _report_material_projection(project, ref, pointer, basis, {})
    assert 'source_error' in projected and 'artifact_url' not in projected and not projected.get('source_verified')


def test_local_report_material_keeps_existing_output_action(retained_report):
    project, ref, run_root, basis, _, _ = retained_report
    path = run_root / 'outputs' / ref['stage_id'] / 'figure.svg'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"/>')
    pointer = {'path': path.name, 'sha256': sha256_bytes(path.read_bytes()), 'media_type': 'image/svg+xml'}
    projected = _report_material_projection(project, ref, pointer, basis, {ref['stage_id']: path.parent})
    assert projected == {**pointer, **artifact_link(project, ref, pointer)}
    assert projected['source_kind'] == 'output'
