import { issueSourceIdentity } from "./phaseWorkflow.js";
import { phaseQuestionAnchor } from "./phaseInputSummary.js";
import { proposalKey } from "./methodWorkspace.js";

// Route a saved copy using its recorded question, without guessing a model
// from its title or replacing its source with the current question version.
export function answerSourceNavigation({ projectId, source, answers = [], proposals = [] }) {
  if (!["P1", "P2", "P3", "P4", "P5"].includes(source?.phase) || !source.branch) return null;
  const identity = JSON.stringify(issueSourceIdentity({ explanation_target: source }));
  const answer = answers.flatMap(current => [current, ...(current.history || [])].map(version => ({ ...version, attention_id: current.attention_id || current.issue_id })))
    .find(version => JSON.stringify(issueSourceIdentity({ explanation_target: version.question_ref || version.attention?.explanation_target })) === identity);
  const question = answer?.attention && { ...answer.attention,
    attention_id: answer.attention.attention_id || answer.attention_id,
    explanation_target: answer.attention.explanation_target || source };
  const anchors = question ? [...new Set([phaseQuestionAnchor(answer.attention), phaseQuestionAnchor(question)])] : [];
  if (source.kind === "researcher_pause") anchors.push(`researcher-pause:${source.run_id}:${source.request_id}:${source.revision}`);
  if (source.kind === "p4_pause") anchors.push(`evaluation-pause:${source.run_id}:${source.request_id}:${source.revision}`);
  if (!anchors.length) return null;
  const shared = ["P1", "P2"].includes(source.phase);
  const change = { phase: source.phase, ...(!shared ? { branch: source.branch } : {}) };
  if (source.phase === "P2" && source.run_id) {
    const model = question?.scope?.model_ref;
    const modelId = model?.identity?.stable_id || model?.stable_id || question?.affected_record_ids?.[0];
    const proposal = proposals.find(item => item.generation_ref?.run_id === source.run_id
      && (!source.package_id || !item.generation_ref.package_id || item.generation_ref.package_id === source.package_id)
      && (!modelId || item.method?.identity?.stable_id === modelId));
    if (proposal) change.p2ProposalKey = proposalKey(proposal);
  }
  return { change, scope: `${projectId}:${shared ? "trunk" : source.branch}:${source.phase}`, anchors };
}
