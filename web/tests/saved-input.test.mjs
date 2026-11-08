import test from "node:test";
import assert from "node:assert/strict";
import { savedInputProjection, scopedContextNotes, scopedSavedNotes } from "../src/savedInput.js";

const modelRef = { stable_id: "method.a", version: 2, definition_sha256: "d".repeat(64) };
const scope = { phase: "P4", branch: "method.a", methodId: "method.a", modelRef };
const source = (id, phase = "P1", extra = {}) => ({ kind: "phase_issue", phase, branch: "trunk", family: "attention_items",
  generation_id: `generation.${phase}`, sha256: "a".repeat(64), run_id: `run.${phase}`, package_id: `package.${phase}`,
  entry_pointer: `/items/${id}`, object_id: id, ...extra });
const question = (id, phase = "P1", extra = {}) => ({ attention_id: id, kind: "researcher_decision", phase,
  branch: "trunk", scope: { kind: "project" }, question: `Authored question ${id}?`, disposition: "open",
  explanation_target: source(id, phase), generation_ref: source(id, phase), ...extra });
const answer = (issue, extra = {}) => ({ attention_id: issue.attention_id, question_ref: issue.explanation_target,
  attention: issue, scope: issue.scope, note: "Keep the researcher's exact $x^2$ account.", revision: 1,
  origin: "researcher_reported", ...extra });
const note = (id, extra = {}) => ({ item_id: id, revision: 1, status: "confirmed", scope: { kind: "project" },
  statement: "Keep this exact correction: $\\alpha = 2$.", origin: "researcher_reported", ...extra });
const project = (options = {}) => savedInputProjection({ ...scope, ...options });

test("answers across phases use their recorded answering phase and count copies once", () => {
  const p1 = ["one", "two", "three"].map(id => question(id));
  const refreshed = question("four", "P2", { target_phase: "P1" });
  const p2 = ["five", "six"].map(id => question(id, "P2"));
  const answers = [...p1, refreshed, ...p2].map(issue => answer(issue, {
    context_ref: { item_id: `copy.${issue.attention_id}`, revision: 1 },
  }));
  const copies = answers.map(saved => note(saved.context_ref.item_id, { statement: saved.note }));
  const goal = note("goal", { topic: "research_goal", source_refs: [{ ...source("goal"), kind: "research_goal" }] });
  const result = project({ issues: [], answers, contextAnswers: answers, problemContext: { items: [...copies, goal] } });
  assert.deepEqual(result.groups.map(group => [group.phase, group.answerCount, group.noteCounts.goal]), [["P1", 4, 1], ["P2", 2, 0]]);
  assert.equal(result.items.find(item => item.answer?.attention_id === "four").issue.target_phase, "P1");
  assert.equal(result.items.find(item => item.answer?.attention_id === "one").contextItem.item_id, "copy.one");
});

test("current questions and their historical answers or mirrors stay at their existing editor", () => {
  const current = question("current", "P4", { branch: scope.branch });
  const previous = { ...current, explanation_target: source("current", "P3", { generation_id: "old" }) };
  const saved = answer(current, { revision: 3, context_ref: { item_id: "copy.current" }, history: [answer(previous)] });
  const result = project({ issues: [current], answers: [saved], problemContext: { items: [note("copy.current")] } });
  assert.deepEqual(result, { groups: [], items: [] });
  const fresh = { ...current, explanation_target: { ...current.explanation_target, generation_id: "fresh" } };
  assert.equal(project({ attention: [fresh], answers: [saved] }).items.length, 0);
});

test("edits and exact source versions remain one owner with separately readable older versions", () => {
  const original = question("stable", "P2");
  const updated = { ...original, question: original.question,
    explanation_target: { ...original.explanation_target, generation_id: "next", sha256: "b".repeat(64) } };
  const old = answer(original, { revision: 1, note: "The earlier scientific statement." });
  const latest = answer(updated, { revision: 3, note: "The current scientific statement.", history: [old] });
  const duplicateEdit = answer(updated, { revision: 2, note: "The intermediate edit." });
  const result = project({ issues: [updated], answers: [duplicateEdit, latest] });
  assert.equal(result.groups[0].answerCount, 1);
  const item = result.items[0];
  assert.equal(item.answer.revision, 3);
  assert.equal(item.earlierAnswers.length, 1);
  assert.equal(item.earlierAnswers[0].answer.note, old.note);
  assert.deepEqual(item.earlierAnswers[0].source, original.explanation_target);
  assert.notEqual(item.earlierAnswers[0].anchor, item.anchor);
});

