import React, { useEffect, useId, useRef, useState } from "react";
import { api } from "../api";
import { fmtMs, fmtBudgetSeconds, freshId, hasExactRef, humanLabel, TERMINAL } from "../research";
import { ResearchDocument, RunState, SourceRef } from "./Shared";
import { ActionButton } from "./Visuals";
import { directionDraftKey, evaluationPlanItems, evaluationRecovery, readDecisionDraft, saveDecisionDraft, decisionAnswerPayload, continuationPayload, savedAnswerMatches, latestDecisionAnswer, savedDecisionHistory } from "../empiricalProgress";

const asList = (value) => Array.isArray(value) ? value : [];
const seconds = (value) => Number.isFinite(value) ? fmtMs(value * 1000) : "Not recorded";
const stamp = (value) => typeof value === "string" ? value.slice(0, 19).replace("T", " ") : "Not recorded";

export default function EmpiricalProgress({ projectId, runId, run: suppliedRun, onChanged, onOpenRun, onShowIssues, includeHistory = false }) {
  const [snapshot, setSnapshot] = useState(null); const [error, setError] = useState(null); const [reload, setReload] = useState(0);
  useEffect(() => {
    if (suppliedRun || !runId) return;
    let alive = true; let pending = false;
    const read = async () => {
      if (pending) return; pending = true;
      try { const next = await api.run(projectId, runId); if (alive) { setSnapshot(next); setError(null); } }
      catch (failure) { if (alive) setError(failure.message); }
      finally { pending = false; }
    };
    read(); const timer = setInterval(read, 3000);
    return () => { alive = false; clearInterval(timer); };
  }, [projectId, runId, suppliedRun, reload]);
  const run = suppliedRun || (snapshot?.run_id === runId ? snapshot : null);
  const changed = () => { setReload((value) => value + 1); onChanged?.(); };
  if (!run?.p4_progress) return error ? <p className="error" role="alert">Evaluation progress could not be loaded: {error}</p> : null;
  return <><EmpiricalProgressCard projectId={projectId} run={run} error={error} onChanged={changed} onOpenRun={onOpenRun} onShowIssues={onShowIssues} />{includeHistory && <EmpiricalExecutionHistory run={run} />}</>;
}

export function EmpiricalPlan({ progress, settled = false, planOnly = false, compact = false }) {
  if (!progress || progress.execution_state_error) return <p className="note">The saved evaluation plan is unavailable.</p>;
  const tasks = evaluationPlanItems(progress, settled); const plan = progress.plan || {};
  return <>{(plan.decision_context?.intent_markdown || plan.intent_markdown) && <ResearchDocument text={plan.decision_context?.intent_markdown || plan.intent_markdown} />}
    {tasks.length > 0 ? <ol className={`evaluation-plan-list${compact ? " compact" : ""}`}>{tasks.map((task, index) => <li key={task.work_item_id || index}><div className="section-heading"><strong>{task.title || humanLabel(task.work_item_id)}</strong><RunState state={planOnly ? "execution_detail_not_recorded" : task.status} /></div>{task.reason && (compact ? <details className="research-details empirical-plan-reasoning"><summary>Why this comparison?</summary><ResearchDocument text={task.reason} /></details> : <ResearchDocument text={task.reason} />)}{task.question_markdown && <ResearchDocument text={task.question_markdown} />}{task.latest?.elapsed_seconds !== undefined && <p className="note">Latest attempt: {seconds(task.latest.elapsed_seconds)}{task.attempts.length > 1 && ` · ${task.attempts.length} recorded attempts`}.</p>}{task.deferred && task.latest && <p className="note">Further work on this comparison was deferred. Its earlier attempts remain recorded.</p>}{(task.reason_not_run || task.latest?.reason) && <ResearchDocument text={task.reason_not_run || task.latest.reason} />}</li>)}</ol> : <p className="note">The analyst has not yet recorded an ordered experiment plan.</p>}
    {asList(plan.amendments || progress.amendments).map((amendment, index) => <div className="context-note" key={amendment.revision_id || index}>{compact ? <details className="research-details empirical-plan-changes"><summary>Plan change {index + 1}</summary><ResearchDocument text={amendment.reason_markdown} /><ResearchDocument text={amendment.changes_markdown} /></details> : <><h4>Plan change {index + 1}</h4><ResearchDocument text={amendment.reason_markdown} /><ResearchDocument text={amendment.changes_markdown} /></>}{amendment.inferential_consequences_markdown && <ResearchDocument text={amendment.inferential_consequences_markdown} />}</div>)}
  </>;
}

