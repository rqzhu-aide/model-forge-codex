import test from "node:test";
import assert from "node:assert/strict";
import { compareDecisionPriority, decisionDraft, decisionOptions, decisionSubmission } from "../src/researcherDecisions.js";
import { issueCardEntries } from "../src/phaseUiState.js";
import { researcherDecisionCards } from "../src/contextualRequests.js";
import { populationChoice, studyFact, resourceChoice, legacyQuestion } from "./fixtures/researcher-decisions.mjs";

test("authored priority outranks newer publication and alphabetical IDs with stable legacy fallback", () => {
  const inference = { ...populationChoice, attention_id: "a.newer", decision_priority: "inference", published_at: "2026-10-21T15:00:00Z" };
  const legacyB = { ...legacyQuestion, attention_id: "legacy.z" }, legacyA = { ...legacyQuestion, attention_id: "legacy.a" };
  const items = [resourceChoice, legacyB, studyFact, legacyA, inference, populationChoice];
  assert.deepEqual(issueCardEntries({ issues: items, phase: "P2", branch: "trunk" }).entries.map(item => item.attention_id), [populationChoice.attention_id, inference.attention_id, studyFact.attention_id, resourceChoice.attention_id, legacyB.attention_id, legacyA.attention_id]);
  assert.deepEqual(researcherDecisionCards(items, [], "trunk", "P2").slice(0, 4).map(({ item }) => item.attention_id), [populationChoice.attention_id, inference.attention_id, studyFact.attention_id, resourceChoice.attention_id]);
});

test("within an authored category publication precedes numeric authored array order", () => {
  const question = (id, date, index) => ({ ...populationChoice, attention_id: id, published_at: date, authored_order: index });
  const older = question("old", "2026-10-20T15:00:00Z", 0), ten = question("ten", "2026-10-21T15:00:00Z", 10), two = question("two", "2026-10-21T15:00:00Z", 2);
  assert.deepEqual([older, ten, two].sort(compareDecisionPriority).map(item => item.attention_id), ["two", "ten", "old"]);
  const pointer = item => ({ ...item, authored_order: undefined, entry_pointer: `/attention_items/${item.authored_order}` });
  assert.deepEqual([pointer(ten), pointer(two)].sort(compareDecisionPriority).map(item => item.attention_id), ["two", "ten"]);
});

test("an older interpretation question carried into a new phase stays above its resource choice", () => {
  const source = { ...populationChoice.explanation_target, phase: "P1" };
  const carried = { ...populationChoice, phase: "P1", target_phase: "P2", explanation_target: source, generation_ref: source };
  const answer = { attention_id: carried.attention_id, attention: carried, question_ref: source, note: "The intended population remains unknown.", origin: "unknown", revision: 1 };
  const result = issueCardEntries({ issues: [resourceChoice], attention: [carried], answers: [answer], phase: "P2", branch: "trunk" });
  assert.deepEqual(result.entries.map(item => item.attention_id), [carried.attention_id, resourceChoice.attention_id]);
  assert.equal(result.entries[0].phase, "P1"); assert.deepEqual(result.entries[0].explanation_target, source);
  assert.equal(result.entries[0].researcher_answer, answer); assert.deepEqual(result.related, []);
});

test("a selectable choice requires complete, distinct authored options", () => {
  assert.equal(decisionOptions(populationChoice).length, 2);
  for (const options of ["one or two", ["one", "two"], [{ id: "a", label: "A" }], [{ id: "a", label: "A", consequence: "Effect." }, { id: "a", label: "B", consequence: "Other effect." }]]) assert.deepEqual(decisionOptions({ ...populationChoice, options }), []);
  assert.deepEqual(decisionOptions({ ...populationChoice, response_kind: undefined }), []);
  assert.deepEqual(decisionOptions({ ...populationChoice, response_kind: "study_fact" }), []);
});

test("saved selection metadata restores the choice without parsing canonical prose", () => {
  const answer = { note: "Wording that is deliberately unrelated to the label.", selection: { option_id: "observed", label: "Patients still under observation", consequence: "An authored effect.", note: "My additional condition." } };
  assert.deepEqual(decisionDraft(populationChoice, answer), { choice: "option:observed", origin: "researcher_reported", note: "My additional condition." });
  assert.equal(decisionDraft(populationChoice, { note: "Selected option: Patients still under observation" }).choice, "custom");
  assert.equal(decisionSubmission(populationChoice, { choice: "option:missing" }), null);
});

test("republished contextual questions keep earlier answers with their original exact source", () => {
  const old = { ...populationChoice, explanation_target: { ...populationChoice.explanation_target, generation_id: "older", sha256: "b".repeat(64) }, generation_ref: { ...populationChoice.generation_ref, generation_id: "older", sha256: "b".repeat(64) } };
  const answer = { attention_id: old.attention_id, attention: old, question_ref: old.explanation_target, note: "The earlier instruction.", revision: 1 };
  const cards = researcherDecisionCards([populationChoice], [answer], "trunk", "P2");
  assert.equal(cards.length, 2);
  assert.equal(cards.find(({ item }) => item.explanation_target.generation_id === populationChoice.explanation_target.generation_id).answer, null);
  assert.equal(cards.find(({ item }) => item.explanation_target.generation_id === "older").answer, answer);
});
