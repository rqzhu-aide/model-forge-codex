"""Only the current author's exact readable primary bytes join math checking."""
import copy
import hashlib
import pytest

from model_forge_codex.catalog import Catalog
from model_forge_codex.domain import MemberRole
from model_forge_codex.math_validation import validate_authored_math
from test_draft_validation import REPO, check, codes, draft_engine, run, snapshot, write_outputs
from test_researcher_workbench_engine import scientific_output_documents


def pointer(path, content, media_type="text/markdown"):
    ref = {"artifact_id": "artifact.primary", "path": path,
           "sha256": hashlib.sha256(content).hexdigest()}
    if media_type is not None:
        ref["media_type"] = media_type
    return ref


@pytest.mark.parametrize("field", ["primary_artifact", "manuscript_artifact", "representations"])
def test_exact_primary_math_uses_shared_checker_and_own_pointer_without_mutation(tmp_path, field):
    content = b"Readable opening.\n\n$\\unknownPrimary{x}$\n"
    ref = pointer("primary.md", content)
    document = ({field: [{"information_layer": "primary_artifact", "artifact": ref}]}
                if field == "representations" else {field: ref})
    file = tmp_path / "primary.md"
    file.write_bytes(content)
    before = copy.deepcopy(document)
    findings = validate_authored_math({"p3.theory_candidate": document},
                                     artifact_roots={"p3.theory_candidate": tmp_path})
    assert len(findings) == 1
    finding = findings[0]
    expected = "/representations/0/artifact" if field == "representations" else "/" + field
    assert finding.code == "math.invalid_latex" and finding.blocks_publication
    assert finding.object_id == "p3.theory_candidate" and finding.json_pointer == expected
    assert finding.details == {"artifact_path": "primary.md", "artifact_sha256": ref["sha256"],
                               "character_offset": content.index(b"$")}
    assert "primary.md" in finding.message
    assert document == before and file.read_bytes() == content


def test_duplicate_primary_representation_is_checked_once_in_collected_working_folder(tmp_path):
    content = b"$$\\unknownPrimary{x}$$"
    ref = pointer("primary.md", content)
    document = {"primary_artifact": ref, "representations": [
        {"information_layer": "primary_artifact", "artifact": copy.deepcopy(ref)}]}
    file = tmp_path / "working/theorist/primary.md"
    file.parent.mkdir(parents=True)
    file.write_bytes(content)
    findings = validate_authored_math({"p3.theory_candidate": document},
                                     artifact_roots={"p3.theory_candidate": tmp_path})
    assert len(findings) == 1 and findings[0].json_pointer == "/primary_artifact"


@pytest.mark.parametrize("location", ["supplementary_artifacts", "artifacts", "justification",
                                     "canonical_artifact", "structured_record", "compact_decision_view"])
def test_other_declared_sources_are_not_primary_math_inputs(tmp_path, location):
    content = b"$\\unknownFrozenSource{x}$"
    (tmp_path / "source.md").write_bytes(content)
    ref = pointer("source.md", content)
    if location in {"structured_record", "compact_decision_view"}:
        document = {"representations": [{"information_layer": location, "artifact": ref}]}
    elif location == "justification":
        document = {"statements": [{"justification": {"source_artifacts": [ref]}}]}
    else:
        document = {location: [ref] if location.endswith("artifacts") else ref}
    assert validate_authored_math({"p3.theory_candidate": document},
                                 artifact_roots={"p3.theory_candidate": tmp_path}) == []


@pytest.mark.parametrize("case", ["missing", "mismatched", "outside", "non_markdown"])
def test_unverified_or_non_markdown_bytes_are_left_to_existing_artifact_checks(tmp_path, case):
    root = tmp_path / "owned"
    root.mkdir()
    content = b"$\\unknownPrimary{x}$"
    path = "primary.md"
    if case == "outside":
        path = "../primary.md"
    file = (root / path)
    if case != "missing":
        file.write_bytes(content)
    ref = pointer(path, b"Different retained bytes" if case == "mismatched" else content,
                  "application/pdf" if case == "non_markdown" else "text/markdown")
    assert validate_authored_math({"p3.theory_candidate": {"primary_artifact": ref}},
                                 artifact_roots={"p3.theory_candidate": root}) == []