// Execution status stays separate from the reviewed scientific account and the
// single decision editor in Card 3. No response form is rendered in this strip.
export function EmpiricalProgressCard({ projectId, run, error, onChanged, onOpenRun, onShowIssues }) {
  const progress = run.p4_progress; const [busy, setBusy] = useState(false); const [failure, setFailure] = useState(null); const lock = useRef(false);
  if (!progress) return null;
  const tasks = evaluationPlanItems(progress, TERMINAL.has(run.state)); const budget = progress.budget || {}; const waiting = run.state === "awaiting_user";
  const setup = progress.setup_attention;
  const recovery = setup ? null : evaluationRecovery(progress);
  const active = tasks.find((task) => task.work_item_id === progress.pending_batch?.work_item_id);
  const pause = async () => {
    if (lock.current) return; lock.current = true; setBusy(true); setFailure(null);
    try { await api.pauseRun(projectId, run.run_id); onChanged?.(); }
    catch (problem) { setFailure(problem.message); }
    finally { lock.current = false; setBusy(false); }
  };
  return <section className="empirical-progress-strip" data-card-role={waiting ? "attention" : "progress"} data-recovery-state={recovery?.kind} aria-label="Evaluation progress"><div className="section-heading" role="status" aria-atomic="true">{setup || recovery ? <strong>{setup ? "Setup needs attention" : recovery.title}</strong> : <RunState state={run.state} />}<span>{setup?.message || recovery?.message || active?.title || (waiting ? "Your direction is needed before work continues." : run.state === "published" ? "Evaluation published after review." : "Evaluation work is provisional until scientific review.")}</span></div>
    {setup && <><ResearchDocument text={setup.guidance} /><TechnicalLogs setup={setup} /></>}
    {recovery && <RecoveryDetails recovery={recovery} />}
    <p className="note">Experiment time: {fmtBudgetSeconds(budget.used_seconds)} used · {fmtBudgetSeconds(budget.remaining_seconds)} remaining. This is separate from per-fit method cost.</p>
    {run.state === "stopping" && <p className="note" role="status">Stopping the current work. You can give direction once it has stopped.</p>}
    {(error || failure) && <p className="error" role="alert">{failure || error}</p>}
    <div className="btnrow">{waiting && (onShowIssues || onOpenRun) && <ActionButton action="details" data-run-origin={`EmpiricalProgress:direction:${run.run_id}`} onClick={(event) => onShowIssues ? onShowIssues() : onOpenRun(run.run_id, event.currentTarget)}>{setup ? "Review setup and continuation" : recovery?.actionLabel || "Review requested direction"}</ActionButton>}{!TERMINAL.has(run.state) && !waiting && run.state !== "stopping" && !progress.execution_state_error && <ActionButton action="pause" uiRole="research" disabled={busy} onClick={pause}>{busy ? "Requesting pause…" : "Pause and give direction"}</ActionButton>}{onOpenRun && <ActionButton action="details" variant="link" data-run-origin={`EmpiricalProgress:1:${run.run_id}`} onClick={(event) => onOpenRun(run.run_id, event.currentTarget)}>Open run history</ActionButton>}</div>
  </section>;
}

function TechnicalLogs({ setup }) {
  return <details className="research-details"><summary>Technical log for this attempt</summary>{setup.diagnostic && <ResearchDocument text={setup.diagnostic} />}{asList(setup.logs).map((log) => <section key={log.path}><h4>{log.path}</h4><pre className="record">{log.text || "The log is empty."}</pre>{log.truncated && <p className="note">Showing the first 8 KiB. The complete retained log remains at this path.</p>}{log.sha256 && <p className="note">SHA-256: <code>{log.sha256}</code></p>}</section>)}{!setup.logs?.length && <p className="note">No launch log was retained for this attempt.</p>}</details>;
}

