// Display only what the recorded event establishes. Commands completing do
// not establish a scientific result; their original records remain inspectable.
const roles = { research_lead: "Research Lead", theorist: "Theorist", data_analyst: "Data Analyst", outside_reviewer: "Outside Reviewer" };
const lifecycle = {
  "run.requested": "Requested work accepted.",
  "run.running": "Work is underway.",
  "run.validating": "Checking the completed work before publication.",
  "run.published": "The research account was published.",
  "run.assessed": "Assessment completed.",
  "run.failed": "The run stopped with a problem. Review the findings and correction options.",
  "run.cancelled": "The run was ended. Saved work remains available.",
  "run.stopping": "Stopping the current work.",
  "run.awaiting_user": "Waiting for your direction.",
  "run.correcting": "Correction authorized.",
  "run.continued": "Continuation authorized.",
  "run.promoting": "Preparing the research account for publication.",
  "brief.assembled": "Prepared the task instructions and research context.",
  "turn.configured": "Applied the member's model and research settings.",
  "member.crashed": "The member's work stopped with a problem. Review the findings and technical activity log.",
  "member.rotated_midturn": "Saved a handoff after reaching the conversation limit.",
  "thread.resumed": "Resumed the saved research conversation.",
  "thread.rotated": "Saved a handoff for continuing in a new conversation.",
  "thread.tools_changed": "Prepared a new conversation with the current research tools.",
  "stage.running": "Started the next stage of work.",
  "stage.correcting": "Correcting the affected work before reviewing it again.",
  "p4.control_rejected": "The evaluation request needs correction. Earlier saved work remains recorded.",
  "p4.control_unknown": "The evaluation request's outcome is unconfirmed. Review the saved work.",
};

const attention = new Set(["run.failed", "member.crashed", "stage.mechanical_repair_stopped", "p4.control_rejected", "p4.control_unknown"]);

function heartbeatMessage(message) {
  const search = message.match(/^(searching|searched|search failed|opening page|opened page|reading page|read page|page retrieval failed|finding in page|find in page completed):\s*(.*)$/i);
  if (search) {
    const labels = { searching: "Searching literature", searched: "Literature search completed", "search failed": "Literature search failed",
      "opening page": "Opening source", "opened page": "Source opened", "reading page": "Retrieving source", "read page": "Source retrieved",
      "page retrieval failed": "Source retrieval failed", "finding in page": "Searching source text", "find in page completed": "Source text search completed" };
    return { message: `${labels[search[1].toLowerCase()]}: ${search[2]}`, tone: /failed/i.test(search[1]) ? "warn" : null };
  }
  const command = message.match(/^(running|completed|declined|failed(?: \(exit (-?\d+)\))?):/i);
  if (command) {
    const status = command[1].toLowerCase();
    return { message: command[2] !== undefined ? `Tool action returned exit code ${command[2]}.`
      : status === "running" ? "Running a tool action." : status === "completed" ? "Tool action completed."
        : status === "declined" ? "Tool action was declined." : "Tool action failed.",
    tone: status.startsWith("failed") || status === "declined" ? "warn" : null };
  }
  if (/^turn start:/i.test(message)) return { message: "Started work on the requested task." };
  if (/^writing:/i.test(message)) return { message: "Updating work files." };
  if (/^wrote:/i.test(message)) return { message: "Work files updated." };
  if (/^file change (failed|declined):/i.test(message)) return { message: "A work file update did not complete.", tone: "warn" };
  if (/^plan:/i.test(message)) return { message: "Updated the work plan." };
  if (message === "checking saved artifacts") return { message: "Checking saved work." };
  if (message === "artifact validation report returned") return { message: "Saved work checks returned." };
  if (message === "artifact validation could not complete") return { message: "Saved work checks could not complete.", tone: "warn" };
  if (message === "context compacted") return { message: "Summarized the conversation to continue working." };
  if (/^sub-agent activity:/i.test(message)) return { message: "Coordinating delegated work." };
  if (/^says:/i.test(message)) return { message: "A member update is recorded in the technical activity log." };
  return { message: "Work activity recorded. See the technical activity log for details." };
}

export function activitySummary(event = {}) {
  const type = event.type || "";
  const raw = typeof event.message === "string" ? event.message : "";
  const summary = { actor: roles[event.role] || "Research team", message: lifecycle[type], tone: attention.has(type) ? "warn" : null };
  if (type === "heartbeat") return { ...summary, ...heartbeatMessage(raw) };
  if (type === "stage.finished") return { ...summary, message: /\bfailed\b/i.test(raw) ? "This stage stopped with a problem. Review the findings." : /\bsucceeded\b/i.test(raw) ? "This stage completed." : "This stage finished.", tone: /\bfailed\b/i.test(raw) ? "warn" : null };
  if (type === "stage.validation" || type === "member.artifact_check") {
    const findings = Array.isArray(event.findings) ? event.findings.length : event.finding_count;
    const passed = /\bpassed\b/i.test(raw) || event.status === "passed";
    return { ...summary, message: passed ? "Saved work checks passed." : findings > 0 ? `Saved work checks reported ${findings} issue${findings === 1 ? "" : "s"}.` : "Saved work checks returned. Review any findings.", tone: !passed && findings > 0 ? "warn" : null };
  }
  if (type === "stage.mechanical_repair") return { ...summary, message: `The original authors are correcting the saved work${Number.isInteger(event.attempt) ? ` (attempt ${event.attempt})` : ""}.` };
  if (type === "stage.mechanical_repair_stopped") return { ...summary, message: event.reason === "unchanged_failure" ? "Automatic repair stopped because the same issue remained. Review the findings." : "Automatic repair stopped. Review the findings." };
  if (type === "p4.control_accepted") return { ...summary, message: ({ save_plan: "Evaluation plan saved.", run_batch: "Experiment request accepted.", checkpoint: "Evaluation progress saved.", request_decision: "Researcher direction requested.", complete: "Stage completion request accepted." }[event.operation] || "Evaluation request accepted.") };
  if (type === "experiment.progress") return { ...summary, message: "Running the next bounded experiment." };
  if (!summary.message && /\.(?:failed|crashed|error)$/.test(type)) return { ...summary, message: "A work operation reported a problem. Review the technical activity log.", tone: "warn" };
  return { ...summary, message: summary.message || "Work activity recorded. See the technical activity log for details." };
}
