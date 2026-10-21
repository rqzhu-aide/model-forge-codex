"""Local acceptance server driven by real Codex collaboration agents.

The application still creates every brief, validates and seals every output,
executes P4 batches, and publishes records. Only the model transport is replaced
by a queue consumed by an operator's Codex subagents. This does not test SDK
authentication, token accounting, or operating-system isolation of model turns.
No research outputs are seeded or synthesized by this adapter.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import inspect
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from fastapi import HTTPException, Request
from model_forge_codex.bridge import TurnOutcome
from model_forge_codex.execution import public_execution
from model_forge_codex.member_tools import member_tools_marker
from model_forge_codex.service import create_app
from model_forge_codex.storage import write_json_atomic


def now():
    return datetime.now(timezone.utc).isoformat()


class SubagentBridge:
    simulated_bridge = False

    def __init__(self, root):
        self.root = Path(root) / "acceptance-transport"
        self.root.mkdir(parents=True, exist_ok=True)
        self.threads = {}
        self.active = {}

    def _configure(self, thread_id, execution):
        execution = execution or {}
        self.threads[thread_id]["configuration"] = {
            "submitted": public_execution(execution),
            "effective": {key: execution.get(key) for key in ("model", "reasoning_effort", "provider_id")},
            "confirmation": "operator_dispatched_collaboration_agent",
            "instructions_delivery": "frozen_brief_and_member_instructions",
            "member_tools": member_tools_marker(execution),
            "transport": "codex_collaboration_acceptance",
            "token_usage": "not_reported_by_transport",
        }

    def execution_configuration(self, thread_id):
        return self.threads.get(thread_id, {}).get("configuration", {})

    async def ensure_thread(self, key, *, member_home, model, reasoning_effort, execution=None, workspace_root=None):
        thread_id = "acceptance-thread." + uuid4().hex
        self.threads[thread_id] = {"key": key.as_string(), "member_home": str(member_home)}
        self._configure(thread_id, execution)
        return thread_id

    async def resume_thread(self, thread_id, *, member_home=None, execution=None, workspace_root=None):
        if thread_id not in self.threads:
            return False
        self._configure(thread_id, execution)
        return True

    def _save(self, turn):
        write_json_atomic(self.root / turn["public"]["turn_id"] / "turn.json", turn["public"])

    async def run_turn(self, thread_id, *, brief_path, workspace, heartbeat, execution=None,
                       validate_artifacts=None, p4_checkpoint=None, tool_feedback=None):
        self._configure(thread_id, execution)
        turn_id = "turn." + uuid4().hex
        directory = self.root / turn_id
        directory.mkdir(parents=True)
        (directory / "member-instructions.md").write_text((execution or {}).get("instructions", ""), encoding="utf-8")
        public = {"turn_id": turn_id, "thread_id": thread_id,
                  "member_key": self.threads[thread_id]["key"], "state": "pending", "created_at": now(),
                  "brief_path": str(brief_path), "workspace": str(workspace),
                  "instructions_path": str(directory / "member-instructions.md"),
                  "model": (execution or {}).get("model"), "reasoning_effort": (execution or {}).get("reasoning_effort"),
                  "tools": [name for name, callback in (("validate_artifacts", validate_artifacts), ("p4_checkpoint", p4_checkpoint)) if callback]}
        turn = {"public": public, "done": asyncio.get_running_loop().create_future(), "heartbeat": heartbeat,
                "callbacks": {"validate_artifacts": validate_artifacts, "p4_checkpoint": p4_checkpoint},
                "tool_feedback": tool_feedback}
        self.active[turn_id] = turn
        self._save(turn)
        heartbeat("Waiting for the assigned research team member.")
        try:
            outcome = await turn["done"]
            public.update(state="completed" if outcome.succeeded else "failed", finished_at=now())
            self._save(turn)
            return outcome
        finally:
            self.active.pop(turn_id, None)

    async def interrupt(self, thread_id):
        for turn in list(self.active.values()):
            if turn["public"]["thread_id"] == thread_id and not turn["done"].done():
                turn["public"].update(state="interrupted", finished_at=now())
                self._save(turn)
                turn["done"].set_result(TurnOutcome(False, diagnostic="Acceptance turn interrupted", interrupted=True))

    async def close(self):
        for thread_id in list(self.threads):
            await self.interrupt(thread_id)


def acceptance_app(root):
    bridge = SubagentBridge(root)
    app = create_app(Path(root), bridge=bridge)

    def active(turn_id):
        turn = bridge.active.get(turn_id)
        if not turn or turn["done"].done():
            raise HTTPException(409, "This member turn is no longer active.")
        return turn

    @app.get("/acceptance/turns")
    async def pending():
        return {"turns": [turn["public"] for turn in bridge.active.values()]}

    @app.post("/acceptance/turns/{turn_id}/{action}")
    async def dispatch(turn_id: str, action: str, request: Request):
        turn = active(turn_id)
        body = await request.json()
        if action == "claim":
            if turn["public"]["state"] != "pending":
                raise HTTPException(409, "This turn was already assigned.")
            turn["public"].update(state="working", agent=body["agent"], dispatched_at=now())
            turn["heartbeat"]("Research team member is working.")
            bridge._save(turn)
            return {"accepted": True}
        if action == "heartbeat":
            turn["heartbeat"](str(body.get("message", "Research team member is working.")))
            return {"accepted": True}
        if action == "finish":
            turn["public"]["completion_note"] = str(body.get("diagnostic", ""))
            bridge._save(turn)
            turn["done"].set_result(TurnOutcome(bool(body.get("succeeded")), diagnostic=str(body.get("diagnostic", "")),
                                               execution=bridge.execution_configuration(turn["public"]["thread_id"])))
            return {"accepted": True}
        callback = turn["callbacks"].get(action)
        if callback is None:
            raise HTTPException(404, "Tool is not available in this member turn.")
        try:
            value = callback() if action == "validate_artifacts" else callback(body)
            if inspect.isawaitable(value):
                value = await value
        except Exception as exc:
            value = {"error": str(exc)}
        if turn.get("tool_feedback"):
            recovery = turn["tool_feedback"](action, body, value)
            if recovery:
                value = {**value, "recovery": recovery}
        with (bridge.root / turn_id / "tool-calls.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"at": now(), "tool": action, "arguments": body, "result": value}, ensure_ascii=False) + "\n")
        return value

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8778)
    args = parser.parse_args()
    # Isolate this acceptance project from the user's saved provider file.
    os.environ["MF_CODEX_PROVIDER_CONFIG"] = str(args.data_root.resolve() / "providers.toml")
    import uvicorn
    uvicorn.run(acceptance_app(args.data_root.resolve()), host="127.0.0.1", port=args.port)
