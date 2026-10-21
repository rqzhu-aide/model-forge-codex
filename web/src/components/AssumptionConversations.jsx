import React, { useId, useRef, useState } from "react";
import { api } from "../api";
import { freshId, humanLabel } from "../research";
import { assumptionSource, conversationDraftKey, conversationPurpose, conversationsForTarget, conversationTitle, defaultConversationQuestion, isConversationTarget, isEarlierConversation, isPendingTurn, readConversationDraft, saveConversationDraft } from "../assumptionConversations";
import { conversationSourceReference } from "../conversationSources";
import { Dialog, MathText, ResearchDocument, SourceRef } from "./Shared";
import { ActionButton, ActionIcon } from "./Visuals";
import ReportSectionComment from "./ReportSectionComment";

const authorName = (role) => ({ research_lead: "Research Lead", theorist: "Theorist", data_analyst: "Data Analyst" }[role] || "Theorist");
const dateLabel = (value) => String(value || "").slice(0, 16).replace("T", " ");
const submissionError = (failure) => failure.status === 409 && /a P3 run is already active on branch/.test(failure.message)
  ? "Another Phase 3 run is in progress for this model. Wait for it to finish before asking. Your question is kept here."
  : failure.message;

function AnswerSources({ references = [], target, onSource }) {
  if (!references.length) return null;
  return <details className="research-details conversation-sources"><summary>Sources used</summary>{references.map((item, index) => {
    const ref = item.generation_ref || item;
    const source = ref.branch && ref.phase ? ref : ref.family === target?.family && ref.generation_id === target?.generation_id ? { ...target, ...ref } : null;
    const url = item.source_url || item.artifact_url;
    return <div key={index}>{item.source_error ? <span className="note">{item.source_error}</span> : source ? <SourceRef reference={source} onOpen={onSource} label={item.label || item.title || humanLabel(ref.family || "Research source")} /> : /^https?:\/\/|^\/api\//i.test(url || "") ? <a className="source-link ui-action" data-action="source" data-ui-role="system" href={url} target="_blank" rel="noreferrer"><ActionIcon name="source" />{item.label || item.title || "Open source"}</a> : <span className="note">Complete linkage for this source is not available.</span>}</div>;
  })}</details>;
}

function DiscussionAnswer({ text, runId, references = [], earlierTurns = [], projectId, conversation, onSource }) {
  const fileLink = (source, label) => {
    const reference = conversationSourceReference(source, runId, references, earlierTurns, { projectId, conversation });
    return reference ? <SourceRef reference={reference} onOpen={onSource} label={label} />
      : <span className="note">{label} (source unavailable)</span>;
  };
  return <ResearchDocument text={text} renderFileLink={fileLink} renderSourceLink={(source, label) => source.startsWith("/api/") ? fileLink(source, label) : null} />;
}

export function ConversationTranscript({ conversation, projectId, onSource, onRetry, submitting = false }) {
  const turns = conversation.turns || [];
  const pending = turns.some(isPendingTurn);
  return <div className="conversation-transcript" aria-label="Conversation messages">
    {turns.map((turn, index) => {
      const failed = ["failed", "cancelled"].includes(turn.state);
      const retried = turns.some((next) => next.retry_run_id === turn.run_id);
      const canRetry = index === turns.length - 1;
      return <section className="conversation-turn" key={turn.run_id}>
        <div className="discussion-message researcher"><b className="note">You</b>{turn.retry_run_id && <span className="note"> · Retry</span>}<ResearchDocument text={turn.instructions} /></div>
        {isPendingTurn(turn) ? <p className="conversation-status note" role="status">Answering… Your question is saved. You can close this dialog and return later.</p> : failed ? <div className="conversation-failure" role="alert"><p>{turn.state === "cancelled" ? "This answer was interrupted." : "The answer could not be completed."} {typeof turn.terminal_reason === "string" ? turn.terminal_reason : turn.terminal_reason?.message || ""}</p>{retried ? <p className="note">A later attempt is shown below.</p> : canRetry && <ActionButton action="retry" uiRole="research" disabled={pending || submitting} onClick={() => onRetry?.(turn)}>Retry question</ActionButton>}</div> : <div className="discussion-message"><b className="note">{authorName(turn.responsible_role || conversation.responsible_role)}</b><DiscussionAnswer text={turn.assessment_markdown || "The saved answer is not available in this record."} runId={turn.run_id} references={turn.evidence_refs} earlierTurns={turns.slice(0, index)} projectId={projectId} conversation={conversation} onSource={onSource} />{turn.followup_questions?.length > 0 && <section><h4>Questions to consider</h4>{turn.followup_questions.map((question, position) => <section key={position}><ResearchDocument text={question.question} />{question.why_it_matters && <><h5>Why it matters</h5><ResearchDocument text={question.why_it_matters} /></>}{question.consequence_markdown && <ResearchDocument text={question.consequence_markdown} />}<p className="note">{authorName(question.responsible_role || turn.responsible_role || conversation.responsible_role)} · {question.scope?.kind === "project" ? "Across models" : "This exact model"}</p></section>)}<p className="note">Use your own words in a follow-up below, or leave the information unknown.</p></section>}<AnswerSources references={turn.evidence_refs || []} target={conversation.target} onSource={onSource} /></div>}
      </section>;
    })}
    {!turns.length && (conversation.messages || []).map((message, index) => <div className={`discussion-message${["user", "researcher"].includes(message.role) ? " researcher" : ""}`} key={message.message_id || index}><b className="note">{["user", "researcher"].includes(message.role) ? "You" : authorName(conversation.responsible_role)}</b>{["user", "researcher"].includes(message.role) ? <ResearchDocument text={message.content || message.instructions} /> : <DiscussionAnswer text={message.content || message.instructions} runId={message.run_id || conversation.run_id} references={message.evidence_refs || conversation.evidence_refs} earlierTurns={(conversation.messages || []).slice(0, index).filter((prior) => prior.role === "assistant")} projectId={projectId} conversation={conversation} onSource={onSource} />}</div>)}
  </div>;
}

function QuestionForm({ projectId, target, conversation, pending, blockedReason, onAccepted }) {
  const storageKey = conversationDraftKey(projectId, target, conversation?.assessment_id);
  const purpose = conversationPurpose(target, conversation);
  const suggestions = purpose === "issue_suggestions";
  const newDraft = () => ({ text: conversation ? "" : defaultConversationQuestion(target), idempotencyKey: freshId(),
    ...(!conversation && target.researcherNote ? { researcherNote: target.researcherNote } : {}),
    ...(!conversation && target.researcherNoteDraft ? { researcherNoteDraft: target.researcherNoteDraft } : {}) });
  const [draft, setDraft] = useState(() => readConversationDraft(storageKey) || newDraft());
  const [error, setError] = useState(null); const [sending, setSending] = useState(false);
  const lock = useRef(false); const questionId = useId();
  const update = (text) => {
    const next = { ...draft, text, idempotencyKey: freshId() };
    setDraft(next); saveConversationDraft(storageKey, next); setError(null);
  };
  const submit = async (event) => {
    event.preventDefault();
    if (lock.current || pending || blockedReason || !draft.text.trim()) return;
    lock.current = true; setSending(true); setError(null);
    saveConversationDraft(storageKey, draft);
    try {
      const body = { instructions: draft.text, idempotency_key: draft.idempotencyKey,
        ...(!conversation && draft.researcherNoteDraft ? { researcher_note_draft: draft.researcherNoteDraft } : {}) };
      const run = conversation
        ? await api.assessmentMessage(projectId, conversation.assessment_id, body)
        : await api.startRun(projectId, { ...body, phase: target.phase || "P1", mode: target.kind === "assumption" || ["project_context", "model_dialogue", "issue_suggestions"].includes(purpose) ? "p3.assessment" : "explanation", branch_id: target.branch || "trunk", intent: "assessment", target: assumptionSource(target), assessment_purpose: purpose });
      if (readConversationDraft(storageKey)?.idempotencyKey === draft.idempotencyKey) saveConversationDraft(storageKey, null);
      setDraft({ text: "", idempotencyKey: freshId() });
      onAccepted(run, draft.text, conversation, undefined, draft.researcherNoteDraft, draft.researcherNote);
    } catch (failure) {
      setError(failure.status ? submissionError(failure) : `${failure.message} The request could not be confirmed. Send the same question again to check its submission without creating a duplicate.`);
    } finally { lock.current = false; setSending(false); }
  };
  const savedNote = conversation ? conversation.researcher_answer : draft.researcherNote;
  const includedDraft = conversation?.researcher_note_draft || (!conversation && draft.researcherNoteDraft);
  return <form className="conversation-question contribution-surface" onSubmit={submit}>
    {(savedNote?.note || includedDraft) && <details className="research-details conversation-note-context" open={!conversation && Boolean(includedDraft)}><summary>Note included as context{includedDraft ? " · unsaved draft" : savedNote?.revision != null ? ` · saved revision ${savedNote.revision}` : ""}</summary>{savedNote?.note && <><h4>Saved response</h4><ResearchDocument text={savedNote.note} /></>}{includedDraft && <><h4>Unsaved draft</h4><ResearchDocument text={includedDraft} /><p className="note">Included for discussion only. Use Save instruction on the item to keep it as your instruction.</p></>}</details>}
    <div className="field"><label htmlFor={questionId}>{conversation ? "Your follow-up" : suggestions ? "Your request to the Lead" : target.kind === "report_section" ? "Your question about this section" : "Your question"}</label><textarea id={questionId} rows={3} value={draft.text} disabled={sending} onChange={(event) => update(event.target.value)} placeholder={conversation ? "Can you give me a simple example?" : target.kind === "report_section" ? "Explain this result, its assumptions or what it means for my problem." : target.kind === "project_context" ? "Describe your setting, ask how it fits a model, or explain what is still unknown." : target.kind === "assumption" ? "What happens without this assumption?" : "Explain more about this. What does it mean for my problem?"} /></div>
    {error && <p className="error" role="alert">{error}</p>}
    <div className="btnrow"><ActionButton action="ask" uiRole="research" variant="primary" type="submit" disabled={sending || pending || Boolean(blockedReason) || !draft.text.trim()}>{sending ? "Sending…" : conversation ? "Ask follow-up" : suggestions ? "Get Lead suggestions" : "Discuss"}</ActionButton><span className="note">{blockedReason || (pending ? "You can draft a follow-up while the answer is prepared." : target.kind === "report_section" ? "The Research Lead answers using this report section, its supporting sources and your saved comment." : suggestions ? "The Research Lead will recommend options using this question, its sources and your note. Suggestions do not save an answer or change the model." : "Discussion uses this exact question, its sources and your note. Saving a response is a separate action.")}</span></div>
  </form>;
}

export default function AssumptionConversations({ projectId, target, conversations = [], onClose, onSource, onStarted }) {
  const [selectedId, setSelectedId] = useState(target.conversationId || null);
  const [accepted, setAccepted] = useState([]);
  const [retrying, setRetrying] = useState(false); const retryLock = useRef(false);
  const [error, setError] = useState(null);
  const saved = conversationsForTarget(conversations, target);
  const combined = [...saved];
  for (const item of accepted) {
    const existing = combined.find((conversation) => conversation.assessment_id === item.assessment_id);
    if (!existing) combined.unshift(item);
    else if (!(existing.turns || []).some((turn) => turn.run_id === item.turns[0].run_id)) {
      combined[combined.indexOf(existing)] = { ...existing, turns: [...(existing.turns || []), ...item.turns] };
    }
  }
  combined.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
  const selected = combined.find((conversation) => conversation.assessment_id === selectedId);
  const earlier = selected && isEarlierConversation(selected, target);
  const displayedTarget = { ...(selected?.target || target), assessmentPurpose: conversationPurpose(target, selected) };
  const pending = selected?.turns?.some(isPendingTurn) || false;
  const retryFirst = selected && !pending && ["failed", "cancelled"].includes(selected.turns?.at(-1)?.state)
    && !selected.turns?.some((turn) => turn.state === "assessed") && !selected.messages?.length;
  const methodVersion = selected?.method_version ?? (!earlier ? target.methodVersion : null);
  const acceptedTurn = (run, instructions, conversation, retryRunId, researcherNoteDraft, researcherNote) => {
    const assessmentId = run.assessment_id || conversation?.assessment_id;
    const turn = { run_id: run.run_id, instructions, state: run.state || "requested", created_at: run.created_at || new Date().toISOString(), retry_run_id: retryRunId };
    const purpose = conversationPurpose(target, conversation);
    setAccepted((items) => [...items, { ...conversation, assessment_id: assessmentId, assessment_purpose: purpose, responsible_role: purpose === "issue_suggestions" ? "research_lead" : run.responsible_role || target.responsible_role, target: conversation?.target || assumptionSource(target), created_at: conversation?.created_at || turn.created_at, researcher_note_draft: conversation ? conversation.researcher_note_draft : researcherNoteDraft, researcher_answer: conversation ? conversation.researcher_answer : researcherNote, turns: [turn] }]);
    setSelectedId(assessmentId); setError(null); onStarted?.(run);
  };
  const retry = async (turn) => {
    if (retryLock.current || pending || !selected) return;
    retryLock.current = true; setRetrying(true); setError(null);
    const key = conversationDraftKey(projectId, selected.target, `${selected.assessment_id}:retry:${turn.run_id}`);
    const draft = readConversationDraft(key) || { idempotencyKey: freshId() };
    saveConversationDraft(key, draft);
    try {
      const run = await api.assessmentMessage(projectId, selected.assessment_id, { instructions: turn.instructions, retry_run_id: turn.run_id, idempotency_key: draft.idempotencyKey });
      saveConversationDraft(key, null); acceptedTurn(run, turn.instructions, selected, turn.run_id);
    } catch (failure) { setError(submissionError(failure)); }
    finally { retryLock.current = false; setRetrying(false); }
  };
  const selectConversation = (id) => { setSelectedId(id); setError(null); };
  const groups = [
    ["This source version", combined.filter((conversation) => !isEarlierConversation(conversation, target))],
    ["Earlier source versions", combined.filter((conversation) => isEarlierConversation(conversation, target))],
  ];
  return <Dialog title={target.kind === "report_section" ? "Discuss this section" : conversationPurpose(target) === "issue_suggestions" ? "Lead suggestions" : target.kind === "project_context" ? target.goal_source_ref ? "Discuss research goal" : "Discuss your problem" : target.kind === "model_dialogue" ? "Discuss this model" : target.kind === "assumption" ? "About this assumption" : "About this issue"} onClose={onClose} className="assumption-conversations-dialog">
    <div className="assumption-conversations">
      <section className="conversation-target" data-card-role="research" aria-label="Selected scientific question">
        <h3>{selected?.target_label ? selected.target_label === selected.target?.object_id ? humanLabel(selected.target_label) : selected.target_label : target.label || humanLabel(target.object_id)}</h3>
        <p className="note">{target.kind === "project_context" ? `Project-wide context revision ${displayedTarget.context_revision} · brief revision ${displayedTarget.brief_revision}` : <>{selected?.method_label || target.methodLabel || humanLabel(target.branch)}{methodVersion != null && methodVersion !== "" ? ` · Model version ${methodVersion}` : ""}</>}</p>
        {earlier && <p className="note warn">Earlier source version. This conversation continues with its original saved sources.</p>}
        {target.kind !== "report_section" && (selected?.target_statement || (!earlier && target.statement)) && <ResearchDocument text={selected?.target_statement || target.statement} />}
        {!earlier && target.latex && <MathText latex={target.latex} />}
        {displayedTarget.goal_source_ref && <SourceRef reference={displayedTarget.goal_source_ref} onOpen={onSource} label="Exact goal source" />}
        {!["p4_pause", "researcher_pause", "project_context"].includes(displayedTarget.kind) && <SourceRef reference={displayedTarget} onOpen={onSource} label={target.kind === "report_section" ? "Read this report version" : target.kind === "assumption" ? "Open exact assumption source" : "Read the issue source"} />}
      </section>
      {!isConversationTarget(target) ? <p className="error" role="alert">The exact source for this question is not available. Reopen it from its issue or assumption.</p> : <>
        {target.kind === "report_section" && <ReportSectionComment key={conversationDraftKey(projectId, displayedTarget, "section-comment")} projectId={projectId} target={displayedTarget} />}
        {combined.length > 0 && <section className="conversation-history" data-card-role="history" aria-label="Saved conversations"><div className="section-heading"><h3>Saved conversations</h3><ActionButton action="ask" uiRole="research" onClick={() => selectConversation(null)} aria-pressed={!selected}>New conversation</ActionButton></div>{groups.filter(([, items]) => items.length).map(([label, items]) => <div className="conversation-history-group" key={label}><h4>{label}</h4><ul>{items.map((conversation) => <li key={conversation.assessment_id}><button type="button" className={`conversation-choice${conversation.assessment_id === selectedId ? " selected" : ""}`} aria-pressed={conversation.assessment_id === selectedId} onClick={() => selectConversation(conversation.assessment_id)}><span className="conversation-title">{conversationTitle(conversation)}</span><span className="note">{dateLabel(conversation.created_at || conversation.updated_at)}{conversation.turns?.some(isPendingTurn) ? " · Answering" : ["failed", "cancelled"].includes(conversation.turns?.at(-1)?.state) ? " · Answer incomplete" : ""}{isEarlierConversation(conversation, target) && ` · ${conversation.target.generation_id || "earlier question"}`}</span></button></li>)}</ul></div>)}</section>}
        {selected && <ConversationTranscript conversation={selected} projectId={projectId} onSource={onSource} onRetry={retry} submitting={retrying} />}
        {error && <p className="error" role="alert">{error}</p>}
        <QuestionForm key={conversationDraftKey(projectId, displayedTarget, selected?.assessment_id)} projectId={projectId} target={displayedTarget} conversation={selected} pending={pending || retrying} blockedReason={retryFirst ? "Retry the first question before asking a follow-up, or start a new conversation." : null} onAccepted={acceptedTurn} />
      </>}
    </div>
  </Dialog>;
}
