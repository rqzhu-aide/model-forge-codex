import test from "node:test";
import assert from "node:assert/strict";
import { answerSourceNavigation } from "../src/researcherAnswerNavigation.js";
import { phaseQuestionAnchor } from "../src/phaseInputSummary.js";

const source = { kind: "phase_issue", phase: "P3", branch: "method.original", family: "attention_items",
  generation_id: "generation.original", sha256: "a".repeat(64), run_id: "run.original", object_id: "question.one", entry_pointer: "/items/0" };
const issue = { attention_id: "question.one", phase: source.phase, branch: source.branch, question: "Which regime is intended?", explanation_target: source };
const answer = { attention_id: issue.attention_id, revision: 1, question_ref: source, attention: issue };

test("saved-answer routes select the recorded phase and model while keeping the exact question anchor", () => {
  const result = answerSourceNavigation({ projectId: "project.one", source: { ...source, label: "Display metadata" }, answers: [answer] });
  assert.deepEqual(result, { change: { phase: "P3", branch: "method.original" }, scope: "project.one:method.original:P3", anchors: [phaseQuestionAnchor(issue)] });
  const inputs = { projectId: "project.one", source, answers: [answer] };
  const before = structuredClone(inputs); answerSourceNavigation(inputs); assert.deepEqual(inputs, before);
});

test("a changed question ID keeps its previous source and history destination separate", () => {
  const newer = { ...source, generation_id: "generation.next", sha256: "b".repeat(64) };
  const current = { ...answer, revision: 2, question_ref: newer, attention: { ...issue, explanation_target: newer }, history: [answer] };
  const result = answerSourceNavigation({ projectId: "project.one", source, answers: [current] });
  assert.deepEqual(result.anchors, [phaseQuestionAnchor(issue)]);
  assert.notDeepEqual(result.anchors, [phaseQuestionAnchor(current.attention)]);
});

test("P2 routes select the original proposal by producing run and model identity", () => {
  const ref = { ...source, phase: "P2", branch: "trunk", package_id: "package.original" };
  const original = { ...answer, question_ref: ref, attention: { ...issue, phase: "P2", branch: "trunk", explanation_target: ref,
    scope: { kind: "model", branch: "trunk", model_ref: { stable_id: "method.original", version: 1 } } } };
  const proposal = (id, model, run = ref.run_id) => ({ proposal_id: id, generation_ref: { run_id: run, package_id: ref.package_id }, method: { identity: { stable_id: model } } });
  const result = answerSourceNavigation({ projectId: "project.one", source: ref, answers: [original], proposals: [
    proposal("wrong-run", "method.original", "another.run"), proposal("wrong-model", "another.model"), proposal("original", "method.original"),
  ] });
  assert.deepEqual(result.change, { phase: "P2", p2ProposalKey: "run.original:original" });
  assert.equal(result.scope, "project.one:trunk:P2");
  assert.deepEqual(result.anchors, [phaseQuestionAnchor(original.attention)]);
});

test("pause routes retain their individual source anchors without requiring a general question editor", () => {
  for (const kind of ["researcher_pause", "p4_pause"]) {
    const ref = { ...source, kind, phase: kind === "p4_pause" ? "P4" : "P5", request_id: "request.one", revision: 2 };
    const result = answerSourceNavigation({ projectId: "project.one", source: ref });
    assert.deepEqual(result.change, { phase: ref.phase, branch: ref.branch });
    assert.deepEqual(result.anchors, [`${kind === "p4_pause" ? "evaluation-pause" : "researcher-pause"}:${ref.run_id}:${ref.request_id}:2`]);
  }
  assert.equal(answerSourceNavigation({ projectId: "project.one", source }), null, "Missing original question data never invents an editor anchor.");
});
