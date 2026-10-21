"""Small native recovery comparison, one isolated case per process.

Use the same catalog, case, and fixture against two --source-root directories.
The default prepares and validates fixtures without connecting or calling a model.
--live authorizes the single case's native turns; --resume uses a prepared root.
This exercises local recovery, not a scientific phase or publication.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


REPO = Path(__file__).resolve().parents[1]
MODEL, EFFORT = "gpt-6-astra", "high"
PID, RUN_ID = "project.recovery_comparison", "run.recovery_comparison"
MARKER = "native-recovery-comparison-v1"
INSTRUCTIONS = (
    "This is a mechanical recovery acceptance fixture, not a research project. "
    "The existing empty literature collections intentionally claim no source reading. "
    "Repair only the missing title in lead_literature.json, using the exact title "
    "'Recovery acceptance fixture'. Preserve every other value and all other files. "
    "Do not search the web, invent literature, synthesize a research basis, or publish. "
    "Use the available artifact validator to check the saved correction, then finish."
)
TOOL_PROMPT = """This is a local tool recovery acceptance test, not a scientific evaluation.
The host already saved protocol.json. It declares one work item and a small budget.
compute.py only computes an arithmetic checksum and records its actual invocation.
Do not edit or directly run either file. Do not use web research or unrelated tools.

