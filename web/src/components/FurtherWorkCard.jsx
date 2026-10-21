import { phaseLabel } from "../research";
import React, { useEffect, useId, useRef, useState } from "react";
import { api } from "../api";
import { furtherWorkKey, issuesForPhase } from "../phaseWorkflow";
import { readConversationDraft, saveConversationDraft } from "../assumptionConversations";
import { ResearchDocument } from "./Shared";
import { ActionButton } from "./Visuals";
import LaunchRun from "./LaunchRun";

const titles = { P1: "Additional Runs and History", P2: "Additional Runs and History", P3: "Further theory development", P4: "Additional Runs and History", P5: "Next revision" };

// The draft includes the researcher's choices as well as prose. Saving the
// prose to the server must not discard locally selected work or exact sources.
export function rememberFurtherWorkDraft(key, previous, changes) {
  const next = { ...(previous || {}), ...changes };
  saveConversationDraft(key, next);
  return next;
}

function FurtherWork({ workflowRevision, readinessRevision, technicalReport, projectId, phase, branch, methodId, modelRef, methodLabel, suppliedMethod, selectedMethodRef, issues = [], recommendations, children, history, workDetails, status, preparedIssue, onPrepared, onStarted, disabled, activeRun, onNavigate, onSource, defaultOpen = false }) {
  const id = useId(); const key = furtherWorkKey(projectId, methodId || branch, phase);
  const cardRef = useRef(null);
  const initialOpen = useRef(defaultOpen);
  const cached = useRef(readConversationDraft(key));
  const [instructions, setInstructions] = useState(cached.current?.text || "");
  const [saved, setSaved] = useState(null); const [error, setError] = useState(null); const [retry, setRetry] = useState(0);
  const [saving, setSaving] = useState(false); const lock = useRef(false);
  const [focus, setFocus] = useState(cached.current?.focus === "alternatives" ? "alternatives" : methodId ? "selected" : "alternatives");
  const [selectedRefs, setSelectedRefs] = useState(Array.isArray(cached.current?.selectedRefs) ? cached.current.selectedRefs : []);
  const [mode, setMode] = useState(phase === "P2" ? "p2.full_catalog" : cached.current?.mode || "");
  const [experimentBudget, setExperimentBudget] = useState(cached.current?.experimentBudget ?? "");
  const [inputIds, setInputIds] = useState(Array.isArray(cached.current?.inputIds) ? cached.current.inputIds : []);
  const remember = (changes) => { cached.current = rememberFurtherWorkDraft(key, cached.current, changes); };
  useEffect(() => {
    let current = true;
    api.phasePreparation(projectId, methodId || branch, phase).then((value) => {
      if (current) { setSaved(value); setError(null); if (typeof cached.current?.text !== "string") setInstructions(value.instructions || ""); if (!Array.isArray(cached.current?.inputIds)) setInputIds(value.input_ids || []); }
    }).catch((failure) => { if (current) setError(`Saved instructions could not be loaded: ${failure.message}`); });
    return () => { current = false; };
  }, [projectId, methodId, branch, phase, retry]);
  useEffect(() => {
    if (!preparedIssue || !saved) return;
    const target = preparedIssue.explanation_target;
    const refs = target && !selectedRefs.some(ref => JSON.stringify(ref) === JSON.stringify(target)) ? [...selectedRefs, target] : selectedRefs;
    const direction = `Investigate this recorded issue: ${preparedIssue.question || preparedIssue.title || "Research question"}`;
    const text = instructions.includes(direction) ? instructions : [instructions, direction].filter(Boolean).join("\n\n");
    setSelectedRefs(refs); setInstructions(text); remember({ selectedRefs: refs, text });
    if (cardRef.current) cardRef.current.open = true;
    cardRef.current?.querySelector("textarea")?.focus();
    onPrepared?.();
  }, [preparedIssue, saved]);
  const update = (text) => { setInstructions(text); remember({ text }); };
  const chooseFocus = (value) => { setFocus(value); remember({ focus: value }); };
  const chooseMode = (value) => { setMode(value); remember({ mode: value }); };
  const changeBudget = (value) => { setExperimentBudget(value); remember({ experimentBudget: value }); };
  const changeInputs = (value) => { setInputIds(value); remember({ inputIds: value }); };
  const chooseReference = (target, checked) => {
    const refs = checked ? [...selectedRefs, target] : selectedRefs.filter((ref) => ref.object_id !== target.object_id || ref.sha256 !== target.sha256 || ref.family !== target.family || ref.generation_id !== target.generation_id || ref.entry_pointer !== target.entry_pointer);
    setSelectedRefs(refs); remember({ selectedRefs: refs });
  };
  const save = async () => {
    if (lock.current || !saved) return;
    lock.current = true; setSaving(true); setError(null);
    try {
      const value = await api.savePhasePreparation(projectId, methodId || branch, phase, { instructions, ...(phase === "P4" ? { input_ids: inputIds } : {}) });
      setSaved(value);
      // A newer edit made while the request was pending remains an unsaved draft.
      if (cached.current?.text === instructions) remember({ text: undefined });
    } catch (failure) { setError(failure.message); }
    finally { lock.current = false; setSaving(false); }
  };
  const available = issuesForPhase(issues, phase, branch, methodId, modelRef).filter((issue) => issue.explanation_target?.kind === "phase_issue");
  const earlierRefs = selectedRefs.filter((ref) => !available.some((issue) => {
    const target = issue.explanation_target;
    return ref.object_id === target.object_id && ref.sha256 === target.sha256 && ref.family === target.family && ref.generation_id === target.generation_id && ref.entry_pointer === target.entry_pointer;
  }));
  const contextRefs = selectedRefs;
  const unchanged = instructions === saved?.instructions && (phase !== "P4" || JSON.stringify(inputIds) === JSON.stringify(saved?.input_ids || []));
  const request = { technicalReport, phase, branch: ["P1", "P2"].includes(phase) ? "trunk" : branch, methodLabel,
    context_refs: contextRefs, supplied_method: phase === "P2" && (!methodId || focus === "selected") ? suppliedMethod : undefined };
  return <details ref={cardRef} open={initialOpen.current || undefined} id={["P1", "P2", "P5"].includes(phase) ? `${phase.toLowerCase()}-additional-work` : undefined} className="card further-work" data-card-role="action" data-reading-anchor="further-work" data-reading-pending={!saved && !error ? "true" : undefined}><summary className="card-heading"><h2>{titles[phase]}</h2>{status}</summary><div className="body">
    {methodLabel && <p className="note">Model: {methodLabel}</p>}
    {recommendations && <div className="further-work-recommendations"><ResearchDocument text={recommendations} /></div>}
    {children}
    {phase === "P2" && methodId && <fieldset><legend>What should guide the lead's proposal?</legend><label className="check-label"><input type="radio" name={`${id}-focus`} checked={focus === "selected"} onChange={() => chooseFocus("selected")} />Explore alternatives from this model</label><label className="check-label"><input type="radio" name={`${id}-focus`} checked={focus === "alternatives"} onChange={() => chooseFocus("alternatives")} />Explore new alternatives</label><p className="note">The lead receives the selected definition as a seed. The theorist and analyst propose independently. This starts a proposal and comparison run; it does not guarantee a revision of the selected model's identity.</p></fieldset>}
    {available.length > 0 && <details className="research-details"><summary>Choose sources to carry into this work</summary>{available.map((issue) => <label className="check-label" key={issue.issue_id}><input type="checkbox" checked={selectedRefs.some((ref) => ref.object_id === issue.explanation_target.object_id && ref.sha256 === issue.explanation_target.sha256 && ref.family === issue.explanation_target.family && ref.generation_id === issue.explanation_target.generation_id && ref.entry_pointer === issue.explanation_target.entry_pointer)} onChange={(event) => chooseReference(issue.explanation_target, event.target.checked)} />{issue.kind === "scientific_issue" ? "Scientific finding: " : issue.kind === "research_task" ? "Team task: " : issue.kind === "researcher_decision" ? "Researcher question: " : ""}{issue.title}</label>)}</details>}
    {error && <p className="error" role="alert">{error} {!saved && <ActionButton action="retry" onClick={() => setRetry((n) => n + 1)}>Retry</ActionButton>}</p>}
    {earlierRefs.length > 0 && <section className="context-note"><h3>Earlier issue sources selected</h3><p className="note">Your request still includes these earlier sources. They have not been replaced by the current questions.</p>{earlierRefs.map((ref, index) => <div className="btnrow" key={JSON.stringify(ref)}><span>Earlier source {index + 1}</span><ActionButton action="close" onClick={() => chooseReference(ref, false)}>Remove earlier source {index + 1}</ActionButton></div>)}</section>}
    {saved ? <LaunchRun workflowRevision={workflowRevision} readinessRevision={readinessRevision} projectId={projectId} request={request} embedded instructions={instructions} onInstructionsChange={update} mode={mode} onModeChange={chooseMode} experimentBudget={experimentBudget} onExperimentBudgetChange={changeBudget} inputIds={inputIds} onInputIdsChange={changeInputs} onStarted={onStarted} onSource={onSource} activeRun={activeRun} disabled={disabled || saving} beforeActions={<div className="btnrow save-instructions"><ActionButton action="save" uiRole="research" disabled={saving || unchanged} onClick={save}>{saving ? "Saving…" : phase === "P4" ? "Save instructions and inputs" : "Save instructions"}</ActionButton><span className="note">{unchanged ? "Instructions and selections saved for your next visit." : activeRun ? "Unsaved edits for the next run." : "Unsaved edits. Starting work uses the text shown here."} Saving does not start work.</span></div>} /> : !error && <p className="note" role="status">Loading your saved instructions…</p>}
    {onNavigate && <div className="btnrow further-work-navigation">{phase === "P1" && <ActionButton action="details" onClick={() => onNavigate("P2")}>Go to {phaseLabel("P2")}</ActionButton>}{phase === "P3" && <><ActionButton action="details" onClick={() => onNavigate("P2")}>Go to {phaseLabel("P2")}</ActionButton><ActionButton action="details" onClick={() => onNavigate("P4")}>Go to {phaseLabel("P4")}</ActionButton></>}{phase === "P4" && <><ActionButton action="details" onClick={() => onNavigate("P2")}>Go to {phaseLabel("P2")}</ActionButton><ActionButton action="details" onClick={() => onNavigate("P3")}>Go to {phaseLabel("P3")}</ActionButton></>}</div>}
    {workDetails}{history}
  </div></details>;
}

export default function FurtherWorkCard(props) {
  return <FurtherWork key={furtherWorkKey(props.projectId, props.methodId || props.branch, props.phase)} {...props} />;
}
