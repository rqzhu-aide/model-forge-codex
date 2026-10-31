import React, { useId, useRef, useState } from "react";
import { api } from "../api";
import { humanLabel, modeLabel } from "../research";
import { clarificationDraftKey, correctionsForScope, earlierSettingQuestions, requestSourceReferences, requestsForScope, researcherDecisionCards, savedClarificationsForScope } from "../contextualRequests";
import { ResearchDocument, RunState, SourceRef } from "./Shared";
import { CitedRequestDocument } from "./LiteratureCitation";
import { methodAnswers, methodRequests } from "../methodWorkspace";
import { ActionButton } from "./Visuals";
import { decisionDraft, decisionOptions, decisionSubmission, decisionSupportSections } from "../researcherDecisions";
import { DecisionBrief, decisionResponseFields } from "./DecisionResponse";
import { readConversationDraft, saveConversationDraft } from "../assumptionConversations";
import { issueSourceIdentity } from "../phaseWorkflow";

const memberName = (role) => ({ research_lead: "Research Lead", theorist: "Theorist", data_analyst: "Data Analyst", outside_reviewer: "Outside Reviewer" }[role] || humanLabel(role));
const itemKey = (item) => item.attention_version_id || item.attention_id;

function RequestSources({ item, onSource }) {
  const references = requestSourceReferences(item);
  return references.length > 0 ? <div className="btnrow request-sources">{references.map(({ label, reference }, i) => <SourceRef key={i} label={label} reference={reference} onOpen={onSource} />)}</div> : null;
}

function RequestContext({ item, branch, onSource }) {
  const methodScoped = item.phase === "P2" && item.affected_record_ids?.length > 0;
  const shared = (item.branch || item.branch_id) === "trunk" && branch !== "trunk" && !methodScoped;
  return <>
    <p className="note request-attribution">{item.raised_by && `Raised by ${memberName(item.raised_by)}`}{shared && " · Shared project question"}{methodScoped && " · Method-specific request"}</p>
    {item.context_markdown && <div className="request-context"><h4>Mathematical context</h4><CitedRequestDocument item={item} text={item.context_markdown} onSource={onSource} /></div>}
    {item.likely_consequence && <div className="request-consequence"><h4>Why it matters</h4><CitedRequestDocument item={item} text={item.likely_consequence} section="consequence" onSource={onSource} /></div>}
    <RequestSources item={item} onSource={onSource} />
  </>;
}

