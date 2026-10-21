import React, { useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "../../src/styles.css";
import { api } from "../../src/api";
import ResearchProgress from "../../src/components/ResearchProgress";
import { EmpiricalProgressCard, EmpiricalExecutionHistory, EmpiricalPause, EmpiricalSavedDecisions } from "../../src/components/EmpiricalProgress";
import { ActionButton } from "../../src/components/Visuals";

const request = { request_id: "decision.preview", revision: 1, question: "Continue the cost comparison or finish with the available evidence?", reason: "The retained pilot covers one regime. The remaining comparison needs your direction.", options: [{ label: "Continue the comparison", consequence: "Use the remaining experiment budget and the frozen method." }, { label: "Finish with available evidence", consequence: "Review the pilot and state the comparison's limitations." }], evidence_refs: [] };
const progress = { plan: { work_items: [{ work_item_id: "cost", title: "Compare discounted cost" }] }, budget: { used_seconds: 12, remaining_seconds: 48 }, ledger: [], pause_request: request, saved_answers: [] };
const feedback = { accepted: false, operation: "run_batch", code: "invalid_arguments", json_pointer: "/timeout_seconds", error: "timeout_seconds is required", hint: "Provide a positive timeout_seconds for the declared work item and submit the corrected request once.", execution_state: "not_accepted" };
const previousFeedback = { operation: "run_batch", code: "execution_outcome_unknown", json_pointer: "", execution_state: "unknown", error: "Response failed after saving C:/saved/previous-request.json.", hint: "Inspect the saved request and attempt ledger before retrying." };
const previousRequest = { ...request, request_id: "decision.previous", question: "Check the saved experiment state before continuing.", reason: previousFeedback.error, evidence_refs: [{ description: "The original tool result needs inspection.", attempt_id: "attempt.previous", control_feedback: previousFeedback }] };
const runs = {
  correcting: { run_id: "preview.correcting", state: "running", phase: "P5", progress: { stages: [{ stage_id: "p5.revision", label: "Manuscript revision", state: "correcting", repair: { attempt: 1, state: "working", message: "Correcting an artifact reference, attempt 1 of 2." } }] } },
  stopped: { run_id: "preview.stopped", state: "failed", phase: "P5", progress: { stages: [{ stage_id: "p5.revision", label: "Manuscript revision", state: "failed", repair: { attempt: 1, state: "stopped", message: "Automatic repair stopped because the same issue remained. Review the findings before requesting correction." } }] } },
  interrupted: { run_id: "preview.interrupted", state: "awaiting_user", phase: "P4", p4_progress: { ...progress, pause_request: { ...request, evidence_refs: [{ attempt_id: "attempt.interrupted" }] }, ledger: [{ attempt_id: "attempt.interrupted", batch_id: "batch.cost", work_item_id: "cost", status: "interrupted", elapsed_seconds: 12, plan_revision_id: "plan.initial", diagnostic: "Computation completed, but retaining its outputs was interrupted; retained evidence is provisional.", output_dir: "p4-execution/batches/attempt.interrupted", artifacts: [{ source_path: "pilot-results.json", path: "p4-execution/batches/attempt.interrupted/artifacts/pilot-results.json", sha256: "a".repeat(64) }] }] } },
  decision: { run_id: "preview.decision", state: "awaiting_user", phase: "P4", p4_progress: progress },
  rejected: { run_id: "preview.rejected", state: "awaiting_user", phase: "P4", p4_progress: { ...progress, control_feedback: feedback } },
  unknown: { run_id: "preview.unknown", state: "awaiting_user", phase: "P4", p4_progress: { ...progress, control_feedback: { operation: "run_batch", code: "execution_outcome_unknown", json_pointer: "", execution_state: "unknown", error: "The tool response could not be delivered after the request was saved.", hint: "Inspect the saved request, pending batch, and attempt ledger before any retry." }, pause_request: { ...request, question: "Check the saved experiment state before continuing.", reason: "The tool response could not be delivered after the request was saved." }, ledger: [{ attempt_id: "attempt.pending", batch_id: "batch.cost", work_item_id: "cost", status: "not_started", elapsed_seconds: 0, plan_revision_id: "plan.initial" }] } },
  historical_unknown: { run_id: "preview.historical_unknown", state: "awaiting_user", phase: "P4", p4_progress: { ...progress, control_feedback: { accepted: true, operation: "request_decision" }, saved_answers: [{ request_id: previousRequest.request_id, request_revision: 1, revision: 1, request: previousRequest, note: "I inspected the saved attempt and authorized continuation.", applied_to: ["preview.historical_unknown"] }] } },
};
const labels = { correcting: "Correcting an artifact", stopped: "Repair stopped", interrupted: "Experiment interrupted", decision: "Direction needed", rejected: "Request rejected", unknown: "Outcome unknown", historical_unknown: "Saved uncertain outcome" };
let refresh = () => {};
const byId = (id) => Object.values(runs).find((run) => run.run_id === id);
// Synthetic endpoints exercise the production editor without starting research.
api.saveDecisionAnswer = async (_project, id, payload) => {
  const run = byId(id); const question = [run.p4_progress.pause_request, ...(run.p4_progress.saved_answers || []).map((answer) => answer.request)].find((item) => item?.request_id === payload.request_id && item.revision === payload.expected_revision);
  const saved = { request_id: payload.request_id, request_revision: payload.expected_revision, revision: (run.p4_progress.saved_answers?.length || 0) + 1, note: payload.note, request: question, applied_to: [] };
  run.p4_progress = { ...run.p4_progress, saved_answers: [...(run.p4_progress.saved_answers || []), saved], saved_answer: saved };
  refresh(); return { saved_answer: saved };
};
api.continueRun = async (_project, id, payload) => { const run = byId(id); run.state = "running"; run.p4_progress = { ...run.p4_progress, pause_request: null, control_feedback: { accepted: true }, finish_requested: payload.action === "finish" }; refresh(); return run; };
api.pauseRun = async (_project, id) => { const run = byId(id); run.state = "awaiting_user"; run.p4_progress = { ...run.p4_progress, pause_request: request }; refresh(); return run; };
api.cancelRun = async (_project, id) => { const run = byId(id); run.state = "cancelled"; refresh(); return run; };

function Preview() {
  const [selected, setSelected] = useState(() => new URLSearchParams(location.search).get("state") in runs ? new URLSearchParams(location.search).get("state") : "correcting");
  const [dark, setDark] = useState(false); const [, update] = useState(0); const history = useRef(null); const direction = useRef(null);
  refresh = () => update((value) => value + 1);
  const run = runs[selected];
  const inspect = () => { const details = history.current?.querySelector("details"); if (details) details.open = true; history.current?.scrollIntoView(); };
  return <main className="content" style={{ maxWidth: 1200, margin: "0 auto" }}><h1>Recovery progress</h1><p className="note">Synthetic saved states rendered with the production progress and decision components. Preview actions do not start research.</p>
    <div className="btnrow" aria-label="Recovery preview states">{Object.entries(labels).map(([key, label]) => <ActionButton key={key} action="details" variant={key === selected ? "primary" : undefined} aria-pressed={key === selected} onClick={() => { setSelected(key); window.history.replaceState(null, "", `?state=${key}`); }}>{label}</ActionButton>)}<label className="direction-choice"><input type="checkbox" checked={dark} onChange={(event) => { setDark(event.target.checked); document.documentElement.dataset.theme = event.target.checked ? "dark" : "light"; }} />Dark theme</label></div>
    <ResearchProgress run={run} phase={run.phase} onOpenRun={inspect}>{run.p4_progress && <EmpiricalProgressCard projectId="preview" run={run} onOpenRun={inspect} onShowIssues={() => direction.current?.scrollIntoView()} onChanged={refresh} />}</ResearchProgress>
    {run.p4_progress?.pause_request && <section className="card" data-card-role="attention" ref={direction}><h2>Issues and decisions</h2><div className="body"><EmpiricalPause key={run.run_id} projectId="preview" run={run} request={run.p4_progress.pause_request} onChanged={refresh} /></div></section>}
    <section ref={history} aria-label="Saved recovery history">{run.p4_progress ? <><EmpiricalSavedDecisions projectId="preview" run={run} onChanged={refresh} /><EmpiricalExecutionHistory run={run} /></> : <details className="research-details"><summary>Recorded repair findings</summary><p>The referenced evidence was not found in the frozen source list. The live run page provides the existing correction authorization action.</p><pre className="record">{JSON.stringify({ code: "reference.unmatched", json_pointer: "/central_claims/0/evidence_refs/0", attempt: 1 }, null, 2)}</pre></details>}</section>
  </main>;
}
createRoot(document.getElementById("root")).render(<Preview />);
