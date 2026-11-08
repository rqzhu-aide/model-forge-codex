import { issueCardEntries, issueDisplayKind } from "./phaseUiState.js";
import { answerMatchesIssue, issueAnswerPhase, issueKey, issueLabel, issueSourceIdentity } from "./phaseWorkflow.js";
import { answerContextOwner, contextApplies, contextAttribution, contextScopeIdentity } from "./researcherDialogue.js";
import { methodRequests } from "./methodWorkspace.js";
import { notationCorrectionApplies, notationCorrectionSource } from "./sharedNotation.js";

const phases = ["P1", "P2", "P3", "P4", "P5"];
const ordered = value => value && typeof value === "object"
  ? Array.isArray(value) ? value.map(ordered) : Object.fromEntries(Object.keys(value).sort().map(key => [key, ordered(value[key])]))
  : value ?? null;
const identity = value => JSON.stringify(ordered(value));
const sourceOf = answer => answer.question_ref || answer.attention?.explanation_target || issueSourceIdentity(answer.attention);
const sourceKey = source => identity(source && issueSourceIdentity({ explanation_target: source }));
const answerId = answer => answer.attention_id || answer.issue_id || issueKey(answer.attention || {});
const scopeOf = answer => answer.scope || answer.attention?.scope;
const ownerKey = answer => identity([answerId(answer), contextScopeIdentity(scopeOf(answer))]);
const versionKey = answer => identity([answerId(answer), sourceKey(sourceOf(answer)),
  sourceOf(answer) ? null : answer.attention?.question_version_id, contextScopeIdentity(scopeOf(answer))]);
const isQuestion = issue => !["research_task", "scientific_issue"].includes(issueDisplayKind(issue));

function answerVersions(answers = []) {
  return answers.flatMap(answer => [answer, ...(answer.history || [])].map(version => ({
    ...version, attention_id: answerId(version) || answerId(answer),
    // The API also carries minimal history rows used only to identify old
    // context mirrors. Those rows are not saved scientific responses.
    scope: scopeOf(version) || (!version.note && sourceKey(sourceOf(version)) === sourceKey(sourceOf(answer)) ? scopeOf(answer) : undefined),
  })));
}

function questionSnapshot(answer, questions) {
  const source = sourceOf(answer);
  const exact = questions.find(issue => issueKey(issue) === answerId(answer)
    && sourceKey(issue.explanation_target || issueSourceIdentity(issue)) === sourceKey(source));
  const snapshot = answer.attention || {};
  return { ...exact, ...snapshot, attention_id: answerId(answer),
    phase: snapshot.phase || exact?.phase || source?.phase,
    branch: snapshot.branch || snapshot.branch_id || exact?.branch || exact?.branch_id || source?.branch,
    target_phase: snapshot.target_phase || exact?.target_phase,
    scope: scopeOf(answer) || exact?.scope,
    explanation_target: source || exact?.explanation_target,
    generation_ref: snapshot.generation_ref || exact?.generation_ref || (source?.generation_id ? source : undefined),
  };
}

function answerApplies(answer, questions, scope) {
  const issue = questionSnapshot(answer, questions);
  return isQuestion(issue) && methodRequests([issue], scope.methodId, scope.branch,
    { includeShared: true, modelRef: scope.modelRef }).length > 0;
}

function noteSource(item) {
  return item.goal_source_ref || (item.source_refs || []).find(reference => reference.kind === "research_goal")
    || item.notation_source_ref || notationCorrectionSource(item) || null;
}

function notePhase(item, source) {
  // Evidence citations and the generic context dialogue target are not owners.
  return phases.includes(source?.phase) ? source.phase : phases.includes(item.phase) ? item.phase : null;
}

