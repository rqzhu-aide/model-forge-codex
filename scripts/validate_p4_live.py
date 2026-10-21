"""Bounded live-provider acceptance against an isolated, explicit test method.

Uses the operator's already connected provider without changing team settings.
The synthetic P1/P2 inputs are test fixtures, not a validated research pipeline.
No package installation, publication to another service, or production run occurs.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from uuid import uuid4

from model_forge_codex.accounts import AccountService
from model_forge_codex.bridge import SdkCodexBridge
from model_forge_codex.domain import MemberRole
from model_forge_codex.members import provision_team, codex_home
from model_forge_codex.methods import activate_method
from model_forge_codex.records import publish_package
from model_forge_codex.runs import RunEngine
from model_forge_codex.storage import read_json, write_json_atomic

REPO = Path(__file__).resolve().parents[1]


def seed_method(ambiguous=False):
    definition = {
        "definition_schema_version": "1.0.0",
        "target_or_estimand": {"object_id": "estimand.mean", "symbol": "\\mu", "definition": "The population mean E[X].", "domain": "Real independent observations with finite variance."},
        "objective_or_estimating_equation": {"object_id": "equation.mean", "symbol": "\\hat\\mu", "definition": "n^{-1}\\sum_{i=1}^n(X_i-\\hat\\mu)=0", "domain": "n >= 1"},
        "algorithm_or_update_rule": [{"step_id": "step.average", "order": 1, "operation": "Sum all observations and divide by n."}],
        "constraints_and_normalization": [], "tuning_definition": [],
        "calculation_defining_assumptions": [{"assumption_id": "assumption.iid", "statement": "Observations are independent and identically distributed with finite variance.", "mathematical_role": "Defines the intended sampling regime."}],
    }
    if ambiguous:
        definition["algorithm_or_update_rule"][0]["operation"] = "Clip observations at a threshold c, then average. The clipping threshold c and its selection rule have not been specified."
        definition["objective_or_estimating_equation"]["definition"] = "Average clip(X_i, -c, c). The value and selection rule of c are unspecified."
    digest = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
    return {
        "identity": {"stable_id": "method.acceptance_mean", "version": 1, "definition_sha256": digest},
        "title": "Sample mean acceptance fixture" if not ambiguous else "Ambiguous clipping acceptance fixture",
        "lifecycle_state": "active", "scientific_question": "Is this implementation useful for estimating a normal population mean?",
        "summary": "A deliberately simple known method for testing the evaluation workflow, with no novelty claim.",
        "rationale": "Compare statistical error and computation to the sample median, and document the limits under contamination.",
        "mathematical_definition": {"canonical_definition": definition},
        "assumptions": [{"assumption_id": "assumption.iid", "statement": "Independent identically distributed observations with finite variance.", "role": "sampling"}],
    }


def prepare(root, provider_root, ambiguous):
    project = root / "projects" / "project.p4_acceptance"
    project.mkdir(parents=True)
    write_json_atomic(project / "project.json", {"project_id": project.name,
        "name": "Isolated Phase 4 live acceptance", "research_instructions":
        "Evaluate the exact method for estimating the mean of normal data. The sample median is the practical baseline. "
        "This is a small software acceptance study, not a novelty claim. Use standard-library Python only. "
        "Keep the scientific account concise and make no external source searches; the supplied exact test method is self-contained."})
    shutil.copytree(REPO / "contracts", project / "contracts")
    provision_team(project)
    # Reuse the account already connected to the application. Never print or
    # include credential bytes in acceptance evidence.
    connected = AccountService(provider_root)._connected_cache_bytes()
    if connected:
        for role in MemberRole:
            destination = codex_home(project, role) / "auth.json"
            descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(connected)
    def publish(phase, docs):
        publish_package(project / "branches" / "trunk" / "phases" / phase.lower(),
            {name: json.dumps(value).encode() for name, value in docs.items()}, run_id="run.acceptance.seed", phase=phase, branch_id="trunk")
    publish("P1", {"literature_synthesis": {"headline": "Self-contained acceptance fixture; no literature or novelty assessment is asserted."}})
    method = seed_method(ambiguous)
    publish("P2", {"method_catalog": {"methods": [method]}})
    branch = activate_method(project, method["identity"]["stable_id"])["branch_id"]
    return project, branch


async def main(args):
    root = Path(args.data_root).resolve() if args.data_root else REPO / ".p4-acceptance" / ("live-" + uuid4().hex[:12])
    root.mkdir(parents=True, exist_ok=True)
    provider_root = Path(args.provider_root).expanduser().resolve()
    os.environ["MF_CODEX_PROVIDER_CONFIG"] = str(provider_root / "providers.toml")
    engine = RunEngine(root, SdkCodexBridge())
    scope = ("Feasibility only: exact check on [1,2,3], then normal samples comparing sample mean and median at n=20 with 20 repetitions. "
             "Do not add n=100 or contamination studies to this preliminary scope."
             if args.mode == "p4.preliminary" else
             "Detailed: include the exact check, normal samples at n=20 and n=100, and a clearly labeled contamination stress case, "
             "20 repetitions per setting; record squared error, per-fit runtime and failures, no tuning study because no tuning parameter exists. "
             "Schedule three separate work items: implementation/timing pilot, the normal-data comparison, and the contamination comparison. "
             "Inspect the pilot and then each comparison before dispatching the next work item.")
    instructions = (
        "Run the smallest scientifically coherent acceptance evaluation for this scope. "
        + scope + " "
        "The computation itself should take seconds. Use small scripts with real outputs, an implementation table, baseline comparison table "
        "and for detailed scope one SVG from actual results. Avoid any invented examples or numerical values. "
        "Write the protocol and submit save_plan before run_batch. Use the host checkpoint tool, and examine its feedback carefully. "
        "In JavaScript tool wrappers use text(await tools.p4_checkpoint({...})) to display the entire response. "
        "Every run_batch needs a unique batch_id. Each batch must execute only one declared work item, with completed dependencies. "
        "Finalize metadata before save_plan; after that preserve the original plan and add prospective amendments for changed work. "
        "Do not repair scientific ambiguity. If the frozen definition is missing a required choice, request_decision before any experiments. "
        "Keep prose concise, explicit about uncertainty, and scoped to this acceptance study."
    )
    started = time.monotonic()
    if args.resume_run:
        if not args.data_root or not args.continue_answer:
            raise ValueError("Resuming requires the existing --data-root and explicit --continue-answer")
        project = root / "projects" / "project.p4_acceptance"
        engine.reconcile_on_boot()
        previous = engine.load_run(project.name, args.resume_run)
        pending = (engine.p4_progress(previous) or {}).get("pause_request") or {}
        record = await engine.continue_p4(project.name, previous.run_id,
            request_id=pending.get("request_id"), expected_revision=pending.get("revision"),
            answer=args.continue_answer, idempotency_key="acceptance." + uuid4().hex)
    else:
        project, branch = prepare(root, provider_root, args.ambiguous)
        record = await engine.start_run(project.name, phase="P4", mode=args.mode, branch_id=branch,
                                        instructions=instructions, budget_seconds=args.budget)
    report = {"data_root": str(root), "project_id": project.name, "run_id": record.run_id,
              "mode": record.mode, "seeded_ambiguity": args.ambiguous, "synthetic_upstream_inputs": True,
              "resumed_run": bool(args.resume_run),
              "experiment_budget_seconds": record.experiment_budget_seconds, "wall_limit_seconds": args.wall_limit}
    print(json.dumps(report), flush=True)
    write_json_atomic(Path(args.report), report)
    try:
        deadline = time.monotonic() + args.wall_limit
        while not engine._tasks[record.run_id].done() and time.monotonic() < deadline:
            await asyncio.sleep(min(15, max(0, deadline - time.monotonic())))
            current = engine.load_run(project.name, record.run_id)
            events, _ = engine.run_events(project.name, record.run_id)
            print(json.dumps({"state": current.state.value, "elapsed_seconds": round(time.monotonic()-started),
                              "last_event": events[-1] if events else None}), flush=True)
        if not engine._tasks[record.run_id].done():
            report["wall_limit_reached"] = True
            await engine.pause_p4(project.name, record.run_id)
        else:
            await engine._tasks[record.run_id]
        current = engine.load_run(project.name, record.run_id)
        report.update(state=current.state.value, elapsed_seconds=time.monotonic()-started,
                      terminal_reason=current.terminal_reason, usage=current.usage,
                      progress=engine.p4_progress(current))
        write_json_atomic(Path(args.report), report)
        print(json.dumps({key: report[key] for key in ("state", "elapsed_seconds", "terminal_reason", "usage")}), flush=True)
    finally:
        await engine.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["p4.preliminary", "p4.comprehensive"], default="p4.preliminary")
    parser.add_argument("--ambiguous", action="store_true")
    parser.add_argument("--budget", type=float, default=60)
    parser.add_argument("--wall-limit", type=float, default=600)
    parser.add_argument("--provider-root", default=str(Path.home() / ".model-forge-codex"))
    parser.add_argument("--data-root")
    parser.add_argument("--resume-run", help="Continue an inspected, paused acceptance run without reseeding its inputs")
    parser.add_argument("--continue-answer", help="Explicit direction for the pending acceptance-run question")
    parser.add_argument("--report", required=True)
    asyncio.run(main(parser.parse_args()))
