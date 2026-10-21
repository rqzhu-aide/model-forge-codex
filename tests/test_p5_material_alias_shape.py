"""Single aliases for new reports; malformed original submissions stay reviewable."""
from pathlib import Path

import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.p5_review_packet import prepare_review_packet, read_review_packet
from model_forge_codex.records import ArtifactError
from model_forge_codex.storage import read_json, sha256_file
from model_forge_codex.technical_reports import export_technical_report, report_required_artifacts
from test_p5_retained_artifact_scalar import artifact_quote
from test_technical_reports import report_case

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('alias', [['sources/paired.json'], [], {}, None, ''])
def test_new_authored_report_rejects_nonstring_or_empty_material_alias(alias):
    catalog = Catalog(REPO / 'contracts')
    report = read_json(REPO / 'contracts/examples/technical-report.example.json')
    report['artifact_authored_paths'] = {'artifact.paired': alias}
    findings = catalog.validate_output('p5.technical_report_candidate', report)
    assert findings and all('artifact_authored_paths' in item.json_pointer for item in findings)
    report['artifact_authored_paths']['artifact.paired'] = 'sources/paired.json'
    assert catalog.validate_output('p5.technical_report_candidate', report) == []


def test_original_array_alias_packet_retains_exact_submission_and_clear_export_error(report_case, tmp_path, monkeypatch):
    report, basis, roots, frozen, _, artifact, pointer = artifact_quote(report_case)
    report['artifact_authored_paths'] = {'artifact.paired': ['sources/paired.json', 'reproduction/paired.json']}
    primary = next(iter(roots.values())) / 'report.md'
    basis['artifacts'].append({'path': str(primary), 'content_sha256': sha256_file(primary)})
    reference = frozen('P5', 'technical_report', report)
    source = tmp_path / 'technical_report.json'
    before = {path: path.read_bytes() for path in (primary, artifact, source)}
    required = next(item for item in report_required_artifacts(report, basis) if item.get('artifact_id') == 'artifact.paired')
    assert required['authored_path'] == report['artifact_authored_paths']['artifact.paired']
    packet = prepare_review_packet(tmp_path / 'review', basis=basis, instructions='Review this original unresolved-alias submission.',
                                  run_id='run.review', project_dir=tmp_path)
    directory = tmp_path / 'review/review-packet'
    assert read_review_packet(directory) == packet
    assert packet['target']['content_sha256'] == reference['content_sha256']
    assert packet['target']['report_artifact_sha256'] == report['report_artifact']['sha256']
    materials = read_json(directory / 'materials.json')
    material = next(item for item in materials['materials'] if item['sha256'] == pointer['sha256'])
    assert material['authored_path'] == report['artifact_authored_paths']['artifact.paired']
    assert (directory / material['submitted_name']).read_bytes() == artifact.read_bytes()
    monkeypatch.setattr('model_forge_codex.technical_reports.subprocess.run', lambda *a, **k: pytest.fail('Malformed alias must fail before rendering'))
    with pytest.raises(ArtifactError, match='artifact_authored_paths.*one relative path, not an array'):
        export_technical_report(report, basis, generation_ref=reference, artifact_roots=roots, exported_at='2026-10-13T12:00:00Z')
    assert all(path.read_bytes() == data for path, data in before.items())


def test_single_material_alias_resolves_in_portable_report_without_source_changes(report_case):
    report, basis, roots, _, _, artifact, _ = artifact_quote(report_case)
    primary = next(iter(roots.values())) / 'report.md'
    primary.write_text(primary.read_text(encoding='utf-8') + '\n\n[Paired data](sources/paired.json)\n', encoding='utf-8')
    report['report_artifact']['sha256'] = sha256_file(primary)
    before = {path: path.read_bytes() for path in (primary, artifact)}
    html = export_technical_report(report, basis, generation_ref={'generation_id': 'generation.report', 'content_sha256': 'c' * 64},
                                  artifact_roots=roots, exported_at='2026-10-13T12:00:00Z').decode('utf-8')
    assert '<a href="data:application/json;base64,' in html
    assert '>Paired data</a>' in html
    assert all(path.read_bytes() == data for path, data in before.items())
