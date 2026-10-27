"""Actual P5 member collection retains owned scientific bytes and explicit aliases."""
import json
import hashlib
import os
from copy import deepcopy

import pytest

from model_forge_codex.domain import MemberRole
from model_forge_codex.runs import owned_writes
from model_forge_codex.storage import read_json, sha256_file, write_json_atomic
from model_forge_codex.technical_reports import CONTENT_SECTIONS, derive_report_completion, export_technical_report, report_required_artifacts, resolve_report_artifact
from test_p5_owned_questions_preflight import frozen_run
from test_researcher_workbench_engine import scientific_output_documents, workbench
from test_technical_reports import report_case


@pytest.mark.parametrize('alias,authored_path', [
    ('source/declared-trace.json', 'claim_traceability.json'),
    (None, 'claim_traceability.json'),
    (['source/legacy-trace.json'], 'claim_traceability.json'),
    ('source/declared-trace.json', './claim_traceability.json'),
    pytest.param('source/declared-trace.json', '.\\claim_traceability.json',
                 marks=pytest.mark.skipif(os.name != 'nt', reason='Backslash is a native Windows path separator')),
])
async def test_actual_member_collection_preserves_owned_snapshot_and_single_alias(workbench, report_case, alias, authored_path):
    engine, project, branch = workbench
    current, stages, directory, basis = frozen_run(engine, project, branch, report_case, mode='p5.assembly')
    ledger = {'issues': []}
    basis['cumulative_inputs'] = {'review_issue_ledger': {'document': ledger, 'sha256': engine._cumulative_digest(ledger)}}
    write_json_atomic(directory / 'basis.json', basis)
    stage = stages[0]
    documents, files = scientific_output_documents(engine._catalog(current), 'P5', basis['method']['identity'], mode='p5.assembly')
    report = documents['p5.technical_report_candidate']
    documents['p5.claim_traceability'] = []
    documents['p5.attention_items'] = []
    report['problem_context_ref'] = {'revision': basis['problem_context']['revision'], 'sha256': basis['problem_context']['sha256']}
    report['supplementary_artifacts'] = []
    report['artifact_authored_paths'] = {}
    trace_bytes = json.dumps(documents['p5.claim_traceability']).encode('utf-8')
    trace = {'artifact_id': 'artifact.owned-trace', 'uri': 'artifact://artifact.owned-trace', 'path': authored_path,
             'sha256': hashlib.sha256(trace_bytes).hexdigest(), 'media_type': 'application/json'}
    report['supplementary_artifacts'].append(trace)
    if alias is not None:
        report['artifact_authored_paths']['artifact.owned-trace'] = deepcopy(alias)
    expected_alias = alias if isinstance(alias, str) else 'claim_traceability.json'
    primary_name = report['report_artifact']['path']
    files[primary_name] = '\n\n'.join(
        f'<a id="{report["section_anchors"][section]}"></a>\n'
        f'## {section.replace("_", " ").capitalize()}\n\n'
        'Synthetic report content for the collection fixture.'
        for section in (*CONTENT_SECTIONS, 'references')
    )
    files[primary_name] += '\n\n[Claim trace](' + expected_alias + ')\n'
    for pointer in engine._artifact_pointers(report):
        if pointer.get('path') == primary_name:
            pointer['sha256'] = hashlib.sha256(files[primary_name].encode('utf-8')).hexdigest()
    report['completion'] = derive_report_completion(report, basis)
    writes = dict(files)
    for output in owned_writes(stage, MemberRole.RESEARCH_LEAD):
        writes[engine._output_filename(output)] = json.dumps(documents[output])
    engine.bridge.script_thread('research_lead:PROJECT:trunk', [('ok', writes)])
    result = await engine._drive_member_turn(current, stage, MemberRole.RESEARCH_LEAD, directory)
    assert result.succeeded, result.diagnostic
    workspace = engine.member_workspace(current, stage.stage_id, MemberRole.RESEARCH_LEAD)
    collected = directory / 'outputs' / stage.stage_id
    raw_trace = workspace / 'claim_traceability.json'
    saved_trace = collected / 'working/research_lead/claim_traceability.json'
    assert raw_trace.read_bytes() == saved_trace.read_bytes() == (collected / 'claim_traceability.json').read_bytes() == trace_bytes
    candidate = read_json(collected / 'technical_report_candidate.json')
    pointer = candidate['supplementary_artifacts'][0]
    assert pointer['path'] == 'working/research_lead/' + authored_path.replace('\\', '/')
    assert pointer['sha256'] == sha256_file(saved_trace)
    assert candidate['artifact_authored_paths']['artifact.owned-trace'] == expected_alias
    material = next(p for p in report_required_artifacts(candidate, basis) if p.get('artifact_id') == 'artifact.owned-trace')
    assert material['authored_path'] == expected_alias
    assert resolve_report_artifact(material, basis, roots=[collected]) == saved_trace
    findings = engine._validate_run_outputs(current, [stage])
    assert not [f for f in findings if f.blocks_publication], [(f.code, f.message) for f in findings]
    assert (workspace / 'technical_report_candidate.json').read_bytes() == writes['technical_report_candidate.json'].encode('utf-8')
    seal = read_json(collected / 'seal.json')
    assert seal['outputs']['technical_report_candidate.json']['sha256'] == sha256_file(collected / 'technical_report_candidate.json')
    html = export_technical_report(candidate, basis, generation_ref={'generation_id': 'generation.fixture', 'content_sha256': 'c' * 64},
                                  artifact_roots={'p5.technical_report_candidate': collected}, exported_at='2026-10-13T12:00:00Z').decode('utf-8')
    assert '<a href="data:application/json;base64,' in html and '>Claim trace</a>' in html
    assert len(engine.bridge.turns) == 1


async def test_collector_still_rejects_another_parallel_members_owned_output(workbench, report_case):
    engine, project, branch = workbench
    current, stages, directory, _ = frozen_run(engine, project, branch, report_case)
    stage = stages[0]
    engine.bridge.script_thread('theorist:P5:' + branch, [('ok', {'theory_audit.json': '[]', 'empirical_audit.json': '[]'})])
    result = await engine._drive_member_turn(current, stage, MemberRole.THEORIST, directory)
    assert not result.succeeded and 'wrote another member' in result.diagnostic
    assert not (directory / 'outputs' / stage.stage_id / 'working').exists()
    assert len(engine.bridge.turns) == 1
