import test from "node:test";
import assert from "node:assert/strict";
import { phaseInputSummary, phaseInputScopeKey, phaseQuestionAnchor, phaseQuestionDraftKey, phaseQuestionKey } from "../src/phaseInputSummary.js";
import { issueCardEntries } from "../src/phaseUiState.js";
import { issueVersionKey } from "../src/phaseWorkflow.js";
import { populationChoice } from "./fixtures/researcher-decisions.mjs";

const modelRef = { stable_id: "method.a", version: 2, definition_sha256: "d".repeat(64) };
const scope = { projectId: "project.summary", phase: "P4", branch: "method.a", methodId: "method.a", modelRef };
const source = (id, overrides = {}) => ({ kind: "phase_issue", branch: "method.a", phase: "P4", family: "attention_items",
  generation_id: "generation.current", sha256: "a".repeat(64), run_id: "run.current", package_id: "package.current",
  entry_pointer: `/items/${id}`, object_id: id, ...overrides });
const question = (id, overrides = {}) => ({ attention_id: id, kind: "researcher_decision", branch: "method.a", phase: "P4",
  disposition: "open", question: `Question ${id}?`, scope: { kind: "project" },
  explanation_target: source(id), generation_ref: source(id), ...overrides });
const answerFor = (issue, overrides = {}) => ({ attention_id: issue.attention_id, question_ref: issue.explanation_target,
  attention: issue, scope: issue.scope, note: "The researcher supplied an account.", revision: 1,
  origin: "researcher_reported", ...overrides });
const summarize = (options = {}) => phaseInputSummary({ ...scope, ...options });
const counts = ({ questions: { total, answered, unanswered, unknown, unsaved } }) => ({ total, answered, unanswered, unknown, unsaved });

test("research question categories are disjoint and unsaved edits are a separate indicator", () => {
  const open = question("open"), answered = question("answered"), unknown = question("unknown");
  const answers = [answerFor(answered), answerFor(unknown, { origin: "unknown", note: "This remains unknown." })];
  const draft = new Map([[phaseQuestionDraftKey(scope.projectId, open), { text: "A local unsaved account.", origin: "researcher_reported" }]]);
  const result = summarize({ issues: [open, answered, unknown], answers, getDraft: (key) => draft.get(key) });
  assert.deepEqual(counts(result), { total: 3, answered: 1, unanswered: 1, unknown: 1, unsaved: 1 });
  assert.deepEqual(result.questions.items.map(({ state, unsaved }) => [state, unsaved]), [["unanswered", true], ["answered", false], ["unknown", false]]);
  assert.equal(result.questions.items[1].issue.researcher_answer, answers[0]);
  assert.equal(result.questions.items[2].issue.researcher_answer, answers[1]);
  assert.equal(Object.hasOwn(result, "can_start"), false);
});

test("shared representations count once and every destination exists in the canonical question list", () => {
  const item = question("shared"), answer = answerFor(item);
  const options = { ...scope, issues: [item, structuredClone(item)], attention: [item], answers: [answer] };
  const result = phaseInputSummary(options);
  assert.deepEqual(counts(result), { total: 1, answered: 1, unanswered: 0, unknown: 0, unsaved: 0 });
  const current = issueCardEntries(options).entries;
  assert.deepEqual(result.questions.items.map(({ anchor }) => anchor), current.map((issue) => `issue:${issueVersionKey(issue)}`));
  assert.equal(result.questions.items[0].draftKey, `issue-response:${JSON.stringify([scope.projectId, issueVersionKey(item)])}`);
});

test("team tasks, scientific findings, conversations and historical operational responses do not count", () => {
  const issues = [question("researcher"), question("legacy", { kind: undefined }),
    question("team", { kind: "research_task" }), question("finding", { kind: "nonblocking_application_conditions" }),
    question("conversation", { kind: "issue_explanation" }),
    ...["p4_pause", "researcher_pause", "project_context"].map((kind) => question(kind, { explanation_target: source(kind, { kind }) })),
  ];
  const answers = issues.filter((issue) => issue.attention_id !== "researcher" && issue.attention_id !== "legacy").map((issue) => answerFor(issue));
  const lookedUp = [];
  const result = summarize({ issues, answers, getDraft: (key) => { lookedUp.push(key); return { text: "Do not count this excluded editor." }; } });
  assert.deepEqual(result.questions.items.map(({ issue }) => issue.attention_id), ["researcher", "legacy"]);
  assert.equal(lookedUp.length, 2);
  assert.equal(summarize({ answers: [answerFor(issues.find((issue) => issue.attention_id === "p4_pause"))] }).questions.total, 0);
});