function RecoveryDetails({ recovery, reason }) {
  if (!recovery) return null;
  const feedback = recovery.feedback || {}; const attempt = recovery.attempt;
  const receipt = attempt ? { attempt_id: attempt.attempt_id, batch_id: attempt.batch_id, status: attempt.status,
    diagnostic: attempt.diagnostic, output_dir: attempt.output_dir, artifacts: attempt.artifacts }
    : Object.fromEntries(["operation", "code", "json_pointer", "object_id", "findings", "execution_state", "accepted", "error"].filter((key) => feedback[key] !== undefined).map((key) => [key, feedback[key]]));
  return <details className="research-details" data-recovery-details="true" style={{ gridColumn: "1 / -1", minWidth: 0 }}><summary>Recovery details</summary>
    {feedback.hint && <ResearchDocument text={feedback.hint} />}{reason && <ResearchDocument text={reason} />}
    <pre className="record">{JSON.stringify(receipt, null, 2)}</pre>
  </details>;
}

export function EmpiricalExecutionHistory({ run }) {
  const progress = run?.p4_progress; if (!progress) return null;
  const ledger = Array.isArray(progress.ledger) ? progress.ledger : asList(progress.ledger?.entries);
  const tasks = evaluationPlanItems(progress, TERMINAL.has(run.state));
  const checkpoint = progress.checkpoint || {}; const observed = checkpoint.observed_results_markdown ?? checkpoint.observed_results; const next = checkpoint.next_action_markdown ?? checkpoint.next_action;
  const feedback = checkpoint.host_feedback ? evaluationRecovery({ control_feedback: checkpoint.latest_control_feedback }) : null;
  return <details className="research-details empirical-execution-history" data-card-role="history"><summary>Evaluation activity and recorded attempts ({ledger.length})</summary>
    <p className="note">Last progress update: {stamp(checkpoint.saved_at || progress.last_checkpoint_at)}.</p>
    {progress.execution_state_error ? <p className="error">The saved execution state could not be read: {progress.execution_state_error}.</p> : <EmpiricalPlan progress={progress} settled={TERMINAL.has(run.state)} />}
    {run.state === "failed" && run.terminal_reason && <div className="context-note"><b>Why this evaluation stopped</b><ResearchDocument text={run.terminal_reason} />{!ledger.length && !progress.execution_state_error && <p className="note">No managed experiment was recorded for this attempt.</p>}</div>}
    {checkpoint.host_feedback ? <div className="context-note"><b>Last planning feedback</b><p>{feedback?.message || "The analyst needed a concrete next action to advance the evaluation."}</p>{feedback ? <RecoveryDetails recovery={feedback} reason={checkpoint.summary} /> : <details className="research-details"><summary>Recorded planning feedback</summary><ResearchDocument text={checkpoint.summary} /></details>}</div> : <>{checkpoint.summary && <ResearchDocument text={checkpoint.summary} />}{observed && <section><h4>Provisional observations</h4><ResearchDocument text={observed} /></section>}{next && <section><h4>Next planned action</h4><ResearchDocument text={next} /></section>}</>}
    {ledger.length > 0 && <div className="table-scroll"><table><caption>Recorded experiment attempts</caption><thead><tr><th scope="col">Comparison</th><th scope="col">Status</th><th scope="col">Experiment time</th><th scope="col">Plan revision</th></tr></thead><tbody>{ledger.map((entry, index) => <tr key={entry.attempt_id || index}><td>{tasks.find((task) => task.work_item_id === entry.work_item_id)?.title || entry.work_item_id || entry.batch_id}</td><td><RunState state={entry.status} /></td><td>{seconds(entry.elapsed_seconds)}</td><td>{entry.plan_revision_id || "Not recorded"}</td></tr>)}</tbody></table></div>}
  </details>;
}

// This editor belongs only in Issues and decisions. Saving a revision never
// starts work; continuation names the exact saved revision that will be used.
export function EmpiricalPause({ projectId, run, request, onChanged, onNavigate, onSource, onExplain }) {
  return <EmpiricalPauseEditor key={directionDraftKey(projectId, run.run_id, request)} {...{ projectId, run, request, onChanged, onNavigate, onSource, onExplain }} />;
}

