import React, { useId } from "react";
import { humanLabel } from "../research";
import { latestScientificAttempt } from "../phaseUiState";
import { ActionButton } from "./Visuals";

const stageLabel = (state) => ({ succeeded: "Delivery accepted", running: "Working", correcting: "Correcting delivery",
  failed: "Work failed", cancelled: "Cancelled", awaiting_user: "Waiting for your direction", pending: "Not started" }[state] || humanLabel(state));
const memberLabel = (state) => ({ accepted: "Accepted", received: "Report received", collecting: "Collecting the report",
  running: "Working", correcting: "Correcting delivery", completed: "Turn completed", failed: "Work failed", cancelled: "Work cancelled",
  awaiting_user: "Waiting for your direction", pending: "Not started" }[state] || humanLabel(state));
const workLabel = (state) => ({ requested: "Work requested", running: "Work in progress", correcting: "Work is being corrected",
  validating: "Checking the completed update", stopping: "Stopping current work", awaiting_user: "Waiting for your direction",
  published: "Update published", assessed: "Assessment saved", failed: "The latest update failed", cancelled: "The latest update was cancelled" }[state] || humanLabel(state));

// Work status, retained-source freshness and scientific conclusions have separate
// owners. This surface only reads work and delivery; phase cards retain the science.
export default function ResearchProgress({ runs = [], run: suppliedRun, phase, branch = "trunk", retained = false, correctionCount = 0, expanded = false, children, onOpenRun, onShowIssues }) {
  const id = useId(); const run = suppliedRun || latestScientificAttempt(runs, phase, branch);
  if (!run && !children && !correctionCount) return null;
  const progress = run?.progress;
  const stoppedRepair = progress?.stages?.some((stage) => stage.repair?.state === "stopped");
  const setupAttention = run?.p4_progress?.attention_kind === "setup";
  const interrupted = ["failed", "cancelled"].includes(run?.state);
  const hasRetained = typeof retained === "object" ? Boolean(retained?.available ?? retained) : Boolean(retained);
  const state = run?.state || (correctionCount ? "awaiting_user" : "unavailable");
  const label = ({ published: "Complete", assessed: "Complete", requested: "Queued", running: "Running", correcting: "Running", validating: "Running", stopping: "Stopping", awaiting_user: "Needs input", failed: "Failed", cancelled: "Stopped", unavailable: "Status unavailable" })[state] || humanLabel(state);
  return <details className="research-progress-strip" data-card-role="progress" data-work-state={state} data-reading-anchor="work-activity" open={expanded}>
    <summary aria-label={`${phase} latest update: ${label}. Activity details`}><span className="work-state-marker" aria-hidden="true" /><span className="research-progress-status" role="status" aria-atomic="true">{label}</span><span className="activity-label">Activity</span></summary>
    <div className="research-activity-body" aria-labelledby={`${id}-heading`}>
    <div className="section-heading"><h2 id={`${id}-heading`}>Activity details</h2>{run && onOpenRun && <ActionButton action="details" variant="link" data-run-origin={`ResearchProgress:1:${run.run_id}`} onClick={(event) => onOpenRun(run.run_id, event.currentTarget)}>{stoppedRepair ? "Review findings and correction" : "Open run history"}</ActionButton>}</div>
    {run && <p className="note">{setupAttention ? "Experiment setup needs attention" : workLabel(run.state)}{hasRetained && run.state !== "published" ? ". Retained results remain available." : "."}</p>}
    {(state === "awaiting_user" || correctionCount > 0) && onShowIssues && <ActionButton action="details" variant="link" onClick={onShowIssues}>{state === "awaiting_user" ? "Review requested input" : "Review interrupted work"}{correctionCount > 0 ? ` (${correctionCount} work correction${correctionCount === 1 ? "" : "s"})` : ""}</ActionButton>}
    {interrupted && <p className="note">{hasRetained ? "This attempt did not replace the retained results." : "This attempt did not publish new results."}</p>}
    {progress?.stages?.length > 0 ? <ol className="research-progress-stages">{progress.stages.map((stage) => <li key={stage.stage_id} data-stage-state={stage.state}>
      <div className="section-heading"><strong>{stage.label}</strong><span className="note">{stage.repair?.state === "stopped" ? "Automatic correction stopped" : setupAttention && stage.state === "awaiting_user" ? "Waiting for setup correction" : stageLabel(stage.state)}</span></div>
      {stage.repair?.message && <p className="note" data-repair-state={stage.repair.state} role={stage.repair.state === "working" ? "status" : undefined}>{stage.repair.message}</p>}
      {stage.parallel && stage.received_accounts != null && <p className="note">{stage.received_accounts} of {stage.total_accounts} member reports received.{stage.state !== "succeeded" && " Delivery checks must pass before this stage is accepted."}</p>}
      {stage.member_detail_available && <ul className="research-progress-members">{stage.members.map((member) => <li key={member.role} data-member-state={member.state}>{member.label}: {setupAttention && member.state === "awaiting_user" ? "Waiting for setup correction" : memberLabel(member.state)}</li>)}</ul>}
      {!stage.member_detail_available && stage.state === "succeeded" && <p className="note">Complete member report details are unavailable for this stage.</p>}
    </li>)}{progress.publication && <li data-stage-state={progress.publication.state}><div className="section-heading"><strong>{progress.publication.label}</strong><span className="note">{progress.publication.state === "completed" ? "Completed" : progress.publication.state === "checking" ? "Delivery checks in progress" : "Pending"}</span></div></li>}</ol>
      : run && <p className="note">Member delivery detail is unavailable for this run. Its recorded work status is shown above.</p>}
    {children}
    </div>
  </details>;
}
