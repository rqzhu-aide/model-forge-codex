import React, { useEffect, useId, useRef, useState } from "react";
import { api } from "../api";
import { answerEffect, answerMatchesIssue, issueKey, issueAnswerPhase, issueIsOpen, issueLabel, issueVersionKey, issueSourceIdentity, issueSourceTarget } from "../phaseWorkflow";
import { issueCardEntries, issueCardState, issueDisplayKind, issueDisplayState, issueUrgency } from "../phaseUiState";
import { readConversationDraft, saveConversationDraft } from "../assumptionConversations";
import { ResearchDocument, ResearchLabel, SourceRef } from "./Shared";
import { CitedRequestDocument } from "./LiteratureCitation";
import { ActionButton, ActionIcon } from "./Visuals";
import { humanLabel, phaseLabel } from "../research";
import { decisionBriefSections, decisionDiscussionDraft, decisionDraft, decisionOptions, decisionPriorityLabel, decisionSubmission, decisionSupportSections } from "../researcherDecisions";
import { DecisionBrief, DecisionOptionsContext, decisionResponseFields } from "./DecisionResponse";
import { requestSourceReferences } from "../contextualRequests";
import { inlineStrongParts, inlineTokens, mathBody } from "../researchMath";
import { MethodReadingWindow, ReadingDocumentButton } from "./MethodReadingWindow";
import { questionSupport, questionSupportSnapshot } from "./QuestionSupport";
import ResearchCardLayout from "./ResearchCardLayout";
import { answerConflictKind, answerDraftBase, exactAnswerSnapshot, sameAnswerSource } from "../answerDrafts";
import { phaseQuestionAnchor } from "../phaseInputSummary";
import ReportDeliveryStatus from "./ReportDeliveryStatus";

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

