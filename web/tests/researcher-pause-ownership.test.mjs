import test from "node:test";
import assert from "node:assert/strict";
import { sequentialDialogueItems } from "../src/researcherPauseOwnership.js";
import { issueCardEntries } from "../src/phaseUiState.js";

const source = { kind: "researcher_pause", project_id: "project.pause", phase: "P3", branch: "method.a",
  run_id: "run.paused", stage_id: "theory.stage", request_id: "request.one", object_id: "request.one",
  revision: 2, sha256: "a".repeat(64) };
const request = { request_id: "request.one", revision: 2, stage_id: source.stage_id,
  phase: "P3", branch: "method.a", question: "Which regime should the theory address?", explanation_target: source };
const attention = { attention_id: request.request_id, kind: "researcher_decision", phase: "P3", branch: "method.a",
  question: request.question, explanation_target: source };
const shared = { attention_id: request.request_id, revision: 3, note: "Use the observed regime.", attention, question_ref: source };
const saved = { request_id: request.request_id, request_revision: request.revision, revision: 1, note: shared.note,
  answer_ref: { kind: "researcher_answer", attention_id: shared.attention_id, answer_revision: shared.revision, question_ref: source } };
const run = { project_id: source.project_id, run_id: source.run_id, phase: source.phase, branch_id: source.branch,
  state: "awaiting_user", researcher_pause: { pending_request: request, saved_answers: [saved] } };
const unrelated = { ...attention, attention_id: "scientific.question", explanation_target: { ...source, kind: "phase_issue" } };
const projection = (value, attentionItems = [attention, unrelated], answerItems = [shared]) => sequentialDialogueItems(value, attentionItems, answerItems);

test("the active sequential pause owns its exact response while other questions keep their editors", () => {
  const inputs = structuredClone({ run, attention: [attention, unrelated], answers: [shared] });
  const before = structuredClone(inputs);
  const result = sequentialDialogueItems(inputs.run, inputs.attention, inputs.answers);
  assert.deepEqual(result, { attention: [unrelated], answers: [] });
  assert.deepEqual(inputs, before);
  assert.deepEqual(issueCardEntries({ ...result, phase: "P3", branch: "method.a" }).entries.map(item => item.attention_id), [unrelated.attention_id]);
  assert.deepEqual(projection({ ...run, researcher_pause: { pending_request: request, saved_answers: [] } }, [attention], []), { attention: [], answers: [] });
});

test("ownership follows every exact source field and does not absorb question history", () => {
  for (const change of [
    { project_id: "another.project" }, { phase: "P2" }, { branch: "method.b" }, { run_id: "another.run" },
    { stage_id: "another.stage" }, { request_id: "another.request" }, { object_id: "another.object" },
    { revision: 1 }, { sha256: "b".repeat(64) },
  ]) {
    const earlierSource = { ...source, ...change };
    const earlier = { ...attention, explanation_target: earlierSource };
    const answer = { ...shared, attention: earlier, question_ref: earlierSource };
    assert.deepEqual(projection(run, [attention, earlier], [shared, answer]), { attention: [earlier], answers: [answer] });
  }
});

test("only the latest exact saved pause response is removed, leaving unowned revisions reachable", () => {
  const first = { ...saved, revision: 1 };
  const latest = { ...saved, revision: 2, note: "Use both regimes.", answer_ref: { ...saved.answer_ref, answer_revision: 4 } };
  const newer = { ...shared, revision: 4, note: latest.note };
  const waiting = { ...run, researcher_pause: { pending_request: request, saved_answers: [latest, first] } };
  assert.deepEqual(projection(waiting, [], [shared, newer]), { attention: [], answers: [shared] });
  for (const change of [{ revision: 9 }, { note: "A newer shared instruction." }, { question_ref: null }, { attention_id: "another.answer" }]) {
    const unowned = { ...shared, ...change };
    assert.deepEqual(projection(run, [], [unowned]), { attention: [], answers: [unowned] });
  }
  assert.deepEqual(projection({ ...run, researcher_pause: { pending_request: request, saved_answers: [{ ...saved, answer_ref: null }] } }, [], [shared]), { attention: [], answers: [shared] });
});

test("resumed, terminal, incomplete and P4 runs retain the general dialogue", () => {
  const unchanged = { attention: [attention, unrelated], answers: [shared] };
  for (const value of [null, { ...run, state: "running" }, { ...run, state: "published" }, { ...run, phase: "P4" },
    { ...run, researcher_pause: null },
    ...[{ sha256: undefined }, { revision: 1 }, { stage_id: "other.stage" }, { project_id: "other.project" }].map(change => ({
      ...run, researcher_pause: { ...run.researcher_pause, pending_request: { ...request, explanation_target: { ...source, ...change } } },
    })),
  ]) assert.deepEqual(projection(value), unchanged);
});

test("the same ownership contract applies to shared and report phase pauses", () => {
  for (const phase of ["P1", "P2", "P3", "P5"]) {
    const target = { ...source, phase };
    const question = { ...request, phase, explanation_target: target };
    const issue = { ...attention, phase, explanation_target: target };
    const answer = { ...shared, attention: issue, question_ref: target };
    const own = { ...saved, answer_ref: { ...saved.answer_ref, question_ref: target } };
    const paused = { ...run, phase, researcher_pause: { pending_request: question, saved_answers: [own] } };
    assert.deepEqual(sequentialDialogueItems(paused, [issue], [answer]), { attention: [], answers: [] });
  }
});
