import test from "node:test";
import assert from "node:assert/strict";
import { correctionsForScope, currentCorrectionsForScope, earlierSettingQuestions, requestSourceReferences, requestsForScope, researcherDecisionCards, savedClarificationsForScope } from "../src/contextualRequests.js";

const request = (attention_id, kind, target_phase, branch = "trunk") => ({ attention_id, kind, target_phase, branch, phase: "P1", disposition: "open", question: attention_id });

test("authored target phase and branch route decisions without using the producing phase", () => {
  const items = [request("setting", "researcher_decision", "P1"), request("method", "researcher_decision", "P2"), request("shared-theory", "researcher_decision", "P3"), request("other-method", "researcher_decision", "P3", "method.b"), request("own-theory", "researcher_decision", "P3", "method.a")];
  assert.deepEqual(requestsForScope(items, "trunk", "P1").decisions.map((item) => item.attention_id), ["setting"]);
  assert.deepEqual(requestsForScope(items, "trunk", "P2").decisions.map((item) => item.attention_id), ["method"]);
  assert.deepEqual(requestsForScope(items, "method.a", "P3").decisions.map((item) => item.attention_id), ["shared-theory", "own-theory"]);
  assert.deepEqual(requestsForScope(items, "method.a", "P4").decisions, []);
});

test("shared team tasks reach the relevant method phase while another method's tasks stay local", () => {
  const items = [request("shared", "research_task", "P4"), request("own", "research_task", "P4", "method.a"), request("other", "research_task", "P4", "method.b"), request("different-phase", "research_task", "P3", "method.a")];
  const selected = requestsForScope(items, "method.a", "P4");
  assert.deepEqual(selected.tasks.map((item) => item.attention_id), ["shared", "own"]);
  assert.deepEqual(selected.decisions, []);
  assert.deepEqual(requestsForScope(items, "trunk", "P1").tasks, []);
});

test("partial project work published on a method remains a team task across methods in its target phase", () => {
  const shared = { ...request("reference-check", "research_task", "P3", "method.a"), phase: "P3",
    scope: { kind: "project" }, disposition: "partially_fixed" };
  const closed = { ...shared, attention_id: "closed", disposition: "resolved" };
  const recordedDecision = { ...shared, attention_id: "decision", kind: "researcher_decision" };
  const before = JSON.stringify([shared, closed, recordedDecision]);
  for (const branch of ["method.a", "method.b", "method.c"]) {
    const selected = requestsForScope([shared, closed, recordedDecision], branch, "P3");
    assert.deepEqual(selected.tasks, [shared]);
    assert.deepEqual(selected.decisions, []);
    assert.deepEqual(requestsForScope([shared], branch, "P4").tasks, []);
  }
  assert.equal(JSON.stringify([shared, closed, recordedDecision]), before);
});

test("legacy questions are preserved by recorded phase and branch without inferred responsibility", () => {
  const legacy = { attention_id: "legacy", branch: "trunk", phase: "P1", question: "The researcher must choose a method." };
  const unknown = { ...legacy, attention_id: "future", kind: "future_kind", target_phase: "P2" };
  const result = requestsForScope([legacy, unknown, { ...legacy, attention_id: "resolved", disposition: "resolved" }], "trunk", "P1");
  assert.deepEqual(result.earlier, [legacy, unknown]);
  assert.deepEqual(result.decisions, []);
  assert.deepEqual(result.tasks, []);
  assert.deepEqual(requestsForScope([legacy], "method.a", "P1").earlier, []);
  assert.deepEqual(requestsForScope([legacy], "trunk", "P2").earlier, []);
});

test("source references preserve exact scientific entry pointers without mutation", () => {
  const scientific = { branch: "trunk", phase: "P1", family: "theory_literature", generation_id: "generation.theory", sha256: "a".repeat(64), entry_pointer: "/papers/2" };
  const original = { ...scientific, family: "research_basis", entry_pointer: "/attention_items/1" };
  const item = { generation_ref: original, entry_pointer: "/wrong/fallback", related_source_refs: [scientific] };
  const before = JSON.stringify(item);
  const references = requestSourceReferences(item);
  assert.deepEqual(references.map((entry) => entry.reference), [original, scientific]);
  assert.equal(JSON.stringify(item), before);
  assert.equal(requestSourceReferences({ generation_ref: { ...original, entry_pointer: undefined }, entry_pointer: "/attention_items/3" })[0].reference.entry_pointer, "/attention_items/3");
});

