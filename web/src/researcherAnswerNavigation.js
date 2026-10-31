import { issueAnswerPhase, issueKey, issueSourceIdentity, issueSourceTarget } from "./phaseWorkflow.js";
import { phaseQuestionAnchor } from "./phaseInputSummary.js";
import { proposalKey } from "./methodWorkspace.js";

// Route a linked question or saved copy using its recorded answer location, without guessing a model
// from its title or replacing its source with the current question version.
export function answerSourceNavigation({ projectId, source, question: linkedQuestion, questions = [], answers = [], proposals = [] }) {
  source ||= linkedQuestion && (issueSourceTarget(linkedQuestion) || { phase: linkedQuestion.phase, branch: linkedQuestion.branch || linkedQuestion.branch_id });
  if (!["P1", "P2", "P3", "P4", "P5"].includes(source?.phase) || !source.branch) return null;
  const identity = JSON.stringify(issueSourceIdentity({ explanation_target: source }));
  const answer = !linkedQuestion && answers.flatMap(current => [current, ...(current.history || [])].map(version => ({ ...version, attention_id: current.attention_id || current.issue_id })))
    .find(version => JSON.stringify(issueSourceIdentity({ explanation_target: version.question_ref || version.attention?.explanation_target })) === identity);
  const question = linkedQuestion || answer?.attention && { ...answer.attention,
    attention_id: answer.attention.attention_id || answer.attention_id,
    explanation_target: answer.attention.explanation_target || source };
  const anchors = question ? [...new Set([...(answer?.attention ? [phaseQuestionAnchor(answer.attention)] : []), phaseQuestionAnchor(question)])] : [];
  if (source.kind === "researcher_pause") anchors.push(`researcher-pause:${source.run_id}:${source.request_id}:${source.revision}`);
  if (source.kind === "p4_pause") anchors.push(`evaluation-pause:${source.run_id}:${source.request_id}:${source.revision}`);
  if (!anchors.length) return null;
  // Earlier answer versions render beside the current question. Its owner can
  // move, while the history anchor and scientific source above stay original.
  const owner = !linkedQuestion && question && !["researcher_pause", "p4_pause"].includes(source.kind)
    && questions.find(item => issueKey(item) === issueKey(question)) || question;
  const phase = owner ? issueAnswerPhase(owner) : source.phase;
  const branch = owner?.branch || owner?.branch_id || source.branch;
  const shared = ["P1", "P2"].includes(phase);
  const change = { phase, ...(!shared ? { branch } : {}) };
  const ownerSource = owner && (issueSourceTarget(owner) || owner.generation_ref) || source;
  if (phase === "P2" && ownerSource.run_id) {
    const model = owner?.scope?.model_ref;
    const modelId = model?.identity?.stable_id || model?.stable_id || owner?.affected_record_ids?.[0];
    const proposal = proposals.find(item => item.generation_ref?.run_id === ownerSource.run_id
      && (!ownerSource.package_id || !item.generation_ref.package_id || item.generation_ref.package_id === ownerSource.package_id)
      && (!modelId || item.method?.identity?.stable_id === modelId));
    if (proposal) change.p2ProposalKey = proposalKey(proposal);
  }
  return { change, scope: `${projectId}:${shared ? "trunk" : branch}:${phase}`, anchors };
}
