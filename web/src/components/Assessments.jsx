import React, { useRef, useState } from "react";
import { api } from "../api";
import { freshId, humanLabel } from "../research";
import { ResearchDocument, RunState, SourceRef } from "./Shared";
import { ActionButton } from "./Visuals";
import { isTheoryComponentTarget, theoryComponentRequest } from "../runRequests";

export function assessmentRepairRequest(assessment) {
  const request = theoryComponentRequest("revision", assessment.target, humanLabel(assessment.target?.object_id));
  return request && { ...request, assessment_id: assessment.assessment_id, assessment, instructions: `${request.instructions}\n\nConsider this saved focused assessment when revising the selected component. Account for its findings, limitations, options, and discussion.\n\n${assessment.summary || ""}` };
}

function Assessment({ projectId, assessment, onStarted, onRepair, onSource }) {
  const [note, setNote] = useState(""); const [error, setError] = useState(null); const [busy, setBusy] = useState(false);
  const key = useRef(freshId()); const lock = useRef(false);
  const options = assessment.options?.length ? assessment.options : assessment.suggested_actions || [];
  const followUp = async (event) => {
    event.preventDefault(); if (lock.current || !note.trim()) return;
    lock.current = true; setBusy(true); setError(null);
    try {
      const run = await api.assessmentMessage(projectId, assessment.assessment_id, { instructions: note, idempotency_key: key.current });
      key.current = freshId(); setNote(""); onStarted(run);
    } catch (e) { setError(e.message); } finally { lock.current = false; setBusy(false); }
  };
  return <details className="assessment" open={undefined}>
    <summary><b>{assessment.title || humanLabel(assessment.target?.object_id || "Focused assessment")}</b> <RunState state={assessment.state || "assessed"} /> <span className="note">{(assessment.updated_at || assessment.created_at || "").slice(0, 16).replace("T", " ")}</span></summary>
    <div className="assessment-body">
      {assessment.summary && <ResearchDocument text={assessment.summary} />}
      {(assessment.findings || []).length > 0 && <div className="assessment-findings">{assessment.findings.map((f, i) => <ResearchDocument key={i} text={typeof f === "string" ? f : f.message || f.summary || f} />)}</div>}
      {(assessment.limitations || []).length > 0 && <section><h3>What was not checked</h3><ul>{assessment.limitations.map((limit, i) => <li key={i}><ResearchDocument text={limit} /></li>)}</ul></section>}
      {options.length > 0 && <section><h3>Possible next steps</h3><ul>{options.map((option, i) => <li key={i}><ResearchDocument text={typeof option === "string" ? option : [option.label || option.title, option.description || option.consequence || option.rationale].filter(Boolean).join("\n\n") || option} /></li>)}</ul><p className="note">These are options for your consideration. Request further work when you choose a direction.</p></section>}
      <details className="research-details"><summary>Assessed component and evidence sources</summary>{assessment.target && <div><b className="note">Assessed component</b><SourceRef reference={assessment.target} onOpen={onSource} /></div>}{(assessment.evidence_refs || []).map((item, i) => { const ref = item.generation_ref || item; const source = ref.branch && ref.phase ? ref : ref.family === assessment.target?.family && ref.generation_id === assessment.target?.generation_id ? { ...assessment.target, ...ref } : null; return <div key={i}><span className="note">{humanLabel(ref.family)}{ref.object_id && ` · ${humanLabel(ref.object_id)}`} </span>{source ? <SourceRef reference={source} onOpen={onSource} /> : <span className="note">{item.source_error || `Generation ${ref.generation_id}: complete source linkage is not available.`}</span>}</div>; })}</details>
      {(assessment.messages || []).map((message, i) => <div className={`discussion-message ${message.role === "user" || message.role === "researcher" ? "researcher" : ""}`} key={message.message_id || i}><b className="note">{message.role === "user" || message.role === "researcher" ? "You" : humanLabel(message.role || "Team")}</b><ResearchDocument text={message.content || message.instructions || ""} /></div>)}
      <form className="contribution-surface" onSubmit={followUp}><div className="field"><label htmlFor={`followup-${assessment.assessment_id}`}>Continue this assessment</label><textarea id={`followup-${assessment.assessment_id}`} rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ask a follow-up or suggest a different angle." disabled={busy} /></div>
        {error && <p role="alert" className="error">{error}</p>}
        <div className="btnrow"><ActionButton action="ask" uiRole="research" variant="primary" type="submit" disabled={busy || !note.trim()}>{busy ? "Sending…" : "Ask follow-up"}</ActionButton>{assessment.target && onRepair && <ActionButton action="repair" uiRole="research" disabled={busy || !isTheoryComponentTarget(assessment.target)} onClick={event => onRepair(assessment, event.currentTarget)}>Prepare theory revision</ActionButton>}</div>
        {assessment.target && onRepair && !isTheoryComponentTarget(assessment.target) && <p className="note">The assessed component's exact theory source is unavailable. Inspect a linked theory component before requesting a revision.</p>}
      </form>
    </div>
  </details>;
}

export default function Assessments({ projectId, assessments = [], selectedNode, onStarted, onRepair, onSource, embedded = false }) {
  const [all, setAll] = useState(false);
  const focused = assessments.filter((assessment) => !["explanation", "issue_explanation", "project_context", "model_dialogue", "issue_suggestions"].includes(assessment.assessment_purpose));
  const shown = selectedNode && !all ? focused.filter((a) => a.target?.object_id === selectedNode) : focused;
  if (!focused.length) return null;
  return <section className={embedded ? "focused-assessments" : "card"} data-card-role={embedded ? undefined : "research"}>{embedded ? <h3>Focused assessments</h3> : <h2>Focused assessments</h2>}<div className="body">
    <p className="note">Each assessment checks its recorded theory source and keeps its own status and discussion. It does not change the published theory.</p>
    {selectedNode && <label className="check-label"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} />Show assessments of other components</label>}
    {shown.map((a) => <Assessment key={a.assessment_id} projectId={projectId} assessment={a} onStarted={onStarted} onRepair={onRepair} onSource={onSource} />)}
    {!shown.length && <p className="note">No saved assessments for this component yet.</p>}
  </div></section>;
}
