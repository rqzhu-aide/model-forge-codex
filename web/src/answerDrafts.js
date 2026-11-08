import { issueKey, issueSourceIdentity } from "./phaseWorkflow.js";

const identity = source => issueSourceIdentity({ explanation_target: source });
export const sameAnswerSource = (first, second) => JSON.stringify(identity(first)) === JSON.stringify(identity(second));
const answerSource = answer => answer?.question_ref || answer?.attention?.explanation_target || issueSourceIdentity(answer?.attention);

// The destination's revision can be in retained history even when an applicable
// answer from another source is shown. Stable-ID revisions are not its base.
export function exactAnswerSnapshot(issue, answers, attached = issue.researcher_answer) {
  const source = issue.explanation_target || issueSourceIdentity(issue);
  const rows = [attached, ...(answers || [])].filter(Boolean).flatMap(answer => [answer, ...(answer.history || [])]);
  const legacy = !issue.scope && !issue.question_version_id && issue.schema_version !== "1.2.0";
  const exact = rows.filter(answer => {
    const id = answer.attention_id || answer.issue_id || answer.attention?.attention_id || answer.attention?.issue_id;
    if (id && id !== issueKey(issue)) return false;
    const recorded = answerSource(answer);
    return recorded ? sameAnswerSource(recorded, source) : legacy && answer === attached;
  }).filter(answer => Number.isInteger(answer.revision) && answer.revision > 0)
    .sort((first, second) => second.revision - first.revision)[0] || null;
  const inherited = attached && answerSource(attached) && !sameAnswerSource(answerSource(attached), source);
  return { source, revision: exact?.revision ?? (inherited && !Array.isArray(answers) ? null : 0), answer: exact };
}

export function answerDraftBase(snapshot, cached) {
  if (!cached) return { source: snapshot.source, revision: snapshot.revision };
  const base = cached.base;
  // Older drafts retain their contents, but a revision must be reviewed before
  // being attached to them. Polling never supplies this missing metadata.
  return base && sameAnswerSource(base.source, snapshot.source)
    ? { source: base.source, revision: Number.isInteger(base.revision) && base.revision >= 0 ? base.revision : null }
    : { source: base?.source || snapshot.source, revision: null };
}

export const answerConflictKind = failure => failure.status !== 409 ? null
  : /source version changed|reopen the exact question|exact original question target/i.test(failure.message) ? "source"
  : /saved (?:response|answer) changed/i.test(failure.message) ? "answer" : null;