test("a saved question that left the open inbox remains counted without reviving superseded history", () => {
  const savedOnly = question("saved-only"), closed = question("closed", { disposition: "resolved" });
  const superseded = question("superseded", { disposition: "superseded" });
  const supersededStatus = question("superseded-status", { status: "superseded" });
  const result = summarize({ issues: [closed, superseded, supersededStatus], answers: [answerFor(savedOnly), answerFor(superseded), answerFor(supersededStatus)] });
  assert.deepEqual(result.questions.items.map(({ issue }) => issue.attention_id), [savedOnly.attention_id]);
  assert.equal(result.questions.answered, 1);
  assert.equal(summarize({ issues: [closed], answers: [answerFor(closed)] }).questions.answered, 1);
});

test("an old answer cannot answer a changed exact source even when stable ID and prose match", () => {
  const first = question("changed");
  const second = { ...first, explanation_target: { ...first.explanation_target, generation_id: "generation.next", sha256: "b".repeat(64) } };
  const oldAnswer = answerFor(first);
  const result = summarize({ issues: [second], answers: [oldAnswer] });
  assert.equal(result.questions.total, 1);
  assert.equal(result.questions.unanswered, 1);
  assert.equal(result.questions.items[0].source.generation_id, "generation.next");
  assert.notEqual(phaseQuestionKey(first), phaseQuestionKey(second));
});

test("only an explicit exact answer revision, source and scope permits applicability", () => {
  const first = question("carried"), oldAnswer = answerFor(first, { revision: 3, origin: "unknown" });
  const link = { attention_id: first.attention_id, answer_revision: 3, question_ref: first.explanation_target, reason: "The same data collection question still applies." };
  const current = { ...first, explanation_target: { ...first.explanation_target, generation_id: "generation.next" }, answer_applicability_refs: [link] };
  assert.equal(summarize({ issues: [current], answers: [oldAnswer] }).questions.unknown, 1);
  for (const changedLink of [{ ...link, answer_revision: 2 }, { ...link, reason: "" }, { ...link, question_ref: source(first.attention_id, { sha256: "c".repeat(64) }) }]) {
    assert.equal(summarize({ issues: [{ ...current, answer_applicability_refs: [changedLink] }], answers: [oldAnswer] }).questions.unanswered, 1);
  }
  const oldScope = { kind: "model", branch: scope.branch, model_ref: { ...modelRef, version: 1 } };
  const scopedAnswer = { ...oldAnswer, scope: oldScope };
  const currentScope = { kind: "model", branch: scope.branch, model_ref: modelRef };
  assert.equal(summarize({ issues: [{ ...current, scope: currentScope }], answers: [scopedAnswer] }).questions.unanswered, 1);
});

test("applicable saved revisions update counts without counting answer history as questions", () => {
  const item = question("revisions");
  const first = answerFor(item, { revision: 1, origin: "unknown" });
  const latest = answerFor(item, { revision: 2, note: "The collection schedule is now documented." });
  const result = summarize({ attention: [item], answers: [first, latest] });
  assert.deepEqual(counts(result), { total: 1, answered: 1, unanswered: 0, unknown: 0, unsaved: 0 });
  assert.equal(result.questions.items[0].issue.researcher_answer, latest);
});

test("phase and exact model scope stay aligned with the original question projection", () => {
  const exact = question("exact", { scope: { kind: "model", branch: scope.branch, model_ref: modelRef } });
  const otherVersion = question("version", { scope: { ...exact.scope, model_ref: { ...modelRef, version: 3 } } });
  const otherBranch = question("branch", { branch: "method.b", scope: { ...exact.scope, branch: "method.b" } });
  const project = question("project", { branch: "trunk" });
  const otherPhase = question("phase", { phase: "P3" });
  const carried = question("carried", { phase: "P3", target_phase: "P4" });
  const result = summarize({ issues: [exact, otherVersion, otherBranch, project, otherPhase, carried] });
  assert.deepEqual(result.questions.items.map(({ issue }) => issue.attention_id), ["exact", "project", "carried"]);
  assert.equal(result.questions.items.find(({ issue }) => issue.attention_id === "carried").issue.phase, "P3");
  assert.equal(summarize({ issues: [exact], modelRef: undefined }).questions.total, 0);
});

