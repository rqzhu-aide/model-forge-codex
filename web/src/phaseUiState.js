import { explanationRun, issueKey, issuesForPhase, answerMatchesIssue } from "./phaseWorkflow.js";
import { methodRequests } from "./methodWorkspace.js";
import { humanLabel, TERMINAL } from "./research.js";
import { compareDecisionPriority } from "./researcherDecisions.js";

// Purpose color is stable. Attention depends only on the recorded request,
// disposition and answer, never on the phrasing of a scientific concern.
// Contextual requests have two contracted kinds. Other authored scientific
// kinds are findings; an absent legacy kind keeps its existing question view.
export const issueDisplayKind = (issue) => ["researcher_decision", "research_task"].includes(issue.kind) ? issue.kind : issue.kind ? "scientific_issue" : undefined;
export function issueDisplayState(issue) {
  const open = !issue.disposition || issue.disposition === "open";
  const kind = issueDisplayKind(issue);
  if (kind === "researcher_decision") {
    if (issue.researcher_answer) return { state: "saved", label: issue.researcher_answer.origin === "unknown" ? "Response saved · remains unknown" : "Response saved" };
    return open ? { state: "response", label: "Response needed" } : { state: "recorded", label: "Recorded decision" };
  }
  if (["scientific_issue", "research_task"].includes(kind) && open) return { state: "science", label: "Open scientific work" };
  return { state: "recorded", label: "Recorded issue" };
}

export function issueUrgency(issue) {
  if (issue.researcher_answer?.origin === "unknown") return { state: "unknown", label: "Still unknown" };
  if (issue.researcher_answer) return { state: "saved", label: "Instruction saved" };
  if (issue.disposition && issue.disposition !== "open") return { state: "recorded", label: "Recorded" };
  if (issue.severity === "blocking") return { state: "blocking", label: "Blocking" };
  if (issue.severity === "reassessment_required") return { state: "reassess", label: "Reassess" };
  return { state: "attention", label: "Discuss" };
}

export function issueCardEntries({ issues = [], attention = [], answers = [], phase, branch, methodId, modelRef }) {
  const all = new Map();
  for (const issue of [...issues, ...attention, ...answers.map((answer) => answer.attention).filter(Boolean)]) {
    if (!all.has(issueKey(issue))) all.set(issueKey(issue), issue);
  }
  const withAnswers = [...all.values()].map((issue) => {
    const candidates = [issue.researcher_answer, ...answers].filter(Boolean).filter((answer) => answerMatchesIssue({ ...answer, attention_id: answer.attention_id || answer.issue_id || issueKey(issue) }, issue));
    const legacyAttached = !issue.scope && !issue.researcher_answer?.question_ref && !issue.researcher_answer?.attention ? issue.researcher_answer : undefined;
    return { ...issue, researcher_answer: candidates.sort((a, b) => (b.revision || 0) - (a.revision || 0))[0] || legacyAttached };
  });
  const relatedScope = branch !== "trunk" || methodId
    ? methodRequests(withAnswers, methodId, branch, { includeShared: true, modelRef })
    : withAnswers.filter((issue) => (issue.branch || issue.branch_id) === "trunk");
  const carried = relatedScope.filter((issue) => issue.phase !== phase && issue.target_phase === phase);
  const isTeamWork = issue => ["research_task", "scientific_issue"].includes(issueDisplayKind(issue));
  const entries = [...issuesForPhase(withAnswers, phase, branch, methodId, modelRef), ...carried.filter(issue => !isTeamWork(issue))].sort(compareDecisionPriority);
  const related = carried.filter(isTeamWork).sort(compareDecisionPriority);
  return {
    entries,
    related,
    earlierAnswers: answers.filter((answer) => [...entries, ...related].some((issue) => issueKey(issue) === (answer.attention_id || answer.issue_id) && !answerMatchesIssue(answer, issue))),
  };
}

export function issueCardState({ entries = [], related = [], activePause = false, activePauseKind, savedPauseCount = 0, correctionCount = 0 }) {
  const responseCount = entries.filter((issue) => issueDisplayState(issue).state === "response").length;
  const scienceCount = entries.filter((issue) => issueDisplayState(issue).state === "science").length;
  if (activePause) return { state: "waiting", label: activePauseKind === "researcher" ? "Work waiting for your response" : activePauseKind === "setup" ? "Experiment setup needs attention" : "Evaluation waiting for your direction" };
  if (responseCount) return { state: "response", label: `${responseCount} ${responseCount === 1 ? "question needs" : "questions need"} your response` };
  if (correctionCount) return { state: "correction", label: "Work needs correction before it can be completed" };
  if (scienceCount) return { state: "science", label: "Open scientific work remains for the team" };
  if (related.length) return { state: "related", label: related.every((issue) => ["scientific_issue", "research_task"].includes(issueDisplayKind(issue))) ? "Related scientific work is linked below" : "Related questions are linked below" };
  if (entries.length || savedPauseCount) return { state: "history", label: "Recorded issues and responses remain available below" };
  return { state: "empty", label: "No decision is currently requested here. New scientific questions and choices will appear with their supporting context." };
}

