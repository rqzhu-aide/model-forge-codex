import React, { useId, useRef, useState } from "react";
import { api } from "../api";
import { humanLabel, freshId } from "../research";
import { readConversationDraft, saveConversationDraft } from "../assumptionConversations";
import { ResearchDocument, SourceRef } from "./Shared";
import { ActionButton, ActionIcon } from "./Visuals";

function QuestionSource({ reference, onSource }) {
  const ref = reference?.generation_ref || reference;
  if (ref?.branch && ref.phase && ref.family && ref.generation_id) return <SourceRef reference={ref} onOpen={onSource} label={reference.label || reference.title || "Open source"} />;
  const url = typeof reference === "string" ? reference : reference?.source_url || reference?.artifact_url || reference?.url;
  if (/^https?:\/\/|^\/api\//i.test(url || "")) return <a className="source-link ui-action" data-action="source" data-ui-role="system" href={url} target="_blank" rel="noreferrer"><ActionIcon name="source" />{reference.label || reference.title || "Open source"}</a>;
  const text = typeof reference === "string" ? reference : reference?.statement || reference?.description || reference?.citation || Object.entries(reference || {}).map(([key, value]) => `${humanLabel(key)}: ${typeof value === "object" ? JSON.stringify(value) : value}`).join("\n\n");
  return <ResearchDocument text={text} />;
}

export default function ResearcherPause({ projectId, run, onSaved, onDiscuss, onPrepare, onSource }) {
  const pause = run?.researcher_pause; const request = pause?.pending_request;
  const id = useId(); const key = `researcher-pause:${JSON.stringify([projectId, run?.run_id, request?.request_id, request?.revision, request?.explanation_target?.sha256])}`;
  const latest = (pause?.saved_answers || []).filter((answer) => answer.request_id === request?.request_id && answer.request_revision === request?.revision).sort((a, b) => b.revision - a.revision)[0];
  const [saved, setSaved] = useState(latest || null);
  const [text, setText] = useState(() => readConversationDraft(key)?.text ?? latest?.note ?? "");
  const [origin, setOrigin] = useState(() => readConversationDraft(key)?.origin || latest?.origin || "researcher_reported"); const [savedOrigin, setSavedOrigin] = useState(latest?.origin || "researcher_reported");
  const [frozen, setFrozen] = useState(false); const [busy, setBusy] = useState(false); const lock = useRef(false);
  const [error, setError] = useState(null); const [notice, setNotice] = useState(null); const submission = useRef(freshId());
  if (!request) return null;
  const changes = pause.context_changes || [];
  const dirty = !saved || text.trim() !== saved.note.trim() || origin !== savedOrigin;
  const update = (value, nextOrigin = origin) => { setText(value); setOrigin(nextOrigin); saveConversationDraft(key, { text: value, origin: nextOrigin }); setNotice(null); };
  const save = async (event) => {
    event.preventDefault(); if (lock.current || !text.trim()) return;
    lock.current = true; setBusy(true); setError(null);
    try {
      const contextRevision = request.scope?.kind === "project" ? (await api.problemContext(projectId)).revision : undefined;
      const result = await api.saveDecisionAnswer(projectId, run.run_id, { request_id: request.request_id, expected_revision: request.revision, expected_answer_revision: saved?.revision || 0, note: text.trim(), ...(request.scope ? { origin } : {}), ...(request.scope?.kind === "project" ? { save_to_context: true, context_expected_revision: contextRevision } : {}) });
      const answer = result.saved_answer || result.answer || result;
      if (!Number.isInteger(answer.revision) || typeof answer.note !== "string") throw new Error("The saved response could not be confirmed. Refresh the run before continuing.");
      setSaved({ ...answer, origin }); setSavedOrigin(origin); setText(answer.note); saveConversationDraft(key, null); setNotice("Response saved. Work remains paused until you choose Continue work."); onSaved?.();
    } catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  };
  const continueWork = async () => {
    if (lock.current || dirty || !saved || changes.length && !frozen) return;
    lock.current = true; setBusy(true); setError(null);
    try { await api.continueRun(projectId, run.run_id, { request_id: request.request_id, expected_revision: request.revision, answer_revision: saved.revision, action: "continue", context_choice: changes.length ? "frozen" : undefined, idempotency_key: submission.current }); saveConversationDraft(key, null); onSaved?.(); }
    catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  };
  return <section className="researcher-pause" aria-labelledby={`${id}-title`} data-reading-anchor={`researcher-pause:${run.run_id}:${request.request_id}:${request.revision}`}>
    <div className="section-heading"><h3 id={`${id}-title`}>Work waiting for your response</h3>{request.explanation_target && onDiscuss && <ActionButton action="ask" uiRole="research" aria-haspopup="dialog" onClick={() => onDiscuss({ ...request.explanation_target, label: request.question, statement: request.reason })}>Discuss</ActionButton>}</div>
    <div className="team-context-band">
      <p className="note">Research team · {humanLabel(request.member || request.responsible_role || "research_lead")} · {request.scope?.kind === "project" ? "Across models" : "This exact model"}</p>
      <ResearchDocument text={request.question} />{request.reason && <section><h4>Why it matters</h4><ResearchDocument text={request.reason} /></section>}
      {request.options?.length > 0 && <ResearchDocument text={request.options} />}
    </div>
    <form className="contribution-surface" onSubmit={save}><div className="field"><label htmlFor={id}>Your response</label><textarea id={id} rows={3} value={text} onChange={(event) => update(event.target.value)} disabled={busy} /></div><div className="btnrow"><ActionButton action="edit" uiRole="research" disabled={busy} onClick={() => update("I am not sure.", "unknown")}>I am not sure</ActionButton><ActionButton action="edit" uiRole="research" disabled={busy} onClick={() => update("No data yet.", "researcher_reported")}>No data yet</ActionButton>{request.scope?.kind === "project" && <label className="check-label"><input type="checkbox" checked={origin === "unknown"} disabled={busy} onChange={(event) => update(text, event.target.checked ? "unknown" : "researcher_reported")} />This remains unknown</label>}</div><p className="hint">Saving retains your words for this exact request{request.scope?.kind === "project" ? " and the shared understanding across models" : ""}. Continuing resumes the authorized stage with this saved answer and its recorded scope.</p><ActionButton action="save" uiRole="research" variant="primary" type="submit" disabled={busy || !dirty || !text.trim()}>{busy ? "Saving…" : "Save response"}</ActionButton></form>
    {changes.length > 0 && <><h4>Other context changed while work was paused</h4><ResearchDocument text={changes} /><label className="check-label"><input type="checkbox" checked={frozen} onChange={(event) => setFrozen(event.target.checked)} disabled={busy} />Continue with the frozen basis plus this response</label><p className="note">To change the model, scientific target, or authorized scope, prepare a new request.</p></>}
    <div className="btnrow"><ActionButton action="continue" uiRole="research" disabled={busy || dirty || !saved || Boolean(pause.continuation_blocked) || Boolean(changes.length && !frozen)} onClick={continueWork}>Continue work</ActionButton>{onPrepare && (pause.continuation_blocked || changes.length > 0) && <ActionButton action="repair" uiRole="research" disabled={busy} onClick={onPrepare}>Prepare further work</ActionButton>}</div>
    {pause.continuation_blocked && <ResearchDocument text={pause.continuation_blocked} />}
    {notice && <p className="note" role="status">{notice}</p>}{error && <p className="error" role="alert">{error}</p>}
    {[...(request.evidence_refs || []), ...(request.source_refs || [])].map((reference, index) => <div key={index}><QuestionSource reference={reference} onSource={onSource} /></div>)}
  </section>;
}
