import React, { useId, useRef, useState } from "react";
import { api } from "../api";
import { conversationDraftKey, conversationDrafts, readConversationDraft, saveConversationDraft } from "../assumptionConversations";
import { goalCorrections, goalSourceKey } from "../phaseOneReader";
import { Dialog, ResearchDocument, SourceRef } from "./Shared";
import { ActionButton } from "./Visuals";

export default function ResearchGoalEditor(props) {
  const [selected, setSelected] = useState(props.snapshot);
  const key = `goal-response:${conversationDraftKey(props.projectId, selected.target)}`;
  const earlier = conversationDrafts("goal-response:").filter(item => item.key !== key && item.draft.projectId === props.projectId && item.draft.text?.trim() && item.draft.snapshot);
  return <GoalResponseForm {...props} snapshot={selected} key={key} earlierDrafts={earlier} onRecover={setSelected} />;
}

function GoalResponseForm({ projectId, snapshot, currentContext, currentGoal, onClose, onSaved, onDiscuss, onSource, earlierDrafts, onRecover }) {
  const id = useId(); const lock = useRef(false);
  const { target, context, paragraph } = snapshot;
  const key = `goal-response:${conversationDraftKey(projectId, target)}`;
  const candidates = goalCorrections(context, target.goal_source_ref);
  const cached = useRef(readConversationDraft(key));
  const [itemId, setItemId] = useState(cached.current?.itemId || (candidates.length === 1 ? candidates[0].item_id : ""));
  const [text, setText] = useState(cached.current?.text ?? (candidates.length === 1 ? candidates[0].statement : ""));
  const [busy, setBusy] = useState(false); const [error, setError] = useState(null);
  const [saveRevision, setSaveRevision] = useState(context.revision);
  const remember = (value, selected = itemId) => { setText(value); setItemId(selected); saveConversationDraft(key, { text: value, itemId: selected, projectId, target, snapshot }); };
  const changed = currentContext?.revision !== context.revision || goalSourceKey(currentGoal) !== goalSourceKey(target.goal_source_ref);
  const save = async event => {
    event.preventDefault(); if (lock.current || !text.trim()) return;
    lock.current = true; setBusy(true); setError(null);
    try {
      await api.saveProblemContext(projectId, { expected_revision: saveRevision, item_id: itemId || undefined,
        statement: text.trim(), origin: "researcher_reported", scope: { kind: "project" }, topic: "research_goal", source_refs: [target.goal_source_ref] });
      saveConversationDraft(key, null); onSaved?.(); onClose();
    } catch (failure) { setError(`${failure.message} Your draft is retained.`); }
    finally { lock.current = false; setBusy(false); }
  };
  return <Dialog title="Correct or discuss research goal" busy={busy} onClose={onClose}>
    <details className="research-details"><summary>Lead's goal you are responding to</summary><ResearchDocument text={paragraph} /><SourceRef reference={target.goal_source_ref} onOpen={onSource} label="Exact goal source" /></details>
    {changed && <p className="note" role="status">The project has newer context or a newer goal. This draft remains attached to the goal you opened.</p>}
    {currentContext?.revision !== saveRevision && <details className="research-details contribution-surface"><summary>Review newer saved context before saving</summary>{(currentContext.items || []).filter(item => item.status === "confirmed").map(item => <ResearchDocument key={item.item_id} text={item.statement} />)}<ActionButton action="check" disabled={busy} onClick={() => setSaveRevision(currentContext.revision)}>Use this context revision for saving</ActionButton><p className="hint">Your text and its original goal reference stay unchanged.</p></details>}
    {earlierDrafts.length > 0 && <details className="research-details contribution-surface"><summary>Unsent goal responses ({earlierDrafts.length})</summary>{earlierDrafts.map(({key: draftKey, draft}) => <div key={draftKey}><ResearchDocument text={draft.text} /><ActionButton action="edit" uiRole="system" disabled={busy} onClick={() => onRecover(draft.snapshot)}>Resume response to {draft.target.goal_source_ref.generation_id}</ActionButton></div>)}</details>}
    <form className="contribution-surface" onSubmit={save}>
      {candidates.length > 1 && <div className="field"><label htmlFor={`${id}-existing`}>Saved correction to edit</label><select id={`${id}-existing`} value={itemId} disabled={busy} onChange={event => { const item = candidates.find(row => row.item_id === event.target.value); remember(item?.statement || "", item?.item_id || ""); }}><option value="">Add a separate correction</option>{candidates.map(item => <option key={item.item_id} value={item.item_id}>{item.statement}</option>)}</select></div>}
      <div className="field"><label htmlFor={id}>Your intended research goal or question</label><textarea id={id} rows={4} value={text} disabled={busy} onChange={event => remember(event.target.value)} /></div>
      <p className="hint">Save keeps your words for future work. Discuss asks the Lead about this exact goal. Earlier research keeps its original interpretation.</p>
      <div className="btnrow"><ActionButton action="save" uiRole="research" variant="primary" type="submit" disabled={busy || !text.trim()}>Save correction</ActionButton><ActionButton action="ask" uiRole="research" disabled={busy || !text.trim()} onClick={() => { saveConversationDraft(conversationDraftKey(projectId, target), { text, idempotencyKey: globalThis.crypto.randomUUID() }); onClose(); onDiscuss(target); }}>Discuss</ActionButton></div>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  </Dialog>;
}
