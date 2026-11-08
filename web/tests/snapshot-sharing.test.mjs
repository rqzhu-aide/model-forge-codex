import test from "node:test";
import assert from "node:assert/strict";
import { reuseUnchangedJson } from "../src/snapshotSharing.js";

const source = { branch: "method.a", phase: "P3", generation_id: "theory.one", sha256: "a".repeat(64) };
const snapshot = () => ({ scope: "project.a:method.a:P3", artifacts: { theories: [{ generation_ref: source, statement: "The bound requires independent donors." }] },
  progressRun: { run_id: "run.same", state: "running", progress: { stage: 1 } },
  pending: { answers: [{ attention_id: "question.same", revision: 1, note: "Use the donor mean." }] },
  readiness: { scope: "method.b:P4", ready: true, basis: { hash: "launch.one", records: [source], notation: { sha256: "launch.notation" }, model_version: 1 } },
  viewReadiness: { scope: "method.a:P3", ready: true, basis: { hash: "view.one", records: [source], notation: { sha256: "view.notation" }, model_version: 2 } },
  project: { settings: { model: "shared-model", effort: "high" } } });

test("equivalent poll responses reuse the complete snapshot without mutation", () => {
  const previous = snapshot(); const next = structuredClone(previous);
  const before = structuredClone(next);
  assert.equal(reuseUnchangedJson(previous, next), previous);
  assert.deepEqual(next, before);
  assert.equal(reuseUnchangedJson(null, next), next);
});

test("progress updates retain unchanged scientific children without dropping new answers", () => {
  const previous = snapshot(); const next = structuredClone(previous);
  next.progressRun.progress.stage = 2;
  next.pending.answers[0] = { ...next.pending.answers[0], revision: 2, note: "Retain the donor mean and uncertainty." };
  const result = reuseUnchangedJson(previous, next);
  assert.notEqual(result, previous);
  assert.equal(result.artifacts, previous.artifacts);
  assert.equal(result.readiness, previous.readiness);
  assert.equal(result.viewReadiness, previous.viewReadiness);
  assert.equal(result.progressRun.progress.stage, 2);
  assert.equal(result.pending.answers[0].revision, 2);
  assert.equal(previous.pending.answers[0].revision, 1);
});

test("same generation IDs do not hide changed source hashes or scientific wording", () => {
  const previous = snapshot(); const next = structuredClone(previous);
  next.artifacts.theories[0].generation_ref.sha256 = "b".repeat(64);
  next.artifacts.theories[0].statement = "The revised bound also requires a finite second moment.";
  const result = reuseUnchangedJson(previous, next);
  assert.equal(result.artifacts.theories[0].generation_ref.sha256, "b".repeat(64));
  assert.equal(result.artifacts.theories[0].statement, next.artifacts.theories[0].statement);
  assert.equal(previous.artifacts.theories[0].generation_ref.sha256, "a".repeat(64));
});

test("launch and reader readiness keep their own changed basis, notation, versions and settings", () => {
  const previous = snapshot(); const next = structuredClone(previous);
  next.readiness.basis = { ...next.readiness.basis, hash: "launch.two", model_version: 2, notation: { sha256: "launch.new" } };
  next.viewReadiness.basis.records = [{ ...source, generation_id: "theory.two", sha256: "c".repeat(64) }];
  next.project.settings.effort = "xhigh";
  const result = reuseUnchangedJson(previous, next);
  assert.deepEqual(result, next);
  assert.notEqual(result.readiness, previous.readiness);
  assert.notEqual(result.viewReadiness, previous.viewReadiness);
  assert.notEqual(result.readiness, result.viewReadiness);
  assert.equal(result.project.settings.effort, "xhigh");
});

test("removed and added JSON fields and reordered arrays remain observable", () => {
  const previous = { kept: { statement: "Preserved" }, removed: true, versions: [1, 2] };
  const next = { kept: { statement: "Preserved" }, added: null, versions: [2, 1] };
  const result = reuseUnchangedJson(previous, next);
  assert.deepEqual(result, next);
  assert.equal(result.kept, previous.kept);
  assert.equal(Object.hasOwn(result, "removed"), false);
  assert.deepEqual(reuseUnchangedJson([1, 2, 3], [1, 2]), [1, 2]);
});
