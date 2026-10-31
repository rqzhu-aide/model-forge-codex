import React, { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import { conversationDraftKey, conversationDrafts, conversationTitle, readConversationDraft, saveConversationDraft } from "../assumptionConversations";
import { humanLabel } from "../research";
import { goalSourceKey } from "../phaseOneReader";
import { answerContextOwner, contextApplies } from "../researcherDialogue";
import { answerMatchesIssue } from "../phaseWorkflow";
import { issueCardEntries } from "../phaseUiState";
import { phaseQuestionAnchor } from "../phaseInputSummary";
import { navigatePhaseInput, phaseInputDestination } from "../phaseInputNavigation";
import IssuesCard from "./IssuesCard";
import WorkflowAdoption from "./WorkflowAdoption";
import { ResearchDocument, SourceRef } from "./Shared";
import { ActionButton } from "./Visuals";
import { NotationLookup } from "./SharedNotation";
import { notationCorrectionApplies, notationCorrectionSource } from "../sharedNotation";

const origins = { researcher_reported: "Researcher reported", evidence_supported: "Evidence supported", proposed_assumption: "Proposed assumption", unknown: "Unknown" };

function ContextStatement({ item, owner, onReviewAnswer, onSource, projectId, context, target, onSaved, onDiscuss, activeWork, goalReference }) {
  const [editing, setEditing] = useState(false);
  const savedGoal = item.source_refs?.find(ref => ref.kind === "research_goal");
  const notationSource = notationCorrectionSource(item);
  if (notationSource) return <div className="dialogue-context-item contribution-surface" data-reading-anchor={`problem-context:${item.item_id}:${item.revision}`}>
    <ResearchDocument text={item.statement} />
    <p className="note">Saved notation correction for future work. The account retains its original definition.</p>
    <NotationLookup record={{ generation_ref: notationSource, _notation_available: true }} entryId={notationSource.entry_id} onSource={onSource} label="Review notation correction" />
  </div>;
  if (owner) return <div className="dialogue-context-item" data-reading-anchor={`problem-context:${item.item_id}:${item.revision}`}>
    {owner.question_ref?.phase && <ActionButton action="details" uiRole="research" onClick={event => onReviewAnswer(owner, event.currentTarget)}>Review your answer{item.topic ? `: ${item.topic}` : ""}</ActionButton>}
    <details className="research-details"><summary>View the saved copy of your answer</summary><ResearchDocument text={item.statement} /><p className="note">Your answer is edited at its original question.{!owner.question_ref?.phase && " Its original question link is unavailable; this copy remains available to read."}</p></details>
  </div>;
  return <div className="dialogue-context-item contribution-surface" data-reading-anchor={`problem-context:${item.item_id}:${item.revision}`}>
    <ResearchDocument text={item.statement} />
    {savedGoal && <p className="note">Research goal correction · {goalReference ? goalSourceKey(savedGoal) === goalSourceKey(goalReference) ? "current published goal" : "earlier published goal" : "published goal status unavailable"}. The source below identifies the goal this response addresses.</p>}
    <p className="note">{origins[item.origin] || humanLabel(item.origin)}{item.topic === "expectation" ? " · Expectation" : ""} · {item.scope?.kind === "model" ? `This model only${item.scope.model_ref?.version != null ? ` · version ${item.scope.model_ref.version}` : ""}` : "Across models"} · revision {item.revision}</p>
    {(item.source_refs || []).map((reference, index) => <SourceRef key={index} reference={reference.generation_ref || reference} onOpen={onSource} />)}
    {target && <ActionButton action="edit" uiRole="research" onClick={() => setEditing((value) => !value)} aria-expanded={editing}>Edit your note</ActionButton>}
    {editing && <ContextResponse key={item.revision} projectId={projectId} context={context} target={{ ...target, object_id: item.item_id, ...(item.topic === "research_goal" && item.source_refs?.find(ref => ref.kind === "research_goal") ? { goal_source_ref: item.source_refs.find(ref => ref.kind === "research_goal") } : {}) }} item={item} onSaved={() => { setEditing(false); onSaved?.(); }} onDiscuss={onDiscuss} activeWork={activeWork} />}
  </div>;
}

function ContextResponse({ projectId, context, target, item, onSaved, onDiscuss, activeWork }) {
  const id = useId(); const key = `problem-response:${conversationDraftKey(projectId, target)}`;
  const cached = useRef(readConversationDraft(key));
  const [text, setText] = useState(cached.current?.text ?? item?.statement ?? "");
  const [origin, setOrigin] = useState(cached.current?.origin || (item?.origin === "unknown" ? "unknown" : "researcher_reported"));
  const [topic, setTopic] = useState(cached.current?.topic ?? item?.topic ?? "");
  const [busy, setBusy] = useState(false); const lock = useRef(false);
  const [error, setError] = useState(null); const [notice, setNotice] = useState(null);
  const update = (value, nextOrigin = origin, nextTopic = topic) => { setText(value); setOrigin(nextOrigin); setTopic(nextTopic); saveConversationDraft(key, { text: value, origin: nextOrigin, topic: nextTopic, projectId, target, item }); setNotice(null); };
  const save = async (event) => {
    event.preventDefault(); if (lock.current || !text.trim()) return;
    lock.current = true; setBusy(true); setError(null); setNotice(null);
    try {
      await api.saveProblemContext(projectId, { expected_revision: context.revision, statement: text.trim(), item_id: item?.item_id, origin, scope: item?.scope || { kind: "project" }, topic: topic || (item?.topic ? "context" : undefined), ...(item?.source_refs ? { source_refs: item.source_refs } : {}) });
      saveConversationDraft(key, null); setText(""); setOrigin("researcher_reported"); setTopic("");
      setNotice("Your note is saved. I’ll use it in future work within its recorded scope."); onSaved?.();
    } catch (failure) { setError(`${failure.message} Your draft is retained for context revision ${context.revision}.`); }
    finally { lock.current = false; setBusy(false); }
  };
  return <details className="research-details dialogue-response" open={item ? true : undefined} data-reading-anchor={`problem-response:${target.context_revision}:${target.brief_revision}:${target.object_id || "project"}`}>
    <summary>{item ? "Edit your saved note" : "Ask me a question or give me more information"}</summary>
    <form className="contribution-surface" onSubmit={save}>
      <div className="field"><label htmlFor={id}>Your problem, collection process, expectations, or correction</label><textarea id={id} rows={3} value={text} disabled={busy} onChange={(event) => update(event.target.value)} placeholder="Use your own words. A conceptual problem or unknown setting is enough to begin." aria-describedby={`${id}-hint`} /></div>
      <div className="field"><label htmlFor={`${id}-topic`}>What your note describes (optional)</label><select id={`${id}-topic`} data-ui-role="research" value={topic} disabled={busy} onChange={(event) => update(text, origin, event.target.value)}><option value="">Other information</option><option value="expectation">Expectation or desired behavior</option>{topic && topic !== "expectation" && <option value={topic}>{humanLabel(topic)}</option>}</select></div>
      <div className="btnrow dialogue-answer-choices"><ActionButton action="edit" uiRole="research" disabled={busy} onClick={() => update("This information remains unknown.", "unknown")}>Not sure yet</ActionButton><ActionButton action="edit" uiRole="research" disabled={busy} onClick={() => update("No data yet.", "researcher_reported")}>No data yet</ActionButton><label className="check-label"><input type="checkbox" checked={origin === "unknown"} disabled={busy} onChange={(event) => update(text, event.target.checked ? "unknown" : "researcher_reported")} />This remains unknown</label></div>
      <p className="hint" id={`${id}-hint`}>Save retains your original words {item?.scope?.kind === "model" ? "for this exact model" : "across models"}. Discuss asks the Research Lead for an explanation. Neither action changes a model or establishes an assumption.{activeWork ? " Work in progress retains its captured context." : ""}</p>
      <div className="btnrow"><ActionButton action="save" uiRole="research" variant="primary" type="submit" disabled={busy || !text.trim()}>{busy ? "Saving…" : "Save your note"}</ActionButton><ActionButton action="ask" uiRole="research" disabled={busy} aria-haspopup="dialog" onClick={() => { if (text.trim()) saveConversationDraft(conversationDraftKey(projectId, target), { text, idempotencyKey: globalThis.crypto.randomUUID() }); onDiscuss(target); }}>Discuss with me</ActionButton></div>
      {error && <p className="error" role="alert">{error}</p>}{notice && <p className="note" role="status">{notice}</p>}
    </form>
  </details>;
}

function ProposedUnderstanding({ projectId, proposal, revision, onSaved }) {
  const id = useId(); const [statement, setStatement] = useState(proposal.item?.statement || "");
  const [busy, setBusy] = useState(false); const lock = useRef(false); const [error, setError] = useState(null);
  const confirm = async (event) => {
    event.preventDefault(); if (lock.current || !statement.trim()) return;
    lock.current = true; setBusy(true); setError(null);
    try { await api.confirmProblemContext(projectId, proposal.amendment_id, { expected_revision: revision, statement: statement.trim() }); onSaved?.(); }
    catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  };
  return <form className="dialogue-proposal" data-reading-anchor={`proposed-understanding:${proposal.amendment_id}`} onSubmit={confirm}>
    <div className="team-context-band">
      <h3>Please check my interpretation</h3><p className="note">Research team interpretation</p><ResearchDocument text={proposal.reason} />
      {proposal.conflicts_with?.length > 0 && <p className="note warn">This proposal identifies a conflict with saved context. The accounts remain separate until you confirm or edit the change.</p>}
    </div>
    <div className="field contribution-surface"><label htmlFor={id}>How I interpreted your input: review or correct it</label><textarea id={id} rows={3} value={statement} onChange={(event) => setStatement(event.target.value)} disabled={busy} /></div>
    <p className="hint">{proposal.item?.scope?.kind === "model" ? "Applies only to the identified model." : "Applies across models."} Confirmation accepts this account of your setting; it does not prove a statistical assumption.</p>
    <ActionButton action="save" uiRole="research" variant="primary" type="submit" disabled={busy || !statement.trim()}>{busy ? "Saving…" : "Confirm interpretation"}</ActionButton>{error && <p className="error" role="alert">{error}</p>}
  </form>;
}

export default function ResearcherDialogue({ problemContext, contextAnswers, project, catalogPreview, modelRef, admittedRecords, admittedNotation, conversations = [], activeWork = false, onDiscuss, onSaved, onSource, goalReference, ...issueProps }) {
  const [notice, setNotice] = useState(null);
  const [answerVisit, setAnswerVisit] = useState(null);
  const answerVisitRef = useRef(null);
  const visitScope = JSON.stringify([issueProps.projectId, issueProps.phase, issueProps.branch, modelRef]);
  const visitScopeRef = useRef(visitScope); visitScopeRef.current = visitScope;
  useEffect(() => { answerVisitRef.current?.dispose(); answerVisitRef.current = null; setAnswerVisit(null); return () => answerVisitRef.current?.dispose(); }, [visitScope]);
  const editorBasis = useRef(null); const [, refreshEditor] = useState(0);
  const saved = () => { setNotice("Your note is saved. I’ll use it in future work; earlier work keeps its original input."); onSaved?.(); };
  const context = problemContext;
  const target = context?.dialogue_target && { ...context.dialogue_target, phase: "P1", branch: "trunk", label: "Your problem and data", responsible_role: "research_lead" };
  const previousDraft = editorBasis.current && readConversationDraft(`problem-response:${conversationDraftKey(issueProps.projectId, editorBasis.current.target)}`);
  if (target && (!editorBasis.current || !previousDraft?.text?.trim())) editorBasis.current = { target, context };
  const editor = editorBasis.current;
  const changedWhileWriting = editor && target && conversationDraftKey(issueProps.projectId, editor.target) !== conversationDraftKey(issueProps.projectId, target);
  const notationScope = { phase: issueProps.phase, branch: issueProps.branch, modelRef, admittedRecords, admittedNotation };
  const items = (context?.items || []).filter((item) => item.status === "confirmed" && contextApplies(item.scope, issueProps.branch, modelRef) && notationCorrectionApplies(item, notationScope));
  const ownerAnswers = contextAnswers ?? issueProps.answers;
  const copies = items.filter(item => answerContextOwner(item, ownerAnswers));
  const notes = items.filter(item => !answerContextOwner(item, ownerAnswers));
  const reviewAnswer = (owner, origin) => {
    const root = origin.closest('[data-reader-ready]');
    const projected = issueCardEntries({ ...issueProps, modelRef });
    const earlier = projected.earlierAnswers.map(answer => ({ ...answer.attention, attention_id: answer.attention?.attention_id || answer.attention_id, explanation_target: answer.attention?.explanation_target || answer.question_ref }));
    const issue = [...projected.entries, ...earlier].find(issue => answerMatchesIssue({ ...owner, revision: owner.answer_revision }, issue));
    const source = owner.question_ref;
    const anchor = issue ? phaseQuestionAnchor(issue) : source?.kind === "researcher_pause" ? `researcher-pause:${source.run_id}:${source.request_id}:${source.revision}` : source?.kind === "p4_pause" ? `evaluation-pause:${source.run_id}:${source.request_id}:${source.revision}` : null;
    if (anchor && phaseInputDestination(root, anchor)) {
      answerVisitRef.current?.dispose();
      const visit = navigatePhaseInput({ root, origin, anchor, scope: visitScope, currentScope: () => visitScopeRef.current, onUnavailable: setNotice });
      answerVisitRef.current = visit; setAnswerVisit(visit);
    } else if (!source?.phase || !issueProps.onNavigate?.(source.phase, source)) setNotice("This answer belongs to an earlier question or run. Its saved copy is available below; open that phase’s run history to review the original request.");
  };
  const proposals = (context?.proposals || []).filter((item) => item.status === "pending" && contextApplies(item.item?.scope, issueProps.branch, modelRef) && notationCorrectionApplies(item.item, notationScope));
  const history = conversations.filter((item) => item.assessment_purpose === "project_context");
  const earlierDrafts = conversationDrafts("problem-response:").filter(({ draft }) => draft.projectId === issueProps.projectId && draft.text?.trim() && draft.target?.sha256 !== target?.sha256 && conversationDraftKey(issueProps.projectId, draft.target) !== (editor && conversationDraftKey(issueProps.projectId, editor.target)));
  const content = <div className="researcher-dialogue" data-reading-anchor="researcher-dialogue">
    <h3>What you told me</h3>
    {copies.length > 0 && <details className="research-details"><summary>Your answers to my questions</summary><p className="note">Your answers stay with their original questions. You do not need to enter them again.</p>{copies.map(item => <ContextStatement key={item.item_id} item={item} owner={answerContextOwner(item, ownerAnswers)} onReviewAnswer={reviewAnswer} />)}</details>}
    {notes.length ? <><h3>Other information you gave me</h3>{notes.slice(0, 2).map((item) => <ContextStatement goalReference={goalReference} key={`${item.item_id}:${item.revision}`} item={item} onSource={onSource} projectId={issueProps.projectId} context={context} target={target} onSaved={saved} onDiscuss={onDiscuss} activeWork={activeWork} />)}{notes.length > 2 && <details className="research-details"><summary>More information you gave me ({notes.length - 2})</summary>{notes.slice(2).map((item) => <ContextStatement goalReference={goalReference} key={`${item.item_id}:${item.revision}`} item={item} onSource={onSource} projectId={issueProps.projectId} context={context} target={target} onSaved={saved} onDiscuss={onDiscuss} activeWork={activeWork} />)}</details>}</> : <p className="note">You have not added separate notes. You can tell me more about your problem, data or expectations here. Data are optional; you can leave unknowns unresolved. Your answers to my questions are saved separately.</p>}
    {changedWhileWriting && <p className="note" role="status">Your saved input changed while you were writing. Your draft remains attached to context revision {editor.target.context_revision}. <ActionButton action="edit" uiRole="system" onClick={() => { editorBasis.current = { target, context }; refreshEditor((value) => value + 1); }}>Use your latest saved input</ActionButton> keeps this draft under earlier responses.</p>}
    {target && editor && <ContextResponse key={conversationDraftKey(issueProps.projectId, editor.target)} projectId={issueProps.projectId} context={editor.context} target={editor.target} onSaved={saved} onDiscuss={onDiscuss} activeWork={activeWork} />}
    {notice && <p className="note" role="status">{notice}</p>}
    {!target && <p className="note">Project-context dialogue becomes available when this project adopts the revised workflow. Earlier questions and their exact sources remain below.</p>}
    <WorkflowAdoption projectId={issueProps.projectId} catalog={catalogPreview} onSaved={() => { setNotice("Updated workflow adopted. Earlier research records, conversations, and historical manuscripts are retained."); onSaved?.(); }} />
    {proposals.map((proposal) => answerContextOwner(proposal.item, ownerAnswers) ? <div key={proposal.amendment_id}><p className="note">This earlier interpretation concerns a saved answer. Review it at the original question.</p><ContextStatement item={proposal.item} owner={answerContextOwner(proposal.item, ownerAnswers)} onReviewAnswer={reviewAnswer} /></div> : <ProposedUnderstanding key={proposal.amendment_id} projectId={issueProps.projectId} proposal={proposal} revision={context.revision} onSaved={saved} />)}
    {earlierDrafts.length > 0 && <details className="research-details"><summary>Unsent responses to earlier context ({earlierDrafts.length})</summary><p className="note">These drafts remain attached to their original revisions. Review your latest saved input before saving a change to it.</p>{earlierDrafts.map(({ key, draft }) => <div key={key}><p className="note">Context revision {draft.target.context_revision} · brief revision {draft.target.brief_revision}</p>{answerContextOwner(draft.item, ownerAnswers) ? <><p className="note">Your unsent draft is retained below. To change the saved answer, return to its original question.</p><ResearchDocument text={draft.text} /><ContextStatement item={draft.item} owner={answerContextOwner(draft.item, ownerAnswers)} onReviewAnswer={reviewAnswer} /></> : <ContextResponse projectId={issueProps.projectId} context={{ revision: draft.target.context_revision }} target={draft.target} item={draft.item} onSaved={saved} onDiscuss={onDiscuss} activeWork={activeWork} />}</div>)}</details>}
    {history.length > 0 && <details className="research-details dialogue-history"><summary>Earlier problem conversations ({history.length})</summary><p className="note">Available across phases and models. Each discussion keeps its original context revision.</p>{history.map((conversation) => <div key={conversation.assessment_id}><ActionButton action="ask" uiRole="system" aria-haspopup="dialog" onClick={() => onDiscuss({ ...conversation.target, phase: "P1", branch: "trunk", label: "Your problem and data", conversationId: conversation.assessment_id })}>{conversationTitle(conversation)}</ActionButton><p className="note">Context revision {conversation.target?.context_revision} · brief revision {conversation.target?.brief_revision}</p></div>)}</details>}
  </div>;
  const compact = ["P1", "P2"].includes(issueProps.phase);
  return <><IssuesCard {...issueProps} modelRef={modelRef} onSaved={onSaved} onSource={onSource} questionsOnly={compact} title="Decisions to Discuss" intro={compact ? <details className="research-details" data-reading-anchor="problem-understanding"><summary>What you told me</summary>{content}</details> : content} progressive />{answerVisit && createPortal(<ActionButton action="back" onClick={() => { answerVisit.back(); setAnswerVisit(null); }}>Back to what you told me</ActionButton>, answerVisit.target)}</>;
}