export function ResearcherDecision({ item, answer, projectId, branch, number, first, onSaved, onSource, headingLevel = 3, expanded = false, draftStore }) {
  const id = useId(); const lock = useRef(false);
  const draftKey = clarificationDraftKey(projectId, item);
  const cached = useRef(draftStore?.get(draftKey) || readConversationDraft(`decision-response:${draftKey}`));
  const initial = decisionDraft(item, answer, cached.current);
  const [note, setNote] = useState(initial.note); const [origin, setOrigin] = useState(initial.origin); const [choice, setChoice] = useState(initial.choice); const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null); const [editing, setEditing] = useState(() => Boolean(cached.current?.editing));
  const editButton = useRef(null); const instructionInput = useRef(null);
  const [saved, setSaved] = useState(false);
  const updateDraft = (text, edit = editing, nextOrigin = origin, nextChoice = choice) => {
    setNote(text); setEditing(edit); setOrigin(nextOrigin); setChoice(nextChoice);
    const draft = { note: text, editing: edit, origin: nextOrigin, choice: nextChoice, ...(nextChoice.startsWith("option:") ? { selection: { option_id: nextChoice.slice(7) } } : {}) };
    draftStore?.set(draftKey, draft); saveConversationDraft(`decision-response:${draftKey}`, draft);
  };
  const clearDraft = () => { draftStore?.delete(draftKey); saveConversationDraft(`decision-response:${draftKey}`, null); setNote(""); setEditing(false); };
  const submission = decisionSubmission(item, { note, origin, choice });
  const hasChoices = decisionOptions(item).length > 0;
  const source = item.explanation_target || issueSourceIdentity(item);
  const methodScoped = item.phase === "P2" && item.affected_record_ids?.length > 0;
  const delivery = methodScoped ? "Your clarification follows only the named model branches into subsequent work. New Phase 2 proposal runs give it only to the Research Lead."
    : item.target_phase === "P1"
    ? "New runs give this shared-setting clarification to all team members."
    : item.target_phase === "P2"
      ? "During Phase 2, new runs give this clarification only to the Research Lead."
      : "New runs receive your clarification.";
  const resolve = async (event) => {
    event.preventDefault();
    if (lock.current || !submission || (submission.selection && !source)) return;
    lock.current = true; setBusy(true); setError(null); setSaved(false);
    try {
      const result = await api.resolveAttention(projectId, item.attention_id, submission.note, {
        ...(source ? { expected_source: source } : {}), expected_revision: answer?.revision || 0,
        ...((item.response_kind || item.scope || submission.origin === "unknown") ? { origin: submission.origin } : {}),
        ...(item.scope?.kind === "project" ? { save_to_context: true } : {}),
        ...(submission.selection ? { selection: submission.selection } : {}),
      });
      onSaved(result.answer || { attention_id: item.attention_id, attention: item, note: submission.note, resolved_at: new Date().toISOString() });
      clearDraft(); setSaved(true);
      globalThis.requestAnimationFrame?.(() => editButton.current?.querySelector("button")?.focus({ preventScroll: true }));
    } catch (e) { setError(e.message); }
    finally { lock.current = false; setBusy(false); }
  };
  return <article className="researcher-decision" data-card-role={answer ? "history" : "attention"} aria-labelledby={`${id}-question`}>
    <div className="request-question" id={`${id}-question`} role="heading" aria-level={headingLevel}><span className="question-number">Question {number}:</span><ResearchDocument text={item.question} /></div>
    <div className="decision-content">
      <div className="decision-context"><DecisionBrief item={item} onSource={onSource} recommendationId={`${id}-recommendation`} /></div>
      <details className="research-details decision-context"><summary>Context and sources</summary><p className="note">{item.raised_by && `Raised by ${memberName(item.raised_by)}. `}{methodScoped ? "Applies to the named model branches." : "Shared project question."}</p>{decisionSupportSections(item).map(({ text, heading, section }) => <section key={section}><h4>{heading}</h4><CitedRequestDocument item={item} text={text} section={section} onSource={onSource} /></section>)}<RequestSources item={item} onSource={onSource} /></details>
      {answer && !editing ? <div className="clarification-answer contribution-surface" ref={editButton}>
        <div className="clarification-answer-heading"><h4>Your clarification</h4><ActionButton action="edit" uiRole="research" onClick={() => { const draft = decisionDraft(item, answer); updateDraft(draft.note, true, draft.origin, draft.choice); setError(null); setSaved(false); globalThis.requestAnimationFrame?.(() => instructionInput.current?.focus({ preventScroll: true })); }}>Edit clarification</ActionButton></div>
        <ResearchDocument text={answer.note} />
        {answer.origin === "unknown" && <p className="note">Still unknown. This response does not settle the question.</p>}
        <p className="note">{answer.resolved_at && `Saved ${answer.resolved_at.slice(0, 16).replace("T", " ")}. `}{delivery}</p>
      </div> : <form onSubmit={resolve} className="clarification-form contribution-surface">
        {decisionResponseFields({ item, id: `${id}-answer`, note, origin, choice, busy, inputRef: instructionInput, update: (text, nextOrigin = origin) => updateDraft(text, editing, nextOrigin), select: value => updateDraft(note, editing, value === "unknown" ? "unknown" : "researcher_reported", value), onSource, recommendationId: `${id}-recommendation` })}
        {hasChoices && !source && <p className="note">The exact question source is unavailable. A selected option cannot be saved until it is restored.</p>}
        <div className="btnrow"><ActionButton action="save" uiRole="research" variant="primary" type="submit" disabled={busy || !submission || (submission.selection && !source)}>{busy ? "Saving…" : hasChoices ? "Save choice" : "Save clarification"}</ActionButton>{answer && <ActionButton action="close" disabled={busy} onClick={() => { clearDraft(); setError(null); globalThis.requestAnimationFrame?.(() => editButton.current?.querySelector("button")?.focus({ preventScroll: true })); }}>Cancel</ActionButton>}<span className="note" id={`${id}-delivery`}>One instruction for this question. {delivery} Work in progress keeps its original instructions.</span></div>
        {error && <p className="error" role="alert">{error}</p>}
      </form>}
      {saved && <p className="note" role="status">Clarification saved for subsequent runs.</p>}
    </div>
  </article>;
}

