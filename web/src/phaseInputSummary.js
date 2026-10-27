import { issueCardEntries, issueDisplayKind } from "./phaseUiState.js";
import { issueIsOpen, issueKey, issueSourceIdentity, issueVersionKey } from "./phaseWorkflow.js";
import { answerContextOwner, contextApplies } from "./researcherDialogue.js";
import { decisionDraft } from "./researcherDecisions.js";

const ordered = (value) => value && typeof value === "object"
  ? Array.isArray(value) ? value.map(ordered) : Object.fromEntries(Object.keys(value).sort().map((key) => [key, ordered(value[key])]))
  : value ?? null;
const identity = (value) => JSON.stringify(ordered(value));

// Navigation retains the viewing scope separately from a question's original
// phase. Carried questions still open in the current phase and method.
export const phaseInputScopeKey = ({ phase, branch, methodId, modelRef }) => identity([phase, branch, methodId, modelRef]);
export const phaseQuestionKey = (issue) => identity([issueKey(issue), issueSourceIdentity(issue)
  || [issue.phase, issue.branch || issue.branch_id, issue.question_version_id]]);
export const phaseQuestionAnchor = (issue) => `issue:${issueVersionKey(issue)}`;
export const phaseQuestionDraftKey = (projectId, issue) => `issue-response:${JSON.stringify([projectId, issueVersionKey(issue)])}`;

function isCurrentQuestion(issue, scope) {
  // Report attention is only an editorial choice for this report's method.
  // Scientific questions carried to an upstream phase keep their own editor.
  if (scope.phase === "P5" && (issue.phase !== "P5" || (issue.branch || issue.branch_id) !== scope.branch
      || issue.target_phase && issue.target_phase !== "P5")) return false;
  if (["research_task", "scientific_issue"].includes(issueDisplayKind(issue))) return false;
  if (["p4_pause", "researcher_pause", "project_context"].includes(issueSourceIdentity(issue)?.kind)) return false;
  if (issue.disposition === "superseded" || issue.status === "superseded") return false;
  return issueIsOpen(issue) || Boolean(issue.researcher_answer);
}

function hasUnsavedDraft(issue, answer, cached) {
  if (!cached) return false;
  const draft = decisionDraft(issue, answer, cached);
  const baseline = decisionDraft(issue, answer);
  // The editor stores an unchanged baseline when entering edit mode. Only an
  // actual response change is an unsaved edit, not opening that editor.
  return ["note", "origin", "choice"].some((key) => draft[key] !== baseline[key]);
}

// This is an input summary, not a scientific sufficiency or launch-readiness
// assessment. Use the original editors' authoritative projection, including
// saved question snapshots that have legitimately left the open inbox.
// getDraft is injected so this projection never reads or changes browser state.
export function phaseInputSummary({ projectId, problemContext, contextAnswers, getDraft, ...scope }) {
  const projected = issueCardEntries(scope);
  const seen = new Set();
  const items = projected.entries.filter(issue => isCurrentQuestion(issue, scope)).flatMap((issue) => {
    const key = phaseQuestionKey(issue);
    if (seen.has(key)) return [];
    seen.add(key);
    const answer = issue.researcher_answer;
    const draftKey = phaseQuestionDraftKey(projectId, issue);
    return [{ key, issue, source: issueSourceIdentity(issue), anchor: phaseQuestionAnchor(issue), draftKey,
      state: answer ? answer.origin === "unknown" ? "unknown" : "answered" : "unanswered",
      unsaved: hasUnsavedDraft(issue, answer, getDraft?.(draftKey)),
    }];
  });
  const saved = (problemContext?.items || []).filter((item) => item.status === "confirmed"
    && !answerContextOwner(item, contextAnswers ?? scope.answers)
    && contextApplies(item.scope, scope.branch, scope.modelRef)).map((item) => ({
    key: identity([item.item_id, item.revision]), item, anchor: `problem-context:${item.item_id}:${item.revision}`,
  }));
  const proposals = (problemContext?.proposals || []).filter((proposal) => proposal.status === "pending"
    && !answerContextOwner(proposal.item, contextAnswers ?? scope.answers)
    && contextApplies(proposal.item?.scope, scope.branch, scope.modelRef)).map((proposal) => ({
    key: proposal.amendment_id, proposal, anchor: `proposed-understanding:${proposal.amendment_id}`,
  }));
  return {
    scopeKey: phaseInputScopeKey(scope),
    questions: { items, total: items.length,
      answered: items.filter((item) => item.state === "answered").length,
      unanswered: items.filter((item) => item.state === "unanswered").length,
      unknown: items.filter((item) => item.state === "unknown").length,
      unsaved: items.filter((item) => item.unsaved).length,
    },
    understanding: { items: saved, proposals, saved: saved.length, pending: proposals.length },
  };
}
