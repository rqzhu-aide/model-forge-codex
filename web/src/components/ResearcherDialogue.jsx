import React, { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import { conversationDraftKey, conversationDrafts, conversationTitle, readConversationDraft, saveConversationDraft } from "../assumptionConversations";
import { humanLabel } from "../research";
import { goalSourceKey } from "../phaseOneReader";
import { answerContextOwner, contextApplies, contextAttribution } from "../researcherDialogue";
import { answerEffect, answerMatchesIssue, issueLabel } from "../phaseWorkflow";
import { issueCardEntries } from "../phaseUiState";
import { phaseQuestionAnchor } from "../phaseInputSummary";
import { navigatePhaseInput, phaseInputDestination } from "../phaseInputNavigation";
import IssuesCard from "./IssuesCard";
import WorkflowAdoption from "./WorkflowAdoption";
import { ResearchDocument, ResearchLabel, SourceRef } from "./Shared";
import { ActionButton } from "./Visuals";
import { NotationLookup } from "./SharedNotation";
import { notationCorrectionApplies, notationCorrectionSource } from "../sharedNotation";
import { savedInputProjection, scopedContextNotes } from "../savedInput";
import { decisionSupportSections } from "../researcherDecisions";
import { requestSourceReferences } from "../contextualRequests";
import { DecisionBrief, DecisionOptionsContext } from "./DecisionResponse";
import { CitedRequestDocument } from "./LiteratureCitation";

const origins = { researcher_reported: "Researcher reported", evidence_supported: "Evidence supported", proposed_assumption: "Proposed assumption", unknown: "Unknown" };

function ContextStatement({ item, owner, onReviewAnswer, onSource, projectId, context, target, onSaved, onDiscuss, activeWork, goalReference, onEditorChange, anchored = true }) {
  const [editing, setEditing] = useState(false);
  const editBasis = useRef(null);
  useEffect(() => () => { if (editBasis.current) onEditorChange?.(editBasis.current.item.item_id, false); }, [onEditorChange]);
  const anchor = anchored ? `problem-context:${item.item_id}:${item.revision}` : undefined;
  const attribution = contextAttribution(item, context);
  const researcherAuthored = attribution.author === "researcher";
  const savedGoal = item.goal_source_ref || item.source_refs?.find(ref => ref.kind === "research_goal");
  const sources = [...(item.source_refs || [])];
  if (savedGoal && !sources.some(reference => goalSourceKey(reference) === goalSourceKey(savedGoal))) sources.push(savedGoal);
  const notationSource = notationCorrectionSource(item);
  if (notationSource && researcherAuthored) return <div className="dialogue-context-item contribution-surface" data-reading-anchor={anchor}>
    <ResearchDocument text={item.statement} />
    <p className="note">Saved notation correction for future work. The account retains its original definition.</p>
    <NotationLookup record={{ generation_ref: notationSource, _notation_available: true }} entryId={notationSource.entry_id} onSource={onSource} label="Review notation correction" />
  </div>;
  if (owner) return <div className="dialogue-context-item" data-reading-anchor={anchor}>
    {owner.question_ref?.phase && <ActionButton action="details" uiRole="research" onClick={event => onReviewAnswer(owner, event.currentTarget)}>Review your answer{item.topic ? `: ${item.topic}` : ""}</ActionButton>}
    <details className="research-details"><summary>View the saved copy of your answer</summary><ResearchDocument text={item.statement} /><p className="note">Your answer is edited at its original question.{!owner.question_ref?.phase && " Its original question link is unavailable; this copy remains available to read."}</p></details>
  </div>;
  return <div className={`dialogue-context-item ${researcherAuthored ? "contribution-surface" : "team-context-band"}`} data-reading-anchor={anchor}>
    <ResearchDocument text={item.statement} />
    {!researcherAuthored && <p className="note">{attribution.author === "team" ? "Research team account" : "Source attribution unavailable"}{attribution.confirmedByResearcher ? " · Confirmed by you" : ""}</p>}
    {savedGoal && <p className="note">Research goal correction · {goalReference ? goalSourceKey(savedGoal) === goalSourceKey(goalReference) ? "current published goal" : "earlier published goal" : "published goal status unavailable"}. The source below identifies the goal this response addresses.</p>}
    <p className="note">{origins[item.origin] || humanLabel(item.origin)}{item.topic === "expectation" ? " · Expectation" : ""} · {item.scope?.kind === "model" ? `This model only${item.scope.model_ref?.version != null ? ` · version ${item.scope.model_ref.version}` : ""}` : "Across models"} · revision {item.revision}</p>
    {sources.map((reference, index) => <SourceRef key={index} reference={reference.generation_ref || reference} onOpen={onSource} />)}
    {target && <ActionButton action="edit" uiRole="research" onClick={() => { if (!editing) editBasis.current = { item, context, target: { ...target, object_id: item.item_id, ...(savedGoal ? { goal_source_ref: savedGoal } : {}) } }; onEditorChange?.(item.item_id, !editing); setEditing(value => !value); }} aria-expanded={editing}>{researcherAuthored ? "Edit your note" : "Correct this account"}</ActionButton>}
    {editing && editBasis.current && <>{item.revision !== editBasis.current.item.revision && <p className="note" role="status">{researcherAuthored ? "Your saved note" : "This account"} changed while you were editing. Your draft is kept with its original saved version.</p>}<ContextResponse projectId={projectId} context={editBasis.current.context} target={editBasis.current.target} item={editBasis.current.item} correction={!researcherAuthored} onSaved={() => { onEditorChange?.(item.item_id, false); setEditing(false); onSaved?.(); }} onDiscuss={onDiscuss} activeWork={activeWork} /></>}
  </div>;
}

function ContextResponse({ projectId, context, target, item, correction = false, onSaved, onDiscuss, activeWork, currentComposer = false, readingAnchor }) {
  const id = useId(); const key = `problem-response:${conversationDraftKey(projectId, target)}`;
  const cached = useRef(readConversationDraft(key));
  const [text, setText] = useState(cached.current?.text ?? item?.statement ?? "");
  const [origin, setOrigin] = useState(cached.current?.origin || (item?.origin === "unknown" ? "unknown" : "researcher_reported"));
  const [topic, setTopic] = useState(cached.current?.topic ?? item?.topic ?? "");
  const [busy, setBusy] = useState(false); const lock = useRef(false);
  const [error, setError] = useState(null); const [notice, setNotice] = useState(null);
  const correctionChanged = !correction || text.trim() !== (item?.statement || "").trim()
    || origin !== (item?.origin === "unknown" ? "unknown" : "researcher_reported");
  const update = (value, nextOrigin = origin, nextTopic = topic) => { setText(value); setOrigin(nextOrigin); setTopic(nextTopic); saveConversationDraft(key, { text: value, origin: nextOrigin, topic: nextTopic, projectId, target, item }); setNotice(null); };
  const save = async (event) => {
    event.preventDefault(); if (lock.current || !text.trim() || !correctionChanged) return;
    lock.current = true; setBusy(true); setError(null); setNotice(null);
    try {
      await api.saveProblemContext(projectId, { expected_revision: context.revision, statement: text.trim(), item_id: item?.item_id, origin, scope: item?.scope || { kind: "project" }, topic: topic || (item?.topic ? "context" : undefined), ...(item?.source_refs ? { source_refs: item.source_refs } : {}) });
      saveConversationDraft(key, null); setText(""); setOrigin("researcher_reported"); setTopic("");
      setNotice("Your note is saved. I’ll use it in future work within its recorded scope."); onSaved?.();
    } catch (failure) { setError(`${failure.message} Your draft is retained for context revision ${context.revision}.`); }
    finally { lock.current = false; setBusy(false); }
  };
  return <details className="research-details dialogue-response" open={item ? true : undefined} data-reading-anchor={readingAnchor || (currentComposer ? "researcher-dialogue" : `problem-response:${target.context_revision}:${target.brief_revision}:${target.object_id || "project"}`)}>
    <summary>{item ? correction ? "Your correction to this account" : "Edit your saved note" : "Add a note or ask a question"}</summary>
    <form className="contribution-surface" onSubmit={save}>
      <div className="field"><label htmlFor={id}>{correction ? "Your correction" : "Your problem, collection process, expectations, or correction"}</label><textarea id={id} rows={3} value={text} disabled={busy} onChange={(event) => update(event.target.value)} placeholder="Use your own words. A conceptual problem or unknown setting is enough to begin." aria-describedby={`${id}-hint`} /></div>
      <div className="field"><label htmlFor={`${id}-topic`}>What your note describes (optional)</label><select id={`${id}-topic`} data-ui-role="research" value={topic} disabled={busy} onChange={(event) => update(text, origin, event.target.value)}><option value="">Other information</option><option value="expectation">Expectation or desired behavior</option>{topic && topic !== "expectation" && <option value={topic}>{humanLabel(topic)}</option>}</select></div>
      <div className="btnrow dialogue-answer-choices"><ActionButton action="edit" uiRole="research" disabled={busy} onClick={() => update("This information remains unknown.", "unknown")}>Not sure yet</ActionButton><ActionButton action="edit" uiRole="research" disabled={busy} onClick={() => update("No data yet.", "researcher_reported")}>No data yet</ActionButton><label className="check-label"><input type="checkbox" checked={origin === "unknown"} disabled={busy} onChange={(event) => update(text, event.target.checked ? "unknown" : "researcher_reported")} />This remains unknown</label></div>
      <p className="hint" id={`${id}-hint`}>{correction ? "Save records your correction as researcher input, with the original sources retained " : "Save retains your original words "}{item?.scope?.kind === "model" ? "for this exact model" : "across models"}. Data are optional; you can leave unknowns unresolved. Discuss asks the Research Lead for an explanation. Neither action changes a model or establishes an assumption.{activeWork ? " Work in progress retains its captured context." : ""}</p>
      <div className="btnrow"><ActionButton action="save" uiRole="research" variant="primary" type="submit" disabled={busy || !text.trim() || !correctionChanged}>{busy ? "Saving…" : correction ? "Save your correction" : "Save your note"}</ActionButton><ActionButton action="ask" uiRole="research" disabled={busy} aria-haspopup="dialog" onClick={() => { if (text.trim()) saveConversationDraft(conversationDraftKey(projectId, target), { text, idempotencyKey: globalThis.crypto.randomUUID() }); onDiscuss(target); }}>Discuss with me</ActionButton></div>
      {error && <p className="error" role="alert">{error}</p>}{notice && <p className="note" role="status">{notice}</p>}
    </form>
  </details>;
}

function SavedAnswer({ item, onReviewAnswer, onSource }) {
  const issue = item.issue;
  const answer = item.answer;
  const source = item.source;
  const canReview = source?.phase && (!item.readonly || ["researcher_pause", "p4_pause"].includes(source.kind) && source.run_id && source.request_id && source.revision != null);
  return <div className="saved-input-answer">
    <h4>Your saved answer</h4><ResearchDocument text={answer?.note || item.contextItem?.statement} />
    {(answer?.origin || item.contextItem?.origin) === "unknown" && <p className="note">Still unknown. This response does not settle the question.</p>}
    {item.scope && <p className="note">{item.scope.kind === "model" ? `This model only${item.scope.model_ref?.version != null ? ` · version ${item.scope.model_ref.version}` : ""}` : "Across models"}</p>}
    {answer && <p className="note">{answerEffect(answer)}</p>}
    {canReview ? <ActionButton action="details" uiRole="research" className="saved-input-origin" data-phase-input-origin={`saved-input-review:${item.key}`} onClick={event => onReviewAnswer({ ...answer, ...item.owner, question_ref: source }, event.currentTarget, issue)}>Review at original question</ActionButton> : <p className="note">The original question link is unavailable. This saved copy remains available to read.</p>}
    {(issue || source?.generation_id) && <details className="research-details"><summary>Original question and sources</summary>
      {issue && <><CitedRequestDocument item={issue} text={issue.question || issueLabel(issue)} section="question" onSource={onSource} /><DecisionBrief item={issue} onSource={onSource} headingLevel={5} /><DecisionOptionsContext item={issue} id={`saved-${item.key}`} onSource={onSource} />
        {decisionSupportSections(issue).map(({ heading, text, section }) => <section key={section}><h5>{heading}</h5><CitedRequestDocument item={issue} text={text} section={section} onSource={onSource} /></section>)}
      </>}
      {source?.generation_id && <SourceRef reference={source} onOpen={onSource} label="Read the original question source" />}
      {issue && requestSourceReferences(issue).map(({ reference, label }, index) => <SourceRef key={index} reference={reference} label={label} onOpen={onSource} />)}
    </details>}
    {item.earlierAnswers?.length > 0 && <details className="research-details"><summary>Responses to earlier question versions ({item.earlierAnswers.length})</summary><p className="note">Each response keeps its original question and scientific source.</p>{item.earlierAnswers.map(earlier => <details className="research-details" key={earlier.key} data-reading-anchor={earlier.anchor}><summary><ResearchLabel text={earlier.title} /></summary><SavedAnswer item={earlier} onReviewAnswer={onReviewAnswer} onSource={onSource} /></details>)}</details>}
  </div>;
}

function savedGroupCount(group) {
  const counts = [];
  const plural = (count, label) => `${count} ${label}${count === 1 ? "" : "s"}`;
  if (group.answerCount) counts.push(plural(group.answerCount, "answer"));
  if (group.noteCounts.goal) counts.push(plural(group.noteCounts.goal, "goal correction"));
  if (group.noteCounts.notation) counts.push(plural(group.noteCounts.notation, "notation correction"));
  if (group.noteCounts.other) counts.push(plural(group.noteCounts.other, "note"));
  return counts.join(", ");
}

function SavedInputFooter({ groups, contextNotes = [], onReviewAnswer, ...noteProps }) {
  if (!groups.length && !contextNotes.length) return null;
  const contextTitle = contextNotes.some(note => note.attribution.author === "unverified") ? "Recorded research context" : "Research team context";
  return <>
    {contextNotes.length > 0 && <section className="recorded-context-footer" data-reading-anchor="recorded-context" aria-label={contextTitle}>
      <h3>{contextTitle}</h3>
      {contextNotes.map(note => <details className="research-details" key={note.key} data-reading-anchor={note.anchor}>
        <summary>{note.attribution.author === "team" ? origins[note.contextItem.origin] === "Researcher reported" ? "Team interpretation" : origins[note.contextItem.origin] || "Team account" : "Recorded account"}{note.attribution.confirmedByResearcher ? " · confirmed by you" : ""} · {note.scope?.kind === "model" ? "This model only" : "Across models"}</summary>
        <ContextStatement {...noteProps} item={note.contextItem} anchored={false} />
      </details>)}
    </section>}
    {groups.length > 0 && <section className="saved-input-footer" data-reading-anchor="saved-input" tabIndex={-1} aria-label="Your saved input">
    <h3>Your saved input</h3>
    <div className="saved-input-groups">{groups.map(group => <details className="saved-input-group" key={group.key} data-reading-anchor={group.anchor}>
      <summary>{group.label} · {savedGroupCount(group)}</summary>
      <div className="saved-input-items">{group.items.map(item => <details className="saved-input-item" key={item.key} data-reading-anchor={item.anchor}>
        <summary><ResearchLabel className="saved-input-item-title" text={item.title} />{(item.answer?.origin || item.contextItem?.origin) === "unknown" && <> <span className="saved-input-status">Saved · still unknown</span></>}</summary>
        {item.unverifiedPhase && <p className="note">The phase of this saved input is unverified.</p>}
        {item.kind === "answer" ? <SavedAnswer item={item} onReviewAnswer={onReviewAnswer} onSource={noteProps.onSource} /> : <ContextStatement {...noteProps} item={item.contextItem} target={item.readonly ? undefined : noteProps.target} anchored={false} />}
      </details>)}</div>
    </details>)}</div>
  </section>}
  </>;
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
  const [activeNoteEditors, setActiveNoteEditors] = useState([]);
  const noteEditorChanged = useCallback((itemId, editing) => setActiveNoteEditors(current => editing ? current.includes(itemId) ? current : [...current, itemId] : current.filter(id => id !== itemId)), []);
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
  const ownerAnswers = contextAnswers ?? issueProps.answers;
  const savedInput = savedInputProjection({ ...issueProps, modelRef, admittedRecords, admittedNotation, problemContext, contextAnswers: ownerAnswers });
  const contextNotes = scopedContextNotes({ ...issueProps, modelRef, admittedRecords, admittedNotation, problemContext, contextAnswers: ownerAnswers }).filter(note => note.attribution.author !== "researcher");
  const reviewAnswer = (owner, origin, originalQuestion) => {
    const root = origin.closest('[data-reader-ready]');
    const projected = issueCardEntries({ ...issueProps, modelRef });
    const earlier = projected.earlierAnswers.map(answer => ({ ...answer.attention, attention_id: answer.attention?.attention_id || answer.attention_id, explanation_target: answer.attention?.explanation_target || answer.question_ref }));
    const issue = [...projected.entries, ...earlier].find(issue => answerMatchesIssue({ ...owner, revision: owner.answer_revision ?? owner.revision }, issue));
    const source = owner.question_ref;
    const anchor = issue ? phaseQuestionAnchor(issue) : source?.kind === "researcher_pause" ? `researcher-pause:${source.run_id}:${source.request_id}:${source.revision}` : source?.kind === "p4_pause" ? `evaluation-pause:${source.run_id}:${source.request_id}:${source.revision}` : null;
    if (anchor && phaseInputDestination(root, anchor)) {
      answerVisitRef.current?.dispose();
      const visit = navigatePhaseInput({ root, origin, anchor, scope: visitScope, currentScope: () => visitScopeRef.current, onUnavailable: setNotice });
      answerVisitRef.current = visit; setAnswerVisit(visit);
    } else if (!source?.phase || !issueProps.onNavigate?.(source.phase, source, originalQuestion, { origin, savedInput: true })) setNotice("This answer belongs to an earlier question or run. Its saved copy is available below; open that phase’s run history to review the original request.");
  };
  const proposals = (context?.proposals || []).filter((item) => item.status === "pending" && contextApplies(item.item?.scope, issueProps.branch, modelRef) && notationCorrectionApplies(item.item, notationScope));
  const actionableProposals = proposals.filter(proposal => !answerContextOwner(proposal.item, ownerAnswers));
  const history = conversations.filter((item) => item.assessment_purpose === "project_context");
  const contextBasisKey = source => conversationDraftKey(issueProps.projectId, { ...source, object_id: undefined, goal_source_ref: undefined });
  const earlierDrafts = conversationDrafts("problem-response:").filter(({ draft }) => draft.projectId === issueProps.projectId && draft.text?.trim() && !activeNoteEditors.includes(draft.item?.item_id) && contextBasisKey(draft.target) !== contextBasisKey(target) && conversationDraftKey(issueProps.projectId, draft.target) !== (editor && conversationDraftKey(issueProps.projectId, editor.target)));
  const content = <div className="researcher-dialogue dialogue-current-input">
    {proposals.map((proposal) => answerContextOwner(proposal.item, ownerAnswers) ? <div key={proposal.amendment_id} data-reading-anchor={`proposed-understanding:${proposal.amendment_id}`}><p className="note">This earlier interpretation concerns a saved answer. Review it at the original question.</p><ContextStatement anchored={false} item={proposal.item} owner={answerContextOwner(proposal.item, ownerAnswers)} onReviewAnswer={reviewAnswer} /></div> : <ProposedUnderstanding key={proposal.amendment_id} projectId={issueProps.projectId} proposal={proposal} revision={context.revision} onSaved={saved} />)}
    {changedWhileWriting && <p className="note" role="status">Your saved input changed while you were writing. Your draft remains attached to context revision {editor.target.context_revision}. <ActionButton action="edit" uiRole="system" onClick={() => { editorBasis.current = { target, context }; refreshEditor((value) => value + 1); }}>Use your latest saved input</ActionButton> keeps this draft under earlier responses.</p>}
    {target && editor && <ContextResponse currentComposer key={conversationDraftKey(issueProps.projectId, editor.target)} projectId={issueProps.projectId} context={editor.context} target={editor.target} onSaved={saved} onDiscuss={onDiscuss} activeWork={activeWork} />}
    {notice && <p className="note" role="status">{notice}</p>}
    {!target && <p className="note" tabIndex={-1} data-reading-anchor="researcher-dialogue">Project-context dialogue becomes available when this project adopts the revised workflow. Earlier questions and their exact sources remain below.</p>}
    <WorkflowAdoption projectId={issueProps.projectId} catalog={catalogPreview} onSaved={() => { setNotice("Updated workflow adopted. Earlier research records, conversations, and historical manuscripts are retained."); onSaved?.(); }} />
    {earlierDrafts.length > 0 && <details className="research-details"><summary>Unsent responses to earlier context ({earlierDrafts.length})</summary><p className="note">These drafts remain attached to their original revisions. Review your latest saved input before saving a change to it.</p>{earlierDrafts.map(({ key, draft }) => <div key={key}><p className="note">Context revision {draft.target.context_revision} · brief revision {draft.target.brief_revision}</p>{answerContextOwner(draft.item, ownerAnswers) ? <><p className="note">Your unsent draft is retained below. To change the saved answer, return to its original question.</p><ResearchDocument text={draft.text} /><ContextStatement anchored={false} item={draft.item} owner={answerContextOwner(draft.item, ownerAnswers)} onReviewAnswer={reviewAnswer} /></> : <ContextResponse readingAnchor={`problem-draft:${encodeURIComponent(key)}`} projectId={issueProps.projectId} context={{ revision: draft.target.context_revision }} target={draft.target} item={draft.item} correction={Boolean(draft.item && contextAttribution(draft.item, context).author !== "researcher")} onSaved={saved} onDiscuss={onDiscuss} activeWork={activeWork} />}</div>)}</details>}
    {history.length > 0 && <details className="research-details dialogue-history"><summary>Earlier problem conversations ({history.length})</summary><p className="note">Available across phases and models. Each discussion keeps its original context revision.</p>{history.map((conversation) => <div key={conversation.assessment_id}><ActionButton action="ask" uiRole="system" aria-haspopup="dialog" onClick={() => onDiscuss({ ...conversation.target, phase: "P1", branch: "trunk", label: "Your problem and data", conversationId: conversation.assessment_id })}>{conversationTitle(conversation)}</ActionButton><p className="note">Context revision {conversation.target?.context_revision} · brief revision {conversation.target?.brief_revision}</p></div>)}</details>}
  </div>;
  const compact = ["P1", "P2"].includes(issueProps.phase);
  const footer = <SavedInputFooter groups={savedInput.groups} contextNotes={contextNotes} onReviewAnswer={reviewAnswer} goalReference={goalReference} onSource={onSource} projectId={issueProps.projectId} context={context} target={target} onSaved={saved} onDiscuss={onDiscuss} onEditorChange={noteEditorChanged} activeWork={activeWork} />;
  return <><IssuesCard {...issueProps} modelRef={modelRef} onSaved={onSaved} onSource={onSource} questionsOnly={compact} title="Decisions to Discuss" intro={content} footer={footer} decisionSummary pendingInterpretationCount={actionableProposals.length} progressive />{answerVisit && createPortal(<ActionButton action="back" onClick={() => { answerVisit.back(); setAnswerVisit(null); }}>Back to saved input</ActionButton>, answerVisit.target)}</>;
}