function DecisionsForScope({ items = [], answers = [], projectId, branch, phase, phases = [phase], methodId, methodTitle, emptyMessage, embedded = false, expanded = false, draftStore, onAnswerSaved, onResolved, onSource }) {
  const id = useId(); const [localAnswers, setLocalAnswers] = useState({});
  const scopedItems = methodId ? methodRequests(items, methodId, branch, { includeShared: !methodTitle }) : items;
  const scopedAnswers = methodId ? methodAnswers([...answers, ...Object.values(localAnswers)], methodId, branch, { includeShared: !methodTitle }) : [...answers, ...Object.values(localAnswers)];
  const cards = phases.flatMap((destination) => researcherDecisionCards(scopedItems, scopedAnswers, branch, destination));
  if (!cards.length) return emptyMessage ? embedded
    ? <section className="method-clarifications no-questions" data-card-role="history" aria-labelledby={`${id}-heading`}><h3 id={`${id}-heading`}>No input needed</h3><p className="note">{emptyMessage}</p></section>
    : <section className="card p2-no-questions" data-card-role="history"><h2>No input needed for this model</h2><div className="body"><p className="note">{emptyMessage}</p></div></section> : null;
  const unanswered = cards.filter(({ answer }) => !answer).length;
  const saveAnswer = (answer) => {
    setLocalAnswers((current) => ({ ...current, [clarificationDraftKey(projectId, answer.attention || { attention_id: answer.attention_id })]: answer }));
    onAnswerSaved?.(answer);
    onResolved?.();
  };
  if (embedded) return <section className="method-clarifications" data-card-role={unanswered ? "attention" : "history"} aria-labelledby={`${id}-heading`}>
    <h3 id={`${id}-heading`}>{unanswered ? "Needs your input" : "Your saved clarifications"}</h3>
    {!unanswered && <p className="note">Your clarifications are recorded.</p>}
    {cards.map(({ item, answer }, i) => <ResearcherDecision key={clarificationDraftKey(projectId, item)} item={item} answer={answer} projectId={projectId} branch={branch} number={i + 1} first={i === 0} headingLevel={4} expanded={expanded} draftStore={draftStore} onSaved={saveAnswer} onSource={onSource} />)}
  </section>;
  return <section className="card researcher-decisions" data-card-role={unanswered ? "attention" : "history"} aria-labelledby={`${id}-heading`}>
    <div className="card-heading"><h2 id={`${id}-heading`}>{unanswered ? "Needs your input" : "Your saved clarifications"}</h2></div>
    <div className="body">{methodTitle && <p className="note">Model: {methodTitle}</p>}{cards.map(({ item, answer }, i) => <ResearcherDecision key={clarificationDraftKey(projectId, item)} item={item} answer={answer} projectId={projectId} branch={branch} number={i + 1} first={i === 0} draftStore={draftStore} onSaved={saveAnswer} onSource={onSource} />)}</div>
  </section>;
}

export function ResearcherDecisions(props) {
  return <DecisionsForScope key={`${props.projectId}:${props.methodId || props.branch}:${props.phase}`} {...props} />;
}