// Retain the same exact scope and anchors for researcher notes and team accounts.
// Only the former belong to the researcher's saved-input summary.
export function scopedContextNotes({ problemContext, contextAnswers, ...scope } = {}) {
  const ownerAnswers = contextAnswers ?? [...(scope.answers || []), ...(scope.applicableAnswers || [])];
  const retained = new Map();
  for (const item of problemContext?.items || []) {
    if (item.status !== "confirmed" || answerContextOwner(item, ownerAnswers)
        || !contextApplies(item.scope, scope.branch, scope.modelRef) || !notationCorrectionApplies(item, scope)) continue;
    const key = identity([item.item_id, contextScopeIdentity(item.scope)]);
    if (!retained.has(key) || (item.revision || 0) > (retained.get(key).revision || 0)) retained.set(key, item);
  }
  return [...retained].map(([key, item]) => {
    const source = noteSource(item);
    const noteKind = source?.kind === "research_goal" || item.topic === "research_goal" ? "goal"
      : source?.kind === "notation_entry" || item.topic === "notation_correction" ? "notation" : "other";
    return { kind: "note", key, anchor: `problem-context:${item.item_id}:${item.revision}`,
      phase: notePhase(item, source), title: noteKind === "goal" ? "Research goal correction"
        : noteKind === "notation" ? "Notation correction" : item.topic === "expectation" ? "Expectation" : "Saved note",
      source, scope: item.scope, item, contextItem: item, noteKind,
      attribution: contextAttribution(item, problemContext) };
  });
}

export function scopedSavedNotes(options = {}) {
  return scopedContextNotes(options).filter(note => note.attribution.author === "researcher");
}

function answerItem(answer, questions) {
  const issue = questionSnapshot(answer, questions);
  const source = sourceOf(answer);
  const recorded = answer.attention?.phase || questions.find(question => issueKey(question) === answerId(answer)
    && sourceKey(question.explanation_target || issueSourceIdentity(question)) === sourceKey(source))?.phase;
  // Group at the recorded answering phase. The separate navigation route may
  // lead to a newer owner, whose earlier-version disclosure keeps this source.
  const phase = recorded && phases.includes(issueAnswerPhase(issue)) ? issueAnswerPhase(issue) : null;
  const key = ownerKey(answer);
  return { kind: "answer", key, anchor: `saved-input:answer:${encodeURIComponent(key)}`, phase,
    title: recorded ? issueLabel(issue, true) : "Saved answer", source, scope: scopeOf(answer),
    issue: recorded ? { ...issue, researcher_answer: answer } : undefined, answer, readonly: !recorded,
    owner: { attention_id: answerId(answer), question_ref: source, answer_revision: answer.revision },
    unverifiedPhase: !phase, earlierAnswers: [] };
}

