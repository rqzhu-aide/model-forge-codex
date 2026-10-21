import React, { useId } from "react";
import { ResearchDocument, SourceRef } from "./Shared";
import PhaseTwoInstructions from "./PhaseTwoInstructions";
import { ActionButton } from "./Visuals";

export default function PhaseTwoPreparation({ basis, instructions, onInstructionsChange, onLaunch, onSource, onSave, ready = true, saving = false, dirty = false, updatedAt, error, onRetry }) {
  const id = useId();
  const preparation = basis?.phase2_preparation;
  const supplied = preparation?.supplied_method;
  return <section className="card phase-two-preparation" data-card-role="action" aria-labelledby={`${id}-heading`}>
    <div className="card-heading"><h2 id={`${id}-heading`}>Notes from Phase 1</h2></div>
    <div className="body">
      {preparation?.instructions_markdown ? <><p className="note">Research Lead · published Phase 1 notes for model development</p><ResearchDocument text={preparation.instructions_markdown} /><SourceRef reference={basis.generation_ref} onOpen={onSource} label="Phase 1 notes source" /></> : <p className="note">No model development notes have been published in Phase 1 yet.</p>}
      {!ready && !error && <p className="note" role="status">Loading saved Phase 2 instructions…</p>}
      <PhaseTwoInstructions id={`${id}-instructions`} value={instructions} onChange={onInstructionsChange} disabled={!ready || saving} suppliedMethod={supplied} onSource={onSource} />
      {error && <p className="error" role="alert">{error} {!ready && <ActionButton action="retry" variant="link" onClick={onRetry}>Retry loading instructions</ActionButton>}</p>}
      {onSave && <div className="btnrow"><ActionButton action="save" uiRole="research" disabled={!ready || saving || !dirty} onClick={onSave}>{saving ? "Saving…" : "Save instructions"}</ActionButton><span className="note" role="status">{dirty ? "Unsaved changes. Preparing a run uses the text above." : updatedAt ? "Saved for future Phase 2 runs. These are your instructions to the lead." : "Save these instructions to keep them between visits."}</span></div>}
      {instructions?.trim() && <details className="research-details contribution-surface"><summary>Preview your Phase 2 instructions</summary><ResearchDocument text={instructions} /></details>}
      <div className="btnrow"><ActionButton action="run" uiRole="research" variant="primary" disabled={!ready || saving} onClick={() => onLaunch("P2", { mode: "p2.full_catalog", title: "Develop models in Phase 2", instructions, supplied_method: supplied || undefined })}>Prepare Phase 2 run</ActionButton><span className="note">Review the inputs before starting.</span></div>
    </div>
  </section>;
}
