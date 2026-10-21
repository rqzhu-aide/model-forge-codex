import React, { useRef, useState } from "react";
import { humanLabel } from "../research";
import { adoptWorkflow, canAdoptWorkflow } from "../workflowAdoption";
import { ActionButton } from "./Visuals";

export function WorkflowAdoptionReview({ catalog, busy = false, error, onAdopt, reviewRef }) {
  if (!catalog?.upgrade_available) return null;
  return <details ref={reviewRef} className="research-details" data-reading-anchor="workflow-adoption">
    <summary>Review updated workflow</summary>
    <p className="note">Apply the offered workflow to future work in this project. Earlier scientific records, conversations, and reports retain their original sources and workflow.</p>
    <p className="note">Current workflow: {catalog.version || "Version not recorded"}. Offered workflow: {catalog.available_version || "Version not recorded"}.</p>
    {!canAdoptWorkflow(catalog) && <><p className="note">{catalog.blocked_runs?.length ? "Finish or cancel active or paused work before adopting the updated workflow." : "Adoption is currently unavailable. Refresh this project's workflow status before trying again."}</p>{catalog.blocked_runs?.length > 0 && <ul className="research-items">{catalog.blocked_runs.map((run) => <li key={run.run_id}><span className="identity-line">{run.run_id}</span> · {humanLabel(run.state)}</li>)}</ul>}</>}
    <ActionButton action="continue" variant="primary" disabled={busy || !canAdoptWorkflow(catalog)} onClick={onAdopt}>{busy ? "Adopting…" : "Adopt updated workflow"}</ActionButton>
    {busy && <p className="note" role="status">Adopting the reviewed workflow. Your research context stays open.</p>}
    {error && <p className="error" role="alert">{error}</p>}
  </details>;
}

export default function WorkflowAdoption({ projectId, catalog, onSaved }) {
  const lock = useRef(false); const review = useRef(null); const [busy, setBusy] = useState(false); const [error, setError] = useState(null);
  return <WorkflowAdoptionReview reviewRef={review} catalog={catalog} busy={busy} error={error} onAdopt={() => adoptWorkflow({ projectId, catalog, lock, review: review.current, onBusy: setBusy, onError: setError, onSaved })} />;
}
