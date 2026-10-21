"""The declared report primary is checked even without a duplicate representation."""
import copy
import hashlib

from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole
from model_forge_codex.storage import read_json, write_json_atomic
from test_draft_validation import REPO, check, draft_engine, run, snapshot, write_outputs
from test_researcher_workbench_engine import scientific_output_documents


def test_declared_technical_report_math_reaches_actual_draft_and_final_gate(draft_engine):
    engine = draft_engine
    current, stages, identity = run(engine, 'P5', 'p5.assembly')
    stage = stages[0]
    catalog = Catalog(REPO / 'contracts')
    documents, files = scientific_output_documents(catalog, 'P5', identity)
    report = documents['p5.technical_report_candidate']
    report['representations'] = []  # Schema allows this; report_artifact remains mandatory.
    documents['p5.claim_traceability'] = []
    documents['p5.attention_items'] = []
    directory = engine.run_dir(current.project_id, current.run_id)
    basis = read_json(directory / 'basis.json')
    basis['problem_context'] = {**copy.deepcopy(report['problem_context_ref']), 'items': []}
    write_json_atomic(directory / 'basis.json', basis)
    pointer = report['report_artifact']
    path = pointer['path']
    headings = '\n\n'.join(f'<a id="{anchor}"></a>\n## {section.replace("_", " ")}'
                            for section, anchor in report['section_anchors'].items())
    workspace = engine.member_workspace(current, stage.stage_id, MemberRole.RESEARCH_LEAD)
    sealed = directory / 'outputs' / stage.stage_id

    def save(text):
        files[path] = headings + '\n\n' + text
        pointer['sha256'] = hashlib.sha256(files[path].encode()).hexdigest()
        assert catalog.validate_output('p5.technical_report_candidate', report) == []
        owned = {family: documents[family] for family in stage.writes}
        write_outputs(workspace, owned, files)
        write_outputs(sealed, owned, files)

    save('The file alone has invalid math. $$\\unknownReport{x}$$')
    before = snapshot(engine.data_root)
    draft = check(engine, current, stage, MemberRole.RESEARCH_LEAD)
    assert any(f['code'] == 'math.invalid_latex' and f['object_id'] == 'p5.technical_report_candidate'
               and f['json_pointer'] == '/report_artifact' and f['details']['artifact_sha256'] == pointer['sha256']
               for f in draft['findings'])
    assert snapshot(engine.data_root) == before
    final = engine._validate_run_outputs(current, [stage], [], scoped_outputs={'p5.technical_report_candidate'})
    errors = [f for f in final if f.code.startswith('math.')]
    assert len(errors) == 1 and errors[0].code == 'math.invalid_latex' and errors[0].blocks_publication
    assert errors[0].object_id == 'p5.technical_report_candidate' and errors[0].json_pointer == '/report_artifact'
    assert (workspace / path).read_bytes() == (sealed / path).read_bytes() == files[path].encode()

    save('Corrected owned math. $$\\frac{1}{2}=0.5$$')
    before = snapshot(engine.data_root)
    corrected = check(engine, current, stage, MemberRole.RESEARCH_LEAD)
    assert not any(f['code'].startswith('math.') for f in corrected['findings'])
    assert snapshot(engine.data_root) == before
    final = engine._validate_run_outputs(current, [stage], [], scoped_outputs={'p5.technical_report_candidate'})
    assert not any(f.code.startswith('math.') for f in final)
    assert (workspace / path).read_bytes() == (sealed / path).read_bytes() == files[path].encode()
    assert engine.bridge.turns == []