@pytest.mark.parametrize("media_type,path", [(None, "primary.md"), (None, "primary.markdown"),
                                           ("text/markdown", "primary.txt")])
def test_valid_declared_markdown_and_math_preserve_exact_bytes(tmp_path, media_type, path):
    content = b"A valid claim.\n\n$$\\frac{1}{2}=0.5$$\n"
    file = tmp_path / path
    file.write_bytes(content)
    document = {"primary_artifact": pointer(path, content, media_type)}
    assert validate_authored_math({"p3.theory_candidate": document},
                                 artifact_roots={"p3.theory_candidate": tmp_path}) == []
    assert file.read_bytes() == content


def test_exact_declared_markdown_with_invalid_utf8_reports_owned_readability(tmp_path):
    content = b"Readable prefix\xff"
    (tmp_path / "primary.md").write_bytes(content)
    ref = pointer("primary.md", content)
    findings = validate_authored_math({"p3.theory_candidate": {"primary_artifact": ref}},
                                     artifact_roots={"p3.theory_candidate": tmp_path})
    assert len(findings) == 1 and findings[0].code == "math.primary_source_unreadable"
    assert findings[0].json_pointer == "/primary_artifact"
    assert findings[0].details["artifact_sha256"] == ref["sha256"]


def rewrite_primary(documents, files, content, family="p3.theory_candidate"):
    ref = documents[family]["primary_artifact"]
    path = ref["path"]
    files[path] = content
    digest = hashlib.sha256(content.encode()).hexdigest()

    def update(value):
        if isinstance(value, dict):
            if value.get("path") == path and "sha256" in value:
                value["sha256"] = digest
            for child in value.values():
                update(child)
        elif isinstance(value, list):
            for child in value:
                update(child)
    update(documents)
    return path


def test_file_only_math_failure_reaches_actual_p3_draft_and_final_gate(draft_engine):
    engine = draft_engine
    record, stages, identity = run(engine, "P3", "p3.theory_establishment")
    stage = stages[0]
    documents, files = scientific_output_documents(Catalog(REPO / "contracts"), "P3", identity)
    path = rewrite_primary(documents, files, "Only the primary has this defect. $$\\unknownPrimary{x}$$")
    owned = {family: documents[family] for family in stage.writes}
    workspace = engine.member_workspace(record, stage.stage_id, MemberRole.THEORIST)
    write_outputs(workspace, owned, files)
    before = snapshot(engine.data_root)
    draft = check(engine, record, stage, MemberRole.THEORIST)
    assert draft["status"] == "failed" and "math.invalid_latex" in codes(draft)
    assert any(f["object_id"] == "p3.theory_candidate" and f["json_pointer"] == "/primary_artifact"
               for f in draft["findings"] if f["code"] == "math.invalid_latex")
    assert snapshot(engine.data_root) == before
    sealed = engine.run_dir(record.project_id, record.run_id) / "outputs" / stage.stage_id
    write_outputs(sealed, owned, files)
    findings = engine._validate_run_outputs(record, [stage], [])
    assert any(f.code == "math.invalid_latex" and f.object_id == "p3.theory_candidate"
               and f.json_pointer == "/primary_artifact" for f in findings)
    assert (sealed / path).read_text(encoding="utf-8") == files[path]
    rewrite_primary(documents, files, "A corrected primary. $$\\frac{1}{2}=0.5$$")
    write_outputs(workspace, {family: documents[family] for family in stage.writes}, files)
    assert check(engine, record, stage, MemberRole.THEORIST)["status"] == "passed"
    write_outputs(sealed, {family: documents[family] for family in stage.writes}, files)
    assert not any(f.code.startswith("math.") for f in engine._validate_run_outputs(record, [stage], []))
    assert engine.bridge.turns == []