test("minimal API history links identify mirrors without becoming ghost answers", () => {
  const issue = question("history-link", "P2");
  const saved = answer(issue, { revision: 2, history: [{ revision: 1, question_ref: issue.explanation_target,
    context_ref: { item_id: "copy.original", revision: 1 } }] });
  const result = project({ answers: [saved], problemContext: { items: [note("copy.original")] } });
  assert.equal(result.groups[0].answerCount, 1);
  assert.equal(result.items.length, 1);
  assert.equal(result.items[0].title, issue.question);
  assert.equal(result.items[0].contextItem.item_id, "copy.original");
  assert.equal(result.items[0].earlierAnswers.length, 0);
});

test("compact owners recover target phase from exact snapshots and retargeting cannot rewrite older ownership", () => {
  const snapshot = question("retarget", "P2", { target_phase: "P1" });
  const compact = { ...snapshot, target_phase: undefined };
  const saved = answer(snapshot);
  assert.equal(project({ issues: [compact], answers: [saved] }).items[0].phase, "P1");
  const updated = { ...snapshot, target_phase: "P3", explanation_target: { ...snapshot.explanation_target, generation_id: "retargeted" } };
  const result = project({ issues: [updated], answers: [saved] });
  assert.equal(result.items[0].phase, "P1");
  assert.equal(result.items[0].issue.target_phase, "P1");
  assert.deepEqual(result.items[0].source, snapshot.explanation_target);
});

test("answer and note scopes require exact branch, model version and definition", () => {
  const exactScope = { kind: "model", branch: scope.branch, model_ref: modelRef };
  const exact = question("exact", "P3", { branch: scope.branch, scope: exactScope });
  const wrongVersion = question("version", "P3", { branch: scope.branch,
    scope: { ...exactScope, model_ref: { ...modelRef, version: 1 } }, question: exact.question });
  const wrongDefinition = question("definition", "P3", { branch: scope.branch,
    scope: { ...exactScope, model_ref: { ...modelRef, definition_sha256: "e".repeat(64) } } });
  const wrongBranch = question("branch", "P3", { branch: "method.b", scope: { ...exactScope, branch: "method.b" } });
  const questions = [exact, wrongVersion, wrongDefinition, wrongBranch];
  const result = project({ answers: questions.map(issue => answer(issue)),
    problemContext: { items: questions.map(issue => note(issue.attention_id, { scope: issue.scope })) } });
  assert.deepEqual(result.items.map(item => item.answer?.attention_id || item.contextItem.item_id), ["exact", "exact"]);
  assert.equal(result.groups[1].label, "Notes for this model");
  assert.equal(project({ answers: [answer(exact)], modelRef: undefined }).items.length, 0);
});

test("verified P2 candidate answers follow their exact model after activation", () => {
  const ref = source("candidate", "P2");
  const candidate = question("candidate", "P2", { scope: { kind: "model", branch: "trunk", model_ref: modelRef }, generation_ref: ref });
  assert.equal(project({ answers: [answer(candidate)] }).items.length, 1);
  assert.equal(project({ answers: [answer(candidate)], modelRef: { ...modelRef, version: 3 } }).items.length, 0);
  assert.equal(project({ answers: [answer({ ...candidate, generation_ref: { ...ref, package_id: undefined } })] }).items.length, 0);
});

test("selected answer arrays admit records while project answers only identify mirror ownership", () => {
  const selected = answer(question("selected"));
  const other = answer(question("other"), { context_ref: { item_id: "copy.other" } });
  const result = project({ applicableAnswers: [selected], contextAnswers: [selected, other], problemContext: { items: [note("copy.other")] } });
  assert.deepEqual(result.items.map(item => item.answer?.attention_id), ["selected"]);
  assert.equal(project({ contextAnswers: [selected] }).items.length, 0);
});

