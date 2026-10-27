import React, { useId, useRef, useState } from "react";
import { api } from "../api";
import { answerEffect, issueKey, issueLabel, issueVersionKey, issueSourceIdentity, issueSourceTarget } from "../phaseWorkflow";
import { issueCardEntries, issueCardState, issueDisplayKind, issueDisplayState, issueUrgency } from "../phaseUiState";
import { readConversationDraft, saveConversationDraft } from "../assumptionConversations";
import { ResearchDocument, ResearchLabel, SourceRef } from "./Shared";
import { CitedRequestDocument } from "./LiteratureCitation";
import { ActionButton, ActionIcon } from "./Visuals";
import { humanLabel, phaseLabel } from "../research";
import { decisionDraft, decisionOptions, decisionPriorityLabel, decisionSubmission, decisionSupportSections } from "../researcherDecisions";
import { DecisionBrief, decisionResponseFields } from "./DecisionResponse";
import { requestSourceReferences } from "../contextualRequests";
import { inlineStrongParts, inlineTokens, mathBody } from "../researchMath";

// Keep question citations actionable outside the native disclosure control,
// without repeating the question or resolving against a newer generation.
function questionSourceLabels(text) {
  return [...new Set(inlineStrongParts(String(text || "")).flatMap(part => part.text.split(inlineTokens)
    .filter(token => /^\[[^\]]+\]\([^\s)]+\)$/.test(token))))];
}

// MathML remains available in the heading. Chromium can omit it from the
// disclosure's computed name, so keep the authored notation in that name too.
function questionAccessibleLabel(text) {
  return inlineStrongParts(String(text || "")).map(part => part.text.split(inlineTokens).map(token => {
    const math = mathBody(token);
    if (math) return math.latex;
    const link = token.match(/^\[([^\]]+)\]\([^)]*\)$/);
    return link ? link[1] : token.startsWith("`") ? token.slice(1, -1) : token;
  }).join("")).join("");
}

