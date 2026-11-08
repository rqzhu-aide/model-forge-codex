import { explanationRun } from "./phaseWorkflow.js";

// A run's progress does not replace the published scientific account. Label an
// earlier account only when its exact publication and the later run share scope.
export function empiricalPublicationPresentation(record, run, branch) {
  const current = { heading: "Summary", status: null, earlier: false };
  const ref = record?.generation_ref;
  if (!record?.decision_summary || !branch || !ref?.run_id || !ref.package_id
    || ref.branch !== branch || ref.phase !== "P4"
    || record.branch && record.branch !== branch || record.phase && record.phase !== "P4"
    || run?.branch_id !== branch || run.phase !== "P4" || !run.run_id || run.run_id === ref.run_id
    || run.intent === "assessment" || explanationRun(run)) return current;
  const publishedAt = Date.parse(record.published_at);
  const requestedAt = Date.parse(run.created_at);
  if (!Number.isFinite(publishedAt) || !Number.isFinite(requestedAt) || requestedAt <= publishedAt) return current;
  if (run.state === "published") return {
    heading: "Previous completed evaluation", earlier: true,
    status: "A newer evaluation has been published. The findings below still belong to the previous publication.",
  };
  const state = {
    requested: "A new evaluation is requested.",
    running: "A new evaluation is running.",
    validating: "The new evaluation is being checked before publication.",
    correcting: "The new evaluation is being corrected before publication.",
    promoting: "The new evaluation is being prepared for publication.",
    stopping: "The new evaluation is stopping.",
    awaiting_user: "The new evaluation is waiting for your direction.",
    failed: "The new evaluation failed before publication.",
    cancelled: "The new evaluation was cancelled before publication.",
  }[run.state];
  return state ? { heading: "Last completed evaluation", earlier: true,
    status: `${state} The findings below are from the last completed evaluation.` } : current;
}