First call p4_checkpoint with exactly this deliberately invalid request:
{"operation":"run_batch","batch_id":"batch.recovery","script_path":"compute.py","timeout_seconds":20,"result_paths":["arithmetic.json","dispatch-count.txt"]}
This negative control intentionally omits one required field. Do not fix it before
the first call. Print the entire returned value and inspect the rejection.
Then use that feedback and the saved protocol.json to correct the request once.
After the corrected call is accepted, end the turn immediately. The host executes
the queued script. Never submit the same accepted batch again. If the outcome is
uncertain, stop and report it instead of retrying.
"""
SCRIPT = """import json
from pathlib import Path
counter = Path('dispatch-count.txt')
count = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(count), encoding='utf-8')
Path('arithmetic.json').write_text(json.dumps({'sum_0_through_9': sum(range(10)), 'invocation': count}), encoding='utf-8')
"""
REJECTED_REQUEST = {"operation": "run_batch", "batch_id": "batch.recovery", "script_path": "compute.py",
                    "timeout_seconds": 20, "result_paths": ["arithmetic.json", "dispatch-count.txt"]}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def encoded(document):
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def fixture(case):
    if case == "repair":
        documents = {}
        for name in ("lead", "theory", "empirical"):
            value = {"schema_version": "1.1.0", "title": "Recovery acceptance fixture",
                     "search_scope": "Empty structural fixture. No literature search was performed.",
                     "coverage_limits": ["No research findings or source reading are claimed."], "papers": []}
            if name == "lead":
                value.pop("title")
            documents[name + "_literature.json"] = encoded(value).decode()
        return {"instructions": INSTRUCTIONS, "documents": documents,
                "basis": "Fresh P1 basis from RunEngine.compute_basis, including its frozen empty literature library."}
    return {"prompt": TOOL_PROMPT, "script": SCRIPT, "rejected_request": REJECTED_REQUEST, "protocol": {
        "plan_revision_id": "plan.recovery", "budget_seconds": 30,
        "work_items": [{"work_item_id": "work.arithmetic", "depends_on": []}], "amendments": []}}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded(value))
    temporary.replace(path)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--source-root", type=Path, default=REPO / "src",
                        help="Directory containing model_forge_codex; use a separate process for each version.")
    parser.add_argument("--catalog", type=Path, default=REPO / "contracts")
    parser.add_argument("--label", required=True)
    parser.add_argument("--case", required=True, choices=("repair", "rejection"))
    parser.add_argument("--live", action="store_true", help="Run this prepared native case, consuming model usage.")
    parser.add_argument("--resume", action="store_true", help="Run an unchanged prepared fixture, never rerun a live case.")
    parser.add_argument("--timeout", type=float, default=360, help="Case timeout in seconds; cancellation interrupts its native turn.")
    return parser.parse_args()


async def execute(args):
    source = args.source_root.expanduser().resolve()
    if not (source / "model_forge_codex/runs.py").is_file():
        raise ValueError("--source-root must contain model_forge_codex/runs.py")
    sys.path.insert(0, str(source))
    from model_forge_codex.accounts import AccountService, find_codex
    from model_forge_codex.bridge import SdkCodexBridge
    from model_forge_codex.catalog import Catalog
    from model_forge_codex.domain import MemberConfig, MemberRole, RunRecord, RunState
    from model_forge_codex.execution import capture_execution
    from model_forge_codex.members import codex_home, provision_team
    from model_forge_codex.p4_execution import P4Controller
    from model_forge_codex.providers import write_provider_config
    from model_forge_codex.runs import RunEngine
    from model_forge_codex.storage import sha256_file
    import model_forge_codex.math_validation as math_validation
    import openai_codex

    # Both versions must use the same installed CLI. The archived bridge predates
    # its explicit codex_bin argument; no recovery logic is patched here.
    cli = find_codex()
    if not cli:
        raise ValueError("An existing shared Codex CLI is required.")
    original_config = openai_codex.CodexConfig
    def shared_cli_config(*positional, **keywords):
        keywords["codex_bin"] = cli
        return original_config(*positional, **keywords)
    openai_codex.CodexConfig = shared_cli_config
    # The archived source snapshot has no generated web math runtime. Resolve
    # its unchanged validator's asset lookup against the current shared build.
    math_validation.__file__ = str(REPO / "src/model_forge_codex/math_validation.py")

    root = args.data_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / "comparison.json"
    frozen = fixture(args.case)
    identity = {"marker": MARKER, "case": args.case, "label": args.label, "source_root": str(source),
                "fixture_sha256": digest(encoded(frozen)), "model": MODEL, "reasoning_effort": EFFORT}
    if args.resume:
        report = load(report_path)
        if any(report.get(key) != value for key, value in identity.items()) or report.get("status") != "prepared":
            raise ValueError("Resume requires an unchanged prepared fixture that has never run live.")
    else:
        if any(root.iterdir()):
            raise ValueError("Use a fresh empty --data-root, or --resume for a prepared fixture.")
        report = {**identity, "scope": "Structural acceptance fixture; no research results or publication.",
                  "compatibility": ["Same installed CLI supplied through CodexConfig for both versions.",
                                    "Same shared generated math runtime; validator logic unchanged."],
                  "turns": [], "tool_receipts": [], "status": "preparing"}
        save(root / "fixture.json", frozen)
        project = root / "projects" / PID
        project.mkdir(parents=True)
        save(project / "project.json", {"project_id": PID, "name": "Local recovery acceptance fixture",
                                        "research_instructions": INSTRUCTIONS})
        shutil.copytree(args.catalog.resolve(), project / "contracts")
        provision_team(project, [MemberConfig(role=role, model=MODEL, reasoning_effort=EFFORT, provider="openai")
                                 for role in MemberRole])
        write_provider_config(root / "providers.toml", {"provider": {"type": "openai", "model": MODEL, "reasoning_effort": EFFORT}})
    os.environ["MF_CODEX_PROVIDER_CONFIG"] = str(root / "providers.toml")
    if load(root / "fixture.json") != frozen:
        raise ValueError("The saved comparison fixture changed.")
    project = root / "projects" / PID
    catalog = Catalog(project / "contracts")
    if catalog.verify_manifest():
        raise ValueError("Frozen catalog integrity check failed.")
    report.update(catalog_sha256=catalog.snapshot_sha256,
                  cli={"path": cli, "sha256": sha256_file(Path(cli)),
                       "version": subprocess.check_output([cli, "--version"], text=True).strip()},
                  source_sha256={name: sha256_file(source / "model_forge_codex" / name)
                                 for name in ("runs.py", "bridge.py", "member_tools.py", "p4_execution.py")})

    class ObservedBridge(SdkCodexBridge):
        async def run_turn(self, thread_id, **kwargs):
            prompt = kwargs["brief_path"].read_bytes()
            effective = self.execution_configuration(thread_id).get("effective") or {}
            if effective.get("model") != MODEL or effective.get("reasoning_effort") != EFFORT:
                raise ValueError("The native thread did not acknowledge the requested Astra high configuration.")
            row = {"prompt_bytes": len(prompt), "prompt_sha256": digest(prompt), "thread_id": thread_id,
                   "effective": effective, "elapsed_seconds": None}
            report["turns"].append(row)
            save(report_path, report)
            started = time.monotonic()
            try:
                result = await super().run_turn(thread_id, **kwargs)
                row.update(succeeded=result.succeeded, diagnostic=result.diagnostic, usage=result.usage)
                return result
            finally:
                row["elapsed_seconds"] = time.monotonic() - started
                save(report_path, report)

        async def _collect_tapped(self, handle, heartbeat, **kwargs):
            class ObservedHandle:
                def __getattr__(self, name):
                    return getattr(handle, name)
                async def stream(self):
                    async for event in handle.stream():
                        if getattr(event, "method", "") == "item/completed":
                            payload = getattr(event, "payload", None)
                            item = getattr(payload, "item", None)
                            item = getattr(item, "root", item)
                            if getattr(item, "tool", "") in {"validate_artifacts", "p4_checkpoint"}:
                                for content in getattr(item, "content_items", None) or []:
                                    content = getattr(content, "root", content)
                                    try:
                                        value = json.loads(getattr(content, "text", ""))
                                    except (TypeError, ValueError):
                                        continue
                                    report["tool_receipts"].append({"tool": item.tool, "arguments": item.arguments, "response": value})
                                    save(report_path, report)
                        yield event
            return await super()._collect_tapped(ObservedHandle(), heartbeat, **kwargs)

    accounts = AccountService(root, executable=cli)
    bridge = ObservedBridge()
    engine = RunEngine(root, bridge, account_service=accounts)
    try:
        if args.case == "repair":
            record = RunRecord(RUN_ID, PID, "P1", "p1.literature_update", "trunk", state=RunState.RUNNING,
                               instructions=INSTRUCTIONS)
            directory = engine.run_dir(PID, RUN_ID)
            stages = engine.stage_plan(PID, "P1", "p1.literature_update")
            stage = stages[0]
            if not args.resume:
                record.stage_states = {item.stage_id: "running" if item is stage else "pending" for item in stages}
                engine._save_run(record)
                shutil.copytree(project / "contracts", directory / "contracts")
                save(directory / "basis.json", engine.compute_basis(PID, "P1", "trunk", "p1.literature_update"))
                save(directory / "stage-plan.json", [asdict(item) for item in stages])
                for role, name in zip(stage.roles, ("lead", "theory", "empirical")):
                    workspace = engine.member_workspace(record, stage.stage_id, role)
                    workspace.mkdir(parents=True)
                    filename = name + "_literature.json"
                    (workspace / filename).write_text(frozen["documents"][filename], encoding="utf-8")
                    target = directory / "outputs" / stage.stage_id / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((workspace / filename).read_bytes())
                    brief = directory / "briefs" / (stage.stage_id + "." + role.value + ".md")
                    brief.parent.mkdir(parents=True, exist_ok=True)
                    brief.write_text(engine._render_brief(record, stage, role, workspace), encoding="utf-8")
            record = engine.load_run(PID, RUN_ID)
            initial = [asdict(value) for value in engine._validate_run_outputs(record, [stage])]
            if len(initial) != 1 or initial[0]["object_id"] != "p1.lead_literature" or "title" not in initial[0]["message"]:
                raise ValueError("Repair fixture must have exactly the missing-title finding: " + json.dumps(initial))
            output = directory / "outputs" / stage.stage_id
            for name, value in frozen["documents"].items():
                if (output / name).read_text(encoding="utf-8") != value:
                    raise ValueError("The prepared repair input changed: " + name)
            siblings = {name: sha256_file(output / name) for name in ("theory_literature.json", "empirical_literature.json")}
            expected = {**json.loads(frozen["documents"]["lead_literature.json"]), "title": "Recovery acceptance fixture"}
            # Exercise all checks with a separate fully corrected candidate
            # before paid work. A shape failure can otherwise mask missing basis.
            golden = root / "offline-corrected-candidate"
            golden.mkdir(exist_ok=True)
            for name, value in frozen["documents"].items():
                (golden / name).write_text(value, encoding="utf-8")
            save(golden / "lead_literature.json", expected)
            corrected_findings = [asdict(value) for value in engine._validate_run_outputs(record, [stage],
                                  output_dirs={stage.stage_id: golden})]
            if corrected_findings:
                raise ValueError("The fully corrected fixture must pass before live work: " + json.dumps(corrected_findings))
            report.update(initial_findings=initial, sibling_sha256_before=siblings,
                          offline_corrected_findings=corrected_findings,
                          frozen_basis_sha256=sha256_file(directory / "basis.json"))
            async def run_case():
                ok, diagnostic = await engine._check_stage_delivery(record, stage)
                final_record = engine.load_run(PID, RUN_ID)
                final = [asdict(value) for value in engine._validate_run_outputs(final_record, [stage])]
                after = {name: sha256_file(output / name) for name in siblings}
                exact_correction = load(output / "lead_literature.json") == expected
                report.update(outcome="passed" if ok and not final and after == siblings and exact_correction else "failed",
                              diagnostic=diagnostic, final_findings=final, sibling_sha256_after=after,
                              exact_correction=exact_correction,
                              siblings_unchanged=after == siblings, repair_attempts=final_record.mechanical_repair_attempts,
                              usage=final_record.usage, duplicate_dispatches=0, experiment_dispatches=0)
        else:
            workspace, directory = root / "tool-workspace", root / "tool-controller"
            if not args.resume:
                workspace.mkdir()
                save(workspace / "protocol.json", frozen["protocol"])
                (workspace / "compute.py").write_text(frozen["script"], encoding="utf-8")
                (workspace / "brief.md").write_text(frozen["prompt"], encoding="utf-8")
            if (load(workspace / "protocol.json") != frozen["protocol"]
                    or (workspace / "compute.py").read_text(encoding="utf-8") != frozen["script"]
                    or (workspace / "brief.md").read_text(encoding="utf-8") != frozen["prompt"]):
                raise ValueError("The prepared tool input changed.")
            controller = P4Controller(directory, workspace, stage_id="p4.analyst", member="data_analyst", budget_seconds=30)
            if not args.resume:
                controller.request({"operation": "save_plan", "protocol_path": "protocol.json"})
            initial_state = controller.snapshot()
            if initial_state.get("pending_batch") or initial_state["ledger"]:
                raise ValueError("Tool fixture already contains an experiment attempt.")
            if not args.resume:
                offline = P4Controller(root / "offline-controller", workspace, stage_id="p4.analyst",
                                       member="data_analyst", budget_seconds=30)
                offline.request({"operation": "save_plan", "protocol_path": "protocol.json"})
                original = offline.snapshot()
                try:
                    offline.request(frozen["rejected_request"])
                except ValueError as exc:
                    report["offline_rejection"] = {"type": type(exc).__name__, "message": str(exc)}
                else:
                    raise ValueError("The negative-control request unexpectedly passed offline.")
                if offline.snapshot() != original:
                    raise ValueError("The rejected offline request changed controller state.")
                corrected = {**frozen["rejected_request"], "work_item_id": "work.arithmetic"}
                response = offline.request(corrected)
                if not response.get("accepted") or not offline.snapshot().get("pending_batch") or offline.snapshot()["ledger"]:
                    raise ValueError("The corrected request must queue exactly one batch without execution offline.")
                report["offline_corrected_request"] = "accepted and queued; not executed"
            report["controller_calls"] = []
            def checkpoint(call):
                before = controller.snapshot()
                entry = {"arguments": call}
                report["controller_calls"].append(entry)
                try:
                    response = controller.request(call)
                    entry["response"] = response
                    return response
                except Exception as exc:
                    entry["exception_type"] = type(exc).__name__
                    raise
                finally:
                    after = controller.snapshot()
                    entry["state_unchanged"] = before == after
                    entry["pending"] = bool(after.get("pending_batch"))
                    entry["ledger_count"] = len(after["ledger"])
            async def run_case():
                member_home = codex_home(project, MemberRole.DATA_ANALYST)
                config = load(project / "members/data_analyst/config.json")
                execution = capture_execution(config, member_home)
                execution["p4_managed_execution"] = True
                thread_id = await bridge.ensure_thread("comparison.tool", member_home=member_home, model=MODEL,
                    reasoning_effort=EFFORT, execution=execution, workspace_root=workspace)
                outcome = await bridge.run_turn(thread_id, brief_path=workspace / "brief.md", workspace=workspace,
                    heartbeat=lambda message: None, execution=execution, p4_checkpoint=checkpoint)
                state = controller.snapshot()
                result = None
                if state.get("pending_batch"):
                    result = await controller.execute_pending()
                state = controller.snapshot()
                count_path = workspace / "dispatch-count.txt"
                count = int(count_path.read_text()) if count_path.is_file() else 0
                rejected = [call for call in report["controller_calls"] if call.get("exception_type")]
                accepted = [call for call in report["controller_calls"] if call.get("response", {}).get("accepted")]
                passed = (outcome.succeeded and len(rejected) == 1 and rejected[0]["state_unchanged"]
                          and len(accepted) == 1 and len(state["ledger"]) == 1 and count == 1
                          and result and result["status"] == "completed"
                          and load(workspace / "protocol.json") == frozen["protocol"]
                          and (workspace / "compute.py").read_text(encoding="utf-8") == frozen["script"]
                          and load(workspace / "arithmetic.json") == {"sum_0_through_9": 45, "invocation": 1})
                report.update(outcome="passed" if passed else "failed", usage=outcome.usage,
                    experiment_dispatches=count, duplicate_dispatches=max(0, count - 1),
                    ledger=[{key: item.get(key) for key in ("batch_id", "attempt_id", "status", "elapsed_seconds", "diagnostic")}
                            for item in state["ledger"]])
        report["status"] = "prepared"
        save(report_path, report)
        if args.live:
            await accounts.connect()
            report["status"] = "running"
            save(report_path, report)
            started = time.monotonic()
            try:
                async with asyncio.timeout(args.timeout):
                    await run_case()
                report["status"] = "completed"
            except TimeoutError:
                report.update(status="timed_out", outcome="incomplete")
            except Exception as exc:
                report.update(status="error", outcome="incomplete", error_type=type(exc).__name__, error=str(exc))
            finally:
                report["elapsed_seconds"] = time.monotonic() - started
                report["member_turns"] = len(report["turns"])
                save(report_path, report)
        print(json.dumps({key: report.get(key) for key in ("label", "case", "status", "outcome", "member_turns", "usage", "elapsed_seconds")}, indent=2))
        print("Evidence: " + str(report_path))
        return 0 if report["status"] == "prepared" or report.get("outcome") == "passed" else 1
    finally:
        await engine.shutdown()


def main():
    return asyncio.run(execute(arguments()))


if __name__ == "__main__":
    raise SystemExit(main())
