"""Run-relative output references retain their exact source run and stage."""
import pytest

from model_forge_codex.records import ArtifactError, source_artifact_path
from model_forge_codex.storage import sha256_bytes


@pytest.mark.parametrize("filename", ["theory_candidate.json", "working/theorist/theory_manuscript.md"])
@pytest.mark.parametrize("with_uri", [False, True])
def test_run_relative_output_resolves_its_declared_stage(tmp_path, filename, with_uri):
    project = tmp_path / "project.test"
    source = project / "runs/run.p3.original/outputs/p3.theorist" / filename
    source.parent.mkdir(parents=True)
    content = b"The retained qualified theory source."
    source.write_bytes(content)
    pointer = {"path": "outputs/p3.theorist/" + filename, "sha256": sha256_bytes(content)}
    if with_uri:
        pointer["uri"] = "run://run.p3.original/outputs/p3.theorist/" + filename

    # A Lead decision may cite the Theorist's exact retained output.
    reference = {"run_id": "run.p3.original", "stage_id": "p3.lead"}
    assert source_artifact_path(project, reference, pointer) == source.resolve()


@pytest.mark.parametrize("mismatch", ["digest", "stage", "run", "uri_stage", "uri_run", "uri_path", "alternate_path"])
def test_run_relative_output_does_not_substitute_another_source(tmp_path, mismatch):
    project = tmp_path / "project.test"
    outputs = project / "runs/run.p3.original/outputs"
    source = outputs / "p3.theorist/theory.md"
    source.parent.mkdir(parents=True)
    content = b"The exact cited theory."
    source.write_bytes(content)
    pointer = {"path": "outputs/p3.theorist/theory.md", "sha256": sha256_bytes(content)}
    if mismatch == "digest":
        source.write_bytes(b"Changed source.")
    elif mismatch in ("stage", "run"):
        substitute = (outputs / "p3.lead/theory.md" if mismatch == "stage" else
                      project / "runs/run.p3.other/outputs/p3.theorist/theory.md")
        substitute.parent.mkdir(parents=True)
        source.rename(substitute)
    elif mismatch.startswith("uri_"):
        pointer["uri"] = {
            "uri_stage": "run://run.p3.original/outputs/p3.lead/theory.md",
            "uri_run": "run://run.p3.other/outputs/p3.theorist/theory.md",
            "uri_path": "run://run.p3.original/outputs/p3.theorist/other.md",
        }[mismatch]
    else:
        pointer["artifact_path"] = "outputs/p3.lead/theory.md"

    with pytest.raises(ArtifactError):
        source_artifact_path(project, {"run_id": "run.p3.original", "stage_id": "p3.lead"}, pointer)


@pytest.mark.parametrize("relative", [
    "outputs/p3.theorist/../p3.lead/theory.md",
    "outputs/p3.theorist/./theory.md",
    "outputs//p3.theorist/theory.md",
    "outputs/p3.theorist/../../inputs/notation.json",
    "outputs/../inputs/notation.json",
])
def test_run_relative_output_rejects_ambiguous_or_traversing_paths(tmp_path, relative):
    project = tmp_path / "project.test"
    output = project / "runs/run.p3.original/outputs/p3.theorist/theory.md"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"The exact source.")
    with pytest.raises(ArtifactError):
        source_artifact_path(project, {"run_id": "run.p3.original"},
                             {"path": relative, "sha256": sha256_bytes(output.read_bytes())})


def test_run_relative_output_cannot_follow_a_foreign_stage_link(tmp_path):
    project = tmp_path / "project.test"
    outputs = project / "runs/run.p3.original/outputs"
    foreign = outputs / "p3.lead/theory.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_bytes(b"A source in another stage.")
    try:
        (outputs / "p3.theorist").symlink_to(foreign.parent, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable for this account")
    with pytest.raises(ArtifactError):
        source_artifact_path(project, {"run_id": "run.p3.original"},
                             {"path": "outputs/p3.theorist/theory.md", "sha256": sha256_bytes(foreign.read_bytes())})


def test_stage_relative_output_lookup_remains_available(tmp_path):
    project = tmp_path / "project.test"
    source = project / "runs/run.p3.original/outputs/p3.theorist/working/theorist/theory.md"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"The retained legacy source.")
    assert source_artifact_path(project, {"run_id": "run.p3.original", "stage_id": "p3.theorist"},
                                {"path": "theory.md", "sha256": sha256_bytes(source.read_bytes())}) == source.resolve()
