#!/usr/bin/env python3
"""Run a simulated assumption-conversation preview using the real engine/API.

From the repository root with shared Python packages:
    python scripts/assumption_conversations_preview.py

In a second PowerShell terminal:
    $env:MF_API_URL = 'http://127.0.0.1:8774'
    $env:MF_WEB_PORT = '5174'
    node web/scripts/vite.mjs dev

Open http://127.0.0.1:5174, choose "Assumption conversations (simulated)",
select P3, then Assumption A1. Two separate conversations are seeded. Every
answer is scripted, not generated research. Only prepared A1 questions receive
scientific examples; other questions explicitly report the simulation limit.
Prefix a question with [slow]
to delay its answer by 12 seconds or [fail] to fail until explicitly retried.

The private preview home is reused without erasing data. Supply --home to
choose another empty directory and --seed-only to prepare it without serving.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tests")]

from model_forge_codex.accounts import AccountError, AccountService
from model_forge_codex.bridge import FakeCodexBridge
from model_forge_codex.domain import RunState
from model_forge_codex.members import provision_team
from model_forge_codex.methods import activate_method
from model_forge_codex.records import current_records
from model_forge_codex.service import create_app
from model_forge_codex.storage import read_json, write_json_atomic
from test_researcher_workbench_engine import publish, script_scientific_run


PROJECT_ID = "project.test"  # The existing scientific fixture uses this ID.
ASSUMPTION_ID = "assumption.example_a1"
PREVIEW_KIND = "assumption-conversations-simulated-v1"


class PreviewAccounts(AccountService):
    """Keep this simulated service independent of the host's real account."""

    def _writable(self):
        raise AccountError("Account connection is disabled in this simulated preview.")

    async def status(self):
        return {
            "state": "signed_out", "read_only": True,
            "message": "Simulated preview: no model calls or account connection.",
            "login_url": None, "user_code": None,
            "can_connect_existing": False, "connected": False,
            "member_homes": {"connected": 0, "existing": 0, "total": 4},
            "provider_config": {"path": str(self.data_root / "providers.toml"),
                                "exists": False, "active": False, "error": None},
        }


def scripted_explanation(question: str, assumption_id: str) -> tuple[str, bool]:
    """Prepared demo answers only; unsupported questions must not look answered."""
    normalized = " ".join(question.lower().split()).removeprefix("[slow] ").removeprefix("[fail] ").rstrip("?.")
    if assumption_id == ASSUMPTION_ID:
        if normalized in {
            "what happens if we do not have this assumption", "what happens without this assumption",
            "what happens if this assumption fails", "what if we drop this assumption",
        }:
            return (
                "**Simulated explanation.** Without Assumption A1, the saved proof no longer "
                "justifies the uniform-consistency guarantee, and asymptotic normality is "
                "unverified outside its stated assumptions. **This does not show that the estimator fails.**\n\n"
                "The recorded consequence is specific: the maximal inequality used to control "
                "the estimation error uniformly no longer supplies the stated uniform rate. "
                "The saved work therefore does not establish the same convergence guarantee "
                "when the sub-Gaussian condition is removed.\n\n"
                "The sensitivity note suggests that normality might survive under a finite "
                "fourth moment, but explicitly leaves that possibility unverified. Whether "
                "consistency or normality actually fails requires a new argument or a "
                "counterexample; it is not settled by this record.", True,
            )
        if normalized == "does the saved proof establish that this assumption is necessary":
            return (
                "**Simulated explanation.** No. The saved work uses Assumption A1 to prove "
                "its results, but does not establish that those results must fail without it. "
                "The sensitivity note identifies a loss of the stated uniform-rate guarantee "
                "and leaves possible normality under a finite fourth moment unverified.", True,
            )
        if normalized == "can you give me a simple example where it fails":
            return (
                "**Simulated explanation.** A heavy-tailed error illustrates what the tail "
                "condition excludes. For example, a centered Student $t_3$ variable has finite "
                "variance but no finite moment-generating function at any nonzero argument. "
                "It therefore cannot satisfy the sub-Gaussian bound.\n\n"
                "This is an illustrative failure of Assumption A1. It does not establish that "
                "the estimator is inconsistent. The recorded sensitivity note says that the "
                "uniform rate is no longer guaranteed by the stated maximal inequality, and "
                "that a relaxation for normality remains unverified.", True,
            )
        if normalized in {"why is this assumption needed", "why is this needed"}:
            return (
                "**Simulated explanation.** The saved theory uses Assumption A1 to control "
                "the tails of the errors in the maximal inequality for the consistency proof. "
                "It also lists A1 among the conditions for asymptotic normality.\n\n"
                "For intuition, a centered sub-Gaussian error $X$ with variance proxy "
                "$\\sigma^2$ obeys\n\n"
                "$$\\Pr(|X| \\ge t) \\le 2\\exp\\!\\left(-\\frac{t^2}{2\\sigma^2}\\right).$$\n\n"
                "Such bounds help control many errors at once. This formula illustrates "
                "the assumption's role; the saved argument does not establish that the "
                "assumption is necessary.", True,
            )
    return (
        "**Simulated preview.** No model was called, and this preview has no prepared "
        "answer to your question about this assumption. Your question is saved, but "
        "no scientific answer has been generated. Arbitrary questions require the "
        "live workbench with a configured Theorist provider.", False,
    )


