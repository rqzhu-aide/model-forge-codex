import { methodRequests } from "./methodWorkspace.js";
import { contextApplies } from "./researcherDialogue.js";
import { researchTaskAppliesToMethod } from "./researchTaskScope.js";

export const explanationRun = (run) => ["explanation", "issue_explanation", "project_context", "model_dialogue", "issue_suggestions"].includes(run?.assessment_purpose);

// Partial progress leaves team work pending without changing its authored status.
export const issueIsOpen = (issue) => !issue.disposition || issue.disposition === "open"
  || issue.kind === "research_task" && issue.disposition === "partially_fixed";

// Scope by recorded identities, never by matching titles or scientific prose.
export function issuesForPhase(issues = [], phase, branch, methodId, modelRef) {
  return issues.filter((issue) => {
    if (issue.phase !== phase) return false;
    if (!researchTaskAppliesToMethod(issue, methodId, branch, modelRef)) return false;
    if (methodId && phase === "P2") return methodRequests([issue], methodId, branch, { includeShared: true, modelRef }).length > 0;
    if (issue.scope?.kind === "project") return true;
    if (issue.scope?.kind === "model" && !contextApplies(issue.scope, branch, modelRef)) return false;
    return (issue.branch || issue.branch_id) === branch;
  });
}

export const issueKey = (issue) => issue.issue_id || issue.attention_id;
// Publication can refresh a question's context without moving its answer.
// A future method phase without a source branch has no answer editor yet;
// report choices are edited only on their own published report.
export function issueAnswerPhase(issue) {
  const target = issue.target_phase;
  const branch = issue.branch || issue.branch_id;
  if (!["P1", "P2", "P3", "P4", "P5"].includes(target)
      || issue.scope?.kind === "model" && ["P1", "P2"].includes(target)
      || target === "P5" && issue.phase !== "P5"
      || ["P3", "P4"].includes(target) && ["P1", "P2"].includes(issue.phase) && (!branch || branch === "trunk")) return issue.phase;
  return target;
}
// Earlier projections used the source object ID as a title even when the
// author supplied a statement. Keep identifiers in provenance, not row labels.
export function issueLabel(issue, preferQuestion = false) {
  const identifiers = new Set([issue.issue_id, issue.attention_id, issue.object_id, issue.finding_id, issue.explanation_target?.object_id].filter(Boolean));
  const labels = preferQuestion ? [issue.question, issue.title] : [issue.title, issue.question];
  return [...labels, issue.statement, issue.issue, issue.summary_markdown].find((value) => typeof value === "string" && value.trim() && !identifiers.has(value)) || "Research issue";
}
export function issueSourceIdentity(issue) {
  let target = issue?.explanation_target;
  if (!target) {
    const reference = issue?.generation_ref;
    if (!reference?.generation_id) return null;
    target = { ...reference, kind: "phase_issue", entry_pointer: issue.entry_pointer || reference.entry_pointer, object_id: issue.object_id || issue.attention_id };
  }
  const fields = target.kind === "project_context" ? ["kind", "project_id", "context_revision", "brief_revision", "sha256", "object_id"]
    : ["researcher_pause", "p4_pause"].includes(target.kind) ? ["kind", "project_id", "branch", "phase", "run_id", "stage_id", "request_id", "object_id", "revision", "sha256"]
    : ["kind", "branch", "phase", "family", "generation_id", "sha256", "run_id", "package_id", "entry_pointer", "object_id"];
  return Object.fromEntries(fields.map((field) => [field, target[field] ?? null]));
}
const sortedIdentity = (value) => value && typeof value === "object" ? Array.isArray(value) ? value.map(sortedIdentity) : Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortedIdentity(value[key])])) : value ?? null;
const stableIdentity = (value) => JSON.stringify(sortedIdentity(value));
export function answerMatchesIssue(answer, issue) {
  if ((answer.attention_id || answer.issue_id) !== issueKey(issue)) return false;
  const source = answer.question_ref ? issueSourceIdentity({ explanation_target: answer.question_ref }) : issueSourceIdentity(answer.attention);
  const destination = issueSourceIdentity(issue);
  if (source && destination && stableIdentity(source) === stableIdentity(destination)) return true;
  if (!source && !destination && !issue.scope && !issue.question_version_id && issue.schema_version !== "1.2.0") return true;
  return (issue.answer_applicability_refs || []).some((reference) => reference.attention_id === (answer.attention_id || answer.issue_id)
    && reference.answer_revision === (answer.revision || 0) && source && stableIdentity(issueSourceIdentity({ explanation_target: reference.question_ref })) === stableIdentity(source)
    && typeof reference.reason === "string" && reference.reason.trim()
    && (!(answer.scope || answer.attention?.scope) || (answer.scope || answer.attention.scope).kind === "project" || stableIdentity(answer.scope || answer.attention.scope) === stableIdentity(issue.scope)));
}
// A published replacement must not reuse an editor drafted for the old question.
export const issueVersionKey = (issue) => JSON.stringify([issueKey(issue), issue.phase, issue.branch || issue.branch_id,
  issue.explanation_target || issue.generation_ref || null, issue.title, issue.question, issue.summary_markdown, issue.context_markdown]);
export const furtherWorkKey = (project, branch, phase) => `further-work:${JSON.stringify([project, branch, phase])}`;

export function answerEffect(answer) {
  if (!answer) return "";
  const used = answer.applied_to || [];
  if (used.length) return "Used in earlier work. Editing saves a new response for future work; the earlier answer remains in that work's history.";
  if (answer.previously_applied_to?.length) return "Updated for future work. Earlier work used your previous response.";
  return "Saved for future work. Work already underway keeps its original instructions.";
}

export function issueSourceTarget(issue) {
  return issue?.explanation_target ? { ...issue.explanation_target, label: issueLabel(issue),
    statement: issue.summary_markdown || issue.question || issue.statement,
    responsible_role: issue.responsible_role || issue.raised_by } : null;
}

// Historical evidence must never inherit the current evaluation's summaries or cases.
export function empiricalReaderProps(artifacts = {}) {
  return { summaries: artifacts.empirical_summaries || [], loadErrors: artifacts.load_errors || [],
    diagnostics: artifacts.diagnostics || [], exhibits: artifacts.exhibits || [], implementations: artifacts.implementations || [],
    questions: artifacts.questions || artifacts.p4_questions || [], protocols: artifacts.protocols || [],
    cases: artifacts.cases || (artifacts.case_manifests || []).flatMap((manifest) => (manifest.cases || []).map((item) => ({ ...item, branch: manifest.branch, generation_ref: manifest.generation_ref }))) };
}