export function IssueEntry({ issue, projectId, phase, branch, answers, onSaved, onSource, onExplain, onAnswerSaved, onPrepare, onNavigate, onReadSupport, readOnly = false, compact = false, headingLevel = 4 }) {
  const QuestionHeading = `h${headingLevel - 1}`;
  const SectionHeading = `h${headingLevel}`;
  const id = useId(); const key = `issue-response:${JSON.stringify([projectId, issueVersionKey(issue)])}`;
  const saved = issue.researcher_answer;
  const [localAnswer, setLocalAnswer] = useState(null);
  const [refreshedAnswers, setRefreshedAnswers] = useState(null);
  const latest = exactAnswerSnapshot(issue, answers || refreshedAnswers ? [...(answers || []), ...(refreshedAnswers || []), ...(localAnswer ? [localAnswer] : [])] : localAnswer ? [localAnswer] : undefined);
  // Applicability controls the displayed answer. The exact destination's
  // concurrency base is separate and may refer to an older retained answer.
  const answer = [saved, localAnswer, ...(refreshedAnswers || [])].filter(Boolean)
    .filter(candidate => candidate === saved || answerMatchesIssue(candidate, issue))
    .sort((first, second) => (second.revision || 0) - (first.revision || 0))[0];
  const cached = useRef(readOnly ? null : readConversationDraft(key));
  const initial = decisionDraft(issue, answer, cached.current);
  const [base, setBase] = useState(() => answerDraftBase(latest, cached.current));
  const [rejectedBase, setRejectedBase] = useState(null);
  const [sourceConflict, setSourceConflict] = useState(Boolean(cached.current?.sourceConflict));
  const [review, setReview] = useState(null);
  const [reviewing, setReviewing] = useState(false);
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
  const support = onReadSupport && !readOnly && (teamWork || ["choice", "study_fact"].includes(issue.response_kind)) ? questionSupport(issue, title, questionSources) : null;
  // A row with background reading places its actions, applicability and reader beside the brief at 3:2; the answer stays full width.
  // Team work without a brief stays in one column rather than leaving the account empty.
  const split = Boolean(support?.available && (decisionBriefSections(issue).length || support.inlineLimits));
  const currentSource = issueSourceIdentity(issue);
  const questionSource = issue.explanation_target || currentSource;
  const target = issueSourceTarget(questionSource ? { ...issue, explanation_target: questionSource } : issue);
  const contextDocument = (text, section) => <CitedRequestDocument item={issue} text={text} section={section} onSource={onSource} />;
  const responseDraft = !teamWork && editing ? decisionDiscussionDraft(issue, { note, origin, choice }) : null;
  const discuss = (purpose) => onExplain?.({ ...target,
    ...(purpose ? { assessmentPurpose: purpose } : {}),
    ...(answer ? { researcherNote: { note: answer.note, revision: answer.revision } } : {}),
    ...(responseDraft ? { researcherResponseDraft: responseDraft } : {}),
  });
  const hasChoices = decisionOptions(issue).length > 0;
  const responseHint = phase === "P2" && (issue.target_phase || phase) === "P2"
    ? issue.scope?.kind === "project" ? "After you save, applicable members can use it across models in their next work." : "After you save, the Lead can use it for the next model development work."
    : "After you save, it is available to the next work you start.";
  const persist = (text, nextOrigin, nextChoice, nextBase = base, blocked = sourceConflict) => saveConversationDraft(key, { text, origin: nextOrigin, choice: nextChoice, base: nextBase, ...(blocked ? { sourceConflict: true } : {}), ...(nextChoice.startsWith("option:") ? { selection: { option_id: nextChoice.slice(7) } } : {}) });
  const update = (text, nextOrigin = origin) => { setNote(text); setOrigin(nextOrigin); persist(text, nextOrigin, choice); };
  const select = (value) => { setChoice(value); const nextOrigin = value === "unknown" ? "unknown" : "researcher_reported"; setOrigin(nextOrigin); persist(note, nextOrigin, value); };
  const restore = (keep = false) => {
    const draft = decisionDraft(issue, answer), nextBase = answerDraftBase(latest);
    setNote(draft.note); setOrigin(draft.origin); setChoice(draft.choice); setBase(nextBase); setRejectedBase(null); setSourceConflict(false); setReview(null); setError(null);
    if (keep) persist(draft.note, draft.origin, draft.choice, nextBase, false);
  };
  const submission = decisionSubmission(issue, { note, origin, choice });
  const changedSource = sourceConflict || !sameAnswerSource(base.source, questionSource);
  const conflict = editing && (changedSource || base.revision == null || latest.revision !== base.revision || rejectedBase === base.revision);
  const reviewLatest = async () => {
    if (busy || reviewing || changedSource) return;
    setReviewing(true); setError(null);
    try {
      const pending = await api.decisionsPending(projectId);
      const current = exactAnswerSnapshot(issue, pending.researcher_answers || []);
      setRefreshedAnswers(pending.researcher_answers || []);
      if (current.revision == null || rejectedBase === current.revision) {
        setError("The latest saved answer is not available yet. Your draft is kept; try reviewing it again."); return;
      }
      setReview(current);
    } catch (failure) { setError(`The latest saved answer could not be loaded. Your draft is kept. ${failure.message}`); }
    finally { setReviewing(false); }
  };
  const adoptReviewed = (useLatest) => {
    if (!review || !sameAnswerSource(review.source, base.source)) return;
    const draft = useLatest ? decisionDraft(issue, review.answer) : { note, origin, choice };
    const nextBase = answerDraftBase(review);
    setNote(draft.note); setOrigin(draft.origin); setChoice(draft.choice); setBase(nextBase); setRejectedBase(null); setReview(null); setError(null);
    persist(draft.note, draft.origin, draft.choice, nextBase, false);
  };
  const save = async (event) => {
    event.preventDefault(); if (lock.current || conflict || !submission || (submission.selection && !questionSource)) return;
    lock.current = true; setBusy(true); setError(null);
    try {
      const result = await api.resolveAttention(projectId, issueKey(issue), submission.note, {
        expected_source: base.source, expected_revision: base.revision,
        ...((issue.scope || issue.response_kind || submission.origin === "unknown") ? { origin: submission.origin } : {}), ...(issue.scope?.kind === "project" ? { save_to_context: true } : {}),
        ...(submission.selection ? { selection: submission.selection } : {}),
      });
      const updated = result.answer;
      if (!updated || !Number.isInteger(updated.revision)) throw new Error("The saved answer could not be confirmed. Your draft is kept. Reload this question before trying again.");
      setLocalAnswer(updated); setBase({ source: base.source, revision: updated.revision }); setRejectedBase(null); setReview(null); onAnswerSaved?.(updated); setEditing(false); saveConversationDraft(key, null); setNotice("Your answer is saved. You can edit it here; I’ll use the updated answer in future work."); onSaved?.();
      globalThis.requestAnimationFrame?.(() => editButton.current?.querySelector("button")?.focus({ preventScroll: true }));
    } catch (failure) {
      const kind = answerConflictKind(failure);
      if (kind === "source") { setSourceConflict(true); setReview(null); persist(note, origin, choice, base, true); }
      else if (kind === "answer") { setRejectedBase(base.revision); setReview(null); persist(note, origin, choice); }
      else setError(failure.message);
    }
    finally { lock.current = false; setBusy(false); }
  };
  const contextAnchor = `issue-context:${issueVersionKey(issue)}`;
  const metadataNote = <span className="note">{metadata}</span>;
  const conversationActions = target && onExplain ? <div className="btnrow issue-conversation-actions"><ActionButton action="ask" uiRole="research" disabled={busy} aria-haspopup="dialog" onClick={() => discuss()}>Discuss</ActionButton>{target.kind === "phase_issue" && <ActionButton action="ask" uiRole="research" disabled={busy} aria-haspopup="dialog" onClick={() => discuss("issue_suggestions")}>Get the Lead's advice</ActionButton>}</div> : null;
  const tools = <div className="issue-team-tools">{metadataNote}{conversationActions}</div>;
  const recordedBrief = <DecisionBrief item={issue} onSource={onSource} showMetadata={false} headingLevel={headingLevel} recommendationId={`${id}-recommendation`} recommendationInResponse={!teamWork} />;
  const brief = issue.delivery_state?.portable_export_check === "passed" ? <details className="research-details"><summary>Recorded concern and scientific context</summary><ResearchDocument text={issue} /></details> : recordedBrief;
  // Team work takes no response, so its notes drop the response clauses and keep the team's assessment beside the brief.
  const applies = support && <>
      {issue.phase && issue.phase !== phase && <p className="note">Raised during {phaseLabel(issue.phase)}; applicable here.{!teamWork && " Your response stays with the original question."}</p>}
      {phase === "P2" && !issue.scope && (issue.branch || issue.branch_id) === "trunk" && !issue.affected_record_ids?.length && <p className="note">Shared across the proposed models.</p>}
      {issue.scope && <p className="note">{issue.scope.kind === "project" ? "Applies across models." : `Applies only to this exact model version${issue.scope.model_ref?.version != null ? ` (Version ${issue.scope.model_ref.version})` : ""}.`}</p>}
      {issue.target_phase && issue.target_phase !== phase && <p className="note">This {teamWork ? "work" : "response"} is intended for {({ P1: "problem and literature work", P2: "model development", P3: "theory development", P4: "numerical evaluation", P5: "report work" })[issue.target_phase]}.</p>}
      {teamWork && issue.disposition && issue.disposition !== "open" && <p className="note">Team assessment: {humanLabel(issue.disposition)}.</p>}
    </>;
  const limits = support?.inlineLimits && <section><SectionHeading>What remains unknown</SectionHeading>{contextDocument(support.inlineLimits, "limits")}</section>;
  const readButton = support?.available && <ReadingDocumentButton title={support.title} size={support.size} sizeLabel={support.sizeLabel} onClick={event => onReadSupport(issue, title, questionSources, event.currentTarget)} />;
  return <details className={`phase-issue issue-row${answer ? " answered" : ""}`} data-issue-state={display.state} data-reading-anchor={phaseQuestionAnchor(issue)} open={open} onToggle={(event) => { if (event.currentTarget.open !== open) setOpen(event.currentTarget.open); }}>
    <summary className="issue-row-summary" aria-label={`${questionAccessibleLabel(title)} ${urgency.label}`}><span className="issue-urgency-light" data-urgency={urgency.state} aria-hidden="true" /><QuestionHeading className="issue-row-title"><ResearchLabel text={title} /></QuestionHeading><span className="issue-row-status" data-response-state={display.state} data-urgency={urgency.state}>{urgency.label}</span><ActionIcon name="details" /></summary>
    <div className="issue-row-body">
    <ReportDeliveryStatus state={issue.delivery_state} onSource={onSource} includeHistory />
    <section className="issue-team-content" aria-label={teamWork ? "Team work and context" : "Team question and context"}>
    {split ? <ResearchCardLayout data-reading-anchor={contextAnchor} actions={conversationActions} resources={<>{metadataNote}{applies}{readButton}</>} actionsLabel={teamWork ? "Team work actions" : "Question actions"} label={teamWork ? "Team work supporting reading" : "Question supporting reading"} resourceElement="div">{brief}{limits}</ResearchCardLayout> : <>{tools}{brief}{support ? <div data-reading-anchor={contextAnchor}>{applies}{limits}{readButton}</div> : <details className="research-details" data-reading-anchor={contextAnchor}>
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
    </details>}</>}
    </section>
    {!teamWork && (readOnly || answer && !editing) && <DecisionOptionsContext item={issue} id={id} onSource={onSource} />}
    {teamWork ? <><p className="note">{issue.delivery_state?.portable_export_check === "passed" ? "The export check passed. Any scientific concerns in this recorded account remain unchanged." : display.state === "science" ? "The team needs to investigate this question." : "The team's assessment is recorded above."} Use the further work request below to add your priorities.</p>{onPrepare && <ActionButton action="repair" uiRole="research" onClick={event => onPrepare(issue, event.currentTarget)}>Prepare further work</ActionButton>}{answer && <section className="issue-answer"><SectionHeading>Your saved answer</SectionHeading><ResearchDocument text={answer.note} /><p className="note">{answerEffect(answer)}</p></section>}</>
      : readOnly ? <section className="issue-answer">{answer && <><SectionHeading>Your saved answer</SectionHeading><ResearchDocument text={answer.note} />{answer.origin === "unknown" && <p className="note">Still unknown. This response does not settle the question.</p>}<p className="note">{answerEffect(answer)}</p></>}<p className="note">Review or answer this question in {phaseLabel(issueAnswerPhase(issue))}.</p>{onNavigate && <ActionButton action="details" onClick={() => onNavigate(issueAnswerPhase(issue), undefined, issue)}>Go to {phaseLabel(issueAnswerPhase(issue))} questions</ActionButton>}</section>
      : answer && !editing ? <section className="issue-answer contribution-surface" ref={editButton}><SectionHeading>Your saved answer</SectionHeading><ResearchDocument text={answer.note} />{answer.origin === "unknown" && <p className="note">Still unknown. This response does not settle the question.</p>}<p className="note">{answerEffect(answer)}</p><ActionButton action="edit" uiRole="research" onClick={() => { restore(true); setEditing(true); setNotice(null); globalThis.requestAnimationFrame?.(() => instructionInput.current?.focus({ preventScroll: true })); }}>Edit your answer</ActionButton></section>
      : <form className="issue-instruction-editor contribution-surface" onSubmit={save}>
        {decisionResponseFields({ item: issue, id, note, origin, choice, busy, inputRef: instructionInput, update, select, onSource, recommendationId: `${id}-recommendation`, recommendationInResponse: true })}
        {conflict && <section className="issue-answer-conflict" aria-label="Answer conflict">
          <p className="note" role="status">{changedSource ? "This question's source changed. Your draft is kept with the original question; it cannot be saved to a different question." : base.revision == null ? "The saved-answer version for this draft is unknown. Review the latest saved answer before saving; your draft is kept." : "Another answer was saved while you were editing. Your draft is kept."}</p>
          {changedSource ? <p className="note">Reopen the original question to check its source, or answer the new question in its own editor.</p> : <>
            <ActionButton action="details" disabled={busy || reviewing} onClick={reviewLatest}>{reviewing ? "Loading latest answer…" : "Review latest answer"}</ActionButton>
            {review && <div className="issue-answer-review">
              <SectionHeading>Latest saved answer</SectionHeading>
              {review.answer ? <><ResearchDocument text={review.answer.note} />{review.answer.origin === "unknown" && <p className="note">Still unknown. This response does not settle the question.</p>}</> : <p className="note">No answer is saved for this exact question.</p>}
              <p className="note">{review.answer ? "Saving your draft will update the answer shown here." : "Saving will add your answer to this exact question."} Choosing how to continue does not save an answer.</p>
              <div className="btnrow"><ActionButton action="edit" uiRole="research" disabled={busy} onClick={() => adoptReviewed(true)}>Use latest answer</ActionButton><ActionButton action="edit" uiRole="research" disabled={busy} onClick={() => adoptReviewed(false)}>Keep editing my draft</ActionButton></div>
            </div>}
          </>}
        </section>}
        {hasChoices && !questionSource && <p className="note">The exact question source is unavailable. A selected option cannot be saved until it is restored.</p>}
        <p className="note">{answer ? "Save to use this update in future work. Work already started keeps its original answer." : "You haven't saved an answer to this question yet."} {responseHint}</p>
        <div className="btnrow"><ActionButton action="save" uiRole="research" type="submit" variant="primary" disabled={busy || conflict || !submission || (submission.selection && !questionSource)}>{busy ? "Saving…" : "Save answer"}</ActionButton>{answer && <ActionButton action="close" disabled={busy} onClick={() => { setEditing(false); restore(); saveConversationDraft(key, null); globalThis.requestAnimationFrame?.(() => editButton.current?.querySelector("button")?.focus({ preventScroll: true })); }}>Cancel edit</ActionButton>}</div>{error && <p className="error" role="alert">{error}</p>}</form>}
    {notice && <p className="note" role="status">{notice}</p>}
    </div>
  </details>;
}

export default function IssuesCard({ projectId, phase, branch, methodId, modelRef, methodLabel, issues = [], attention = [], answers = [], onSaved, onSource, onExplain, onNavigate, onPrepare, pause, activePause = false, activePauseKind, savedPauseCount = 0, corrections, correctionCount = 0, children, title = "Issues and decisions", intro, footer, decisionSummary = false, decisionDataState = "unavailable", decisionScope = "selected", pendingInterpretationCount = 0, progressive = false, questionsOnly = false, workOnly = false, embedded = false }) {
  const [localAnswers, setLocalAnswers] = useState({});
  const [reader, setReader] = useState(null);
  const cardRef = useRef(null);
  // A reader belongs to the project, viewing phase and selected branch/model that opened it.
  const readerScope = JSON.stringify([projectId, phase, branch ?? null, methodId ?? null, modelRef ?? null]);
  useEffect(() => { setReader(null); }, [readerScope]);
  const visibleReader = reader?.scope === readerScope ? reader : null;
  const readSupport = (issue, questionTitle, questionSources, trigger) => setReader({ scope: readerScope, trigger,
    ...questionSupportSnapshot({ projectId, phase, branch, methodId, modelRef }, issue, questionTitle, questionSources, onSource) });
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
  if (state.state === "empty" && !pause && !children && !corrections && !intro && !footer && !visibleReader) return null;
  // Every native summary owns the question heading; its sections follow it.
  const sectionLevel = embedded ? 5 : 4;
  const entryRenderer = (headingLevel) => (issue) => <IssueEntry key={issueVersionKey(issue)} compact={questionsOnly || workOnly} headingLevel={headingLevel} issue={issue} answers={answers} projectId={projectId} phase={phase} branch={branch} onSaved={onSaved} onSource={onSource} onExplain={onExplain} onPrepare={onPrepare} onReadSupport={readSupport} onAnswerSaved={(answer) => setLocalAnswers((current) => ({ ...current, [issueVersionKey(issue)]: answer }))} />;
  const renderEntry = entryRenderer(sectionLevel);
  const questions = entries.filter((issue) => !isWork(issue));
  const findings = entries.filter((issue) => issueDisplayKind(issue) === "scientific_issue");
  const tasks = entries.filter((issue) => issue.kind === "research_task");
  const relatedQuestions = related.filter((issue) => !isWork(issue));
  const relatedWork = related.filter(isWork);
  const linkedAnswers = decisionSummary ? relatedQuestions.filter(issue => issue.researcher_answer) : [];
  const linkedQuestions = decisionSummary ? relatedQuestions.filter(issue => !issue.researcher_answer) : relatedQuestions;
  const openQuestions = questions.filter(issue => !issue.researcher_answer && issueIsOpen(issue)).length;
  const researcherState = activePause ? { state: "waiting", label: "Work is paused." }
    : openQuestions ? { state: "response", label: `${openQuestions} open ${openQuestions === 1 ? "question" : "questions"}${pendingInterpretationCount ? ` · ${pendingInterpretationCount} ${pendingInterpretationCount === 1 ? "interpretation" : "interpretations"} awaiting your review` : ""}` }
    : pendingInterpretationCount ? { state: "response", label: `${pendingInterpretationCount} ${pendingInterpretationCount === 1 ? "interpretation" : "interpretations"} awaiting your review` }
    : decisionScope === "unselected-method" ? { state: "unavailable", label: "Choose a method to see its questions." }
    : ["ready", "refreshing", "refresh-failed"].includes(decisionDataState) ? { state: "empty", label: decisionScope === "shared-overview"
      ? `${decisionDataState !== "ready" ? "The last available update had no open questions shared across methods." : "No open questions shared across methods."} Select a method to see its questions.`
      : decisionDataState !== "ready" ? `The last available update had no open Phase ${phase.slice(1)} questions.` : `No Phase ${phase.slice(1)} question needs your answer.` }
    : { state: "unavailable", label: decisionDataState === "partial" ? "Decision information is incomplete." : "Decision information is unavailable." };
  const summary = decisionSummary ? researcherState : state;
  const renderQuestions = () => <>{questions.filter(issue => decisionPriorityLabel(issue)).map(renderEntry)}{questions.some(issue => !decisionPriorityLabel(issue)) && <><p className="note legacy-decision-priority">Earlier questions · priority not recorded</p>{questions.filter(issue => !decisionPriorityLabel(issue)).map(renderEntry)}</>}</>;
  const Heading = embedded ? "h3" : "h2";
  return <section ref={cardRef} id={workOnly ? "phase-work-details" : "phase-issues"} tabIndex={-1} className={embedded ? "phase-work-details" : "card phase-issues"} data-card-role={embedded ? undefined : "attention"} data-reading-anchor={workOnly ? "phase-work-details" : "phase-decisions"} data-attention-state={summary.state}><div className={embedded ? "section-heading" : "card-heading"}><Heading>{title}</Heading></div><div className={embedded ? undefined : "body"}>
    <p className={`note issue-state-summary${summary.state === "empty" ? " issues-empty" : ""}`} data-attention-state={summary.state}>{summary.label}</p>
    {decisionSummary && decisionDataState === "refreshing" && <p className="note issue-refresh-status" role="status">Showing the last available decision information. Updated information is not yet available.</p>}
    {decisionSummary && decisionDataState === "refresh-failed" && <p className="note issue-refresh-status" role="status">Updates could not be loaded. Showing the last available decision information.</p>}
    {decisionSummary && decisionDataState === "partial" && (openQuestions > 0 || activePause || pendingInterpretationCount > 0) && <p className="note issue-refresh-status" role="status">Some decision information is unavailable. The available questions and saved input remain below.</p>}
    {methodLabel && <p className="note">Model: {methodLabel}</p>}
    {pause}
    {questionsOnly ? <>{renderQuestions()}{intro}</> : progressive ? <>{renderQuestions()}{intro}{!decisionSummary && <>{findings.length > 0 && <details className="research-details"><summary>Scientific findings ({findings.length})</summary>{findings.map(renderEntry)}</details>}{tasks.length > 0 && <details className="research-details"><summary>Team investigation tasks ({tasks.length})</summary>{tasks.map(renderEntry)}</details>}</>}</> : entries.map(renderEntry)}
    {linkedQuestions.length > 0 && <section className="related-phase-questions"><h3>Questions linked to another phase</h3>{linkedQuestions.map((issue) => <IssueEntry key={issueVersionKey(issue)} compact readOnly headingLevel={Math.min(sectionLevel + 1, 6)} issue={issue} projectId={projectId} phase={phase} branch={branch} onSource={onSource} onExplain={onExplain} onNavigate={onNavigate} />)}</section>}
    {linkedAnswers.length > 0 && <details className="research-details related-phase-questions"><summary>Questions answered in another phase ({linkedAnswers.length})</summary>{linkedAnswers.map(issue => <p key={issueVersionKey(issue)}><ActionButton action="details" uiRole="research" onClick={() => onNavigate?.(issueAnswerPhase(issue), undefined, issue)}><ResearchLabel text={issueLabel(issue, true)} /></ActionButton><span className="note"> · {issue.researcher_answer.origin === "unknown" ? "Saved · still unknown" : "Answer saved"}</span></p>)}</details>}
    {decisionSummary && [...findings, ...tasks, ...relatedWork].length > 0 && <details className="research-details related-phase-work"><summary>Work the team is carrying forward</summary>{[...findings, ...tasks, ...relatedWork].map(renderEntry)}</details>}
    {!decisionSummary && relatedWork.length > 0 && <section className="related-phase-work"><h3>Scientific work carried forward</h3><p className="note">These findings and tasks remain linked to their original scientific sources.</p>{relatedWork.map(entryRenderer(Math.min(sectionLevel + 1, 6)))}</section>}
    {earlierEntries.size > 0 && <details className="research-details"><summary>Responses to earlier question versions ({earlierEntries.size})</summary><p className="note">These original responses do not answer the current question without an explicit link from its author.</p>{[...earlierEntries.values()].map((issue) => <IssueEntry key={issueVersionKey(issue)} compact headingLevel={sectionLevel} issue={issue} answers={answers} projectId={projectId} phase={issue.phase} branch={issue.branch} onSaved={onSaved} onSource={onSource} onExplain={onExplain} onPrepare={onPrepare} onAnswerSaved={(answer) => setLocalAnswers((current) => ({ ...current, [issueVersionKey(issue)]: answer }))} />)}</details>}
    {children}{corrections}{footer}
  </div>{visibleReader && <MethodReadingWindow key={visibleReader.key} snapshot={visibleReader} onClose={() => setReader(null)} returnFocus={() => visibleReader.trigger?.isConnected ? visibleReader.trigger : cardRef.current} />}</section>;
}