// Project-wide answers identify a context copy's owner; they never admit that
// owner's response into the selected proposal or model. Admission starts only
// from the selected view's answer arrays, with exact scope checked again here.
export function savedInputProjection({ problemContext, contextAnswers, answers = [], applicableAnswers = [],
  issues = [], attention = [], ...scope } = {}) {
  const questions = methodRequests([...issues, ...attention], scope.methodId, scope.branch,
    { includeShared: true, modelRef: scope.modelRef });
  const scopedAnswers = answerVersions([...answers, ...applicableAnswers]);
  const ownerAnswers = answerVersions(contextAnswers ?? [...answers, ...applicableAnswers]);
  const current = issueCardEntries({ ...scope, issues, attention, answers: [...answers, ...applicableAnswers] }).entries.filter(isQuestion);
  const retained = new Map();
  for (const answer of scopedAnswers) {
    if (!answerId(answer) || typeof answer.note !== "string" || !answer.note.trim()
        || !answerApplies(answer, questions, scope)) continue;
    const key = versionKey(answer), previous = retained.get(key);
    if (!previous || (answer.revision || 0) > (previous.revision || 0)) retained.set(key, answer);
  }
  const owners = new Map();
  for (const answer of retained.values()) {
    // The current card already provides earlier-version reading at this owner.
    if (current.some(issue => issueKey(issue) === answerId(answer))) continue;
    const key = ownerKey(answer);
    if (!owners.has(key)) owners.set(key, []);
    owners.get(key).push(answer);
  }
  const items = [...owners.values()].map(versions => {
    const currentQuestion = questions.find(issue => issueKey(issue) === answerId(versions[0]));
    const exact = answer => Boolean(currentQuestion && sourceKey(sourceOf(answer)) === sourceKey(currentQuestion.explanation_target || issueSourceIdentity(currentQuestion)));
    const sorted = [...versions].sort((left, right) => Number(exact(right)) - Number(exact(left))
      || Number(Boolean(currentQuestion && answerMatchesIssue(right, currentQuestion)))
      - Number(Boolean(currentQuestion && answerMatchesIssue(left, currentQuestion))) || (right.revision || 0) - (left.revision || 0)
      || versionKey(left).localeCompare(versionKey(right)));
    const item = answerItem(sorted[0], questions);
    item.earlierAnswers = sorted.slice(1).map(answer => ({ ...answerItem(answer, questions),
      key: versionKey(answer), anchor: `saved-input:version:${encodeURIComponent(versionKey(answer))}` }));
    return item;
  });
  const admittedOwnerKeys = new Set([...retained.values()].map(ownerKey));
  const seenCopies = new Map();
  for (const contextItem of problemContext?.items || []) {
    if (contextItem.status !== "confirmed" || !contextApplies(contextItem.scope, scope.branch, scope.modelRef)
        || !notationCorrectionApplies(contextItem, scope)) continue;
    const owner = answerContextOwner(contextItem, ownerAnswers);
    if (!owner) continue;
    const known = ownerAnswers.find(answer => answer.context_ref?.item_id === contextItem.item_id
      || answerId(answer) === owner.attention_id && sourceKey(sourceOf(answer)) === sourceKey(owner.question_ref)
        && (owner.answer_revision == null || answer.revision === owner.answer_revision));
    if (known) {
      if (!admittedOwnerKeys.has(ownerKey(known))) continue;
      const item = items.find(candidate => candidate.key === ownerKey(known));
      if (item && (!item.contextItem || contextItem.revision > item.contextItem.revision)) item.contextItem = contextItem;
      continue;
    }
    // A damaged historical copy remains readable, without inventing a phase or
    // offering a second answer editor. Its publication phase is not its owner.
    if (current.some(issue => answerMatchesIssue({ ...owner, revision: owner.answer_revision }, issue))) continue;
    const key = identity([owner.attention_id || contextItem.item_id, sourceKey(owner.question_ref), contextScopeIdentity(contextItem.scope)]);
    const previous = seenCopies.get(key);
    if (previous && (previous.contextItem.revision || 0) >= (contextItem.revision || 0)) continue;
    const copy = { kind: "answer", key, anchor: `problem-context:${contextItem.item_id}:${contextItem.revision}`,
      phase: null, title: "Saved answer", source: owner.question_ref || null, scope: contextItem.scope,
      owner, contextItem, readonly: true, unverifiedPhase: true, earlierAnswers: [] };
    if (previous) items.splice(items.indexOf(previous), 1, copy);
    else items.push(copy);
    seenCopies.set(key, copy);
  }
  items.push(...scopedSavedNotes({ problemContext, contextAnswers: ownerAnswers, ...scope }));
  const grouped = new Map();
  for (const item of items) {
    const key = item.phase || (item.unverifiedPhase ? "unverified" : item.scope?.kind === "model" ? "model" : "project");
    if (!grouped.has(key)) grouped.set(key, { key, anchor: `saved-input:${key}`, phase: item.phase,
      label: item.phase ? `Phase ${item.phase.slice(1)}` : key === "model" ? "Notes for this model"
        : key === "project" ? "Project notes" : "Phase unverified",
      items: [], answerCount: 0, noteCount: 0, noteCounts: { goal: 0, notation: 0, other: 0 } });
    const group = grouped.get(key);
    group.items.push(item);
    if (item.kind === "answer") group.answerCount += 1;
    else { group.noteCount += 1; group.noteCounts[item.noteKind] += 1; }
  }
  const order = [...phases, "project", "model", "unverified"];
  const groups = [...grouped.values()].sort((left, right) => order.indexOf(left.key) - order.indexOf(right.key));
  return { groups, items };
}