export function methodPhaseContexts({ branches = [], methods = [], runs = [] }) {
  const ids = new Set([...branches.map((item) => item.branch_id), ...runs.map((run) => run.branch_id)].filter((id) => id && id !== "trunk"));
  return [...ids].map((branch) => {
    const record = branches.find((item) => item.branch_id === branch);
    const method = methods.find((item) => item.branch_id === branch || item.method_id === branch);
    return { branch, label: method?.title || method?.name || record?.method?.title || humanLabel(branch) };
  });
}

// Viewing a published evaluation never activates a method or starts work.
export function singleEvaluatedMethod({ branches = [], methods = [], runs = [] }) {
  const evaluated = methodPhaseContexts({ branches, methods, runs }).filter(({ branch }) =>
    branches.some((record) => record.branch_id === branch && record.phases?.p4?.length)
    || runs.some((run) => run.branch_id === branch && run.phase === "P4" && run.state === "published" && !explanationRun(run)));
  return evaluated.length === 1 ? evaluated[0].branch : null;
}

export function scientificPhaseRuns(runs, phase, branch) {
  const scope = ["P1", "P2"].includes(phase) ? "trunk" : branch;
  return runs.filter((run) => run.branch_id === scope && run.phase === phase && run.intent !== "assessment"
    && run.mode !== "p3.assessment" && !explanationRun(run))
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
}

export function latestScientificAttempt(runs, phase, branch) {
  const list = scientificPhaseRuns(runs, phase, branch);
  return list.find((run) => run.state === "awaiting_user") || list.find((run) => !TERMINAL.has(run.state)) || list[0];
}

// Launch availability follows the backend phase lock. Focused assessments and
// assumption explanations share it; issue explanations can run independently.
export function activePhaseRun(runs, phase, branch) {
  const scope = ["P1", "P2"].includes(phase) ? "trunk" : branch;
  return runs.find((run) => run.phase === phase && run.branch_id === scope
    && !["issue_explanation", "project_context", "model_dialogue", "issue_suggestions"].includes(run.assessment_purpose) && !TERMINAL.has(run.state)) || null;
}

function branchPhaseState(phase, branch, runs, branches, outputStatuses) {
  const list = scientificPhaseRuns(runs, phase, branch);
  const record = branches.find((item) => item.branch_id === branch);
  const published = list.find((run) => run.state === "published");
  const retained = Boolean(record?.phases?.[phase.toLowerCase()]?.length || published);
  const freshness = outputStatuses.find((item) => (item.branch || item.branch_id) === branch && item.phase === phase) || published?.method_status;
  const outdated = retained && freshness?.status === "needs_update";
  const latest = latestScientificAttempt(runs, phase, branch);
  const interrupted = ["failed", "cancelled"].includes(latest?.state);
  const details = { retained, retained_freshness: freshness || null, outdated, interrupted, latest_attempt: latest || null };
  if (latest?.state === "awaiting_user") return { ...details, state: "waiting", label: "Waiting for your direction" };
  if (latest && !TERMINAL.has(latest.state)) return { ...details, state: "running", label: "Work in progress" };
  if (interrupted) return { ...details, state: "interrupted", label: `Update ${latest.state}${retained ? " · earlier results available" : ""}` };
  if (outdated) return { ...details, state: "outdated", label: "Retained results need updating" };
  if (retained) return { ...details, state: "done", label: freshness?.status === "unknown" ? "Results available · freshness unknown" : "Results available" };
  return { ...details, state: "idle", label: "Explore" };
}

// A trunk view summarizes methods explicitly. A selected method is always exact,
// including while the researcher revisits the shared literature/method phases.
export function phaseNavigationState({ phase, branch = "trunk", runs = [], branches = [], methods = [], outputStatuses = [] }) {
  if (["P1", "P2"].includes(phase)) return branchPhaseState(phase, "trunk", runs, branches, outputStatuses);
  if (branch !== "trunk") return branchPhaseState(phase, branch, runs, branches, outputStatuses);
  const contexts = methodPhaseContexts({ branches, methods, runs }).map((item) => ({ ...item, ...branchPhaseState(phase, item.branch, runs, branches, outputStatuses) }));
  const interruptedCount = contexts.filter((item) => item.interrupted).length;
  const outdatedCount = contexts.filter((item) => item.outdated).length;
  const retainedCount = contexts.filter((item) => item.retained).length;
  const qualifications = [interruptedCount && `${interruptedCount} interrupted`, outdatedCount && `${outdatedCount} outdated`].filter(Boolean).join(" · ");
  for (const state of ["waiting", "running", "interrupted", "outdated", "done"]) {
    const count = contexts.filter((item) => item.state === state).length;
    if (!count) continue;
    const noun = count === 1 ? "model" : "models";
    const label = state === "waiting" ? `${count} ${noun} ${count === 1 ? "needs" : "need"} your direction`
      : state === "running" ? `Work in progress on ${count} ${noun}`
      : state === "interrupted" ? `Work interrupted on ${count} ${noun}`
      : state === "outdated" ? `Results need updating on ${count} ${noun}` : `Results on ${count} ${noun}`;
    return { state, label: qualifications ? `${label} · ${qualifications}` : label, contexts, interruptedCount, outdatedCount, retainedCount };
  }
  return { state: "idle", label: "Choose a model", contexts, interruptedCount, outdatedCount, retainedCount };
}
