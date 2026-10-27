import { answerMatchesIssue, issueSourceIdentity } from "./phaseWorkflow.js";

// The active pause has its own response editor. Remove only the exact shared
// projection it owns; other requests, question versions and newer answers stay
// available in the general dialogue. Once work resumes, that dialogue owns the
// saved response again.
export function sequentialDialogueItems(run, attention = [], answers = []) {
  const request = run?.researcher_pause?.pending_request;
  const source = request?.explanation_target;
  const nonempty = value => typeof value === "string" && Boolean(value.trim());
  if (run?.state !== "awaiting_user" || !["P1", "P2", "P3", "P5"].includes(run.phase)
      || !nonempty(run.run_id) || !nonempty(run.branch_id)
      || !nonempty(request?.request_id) || !nonempty(request.stage_id)
      || !Number.isInteger(request.revision) || request.revision <= 0
      || source?.kind !== "researcher_pause" || source.phase !== run.phase || source.branch !== run.branch_id
      || source.run_id !== run.run_id || source.stage_id !== request.stage_id
      || source.request_id !== request.request_id || source.object_id !== request.request_id
      || source.revision !== request.revision || !nonempty(source.sha256)
      || run.project_id && source.project_id !== run.project_id) return { attention, answers };

  const sameQuestion = issue => JSON.stringify(issueSourceIdentity(request)) === JSON.stringify(issueSourceIdentity(issue));
  const saved = (run.researcher_pause.saved_answers || [])
    .filter(answer => answer.request_id === request.request_id && answer.request_revision === request.revision)
    .reduce((latest, answer) => !latest || answer.revision > latest.revision ? answer : latest, null);
  const ownsAnswer = shared => Boolean(saved?.answer_ref
    && saved.answer_ref.attention_id === (shared.attention_id || shared.issue_id)
    && saved.answer_ref.answer_revision === shared.revision && saved.note === shared.note
    && sameQuestion({ explanation_target: saved.answer_ref.question_ref })
    && sameQuestion({ explanation_target: shared.question_ref })
    && answerMatchesIssue(shared, { ...request, attention_id: saved.answer_ref.attention_id }));
  return {
    attention: attention.filter(issue => !sameQuestion(issue)),
    answers: answers.filter(shared => !ownsAnswer(shared)),
  };
}