class ConversationPreviewBridge(FakeCodexBridge):
    """Script explanations and deliberate delays/failures by saved question."""

    async def run_turn(self, thread_id, **kwargs):
        brief = kwargs["brief_path"]
        run_dir = brief.parent.parent
        record = read_json(run_dir / "run.json") or {}
        if record.get("assessment_purpose") == "explanation":
            question = record.get("instructions", "")
            if question.lower().startswith("[slow]"):
                kwargs["heartbeat"]("Simulated answer: waiting 12 seconds.")
                await asyncio.sleep(12)
            if question.lower().startswith("[fail]") and not record.get("retry_run_id"):
                behavior = ("fail", "Simulated response failure. Choose Retry to complete this question.")
            else:
                target = record["target"]
                answer, uses_source = scripted_explanation(question, target["object_id"])
                response = {
                    "headline": "Simulated assumption explanation",
                    "assessment_markdown": answer,
                    "limitations": [], "suggested_actions": [],
                    "evidence_refs": [{"family": target["family"],
                                       "generation_id": target["generation_id"],
                                       "object_id": target["object_id"]}] if uses_source else [],
                }
                behavior = ("ok", {"assessment.json": json.dumps(response)})
            self.script[thread_id] = [behavior]
        return await super().run_turn(thread_id, **kwargs)


async def seed(engine, home: Path):
    marker = home / "preview.json"
    existing = read_json(marker)
    if existing:
        if existing.get("kind") != PREVIEW_KIND:
            raise RuntimeError("This directory belongs to a different preview.")
        if not (home / "projects" / PROJECT_ID / "project.json").is_file():
            raise RuntimeError("Preview metadata exists but its project is missing; choose a fresh --home.")
        return existing
    if any(home.iterdir()):
        raise RuntimeError("Choose an empty --home. This preview never deletes existing data.")
    (home / ".gitignore").write_text("*\n", encoding="utf-8")
    project = home / "projects" / PROJECT_ID
    project.mkdir(parents=True)
    write_json_atomic(project / "project.json", {
        "project_id": PROJECT_ID,
        "name": "Assumption conversations (simulated)",
        "research_question": "How do the recorded assumptions support tapered quantile estimation?",
        "research_instructions": "This is a deterministic simulated UI preview. All explanations are scripted.",
    })
    shutil.copytree(REPO / "contracts", project / "contracts")
    provision_team(project)
    method = read_json(REPO / "contracts/examples/method.example.json")
    publish(project, "trunk", "P1", {"literature_synthesis": {"headline": "Simulated frozen literature"}})
    publish(project, "trunk", "P2", {"method_catalog": {"methods": [method]}})
    branch = activate_method(project, method["identity"]["stable_id"])["branch_id"]
    script_scientific_run(engine, project, branch, "P3", "p3.theory_establishment")
    scientific = await engine.start_run(PROJECT_ID, phase="P3", mode="p3.theory_establishment", branch_id=branch)
    await engine._tasks[scientific.run_id]
    final = engine.load_run(PROJECT_ID, scientific.run_id)
    if final.state is not RunState.PUBLISHED:
        raise RuntimeError(f"Preview theory did not publish: {final.terminal_reason}")
    pointer = current_records(project / "branches" / branch / "phases/p3")["theory_record"]
    target = {"branch": branch, "phase": "P3", "family": "theory_record",
              "generation_id": pointer["generation_id"], "sha256": pointer["content_sha256"],
              "run_id": pointer["run_id"], "object_id": ASSUMPTION_ID, "kind": "assumption"}

    async def ask(question, assessment_id=None):
        turn = await engine.start_run(
            PROJECT_ID, phase="P3", mode="p3.assessment", branch_id=branch,
            intent="assessment", assessment_purpose="explanation", target=target,
            assessment_id=assessment_id, instructions=question,
        )
        await engine._tasks[turn.run_id]
        finished = engine.load_run(PROJECT_ID, turn.run_id)
        if finished.state is not RunState.ASSESSED:
            raise RuntimeError(f"Preview explanation failed: {finished.terminal_reason}")
        return turn.assessment_id

    first = await ask("Why is this assumption needed?")
    await ask("Can you give me a simple example where it fails?", first)
    second = await ask("Does the saved proof establish that this assumption is necessary?")
    metadata = {"kind": PREVIEW_KIND, "simulated": True, "project_id": PROJECT_ID,
                "branch_id": branch, "assumption_id": ASSUMPTION_ID,
                "target": target, "assessment_ids": [first, second]}
    write_json_atomic(marker, metadata)
    return metadata


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=REPO / ".assumption-conversations-preview")
    parser.add_argument("--port", type=int, default=8774)
    parser.add_argument("--seed-only", action="store_true")
    args = parser.parse_args()
    home = args.home.resolve()
    home.mkdir(parents=True, exist_ok=True)
    # Isolate simulation from any operator-selected provider file or viewer mode.
    os.environ["MF_CODEX_PROVIDER_CONFIG"] = str(home / "providers.toml")
    os.environ["MF_CODEX_FAKE_BRIDGE"] = "1"
    os.environ["MF_CODEX_READ_ONLY"] = "0"
    app = create_app(home, ConversationPreviewBridge(), PreviewAccounts(home))
    metadata = await seed(app.state.engine, home)
    print(json.dumps({**metadata, "home": str(home), "api_url": f"http://127.0.0.1:{args.port}"}, indent=2), flush=True)
    if not args.seed_only:
        import uvicorn
        await uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port)).serve()


if __name__ == "__main__":
    asyncio.run(main())