def test_p3_analyst_draft_and_gate_do_not_revalidate_prerequisite_primary(draft_engine):
    engine = draft_engine
    record, stages, identity = run(engine, "P3", "p3.theory_establishment")
    theorist, analyst = stages[:2]
    documents, files = scientific_output_documents(Catalog(REPO / "contracts"), "P3", identity)
    rewrite_primary(documents, files, "Frozen original only. $$\\unknownOriginal{x}$$")
    record.stage_states[theorist.stage_id] = "succeeded"
    sealed = engine.run_dir(record.project_id, record.run_id) / "outputs"
    write_outputs(sealed / theorist.stage_id, {family: documents[family] for family in theorist.writes}, files)
    owned = {family: documents[family] for family in analyst.writes}
    workspace = engine.member_workspace(record, analyst.stage_id, MemberRole.DATA_ANALYST)
    write_outputs(workspace, owned, files)
    assert not any(code.startswith("math.") for code in codes(check(engine, record, analyst, MemberRole.DATA_ANALYST)))
    write_outputs(sealed / analyst.stage_id, owned, files)
    assert not any(f.code.startswith("math.") for f in engine._validate_run_outputs(record, [analyst], [theorist]))


def test_current_lead_primary_is_checked_in_actual_draft_and_final_gate(draft_engine):
    engine = draft_engine
    record, stages, identity = run(engine, "P3", "p3.theory_establishment")
    documents, files = scientific_output_documents(Catalog(REPO / "contracts"), "P3", identity)
    lead = stages[-1]
    # The Lead authors a new readable account while retaining the original
    # Theorist proof and assumption source pointers unchanged.
    primary = copy.deepcopy(documents["p3.complete_theory"]["primary_artifact"])
    primary.update(path="lead-primary.md", artifact_id="artifact.lead.primary",
                   uri="artifact://artifact.lead.primary")
    documents["p3.complete_theory"]["primary_artifact"] = primary
    for representation in documents["p3.complete_theory"]["representations"]:
        if representation["information_layer"] == "primary_artifact":
            representation["artifact"] = copy.deepcopy(primary)
    path = rewrite_primary(documents, files, "Current Lead account.\n$\n\\unknownLead{x}\n$\n",
                           family="p3.complete_theory")
    sealed = engine.run_dir(record.project_id, record.run_id) / "outputs"
    for stage in stages[:-1]:
        write_outputs(sealed / stage.stage_id, {family: documents[family] for family in stage.writes}, files)
        record.stage_states[stage.stage_id] = "succeeded"
    owned = {family: documents[family] for family in lead.writes}
    workspace = engine.member_workspace(record, lead.stage_id, MemberRole.RESEARCH_LEAD)
    write_outputs(workspace, owned, files)
    draft = check(engine, record, lead, MemberRole.RESEARCH_LEAD)
    assert draft["status"] == "failed"
    assert any(f["code"] == "math.invalid_latex" and f["object_id"] == "p3.complete_theory"
               and f["json_pointer"] == "/primary_artifact" for f in draft["findings"])
    write_outputs(sealed / lead.stage_id, owned, files)
    assert any(f.code == "math.invalid_latex" and f.object_id == "p3.complete_theory"
               for f in engine._validate_run_outputs(record, [lead], stages[:-1]))
    assert (sealed / lead.stage_id / path).read_text(encoding="utf-8") == files[path]
    rewrite_primary(documents, files, "Current Lead account.\n$\nx=1\n$\n", family="p3.complete_theory")
    write_outputs(workspace, {family: documents[family] for family in lead.writes}, files)
    corrected = check(engine, record, lead, MemberRole.RESEARCH_LEAD)
    assert corrected["status"] == "passed", corrected["findings"]
    write_outputs(sealed / lead.stage_id, {family: documents[family] for family in lead.writes}, files)
    assert not any(f.code.startswith("math.") for f in engine._validate_run_outputs(record, [lead], stages[:-1]))
