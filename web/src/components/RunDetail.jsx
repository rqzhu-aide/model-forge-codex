import RunFindings from "./RunFindings.jsx";
import { explanationRun } from "../phaseWorkflow";
import React, { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { TERMINAL, activityIsSettled, humanLabel, modeLabel, shouldReconnectActivity } from "../research";
import { ResearchDocument, RunState } from "./Shared";
import { ActionButton } from "./Visuals";
import EmpiricalProgress from "./EmpiricalProgress";
import ResearchProgress from "./ResearchProgress";
import { activitySummary } from "../runActivity";
import ResearcherPause from "./ResearcherPause";
import AssumptionConversations from "./AssumptionConversations";

export function RunActivity({ run, events, connection }) {
  const [showAll, setShowAll] = useState(false);
  const terminal = TERMINAL.has(run.state);
  const shown = showAll ? events : events.slice(-60);
  return <details className="card activity-panel" data-card-role="history" open={!terminal && !run.p4_progress}>
    <summary className="card-summary">Activity <span className="note">{terminal || run.state === "awaiting_user" ? "Recorded history" : connection === "live" ? "Live" : humanLabel(connection)}</span></summary>
    <div className="body feed">{shown.map((event, index) => {
      const summary = activitySummary(event);
      return <div className="row" key={event._key || event.event_id || index}><span className="t">{(event.at || "").slice(11, 19)}</span><span className="who">{summary.actor}</span><span className={summary.tone === "warn" ? "warn" : undefined} style={{ overflowWrap: "anywhere", minWidth: 0 }}>{summary.message}</span></div>;
    })}
    {!events.length && <p className="note">No activity has been received yet.</p>}
    {events.length > 60 && <ActionButton action="details" onClick={() => setShowAll(!showAll)}>{showAll ? "Show recent activity" : `Show all ${events.length} events`}</ActionButton>}
    {events.length > 0 && <details className="research-details" data-technical-activity="true"><summary>Technical activity log</summary><pre className="record">{JSON.stringify(events.map(({ _key, ...event }) => event), null, 2)}</pre></details>}
    </div>
  </details>;
}

export default function RunDetail({ projectId, runId, onBack }) {
  const [run, setRun] = useState(null); const [preview, setPreview] = useState(null); const [events, setEvents] = useState([]);
  const [note, setNote] = useState(""); const [error, setError] = useState(null); const [previewError, setPreviewError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [conversationTarget, setConversationTarget] = useState(null); const [conversations, setConversations] = useState([]);
  const [connection, setConnection] = useState("connecting"); const [epoch, setEpoch] = useState(0); const [busy, setBusy] = useState(false);
  const lock = useRef(false); const stateRef = useRef(null);
  useEffect(() => {
    if (!conversationTarget) return;
    let active = true;
    api.assessments(projectId, conversationTarget.branch || run?.branch_id || "trunk").then((result) => { if (active) setConversations(result.assessments || []); }).catch((failure) => { if (active) setActionError(failure.message); });
    return () => { active = false; };
  }, [projectId, conversationTarget, epoch]);
  useEffect(() => {
    let alive = true; let pending = false; let reconnect; let stream; let retry = 0; let closedState = null;
    const refresh = async () => {
      if (pending) return; pending = true;
      const results = await Promise.allSettled([api.run(projectId, runId), api.correctionPreview(projectId, runId)]);
      if (alive) {
        if (results[0].status === "fulfilled") { const previous = stateRef.current; setRun(results[0].value); stateRef.current = results[0].value.state; setError(null); if (shouldReconnectActivity(previous, stateRef.current, closedState)) { stream?.close(); clearTimeout(reconnect); connect(); } }
        else setError(results[0].reason.message);
        if (results[1].status === "fulfilled") { setPreview(results[1].value); setPreviewError(null); }
        else setPreviewError(results[1].reason.message);
      }
      pending = false;
    };
    const connect = () => {
      if (!alive) return;
      closedState = null; setConnection("connecting"); stream = new EventSource(api.activityUrl(projectId, runId));
      stream.onopen = () => { if (alive) { retry = 0; setConnection("live"); } };
      stream.onmessage = (message) => {
        if (!alive) return;
        let event; try { event = JSON.parse(message.data); } catch { setConnection("unreadable update; checking run state"); refresh(); return; }
        if (event.type === "stream.closed") { closedState = event.state; stream.close(); setConnection("complete"); refresh(); return; }
        const key = event.event_id || event.id || message.lastEventId || JSON.stringify(event);
        setEvents((current) => current.some((e) => e._key === key) ? current : [...current, { ...event, _key: key }]);
        // Stage and lifecycle notifications refresh both run state and correction eligibility.
        if (/^(run\.|stage\.|member\.|turn\.|p4\.)/.test(event.type || "")) refresh();
      };
      stream.onerror = () => {
        stream.close(); if (!alive) return;
        if (activityIsSettled(stateRef.current)) { setConnection("complete"); return; }
        setConnection("disconnected"); refresh();
        reconnect = setTimeout(connect, Math.min(1000 * 2 ** retry++, 10000));
      };
    };
    refresh(); connect(); const poll = setInterval(refresh, 3000);
    const focus = () => refresh(); window.addEventListener("focus", focus);
    return () => { alive = false; stream?.close(); clearTimeout(reconnect); clearInterval(poll); window.removeEventListener("focus", focus); };
  }, [projectId, runId, epoch]);
  const correct = async (event) => {
    event.preventDefault(); if (lock.current) return; lock.current = true; setBusy(true); setActionError(null);
    try { await api.correctRun(projectId, runId, note); setNote(""); setEpoch((n) => n + 1); }
    catch (e) { setActionError(e.message); setEpoch((n) => n + 1); } finally { lock.current = false; setBusy(false); }
  };
  const cancel = async () => {
    if (lock.current) return; lock.current = true; setBusy(true); setActionError(null);
    try { await api.cancelRun(projectId, runId); setEpoch((n) => n + 1); }
    catch (e) { setActionError(e.message); } finally { lock.current = false; setBusy(false); }
  };
  const retryProvider = async () => {
    if (lock.current || run?.state !== "failed" || run.provider_retry?.eligible !== true) return;
    lock.current = true; setBusy(true); setActionError(null);
    try { await api.retryProvider(projectId, runId); setEpoch((n) => n + 1); }
    catch (e) { setActionError(e.message); setEpoch((n) => n + 1); }
    finally { lock.current = false; setBusy(false); }
  };
  if (!run) return error ? <div className="error" role="alert">{error} <ActionButton action="retry" onClick={() => setEpoch((n) => n + 1)}>Retry</ActionButton><ActionButton action="back" onClick={onBack}>Return to research</ActionButton></div> : <p role="status" className="note">Loading run…</p>;
  const terminal = TERMINAL.has(run.state); const findings = run.findings_history?.slice(-1)[0] || [];
  const providerRetry = run.state === "failed" && run.provider_retry?.eligible === true;
  const providerInterruption = providerRetry || run.state === "failed" && run.provider_retry?.failure_code === "provider.capacity";
  return <>
    <header className="page"><div><h1 className="serif">{run.assessment_purpose === "issue_suggestions" ? "Lead suggestions" : explanationRun(run) ? "Explanation conversation" : modeLabel(run.mode)}</h1><div className="sub">{run.phase} · {humanLabel(run.branch_id)} · <RunState state={run.state} /></div></div><div className="btnrow">{!terminal && <ActionButton action="stop" variant="danger" onClick={cancel} disabled={busy}>End run</ActionButton>}<ActionButton action="back" onClick={onBack}>Return to research</ActionButton></div></header>
    {error && <p className="error" role="alert">{error}</p>}
    {actionError && <p className="error" role="alert">{actionError} <ActionButton action="close" variant="link" onClick={() => setActionError(null)}>Dismiss</ActionButton></p>}
    {connection === "disconnected" && <p className="note warn" role="status">Live activity was disconnected. Reconnecting automatically; the run state is still being checked. <ActionButton action="retry" onClick={() => setEpoch((n) => n + 1)}>Reconnect now</ActionButton></p>}
    {explanationRun(run) ? <p className="context-note">This discussion uses saved scientific sources. It does not change the research or run experiments.</p> : run.intent === "assessment" || run.mode === "p3.assessment" ? <p className="context-note">This work saves a focused assessment. The formal theory is changed only through a separate reviewed repair.</p> : terminal && run.state === "published" ? <p className="context-note">The run has published its account. Open the research workspace to inspect the scientific conclusion and evidence.</p> : null}
    <ResearchProgress expanded run={run} phase={run.phase} branch={run.branch_id} retained={run.state === "published"}>{run.phase === "P4" && <EmpiricalProgress projectId={projectId} run={run} includeHistory onShowIssues={run.state === "awaiting_user" && run.p4_progress?.pause_request ? onBack : undefined} onChanged={() => setEpoch((value) => value + 1)} />}</ResearchProgress>
    {run.state === "awaiting_user" && run.researcher_pause?.pending_request && <section className="card" data-card-role="attention"><div className="body"><ResearcherPause key={`${run.run_id}:${run.researcher_pause.pending_request.request_id}:${run.researcher_pause.pending_request.revision}`} projectId={projectId} run={run} onSaved={() => setEpoch((value) => value + 1)} onDiscuss={setConversationTarget} onPrepare={onBack} /></div></section>}
    {(run.instructions || run.target) && <details className="research-details"><summary>Requested work and source</summary>{run.instructions && <ResearchDocument text={run.instructions} />}{run.target && <pre className="record">{JSON.stringify(run.target, null, 2)}</pre>}</details>}
    {(findings.length > 0 || run.state === "failed") && <section className="card" data-card-role={run.state === "failed" ? "attention" : "history"}><h2>{run.state === "failed" ? "Work needs attention" : "Validation findings"}</h2><div className="body">{run.state === "failed" && run.terminal_reason && <ResearchDocument text={run.terminal_reason} />}<RunFindings findings={findings} />{!findings.length && <p className="note">No structured validation finding was recorded.</p>}
      {providerRetry && <><p className="note">Retry the interrupted step with the same frozen model and remaining experiment budget. Saved work and your evaluation direction are retained.</p><ActionButton action="retry" uiRole="research" variant="primary" onClick={retryProvider} disabled={busy}>{busy ? "Requesting retry…" : "Retry interrupted step"}</ActionButton></>}
      {providerInterruption && !providerRetry && run.provider_retry?.reason && <div className="note" role="status"><ResearchDocument text={run.provider_retry.reason} /></div>}
      {!providerInterruption && previewError && <p className="error" role="alert">Correction availability could not be checked: {previewError}</p>}
      {run.state === "failed" && !providerInterruption && preview?.eligible && <form className="contribution-surface" onSubmit={correct}><div className="field"><label htmlFor="correction-note">Correction note</label><textarea id="correction-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Clarify how the reported validation failure should be addressed." disabled={busy} /></div><p className="note">This correction addresses the reported failure. A scientific change to published theory belongs in a reviewed revision.</p><ActionButton action="repair" uiRole="research" variant="primary" type="submit" disabled={busy}>{busy ? "Requesting correction…" : "Authorize correction"}</ActionButton><span className="note"> {preview.attempts_remaining} attempt{preview.attempts_remaining === 1 ? "" : "s"} remaining.</span></form>}
      {run.state === "failed" && !providerInterruption && preview && !preview.eligible && preview.attempts_remaining > 0 && preview.reason && <p className="note" role="status">{preview.reason}</p>}
      {run.state === "failed" && !providerInterruption && preview?.attempts_remaining === 0 && <p className="note">The correction budget for this run is spent. Return to the research workspace to plan further work.</p>}
    </div></section>}
    <RunActivity run={run} events={events} connection={connection} />
    <details className="drawer" data-card-role="history"><summary>Execution detail, usage, and member threads</summary><div className="strip"><div className="stat"><div className="k">Correction attempts</div><div className="v">{run.correction_attempts || 0}</div></div><div className="stat"><div className="k">Recorded tokens</div><div className="v">{(run.usage?.input_tokens || 0).toLocaleString()} in · {(run.usage?.output_tokens || 0).toLocaleString()} out</div></div></div><p className="note">Run: {run.run_id}</p>{Object.entries(run.thread_ids || {}).map(([key, id]) => <p className="note" key={key}>{key}: {id}</p>)}<pre className="record">{JSON.stringify(run, null, 2)}</pre></details>
    {conversationTarget && <AssumptionConversations projectId={projectId} target={conversationTarget} conversations={conversations} onClose={() => setConversationTarget(null)} onStarted={() => setEpoch((value) => value + 1)} />}
  </>;
}
