import { explanationRun, issueSourceIdentity, issueIsOpen } from "./phaseWorkflow.js";
import { compareDecisionPriority, decisionPriorityLabel } from "./researcherDecisions.js";

// Responsibility and destination come from the author, never from question wording.
const kinds = new Set(["researcher_decision", "research_task"]);
const phases = new Set(["P1", "P2", "P3", "P4", "P5"]);
export const isContextualRequest = (item) => Boolean(item && kinds.has(item.kind) && phases.has(item.target_phase));
// A draft belongs to one authored question in one project. A republished or
// changed question gets a fresh editor instead of inheriting an old response.
export function clarificationDraftKey(projectId, item) {
  const source = item.explanation_target || item.generation_ref || {};
  return JSON.stringify([projectId, item.attention_id, item.attention_version_id, item.branch || item.branch_id, item.phase,
    source.family, source.generation_id, source.sha256 || source.content_sha256,
    source.entry_pointer || item.entry_pointer, item.question, item.context_markdown,
    item.target_phase, item.affected_record_ids]);
}
const branchOf = (item) => item.branch || item.branch_id;
const matchesContext = (item, branch, phase) => item.target_phase === phase &&
  (item.scope?.kind === "project" || branchOf(item) === branch || (branchOf(item) === "trunk" && branch !== "trunk"));

export function requestsForScope(items, branch, phase) {
  const result = { decisions: [], tasks: [], earlier: [] };
  for (const item of Array.isArray(items) ? items : []) {
    if (!item || !issueIsOpen(item)) continue;
    const itemBranch = branchOf(item);
    if (isContextualRequest(item)) {
      // A trunk request is shared project work in this phase, including when
      // the researcher is viewing a method. Another method's requests stay local.
      if (!matchesContext(item, branch, phase)) continue;
      result[item.kind === "researcher_decision" ? "decisions" : "tasks"].push(item);
    } else if (item.phase === phase && itemBranch === branch) {
      result.earlier.push(item);
    }
  }
  return result;
}

export function savedClarificationsForScope(answers, branch, phase) {
  return (Array.isArray(answers) ? answers : []).filter((answer) =>
    typeof answer?.note === "string" && answer.note.trim() &&
    isContextualRequest(answer.attention) && answer.attention.kind === "researcher_decision" &&
    matchesContext(answer.attention, branch, phase));
}

// Resolved questions stay in their original position. The API orders open
// requests by these same fields, so answering a question never renumbers it.
const severityOrder = { blocking: 0, reassessment_required: 1, major: 2, minor: 3 };
const compareText = (a, b) => a === b ? 0 : a < b ? -1 : 1;
const decisionVersion = item => JSON.stringify([item.attention_id, issueSourceIdentity(item)]);
export function researcherDecisionCards(items, answers, branch, phase) {
  const cards = new Map(requestsForScope(items, branch, phase).decisions.map((item) =>
    [decisionVersion(item), { item, answer: null }]));
  for (const answer of savedClarificationsForScope(answers, branch, phase)) {
    const attentionId = answer.attention_id || answer.attention.attention_id;
    if (!attentionId) continue;
    const item = { ...answer.attention, attention_id: attentionId };
    const version = decisionVersion(item);
    const current = cards.get(version)?.answer;
    // A refresh that started before Save may return an older answer. Keep the
    // newest saved text and its exact original question together.
    if (current && (Date.parse(current.resolved_at) || 0) > (Date.parse(answer.resolved_at) || 0)) continue;
    cards.set(version, { item, answer });
  }
  return [...cards.values()].sort(({ item: a }, { item: b }) =>
    compareDecisionPriority(a, b) || (decisionPriorityLabel(a) || decisionPriorityLabel(b) ? 0 :
    (severityOrder[a.severity] ?? 4) - (severityOrder[b.severity] ?? 4) ||
    compareText([branchOf(a), a.phase, a.attention_id].join("\0"), [branchOf(b), b.phase, b.attention_id].join("\0"))));
}

export function correctionsForScope(runs, branch, phase) {
  return (Array.isArray(runs) ? runs : []).filter((run) => run && run.phase === phase && branchOf(run) === branch);
}

const orderedTarget = (value) => value && typeof value === "object" ? Array.isArray(value) ? value.map(orderedTarget)
  : Object.fromEntries(Object.keys(value).sort().map((key) => [key, orderedTarget(value[key])])) : value ?? null;
const correctionWork = (run) => JSON.stringify([
  run.intent === "assessment" || run.mode === "p3.assessment" ? run.assessment_id || run.run_id : "phase",
  orderedTarget(run.target),
]);

// A failed attempt remains in history. It needs current attention only until a
// later attempt takes over the same work, not merely another task in the phase.
export function currentCorrectionsForScope(corrections, runs, branch, phase) {
  const attempts = correctionsForScope(runs, branch, phase);
  return correctionsForScope(corrections, branch, phase).filter((run) => {
    const current = attempts.find((attempt) => attempt.run_id === run.run_id);
    if (current?.state && current.state !== "failed") return false;
    return !attempts.some((attempt) => attempt.run_id !== run.run_id && attempt.state && attempt.state !== "cancelled"
      && !explanationRun(attempt) && Date.parse(attempt.created_at) > Date.parse(run.created_at)
      && correctionWork(attempt) === correctionWork(run));
  });
}

export function requestSourceReferences(item) {
  const primary = item.generation_ref && {
    ...item.generation_ref,
    ...(item.generation_ref.entry_pointer == null && item.entry_pointer ? { entry_pointer: item.entry_pointer } : {}),
  };
  return [
    ...(primary ? [{ label: "Original request", reference: primary }] : []),
    ...(Array.isArray(item.related_source_refs) ? item.related_source_refs : []).filter(Boolean)
      .map((reference, index) => ({ label: `Related scientific source ${index + 1}`, reference })),
  ];
}

export function earlierSettingQuestions(questions, currentRequests) {
  const current = new Set((currentRequests || []).map((item) => item.question?.trim()));
  return (Array.isArray(questions) ? questions : []).flatMap((text, index) =>
    typeof text === "string" && !current.has(text.trim()) ? [{ text, index }] : []);
}
