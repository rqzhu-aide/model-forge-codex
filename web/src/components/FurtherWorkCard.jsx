import { freshId, phaseLabel } from "../research";
import React, { useCallback, useEffect, useId, useRef, useState } from "react";
import { api } from "../api";
import { furtherWorkKey, issuesForPhase } from "../phaseWorkflow";
import { readConversationDraft, saveConversationDraft, subscribeConversationDrafts } from "../assumptionConversations";
import { ResearchDocument, SourceRef } from "./Shared";
import { ActionButton } from "./Visuals";
import LaunchRun from "./LaunchRun";
import PhaseInputSummary from "./PhaseInputSummary";
import { phaseInputScopeKey } from "../phaseInputSummary";

// The draft includes the researcher's choices as well as prose. Saving the
// prose to the server must not discard locally selected work or exact sources.
export function rememberFurtherWorkDraft(key, previous, changes) {
  const next = { ...(previous || {}), ...changes };
  saveConversationDraft(key, next);
  return next;
}

function FurtherWork({ workflowRevision, readinessRevision, technicalReport, projectId, phase, branch, methodId, modelRef, methodLabel, suppliedMethod, selectedMethodRef, issues = [], summaryContext, recommendations, children, history, workDetails, status, preparedIssue, preparedTheory, currentTheoryRef, currentTheoryAligned, onPrepared, onStarted, disabled, activeRun, onNavigate, onSource, defaultOpen = false, hasRun = false, setupProject, onTeamSettings, onOpenAIAccount }) {
  const id = useId(); const key = furtherWorkKey(projectId, methodId || branch, phase);
  const cardRef = useRef(null);
  const initialOpen = useRef(!hasRun || defaultOpen);
  const cached = useRef(readConversationDraft(key));
  const [instructions, setInstructions] = useState(cached.current?.text || "");
  const [saved, setSaved] = useState(null); const [error, setError] = useState(null); const [retry, setRetry] = useState(0);
  const [saving, setSaving] = useState(false); const lock = useRef(false);
  const [focus, setFocus] = useState(cached.current?.focus === "alternatives" ? "alternatives" : methodId ? "selected" : "alternatives");
  const [selectedRefs, setSelectedRefs] = useState(Array.isArray(cached.current?.selectedRefs) ? cached.current.selectedRefs : []);
  const [mode, setMode] = useState(phase === "P2" ? "p2.full_catalog" : cached.current?.mode || "");
  const [experimentBudget, setExperimentBudget] = useState(cached.current?.experimentBudget ?? "");
  const [inputIds, setInputIds] = useState(Array.isArray(cached.current?.inputIds) ? cached.current.inputIds : []);
  const [theoryPreparation, setTheoryPreparation] = useState(phase === "P3" ? cached.current?.theoryPreparation || null : null);
  const [navigationRequest, setNavigationRequest] = useState(null);
  const [preparationStatus, setPreparationStatus] = useState(null);
  const reportPreparationStatus = useCallback(value => setPreparationStatus(previous => JSON.stringify(previous) === JSON.stringify(value) ? previous : value), []);
  const remember = (changes) => { cached.current = rememberFurtherWorkDraft(key, cached.current, changes); };
  useEffect(() => phase === "P3" ? subscribeConversationDrafts(changedKey => {
    if (changedKey !== key) return;
    const latest = readConversationDraft(key); cached.current = latest;
    const next = latest?.theoryPreparation || null;
    // Completion can arrive through the editor that submitted before a phase
    // return. Keep this mounted view in sync with that consumed request only.
    setTheoryPreparation(current => current?.revision === next?.revision ? current : next);
  }) : undefined, [key, phase]);
  useEffect(() => {
    let current = true;
    api.phasePreparation(projectId, methodId || branch, phase).then((value) => {
      if (current) { setSaved(value); setError(null); if (typeof cached.current?.text !== "string") setInstructions(value.instructions || ""); if (!Array.isArray(cached.current?.inputIds)) setInputIds(value.input_ids || []); }
    }).catch((failure) => { if (current) setError(`Saved instructions could not be loaded: ${failure.message}`); });
    return () => { current = false; };
  }, [projectId, methodId, branch, phase, retry]);
  useEffect(() => {
    if (!preparedIssue || !saved) return;
    const issue = preparedIssue.issue || preparedIssue;
    const target = issue.explanation_target;
    const refs = target && !selectedRefs.some(ref => JSON.stringify(ref) === JSON.stringify(target)) ? [...selectedRefs, target] : selectedRefs;
    const direction = `Investigate this recorded issue: ${issue.question || issue.title || "Research question"}`;
    const text = instructions.includes(direction) ? instructions : [instructions, direction].filter(Boolean).join("\n\n");
    setSelectedRefs(refs); setInstructions(text); remember({ selectedRefs: refs, text });
    if (preparedIssue.origin) setNavigationRequest({ origin: preparedIssue.origin, returnLabel: preparedIssue.returnLabel || "Back to research question" });
    else {
      if (cardRef.current) cardRef.current.open = true;
      cardRef.current?.querySelector("textarea")?.focus();
    }
    onPrepared?.();
  }, [preparedIssue, saved]);
  useEffect(() => {
    if (phase !== "P3" || !preparedTheory || !saved) return;
    if (preparedTheory.request?.target) {
      const { target, targetLabel, instructions: preparedDirections, assessment_id, assessment } = preparedTheory.request;
      const next = { target: structuredClone(target), targetLabel, preparedDirections, assessment_id, assessment,
        methodRef: structuredClone(preparedTheory.modelRef || null), revision: freshId() };
      setTheoryPreparation(next); setMode("p3.theory_revision"); remember({ theoryPreparation: next, mode: "p3.theory_revision" });
    }
    if (preparedTheory.issue) {
      const issue = preparedTheory.issue; const target = issue.explanation_target;
      const refs = target && !selectedRefs.some(ref => JSON.stringify(ref) === JSON.stringify(target)) ? [...selectedRefs, target] : selectedRefs;
      const direction = `Investigate this recorded issue: ${issue.question || issue.title || "Research question"}`;
      const text = instructions.includes(direction) ? instructions : [instructions, direction].filter(Boolean).join("\n\n");
      setSelectedRefs(refs); setInstructions(text); remember({ selectedRefs: refs, text });
    }
    // This is an explicit preparation action. Background readiness refreshes do
    // not replay it or move focus. The summary owns the shared Back session.
    if (preparedTheory.origin) setNavigationRequest({ origin: preparedTheory.origin, returnLabel: preparedTheory.returnLabel || "Back to theory" });
    else if (cardRef.current) cardRef.current.open = true;
    onPrepared?.();
  }, [preparedTheory, Boolean(saved)]);
  const update = (text) => { setInstructions(text); remember({ text }); };
  const chooseFocus = (value) => { setFocus(value); remember({ focus: value }); };
  const chooseMode = (value) => { setMode(value); remember({ mode: value }); };
  const changeBudget = (value) => { setExperimentBudget(value); remember({ experimentBudget: value }); };
  const changeInputs = (value) => { setInputIds(value); remember({ inputIds: value }); };
  const clearTheoryFocus = () => { setTheoryPreparation(null); remember({ theoryPreparation: null }); };
  const started = (run) => {
    // A second preparation made while launch was pending belongs to the next
    // run, including in a newly mounted editor after navigation. Merge into the
    // latest browser draft so an old callback cannot overwrite newer edits.
    const latest = readConversationDraft(key);
    if (theoryPreparation && latest?.theoryPreparation?.revision === theoryPreparation.revision) {
      cached.current = rememberFurtherWorkDraft(key, latest, { theoryPreparation: null });
      setTheoryPreparation(current => current?.revision === theoryPreparation.revision ? null : current);
    }
    onStarted?.(run);
  };
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
      const latest = readConversationDraft(key);
      if (latest?.text === instructions) cached.current = rememberFurtherWorkDraft(key, latest, { text: undefined });
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
    context_refs: contextRefs, supplied_method: phase === "P2" && (!methodId || focus === "selected") ? suppliedMethod : undefined,
    ...(phase === "P3" && theoryPreparation ? theoryPreparation : {}) };
  return <><PhaseInputSummary showSummary={hasRun} status={status} navigationRequest={navigationRequest} context={summaryContext || { projectId, phase, branch, methodId, modelRef, issues }} phase={phase} scope={JSON.stringify([key, phaseInputScopeKey(summaryContext || { phase, branch, methodId, modelRef })])} activeRun={activeRun} preparationStatus={preparationStatus} preparation={{ loaded: Boolean(saved), error: Boolean(error), hasInstructions: Boolean(instructions.trim()), instructionsChanged: Boolean(saved && instructions !== (saved.instructions || "")), inputCount: inputIds.length, inputsChanged: Boolean(saved && JSON.stringify(inputIds) !== JSON.stringify(saved.input_ids || [])) }}>
  <details ref={cardRef} open={initialOpen.current || undefined} id={["P1", "P2", "P5"].includes(phase) ? `${phase.toLowerCase()}-additional-work` : undefined} className="further-work" data-reading-anchor="further-work" data-reading-pending={!saved && !error ? "true" : undefined}><summary hidden={!hasRun}>Edit instructions and settings</summary><div className="body">
    {methodLabel && <p className="note">Model: {methodLabel}</p>}
    {phase === "P3" && <div className="context-note" data-reading-anchor="theory-preparation-focus"><p><b>Theory focus:</b> {theoryPreparation ? <>{theoryPreparation.targetLabel || theoryPreparation.target?.object_id}{theoryPreparation.methodRef?.version != null && <> · Model version {theoryPreparation.methodRef.version}</>}</> : "Whole theory"}</p>{theoryPreparation && <><div className="btnrow"><SourceRef reference={theoryPreparation.target} onOpen={onSource} label="Inspected theory source" /><ActionButton action="close" disabled={saving} onClick={clearTheoryFocus}>Clear theory focus</ActionButton></div><p className="note">The revision includes this component and its affected consequences, and publishes a complete theory account.</p></>}</div>}
    {recommendations && <details className="research-details further-work-recommendations"><summary>Team recommendations</summary><ResearchDocument text={recommendations} /></details>}
    {children}
    {phase === "P2" && methodId && <fieldset><legend>What should guide the lead's proposal?</legend><label className="check-label"><input type="radio" name={`${id}-focus`} checked={focus === "selected"} onChange={() => chooseFocus("selected")} />Explore alternatives from this model</label><label className="check-label"><input type="radio" name={`${id}-focus`} checked={focus === "alternatives"} onChange={() => chooseFocus("alternatives")} />Explore new alternatives</label><p className="note">The lead receives the selected definition as a seed. The theorist and analyst propose independently. This starts a proposal and comparison run; it does not guarantee a revision of the selected model's identity.</p></fieldset>}
    {available.length > 0 && <details className="research-details"><summary>Choose sources to carry into this work</summary>{available.map((issue) => <label className="check-label" key={issue.issue_id}><input type="checkbox" checked={selectedRefs.some((ref) => ref.object_id === issue.explanation_target.object_id && ref.sha256 === issue.explanation_target.sha256 && ref.family === issue.explanation_target.family && ref.generation_id === issue.explanation_target.generation_id && ref.entry_pointer === issue.explanation_target.entry_pointer)} onChange={(event) => chooseReference(issue.explanation_target, event.target.checked)} />{issue.kind === "scientific_issue" ? "Scientific finding: " : issue.kind === "research_task" ? "Team task: " : issue.kind === "researcher_decision" ? "Researcher question: " : ""}{issue.title}</label>)}</details>}
    {error && <p className="error" role="alert">{error} {!saved && <ActionButton action="retry" onClick={() => setRetry((n) => n + 1)}>Retry</ActionButton>}</p>}
    {earlierRefs.length > 0 && <section className="context-note"><h3>Additional selected issue sources</h3><p className="note">These selected sources remain attached to your request.</p>{earlierRefs.map((ref, index) => <div className="btnrow" key={JSON.stringify(ref)}><span>Selected source {index + 1}</span><ActionButton action="close" onClick={() => chooseReference(ref, false)}>Remove selected source {index + 1}</ActionButton></div>)}</section>}
    {saved ? <LaunchRun setupProject={setupProject} onTeamSettings={onTeamSettings} onOpenAIAccount={onOpenAIAccount} onPreparationStatus={reportPreparationStatus} workflowRevision={workflowRevision} readinessRevision={readinessRevision} projectId={projectId} request={request} currentTargetRef={currentTheoryRef} currentMethodRef={phase === "P3" ? modelRef : undefined} currentTheoryAligned={currentTheoryAligned} embedded instructions={instructions} onInstructionsChange={update} mode={mode} onModeChange={chooseMode} experimentBudget={experimentBudget} onExperimentBudgetChange={changeBudget} inputIds={inputIds} onInputIdsChange={changeInputs} onStarted={started} onSource={onSource} activeRun={activeRun} disabled={disabled || saving} beforeActions={<div className="btnrow save-instructions"><ActionButton action="save" uiRole="research" disabled={saving || unchanged} onClick={save}>{saving ? "Saving…" : phase === "P4" ? "Save instructions and inputs" : "Save instructions"}</ActionButton><span className="note">{unchanged ? "Instructions and selections saved for your next visit." : activeRun ? "Unsaved edits for the next run." : "Unsaved edits. Starting work uses the text shown here."} Saving does not start work.</span></div>} /> : !error && <p className="note" role="status">Loading your saved instructions…</p>}
    {onNavigate && <div className="btnrow further-work-navigation">{phase === "P1" && <ActionButton action="details" onClick={() => onNavigate("P2")}>Go to {phaseLabel("P2")}</ActionButton>}{phase === "P3" && <><ActionButton action="details" onClick={() => onNavigate("P2")}>Go to {phaseLabel("P2")}</ActionButton><ActionButton action="details" onClick={() => onNavigate("P4")}>Go to {phaseLabel("P4")}</ActionButton></>}{phase === "P4" && <><ActionButton action="details" onClick={() => onNavigate("P2")}>Go to {phaseLabel("P2")}</ActionButton><ActionButton action="details" onClick={() => onNavigate("P3")}>Go to {phaseLabel("P3")}</ActionButton></>}</div>}
  </div></details></PhaseInputSummary>
  {workDetails}{history}</>;
}

export default function FurtherWorkCard(props) {
  return <FurtherWork key={furtherWorkKey(props.projectId, props.methodId || props.branch, props.phase)} {...props} />;
}
