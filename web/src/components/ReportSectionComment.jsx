import React, { useEffect, useId, useRef, useState } from "react";
import { api } from "../api";
import { freshId } from "../research";
import { assumptionSource, conversationDraftKey, readConversationDraft, saveConversationDraft } from "../assumptionConversations";
import { ActionButton } from "./Visuals";
import { ResearchDocument } from "./Shared";
import "../reportSectionComment.css";

export default function ReportSectionComment({ projectId, target }) {
  const source = assumptionSource(target);
  const draftKey = conversationDraftKey(projectId, source, "section-comment");
  const initialDraft = useRef(readConversationDraft(draftKey));
  const [draft, setDraft] = useState(initialDraft.current?.text || "");
  const [saved, setSaved] = useState(null);
  const [expectedRevision, setExpectedRevision] = useState(initialDraft.current?.expectedRevision ?? 0);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);
  const lock = useRef(false);
  const fieldId = useId();
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    api.reportSectionComment(projectId, source).then(({ comment }) => {
      if (!active) return;
      setSaved(comment); setReady(true);
      const retainedDraft = readConversationDraft(draftKey);
      if (retainedDraft && reload === 0) {
        setDraft(retainedDraft.text); setExpectedRevision(retainedDraft.expectedRevision);
        if (retainedDraft.expectedRevision !== (comment?.revision || 0)) { setReady(false); setError("The saved comment changed. Reload the saved version before saving your draft."); }
      } else {
        setExpectedRevision(comment?.revision || 0);
        if (retainedDraft) saveConversationDraft(draftKey, { ...retainedDraft, expectedRevision: comment?.revision || 0 });
        else setDraft(comment?.note || "");
      }
    }).catch(failure => { if (active) setError(failure.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [projectId, draftKey, reload]);
  const update = (text) => {
    setDraft(text); setNotice("");
    saveConversationDraft(draftKey, { text, expectedRevision, draftId: freshId() });
  };
  const save = async (note) => {
    if (lock.current || loading || !ready) return;
    const submittedDraft = JSON.stringify(readConversationDraft(draftKey));
    lock.current = true; setSaving(true); setError(null); setNotice("");
    try {
      const { comment } = await api.saveReportSectionComment(projectId, { target: source, note, expected_revision: expectedRevision });
      setSaved(comment); setDraft(comment?.note || ""); setExpectedRevision(comment?.revision || 0);
      if (JSON.stringify(readConversationDraft(draftKey)) === submittedDraft) saveConversationDraft(draftKey, null);
      setNotice(note ? "Comment saved." : "Comment removed.");
    } catch (failure) { setError(failure.message); if (failure.status === 409) setReady(false); }
    finally { lock.current = false; setSaving(false); }
  };
  const hasSavedComment = Boolean(saved?.note);
  return <details className="research-details report-section-comment contribution-surface" open={initialDraft.current ? true : undefined}>
    <summary>{hasSavedComment ? "Your saved comment" : "Leave a comment"}</summary>
    <form onSubmit={event => { event.preventDefault(); save(draft); }}>
      <div className="field"><label htmlFor={fieldId}>Your comment on this section</label><textarea id={fieldId} rows={3} value={draft} disabled={loading || saving} onChange={event => update(event.target.value)} placeholder="Record an interpretation, concern or change you would like to discuss." /></div>
      <p className="note">One editable comment for this section and report version. The Lead can use your saved comment when you discuss this section.</p>
      {loading && <p className="note" role="status">Loading saved comment…</p>}
      {error && <div className="error" role="alert"><p>{error}</p><ActionButton action="retry" disabled={loading || saving} onClick={() => setReload(value => value + 1)}>Reload saved comment</ActionButton><p className="note">Your draft is kept when the saved version is reloaded.</p></div>}
      {reload > 0 && saved?.note && draft !== saved.note && <details className="research-details"><summary>Latest saved comment</summary><ResearchDocument text={saved.note} /></details>}
      {notice && <p className="note" role="status">{notice}</p>}
      <div className="btnrow"><ActionButton action="save" uiRole="research" type="submit" disabled={loading || !ready || saving || draft === (saved?.note || "")}>{saving ? "Saving…" : "Save comment"}</ActionButton>{hasSavedComment && <ActionButton action="close" uiRole="research" disabled={loading || !ready || saving} onClick={() => save("")}>Remove comment</ActionButton>}</div>
    </form>
  </details>;
}
