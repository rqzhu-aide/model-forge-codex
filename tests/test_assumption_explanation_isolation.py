"""Explanation turns leave saved research and the scientific member unchanged."""
from dataclasses import asdict

from model_forge_codex.domain import MemberRole, RunState, ThreadKey
from model_forge_codex.threads import ThreadRegistry
from test_assumption_conversations import ask, set_answer
from test_researcher_workbench_engine import seed_theory, workbench


async def test_explanation_and_followup_preserve_science_publication_and_existing_memory(workbench):
    engine, project, branch = workbench
    package = seed_theory(project, branch)
    notebook = project / "members/theorist/notebooks" / f"{branch}.md"
    notebook.parent.mkdir(parents=True)
    notebook.write_text("SCIENTIFIC_CONTINUING_MEMORY_ONLY\n", encoding="utf-8")
    scientific_key = ThreadKey(member=MemberRole.THEORIST, phase="P3", branch_id=branch)
    registry = ThreadRegistry(project / "branches" / branch)
    registry.register(scientific_key, "existing-scientific-thread")
    registry.note_turn(scientific_key)
    existing_thread = asdict(registry.lookup(scientific_key))

    def saved_research():
        # Phase snapshots include every generation, package, and publication pointer.
        roots = [project / name for name in ("members", "methods", "authority")]
        roots += list((project / "branches").glob("*/phases"))
        return {str(path.relative_to(project)): path.read_bytes()
                for root in roots for path in root.rglob("*") if path.is_file()}

    before = saved_research()
    set_answer(engine, package)
    first = await ask(engine, branch, package, "Why is this assumption needed?")
    followup = await ask(engine, branch, package, "Give an example.", assessment_id=first.assessment_id)

    assert first.state is followup.state is RunState.ASSESSED
    assert saved_research() == before
    registry.reload()
    assert asdict(registry.lookup(scientific_key)) == existing_thread
    assert len(engine.bridge.turns) == 2
    assert all(turn["thread_id"] != "existing-scientific-thread" for turn in engine.bridge.turns)
    assert all("SCIENTIFIC_CONTINUING_MEMORY_ONLY" not in turn["brief"] for turn in engine.bridge.turns)
    assert engine.bridge.turns[0]["thread_id"] != engine.bridge.turns[1]["thread_id"]