export function EmpiricalSavedDecisions({ projectId, run, onChanged, onNavigate, onSource, onExplain }) {
  const decisions = savedDecisionHistory(run?.p4_progress, run?.state === "awaiting_user");
  if (!decisions.length) return null;
  return <details className="research-details empirical-saved-decisions" data-reading-anchor={`evaluation:${run.run_id}:saved-decisions`}><summary>Saved evaluation decisions ({decisions.length})</summary>{decisions.map(({ request }) => <EmpiricalPauseEditor key={directionDraftKey(projectId, run.run_id, request)} historical {...{ projectId, run, request, onChanged, onNavigate, onSource, onExplain }} />)}</details>;
}

function EmpiricalPauseEditor({ projectId, run, request, onChanged, onNavigate, onSource, onExplain, historical = false }) {
  const id = useId(); const draftKey = directionDraftKey(projectId, run.run_id, request);
  const initialSaved = latestDecisionAnswer(run.p4_progress, request);
  const [saved, setSaved] = useState(() => savedAnswerMatches(initialSaved, request) ? initialSaved : null);
  const [draft, setDraft] = useState(() => readDecisionDraft(draftKey, savedAnswerMatches(initialSaved, request) ? initialSaved : null));
  const [editing, setEditing] = useState(!historical);
  const answer = draft.note;
  const [draftError, setDraftError] = useState(null); const [contextChoice, setContextChoice] = useState(""); const [extraBudget, setExtraBudget] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState(null); const lock = useRef(false); const key = useRef(null); const submissionAction = useRef(null);
  const changes = asList(run.p4_progress.context_changes); const blocked = run.p4_progress.continuation_blocked;
  const waiting = !historical && run.state === "awaiting_user";
  const setup = request.attention_kind === "setup";
  const recovery = setup ? null : evaluationRecovery(run.p4_progress, request);
  const dirty = answer.trim() !== (saved?.note || "").trim() || Boolean(request.scope && (draft.origin || "researcher_reported") !== (saved?.origin || "researcher_reported"));
  const stale = Boolean(saved && draft.base_revision !== saved.revision && dirty);
  const budgetInvalid = extraBudget !== "" && (!Number.isFinite(Number(extraBudget)) || Number(extraBudget) < 0);
  useEffect(() => { const incoming = latestDecisionAnswer(run.p4_progress, request); if (incoming && (!saved || incoming.revision >= saved.revision)) { setSaved(incoming); if (!dirty) setDraft({ note: incoming.note, base_revision: incoming.revision, ...(incoming.origin ? { origin: incoming.origin } : {}) }); } }, [run.p4_progress.saved_answer, run.p4_progress.saved_answers, request.request_id, request.revision]);
  useEffect(() => { setDraftError(saveDecisionDraft(draftKey, draft) ? null : "Your draft is retained for this exact question in this browser session."); }, [draftKey, draft]);
  const save = async () => {
    if (lock.current || !answer.trim() || (!dirty && saved)) return;
    lock.current = true; setBusy(true); setError(null);
    try {
      const contextRevision = request.scope?.kind === "project" ? (await api.problemContext(projectId)).revision : undefined;
      const result = await api.saveDecisionAnswer(projectId, run.run_id, decisionAnswerPayload(request, answer, draft.base_revision, { origin: draft.origin, contextRevision }));
      const value = result.saved_answer || result.answer || result;
      if (!Number.isInteger(value.revision) || typeof value.note !== "string") throw new Error("The saved response could not be confirmed. Refresh this run before continuing.");
      setSaved({ ...value, origin: draft.origin || "researcher_reported" }); setDraft({ note: value.note, base_revision: value.revision, origin: draft.origin || "researcher_reported" }); if (historical) setEditing(false); key.current = null; onChanged?.();
    } catch (problem) { setError(problem.message); if (problem.status === 409) onChanged?.(); }
    finally { lock.current = false; setBusy(false); }
  };
  const submit = async (action) => {
    if (lock.current || !waiting || blocked || dirty || (action === "finish" && !run.p4_progress.plan) || (action === "continue" && (!saved?.revision || !saved.note?.trim() || budgetInvalid)) || (changes.length && contextChoice !== "frozen")) return;
    lock.current = true; setBusy(true); setError(null);
    if (submissionAction.current !== action) key.current = null;
    submissionAction.current = action; key.current ||= freshId();
    try {
      await api.continueRun(projectId, run.run_id, continuationPayload({ request, action, saved, contextChoice, extraBudget, idempotencyKey: key.current }));
      saveDecisionDraft(draftKey, null);
      onChanged?.();
    } catch (problem) { setError(problem.message); }
    finally { lock.current = false; setBusy(false); }
  };
  const end = async () => {
    if (lock.current || !waiting) return; lock.current = true; setBusy(true); setError(null);
    try { await api.cancelRun(projectId, run.run_id); onChanged?.(); }
    catch (problem) { setError(problem.message); }
    finally { lock.current = false; setBusy(false); }
  };
  const usedBefore = asList(run.p4_progress.saved_answers).some((item) => savedAnswerMatches(item, request) && item.applied_to?.length);
  const effect = saved?.applied_to?.length ? "This response was used by the evaluation. Edits cannot change work already completed." : saved ? usedBefore ? "Updated for future work; the earlier evaluation used your previous answer." : historical ? "Response saved for future work." : "Response saved for this evaluation. Continue applies this exact saved response." : "Your draft is kept in this browser. Save your response to make it available to the evaluation.";
  return <section className="evaluation-pause" data-card-role={historical || (saved?.applied_to?.length && !waiting) ? "history" : "attention"} aria-labelledby={`${id}-title`}>
    <div className="section-heading"><h3 id={`${id}-title`}>{setup ? waiting ? "Setup needs attention" : "Saved setup direction" : waiting ? "Waiting for your direction" : "Your evaluation direction"}</h3>{!setup && onExplain && request.explanation_target && <ActionButton action="ask" uiRole="research" aria-label="Explain more about this decision" onClick={() => onExplain({ ...request.explanation_target, label: request.question || request.question_markdown, statement: request.reason || request.reason_markdown })}>Explain more</ActionButton>}</div>
    {setup && <p className="note">The computation did not run. Correct the shared runtime or sandbox access before continuing; this is not evidence that the model failed. Saving setup instructions does not restart work.</p>}
    {setup && waiting && run.p4_progress.setup_attention && <><ResearchDocument text={run.p4_progress.setup_attention.guidance} /><TechnicalLogs setup={run.p4_progress.setup_attention} /></>}
    <ResearchDocument text={request.question || request.question_markdown} />{recovery ? <><p>{recovery.message}</p><RecoveryDetails recovery={recovery} reason={request.reason || request.reason_markdown} /></> : <ResearchDocument text={request.reason || request.reason_markdown} />}
    {request.recommendation && <div className="context-note" data-card-role="research"><b>Team recommendation</b><ResearchDocument text={request.recommendation} /></div>}
    {asList(request.options).length > 0 && <ul className="direction-options">{request.options.map((option, index) => <li key={option.option_id || index}><b>{option.label}</b><p>{option.consequence}</p></li>)}</ul>}
    {asList(request.evidence_refs).length > 0 && <details className="research-details"><summary>Evidence for this question</summary>{request.evidence_refs.map((reference, index) => typeof reference === "string" ? <p className="note" key={index}>{reference}</p> : hasExactRef(reference) ? <SourceRef key={index} reference={reference} onOpen={onSource} /> : <div key={index}><ResearchDocument text={reference.statement || reference.description} />{reference.path && <p className="note">Saved input: <code>{reference.path}</code></p>}</div>)}</details>}
    {changes.length > 0 && waiting && <div className="context-note"><h4>Research context has changed</h4>{changes.map((change, index) => <ResearchDocument key={index} text={typeof change === "string" ? change : change.message || change} />)}<label className="direction-choice"><input type="checkbox" checked={contextChoice === "frozen"} onChange={(event) => { setContextChoice(event.target.checked ? "frozen" : ""); key.current = null; }} disabled={busy} /><span>Continue using this run's frozen research context. To evaluate a changed method, start a new run.</span></label></div>}
    {blocked && waiting && <p className="note warn" role="alert">{typeof blocked === "string" ? blocked : "This run cannot continue against the changed method or publication. Its observations remain available; start a new run for the current model."}</p>}
    {historical && !editing ? <div className="context-note contribution-surface"><b>Your saved response</b><ResearchDocument text={saved?.note} /><p className="note">{effect}</p>{dirty && <p className="note">An unsaved edit is kept in this browser.</p>}<ActionButton action="edit" uiRole="research" onClick={() => setEditing(true)}>Edit response</ActionButton></div> : <div className="field contribution-surface"><label htmlFor={`${id}-answer`}>Your instruction or answer</label><textarea id={`${id}-answer`} rows={4} value={answer} onChange={(event) => { setDraft((current) => ({ ...current, note: event.target.value })); key.current = null; }} disabled={busy} /><p className="note" role="status">{draftError || (dirty ? historical ? "Unsaved changes are kept in this browser. Save your response for future work." : "Unsaved changes are kept in this browser. Save your response before continuing." : effect)}</p></div>}
    {stale && <p className="note warn">A newer response was saved elsewhere. Your local edits are preserved; reload the saved response before replacing it.</p>}
    {editing && !setup && <div className="btnrow"><ActionButton action="edit" uiRole="research" disabled={busy} onClick={() => setDraft((current) => ({ ...current, note: "I am not sure.", origin: "unknown" }))}>I am not sure</ActionButton><ActionButton action="edit" uiRole="research" disabled={busy} onClick={() => setDraft((current) => ({ ...current, note: "No data yet.", origin: "researcher_reported" }))}>No data yet</ActionButton></div>}
    {request.scope?.kind === "project" && <p className="note">Saving also retains this response in the shared understanding across models.</p>}
    {editing && <div className="btnrow"><ActionButton action="save" uiRole="research" variant="primary" disabled={busy || !answer.trim() || (!dirty && Boolean(saved)) || stale} onClick={save}>{busy ? "Saving or submitting…" : saved ? "Save updated response" : "Save response"}</ActionButton>{saved && dirty && <ActionButton action="retry" disabled={busy} onClick={() => { setDraft({ note: saved.note, base_revision: saved.revision }); setError(null); }}>Use saved response</ActionButton>}</div>}
    <p className="note">{historical ? "Saving an edit does not change this evaluation. After it ends, your latest response is included when you explicitly start another evaluation." : "Saving or discussing an answer does not resume experiments."}</p>
    {waiting && <>
      <div className="field optional-budget"><label htmlFor={`${id}-budget`}>Additional experiment seconds (optional)</label><input id={`${id}-budget`} type="number" min="0" step="1" value={extraBudget} onChange={(event) => { setExtraBudget(event.target.value); key.current = null; }} disabled={busy} aria-describedby={`${id}-budget-note`} /><p className="note" id={`${id}-budget-note`}>Leave blank to keep the remaining budget. Extra time is granted only when you continue.</p></div>
      {budgetInvalid && <p className="error" role="alert">Additional time must be zero or a positive number of seconds.</p>}
      <div className="btnrow"><ActionButton action="continue" uiRole="research" variant="primary" disabled={busy || Boolean(blocked) || dirty || !saved?.revision || !saved.note?.trim() || budgetInvalid || (changes.length > 0 && contextChoice !== "frozen")} onClick={() => submit("continue")}>Continue with instructions</ActionButton><ActionButton action="check" uiRole="research" disabled={busy || Boolean(blocked) || dirty || !run.p4_progress.plan || (changes.length > 0 && contextChoice !== "frozen")} onClick={() => submit("finish")}>Finish with evidence so far</ActionButton><ActionButton action="stop" variant="danger" disabled={busy} onClick={end}>End run</ActionButton></div>
      <p className="note">{run.p4_progress.plan ? "Finishing sends the available evidence through theorist and lead review." : "Finishing becomes available after the analyst saves an evaluation plan. Answer the question and continue, or end this run."} Ending keeps the work provisional and publishes no new account.</p>
    </>}
    {error && <p className="error" role="alert">{error}</p>}
    {!setup && onNavigate && <div className="btnrow"><ActionButton action="details" variant="link" onClick={() => onNavigate("P2")}>Open Phase 2 methods</ActionButton><ActionButton action="details" variant="link" onClick={() => onNavigate("P3")}>Open Phase 3 theory</ActionButton></div>}
  </section>;
}
