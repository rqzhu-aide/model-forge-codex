import { readConversationDraft, saveConversationDraft } from "./assumptionConversations.js";
import { answerMatchesIssue, issueSourceIdentity } from "./phaseWorkflow.js";

// The reader projects authored work and recorded host attempts. It never infers
// a scientific outcome from whether a process completed successfully.
export function evaluationPlanItems(progress, settled = false) {
  const plan = progress?.plan || {};
  const amendments = Array.isArray(plan.amendments) ? plan.amendments : [];
  const tasks = [...(plan.work_items || []), ...amendments.flatMap((change) => change.added_work_items || [])];
  const deferred = new Set(amendments.flatMap((change) => change.deferred_work_item_ids || []));
  const ordering = [...amendments].reverse().find((change) => change.work_item_order?.length)?.work_item_order;
  const ledger = Array.isArray(progress?.ledger) ? progress.ledger : Array.isArray(progress?.ledger?.entries) ? progress.ledger.entries : [];
  return tasks.map((task, index) => {
    const attempts = ledger.filter((entry) => task.work_item_id && entry.work_item_id === task.work_item_id);
    const pending = progress.pending_batch?.work_item_id === task.work_item_id ? progress.pending_batch : null;
    const latest = attempts.at(-1);
    return { ...task, attempts, latest, deferred: deferred.has(task.work_item_id),
      status: pending?.status || (deferred.has(task.work_item_id) && !latest ? "deferred" : latest?.status) || (settled ? "not_run" : "planned"),
      display_order: ordering?.includes(task.work_item_id) ? ordering.indexOf(task.work_item_id) : ordering ? ordering.length + index : index };
  }).sort((a, b) => a.display_order - b.display_order);
}

// Match the current question to its recorded attempt. A past interrupted batch
// does not establish why a later scientific question needs the researcher's help.
export function evaluationRecovery(progress, request = progress?.pause_request) {
  if (!progress) return null;
  const current = !request || request.request_id === progress.pause_request?.request_id && request.revision === progress.pause_request?.revision;
  if (current && progress.execution_state_error) return { kind: "unknown", title: "Execution state needs checking",
    message: "The saved work could not be confirmed. Review this run's history before authorizing another attempt.",
    actionLabel: "Review saved work", feedback: { error: progress.execution_state_error } };
  const ledger = Array.isArray(progress.ledger) ? progress.ledger : Array.isArray(progress.ledger?.entries) ? progress.ledger.entries : [];
  const evidence = Array.isArray(request?.evidence_refs) ? request.evidence_refs : [];
  const references = new Set(evidence.map((reference) => reference?.attempt_id).filter(Boolean));
  const attempt = [...ledger].reverse().find((entry) => references.has(entry.attempt_id) && ["interrupted", "output_error"].includes(entry.status));
  if (attempt) return { kind: attempt.status, title: attempt.status === "interrupted" ? "Experiment interrupted" : "Experiment outputs need attention",
    message: attempt.status === "output_error"
      ? "Computation finished, but some declared outputs could not be retained. Available results remain provisional."
      : attempt.artifacts?.length ? "Retained results remain provisional. Review this attempt before continuing or finishing with the available evidence."
        : "The interrupted attempt is recorded. Review the available evidence before continuing or finishing this evaluation.",
    actionLabel: "Review evidence and direction", attempt };
  const retainedFeedback = evidence.find((reference) => reference?.control_feedback && typeof reference.control_feedback === "object" && !Array.isArray(reference.control_feedback))?.control_feedback;
  const feedback = current ? progress.control_feedback : retainedFeedback;
  if (!feedback || feedback.accepted === true) return null;
  if (feedback.execution_state === "unknown" || feedback.accepted !== false && (feedback.error || feedback.code)) {
    return { kind: "unknown", title: current ? "Request outcome needs checking" : "Recorded request outcome was unconfirmed",
      message: current ? "The latest request's outcome is unconfirmed. Inspect saved work before authorizing another attempt."
        : "The request's outcome was unconfirmed when this question was saved. Its original receipt remains available for inspection.",
      actionLabel: "Review saved work", feedback };
  }
  if (feedback.accepted === false) return { kind: feedback.code === "validation_unavailable" ? "validation_unavailable" : "rejected",
    title: feedback.code === "validation_unavailable" ? "Validation setup needs attention"
      : ({ run_batch: "Experiment request needs correction", save_plan: "Plan request needs correction", complete: "Completion request needs correction" }[feedback.operation] || "Request needs correction"),
    message: feedback.code === "validation_unavailable"
      ? "Validation could not check the scientific artifacts. Restore the validation setup before checking them again."
      : "This request was not accepted. The analyst needs to correct it; earlier saved work remains recorded.",
    actionLabel: "Review requested direction", feedback };
  return null;
}

export const directionDraftKey = (projectId, runId, request) => `model-forge:p4-direction:${projectId}:${runId}:${request.request_id}:${request.revision}`;

export const savedAnswerMatches = (saved, request) => Boolean(saved && saved.request_id === request.request_id && saved.request_revision === request.revision && Number.isInteger(saved.revision) && saved.revision >= 0);