export function IssueEntry({ issue, projectId, phase, branch, onSaved, onSource, onExplain, onAnswerSaved, onPrepare, compact = false, headingLevel = 4 }) {
  const QuestionHeading = `h${headingLevel - 1}`;
  const SectionHeading = `h${headingLevel}`;
  const id = useId(); const key = `issue-response:${JSON.stringify([projectId, issueVersionKey(issue)])}`;
  const saved = issue.researcher_answer;
  const [localAnswer, setLocalAnswer] = useState(null);
  const answer = localAnswer && (localAnswer.revision ?? 0) >= (saved?.revision ?? 0) ? localAnswer : saved;
  const cached = useRef(readConversationDraft(key));
  const initial = decisionDraft(issue, answer, cached.current);
  const [note, setNote] = useState(initial.note);
  const [origin, setOrigin] = useState(initial.origin);
  const [choice, setChoice] = useState(initial.choice);
  const [editing, setEditing] = useState(Boolean(cached.current) || !saved);
  const [open, setOpen] = useState(Boolean(cached.current));
  const editButton = useRef(null); const instructionInput = useRef(null);
  const [busy, setBusy] = useState(false); const lock = useRef(false); const [error, setError] = useState(null); const [notice, setNotice] = useState(null);
  const display = issueDisplayState({ ...issue, researcher_answer: answer });
  const urgency = issueUrgency({ ...issue, researcher_answer: answer });
  const teamWork = ["research_task", "scientific_issue"].includes(issueDisplayKind(issue));
  const title = !teamWork && issue.question?.trim() ? issue.question : issueLabel(issue, compact);
  const metadata = `From ${humanLabel(issue.original_role || issue.responsible_role || "research_team")}`;
  const questionSources = questionSourceLabels(title);
  const currentSource = issueSourceIdentity(issue);
  const questionSource = issue.explanation_target || currentSource;
  const target = issueSourceTarget(questionSource ? { ...issue, explanation_target: questionSource } : issue);
  const contextDocument = (text, section) => <CitedRequestDocument item={issue} text={text} section={section} onSource={onSource} />;
  const discuss = (purpose) => onExplain?.({ ...target,
    ...(purpose ? { assessmentPurpose: purpose } : {}),
    ...(answer ? { researcherNote: { note: answer.note, revision: answer.revision } } : {}),
    ...(!teamWork && editing && note.trim() ? { researcherNoteDraft: note.trim() } : {}),
  });
  const hasChoices = decisionOptions(issue).length > 0;
  const responseHint = phase === "P2" && (issue.target_phase || phase) === "P2"
    ? issue.scope?.kind === "project" ? "After you save, applicable members can use it across models in their next work." : "After you save, the Lead can use it for the next model development work."
    : "After you save, it is available to the next work you start.";
  const persist = (text, nextOrigin, nextChoice) => saveConversationDraft(key, { text, origin: nextOrigin, choice: nextChoice, ...(nextChoice.startsWith("option:") ? { selection: { option_id: nextChoice.slice(7) } } : {}) });
  const update = (text, nextOrigin = origin) => { setNote(text); setOrigin(nextOrigin); persist(text, nextOrigin, choice); };
  const select = (value) => { setChoice(value); const nextOrigin = value === "unknown" ? "unknown" : "researcher_reported"; setOrigin(nextOrigin); persist(note, nextOrigin, value); };
  const restore = () => { const draft = decisionDraft(issue, answer); setNote(draft.note); setOrigin(draft.origin); setChoice(draft.choice); };
  const submission = decisionSubmission(issue, { note, origin, choice });
  const answerSource = issueSourceIdentity(answer?.question_ref ? { explanation_target: answer.question_ref } : answer?.attention);
  const inheritedAnswer = answerSource && currentSource && JSON.stringify(answerSource) !== JSON.stringify(currentSource);
  const save = async (event) => {
    event.preventDefault(); if (lock.current || !submission || (submission.selection && !questionSource)) return;
    lock.current = true; setBusy(true); setError(null);
    try {
      const result = await api.resolveAttention(projectId, issueKey(issue), submission.note, {
        expected_source: questionSource, expected_revision: inheritedAnswer ? 0 : answer?.revision ?? 0,
        ...((issue.scope || issue.response_kind || submission.origin === "unknown") ? { origin: submission.origin } : {}), ...(issue.scope?.kind === "project" ? { save_to_context: true } : {}),
        ...(submission.selection ? { selection: submission.selection } : {}),
      });
      const updated = result.answer || { note: submission.note };
      setLocalAnswer(updated); onAnswerSaved?.(updated); setEditing(false); saveConversationDraft(key, null); setNotice("Your answer is saved. You can edit it here; I’ll use the updated answer in future work."); onSaved?.();
      globalThis.requestAnimationFrame?.(() => editButton.current?.querySelector("button")?.focus({ preventScroll: true }));
    } catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  };
  return <details className={`phase-issue issue-row${answer ? " answered" : ""}`} data-issue-state={display.state} data-reading-anchor={`issue:${issueVersionKey(issue)}`} open={open} onToggle={(event) => { if (event.currentTarget.open !== open) setOpen(event.currentTarget.open); }}>
    <summary className="issue-row-summary" aria-label={`${questionAccessibleLabel(title)} ${urgency.label}`}><span className="issue-urgency-light" data-urgency={urgency.state} aria-hidden="true" /><QuestionHeading className="issue-row-title"><ResearchLabel text={title} /></QuestionHeading><span className="issue-row-status" data-response-state={display.state} data-urgency={urgency.state}>{urgency.label}</span><ActionIcon name="details" /></summary>
    <div className="issue-row-body">
    <section className="issue-team-content" aria-label="Team question and context">
    <div className="issue-team-tools"><span className="note">{metadata}</span>{target && onExplain && <div className="btnrow issue-conversation-actions"><ActionButton action="ask" uiRole="research" disabled={busy} aria-haspopup="dialog" onClick={() => discuss()}>Discuss</ActionButton>{target.kind === "phase_issue" && <ActionButton action="ask" uiRole="research" disabled={busy} aria-haspopup="dialog" onClick={() => discuss("issue_suggestions")}>Get the Lead's advice</ActionButton>}</div>}</div>
    <DecisionBrief item={issue} onSource={onSource} showMetadata={false} headingLevel={headingLevel} />
    <details className="research-details" data-reading-anchor={`issue-context:${issueVersionKey(issue)}`}>
    <summary>Context and sources</summary>
    <p className="note issue-attribution"><span className="issue-state-badge" data-issue-state={display.state}>{display.label}</span>{(issue.original_role || issue.responsible_role) && ` · ${humanLabel(issue.original_role || issue.responsible_role)}`}</p>
    {(issue.response_kind || decisionPriorityLabel(issue)) && <p className="note">{issue.response_kind === "study_fact" ? "Study information" : issue.response_kind === "choice" ? "Researcher choice" : "Researcher question"}{decisionPriorityLabel(issue) && ` · ${decisionPriorityLabel(issue)}`}</p>}
    {issue.severity && <p className="note">Scientific importance: {humanLabel(issue.severity)}.</p>}
    {issue.title && issue.title !== title && <section><SectionHeading>Original title</SectionHeading>{contextDocument(issue.title, "title")}</section>}
    {issue.phase && issue.phase !== phase && <p className="note">Raised during {phaseLabel(issue.phase)}; applicable here. Your response stays with the original question.</p>}
    {phase === "P2" && (issue.branch || issue.branch_id) === "trunk" && !issue.affected_record_ids?.length && <p className="note">Shared across the proposed models.</p>}
    {issue.scope && <p className="note">{issue.scope.kind === "project" ? "Applies across models." : `Applies only to this exact model version${issue.scope.model_ref?.version != null ? ` (Version ${issue.scope.model_ref.version})` : ""}.`}</p>}
    {issue.original_role === "outside_reviewer" && <p className="note">The Research Lead can explain this comment as an interpretation of the independent review.</p>}
    {issue.target_phase && issue.target_phase !== phase && <p className="note">This {teamWork ? "work" : "response"} is intended for {({ P1: "problem and literature work", P2: "model development", P3: "theory development", P4: "numerical evaluation", P5: "report work" })[issue.target_phase]}.</p>}
    {decisionSupportSections(issue, title).map(({ text, heading, section }) => <section key={section}><SectionHeading>{heading}</SectionHeading>{contextDocument(text, section)}</section>)}
    {questionSources.length > 0 && <section><SectionHeading>Question sources</SectionHeading>{contextDocument(questionSources.join("\n\n"), "question-sources")}</section>}
    {issue.disposition && issue.disposition !== "open" && <p className="note">Team assessment: {humanLabel(issue.disposition)}.{!teamWork && " Your response below is kept separately."}</p>}
    {requestSourceReferences(issue).length > 0 && <div className="btnrow issue-actions">{requestSourceReferences(issue).map(({ label, reference }, index) => <SourceRef key={index} reference={reference} onOpen={onSource} label={index === 0 ? "Read the scientific context" : label} />)}</div>}
    </details>
    </section>
    {teamWork ? <><p className="note">{display.state === "science" ? "The team needs to investigate this question." : "The team's assessment is recorded above."} Use the further work request below to add your priorities.</p>{onPrepare && <ActionButton action="repair" uiRole="research" onClick={event => onPrepare(issue, event.currentTarget)}>Prepare further work</ActionButton>}{answer && <section className="issue-answer"><SectionHeading>Your saved answer</SectionHeading><ResearchDocument text={answer.note} /><p className="note">{answerEffect(answer)}</p></section>}</>
      : answer && !editing ? <section className="issue-answer contribution-surface" ref={editButton}><SectionHeading>Your saved answer</SectionHeading><ResearchDocument text={answer.note} />{answer.origin === "unknown" && <p className="note">Still unknown. This response does not settle the question.</p>}<p className="note">{answerEffect(answer)}</p><ActionButton action="edit" uiRole="research" onClick={() => { restore(); setEditing(true); setNotice(null); globalThis.requestAnimationFrame?.(() => instructionInput.current?.focus({ preventScroll: true })); }}>Edit your answer</ActionButton></section>
      : <form className="issue-instruction-editor contribution-surface" onSubmit={save}>
        {decisionResponseFields({ item: issue, id, note, origin, choice, busy, inputRef: instructionInput, update, select, onSource })}
        {hasChoices && !questionSource && <p className="note">The exact question source is unavailable. A selected option cannot be saved until it is restored.</p>}
        <p className="note">{answer ? "Save to use this update in future work. Work already started keeps its original answer." : "You haven't saved an answer to this question yet."} {responseHint}</p>
        <div className="btnrow"><ActionButton action="save" uiRole="research" type="submit" variant="primary" disabled={busy || !submission || (submission.selection && !questionSource)}>{busy ? "Saving…" : "Save answer"}</ActionButton>{answer && <ActionButton action="close" disabled={busy} onClick={() => { setEditing(false); restore(); saveConversationDraft(key, null); globalThis.requestAnimationFrame?.(() => editButton.current?.querySelector("button")?.focus({ preventScroll: true })); }}>Cancel edit</ActionButton>}</div>{error && <p className="error" role="alert">{error}</p>}</form>}
    {notice && <p className="note" role="status">{notice}</p>}
    </div>
  </details>;
}

export default function IssuesCard({ projectId, phase, branch, methodId, modelRef, methodLabel, issues = [], attention = [], answers = [], onSaved, onSource, onExplain, onNavigate, onPrepare, pause, activePause = false, activePauseKind, savedPauseCount = 0, corrections, correctionCount = 0, children, title = "Issues and decisions", intro, progressive = false, questionsOnly = false, workOnly = false, embedded = false }) {
  const [localAnswers, setLocalAnswers] = useState({});
  const projected = issueCardEntries({ issues, attention, answers, phase, branch, methodId, modelRef });
  const isWork = issue => ["research_task", "scientific_issue"].includes(issueDisplayKind(issue));
  const include = issue => questionsOnly ? !isWork(issue) : workOnly ? isWork(issue) : true;
  const entries = projected.entries.filter(include).map((issue) => {
    const local = localAnswers[issueVersionKey(issue)];
    return local && (local.revision ?? 0) >= (issue.researcher_answer?.revision ?? 0) ? { ...issue, researcher_answer: local } : issue;
  });
  const related = projected.related.filter(include); const earlierAnswers = workOnly ? [] : projected.earlierAnswers;
  const earlierEntries = new Map();
  for (const answer of earlierAnswers) {
    const original = answer.attention || {};
    const issue = { ...original, attention_id: original.attention_id || answer.attention_id || answer.issue_id,
      phase: original.phase || answer.question_ref?.phase || phase, branch: original.branch || original.branch_id || answer.question_ref?.branch || branch,
      explanation_target: original.explanation_target || answer.question_ref,
      generation_ref: original.generation_ref || (answer.question_ref?.generation_id ? answer.question_ref : undefined), researcher_answer: answer };
    const key = issueVersionKey(issue); const source = issueSourceIdentity(issue);
    const historyKey = source ? JSON.stringify([issueKey(issue), source]) : key; const previous = earlierEntries.get(historyKey);
    const local = localAnswers[key];
    if (local && (local.revision ?? 0) >= (answer.revision ?? 0)) issue.researcher_answer = local;
    if (!previous || (issue.researcher_answer.revision ?? 0) > (previous.researcher_answer.revision ?? 0)) earlierEntries.set(historyKey, issue);
  }
  const state = issueCardState({ entries, related, activePause, activePauseKind, savedPauseCount, correctionCount });
  if (state.state === "empty" && !pause && !children && !corrections && !intro) return null;
  // Every native summary owns the question heading; its sections follow it.
  const sectionLevel = embedded ? 5 : 4;
  const entryRenderer = (headingLevel) => (issue) => <IssueEntry key={issueVersionKey(issue)} compact={questionsOnly || workOnly} headingLevel={headingLevel} issue={issue} projectId={projectId} phase={phase} branch={branch} onSaved={onSaved} onSource={onSource} onExplain={onExplain} onPrepare={onPrepare} onAnswerSaved={(answer) => setLocalAnswers((current) => ({ ...current, [issueVersionKey(issue)]: answer }))} />;
  const renderEntry = entryRenderer(sectionLevel);
  const questions = entries.filter((issue) => !isWork(issue));
  const findings = entries.filter((issue) => issueDisplayKind(issue) === "scientific_issue");
  const tasks = entries.filter((issue) => issue.kind === "research_task");
  const relatedQuestions = related.filter((issue) => !isWork(issue));
  const relatedWork = related.filter(isWork);
  const renderQuestions = () => <>{questions.filter(issue => decisionPriorityLabel(issue)).map(renderEntry)}{questions.some(issue => !decisionPriorityLabel(issue)) && <><p className="note legacy-decision-priority">Earlier questions · priority not recorded</p>{questions.filter(issue => !decisionPriorityLabel(issue)).map(renderEntry)}</>}</>;
  const Heading = embedded ? "h3" : "h2";
  return <section id={workOnly ? "phase-work-details" : "phase-issues"} tabIndex={-1} className={embedded ? "phase-work-details" : "card phase-issues"} data-card-role={embedded ? undefined : "attention"} data-reading-anchor={workOnly ? "phase-work-details" : "phase-decisions"} data-attention-state={state.state}><div className={embedded ? "section-heading" : "card-heading"}><Heading>{title}</Heading></div><div className={embedded ? undefined : "body"}>
    {methodLabel && <p className="note">Model: {methodLabel}</p>}
    <p className={`note issue-state-summary${state.state === "empty" ? " issues-empty" : ""}`} data-attention-state={state.state}>{state.label}</p>
    {pause}
    {questionsOnly ? <>{renderQuestions()}{intro}</> : progressive ? <>{renderQuestions()}{intro}{findings.length > 0 && <details className="research-details"><summary>Scientific findings ({findings.length})</summary>{findings.map(renderEntry)}</details>}{tasks.length > 0 && <details className="research-details"><summary>Team investigation tasks ({tasks.length})</summary>{tasks.map(renderEntry)}</details>}</> : entries.map(renderEntry)}
    {relatedQuestions.length > 0 && <section className="related-phase-questions"><h3>Questions carried from earlier work</h3><p className="note">Their responses stay with the original question, so you can review or edit them there.</p>{relatedQuestions.map((issue) => { const display = issueDisplayState(issue); return <div key={issueKey(issue)}><ResearchDocument text={issueLabel(issue)} /><p className="note"><span className="issue-state-badge" data-issue-state={display.state}>{display.label}</span>{issue.disposition && issue.disposition !== "open" && ` · Team assessment: ${humanLabel(issue.disposition)}`}</p>{onNavigate && <ActionButton action="details" onClick={() => onNavigate(issue.phase)}>{`Go to ${phaseLabel(issue.phase)} questions`}</ActionButton>}</div>; })}</section>}
    {relatedWork.length > 0 && <section className="related-phase-work"><h3>Scientific work carried forward</h3><p className="note">These findings and tasks remain linked to their original scientific sources.</p>{relatedWork.map(entryRenderer(Math.min(sectionLevel + 1, 6)))}</section>}
    {earlierEntries.size > 0 && <details className="research-details"><summary>Responses to earlier question versions ({earlierEntries.size})</summary><p className="note">These original responses do not answer the current question without an explicit link from its author.</p>{[...earlierEntries.values()].map((issue) => <IssueEntry key={issueVersionKey(issue)} compact headingLevel={sectionLevel} issue={issue} projectId={projectId} phase={issue.phase} branch={issue.branch} onSaved={onSaved} onSource={onSource} onExplain={onExplain} onPrepare={onPrepare} onAnswerSaved={(answer) => setLocalAnswers((current) => ({ ...current, [issueVersionKey(issue)]: answer }))} />)}</details>}
    {children}{corrections}
  </div></section>;
}