test("run corrections are scoped independently and old setting strings do not duplicate current requests", () => {
  const runs = [{ run_id: "match", phase: "P3", branch_id: "method.a" }, { run_id: "other", phase: "P3", branch_id: "method.b" }, { run_id: "phase", phase: "P4", branch: "method.a" }];
  assert.deepEqual(correctionsForScope(runs, "method.a", "P3").map((run) => run.run_id), ["match"]);
  assert.deepEqual(earlierSettingQuestions(["Current question", "Preserved old wording"], [{ question: "Current question" }]), [{ text: "Preserved old wording", index: 1 }]);
});

test("a newer phase attempt supersedes a historical correction without altering failed history", () => {
  const failed = { run_id: "run.old", phase: "P3", branch_id: "method.a", mode: "p3.theory_establishment", intent: "run", target: null, state: "failed", created_at: "2026-10-16T13:37:07.357Z" };
  const later = { ...failed, run_id: "run.new", mode: "p3.theory_revision", created_at: "2026-10-20T03:00:44.290Z" };
  for (const state of ["requested", "running", "validating", "correcting", "awaiting_user", "published", "failed"]) {
    const runs = [failed, { ...later, state }]; const before = JSON.stringify(runs);
    assert.deepEqual(currentCorrectionsForScope([failed], runs, "method.a", "P3"), [], state);
    assert.equal(JSON.stringify(runs), before, "history is unchanged");
  }
  const latestFailure = { ...later, state: "failed" };
  assert.deepEqual(currentCorrectionsForScope([failed, latestFailure], [latestFailure, failed], "method.a", "P3"), [latestFailure]);
});

test("unresolved failures stay current without a proven superseding attempt", () => {
  const failed = { run_id: "run.failed", phase: "P3", branch_id: "method.a", state: "failed", created_at: "2026-10-16T13:37:07.357Z" };
  const later = { ...failed, run_id: "run.later", state: "running", created_at: "2026-10-20T03:00:44.290Z" };
  for (const attempt of [
    { ...later, branch_id: "method.b" }, { ...later, phase: "P4" }, { ...later, state: "cancelled" },
    { ...later, intent: "assessment", mode: "p3.assessment" }, { ...later, assessment_purpose: "model_dialogue" },
    { ...later, target: { kind: "statement", object_id: "statement.other" } },
    { ...later, created_at: "2026-10-15T00:00:00Z" }, { ...later, created_at: "" },
  ]) assert.deepEqual(currentCorrectionsForScope([failed], [failed, attempt], "method.a", "P3"), [failed]);
  assert.deepEqual(currentCorrectionsForScope([failed], [], "method.a", "P3"), [failed]);
  assert.deepEqual(currentCorrectionsForScope([{ ...failed, created_at: "" }], [later], "method.a", "P3").map(run => run.run_id), [failed.run_id]);
  assert.deepEqual(currentCorrectionsForScope([failed], [{ ...failed, state: "correcting" }], "method.a", "P3"), []);
});

test("targeted work and separate assessment histories do not clear unrelated corrections", () => {
  const target = { branch: "method.a", family: "theory_record", generation_id: "theory.1", object_id: "statement.one" };
  const failed = { run_id: "run.failed", phase: "P3", branch_id: "method.a", target, state: "failed", created_at: "2026-10-16T13:37:07.357Z" };
  const later = { ...failed, run_id: "run.later", state: "running", created_at: "2026-10-20T03:00:44.290Z" };
  for (const nextTarget of [null, { ...target, object_id: "statement.two" }, { ...target, generation_id: "theory.2" }])
    assert.deepEqual(currentCorrectionsForScope([failed], [{ ...later, target: nextTarget }], "method.a", "P3"), [failed]);
  assert.deepEqual(currentCorrectionsForScope([failed], [{ ...later, target: Object.fromEntries(Object.entries(target).reverse()) }], "method.a", "P3"), []);
  const assessment = { ...failed, intent: "assessment", assessment_id: "assessment.one" };
  assert.deepEqual(currentCorrectionsForScope([assessment], [{ ...later, intent: "assessment", assessment_id: "assessment.two" }], "method.a", "P3"), [assessment]);
  assert.deepEqual(currentCorrectionsForScope([assessment], [{ ...later, intent: "assessment", assessment_id: "assessment.one" }], "method.a", "P3"), []);
});