export function latestDecisionAnswer(progress, request) {
  return [...(Array.isArray(progress?.saved_answers) ? progress.saved_answers : []), progress?.saved_answer]
    .filter((answer) => savedAnswerMatches(answer, request))
    .reduce((latest, answer) => !latest || answer.revision >= latest.revision ? answer : latest, null);
}

// The original question is part of the saved answer record. Do not reconstruct
// an earlier question from the currently paused question or a later revision.
export function savedDecisionHistory(progress, excludeCurrent = false) {
  const groups = new Map();
  for (const answer of [...(Array.isArray(progress?.saved_answers) ? progress.saved_answers : []), progress?.saved_answer]) {
    if (!answer?.request || !savedAnswerMatches(answer, answer.request)) continue;
    if (excludeCurrent && savedAnswerMatches(answer, progress?.pause_request || {})) continue;
    const key = JSON.stringify([answer.request_id, answer.request_revision]);
    const previous = groups.get(key);
    if (!previous || answer.revision >= previous.answer.revision) groups.set(key, { request: answer.request, answer });
  }
  return [...groups.values()];
}

// The evaluation editor owns these exact pause sources. Other runs, question
// versions and newer shared answers remain in the general dialogue.
export function empiricalDialogueItems(run, attention = [], answers = []) {
  if (run?.phase !== "P4" || !run.p4_progress) return { attention, answers };
  const active = run.state === "awaiting_user" ? run.p4_progress.pause_request : null;
  const owned = savedDecisionHistory(run.p4_progress, Boolean(active));
  if (active) owned.push({ request: active, answer: latestDecisionAnswer(run.p4_progress, active), active: true });
  const exactRequest = (request) => {
    const source = request?.explanation_target;
    return typeof run.run_id === "string" && Boolean(run.run_id.trim())
      && typeof run.branch_id === "string" && Boolean(run.branch_id.trim())
      && typeof request?.request_id === "string" && Boolean(request.request_id.trim())
      && Number.isInteger(request.revision) && request.revision > 0
      && source?.kind === "p4_pause" && source.phase === "P4" && source.branch === run.branch_id
      && source.run_id === run.run_id && source.request_id === request.request_id
      && source.object_id === request.request_id && source.revision === request.revision
      && typeof source.sha256 === "string" && source.sha256.trim();
  };
  const sameQuestion = (request, issue) => exactRequest(request)
    && JSON.stringify(issueSourceIdentity(request)) === JSON.stringify(issueSourceIdentity(issue));
  const sameAnswer = ({ request, answer }, shared) => Boolean(answer?.answer_ref
    && answer.answer_ref.attention_id === shared.attention_id
    && answer.answer_ref.answer_revision === shared.revision
    && answer.note === shared.note
    && sameQuestion(request, { explanation_target: answer.answer_ref.question_ref })
    && sameQuestion(request, { explanation_target: shared.question_ref })
    && answerMatchesIssue(shared, { ...request, attention_id: answer.answer_ref.attention_id }));
  return {
    answers: answers.filter((shared) => !owned.some((item) => sameAnswer(item, shared))),
    attention: attention.filter((issue) => !owned.some((item) => sameQuestion(item.request, issue)
      && (item.active || answers.some((shared) => sameAnswer(item, shared) && answerMatchesIssue(shared, issue))))),
  };
}

export function readDecisionDraft(key, saved, storage) {
  const fallback = { note: saved?.note || "", base_revision: saved?.revision || 0, ...(saved?.origin ? { origin: saved.origin } : {}) };
  try {
    const memory = storage ? null : readConversationDraft(key);
    const raw = memory ? JSON.stringify(memory) : (storage || globalThis.localStorage)?.getItem(key);
    if (!raw) return fallback;
    let parsed;
    try { parsed = JSON.parse(raw); } catch { parsed = raw; }
    const draft = typeof parsed === "string" ? { note: parsed, base_revision: 0 }
      : typeof parsed?.note === "string" && Number.isInteger(parsed.base_revision) && parsed.base_revision >= 0 ? parsed : fallback;
    return saved && draft.note.trim() === saved.note.trim() ? fallback : draft;
  } catch { return fallback; }
}

export function saveDecisionDraft(key, draft) {
  saveConversationDraft(key, draft);
  try { if (draft) globalThis.localStorage?.setItem(key, JSON.stringify(draft)); else globalThis.localStorage?.removeItem(key); return true; }
  catch { return false; }
}

export const decisionAnswerPayload = (request, note, revision, options = {}) => ({ request_id: request.request_id, expected_revision: request.revision, note: note.trim(), expected_answer_revision: revision,
  ...(request.scope ? { origin: options.origin || "researcher_reported" } : {}), ...(request.scope?.kind === "project" ? { save_to_context: true, context_expected_revision: options.contextRevision } : {}) });

export function continuationPayload({ request, action, saved, contextChoice, extraBudget, idempotencyKey }) {
  const ready = savedAnswerMatches(saved, request) && saved.revision > 0;
  if (action === "continue" && !ready) throw new Error("Save a response to this exact question before continuing.");
  return { request_id: request.request_id, expected_revision: request.revision, action, idempotency_key: idempotencyKey,
    ...(ready ? { answer_revision: saved.revision } : {}),
    ...(contextChoice ? { context_choice: contextChoice } : {}),
    ...(action === "continue" && Number(extraBudget) > 0 ? { additional_budget_seconds: Number(extraBudget) } : {}) };
}