export function TeamResearchFollowUp({ items, branch, phase, onSource, methodId, expanded = false }) {
  const { tasks } = requestsForScope(methodId ? methodRequests(items, methodId, branch, { includeShared: true }) : items, branch, phase);
  if (!tasks.length) return null;
  if (expanded) return <section className="p2-reader-section team-research-followup" data-card-role="research"><h3>Team research follow-up · Phase {phase.slice(1)}</h3>
    {tasks.map((item) => <article className="p2-research-task" key={itemKey(item)}><div role="heading" aria-level={4}><ResearchDocument text={item.question} /></div><RequestContext item={item} branch={branch} onSource={onSource} /></article>)}
  </section>;
  return <details className="research-details team-research-followup" data-card-role="research"><summary>Team research follow-up ({tasks.length})</summary><p className="note">Research tasks for the team in Phase {phase.slice(1)}. No clarification from you is requested.</p>
    {tasks.map((item) => <details className="contextual-request research-task" key={itemKey(item)}><summary><ResearchDocument text={item.question} /></summary><div className="request-body"><RequestContext item={item} branch={branch} onSource={onSource} /></div></details>)}
  </details>;
}

export function EarlierOpenQuestions({ items, answers, branch, phase, onSource, settingQuestions, settingReference }) {
  const { earlier, decisions, tasks } = requestsForScope(items, branch, phase);
  const saved = savedClarificationsForScope(answers, branch, phase);
  const questions = earlierSettingQuestions(settingQuestions, [...decisions, ...tasks, ...saved.map((answer) => answer.attention)]);
  if (!earlier.length && !questions.length) return null;
  return <details className="research-details earlier-open-questions" data-card-role="history"><summary>Earlier open questions ({earlier.length + questions.length})</summary>
    <p className="note">These questions were recorded in earlier work. Their context and intended recipient may be incomplete.</p>
    {earlier.map((item) => <details className="contextual-request historical-question" key={itemKey(item)}><summary><ResearchDocument text={item.question} /></summary><div className="request-body"><RequestContext item={item} branch={branch} onSource={onSource} /></div></details>)}
    {questions.map(({ text, index }) => <details className="contextual-request historical-question" key={`setting-${index}`}><summary><ResearchDocument text={text} /></summary><div className="request-body"><p className="note">Question preserved from the published research setting.</p><SourceRef reference={settingReference && { ...settingReference, entry_pointer: `/research_setting/clarification_questions/${index}` }} onOpen={onSource} label="Original setting question" /></div></details>)}
  </details>;
}

export function RunCorrections({ runs, branch, phase, onOpenRun }) {
  const corrections = correctionsForScope(runs, branch, phase);
  if (!corrections.length) return null;
  return <section className="card run-corrections" data-card-role="attention"><h2>Runs needing correction ({corrections.length})</h2><div className="body"><p className="note">Execution or output issues recorded by these runs.</p>{corrections.map((run) => <div className="inbox-row" key={run.run_id}><RunState state={run.state} /><span className="inbox-q">{modeLabel(run.mode || run.phase)}</span><ActionButton action="details" data-run-origin={`ContextualRequests:1:${run.run_id}`} onClick={(event) => onOpenRun(run.run_id, event.currentTarget)}>Review run findings</ActionButton></div>)}</div></section>;
}

export function RunsAwaitingDirection({ runs = [], branch, phase, onOpenRun }) {
  const waiting = runs.filter((run) => run.state === "awaiting_user" && (run.branch_id || run.branch) === branch && run.phase === phase);
  if (!waiting.length) return null;
  return <section className="card runs-awaiting-direction" data-card-role="attention"><h2>Evaluations waiting for your direction ({waiting.length})</h2><div className="body"><p className="note">Open the saved evaluation to answer its question or finish with the evidence already collected.</p>{waiting.map((run) => <div className="inbox-row" key={run.run_id}><RunState state={run.state} /><span className="inbox-q">{modeLabel(run.mode)}</span><ActionButton action="details" data-run-origin={`ContextualRequests:2:${run.run_id}`} onClick={(event) => onOpenRun(run.run_id, event.currentTarget)}>Review waiting evaluation</ActionButton></div>)}</div></section>;
}