test("genuine interpretations citing answers remain notes and evidence citations do not assign a phase", () => {
  const saved = answer(question("evidence"));
  const ref = { kind: "researcher_answer", attention_id: saved.attention_id, question_ref: saved.question_ref, answer_revision: 1 };
  const item = note("interpretation", { answer_refs: [ref], source_refs: [source("evidence", "P3")] });
  const result = project({ contextAnswers: [saved], problemContext: { dialogue_target: { phase: "P1" }, items: [item] } });
  assert.equal(result.items[0].kind, "note");
  assert.equal(result.items[0].phase, null);
  assert.equal(result.groups[0].label, "Project notes");
});

test("notes prefer explicit goal and notation owners and enforce admitted notation", () => {
  const goal = note("goal", { topic: "research_goal", source_refs: [source("evidence", "P3"), { ...source("goal", "P1"), kind: "research_goal" }] });
  const notationRef = { ...source("symbol", "P3", { branch: scope.branch }), kind: "notation_entry", entry_id: "symbol" };
  const notation = note("notation", { topic: "notation_correction", source_refs: [notationRef] });
  const options = { problemContext: { items: [notation, goal] }, admittedRecords: [notationRef] };
  assert.deepEqual(project(options).groups.map(group => [group.phase, group.noteCounts]), [
    ["P1", { goal: 1, notation: 0, other: 0 }], ["P3", { goal: 0, notation: 1, other: 0 }],
  ]);
  assert.equal(project({ ...options, admittedRecords: [] }).items.length, 1);
  assert.equal(project({ ...options, phase: "P2" }).items.length, 1);
});

test("retained note revision controls the anchor while keys survive revisions and reordering", () => {
  const first = note("retained"), latest = { ...first, revision: 3, statement: "The saved correction." };
  const pending = note("pending", { status: "proposed" });
  const before = project({ problemContext: { items: [first] } }).items[0];
  const after = project({ problemContext: { items: [latest, first, pending], proposals: [{ status: "pending", item: first }] } }).items[0];
  assert.equal(after.key, before.key);
  assert.equal(after.anchor, "problem-context:retained:3");
  assert.equal(after.contextItem.statement, latest.statement);
  assert.equal(scopedSavedNotes({ ...scope, problemContext: { items: [first, latest] } }).length, 1);
  assert.deepEqual(project({ problemContext: { items: [first, latest] } }).items, [after]);
});

test("display metadata in scope and source does not change identity or create another saved item", () => {
  const modelScope = { kind: "model", branch: scope.branch, model_ref: modelRef };
  const issue = question("metadata", "P3", { branch: scope.branch, scope: modelScope });
  const saved = answer(issue), plain = note("model-note", { scope: modelScope });
  const updatedScope = { ...modelScope, label: "The selected model", model_ref: { ...modelRef, title: "Clearer title" } };
  const updated = answer({ ...issue, question: "A clearer scientific question?", scope: updatedScope,
    explanation_target: { ...issue.explanation_target, label: "A clearer source label" } }, { revision: 2 });
  const before = project({ answers: [saved], problemContext: { items: [plain] } });
  const after = project({ answers: [saved, updated], problemContext: { items: [plain, { ...plain, scope: updatedScope, revision: 2 }] } });
  assert.equal(after.items.length, 2);
  assert.equal(after.items[0].key, before.items[0].key);
  assert.equal(after.items[0].anchor, before.items[0].anchor);
  assert.equal(after.items[1].key, before.items[1].key);
});

test("unknown responses retain original wording and damaged copies stay read-only with unverified phase", () => {
  const unknown = answer(question("unknown"), { origin: "unknown", note: "We still do not know this collection fact." });
  const mirror = note("context.answer.unroutable", { answer_refs: [{ kind: "researcher_answer", attention_id: "unroutable", question_ref: source("unroutable", "P2") }] });
  const result = project({ answers: [unknown], problemContext: { items: [mirror] } });
  assert.equal(result.groups[0].answerCount, 1);
  assert.equal(result.items[0].answer.origin, "unknown");
  assert.equal(result.items[0].answer.note, unknown.note);
  const damaged = result.items.find(item => item.readonly);
  assert.equal(damaged.phase, null);
  assert.equal(damaged.unverifiedPhase, true);
  assert.equal(damaged.contextItem.statement, mirror.statement);
  assert.equal(result.groups.at(-1).label, "Phase unverified");
});

