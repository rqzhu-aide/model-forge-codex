"""Run real P1 through P5 recovery acceptance in a fresh, isolated data root.

No research outputs are seeded. Model work uses the existing OpenAI account,
gpt-6-astra at high reasoning, and the native SDK bridge. Stop for method
selection, unresolved researcher decisions, failed runs, or phase timeouts.
Resume skips published work and never answers a question or retries a failure.

Example: python scripts/validate_recovery_live.py --data-root <isolated-root>
Then inspect P2 and resume with --resume --method-id <published-stable-id>.
Use --dry-run to inspect the fixed scientific scope without writing or calling a model.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from model_forge_codex.accounts import AccountService
from model_forge_codex.bridge import SdkCodexBridge
from model_forge_codex.catalog import Catalog
from model_forge_codex.cumulative_attention import attention_applies_to_branch, open_attention_items
from model_forge_codex.domain import MemberConfig, MemberRole, RunState
from model_forge_codex.instance_lock import writable_instance
from model_forge_codex.members import codex_home, provision_team
from model_forge_codex.methods import activate_method, get_method, list_methods
from model_forge_codex.p4_execution import shared_python_executable
from model_forge_codex.project_brief import normalize_project
from model_forge_codex.providers import load_provider_config, write_provider_config
from model_forge_codex.runs import RunEngine
from model_forge_codex.storage import read_json, sha256_bytes, write_json_atomic

PROJECT_ID = "project.recovery_quantile_rl"
MODEL = "gpt-6-astra"
EFFORT = "high"
MARKER = "recovery-live-acceptance-v1"


def scientific_scope():
    """Fixed researcher inputs, not estimates or synthetic research findings."""
    gamma = 0.9
    horizon = 100
    return {
        "states": [0, 1], "actions": [0, 1], "initial_distribution": [1.0, 0.0],
        "reward_discount": gamma, "cost_discount": gamma,
        "quantile_level": 0.9, "cost_quantile_threshold": 3.0,
        "quantile_definition": "Q_alpha(X) = inf{x in R: P(X <= x) >= alpha}",
        "policy_class": "Stationary randomized Markov policies pi(a=1|s)=p_s, (p_0,p_1) in [0,1]^2; actions are sampled anew conditional on each current state.",
        "transitions": [
            {"state": 0, "action": 0, "next_state_probabilities": [1.0, 0.0], "reward": 0.5, "cost": 0.05},
            {"state": 0, "action": 1, "next_state_probabilities": [0.8, 0.2], "reward": 1.0, "cost": 0.2},
            {"state": 1, "action": 0, "next_state_probabilities": [0.9, 0.1], "reward": 0.2, "cost": 0.1},
            {"state": 1, "action": 1, "next_state_probabilities": [0.3, 0.7], "reward": 1.5, "cost": 1.0},
        ],
        "reward_and_cost_timing": "r(S_t,A_t) and c(S_t,A_t) accrue before drawing S_(t+1); summation starts at t=0.",
        "numerical_horizon": horizon, "reward_bound": [0.0, 1.5], "cost_bound": [0.0, 1.0],
        "reward_tail_upper_bound": 1.5 * gamma ** horizon / (1 - gamma),
        "cost_tail_upper_bound": gamma ** horizon / (1 - gamma),
        "reference_policy_grid": [0.0, 0.25, 0.5, 0.75, 1.0],
        "pilot_seed": 101, "evaluation_seed_blocks": [1101, 1102, 1103, 1104, 1105],
        "trajectories_per_policy_per_seed_block": 2000,
        "scope_limit": "One known finite MDP. A 25-policy reference grid is a finite comparison, not a certificate of the continuum optimum or arbitrary history-dependent optimality.",
    }


def project_instructions(problem):
    return (
        "This is a small end-to-end research-workflow acceptance study with real literature work, mathematical reasoning and executed numerical evidence. "
        "The exact infinite-horizon objective is\n\n"
        r"$$\max_{\pi\in\Pi_{\mathrm{stat}}} J(\pi)=\mathbb{E}_{S_0\sim\mu_0,\pi,P}\!\left[\sum_{t=0}^{\infty}\gamma_R^t r(S_t,A_t)\right]"
        "\n" + r"\quad\text{subject to}\quad Q_{\alpha}\!\left(\sum_{t=0}^{\infty}\gamma_C^t c(S_t,A_t)\right)\le b.$$") + (
        "\n\nThe quantile is over the distribution of the entire cumulative discounted trajectory cost, including policy randomization. "
        "Do not replace it with a per-step quantile, expected cost, CVaR, or a quantile of reward. "
        "The stationary randomized policy restriction is an explicit acceptance-study scope, not a general optimality claim. "
        "Rewards and costs are deterministic functions of the current state and action; the transition kernel is known. "
        "Freeze these choices in all later definitions and reports:\n\n```json\n"
        + json.dumps(problem, ensure_ascii=False, indent=2) + "\n```\n\n"
        "Computation may sum t=0,...,H-1 at H=100, while the scientific target stays infinite-horizon. "
        r"Use $0\le C_\infty-C_H\le\gamma_C^H/(1-\gamma_C)$ and "
        r"$0\le R_\infty-R_H\le1.5\gamma_R^H/(1-\gamma_R)$. "
        "Report these bounds and quantile/feasibility consequences explicitly. For a cost tail bound tau, "
        "P(C_H <= b-tau) >= alpha suffices for feasibility; P(C_H <= b) < alpha suffices for infeasibility. "
        "Finite-sample estimates require their own uncertainty bounds, accounting for policy selection or simultaneous comparisons. "
        "Near-threshold cases may remain unresolved. The 25-policy grid uses every pair of the five specified probabilities; "
        "it does not replace the continuous policy-class target. Compare to the always-safe and always-risky policies. "
        "Use concise, complete artifacts with retained proofs, code, tables and exact source references. "
        "Negative or unresolved results are acceptable. Never invent a citation, numerical result, theorem, or successful execution. "
        "Use only shared installed tools and standard-library Python for the small computations; install nothing. "
        "If the supplied definition is ambiguous or cannot be implemented faithfully, request researcher direction and stop affected work."
    )


def phase_steps():
    return [
        {"phase": "P1", "mode": "p1.literature_update", "instructions":
         "Develop a focused literature basis for the frozen infinite-horizon cumulative discounted-cost quantile constraint. "
         "Each discovery member should deeply check a small number of directly relevant primary sources, normally two, preserving exact definitions, assumptions, source locations and reading limits. "
         "Distinguish trajectory chance/quantile constraints from expected-cost and CVaR formulations. Include relevant recent work when verifiable. No invented or merely remembered citations."},
        {"phase": "P2", "mode": "p2.researcher_proposal", "instructions":
         "Develop the lead's one candidate around a transparent distribution/trajectory-based method for the exact stationary randomized policy problem. "
         "Aim for an implementable small method, with controlled discounted-cost truncation and explicit sampling or discretization uncertainty. "
         "The two specialists independently supply their one candidate each and perform the required cross-audits. "
         "Retain the original cumulative-cost quantile target and [0,1]^2 stationary policy scope. A finite grid is a declared numerical approximation, not a changed target. "
         "Make comparison and limitations explicit; leave actual method selection to the researcher."},
        {"phase": "P3", "mode": "p3.theory_establishment", "instructions":
         "Analyze the exact selected P2 definition on the frozen MDP. Establish only the relevant results: discounted-return well-definedness, "
         "the cumulative-cost distribution/quantile definition, the selected method's approximation and feasibility logic, and the nonnegative horizon tail bounds. "
         "Separate continuous-policy optimization from finite-grid checks, and statistical confidence from deterministic truncation. "
         "Provide actual arguments or explicitly unresolved proof obligations. Do not silently redesign the selected method or assert novelty or global optimality without a proof."},
        {"phase": "P4", "mode": "p4.preliminary", "instructions":
         "Faithfully implement the selected method using standard-library Python and the host's managed execution tool. "
         "Save a prospective protocol before run_batch. Use a small implementation/reference pilot followed by one bounded evaluation work item; inspect the pilot before the evaluation. "
         "For the pilot use seed 101. In the evaluation use the 25-policy reference grid, H=100, five seed blocks 1101 through 1105, "
         "and 2000 independent trajectories per policy per block. Preserve the selected method's exact RNG seed and draw schedule and record it; "
         "if that schedule is unspecified, request researcher direction before executing rather than inventing a different protocol. "
         "For a selected method requiring training, keep training independent of these evaluation seeds. "
         "Evaluate discounted expected reward, lower 0.9 cost quantile, P(C_H<=3) and P(C_H<=3-tau), confidence/selection uncertainty, runtime and failures. "
         "Check expected rewards with the exact 2-by-2 discounted policy-evaluation linear system and compare always-safe and always-risky baselines. "
         "Preserve the infinite-horizon tail bounds and report unresolved feasibility honestly. A grid winner is not a continuum-optimality proof. "
         "Keep actual execution inside the stated runtime budget. If the exact method cannot fit this small design or requires an unspecified scientific choice, request_decision. "
         "Retain real code and result tables and a concise implementation account. Do not guess identifiers or rewrite the method. Print complete tool feedback and never resubmit an uncertain batch before inspecting saved state."},
        {"phase": "P5", "mode": "p5.assembly", "instructions":
         "Assemble a compact but complete conference-style manuscript from this run's exact P1 through P4 basis. "
         "State the infinite-horizon reward objective, cumulative discounted-cost lower quantile constraint, stationary policy scope, frozen MDP, "
         "H=100 approximation, rigorous tail control, and finite-sample limitations. Link every theoretical and empirical claim to actual retained evidence. "
         "The acceptance study does not establish general novelty or a globally optimal method. Preserve negative, partial and unresolved outcomes. "
         "Use the exact supplied generation IDs, source digests, evidence IDs, and canonical record locations."},
        {"phase": "P5", "mode": "p5.review_revision", "instructions":
         "Review and revise the frozen manuscript for fidelity to the infinite-horizon cumulative discounted-cost quantile formulation, "
         "the exact selected method, the stationary policy restriction, retained empirical evidence, tail and statistical uncertainty, and internal consistency. "
         "Verify source claims without fabricating missing support. The revision must address or explicitly retain each review concern and may report negative or unresolved findings. "
         "Preserve the exact scientific scope; do not add new experiments or silently change the risk measure."},
    ]


def save_report(root, manifest, **changes):
    if changes.get("status") == "running":
        for key in ("error", "stopped_at", "pending_decisions", "readiness_reasons", "method_options"):
            manifest.pop(key, None)
    manifest.update(changes, updated_at=datetime.now(timezone.utc).isoformat())
    manifest["usage"] = {name: sum(row.get("usage", {}).get(name, 0) for row in manifest["runs"].values())
                         for name in ("input_tokens", "output_tokens")}
    write_json_atomic(root / "recovery-acceptance.json", manifest)


def prepare(root, args):
    if args.resume:
        saved = read_json(root / "recovery-acceptance.json")
        if not saved or saved.get("runner") != MARKER:
            raise ValueError("Resume requires this runner's existing isolated acceptance root.")
        return saved
    if any(path.name != ".writer.lock" for path in root.iterdir()):
        raise ValueError("Use a fresh empty --data-root, or --resume for an existing acceptance project.")
    project = root / "projects" / PROJECT_ID
    project.mkdir(parents=True)
    problem = scientific_scope()
    instructions = project_instructions(problem)
    write_json_atomic(project / "project.json", normalize_project({
        "project_id": PROJECT_ID, "name": "Quantile-constrained discounted RL recovery acceptance",
        "research_instructions": instructions, "venue_length": "conference"}))
    shutil.copytree(REPO / "contracts", project / "contracts")
    provision_team(project, [MemberConfig(role=role, model=MODEL, reasoning_effort=EFFORT, provider="openai") for role in MemberRole])
    write_provider_config(root / "providers.toml", {"provider": {"type": "openai", "model": MODEL, "reasoning_effort": EFFORT}})
    manifest = {"runner": MARKER, "project_id": PROJECT_ID, "data_root": str(root), "model": MODEL,
                "reasoning_effort": EFFORT, "problem": problem, "steps": phase_steps(), "runs": {},
                "project_instructions_sha256": sha256_bytes(instructions.encode("utf-8")),
                "experiment_budget_seconds": args.budget_seconds,
                "catalog_pin": read_json(project / "contracts/catalog-pin.json")}
    save_report(root, manifest, status="prepared")
    return manifest


def summarize(engine, record):
    report = {"run_id": record.run_id, "phase": record.phase, "mode": record.mode,
              "branch_id": record.branch_id, "state": record.state.value, "usage": record.usage,
              "terminal_reason": record.terminal_reason, "stage_states": record.stage_states,
              "mechanical_repair_attempts": record.mechanical_repair_attempts,
              "correction_attempts": record.correction_attempts,
              "findings": record.findings_history[-1] if record.findings_history else [],
              "run_directory": str(engine.run_dir(record.project_id, record.run_id))}
    if record.phase == "P4":
        progress = engine.p4_progress(record) or {}
        report["evaluation"] = {"pause_request": progress.get("pause_request"), "budget": progress.get("budget"),
                                "batches": [{key: batch.get(key) for key in ("batch_id", "attempt_id", "status", "elapsed_seconds")}
                                            for batch in progress.get("ledger", [])]}
    return report


def unresolved_decisions(project, branch, method_id):
    resolved = read_json(project / "researcher/attention_resolutions.json") or {}
    return [item for item in open_attention_items(project, resolved)
            if item.get("kind") == "researcher_decision" and attention_applies_to_branch(item, branch, method_id)]


async def execute(args):
    root = args.data_root.expanduser().resolve()
    if args.dry_run:
        print(json.dumps({"data_root": str(root), "model": MODEL, "reasoning_effort": EFFORT,
                          "problem": scientific_scope(), "steps": phase_steps(),
                          "experiment_budget_seconds": args.budget_seconds,
                          "phase_timeout_seconds": args.phase_timeout, "model_calls": 0}, indent=2))
        return 0
    os.environ["MF_CODEX_PROVIDER_CONFIG"] = str(root / "providers.toml")
    with writable_instance(root):
        manifest = prepare(root, args)
        project = root / "projects" / manifest["project_id"]
        accounts = AccountService(root)
        engine = RunEngine(root, SdkCodexBridge(), account_service=accounts)
        try:
            if Catalog(project / "contracts").verify_manifest():
                raise ValueError("The acceptance project's frozen catalog failed its integrity check.")
            instructions = (read_json(project / "project.json") or {}).get("research_instructions", "")
            if sha256_bytes(instructions.encode("utf-8")) != manifest["project_instructions_sha256"]:
                raise ValueError("The frozen acceptance problem changed. Inspect it before authorizing a new project.")
            providers = load_provider_config(root)
            providers.require_ready()
            for role in MemberRole:
                config = read_json(project / "members" / role.value / "config.json") or {}
                actual = providers.effective_member(config, role.value, codex_home(project, role))
                if any(actual.get(key) != value for key, value in {"provider": "openai", "model": MODEL, "reasoning_effort": EFFORT}.items()):
                    raise ValueError("Acceptance requires every member to use OpenAI gpt-6-astra at high reasoning.")
            experiment_python = shared_python_executable()
            if not experiment_python.is_file() or any((parent / "pyvenv.cfg").is_file() or parent.name in {".venv", "venv", ".env"}
                                                      for parent in (experiment_python.parent, experiment_python.parent.parent)):
                raise ValueError("Set MF_P4_PYTHON to an existing user-wide or machine-wide Python installation before running acceptance.")
            engine.reconcile_on_boot()
            await accounts.connect()  # Reuse the existing login; only this isolated root is provisioned.
            save_report(root, manifest, shared_experiment_python=str(experiment_python), status="running")
            selected = manifest.get("selected_method")
            if args.method_id and selected and args.method_id != selected["method_id"]:
                raise ValueError("This acceptance run already selected a different method. Use a fresh root for a different branch.")
            for step in manifest["steps"]:
                phase, mode = step["phase"], step["mode"]
                if mode == "p5.review_revision" and not args.review_revision:
                    break
                if phase in {"P3", "P4", "P5"} and selected is None:
                    methods = list_methods(project)
                    if not args.method_id:
                        save_report(root, manifest, status="awaiting_method_selection",
                                    method_options=[{key: method.get(key) for key in ("method_id", "title", "identity", "status", "registered")}
                                                    for method in methods])
                        print(json.dumps({"status": manifest["status"], "method_options": manifest["method_options"]}), flush=True)
                        return 2
                    method = next((row for row in methods if row["method_id"] == args.method_id), None)
                    if method is None:
                        raise ValueError("--method-id must identify a method in the actual published P2 catalog.")
                    activated = activate_method(project, args.method_id, expected_identity=method["identity"])
                    selected = {key: activated[key] for key in ("method_id", "identity", "branch_id")}
                    save_report(root, manifest, selected_method=selected)
                branch = "trunk" if phase in {"P1", "P2"} else selected["branch_id"]
                if selected and phase in {"P3", "P4", "P5"}:
                    current = get_method(project, branch)
                    if not current or current.get("identity") != selected["identity"] or current.get("status") != "active":
                        raise ValueError("The selected method changed or is no longer active; inspect it before continuing.")
                candidates = [read_json(path) for path in (project / "runs").glob("*/run.json")]
                matches = [row for row in candidates if row and row.get("mode") == mode and row.get("branch_id") == branch
                           and row.get("intent", "run") == "run"]
                if len(matches) > 1:
                    raise ValueError(f"Multiple {mode} runs exist. Inspect them before choosing continuation.")
                record = engine.load_run(project.name, matches[0]["run_id"]) if matches else None
                if record:
                    manifest["runs"][mode] = summarize(engine, record)
                    save_report(root, manifest)
                    if record.state is RunState.PUBLISHED:
                        continue
                    save_report(root, manifest, status="needs_attention", stopped_at=mode)
                    print(json.dumps({"status": "needs_attention", "run": manifest["runs"][mode]}), flush=True)
                    return 2
                decisions = unresolved_decisions(project, branch, selected["method_id"] if selected else None)
                if decisions:
                    save_report(root, manifest, status="awaiting_researcher_decision", stopped_at=mode, pending_decisions=decisions)
                    print(json.dumps({"status": manifest["status"], "pending_decisions": decisions}), flush=True)
                    return 2
                reasons = engine.check_readiness(project.name, phase, branch, mode)
                if reasons:
                    save_report(root, manifest, status="readiness_blocked", stopped_at=mode, readiness_reasons=reasons)
                    return 2
                record = await engine.start_run(project.name, phase=phase, mode=mode, branch_id=branch,
                                                instructions=step["instructions"],
                                                budget_seconds=manifest["experiment_budget_seconds"] if phase == "P4" else None)
                started = time.monotonic()
                task = engine._tasks[record.run_id]
                while not task.done():
                    manifest["runs"][mode] = summarize(engine, engine.load_run(project.name, record.run_id))
                    save_report(root, manifest, status="running", current_mode=mode)
                    print(json.dumps({"mode": mode, "run_id": record.run_id,
                                      "state": manifest["runs"][mode]["state"],
                                      "elapsed_seconds": round(time.monotonic() - started)}), flush=True)
                    remaining = args.phase_timeout - (time.monotonic() - started)
                    if remaining <= 0:
                        await engine.cancel(project.name, record.run_id)
                        manifest["runs"][mode] = summarize(engine, engine.load_run(project.name, record.run_id))
                        save_report(root, manifest, status="phase_timeout", stopped_at=mode)
                        return 2
                    await asyncio.wait({task}, timeout=min(15, remaining))
                await task
                record = engine.load_run(project.name, record.run_id)
                manifest["runs"][mode] = {**summarize(engine, record), "wall_seconds": time.monotonic() - started}
                save_report(root, manifest)
                if record.state is not RunState.PUBLISHED:
                    save_report(root, manifest, status="needs_attention", stopped_at=mode)
                    return 2
            decisions = unresolved_decisions(project, selected["branch_id"], selected["method_id"]) if selected else []
            save_report(root, manifest, status="awaiting_researcher_decision" if decisions else "completed",
                        pending_decisions=decisions, review_revision_included=args.review_revision)
            return 2 if decisions else 0
        except asyncio.CancelledError:
            save_report(root, manifest, status="interrupted")
            raise
        except Exception as exc:
            save_report(root, manifest, status="runner_error", error=str(exc))
            raise
        finally:
            try:
                await engine.shutdown()
                for mode, row in list(manifest["runs"].items()):
                    manifest["runs"][mode] = {**row, **summarize(engine, engine.load_run(project.name, row["run_id"]))}
                save_report(root, manifest)
            finally:
                await accounts.close()
            print(json.dumps({"status": manifest["status"], "report": str(root / "recovery-acceptance.json"),
                              "usage": manifest["usage"]}), flush=True)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True, help="Fresh isolated root, or an existing acceptance root with --resume")
    parser.add_argument("--resume", action="store_true", help="Skip published phases; stop on every unresolved or failed run")
    parser.add_argument("--method-id", help="Researcher-selected stable ID from the actual published P2 catalog")
    parser.add_argument("--phase-timeout", type=float, default=1800, help="Maximum wall seconds per phase run; expiry cancels owned work")
    parser.add_argument("--budget-seconds", type=float, default=120, help="Managed P4 computation budget, frozen when the project is created")
    parser.add_argument("--review-revision", action=argparse.BooleanOptionalAction, default=True,
                        help="Run P5 review_revision after assembly (default); a later resume can add it without repeating assembly")
    parser.add_argument("--dry-run", action="store_true", help="Print the scientific scope and route; write nothing and make no model/account calls")
    args = parser.parse_args()
    if any(not math.isfinite(value) or value <= 0 for value in (args.phase_timeout, args.budget_seconds)):
        parser.error("Timeout and computation budget must be finite positive seconds.")
    return args


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(execute(parse_args())))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