test("P5 editorial summaries stay with their report method and exclude upstream questions and pause editors", () => {
  const editorial = question("editorial", { phase: "P5", target_phase: "P5", scope: { kind: "model", branch: scope.branch, model_ref: modelRef } });
  const projectEditorial = question("project-editorial", { phase: "P5", target_phase: "P5" });
  const stale = { ...editorial, attention_id: "earlier-model", scope: { ...editorial.scope, model_ref: { ...modelRef, version: 1 } } };
  const upstream = question("upstream", { phase: "P5", target_phase: "P1" });
  const carried = question("carried", { phase: "P3", target_phase: "P5" });
  const pause = question("pause", { phase: "P5", explanation_target: source("pause", { kind: "researcher_pause", phase: "P5" }) });
  const result = summarize({ phase: "P5", issues: [editorial, projectEditorial, stale, upstream, carried, pause], answers: [answerFor(editorial)] });
  assert.deepEqual(result.questions.items.map(row => row.issue.attention_id), ["editorial", "project-editorial"]);
  assert.equal(result.questions.answered, 1); assert.equal(result.questions.unanswered, 1);
  assert.equal(summarize({ phase: "P5", branch: "method.b", issues: [projectEditorial] }).questions.total, 0);
});

test("P2 selected candidates include shared and intended questions, with exact identity checks", () => {
  const candidateSource = (id) => source(id, { branch: "trunk", phase: "P2" });
  const candidate = question("candidate", { phase: "P2", branch: "trunk", target_phase: "P2", scope: { kind: "model", branch: "trunk", model_ref: modelRef }, generation_ref: candidateSource("candidate"), explanation_target: candidateSource("candidate") });
  const shared = question("shared", { phase: "P2", branch: "trunk" });
  const legacyOther = question("other", { phase: "P2", branch: "trunk", scope: undefined, affected_record_ids: ["method.b"] });
  const legacyThis = { ...legacyOther, attention_id: "this", affected_record_ids: ["method.a"], explanation_target: candidateSource("this") };
  const options = { phase: "P2", issues: [candidate, shared, legacyOther, legacyThis] };
  assert.deepEqual(summarize(options).questions.items.map(({ issue }) => issue.attention_id), ["candidate", "shared", "this"]);
  assert.deepEqual(summarize({ ...options, modelRef: { ...modelRef, definition_sha256: "e".repeat(64) } }).questions.items.map(({ issue }) => issue.attention_id), ["shared", "this"]);
});

test("merely editing an existing saved response is clean; changed text or choices are unsaved", () => {
  const item = { ...populationChoice, phase: "P4", branch: scope.branch };
  const answer = answerFor(item, { selection: { option_id: "survivors", note: "For the cohort." }, note: "A persisted rendering of the answer." });
  const project = (draft) => summarize({ issues: [item], answers: [answer], getDraft: () => draft });
  assert.equal(project({ text: "For the cohort.", origin: "researcher_reported", choice: "option:survivors", editing: true }).questions.unsaved, 0);
  assert.equal(project({ text: "Changed target population.", origin: "researcher_reported", choice: "option:survivors" }).questions.unsaved, 1);
  const changedChoice = project({ text: "For the cohort.", origin: "unknown", choice: "unknown" });
  assert.equal(changedChoice.questions.unsaved, 1);
  assert.equal(changedChoice.questions.answered, 1);
  assert.equal(changedChoice.questions.unknown, 0);
  assert.equal(project(null).questions.unsaved, 0);
  assert.equal(summarize({ issues: [item], getDraft: () => ({ text: "", origin: "researcher_reported", choice: "" }) }).questions.unsaved, 0);
});

test("drafts of earlier exact sources do not mark the current question unsaved", () => {
  const first = question("draft"), current = { ...first, explanation_target: { ...first.explanation_target, generation_id: "generation.next" } };
  const drafts = new Map([[phaseQuestionDraftKey(scope.projectId, first), { text: "Earlier draft" }]]);
  const result = summarize({ issues: [current], getDraft: (key) => drafts.get(key) });
  assert.equal(result.questions.unsaved, 0);
  assert.notEqual(phaseQuestionDraftKey(scope.projectId, first), phaseQuestionDraftKey(scope.projectId, current));
  assert.notEqual(phaseQuestionDraftKey(scope.projectId, current), phaseQuestionDraftKey("another-project", current));
});

