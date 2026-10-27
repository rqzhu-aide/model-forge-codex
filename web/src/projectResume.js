import { issueCardEntries, issueDisplayState, methodPhaseContexts } from "./phaseUiState.js";
import { catalogMethodForProposal, catalogOnlyMethods, catalogSelectionKey, orderedProposals, proposalKey } from "./methodWorkspace.js";
import { issueKey } from "./phaseWorkflow.js";
import { phaseInputSummary } from "./phaseInputSummary.js";
import { goalCorrections } from "./phaseOneReader.js";

// The project header restates the research question in its opening sentences.
// Display equations and later paragraphs stay in the complete setting.
export function goalExcerpt(markdown, limit = 320) {
  // Heading lines label the setting; they are not part of the question.
  const text = String(markdown || "").replace(/^[ \t]*#+[ \t]+.*$/gm, "").trim();
  const first = text.split(/\n\s*\n|\$\$|\\\[/)[0];
  const paragraph = first.replace(/\s+/g, " ").trim();
  // The paragraph is unfinished only when a display equation interrupts it.
  const continues = /^(\$\$|\\\[)/.test(text.slice(first.length).trimStart());
  const complete = (piece) => /[.!?]["')\]]?$/.test(piece);
  if (paragraph.length <= limit && (!continues || complete(paragraph))) return paragraph;
  // Whole sentences only: a sentence that runs into a display equation is left out.
  let excerpt = "";
  for (const piece of paragraph.split(/(?<=[.!?]["')\]]?)\s+(?=[A-Z$\\(])/)) {
    if (!complete(piece) || `${excerpt} ${piece}`.trim().length > limit) break;
    excerpt = `${excerpt} ${piece}`.trim();
  }
  if (excerpt) return excerpt;
  if (paragraph.length <= limit) return `${paragraph}…`;
  // A single long sentence is cut at a word, never inside inline mathematics.
  let cut = paragraph.slice(0, paragraph.lastIndexOf(" ", limit) > 0 ? paragraph.lastIndexOf(" ", limit) : limit);
  if ((cut.match(/(?<!\\)\$/g) || []).length % 2) cut = cut.slice(0, cut.lastIndexOf("$"));
  return `${cut.trimEnd()}…`;
}

export function sharedGoalExcerpt(markdown, context, reference) {
  const clarifications = reference ? goalCorrections(context, reference) : [];
  // Separate excerpts preserve multiple saved accounts without selecting or
  // synthesizing one. The existing resume surface keeps its visual line limit.
  return clarifications.length ? clarifications.map(item => goalExcerpt(item.statement)).filter(Boolean).join(" · ") : goalExcerpt(markdown);
}

// Questions waiting for the researcher, grouped where they are answered. Each
// count follows the same projection as that phase's answer surface. Phase 5
// adds only indispensable editorial choices inside the report revision card.
export function p2DecisionContexts({ methods = [], proposals = [] }) {
  const direct = proposals.filter((proposal) => proposal.method && !proposal.no_method_proposed);
  const selections = [...orderedProposals(direct.filter((proposal) => proposal.is_current_package !== false)),
    ...direct.filter((proposal) => proposal.is_current_package === false)].map((proposal) => ({ proposal,
      method: proposal.method, catalogMethod: catalogMethodForProposal(proposal, methods), p2ProposalKey: proposalKey(proposal) }));
  selections.push(...catalogOnlyMethods(methods, direct).map((method) => ({ catalogMethod: method,
    method: { ...method, identity: method.identity || method.current_identity || method.definition?.identity }, p2ProposalKey: catalogSelectionKey(method) })));
  return selections;
}

export function waitingDecisions({ attention = [], answers = [], branches = [], methods = [], runs = [], proposals = [], p2ProposalKey: selectedKey }) {
  const methodBranches = methodPhaseContexts({ branches, methods, runs });
  const responses = (context) => issueCardEntries({ attention, answers, ...context }).entries
    // Shared setting questions count once at P1, even while their source card
    // retains the original question and scientific context.
    .filter((issue) => issueDisplayState(issue).state === "response"
      && !(issue.scope?.kind === "project" && issue.target_phase === "P1" && context.phase !== "P1"));
  const selections = p2DecisionContexts({ methods, proposals });
  const selected = selections.find((item) => item.p2ProposalKey === selectedKey) || selections[0];
  // Shared questions count once, in the selected card where they are visible.
  // Other groups then name only the additional questions at their destination.
  const seen = new Set();
  const p2 = (selected ? [selected, ...selections.filter((item) => item !== selected)] : []).flatMap(({ proposal, method, catalogMethod, p2ProposalKey }) => {
    const methodId = method.identity?.stable_id || catalogMethod?.method_id;
    const branch = catalogMethod?.branch_id || methodId;
    // An unregistered proposal's card keeps the issues from its producing run.
    const inSelection = (issue) => !proposal || catalogMethod || issue.generation_ref?.run_id === proposal.generation_ref?.run_id;
    const entries = responses({ attention: attention.filter(inSelection), answers: answers.filter((answer) => inSelection(answer.attention || {})),
      phase: "P2", branch, methodId, modelRef: method.identity }).filter((issue) => !seen.has(issueKey(issue)));
    entries.forEach((issue) => seen.add(issueKey(issue)));
    const version = method.identity?.version ?? method.version;
    const label = method.title || method.name || catalogMethod?.title || methodId;
    return entries.length ? [{ phase: "P2", branch, count: entries.length,
      methodLabel: `${label}${version != null ? ` · Version ${version}` : ""}`, p2ProposalKey }] : [];
  });
  const contexts = [["P1", "trunk"],
    ...["P3", "P4"].flatMap((phase) => methodBranches.map((item) => [phase, item.branch, item.label]))];
  const groups = contexts.flatMap(([phase, branch, label]) => {
    const method = branch === "trunk" ? null : methods.find((item) => item.branch_id === branch || item.method_id === branch);
    const count = responses({ phase, branch, methodId: method?.method_id, modelRef: method?.identity || method?.current_identity }).length;
    return count ? [{ phase, branch, count, methodLabel: branch === "trunk" ? null : label }] : [];
  });
  if (!selections.length) {
    const count = responses({ phase: "P2", branch: "trunk" }).length;
    if (count) p2.push({ phase: "P2", branch: "trunk", count, methodLabel: null });
  }
  const editorial = methodBranches.flatMap(({ branch, label }) => {
    const method = methods.find((item) => item.branch_id === branch || item.method_id === branch);
    const questions = phaseInputSummary({ attention, answers, phase: "P5", branch, methodId: method?.method_id,
      modelRef: method?.identity || method?.current_identity }).questions.items.filter(item => item.state === "unanswered");
    return questions.length ? [{ phase: "P5", branch, count: questions.length, methodLabel: label, anchors: questions.map(item => item.anchor) }] : [];
  });
  return [...groups.filter((item) => item.phase === "P1"), ...p2, ...groups.filter((item) => item.phase !== "P1"), ...editorial];
}