test("saved clarifications use the original typed scope even after resolution and never infer legacy recipients", () => {
  const answer = (id, attention) => ({ attention_id: id, note: "Recorded answer", attention });
  const items = [answer("shared", { ...request("shared", "researcher_decision", "P3"), disposition: "resolved" }), answer("other", request("other", "researcher_decision", "P3", "method.b")), answer("p2", request("p2", "researcher_decision", "P2")), answer("legacy", { branch: "trunk", phase: "P1", question: "Choose a model" }), answer("task", request("task", "research_task", "P3")), { ...answer("blank", request("blank", "researcher_decision", "P3")), note: "  " }];
  assert.deepEqual(savedClarificationsForScope(items, "method.a", "P3").map((item) => item.attention_id), ["shared"]);
  assert.deepEqual(savedClarificationsForScope(items, "trunk", "P1"), []);
  assert.deepEqual(savedClarificationsForScope(items, "trunk", "P2").map((item) => item.attention_id), ["p2"]);
});

test("answered cards retain their question order when open requests disappear and answers arrive in save order", () => {
  const questions = [request("question.a", "researcher_decision", "P1"), request("question.b", "researcher_decision", "P1"), request("question.c", "researcher_decision", "P1")];
  const answer = (item) => ({ attention_id: item.attention_id, note: `Answer to ${item.question}`, attention: item });
  const before = researcherDecisionCards(questions, [], "trunk", "P1");
  const after = researcherDecisionCards([questions[1]], [answer(questions[2]), answer(questions[0])], "trunk", "P1");
  assert.deepEqual(after.map(({ item }) => item.attention_id), before.map(({ item }) => item.attention_id));
  assert.deepEqual(after.map(({ answer }) => Boolean(answer)), [true, false, true]);
  assert.equal(researcherDecisionCards(questions, questions.map(answer), "trunk", "P1").length, 3);
});

test("latest saved answer survives stale refreshes without duplicating questions or losing its original context", () => {
  const attention = { ...request("question.a", "researcher_decision", "P1"), context_markdown: "Original mathematical context." };
  const old = { attention_id: attention.attention_id, attention, note: "Old answer", resolved_at: "2026-09-12T10:00:00Z" };
  const latest = { ...old, note: "Edited answer", resolved_at: "2026-09-12T11:00:00Z" };
  const staleOpen = { ...attention, question: "Stale open response" };
  for (const answers of [[old, latest], [latest, old]]) {
    const cards = researcherDecisionCards([staleOpen], answers, "trunk", "P1");
    assert.equal(cards.length, 1);
    assert.equal(cards[0].answer.note, "Edited answer");
    assert.equal(cards[0].item.context_markdown, attention.context_markdown);
    assert.equal(cards[0].item.question, attention.question);
  }
  assert.equal(researcherDecisionCards([], [latest], "trunk", "P2").length, 0);
});

test("question numbering retains backend severity and branch order across answers", () => {
  const minor = { ...request("question.a", "researcher_decision", "P3", "method.a"), severity: "minor" };
  const major = { ...request("question.z", "researcher_decision", "P3"), severity: "major" };
  const cards = researcherDecisionCards([minor], [{ attention_id: major.attention_id, attention: major, note: "Proceed under this assumption." }], "method.a", "P3");
  assert.deepEqual(cards.map(({ item }) => item.attention_id), [major.attention_id, minor.attention_id]);
});
