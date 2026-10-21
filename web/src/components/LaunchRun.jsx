import React, { useEffect, useId, useRef, useState } from "react";
import { api } from "../api";
import { freshId, hasExactRef, modeLabel, normalizeModes, phaseLabel } from "../research";
import { isEmpiricalTarget, modesForRequest, targetIsStale } from "../runRequests";
import { Dialog, ResearchDocument } from "./Shared";
import { ActionButton } from "./Visuals";
import PhaseTwoInstructions from "./PhaseTwoInstructions";
import { readinessMessages } from "../readinessContent";
import EmpiricalInputs from "./EmpiricalInputs";
import { readConversationDraft, saveConversationDraft } from "../assumptionConversations";

export default function LaunchRun({ projectId, request, workflowRevision, readinessRevision, currentTargetRef, onClose, onStarted, onSource, embedded = false, instructions: savedInstructions, onInstructionsChange, mode: savedMode, onModeChange, experimentBudget: savedExperimentBudget, onExperimentBudgetChange, inputIds: savedInputIds, onInputIdsChange, beforeActions, disabled = false, activeRun }) {
  const formId = useId();
  const reportWork = request.technicalReport !== false;
  const [readiness, setReadiness] = useState(null);
  const [localMode, setLocalMode] = useState(request.phase === "P2" ? "p2.full_catalog" : request.mode || "");
  const mode = savedMode ?? localMode;
  const setMode = onModeChange || setLocalMode;
  const [localInstructions, setLocalInstructions] = useState(request.instructions || "");
  const instructions = savedInstructions ?? localInstructions;
  const setInstructions = onInstructionsChange || setLocalInstructions;
  const [localExperimentBudget, setLocalExperimentBudget] = useState("");
  const experimentBudget = savedExperimentBudget ?? localExperimentBudget;
  const setExperimentBudget = onExperimentBudgetChange || setLocalExperimentBudget;
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState(false);
  const inputDraftKey = `p4-inputs:${JSON.stringify([projectId, request.branch])}`;
  const [localInputIds, setLocalInputIds] = useState(() => request.input_ids || readConversationDraft(inputDraftKey)?.inputIds || []);
  const inputIds = savedInputIds ?? localInputIds;
  const setInputIds = onInputIdsChange || setLocalInputIds;
  useEffect(() => { if (!embedded && request.phase === "P4") saveConversationDraft(inputDraftKey, { inputIds }); }, [inputDraftKey, inputIds, embedded, request.phase]);
  const [error, setError] = useState(null);
  const [retry, setRetry] = useState(0);
  const requestKey = useRef(freshId()); const lock = useRef(false);
  useEffect(() => {
    let active = true; setLoading(true); setError(null);
    api.readiness(projectId, request.branch, request.phase, mode || undefined)
      .then((data) => { if (active) { setReadiness(data); const available = normalizeModes(data).filter((item) => item.mode !== "p3.assessment"); if (!mode && available.length === 1) setMode(available[0].mode); } })
      .catch((e) => { if (active) { setReadiness(null); setError(e.message); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [projectId, request.branch, request.phase, mode, retry, workflowRevision, readinessRevision]);
  const modes = normalizeModes(readiness);
  const selected = modes.find((m) => m.mode === mode);
  const targeted = Boolean(request.target);
  const empirical = isEmpiricalTarget(request.target);
  const stale = targetIsStale(request, currentTargetRef);
  const exact = !targeted || hasExactRef(request.target);
  const progressive = request.phase === "P4" && selected?.progressive_evaluation;
  const budgetSeconds = experimentBudget === "" ? selected?.budget_seconds || 600 : Number(experimentBudget);
  const invalidBudget = progressive && (!Number.isFinite(budgetSeconds) || budgetSeconds <= 0);
  const invalidInputs = request.phase === "P4" && inputIds.length > 0 && selected?.local_inputs !== true;
  const blocked = disabled || Boolean(activeRun);
  const activeLabel = activeRun?.state === "awaiting_user" ? "Current work is waiting for your direction"
    : activeRun?.state === "stopping" ? "Current work is stopping" : "Work already in progress";
  const start = async (event) => {
    event.preventDefault(); if (blocked || importing || lock.current || loading || !selected?.ready || !exact || stale || invalidBudget || invalidInputs) return;
    lock.current = true; setBusy(true); setError(null);
    try {
      const run = await api.startRun(projectId, {
        phase: request.phase, branch_id: request.branch, mode,
        intent: mode === "p3.assessment" ? "assessment" : "run",
        target: request.target || undefined,
        assessment_id: request.assessment_id || undefined,
        supplied_method: request.phase === "P2" ? request.supplied_method : undefined,
        context_refs: request.context_refs?.length ? request.context_refs : undefined,
        budget_seconds: progressive ? budgetSeconds : undefined,
        input_ids: request.phase === "P4" ? inputIds : undefined,
        basis_sha256: selected.basis?.sha256 || readiness?.basis?.sha256 || "",
        instructions: instructions.trim() ? instructions : undefined, idempotency_key: requestKey.current,
      });
      requestKey.current = freshId(); setRetry((value) => value + 1);
      onStarted(run);
    } catch (e) {
      setReadiness(null);
      setError(e.message?.includes("basis is stale") ? "Research inputs changed after this form was opened. Refresh the inputs, then start again. Your instructions are kept." : e.message);
    } finally { lock.current = false; setBusy(false); }
  };
  const form = <form onSubmit={start} data-reading-pending={loading ? "true" : undefined}>
      {(!embedded || !request.methodLabel || targeted) && <p className="note">{request.methodLabel || (request.phase === "P1" ? "The shared research question" : "Selected method")}{targeted && <> · {empirical ? "Selected question" : "Selected component"}: <b>{request.targetLabel || request.target.object_id}</b></>}</p>}
      {selected?.basis?.project?.research_instructions?.trim() && <details className="research-details contribution-surface"><summary>Project instructions for this run</summary><ResearchDocument text={selected.basis.project.research_instructions} /></details>}
      {empirical ? <div className="context-note"><p>This request revisits the exact evaluation you inspected. The new check will use the current model and theory.</p>{request.caseLabels?.length > 0 && <p><b>Cases in focus:</b> {request.caseLabels.join(", ")}</p>}{request.theoryContext?.message && <p>{request.theoryContext.message}</p>}</div> : targeted && <p className="context-note">This request refers to the theory you inspected. An assessment saves a separate account. A theory revision can change the selected component and its affected consequences, followed by specialist audit and lead integration.</p>}
      {request.assessment && <details className="research-details"><summary>Saved assessment informing this revision</summary><ResearchDocument text={request.assessment.assessment_markdown || request.assessment.summary} /><p className="note">Its full findings, options, limitations, and discussion will accompany this revision request.</p></details>}
      {stale && <p className="error" role="alert">This component has a newer published version. Close this request and inspect the updated theory before continuing.</p>}
      {!exact && <p className="error" role="alert">{empirical ? "This question has no exact evaluation reference. Reopen an evaluation with a verified protocol before requesting a check." : "This component has no exact theory source reference. A linked theory generation is required before work on this component can be requested."}</p>}
      {request.phase !== "P2" && <fieldset disabled={busy || loading}><legend>Choose the work</legend>
        {modesForRequest(request, modes).map((m) => <label className="mode-option" key={m.mode}>
          <input type="radio" name={`${formId}-mode`} value={m.mode} checked={mode === m.mode} onChange={() => setMode(m.mode)} />
          <span><b>{modeLabel(m.mode)}</b>{m.purpose && <span className="mode-purpose">{m.purpose}</span>}{!m.ready && <span className="note">{readinessMessages(m.reasons).join(" ")}</span>}</span>
        </label>)}
      </fieldset>}
      {loading && <p className="note" role="status">Checking available work and its inputs…</p>}
      {!loading && !modes.length && <p className="note">No work modes are available for this phase.</p>}
      {!loading && selected && !selected.ready && <><p className="note warn">{readinessMessages(selected.reasons).join(" ") || "The required inputs are not ready."}</p>{selected.reasons?.length > 0 && <details className="research-details"><summary>Readiness details</summary><ul>{selected.reasons.map((reason, index) => <li key={index}>{typeof reason === "string" ? reason : reason.message || reason.code}</li>)}</ul></details>}</>}
      {request.phase === "P2" ? <PhaseTwoInstructions id={`${formId}-instructions`} value={instructions} onChange={setInstructions} disabled={busy} suppliedMethod={request.supplied_method} onSource={onSource} /> : <div className="field contribution-surface"><label htmlFor={`${formId}-instructions`}>{request.phase === "P5" ? mode === "p5.review_revision" ? "Review and revision focus" : "Assembly instructions" : "Your instruction"}</label><textarea id={`${formId}-instructions`} aria-describedby={request.phase === "P5" ? `${formId}-recipients` : undefined} rows={4} value={instructions} onChange={(e) => setInstructions(e.target.value)} disabled={busy} placeholder={targeted ? "What would you like the team to examine or change?" : "Describe the question, focus, or revision you want."} />{request.phase === "P5" && <p className="hint" id={`${formId}-recipients`}>{mode === "p5.review_revision" ? reportWork ? "The producing reviewers and revision lead receive this focus with the exact report. The independent reviewer receives only the frozen report, declared supplements, and review directions." : "The reviewers receive these directions with the frozen historical manuscript." : reportWork ? "The Research Lead receives these instructions to assemble the technical report from exact retained sources. Missing work remains explicit in an interim report." : "The Research Lead receives these instructions to assemble a manuscript under the pinned legacy workflow."}</p>}</div>}
      {progressive && <div className="field"><label htmlFor={`${formId}-budget`}>Experiment budget (seconds)</label><input id={`${formId}-budget`} type="number" min="1" step="1" value={experimentBudget} placeholder={String(selected?.budget_seconds || 600)} onChange={(event) => setExperimentBudget(event.target.value)} disabled={busy} aria-describedby={`${formId}-budget-help`} /><p id={`${formId}-budget-help`} className="note">Maximum managed experiment time, across all batches. Model discussion and waiting for your direction are separate. The analyst pauses when the budget runs out.</p>{invalidBudget && <p className="error" role="alert">Enter a positive number of seconds.</p>}</div>}
      {request.phase === "P4" && selected?.local_inputs === true && <EmpiricalInputs projectId={projectId} selected={inputIds} onChange={setInputIds} disabled={busy} onBusyChange={setImporting} />}
      {request.phase === "P4" && selected && selected.local_inputs !== true && <p className="note">Adopt the revised Phase 4 workflow to supply local data, code or configuration files.{invalidInputs && <> This draft still has {inputIds.length} selected {inputIds.length === 1 ? "input" : "inputs"}. <ActionButton action="close" disabled={busy} onClick={() => setInputIds([])}>Clear selected inputs</ActionButton></>}</p>}
      {targeted && <details><summary className="note">Target source</summary><pre className="record">{JSON.stringify(request.target, null, 2)}</pre></details>}
      {error && <p className="error" role="alert">{error} {!readiness && <ActionButton action="retry" onClick={() => setRetry((n) => n + 1)}>Refresh research inputs</ActionButton>}</p>}
      {beforeActions}
      {activeRun && <p className="note" role="status">{activeLabel}. Finish or cancel it before starting more work in this phase. You can prepare instructions for the next run.</p>}
      <div className="btnrow"><ActionButton uiRole="research" action={mode === "p3.assessment" ? "check" : targeted && !empirical ? "repair" : "run"} variant="primary" type="submit" disabled={blocked || busy || importing || loading || !selected?.ready || !exact || stale || invalidBudget || invalidInputs}>{busy ? "Starting…" : activeRun ? activeLabel : request.phase === "P4" && mode ? `Start ${modeLabel(mode).toLowerCase()}` : mode === "p3.assessment" ? "Request assessment" : targeted && !empirical ? "Request a theory revision" : ({ P1: "Start literature study", P2: "Propose methods", P3: "Start theory development", P5: mode === "p5.review_revision" ? "Request review and revision" : reportWork ? "Assemble technical report" : "Start manuscript work" }[request.phase] || "Start research")}</ActionButton>{!embedded && <ActionButton action="close" disabled={busy || importing} onClick={onClose}>Cancel</ActionButton>}</div>
    </form>;
  return embedded ? form : <Dialog title={request.title || `Prepare ${phaseLabel(request.phase)}`} returnFocus={request.returnFocus} busy={busy || importing} onClose={() => { if (!busy && !importing) onClose(); }}>{form}</Dialog>;
}