test("a saved answer with only a publication reference cannot invent its answering phase", () => {
  const saved = { attention_id: "missing-snapshot", question_ref: source("missing-snapshot", "P2"),
    scope: { kind: "project" }, note: "A retained response without its original question snapshot.", revision: 1 };
  const result = project({ answers: [saved] });
  assert.equal(result.groups[0].label, "Phase unverified");
  assert.equal(result.items[0].phase, null);
  assert.equal(result.items[0].issue, undefined);
  assert.equal(result.items[0].title, "Saved answer");
  assert.equal(result.items[0].answer.note, saved.note);
});

test("exact pause source remains available and active pause copies are not counted when removed upstream", () => {
  const ref = source("request", "P3", { kind: "researcher_pause", branch: scope.branch,
    run_id: "run.pause", stage_id: "stage", request_id: "request", revision: 2 });
  const issue = question("request", "P3", { branch: scope.branch, explanation_target: ref });
  const saved = answer(issue, { context_ref: { item_id: "copy.pause" } });
  const result = project({ answers: [saved] });
  assert.deepEqual(result.items[0].source, ref);
  assert.equal(project({ answers: [], contextAnswers: [saved], problemContext: { items: [note("copy.pause")] } }).items.length, 0);
});

test("team tasks, pending proposals and drafts do not add saved input; projection is pure", () => {
  const task = question("task", "P3", { kind: "research_task" });
  const q = question("reading");
  const options = { ...scope, answers: [answer(task), answer(q)], problemContext: { items: [note("note")],
    proposals: [{ status: "pending", item: note("pending") }] }, drafts: [{ text: "A draft." }] };
  const before = structuredClone(options);
  const result = savedInputProjection(options);
  assert.equal(result.items.length, 2);
  assert.deepEqual(options, before);
  const reordered = savedInputProjection({ ...options, answers: [...options.answers].reverse() });
  assert.deepEqual(result.items.map(item => item.anchor).sort(), reordered.items.map(item => item.anchor).sort());
});

test("team and unverified accounts keep their exact sources and anchors outside researcher saved input", () => {
  const modelScope = { kind: "model", branch: scope.branch, model_ref: modelRef };
  const evidence = note("team.evidence", { origin: "evidence_supported", scope: modelScope, source_refs: [source("evidence", "P3")] });
  const assumption = note("team.assumption", { origin: "proposed_assumption" });
  const accepted = note("team.accepted");
  const unspecified = note("unverified", { origin: undefined });
  const reported = note("researcher"), unknown = note("researcher.unknown", { origin: "unknown" });
  const problemContext = { items: [evidence, assumption, accepted, unspecified, reported, unknown], proposals: [
    { status: "confirmed", item: { ...accepted, status: "proposed" }, confirmed_item_revision: accepted.revision },
  ] };
  const before = structuredClone(problemContext);
  for (const phase of ["P1", "P2", "P3", "P4", "P5"]) {
    const options = { ...scope, phase, problemContext };
    assert.deepEqual(scopedSavedNotes(options).map(row => row.item.item_id), ["researcher", "researcher.unknown"], phase);
    assert.equal(savedInputProjection(options).items.length, 2, phase);
    const notes = scopedContextNotes(options);
    const retained = notes.find(row => row.item.item_id === evidence.item_id);
    assert.deepEqual(retained.item.source_refs, evidence.source_refs);
    assert.equal(retained.anchor, "problem-context:team.evidence:1");
    assert.deepEqual(notes.find(row => row.item.item_id === accepted.item_id).attribution, { author: "team", confirmedByResearcher: true });
    assert.equal(notes.find(row => row.item.item_id === unspecified.item_id).attribution.author, "unverified");
    assert.equal(scopedContextNotes({ ...options, modelRef: { ...modelRef, version: 3 } }).some(row => row.item.item_id === evidence.item_id), false);
  }
  assert.deepEqual(problemContext, before);
  const corrected = { ...accepted, revision: 2, statement: "The researcher's subsequent correction." };
  assert.deepEqual(scopedSavedNotes({ ...scope, problemContext: { ...problemContext, items: [corrected] } }).map(row => row.item), [corrected]);
});