test("study understanding counts only confirmed contributions and pending interpretations in scope", () => {
  const project = { kind: "project" }, exact = { kind: "model", branch: scope.branch, model_ref: modelRef };
  const contextItem = (id, itemScope = project, status = "confirmed") => ({ item_id: id, revision: 2, statement: "Saved information.", status, scope: itemScope });
  const proposal = (id, item, status = "pending") => ({ amendment_id: id, item, status });
  const problemContext = { items: [contextItem("project"), contextItem("exact", exact), contextItem("old", { ...exact, model_ref: { ...modelRef, version: 1 } }), contextItem("retired", project, "superseded"), contextItem("unconfirmed", project, "proposed")],
    proposals: [proposal("shared", contextItem("shared")), proposal("model", contextItem("model", exact)), proposal("elsewhere", contextItem("elsewhere", { ...exact, branch: "method.b" })), proposal("old-version", contextItem("old-version", { ...exact, model_ref: { ...modelRef, version: 1 } })), proposal("confirmed", contextItem("confirmed"), "confirmed")],
    brief: { text: "An initial brief is not a saved context contribution." },
  };
  const result = summarize({ problemContext });
  assert.equal(result.understanding.saved, 2);
  assert.equal(result.understanding.pending, 2);
  assert.deepEqual(result.understanding.items.map(({ anchor }) => anchor), ["problem-context:project:2", "problem-context:exact:2"]);
  assert.deepEqual(result.understanding.proposals.map(({ anchor }) => anchor), ["proposed-understanding:shared", "proposed-understanding:model"]);
  assert.deepEqual(counts(result), { total: 0, answered: 0, unanswered: 0, unknown: 0, unsaved: 0 });
  const empty = summarize({ problemContext: { items: [], proposals: [] } });
  assert.deepEqual(empty.understanding, { items: [], proposals: [], saved: 0, pending: 0 });
});

test("navigation keys survive reordering and cosmetic source metadata but detect exact source and scope changes", () => {
  const item = question("navigation");
  const reordered = { ...item, title: "A clearer title", explanation_target: { label: "Display metadata", ...Object.fromEntries(Object.entries(item.explanation_target).reverse()) } };
  assert.equal(phaseQuestionKey(item), phaseQuestionKey(reordered));
  assert.equal(phaseQuestionAnchor(item), `issue:${issueVersionKey(item)}`);
  assert.equal(phaseInputScopeKey(scope), phaseInputScopeKey({ ...scope, modelRef: Object.fromEntries(Object.entries(modelRef).reverse()) }));
  for (const changed of [{ phase: "P3" }, { branch: "method.b" }, { modelRef: { ...modelRef, version: 3 } }]) assert.notEqual(phaseInputScopeKey(scope), phaseInputScopeKey({ ...scope, ...changed }));
});

test("copied answers never count as extra information, including earlier phases, pauses and damaged legacy links", () => {
  const current = question("current"), earlier = question("earlier", { phase: "P1", explanation_target: source("earlier", { phase: "P1" }) });
  const saved = answerFor(current, { context_ref: { item_id: "custom.answer-copy", revision: 1 } });
  const prior = answerFor(earlier, { context_ref: { item_id: "new.custom-copy", revision: 2 }, history: [{ context_ref: { item_id: "historical.custom-copy", revision: 1 } }] });
  const ref = { kind: "researcher_answer", attention_id: current.attention_id, question_ref: current.explanation_target, answer_revision: 1 };
  const item = (item_id, extra = {}) => ({ item_id, revision: 1, status: "confirmed", statement: "Keep this exact statement.", scope: { kind: "project" }, ...extra });
  const problemContext = { items: [item("context.answer.current", { answer_refs: [ref] }), item("context.answer.pause"), item("custom.answer-copy"), item("historical.custom-copy"), item("context.note"), item("context.interpretation", { answer_refs: [ref] })], proposals: [] };
  for (const phase of ["P1", "P2", "P3", "P4", "P5"]) {
    const result = summarize({ phase, issues: [current], answers: [saved, prior], problemContext });
    assert.deepEqual(result.understanding.items.map(row => row.item.item_id), ["context.note", "context.interpretation"], phase);
    assert.equal(result.understanding.saved, 2, phase);
  }
});

test("projection leaves saved questions, context, answers and local drafts unchanged", () => {
  const item = question("pure"), answer = answerFor(item), draft = { text: "A local change", origin: "unknown" };
  const options = { ...scope, issues: [item], answers: [answer], problemContext: { items: [], proposals: [] } };
  const before = JSON.stringify({ options, draft });
  const result = phaseInputSummary({ ...options, getDraft: () => draft });
  assert.equal(result.questions.unsaved, 1);
  assert.equal(JSON.stringify({ options, draft }), before);
});
